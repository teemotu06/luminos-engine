from typing import Optional
from pydantic import BaseModel

from app.schemas.block_id import BlockId


class BlockDefinition(BaseModel):
    block_id: BlockId
    label: str
    allowed_view_types: Optional[tuple[str, ...]] = None
