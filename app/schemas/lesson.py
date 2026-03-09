from typing import List

from pydantic import BaseModel, Field

from app.schemas.lesson_block import LessonBlock


class Lesson(BaseModel):
    lesson_id: str
    unit_id: str
    target_pattern: str
    title: str
    korean_interference_active: List[str] = Field(default_factory=list)
    blocks: List[LessonBlock] = Field(default_factory=list)