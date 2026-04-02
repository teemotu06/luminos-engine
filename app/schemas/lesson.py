from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.block_id import BlockId
from app.schemas.lesson_block import LessonBlock


class Lesson(BaseModel):
    lesson_id: str
    unit_id: str
    target_pattern: str
    title: str
    new_units: List[str] = Field(default_factory=list)
    new_sight_words: List[str] = Field(default_factory=list)
    korean_interference_active: List[str] = Field(default_factory=list)
    content_pack_status: str = "draft"
    json_path: Optional[str] = None
    blocks: Dict[BlockId, LessonBlock] = Field(default_factory=dict)
