from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID

from vkr_itmo.db.session import get_session
from vkr_itmo.db.models import User, CourseEnrollment, SessionParticipant, QuizSubmission, Achievement
from vkr_itmo.auth import get_current_user, get_current_admin_user, check_self_or_admin
from vkr_itmo.schemas.users import UserResponse, UserUpdate, StudentStats

api_router = APIRouter(prefix="/users", tags=["Users"])


@api_router.get("", response_model=list[UserResponse])
async def get_users(
        session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_admin_user)
):
    result = await session.execute(select(User))
    return result.scalars().all()


@api_router.get("/{user_id}", response_model=UserResponse)
async def get_user(
        user_id: UUID,
        session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_user)  # Требует просто Bearer
):
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@api_router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
        user_id: UUID,
        body: UserUpdate,
        session: AsyncSession = Depends(get_session),
        current_user: User = Depends(check_self_or_admin)  # Требует Self | Admin
):
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Обновляем только переданные поля
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)

    await session.commit()
    await session.refresh(user)
    return user


@api_router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
        user_id: UUID,
        session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_admin_user)  # Требует Admin
):
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await session.delete(user)
    await session.commit()
    return None


@api_router.get("/{user_id}/stats", response_model=StudentStats)
async def get_student_stats(
        user_id: UUID,
        session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_user)  # Требует Bearer
):
    # Проверяем, что пользователь вообще есть
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 1. Total Courses (Enrollments)
    enroll_result = await session.execute(
        select(func.count()).where(CourseEnrollment.student_id == user_id)
    )
    total_courses = enroll_result.scalar() or 0

    # 2. Total Lectures Attended (Session Participants)
    session_result = await session.execute(
        select(func.count()).where(SessionParticipant.student_id == user_id)
    )
    total_lectures_attended = session_result.scalar() or 0

    # 3. Total Quizzes & Average Score (Quiz Submissions)
    quiz_result = await session.execute(
        select(func.count(), func.avg(QuizSubmission.score)).where(QuizSubmission.student_id == user_id)
    )
    quiz_row = quiz_result.first()
    total_quizzes_taken = quiz_row[0] or 0
    average_quiz_score = float(quiz_row[1]) if quiz_row[1] else 0.0

    # 4. Total Achievements
    ach_result = await session.execute(
        select(func.count()).where(Achievement.student_id == user_id)
    )
    total_achievements = ach_result.scalar() or 0

    return StudentStats(
        total_courses=total_courses,
        total_lectures_attended=total_lectures_attended,
        total_quizzes_taken=total_quizzes_taken,
        average_quiz_score=average_quiz_score,
        total_achievements=total_achievements
    )