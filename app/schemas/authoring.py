from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AddSlideRequest(BaseModel):
    view_type: str
    position: Optional[int] = None


class UpdateSlideRequest(BaseModel):
    payload: Optional[Dict[str, Any]] = None
    slide_title: Optional[str] = None
    teacher_cue: Optional[str] = None
    luminos_says: Optional[Dict[str, Any]] = None


class ReorderSlidesRequest(BaseModel):
    slide_ids: List[str] = Field(default_factory=list)


class SaveLessonRequest(BaseModel):
    lesson_data: Dict[str, Any]


class ValidationResult(BaseModel):
    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
