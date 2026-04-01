from typing import List, Literal, Optional

from pydantic import BaseModel, Field


OralParticipationMode = Literal["full_roster", "short_reader_full_roster", "audit_roster"]
AuditSelectionStrategy = Literal["roster_order", "least_recently_checked"]
OralTextLengthMode = Literal["normal", "short"]
OralSessionStatus = Literal["in_progress", "complete"]
OralPhase = Literal["model", "rehearsal", "individual_check", "reteach_queue", "complete"]
OralPerformanceType = Literal["read_accuracy", "reread_fluency", "correction_reread"]
OralAssignmentStatus = Literal["pending", "active", "secure", "shaky", "missed", "deferred", "absent"]
FinalOralStatus = Literal["secure", "shaky", "missed", "deferred", "absent"]


class OralCheckSessionStartRequest(BaseModel):
    attempt_id: str
    lesson_id: str
    slide_id: str
    block_id: str
    roster: List[str] = Field(default_factory=list)
    participation_mode: OralParticipationMode = "full_roster"
    text_length_mode: OralTextLengthMode = "normal"
    required_evidence_count: int = 1
    rehearsal_seconds: int = 30
    audit_sample_size: int = 0
    audit_selection_strategy: AuditSelectionStrategy = "roster_order"
    force_restart: bool = False


class OralCheckAssignmentSummary(BaseModel):
    assignment_id: str
    student_name: str
    performance_type: OralPerformanceType
    attempt_number: int
    queue_order: int
    status: OralAssignmentStatus
    teacher_note: str = ""
    override_reason: str = ""


class OralCheckSessionResponse(BaseModel):
    session_id: str
    participation_mode: OralParticipationMode
    audit_selection_strategy: AuditSelectionStrategy = "roster_order"
    text_length_mode: OralTextLengthMode
    phase: OralPhase
    session_status: OralSessionStatus
    required_student_count: int
    resolved_student_count: int
    unresolved_student_count: int
    required_evidence_count: int
    active_assignment_id: Optional[str] = None
    active_student_name: Optional[str] = None
    active_performance_type: Optional[OralPerformanceType] = None
    assignments: List[OralCheckAssignmentSummary] = Field(default_factory=list)


class OralCheckAssignmentMarkRequest(BaseModel):
    session_id: str
    assignment_id: str
    status: FinalOralStatus
    teacher_note: Optional[str] = None
    override_reason: Optional[str] = None


class OralCheckAssignmentMarkResponse(BaseModel):
    assignment_id: str
    student_name: str
    status: FinalOralStatus
    requires_reteach: bool
    student_resolved: bool
    next_assignment_id: Optional[str] = None
    session_status: OralSessionStatus
    resolved_student_count: int
    unresolved_student_count: int
    session: OralCheckSessionResponse


class OralCheckCompleteRequest(BaseModel):
    session_id: str
