from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vkr_itmo.auth import create_access_token, verify_password, get_password_hash, CurrentUser
from vkr_itmo.db.models import User, UserRole
from vkr_itmo.db.session import get_session
from vkr_itmo.schemas.users import UserCreate, UserResponse

api_router = APIRouter(prefix="/auth", tags=["auth"])


@api_router.get("/me")
def read_current_user(user: CurrentUser):
    return {"username": user.email, "id": user.id}


@api_router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, session: AsyncSession = Depends(get_session)):
    """Зарегистрировать нового пользователя"""
    existing_user = await session.execute(select(User).where(User.email == user_data.email))
    if existing_user.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    hashed_password = get_password_hash(user_data.password)

    new_user = User(
        email=user_data.email,
        password_hash=hashed_password,
        full_name=user_data.full_name,
        role=UserRole(user_data.role.value),
    )

    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)

    return new_user


@api_router.post("/token")
async def login(
    email: str, password: str, session: AsyncSession = Depends(get_session)
):
    """Получить токен доступа с проверкой хешированного пароля"""
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(user.email)

    return {"access_token": access_token, "token_type": "bearer"}
