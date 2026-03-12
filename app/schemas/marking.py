from typing import List, Literal, Optional

from pydantic import BaseModel, Field


MarkStatus = Literal["secure", "shaky", "missed", "skipped"]
ErrorTag = Literal[
    "sound_substitution",
    "vowel_confusion",
    "omission",
    "insertion",
    "blending_failure",
    "segmentation_failure",
    "oral_vocabulary_gap",
    "low_automaticity",
]


class QuickCheckItemResult(BaseModel):
    label: str
    phoneme: Optional[str] = None
    status: MarkStatus
    error_tags: List[ErrorTag] = Field(default_factory=list)
    korean_transfer: bool = False


class SlideMarkRequest(BaseModel):
    attempt_id: str
    lesson_id: str
    slide_id: str
    block_id: str
    status: MarkStatus
    error_tags: List[ErrorTag] = Field(default_factory=list)
    korean_transfer: bool = False
    teacher_note: Optional[str] = None
    lesson_notes: Optional[str] = None
    completed: bool = False
    item_results: List[QuickCheckItemResult] = Field(default_factory=list)


class SlideMarkResponse(BaseModel):
    attempt_id: str
    mastery_status: str
    next_recommendation: str
    phoneme_error_log_size: int
