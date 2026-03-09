from typing import List

from pydantic import BaseModel, Field

from app.services.block_definition import BlockCode
from app.schemas.slide import Slide


class LessonBlock(BaseModel):
    block_no: int = Field(ge=1, le=10)
    code: BlockCode
    label: str
    slides: List[Slide]