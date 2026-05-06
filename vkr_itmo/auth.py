from datetime import datetime, timedelta
from typing import Annotated
from uuid import UUID

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vkr_itmo.db.models import User, UserRole
from vkr_itmo.db.session import get_session

bearer_scheme = HTTPBearer()

SECRET_KEY = "secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверяет пароль с хешем через bcrypt"""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def get_password_hash(password: str) -> str:
    """Хеширует пароль через bcrypt"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(email: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": email, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    session: AsyncSession = Depends(get_session),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError as err:
        raise credentials_exception from err

    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    return user


# Добавь это в vkr_itmo/auth.py


# ... твой существующий код ...


async def get_current_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if (
        current_user.role != UserRole.ADMIN
    ):  # Или current_user.role.value, зависит от реализации Enum
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. Admin only.",
        )
    return current_user


def check_self_or_admin(
    user_id: UUID, current_user: User = Depends(get_current_user)
) -> User:
    if current_user.role == UserRole.ADMIN:
        return current_user

    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own profile.",
        )
    return current_user


# vkr_itmo/auth.py или vkr_itmo/dependencies.py

from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from vkr_itmo.db.models import Course, User
from vkr_itmo.auth import get_current_user


async def get_course_owner(
        course_id: UUID,
        session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_user)
) -> Course:
    """
    Проверяет, что пользователь является владельцем курса (teacher)
    или админом
    """
    result = await session.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()

    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Если админ - пропускаем
    if current_user.role == UserRole.ADMIN:
        return course

    # Если не teacher - запрещаем
    if current_user.role != UserRole.TEACHER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers can manage courses"
        )

    # Если teacher, но не владелец курса - запрещаем
    if course.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage your own courses"
        )

    return course


async def get_course_teacher(
        course_id: UUID,
        session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_user)
) -> Course:
    """
    Проверяет, что пользователь - teacher или admin (для просмотра студентов курса)
    """
    result = await session.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()

    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Только teacher или admin могут смотреть список студентов
    if current_user.role!=UserRole.TEACHER and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers can view course students"
        )

    return course


# vkr_itmo/dependencies.py

from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from vkr_itmo.db.models import Lecture, Course, User
from vkr_itmo.auth import get_current_user


async def get_lecture_owner(
        lecture_id: UUID,
        session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_user)
) -> Lecture:
    """
    Проверяет, что пользователь является владельцем лекции (teacher)
    или админом
    """
    result = await session.execute(select(Lecture).where(Lecture.id == lecture_id))
    lecture = result.scalar_one_or_none()

    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found")

    # Если админ - пропускаем
    if current_user.role == UserRole.ADMIN:
        return lecture

    # Если не teacher - запрещаем
    if current_user.role != UserRole.TEACHER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers can manage lectures"
        )

    # Если teacher, но не владелец лекции - запрещаем
    if lecture.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage your own lectures"
        )

    return lecture


async def get_course_for_lecture(
        course_id: UUID,
        session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_user)
) -> Course:
    """
    Проверяет, что пользователь может создавать лекции в этом курсе
    (владелец курса или админ)
    """
    result = await session.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()

    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Если админ - пропускаем
    if current_user.role == UserRole.ADMIN:
        return course

    # Если не teacher - запрещаем
    if current_user.role != UserRole.TEACHER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers can create lectures"
        )

    # Если teacher, но не владелец курса - запрещаем
    if course.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create lectures in your own courses"
        )

    return course


# vkr_itmo/dependencies.py

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, HTTPException, status

from vkr_itmo.db.models import Session, Lecture, User
from vkr_itmo.auth import get_current_user


async def get_session_owner(
        session_id: UUID,
        session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_user)
) -> Session:
    """Проверяет, что пользователь владелец сессии"""
    result = await session.execute(select(Session).where(Session.id == session_id))
    sess = result.scalar_one_or_none()

    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    if current_user.role == UserRole.ADMIN:
        return sess

    if current_user.role != UserRole.TEACHER or sess.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )

    return sess


async def get_active_teacher_session(
        session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_user)
) -> Session | None:
    """Получает активную сессию учителя"""
    if current_user.role != UserRole.TEACHER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers have active sessions"
        )

    result = await session.execute(
        select(Session)
        .where(Session.teacher_id == current_user.id)
        .where(Session.ended_at == None)
    )
    return result.scalar_one_or_none()


# vkr_itmo/dependencies.py

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, HTTPException, status

from vkr_itmo.db.models import Quiz, SessionQuiz, QuizSubmission, User
from vkr_itmo.auth import get_current_user


async def get_quiz_owner(
        quiz_id: UUID,
        session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_user)
) -> Quiz:
    """Проверяет, что учитель владеет квизом"""
    result = await session.execute(select(Quiz).where(Quiz.id == quiz_id))
    quiz = result.scalar_one_or_none()

    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    if current_user.role != UserRole.TEACHER or quiz.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return quiz


async def get_active_session_quiz(
        session_id: UUID,
        quiz_id: UUID,
        db_session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_user)
) -> SessionQuiz:
    """Получает активный квиз в сессии"""
    result = await db_session.execute(
        select(SessionQuiz)
        .where(SessionQuiz.session_id == session_id)
        .where(SessionQuiz.quiz_id == quiz_id)
        .where(SessionQuiz.ended_at == None)
    )
    session_quiz = result.scalar_one_or_none()

    if not session_quiz:
        raise HTTPException(status_code=404, detail="Active quiz not found in this session")

    return session_quiz



CurrentUser = Annotated[User, Depends(get_current_user)]
