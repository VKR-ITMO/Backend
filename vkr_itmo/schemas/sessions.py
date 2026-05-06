from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class SessionBase(BaseModel):
    pass


class SessionStart(BaseModel):
    lecture_id: UUID


class SessionJoin(BaseModel):
    access_code: str


class SessionResponse(BaseModel):
    id: UUID
    lecture_id: UUID
    teacher_id: UUID
    access_code: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    total_participants: int = 0
    total_reactions: int = 0
    total_quizzes: int = 0

    model_config = {"from_attributes": True}


class SessionWithLecture(SessionResponse):
    lecture: dict  # Можно сделать отдельную схему LectureInfo


class CompletedSession(BaseModel):
    id: UUID
    lecture_id: UUID
    started_at: datetime
    ended_at: datetime
    total_participants: int
    total_reactions: int
    total_quizzes: int
    duration_seconds: int


class SessionParticipantResponse(BaseModel):
    id: UUID
    session_id: UUID
    student_id: UUID
    student_name: str
    student_email: str
    joined_at: datetime
    left_at: Optional[datetime] = None

    model_config = {"from_attributes": True}