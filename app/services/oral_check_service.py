from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.lesson import LessonAttemptRecord, OralCheckAssignmentRecord, OralCheckSessionRecord, StudentMarkRecord
from app.schemas.marking import StudentMarkRequest
from app.schemas.oral_check import (
    OralCheckAssignmentMarkRequest,
    OralCheckAssignmentMarkResponse,
    OralCheckAssignmentSummary,
    OralCheckCompleteRequest,
    OralCheckSessionResponse,
    OralCheckSessionStartRequest,
)
from app.services.marking_service import record_student_mark
from app.services.status_service import normalize_mark_status


TERMINAL_STATUSES = {"secure", "shaky", "missed", "deferred", "absent"}


def is_oral_check_eligible(slide) -> bool:
    payload = getattr(slide, "content_payload", None)
    config = getattr(payload, "oral_enforcement", None)
    if config and config.enabled:
        return True
    return (
        slide.block_id == "07"
        and slide.view_type == "read_respond"
        and getattr(payload, "display_mode", None) == "reader"
    )


def resolve_oral_check_runtime(slide, has_roster: bool) -> Optional[dict]:
    if not has_roster or not is_oral_check_eligible(slide):
        return None

    payload = getattr(slide, "content_payload", None)
    config = getattr(payload, "oral_enforcement", None)
    if config and config.enabled:
        return {
            "participation_mode": config.participation_mode,
            "text_length_mode": config.text_length_mode,
            "required_evidence_count": config.required_evidence_count,
            "rehearsal_seconds": config.rehearsal_seconds,
            "audit_sample_size": config.audit_sample_size,
        }

    return {
        "participation_mode": "full_roster",
        "text_length_mode": "normal",
        "required_evidence_count": 1,
        "rehearsal_seconds": 30,
        "audit_sample_size": 0,
    }


def _session_response(session: OralCheckSessionRecord, assignments: Optional[Iterable[OralCheckAssignmentRecord]] = None):
    assignment_list = list(assignments if assignments is not None else session.assignments)
    active = next((a for a in assignment_list if a.status == "active"), None)
    phase = "complete" if session.session_status == "complete" else "individual_check"
    if session.session_status != "complete" and not active and any(a.requires_reteach and not a.resolved_in_block for a in assignment_list):
        phase = "reteach_queue"

    return OralCheckSessionResponse(
        session_id=str(session.id),
        participation_mode=session.participation_mode,
        audit_selection_strategy=session.audit_selection_strategy,
        text_length_mode=session.text_length_mode,
        phase=phase,
        session_status=session.session_status,
        required_student_count=session.required_student_count,
        resolved_student_count=session.resolved_student_count,
        unresolved_student_count=session.unresolved_student_count,
        required_evidence_count=session.required_evidence_count,
        active_assignment_id=str(active.id) if active else None,
        active_student_name=active.student_name if active else None,
        active_performance_type=active.performance_type if active else None,
        assignments=[
            OralCheckAssignmentSummary(
                assignment_id=str(a.id),
                student_name=a.student_name,
                performance_type=a.performance_type,
                attempt_number=a.attempt_number,
                queue_order=a.queue_order,
                status=a.status,
                teacher_note=a.teacher_note or "",
                override_reason=a.override_reason or "",
            )
            for a in assignment_list
        ],
    )


def _refresh_session_counts(session: OralCheckSessionRecord) -> None:
    selected_students = {assignment.student_name for assignment in session.assignments}
    resolved_students = set()
    for assignment in session.assignments:
        if assignment.resolved_in_block:
            resolved_students.add(assignment.student_name)

    session.required_student_count = len(selected_students)
    session.resolved_student_count = len(resolved_students)
    session.unresolved_student_count = max(session.required_student_count - session.resolved_student_count, 0)
    session.session_status = "complete" if session.unresolved_student_count == 0 else "in_progress"


def _set_next_active_assignment(session: OralCheckSessionRecord) -> Optional[OralCheckAssignmentRecord]:
    for assignment in sorted(session.assignments, key=lambda item: item.queue_order):
        if assignment.status == "active":
            return assignment

    next_assignment = next(
        (a for a in sorted(session.assignments, key=lambda item: item.queue_order) if a.status == "pending"),
        None,
    )
    if next_assignment:
        next_assignment.status = "active"
    return next_assignment


def _find_student_record(assignments: list[OralCheckAssignmentRecord], student_name: str) -> list[OralCheckAssignmentRecord]:
    return [a for a in assignments if a.student_name == student_name]


def _select_roster_subset(roster: list[str], participation_mode: str, audit_sample_size: int) -> list[str]:
    if participation_mode != "audit_roster":
        return roster
    if audit_sample_size <= 0:
        raise ValueError("Audit roster mode requires audit_sample_size > 0")
    return roster[: min(audit_sample_size, len(roster))]


def _select_roster_subset_with_strategy(
    db: Session,
    attempt: LessonAttemptRecord,
    roster: list[str],
    participation_mode: str,
    audit_sample_size: int,
    audit_selection_strategy: str,
) -> list[str]:
    """Choose the audit subset, preferring least-recently-marked learners when requested."""
    if participation_mode != "audit_roster":
        return roster
    if audit_sample_size <= 0:
        raise ValueError("Audit roster mode requires audit_sample_size > 0")
    if audit_selection_strategy == "roster_order" or not attempt.class_id:
        return roster[: min(audit_sample_size, len(roster))]

    latest_by_student = {student: None for student in roster}
    previous_marks = (
        db.execute(
            select(StudentMarkRecord, LessonAttemptRecord)
            .join(LessonAttemptRecord, StudentMarkRecord.attempt_id == LessonAttemptRecord.attempt_id)
            .where(
                LessonAttemptRecord.class_id == attempt.class_id,
                StudentMarkRecord.student_name.in_(roster),
            )
        )
        .all()
    )
    for mark, mark_attempt in previous_marks:
        current = latest_by_student.get(mark.student_name)
        if current is None or (mark.timestamp and mark.timestamp > current):
            latest_by_student[mark.student_name] = mark.timestamp

    indexed = {student: index for index, student in enumerate(roster)}
    ordered = sorted(
        roster,
        key=lambda student: (
            latest_by_student[student] is not None,
            latest_by_student[student] or 0,
            indexed[student],
        ),
    )
    return ordered[: min(audit_sample_size, len(ordered))]


def _queue_assignment(
    db: Session,
    session: OralCheckSessionRecord,
    assignment: OralCheckAssignmentRecord,
    performance_type: str,
    requires_reteach: bool = False,
) -> OralCheckAssignmentRecord:
    max_queue = max((item.queue_order for item in session.assignments), default=-1)
    queued = OralCheckAssignmentRecord(
        session_id=session.id,
        attempt_id=session.attempt_id,
        lesson_id=session.lesson_id,
        slide_id=session.slide_id,
        block_id=session.block_id,
        student_name=assignment.student_name,
        performance_type=performance_type,
        attempt_number=assignment.attempt_number + 1,
        queue_order=max_queue + 1,
        status="pending",
        requires_reteach=requires_reteach,
        resolved_in_block=False,
    )
    db.add(queued)
    return queued


def _should_run_short_reader_followup(session: OralCheckSessionRecord, assignment: OralCheckAssignmentRecord) -> bool:
    return (
        session.text_length_mode == "short"
        and session.required_evidence_count > 1
        and assignment.performance_type == "read_accuracy"
    )


def _mark_student_resolved(
    db: Session,
    session: OralCheckSessionRecord,
    assignment: OralCheckAssignmentRecord,
    student_assignments: list[OralCheckAssignmentRecord],
) -> None:
    assignment.resolved_in_block = True
    for record in student_assignments:
        if record.id == assignment.id:
            continue
        record.resolved_in_block = True
    _upsert_final_student_mark(db, session, assignment)


def _upsert_final_student_mark(
    db: Session,
    session: OralCheckSessionRecord,
    assignment: OralCheckAssignmentRecord,
) -> None:
    record_student_mark(
        db,
        StudentMarkRequest(
            attempt_id=str(session.attempt_id),
            lesson_id=session.lesson_id,
            slide_id=session.slide_id,
            block_id=session.block_id,
            student_name=assignment.student_name,
            status=normalize_mark_status(assignment.status),
            teacher_note=assignment.teacher_note,
        ),
    )


def start_oral_check_session(db: Session, request: OralCheckSessionStartRequest) -> OralCheckSessionResponse:
    """Create or resume a single oral-check session for an attempt+slide pair."""
    attempt = db.get(LessonAttemptRecord, request.attempt_id)
    if attempt is None:
        raise ValueError(f"Unknown attempt_id {request.attempt_id}")
    if attempt.lesson_id != request.lesson_id:
        raise ValueError("Attempt lesson_id does not match session lesson_id")
    if not request.roster:
        raise ValueError("Roster required for oral check")
    if request.text_length_mode == "short" and request.required_evidence_count < 2:
        raise ValueError("Short reader oral check requires required_evidence_count >= 2")

    existing = (
        db.execute(
            select(OralCheckSessionRecord).where(
                OralCheckSessionRecord.attempt_id == request.attempt_id,
                OralCheckSessionRecord.slide_id == request.slide_id,
            )
        )
        .scalars()
        .first()
    )
    if existing is not None:
        if request.force_restart:
            if existing.resolved_student_count > 0:
                raise ValueError("Cannot restart oral check after marking has begun")
            db.delete(existing)
            db.commit()
        else:
            existing = _prepare_session_snapshot(existing)
            return _session_response(existing)

    selected_roster = _select_roster_subset_with_strategy(
        db,
        attempt,
        request.roster,
        request.participation_mode,
        request.audit_sample_size,
        request.audit_selection_strategy,
    )

    session = OralCheckSessionRecord(
        attempt_id=request.attempt_id,
        lesson_id=request.lesson_id,
        slide_id=request.slide_id,
        block_id=request.block_id,
        participation_mode=request.participation_mode,
        audit_selection_strategy=request.audit_selection_strategy,
        text_length_mode=request.text_length_mode,
        required_evidence_count=request.required_evidence_count,
        roster_size=len(request.roster),
        required_student_count=len(selected_roster),
        resolved_student_count=0,
        unresolved_student_count=len(selected_roster),
        session_status="in_progress",
    )
    db.add(session)
    db.flush()

    for index, student_name in enumerate(selected_roster):
        db.add(
            OralCheckAssignmentRecord(
                session_id=session.id,
                attempt_id=request.attempt_id,
                lesson_id=request.lesson_id,
                slide_id=request.slide_id,
                block_id=request.block_id,
                student_name=student_name,
                performance_type="read_accuracy",
                attempt_number=1,
                queue_order=index,
                status="pending",
                requires_reteach=False,
                resolved_in_block=False,
            )
        )

    db.flush()
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing = (
            db.execute(
                select(OralCheckSessionRecord).where(
                    OralCheckSessionRecord.attempt_id == request.attempt_id,
                    OralCheckSessionRecord.slide_id == request.slide_id,
                )
            )
            .scalars()
            .first()
        )
        if existing is None:
            raise ValueError("Another teacher started the oral check at the same time; retry.") from exc
        existing = _prepare_session_snapshot(existing)
        return _session_response(existing)

    session = db.get(OralCheckSessionRecord, session.id)
    session = _prepare_session_snapshot(session)
    return _session_response(session)


def _prepare_session_snapshot(session: OralCheckSessionRecord) -> OralCheckSessionRecord:
    """Refresh derived oral-check counters without committing state as a side effect of reads."""
    _set_next_active_assignment(session)
    _refresh_session_counts(session)
    return session


def get_oral_check_session(db: Session, attempt_id: str, slide_id: str) -> OralCheckSessionResponse:
    """Return the current oral-check session state without mutating durable database state."""
    session = (
        db.execute(
            select(OralCheckSessionRecord).where(
                OralCheckSessionRecord.attempt_id == attempt_id,
                OralCheckSessionRecord.slide_id == slide_id,
            )
        )
        .scalars()
        .first()
    )
    if session is None:
        raise ValueError("Oral check session not found")

    session = _prepare_session_snapshot(session)
    return _session_response(session)


def mark_oral_check_assignment(db: Session, request: OralCheckAssignmentMarkRequest) -> OralCheckAssignmentMarkResponse:
    """Resolve a single oral-check assignment and advance the session queue."""
    session = db.get(OralCheckSessionRecord, request.session_id)
    if session is None:
        raise ValueError("Unknown oral check session")
    if session.session_status == "complete":
        raise ValueError("Oral check session already complete")

    assignment = db.get(OralCheckAssignmentRecord, request.assignment_id)
    if assignment is None or str(assignment.session_id) != str(session.id):
        raise ValueError("Assignment not found in oral check session")
    if assignment.status not in {"active", "pending"}:
        raise ValueError("Assignment already resolved")

    assignment.status = normalize_mark_status(request.status)
    assignment.teacher_note = request.teacher_note
    assignment.override_reason = request.override_reason

    student_assignments = sorted(
        _find_student_record(session.assignments, assignment.student_name),
        key=lambda item: item.queue_order,
    )

    requires_reteach = False
    student_resolved = False
    if _should_run_short_reader_followup(session, assignment):
        if assignment.status == "secure":
            _queue_assignment(
                db,
                session,
                assignment,
                performance_type="reread_fluency",
                requires_reteach=False,
            )
        elif assignment.status in {"shaky", "missed"}:
            _queue_assignment(
                db,
                session,
                assignment,
                performance_type="correction_reread",
                requires_reteach=True,
            )
            requires_reteach = True
        else:
            _mark_student_resolved(db, session, assignment, student_assignments)
            student_resolved = True
    elif assignment.status == "missed" and assignment.performance_type == "read_accuracy":
        _queue_assignment(
            db,
            session,
            assignment,
            performance_type="correction_reread",
            requires_reteach=True,
        )
        requires_reteach = True
    else:
        _mark_student_resolved(db, session, assignment, student_assignments)
        student_resolved = True

    db.flush()
    session = db.get(OralCheckSessionRecord, session.id)
    next_assignment = _set_next_active_assignment(session)
    _refresh_session_counts(session)
    db.commit()
    db.refresh(session)
    return OralCheckAssignmentMarkResponse(
        assignment_id=str(assignment.id),
        student_name=assignment.student_name,
        status=assignment.status,
        requires_reteach=requires_reteach,
        student_resolved=student_resolved,
        next_assignment_id=str(next_assignment.id) if next_assignment else None,
        session_status=session.session_status,
        resolved_student_count=session.resolved_student_count,
        unresolved_student_count=session.unresolved_student_count,
        session=_session_response(session),
    )


def complete_oral_check_session(db: Session, request: OralCheckCompleteRequest) -> OralCheckSessionResponse:
    """Mark the oral-check session complete once all required learners are resolved."""
    session = db.get(OralCheckSessionRecord, request.session_id)
    if session is None:
        raise ValueError("Unknown oral check session")

    _refresh_session_counts(session)
    if session.unresolved_student_count > 0:
        raise ValueError(f"Cannot complete oral check: {session.unresolved_student_count} students unresolved")

    session.session_status = "complete"
    db.commit()
    db.refresh(session)
    return _session_response(session)
