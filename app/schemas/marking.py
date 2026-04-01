from typing import List, Literal, Optional

from pydantic import BaseModel, Field


MarkStatus = Literal["secure", "shaky", "missed", "skipped", "deferred", "absent"]
SupportLevel = Literal["independent", "prompted", "modeled"]
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
# Student marks include Korean transfer as an error tag (stored in error_tags list)
StudentErrorTag = Literal[
    "sound_substitution",
    "vowel_confusion",
    "omission",
    "insertion",
    "blending_failure",
    "segmentation_failure",
    "oral_vocabulary_gap",
    "low_automaticity",
    "korean_transfer",
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


class StudentMarkRequest(BaseModel):
    attempt_id: str
    lesson_id: str
    slide_id: str
    block_id: str
    student_name: str
    status: MarkStatus
    error_tags: List[StudentErrorTag] = Field(default_factory=list)
    support_level: Optional[SupportLevel] = None
    teacher_note: Optional[str] = None


class StudentMarkDeleteRequest(BaseModel):
    attempt_id: str
    lesson_id: str
    slide_id: str
    student_name: str


class StudentMarkResponse(BaseModel):
    id: str
    student_name: str
    status: str
