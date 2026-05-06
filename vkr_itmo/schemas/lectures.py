# schemas/lectures.py

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from enum import Enum


class LectureStatus(str, Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    CANCELLED = "CANCELLED"


# Убираем ReactionType enum - пусть будут просто строки
# Фронтенд сам разберётся что там

class LectureBase(BaseModel):
    name: str
    topic: str
    description: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    max_participants: Optional[int] = None
    enabled_reactions: Optional[List[str]] = None  # Просто список строк


class LectureCreate(LectureBase):
    pass


class LectureUpdate(BaseModel):
    name: Optional[str] = None
    topic: Optional[str] = None
    description: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    status: Optional[LectureStatus] = None
    max_participants: Optional[int] = None
    enabled_reactions: Optional[List[str]] = None


# schemas/lectures.py

from pydantic import field_validator
import json


class LectureResponse(LectureBase):
    id: UUID
    course_id: Optional[UUID]
    teacher_id: UUID
    status: LectureStatus
    access_code: Optional[str]
    is_free_session: bool

    model_config = {"from_attributes": True}

    @field_validator('enabled_reactions', mode='before')
    @classmethod
    def parse_enabled_reactions(cls, value):
        """Парсит JSON строку в список"""
        if isinstance(value, str):
            return json.loads(value)
        return value


class LecturePublishResponse(BaseModel):
    access_code: str
    qr_code_url: str
