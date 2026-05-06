from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID
from enum import Enum


class CourseStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class CourseBase(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    semester: str


class CourseCreate(CourseBase):
    pass


class CourseUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    semester: Optional[str] = None
    status: Optional[CourseStatus] = None


class CourseResponse(CourseBase):
    id: UUID
    teacher_id: UUID
    status: CourseStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class CourseWithStats(CourseResponse):
    total_students: int
    total_lectures: int