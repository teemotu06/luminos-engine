from typing import Optional, Literal, List

from pydantic import BaseModel, Field, field_validator

from app.schemas.block_id import BlockId
from app.schemas.command_state import LuminosRuntimeConfig
from app.schemas.slide_payloads import SlidePayload, TeacherPrompt
from app.schemas.view_type import ViewType
from app.schemas.view_type import validate_view_type


KoreanInterferenceFlag = Literal[
    "r_l",
    "f_p",
    "v_b",
    "th_voiceless",
    "th_voiced",
    "cluster",
    "final_coda",
    "vowel_quality",
]

NextAction = Literal["manual_next", "auto_next"]


class Slide(BaseModel):
    slide_id: str
    block_id: BlockId
    slide_title: str
    view_type: ViewType
    content_payload: SlidePayload
    teacher_cue: Optional[str] = Field(...)
    expected_response: Optional[str] = Field(...)
    correction_move: Optional[str] = Field(...)
    observation_note: Optional[str] = Field(...)
    slide_audio_url: Optional[str] = None
    teacher_prompts: List[TeacherPrompt] = Field(default_factory=list)
    korean_interference_flag: Optional[KoreanInterferenceFlag] = Field(...)
    markable: bool
    marking_options: List[str] = Field(default_factory=list)
    next_action: NextAction
    luminos_runtime: Optional[LuminosRuntimeConfig] = None

    @field_validator("view_type")
    @classmethod
    def _validate_view_type(cls, value: str) -> str:
        return validate_view_type(value)
