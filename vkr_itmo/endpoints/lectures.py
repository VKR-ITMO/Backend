from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
import secrets
import qrcode
from io import BytesIO
import base64

from vkr_itmo.db.session import get_session
from vkr_itmo.db.models import Lecture, Course, User
from vkr_itmo.auth import get_current_user
from vkr_itmo.auth import get_lecture_owner, get_course_for_lecture
from vkr_itmo.schemas.lectures import (
    LectureResponse,
    LectureCreate,
    LectureUpdate,
    LecturePublishResponse
)

api_router = APIRouter(prefix="/lectures", tags=["Lectures"])


@api_router.get("/courses/{course_id}/lectures", response_model=list[LectureResponse])
async def get_course_lectures(
        course_id: UUID,
        session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_user)
):
    """
    Получить список лекций курса
    """
    result = await session.execute(
        select(Lecture).where(Lecture.course_id == course_id)
    )
    return result.scalars().all()


@api_router.post("/courses/{course_id}/lectures", response_model=LectureResponse, status_code=status.HTTP_201_CREATED)
async def create_lecture(
        course_id: UUID,
        lecture_data: LectureCreate,
        session: AsyncSession = Depends(get_session),
        course: Course = Depends(get_course_for_lecture)
):
    """
    Создать лекцию в курсе (только для teachers)
    """
    lecture = Lecture(
        **lecture_data.model_dump(),
        course_id=course_id,
        teacher_id=course.teacher_id,
        status="DRAFT"
    )

    session.add(lecture)
    await session.commit()
    await session.refresh(lecture)
    return lecture


@api_router.get("/{lecture_id}", response_model=LectureResponse)
async def get_lecture(
        lecture_id: UUID,
        session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_user)
):
    """
    Получить лекцию по ID
    """
    result = await session.execute(select(Lecture).where(Lecture.id == lecture_id))
    lecture = result.scalar_one_or_none()

    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found")

    return lecture


@api_router.put("/{lecture_id}", response_model=LectureResponse)
async def update_lecture(
        lecture_id: UUID,
        lecture_data: LectureUpdate,
        session: AsyncSession = Depends(get_session),
        lecture: Lecture = Depends(get_lecture_owner)
):
    """
    Обновить лекцию (только владелец или админ)
    """
    update_data = lecture_data.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(lecture, key, value)

    await session.commit()
    await session.refresh(lecture)
    return lecture


@api_router.delete("/{lecture_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lecture(
        lecture_id: UUID,
        session: AsyncSession = Depends(get_session),
        lecture: Lecture = Depends(get_lecture_owner)
):
    """
    Удалить лекцию (только владелец или админ)
    """
    await session.delete(lecture)
    await session.commit()
    return None


@api_router.post("/free", response_model=LectureResponse, status_code=status.HTTP_201_CREATED)
async def create_free_lecture(
        topic: str,
        session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_user)
):
    """
    Создать свободную лекцию без курса (только для teachers)
    """
    if current_user.role != "TEACHER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers can create lectures"
        )

    lecture = Lecture(
        name=topic,
        topic=topic,
        course_id=None,  # Без курса
        teacher_id=current_user.id,
        status="DRAFT",
        is_free_session=True
    )

    session.add(lecture)
    await session.commit()
    await session.refresh(lecture)
    return lecture


@api_router.post("/{lecture_id}/publish", response_model=LecturePublishResponse)
async def publish_lecture(
        lecture_id: UUID,
        session: AsyncSession = Depends(get_session),
        lecture: Lecture = Depends(get_lecture_owner)
):
    """
    Опубликовать лекцию, сгенерировать access_code
    """
    # Генерируем уникальный 6-символьный код
    while True:
        access_code = secrets.token_hex(3).upper()  # 6 символов
        # Проверяем уникальность
        result = await session.execute(
            select(Lecture).where(Lecture.access_code == access_code)
        )
        if not result.scalar_one_or_none():
            break

    lecture.access_code = access_code
    lecture.status = "PUBLISHED"

    await session.commit()
    await session.refresh(lecture)

    # Генерируем QR code
    qr_data = f"lecture:{access_code}"
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(qr_data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Конвертируем в base64
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()

    qr_code_url = f"data:image/png;base64,{img_str}"

    return LecturePublishResponse(
        access_code=access_code,
        qr_code_url=qr_code_url
    )