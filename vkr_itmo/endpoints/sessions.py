from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
from datetime import datetime, timezone
from typing import Optional, List
import secrets

from vkr_itmo.db.session import get_session
from vkr_itmo.db.models import Session, Lecture, User, SessionParticipant, Course, UserRole
from vkr_itmo.auth import get_current_user
from vkr_itmo.auth import get_session_owner, get_active_teacher_session
from vkr_itmo.schemas.sessions import (
    SessionResponse,
    SessionStart,
    SessionJoin,
    SessionWithLecture,
    CompletedSession,
    SessionParticipantResponse
)

api_router = APIRouter(prefix="/sessions", tags=["Sessions"])


@api_router.post("/start", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def start_session(
        session_data: SessionStart,
        db_session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_user)
):
    """Начать live-сессию по лекции (только teacher)"""
    if current_user.role != UserRole.TEACHER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers can start sessions"
        )

    # Проверяем, нет ли уже активной сессии
    active = await db_session.execute(
        select(Session)
        .where(Session.teacher_id == current_user.id)
        .where(Session.ended_at == None)
    )
    if active.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have an active session"
        )

    # Получаем лекцию
    lecture_result = await db_session.execute(
        select(Lecture).where(Lecture.id == session_data.lecture_id)
    )
    lecture = lecture_result.scalar_one_or_none()

    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found")

    if lecture.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only start sessions for your own lectures"
        )

    # Генерируем уникальный access_code
    while True:
        access_code = secrets.token_hex(3).upper()
        result = await db_session.execute(
            select(Session).where(Session.access_code == access_code)
        )
        if not result.scalar_one_or_none():
            break

    session = Session(
        lecture_id=lecture.id,
        teacher_id=current_user.id,
        access_code=access_code,
        started_at=datetime.now(timezone.utc),
        total_participants=0,
        total_reactions=0,
        total_quizzes=0
    )

    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    return session


@api_router.post("/join", response_model=SessionWithLecture)
async def join_session(
        join_data: SessionJoin,
        db_session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_user)
):
    """Подключиться к сессии по коду (только student)"""
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can join sessions"
        )

    # Ищем сессию по коду
    result = await db_session.execute(
        select(Session).where(Session.access_code == join_data.access_code.upper())
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.ended_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session has ended"
        )

    # Проверяем, был ли ранее (ушёл или активен) — разрешаем повторный вход
    existing_participant = await db_session.execute(
        select(SessionParticipant)
        .where(SessionParticipant.session_id == session.id)
        .where(SessionParticipant.student_id == current_user.id)
    )
    prev_participant = existing_participant.scalar_one_or_none()

    if prev_participant:
        # Rejoin: clear left_at and update joined_at
        prev_participant.left_at = None
        prev_participant.joined_at = datetime.now(timezone.utc)
    else:
        # Создаём участника
        participant = SessionParticipant(
            session_id=session.id,
            student_id=current_user.id,
            joined_at=datetime.now(timezone.utc)
        )
        db_session.add(participant)

        # Увеличиваем счётчик только для новых участников
        session.total_participants += 1

    await db_session.commit()
    await db_session.refresh(session)

    # Получаем информацию о лекции
    lecture_result = await db_session.execute(
        select(Lecture).where(Lecture.id == session.lecture_id)
    )
    lecture = lecture_result.scalar_one_or_none()

    # Получаем информацию о преподавателе
    teacher_result = await db_session.execute(
        select(User).where(User.id == session.teacher_id)
    )
    teacher = teacher_result.scalar_one_or_none()

    return SessionWithLecture(
        id=session.id,
        lecture_id=session.lecture_id,
        teacher_id=session.teacher_id,
        access_code=session.access_code,
        started_at=session.started_at,
        ended_at=session.ended_at,
        total_participants=session.total_participants,
        total_reactions=session.total_reactions,
        total_quizzes=session.total_quizzes,
        lecture={
            "id": str(lecture.id),
            "name": lecture.name,
            "topic": lecture.topic
        } if lecture else {}
    )


@api_router.get("/active", response_model=Optional[SessionResponse])
async def get_active_session(
        db_session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_user)
):
    """Получить активную сессию преподавателя"""
    session = await get_active_teacher_session(db_session, current_user)
    return session


@api_router.post("/{session_id}/end", response_model=CompletedSession)
async def end_session(
        session_id: UUID,
        db_session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_user)
):
    """Завершить сессию (только владелец)"""
    session = await get_session_owner(session_id, db_session, current_user)

    if session.ended_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session already ended"
        )

    ended_at = datetime.now(timezone.utc)
    session.ended_at = ended_at

    # Считаем длительность (handle both aware and naive started_at)
    started_at = session.started_at
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    duration = int((ended_at - started_at).total_seconds())

    await db_session.commit()
    await db_session.refresh(session)

    return CompletedSession(
        id=session.id,
        lecture_id=session.lecture_id,
        started_at=session.started_at,
        ended_at=session.ended_at,
        total_participants=session.total_participants,
        total_reactions=session.total_reactions,
        total_quizzes=session.total_quizzes,
        duration_seconds=duration
    )


@api_router.get("/history", response_model=List[CompletedSession])
async def get_session_history(
        db_session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_user)
):
    """История завершённых сессий (только teacher)"""
    if current_user.role not in [UserRole.TEACHER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers can view session history"
        )

    query = select(Session).where(Session.ended_at != None)

    if current_user.role == UserRole.TEACHER:
        query = query.where(Session.teacher_id == current_user.id)

    result = await db_session.execute(query.order_by(Session.ended_at.desc()))
    sessions = result.scalars().all()

    completed = []
    for s in sessions:
        s_ended = s.ended_at if s.ended_at.tzinfo else s.ended_at.replace(tzinfo=timezone.utc)
        s_started = s.started_at if s.started_at.tzinfo else s.started_at.replace(tzinfo=timezone.utc)
        duration = int((s_ended - s_started).total_seconds())
        completed.append(CompletedSession(
            id=s.id,
            lecture_id=s.lecture_id,
            started_at=s.started_at,
            ended_at=s.ended_at,
            total_participants=s.total_participants,
            total_reactions=s.total_reactions,
            total_quizzes=s.total_quizzes,
            duration_seconds=duration
        ))

    return completed


@api_router.post("/{session_id}/leave", response_model=dict)
async def leave_session(
        session_id: UUID,
        db_session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_user)
):
    """Покинуть сессию (только student)"""
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can leave sessions"
        )

    result = await db_session.execute(
        select(SessionParticipant)
        .where(SessionParticipant.session_id == session_id)
        .where(SessionParticipant.student_id == current_user.id)
        .where(SessionParticipant.left_at == None)
    )
    participant = result.scalar_one_or_none()

    if not participant:
        raise HTTPException(status_code=404, detail="Not in this session")

    participant.left_at = datetime.now(timezone.utc)
    await db_session.commit()

    return {"message": "Left session successfully"}


@api_router.get("/{session_id}", response_model=SessionResponse)
async def get_session_by_id(
        session_id: UUID,
        db_session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_user)
):
    """Получить сессию по ID"""
    result = await db_session.execute(
        select(Session).where(Session.id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return session


@api_router.get("/{session_id}/participants", response_model=List[SessionParticipantResponse])
async def get_session_participants(
        session_id: UUID,
        db_session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_user)
):
    """Получить список участников сессии (teacher и участники сессии)"""
    # Проверяем что сессия существует
    result = await db_session.execute(select(Session).where(Session.id == session_id))
    session_obj = result.scalar_one_or_none()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Проверяем что пользователь имеет доступ к сессии
    # (является учителем сессии или участником сессии)
    if current_user.role != UserRole.TEACHER:
        participant_result = await db_session.execute(
            select(SessionParticipant).where(
                SessionParticipant.session_id == session_id,
                SessionParticipant.student_id == current_user.id
            )
        )
        if not participant_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Not a participant of this session")

    result = await db_session.execute(
        select(SessionParticipant, User)
        .join(User, SessionParticipant.student_id == User.id)
        .where(SessionParticipant.session_id == session_id)
    )

    participants = []
    for participant, user in result.all():
        participants.append(SessionParticipantResponse(
            id=participant.id,
            session_id=participant.session_id,
            student_id=participant.student_id,
            student_name=user.full_name,
            student_email=user.email,
            joined_at=participant.joined_at,
            left_at=participant.left_at
        ))

    return participants


@api_router.get("/lecture/{lecture_id}/active", response_model=Optional[SessionWithLecture])
async def get_active_session_for_lecture(
        lecture_id: UUID,
        db_session: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_user)
):
    """Получить активную сессию для лекции (любой пользователь)"""
    # Ищем активную сессию для лекции
    result = await db_session.execute(
        select(Session)
        .where(Session.lecture_id == lecture_id)
        .where(Session.ended_at == None)
    )
    session = result.scalar_one_or_none()

    if not session:
        return None

    # Получаем информацию о лекции
    lecture_result = await db_session.execute(
        select(Lecture).where(Lecture.id == session.lecture_id)
    )
    lecture = lecture_result.scalar_one_or_none()

    return SessionWithLecture(
        id=session.id,
        lecture_id=session.lecture_id,
        teacher_id=session.teacher_id,
        access_code=session.access_code,
        started_at=session.started_at,
        ended_at=session.ended_at,
        total_participants=session.total_participants,
        total_reactions=session.total_reactions,
        total_quizzes=session.total_quizzes,
        lecture={
            "id": str(lecture.id),
            "name": lecture.name,
            "topic": lecture.topic
        } if lecture else {}
    )