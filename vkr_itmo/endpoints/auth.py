from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vkr_itmo.auth import create_access_token, verify_password, CurrentUser
from vkr_itmo.db.models import User
from vkr_itmo.db.session import get_session

api_router = APIRouter(prefix="/auth", tags=["auth"])


@api_router.get("/me")
def read_current_user(user: CurrentUser):
    return {"username": user.email, "id": user.id}


# @api_router.post("/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
# async def register(user_data: schemas.UserCreate, session: AsyncSession = Depends(get_session)):
#     """Зарегистрировать нового пользователя с хешированием пароля"""
#     existing_user = await session.execute(select(User).where(User.name == user_data.name))
#     if existing_user.scalar_one_or_none():
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")
#
#     hashed_password = get_password_hash(user_data.password)
#
#     new_user = User(
#         name=user_data.name,
#         password=hashed_password,
#         role_id=user_data.role_id,
#     )
#
#     session.add(new_user)
#
#     try:
#         await session.commit()
#         await session.refresh(new_user)
#     except IntegrityError as err:
#         await session.rollback()
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role_id") from err
#
#     return new_user
#
#
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
