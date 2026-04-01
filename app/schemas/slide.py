from typing import Optional, Literal, List

from pydantic import BaseModel, Field

from app.schemas.block_id import BlockId
from app.schemas.slide_payloads import SlidePayload
from app.schemas.view_type import ViewType


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
    korean_interference_flag: Optional[KoreanInterferenceFlag] = Field(...)
    markable: bool
    marking_options: List[str] = Field(default_factory=list)
    next_action: NextAction
