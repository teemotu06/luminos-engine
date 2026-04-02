from typing import List, Literal, Optional

from pydantic import BaseModel, Field


CommandAction = Literal["mark", "mark_class", "skip", "force_advance", "replay", "pause", "resume"]


class LuminosRuntimeStateConfig(BaseModel):
    key: str
    prompt: Optional[str] = None
    board_prompt: Optional[str] = None
    teacher_prompt: Optional[str] = None
    tts_prompt: Optional[str] = None
    timeout_ms: Optional[int] = None
    action: Optional[str] = None
    teacher_controls: List[str] = Field(default_factory=list)
    questions: List[str] = Field(default_factory=list)
    roster: Optional[Literal["full", "audit"]] = None
    audit_strategy: Optional[Literal["roster_order", "least_recently_checked"]] = None


class LuminosRuntimeConfig(BaseModel):
    enabled: bool = True
    default_state: str = "transition"
    partner_practice_ms: int = 30000
    state_sequence: List[LuminosRuntimeStateConfig] = Field(default_factory=list)


class CommandStateResponse(BaseModel):
    attempt_id: str
    slide_id: str
    block_id: str
    state_version: int
    audio_event_id: int
    ui_event_id: int
    current_state: str
    current_student: Optional[str] = None
    prompt_text: str = ""
    teacher_prompt_text: str = ""
    state_timeout_ms: Optional[int] = None
    state_started_at: Optional[str] = None
    audio_url: Optional[str] = None
    queue_position: int = 0
    queue_total: int = 0
    mark_required: bool = False
    advance_blocked: bool = False
    reteach_queue: List[str] = Field(default_factory=list)
    next_students: List[str] = Field(default_factory=list)
    teacher_controls: List[str] = Field(default_factory=list)
    paused: bool = False
    session_mode: str = "legacy"


class CommandStateAdvanceRequest(BaseModel):
    slide_id: str
    action: CommandAction
    student: Optional[str] = None
    status: Optional[str] = None


class ActiveSlideRequest(BaseModel):
    slide_id: str
