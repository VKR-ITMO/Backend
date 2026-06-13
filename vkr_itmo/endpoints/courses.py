from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
import os
import uuid as uuid_lib
import logging
from typing import Optional

from vkr_itmo.db.session import get_session
from vkr_itmo.db.models import Course, CourseEnrollment, Lecture, Session, User, UserRole, CourseStatus
from vkr_itmo.auth import get_current_user
from vkr_itmo.auth import get_course_owner, get_course_teacher  # или из auth.py
from vkr_itmo.schemas.courses import CourseResponse, CourseCreate, CourseUpdate, CourseWithStats
from vkr_itmo.schemas.users import UserResponse
from vkr_itmo.achievements import check_and_award_achievements

api_router = APIRouter(prefix="/courses", tags=["Courses"])


@api_router.get("", response_model=list[CourseResponse])
async def get_courses(
        role: Optional[str] = Query(None, description="Фильтр по роли пользователя"),
        session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_user)
):
    """
    Получить список курсов с опциональным фильтром
    """
    query = select(Course)

    # Преподаватель всегда видит только свои курсы
    if current_user.role == UserRole.TEACHER:
        query = query.where(Course.teacher_id == current_user.id)
    elif current_user.role == UserRole.STUDENT:
        # Для студента - только курсы, на которые он записан
        query = (
            query
            .join(CourseEnrollment)
            .where(CourseEnrollment.student_id == current_user.id)
        )

    result = await session.execute(query)
    return result.scalars().all()


@api_router.post("", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
async def create_course(
        course_data: CourseCreate,
        session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_user)
):
    """
    Создать новый курс (только для teachers)
    """
    if current_user.role != UserRole.TEACHER:
        logging.warning(f"Access denied: user role is {current_user.role}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers can create courses"
        )

    # Проверяем уникальность code
    result = await session.execute(select(Course).where(Course.code == course_data.code))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Course with this code already exists"
        )

    course = Course(
        **course_data.model_dump(),
        teacher_id=current_user.id,
        status=CourseStatus.ACTIVE
    )

    session.add(course)
    await session.commit()
    await session.refresh(course)
    return course


@api_router.get("/{course_id}", response_model=CourseWithStats)
async def get_course(
        course_id: UUID,
        session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_user)
):
    """
    Получить курс с статистикой
    """
    # Получаем курс
    result = await session.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()

    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Получаем статистику
    # Количество студентов
    students_count = await session.execute(
        select(func.count()).where(CourseEnrollment.course_id == course_id)
    )

    # Количество лекций
    lectures_count = await session.execute(
        select(func.count()).where(Lecture.course_id == course_id)
    )

    total_students = students_count.scalar() or 0
    total_lectures = lectures_count.scalar() or 0

    return CourseWithStats(
        id=course.id,
        teacher_id=course.teacher_id,
        name=course.name,
        code=course.code,
        description=course.description,
        semester=course.semester,
        image_url=course.image_url,
        status=course.status,
        created_at=course.created_at,
        total_students=total_students,
        total_lectures=total_lectures
    )


@api_router.put("/{course_id}", response_model=CourseResponse)
async def update_course(
        course_id: UUID,
        course_data: CourseUpdate,
        session: AsyncSession = Depends(get_session),
        course: Course = Depends(get_course_owner)
):
    """
    Обновить курс (только владелец или админ)
    """
    update_data = course_data.model_dump(exclude_unset=True)

    # Если пытаются изменить code, проверяем уникальность
    if "code" in update_data and update_data["code"] != course.code:
        result = await session.execute(
            select(Course).where(Course.code == update_data["code"])
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Course with this code already exists"
            )

    for key, value in update_data.items():
        setattr(course, key, value)

    await session.commit()
    await session.refresh(course)
    return course


@api_router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
        course_id: UUID,
        session: AsyncSession = Depends(get_session),
        course: Course = Depends(get_course_owner)
):
    """
    Удалить курс (только владелец или админ)
    """
    await session.delete(course)
    await session.commit()
    return None


@api_router.get("/{course_id}/students", response_model=list[UserResponse])
async def get_course_students(
        course_id: UUID,
        session: AsyncSession = Depends(get_session),
        course: Course = Depends(get_course_teacher)
):
    """
    Получить список студентов на курсе (только teacher/admin)
    """
    result = await session.execute(
        select(User)
        .join(CourseEnrollment)
        .where(CourseEnrollment.course_id == course_id)
        .where(User.role == UserRole.STUDENT)
    )
    return result.scalars().all()


@api_router.post("/{course_id}/enroll", response_model=dict)
async def enroll_to_course(
        course_id: UUID,
        session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_user)
):
    """
    Записаться на курс (только для students)
    """
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can enroll to courses"
        )

    # Проверяем существование курса
    result = await session.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()

    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    if course.status != CourseStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot enroll to archived course"
        )

    # Проверяем, не записан ли уже
    existing = await session.execute(
        select(CourseEnrollment).where(
            CourseEnrollment.course_id == course_id,
            CourseEnrollment.student_id == current_user.id
        )
    )

    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already enrolled to this course"
        )

    enrollment = CourseEnrollment(
        course_id=course_id,
        student_id=current_user.id
    )

    session.add(enrollment)
    await session.commit()
    await session.refresh(enrollment)

    await check_and_award_achievements(current_user.id, session)

    return {"message": "Successfully enrolled", "enrollment_id": str(enrollment.id)}


@api_router.delete("/{course_id}/enroll", status_code=status.HTTP_204_NO_CONTENT)
async def unenroll_from_course(
        course_id: UUID,
        session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_user)
):
    """
    Отчислиться с курса (только для students)
    """
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can unenroll from courses"
        )

    # Находим запись о зачислении
    result = await session.execute(
        select(CourseEnrollment).where(
            CourseEnrollment.course_id == course_id,
            CourseEnrollment.student_id == current_user.id
        )
    )

    enrollment = result.scalar_one_or_none()

    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not enrolled to this course"
        )

    await session.delete(enrollment)
    await session.commit()
    return None


@api_router.post("/{course_id}/image", response_model=CourseResponse)
async def upload_course_image(
    course_id: UUID,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Загрузить изображение курса"""
    # Проверяем размер файла (макс 5 МБ)
    MAX_SIZE = 5 * 1024 * 1024
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 5 MB)")
    
    # Проверяем тип файла
    ALLOWED_TYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp']
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"File type {file.content_type} not allowed")
    
    # Генерируем уникальный ID для файла
    file_id = str(uuid_lib.uuid4())
    
    # Создаем директорию для изображений курсов если её нет
    upload_dir = "uploads/course_images"
    os.makedirs(upload_dir, exist_ok=True)
    
    # Сохраняем файл
    file_extension = file.filename.split('.')[-1] if file.filename else 'jpg'
    file_path = f"{upload_dir}/{file_id}.{file_extension}"
    
    with open(file_path, "wb") as f:
        f.write(content)
    
    # Обновляем курс
    result = await session.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()
    
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Проверяем права (только владелец или админ)
    if current_user.role != UserRole.ADMIN and course.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your course")
    
    # Сохраняем URL изображения
    course.image_url = f"/uploads/course_images/{file_id}.{file_extension}"
    
    await session.commit()
    await session.refresh(course)
    
    return course