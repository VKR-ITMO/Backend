from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
from datetime import datetime, timedelta

from vkr_itmo.db.session import get_session
from vkr_itmo.db.models import Reaction, Session, User, UserRole
from vkr_itmo.auth import get_current_user
from vkr_itmo.schemas.reactions import ReactionCreate, ReactionResponse, ReactionStats

api_router = APIRouter(prefix="/sessions/{session_id}/reactions", tags=["Reactions"])


@api_router.post("", response_model=ReactionResponse, status_code=status.HTTP_201_CREATED)
async def send_reaction(
    session_id: UUID,
    reaction_data: ReactionCreate,
    db_session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Отправить реакцию в сессию (только student)"""
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can send reactions"
        )

    # Проверяем, что сессия существует и активна
    session_result = await db_session.execute(
        select(Session).where(Session.id == session_id)
    )
    session_obj = session_result.scalar_one_or_none()

    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")

    if session_obj.ended_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session has ended"
        )

    # Проверяем, не отправлял ли уже такую реакцию недавно (за последние 5 секунд)
    recent_reaction = await db_session.execute(
        select(Reaction)
        .where(Reaction.session_id == session_id)
        .where(Reaction.student_id == current_user.id)
        .where(Reaction.type == reaction_data.type)
        .where(
            Reaction.created_at >= datetime.utcnow() - timedelta(seconds=5)
        )
    )

    if recent_reaction.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Too many requests. Please wait a moment."
        )

    # Создаем реакцию
    reaction = Reaction(
        session_id=session_id,
        student_id=current_user.id,
        type=reaction_data.type,
        created_at=datetime.utcnow()
    )

    db_session.add(reaction)

    # Увеличиваем счетчик реакций в сессии
    session_obj.total_reactions += 1

    await db_session.commit()
    await db_session.refresh(reaction)

    # TODO: Отправить реакцию через WebSocket всем участникам
    # await websocket_manager.broadcast_to_session(
    #     session_id,
    #     {
    #         "event": "reaction:new",
    #         "payload": {
    #             "type": reaction.type,
    #             "student_id": str(current_user.id),
    #             "count": session_obj.total_reactions
    #         }
    #     }
    # )

    return reaction


@api_router.get("/stats", response_model=ReactionStats)
async def get_reaction_stats(
        session_id: UUID,
        db_session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_user)
):
    """Получить статистику реакций за сессию (только teacher)"""
    # Проверяем права
    session_result = await db_session.execute(
        select(Session).where(Session.id == session_id)
    )
    session_obj = session_result.scalar_one_or_none()

    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")

    if current_user.role not in ["TEACHER", "ADMIN"]:
        if session_obj.teacher_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

    # Получаем статистику по типам реакций
    result = await db_session.execute(
        select(
            Reaction.type,
            func.count().label("count")
        )
        .where(Reaction.session_id == session_id)
        .group_by(Reaction.type)
    )

    stats = ReactionStats()
    total = 0

    for reaction_type, count in result.all():
        # Конвертируем Enum в строку!
        type_name = reaction_type.value if hasattr(reaction_type, 'value') else str(reaction_type)

        if hasattr(stats, type_name):
            setattr(stats, type_name, count)
            total += count

    stats.total = total

    return stats
    return stats