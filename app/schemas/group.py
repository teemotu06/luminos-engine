from typing import List, Optional

from pydantic import BaseModel, Field


class GroupMeta(BaseModel):
    unit_id: str
    group_number: int
    title: str
    description: str = ""
    target_phonemes: List[str] = Field(default_factory=list)
    sort_order: int


class GroupCreateRequest(BaseModel):
    unit_id: str
    title: str
    description: Optional[str] = ""
    target_phonemes: List[str] = Field(default_factory=list)


class GroupUpdateRequest(BaseModel):
    title: str
    description: Optional[str] = ""
    target_phonemes: List[str] = Field(default_factory=list)
