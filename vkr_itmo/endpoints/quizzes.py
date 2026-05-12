from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
from datetime import datetime, timedelta, timezone
from typing import List
import os
import uuid as uuid_lib

from vkr_itmo.db.session import get_session
from vkr_itmo.db.models import (
    Quiz, QuizQuestion, QuizAnswer, SessionQuiz,
    QuizSubmission, User, Session, UserRole
)
from vkr_itmo.auth import get_current_user
from vkr_itmo.auth import get_quiz_owner
from vkr_itmo.schemas.quizzes import (
    QuizCreate, QuizUpdate, QuizResponse,
    LaunchQuiz, SessionQuizResponse, SessionQuizWithStats,
    QuizSubmissionRequest, QuizSubmissionResponse,
    LeaderboardEntry, QuizDetailResponse
)

api_router = APIRouter(prefix="/quizzes", tags=["Quizzes"])


# ==========================================
# CRUD КВИЗОВ
# ==========================================

@api_router.get("", response_model=List[QuizResponse])
async def get_my_quizzes(
    db_session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Список квизов преподавателя"""
    if current_user.role != UserRole.TEACHER:
        raise HTTPException(status_code=403, detail="Teachers only")

    result = await db_session.execute(
        select(Quiz).where(Quiz.teacher_id == current_user.id)
    )
    return result.scalars().all()


@api_router.post("", response_model=QuizResponse, status_code=status.HTTP_201_CREATED)
async def create_quiz(
    quiz_data: QuizCreate,
    db_session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Создать квиз"""
    quiz = Quiz(
        **quiz_data.model_dump(),
        teacher_id=current_user.id
    )
    db_session.add(quiz)
    await db_session.commit()
    await db_session.refresh(quiz)
    return quiz


@api_router.get("/{quiz_id}", response_model=QuizDetailResponse)
async def get_quiz(
    quiz_id: UUID,
    db_session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Получить квиз с вопросами"""
    result = await db_session.execute(select(Quiz).where(Quiz.id == quiz_id))
    quiz = result.scalar_one_or_none()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    # Загружаем вопросы и ответы
    questions_result = await db_session.execute(
        select(QuizQuestion)
        .where(QuizQuestion.quiz_id == quiz_id)
        .order_by(QuizQuestion.order_index)
    )
    questions = questions_result.scalars().all()

    # Формируем структуру для ответа
    quiz_dict = {
        **{c.name: getattr(quiz, c.name) for c in quiz.__table__.columns},
        "questions": []
    }

    for q in questions:
        answers_result = await db_session.execute(
            select(QuizAnswer).where(QuizAnswer.question_id == q.id)
        )
        answers = answers_result.scalars().all()

        quiz_dict["questions"].append({
            "id": q.id,
            "text": q.text,
            "type": q.type,
            "points": q.points,
            "timer": q.timer,
            "answers": [
                {
                    "id": a.id,
                    "text": a.text,
                    "is_correct": a.is_correct
                }
                for a in answers
            ]
        })

    return quiz_dict


@api_router.put("/{quiz_id}", response_model=QuizResponse)
async def update_quiz(
    quiz_id: UUID,
    quiz_data: QuizUpdate,
    db_session: AsyncSession = Depends(get_session),
    quiz: Quiz = Depends(get_quiz_owner)
):
    """Обновить квиз (полная замена вопросов)"""

    # 1. Обновляем поля квиза
    if quiz_data.title:
        quiz.title = quiz_data.title
    if quiz_data.description is not None:
        quiz.description = quiz_data.description

    await db_session.commit()

    # 2. Если переданы вопросы, заменяем их полностью
    if quiz_data.questions is not None:
        # Удаляем старые вопросы (каскадно удалятся ответы)
        await db_session.execute(
            QuizQuestion.__table__.delete().where(
                QuizQuestion.quiz_id == quiz_id
            )
        )

        # Добавляем новые
        for q_data in quiz_data.questions:
            question = QuizQuestion(
                quiz_id=quiz_id,
                text=q_data.text,
                type=q_data.type,
                points=q_data.points,
                timer=q_data.timer,
                order_index=q_data.order_index,
                extra_data=q_data.extra_data
            )
            db_session.add(question)
            await db_session.flush()  # Чтобы получить ID вопроса

            for a_data in q_data.answers:
                db_session.add(QuizAnswer(
                    question_id=question.id,
                    text=a_data.text,
                    is_correct=a_data.is_correct
                ))

        await db_session.commit()

    await db_session.refresh(quiz)
    return quiz


@api_router.delete("/{quiz_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quiz(
    quiz_id: UUID,
    db_session: AsyncSession = Depends(get_session),
    quiz: Quiz = Depends(get_quiz_owner)
):
    await db_session.delete(quiz)
    await db_session.commit()


# ==========================================
# ЗАГРУЗКА ФАЙЛОВ
# ==========================================

@api_router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    db_session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Загрузка файла для ответов на вопросы типа FILE"""
    # Проверяем размер файла (макс 10 МБ)
    MAX_SIZE = 10 * 1024 * 1024  # 10 MB
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 10 MB)")
    
    # Проверяем тип файла
    ALLOWED_TYPES = ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'image/jpeg', 'image/png']
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"File type {file.content_type} not allowed")
    
    # Генерируем уникальный ID для файла
    file_id = str(uuid_lib.uuid4())
    
    # Создаем директорию для файлов если её нет
    upload_dir = "uploads/quiz_files"
    os.makedirs(upload_dir, exist_ok=True)
    
    # Сохраняем файл
    file_extension = file.filename.split('.')[-1] if file.filename else 'bin'
    file_path = f"{upload_dir}/{file_id}.{file_extension}"
    
    with open(file_path, "wb") as f:
        f.write(content)
    
    return {
        "file_id": file_id,
        "filename": file.filename,
        "content_type": file.content_type,
        "size": len(content)
    }


# ==========================================
# СЕССИОННЫЕ КВИЗЫ (RUNTIME)
# ==========================================

runtime_router = APIRouter(prefix="/sessions/{session_id}/quiz", tags=["Session Quizzes"])


@runtime_router.post("/launch", response_model=SessionQuizResponse)
async def launch_quiz_in_session(
    session_id: UUID,
    launch_data: LaunchQuiz,
    db_session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Запустить квиз в активной сессии"""
    # Проверки: сессия активна, квиз принадлежит учителю
    session_result = await db_session.execute(
        select(Session).where(Session.id == session_id)
    )
    session_obj = session_result.scalar_one_or_none()
    if not session_obj or session_obj.ended_at:
        raise HTTPException(status_code=400, detail="Session is not active")

    if session_obj.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your session")

    quiz_result = await db_session.execute(
        select(Quiz).where(Quiz.id == launch_data.quiz_id)
    )
    quiz_obj = quiz_result.scalar_one_or_none()
    if not quiz_obj or quiz_obj.teacher_id != current_user.id:
        raise HTTPException(status_code=404, detail="Quiz not found or not yours")

    # Создаем запись о запуске
    session_quiz = SessionQuiz(
        session_id=session_id,
        quiz_id=launch_data.quiz_id,
        launched_at=datetime.now(timezone.utc)
    )
    db_session.add(session_quiz)

    # Инкрементируем счетчик квизов в сессии
    session_obj.total_quizzes += 1

    await db_session.commit()
    await db_session.refresh(session_quiz)
    return session_quiz


@runtime_router.get("/active")
async def get_active_quiz_in_session(
    session_id: UUID,
    db_session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Получить активный квиз в сессии (для студентов и учителей)"""
    result = await db_session.execute(
        select(SessionQuiz)
        .where(SessionQuiz.session_id == session_id)
        .where(SessionQuiz.ended_at == None)
        .order_by(SessionQuiz.launched_at.desc())
    )
    session_quiz = result.scalar_one_or_none()

    if not session_quiz:
        return None

    # Загружаем квиз с вопросами
    quiz_result = await db_session.execute(
        select(Quiz).where(Quiz.id == session_quiz.quiz_id)
    )
    quiz_obj = quiz_result.scalar_one_or_none()
    if not quiz_obj:
        return None

    questions_result = await db_session.execute(
        select(QuizQuestion)
        .where(QuizQuestion.quiz_id == session_quiz.quiz_id)
        .order_by(QuizQuestion.order_index)
    )
    questions = questions_result.scalars().all()

    questions_data = []
    for q in questions:
        answers_result = await db_session.execute(
            select(QuizAnswer).where(QuizAnswer.question_id == q.id)
        )
        answers = answers_result.scalars().all()

        questions_data.append({
            "id": str(q.id),
            "text": q.text,
            "type": q.type.value if hasattr(q.type, 'value') else str(q.type),
            "points": q.points,
            "timer": q.timer,
            "order_index": q.order_index,
            "extra_data": q.extra_data,
            "answers": [
                {
                    "id": str(a.id),
                    "text": a.text,
                    "is_correct": a.is_correct
                }
                for a in answers
            ]
        })

    return {
        "session_quiz_id": str(session_quiz.id),
        "quiz_id": str(session_quiz.quiz_id),
        "title": quiz_obj.title,
        "description": quiz_obj.description,
        "launched_at": session_quiz.launched_at.isoformat(),
        "questions": questions_data
    }


@runtime_router.post("/end", response_model=SessionQuizWithStats)
async def end_session_quiz(
    session_id: UUID,
    db_session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Завершить текущий активный квиз в сессии"""
    # Находим последний незавершенный квиз в сессии
    result = await db_session.execute(
        select(SessionQuiz)
        .where(SessionQuiz.session_id == session_id)
        .where(SessionQuiz.ended_at == None)
        .order_by(SessionQuiz.launched_at.desc())
    )
    session_quiz = result.scalar_one_or_none()

    if not session_quiz:
        raise HTTPException(status_code=404, detail="No active quiz in this session")

    # Проверка прав
    session_result = await db_session.execute(
        select(Session).where(Session.id == session_id)
    )
    session_obj = session_result.scalar_one_or_none()
    if session_obj.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    session_quiz.ended_at = datetime.now(timezone.utc)
    await db_session.commit()

    # Считаем статистику
    subs = await db_session.execute(
        select(func.count(), func.avg(QuizSubmission.score))
        .where(QuizSubmission.session_quiz_id == session_quiz.id)
    )
    count, avg = subs.first()

    return {
        **{c.name: getattr(session_quiz, c.name) for c in session_quiz.__table__.columns},
        "total_submissions": count or 0,
        "average_score": float(avg) if avg else 0.0
    }


# ==========================================
# ОТВЕТЫ СТУДЕНТОВ
# ==========================================

submissions_router = APIRouter(prefix="/session-quizzes", tags=["Submissions"])


@submissions_router.post("/{submission_id}/submit", response_model=QuizSubmissionResponse)
async def submit_answers(
    submission_id: UUID,
    submission_data: QuizSubmissionRequest,
    db_session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Студент отправляет ответы"""
    # Находим SessionQuiz
    sq_result = await db_session.execute(
        select(SessionQuiz).where(SessionQuiz.id == submission_id)
    )
    session_quiz = sq_result.scalar_one_or_none()
    if not session_quiz or session_quiz.ended_at:
        raise HTTPException(status_code=400, detail="Quiz is not active")

    # Считаем баллы
    total_score = 0

    # submission_data.answers = { question_id: [answer_ids or text or file_id] }
    for q_id, a_values in submission_data.answers.items():
        # Получаем вопрос
        q_result = await db_session.execute(
            select(QuizQuestion).where(QuizQuestion.id == q_id)
        )
        question = q_result.scalar_one_or_none()
        if not question:
            continue

        q_type = question.type.value if hasattr(question.type, 'value') else str(question.type)
        pts = question.points

        # TEXT и FILE - ручная проверка (0 баллов)
        if q_type in ['TEXT', 'FILE']:
            continue

        # BOOLEAN - проверка правильного ответа
        if q_type == 'BOOLEAN':
            correct_answers = await db_session.execute(
                select(QuizAnswer).where(
                    QuizAnswer.question_id == q_id,
                    QuizAnswer.is_correct == True
                )
            )
            correct_ids = {str(a.id) for a in correct_answers.scalars().all()}
            submitted_ids = set(a_values)
            if correct_ids == submitted_ids and len(correct_ids) > 0:
                total_score += pts

        # SINGLE и MULTIPLE - проверка наборов
        elif q_type in ['SINGLE', 'MULTIPLE']:
            correct_answers = await db_session.execute(
                select(QuizAnswer).where(
                    QuizAnswer.question_id == q_id,
                    QuizAnswer.is_correct == True
                )
            )
            correct_ids = {str(a.id) for a in correct_answers.scalars().all()}
            submitted_ids = set(a_values)
            if correct_ids == submitted_ids and len(correct_ids) > 0:
                total_score += pts

        # ORDERING - проверка последовательности
        elif q_type == 'ORDERING':
            extra_data = question.extra_data or {}
            correct_order = extra_data.get('correct_order', [])
            if correct_order and a_values:
                # Подсчитываем сколько элементов на правильных позициях
                correct_positions = sum(1 for i, item in enumerate(a_values) if i < len(correct_order) and item == correct_order[i])
                # Частичный балл: (правильные позиции / общее количество) * баллы
                if len(correct_order) > 0:
                    total_score += int((correct_positions / len(correct_order)) * pts)

        # MATCHING - проверка пар
        elif q_type == 'MATCHING':
            extra_data = question.extra_data or {}
            correct_pairs = extra_data.get('correct_pairs', {})
            if correct_pairs and a_values:
                try:
                    # a_values - это JSON строка с парами
                    import json
                    submitted_pairs = json.loads(a_values[0]) if a_values else {}
                    # Подсчитываем сколько правильных пар
                    correct_count = sum(1 for k, v in submitted_pairs.items() if correct_pairs.get(k) == v)
                    # Частичный балл: (правильные пары / общее количество) * баллы
                    if len(correct_pairs) > 0:
                        total_score += int((correct_count / len(correct_pairs)) * pts)
                except (json.JSONDecodeError, TypeError):
                    pass

    submission = QuizSubmission(
        session_quiz_id=submission_id,
        student_id=current_user.id,
        answers=submission_data.answers,
        score=total_score,
        submitted_at=datetime.now(timezone.utc)
    )
    db_session.add(submission)
    await db_session.commit()
    await db_session.refresh(submission)
    return submission


@submissions_router.get("/{submission_id}/leaderboard", response_model=List[LeaderboardEntry])
async def get_leaderboard(
    submission_id: UUID,
    db_session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Таблица лидеров для конкретного запуска квиза"""
    result = await db_session.execute(
        select(QuizSubmission, User.full_name)
        .join(User, QuizSubmission.student_id == User.id)
        .where(QuizSubmission.session_quiz_id == submission_id)
        .order_by(QuizSubmission.score.desc(), QuizSubmission.submitted_at.asc())
    )

    return [
        LeaderboardEntry(
            student_id=sub.student_id,
            student_name=name,
            score=sub.score,
            submitted_at=sub.submitted_at
        )
        for sub, name in result.all()
    ]