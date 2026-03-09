from typing import List

from pydantic import BaseModel, Field

from app.schemas.lesson_block import LessonBlock


class Lesson(BaseModel):
    lesson_id: str
    level: str
    unit: str
    lesson_number: int
    title: str
    blocks: List[LessonBlock] = Field(default_factory=list)