from pydantic import BaseModel
from typing import Dict
from datetime import datetime
from uuid import UUID
from enum import Enum

class ReactionType(str, Enum):
    THUMBS_UP = "THUMBS_UP"
    HEART = "HEART"
    CLAP = "CLAP"
    THINKING = "THINKING"
    CONFUSED = "CONFUSED"
    FIRE = "FIRE"

class ReactionCreate(BaseModel):
    type: ReactionType

class ReactionResponse(BaseModel):
    id: UUID
    session_id: UUID
    student_id: UUID
    type: ReactionType
    created_at: datetime

    model_config = {"from_attributes": True}

class ReactionStats(BaseModel):
    THUMBS_UP: int = 0
    HEART: int = 0
    CLAP: int = 0
    THINKING: int = 0
    CONFUSED: int = 0
    FIRE: int = 0
    total: int = 0