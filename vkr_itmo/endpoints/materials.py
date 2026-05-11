from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from vkr_itmo.db.session import get_session
from vkr_itmo.db.models import CourseMaterial, Course, User, UserRole
from vkr_itmo.auth import get_current_user

api_router = APIRouter(prefix="/courses", tags=["Materials"])


class MaterialCreate(BaseModel):
    name: str
    description: Optional[str] = None
    url: Optional[str] = None
    file_size: Optional[str] = None


class MaterialResponse(BaseModel):
    id: UUID
    course_id: UUID
    name: str
    description: Optional[str] = None
    url: Optional[str] = None
    file_size: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


@api_router.get("/{course_id}/materials", response_model=list[MaterialResponse])
async def get_course_materials(
    course_id: UUID,
    db_session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Получить материалы курса"""
    result = await db_session.execute(
        select(CourseMaterial)
        .where(CourseMaterial.course_id == course_id)
        .order_by(CourseMaterial.created_at.desc())
    )
    return result.scalars().all()


@api_router.post("/{course_id}/materials", response_model=MaterialResponse, status_code=status.HTTP_201_CREATED)
async def create_material(
    course_id: UUID,
    data: MaterialCreate,
    db_session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Добавить материал к курсу (только teacher)"""
    if current_user.role != UserRole.TEACHER and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only teachers can add materials")

    # Проверяем курс
    course_result = await db_session.execute(
        select(Course).where(Course.id == course_id)
    )
    course = course_result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    if current_user.role == UserRole.TEACHER and course.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only add materials to your own courses")

    material = CourseMaterial(
        course_id=course_id,
        name=data.name,
        description=data.description,
        url=data.url,
        file_size=data.file_size,
    )
    db_session.add(material)
    await db_session.commit()
    await db_session.refresh(material)
    return material


@api_router.delete("/{course_id}/materials/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material(
    course_id: UUID,
    material_id: UUID,
    db_session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Удалить материал (только teacher)"""
    if current_user.role != UserRole.TEACHER and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only teachers can delete materials")

    result = await db_session.execute(
        select(CourseMaterial)
        .where(CourseMaterial.id == material_id)
        .where(CourseMaterial.course_id == course_id)
    )
    material = result.scalar_one_or_none()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    await db_session.delete(material)
    await db_session.commit()
