from typing import List, Optional, Literal
from pydantic import BaseModel, Field


ViewType = Literal[
    "launch",
    "teach",
    "model",
    "guided",
    "independent",
    "check",
    "quiz",
    "wrap",
]


class Slide(BaseModel):
    id: str
    block: int = Field(ge=1, le=10)
    view_type: ViewType
    title: str
    teacher_note: Optional[str] = None
    text: Optional[str] = None
    prompt: Optional[str] = None


class Lesson(BaseModel):
    lesson_id: str
    level: str
    unit: str
    lesson_number: int
    title: str
    slides: List[Slide]