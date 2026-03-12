from typing import Literal

from pydantic import BaseModel

from app.schemas.block_id import BlockId
from app.schemas.view_type import ViewType

class BlockDefinition(BaseModel):
    block_id: BlockId
    label: str
    allowed_view_types: tuple[ViewType, ...]
