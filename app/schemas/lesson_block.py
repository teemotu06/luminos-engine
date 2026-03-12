from typing import List

from pydantic import BaseModel, Field

from app.schemas.block_id import BlockId
from app.schemas.slide import Slide


class LessonBlock(BaseModel):
    block_id: BlockId
    label: str
    slides: List[Slide] = Field(default_factory=list)
