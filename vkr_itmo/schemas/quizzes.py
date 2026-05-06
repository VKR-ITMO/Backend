from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from enum import Enum


class QuizQuestionType(str, Enum):
    SINGLE = "SINGLE"
    MULTIPLE = "MULTIPLE"
    BOOLEAN = "BOOLEAN"
    FILE = "FILE"
    TEXT = "TEXT"
    ORDERING = "ORDERING"
    MATCHING = "MATCHING"


# --- Вложенные модели для создания/обновления ---

class QuizAnswerBase(BaseModel):
    text: str
    is_correct: bool = False


class QuizAnswerCreate(QuizAnswerBase):
    pass


class QuizQuestionBase(BaseModel):
    text: str
    type: QuizQuestionType
    points: int = 1
    timer: int = 30
    order_index: int
    extra_data: Optional[dict] = None
    answers: List[QuizAnswerCreate] = []


class QuizQuestionCreate(QuizQuestionBase):
    pass


# --- Основные модели ---

class QuizBase(BaseModel):
    title: str
    description: Optional[str] = None
    course_id: Optional[UUID] = None


class QuizCreate(QuizBase):
    pass


class QuizUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    questions: Optional[List[QuizQuestionCreate]] = None


class QuizResponse(QuizBase):
    id: UUID
    teacher_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


# Детальный ответ с вопросами и ответами
class QuizDetailResponse(QuizResponse):
    questions: List[dict]  # Для простоты вернем словари, или создадим полные Pydantic модели

    model_config = {"from_attributes": True}


# --- Session Quiz & Submissions ---

class LaunchQuiz(BaseModel):
    quiz_id: UUID


class SessionQuizResponse(BaseModel):
    id: UUID
    session_id: UUID
    quiz_id: UUID
    launched_at: datetime
    ended_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class SessionQuizWithStats(SessionQuizResponse):
    total_submissions: int = 0
    average_score: float = 0.0


class QuizSubmissionRequest(BaseModel):
    # Формат: { question_id: [answer_id, ...] }
    answers: dict[str, list[str]]


class QuizSubmissionResponse(BaseModel):
    id: UUID
    score: int
    submitted_at: datetime

    model_config = {"from_attributes": True}


class LeaderboardEntry(BaseModel):
    student_id: UUID
    student_name: str
    score: int
    submitted_at: datetime