from typing import Optional, Literal, List, Dict, Any

from pydantic import BaseModel, Field

from app.schemas.view_type import ViewType

from app.schemas.block_id import BlockId


KoreanInterferenceFlag = Literal[
    "r_l",
    "f_p",
    "v_b",
    "th_voiceless",
    "th_voiced",
    "cluster",
    "vowel_quality",
]

NextAction = Literal["manual_next", "auto_next"]


class Slide(BaseModel):
    slide_id: str
    block_id: BlockId
    slide_title: str
    view_type: ViewType
    content_payload: Dict[str, Any] = Field(default_factory=dict)
    teacher_cue: Optional[str] = None
    expected_response: Optional[str] = None
    correction_move: Optional[str] = None
    korean_interference_flag: Optional[KoreanInterferenceFlag] = None
    markable: bool = False
    marking_options: List[str] = Field(default_factory=list)
    next_action: NextAction = "manual_next"