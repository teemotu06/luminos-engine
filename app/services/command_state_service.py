import logging
from datetime import timedelta
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.lesson import LessonAttemptRecord, LessonRuntimeStateRecord, OralCheckSessionRecord, StudentRecord
from app.schemas.command_state import CommandStateAdvanceRequest, CommandStateResponse, LuminosRuntimeStateConfig
from app.schemas.oral_check import OralCheckAssignmentMarkRequest, OralCheckSessionStartRequest
from app.services.kokoro_tts_service import KokoroTtsError, ensure_tts_audio
from app.services.lesson_navigation import build_runtime_lesson_for_attempt
from app.services.oral_check_service import (
    get_oral_check_session,
    is_oral_check_eligible,
    mark_oral_check_assignment,
    resolve_oral_check_runtime,
    start_oral_check_session,
)
from app.slide_types import registry

logger = logging.getLogger(__name__)


def _load_slide(db: Session, lesson_id: str, slide_id: str, class_id: Optional[str] = None) -> Any:
    runtime_lesson, ordered_slides, _dynamic_review_recommendations, _dynamic_review_error = (
        build_runtime_lesson_for_attempt(db, lesson_id, class_id)
    )
    for entry in ordered_slides:
        if entry["slide"].slide_id == slide_id:
            return entry["slide"]
    raise ValueError(f"Slide {slide_id} not found in lesson {lesson_id}")


def _roster_for_attempt(db: Session, attempt: LessonAttemptRecord) -> list[str]:
    if not attempt.class_id:
        return []
    students = (
        db.execute(
            select(StudentRecord).where(StudentRecord.class_id == attempt.class_id).order_by(StudentRecord.student_name)
        )
        .scalars()
        .all()
    )
    return [student.student_name for student in students]


def _safe_audio_url(prompt_text: str) -> Optional[str]:
    if not prompt_text:
        return None
    try:
        return ensure_tts_audio(prompt_text).get("audio_url")
    except KokoroTtsError as exc:
        logger.warning("Command-state TTS generation failed for prompt %r: %s", prompt_text, exc)
        return None


def _runtime_state_map(slide: Any) -> dict[str, Any]:
    return {item.key: item for item in _runtime_state_sequence(slide)}


def _default_runtime_state_sequence(slide: Any) -> list[LuminosRuntimeStateConfig]:
    payload = slide.content_payload
    prompt_text = getattr(payload, "prompt_text", None)
    teacher_cue = slide.teacher_cue or ""
    view_type = str(slide.view_type)
    block_id = str(slide.block_id)
    defaults = registry.command_state_defaults_for(view_type)
    if defaults is not None:
        state_sequence = list(defaults(slide, block_id) or [])
        if state_sequence:
            return state_sequence

    if prompt_text or teacher_cue:
        return [
            LuminosRuntimeStateConfig(
                key="transition",
                board_prompt=prompt_text or "",
                teacher_prompt=teacher_cue or prompt_text or slide.slide_title,
                tts_prompt=prompt_text or "",
                teacher_controls=["replay", "force_advance"],
            )
        ]

    return []


def _runtime_state_sequence(slide: Any) -> list[LuminosRuntimeStateConfig]:
    if slide.luminos_runtime and slide.luminos_runtime.enabled and slide.luminos_runtime.state_sequence:
        return list(slide.luminos_runtime.state_sequence)
    return _default_runtime_state_sequence(slide)


def _current_runtime_state_config(runtime: LessonRuntimeStateRecord, slide: Any) -> Optional[Any]:
    state_map = _runtime_state_map(slide)
    if not state_map:
        return None
    if runtime.current_state in state_map:
        return state_map[runtime.current_state]
    if runtime.state_sequence and runtime.state_index < len(runtime.state_sequence):
        return state_map.get(runtime.state_sequence[runtime.state_index])
    return None


def _advance_runtime_state(runtime: LessonRuntimeStateRecord) -> None:
    sequence = list(runtime.state_sequence or [])
    if not sequence:
        runtime.current_state = "complete"
        return
    if runtime.state_index >= len(sequence) - 1:
        runtime.state_index = len(sequence) - 1
        runtime.current_state = "complete"
        return
    runtime.state_index += 1
    runtime.current_state = sequence[runtime.state_index]


def _build_generic_prompt(slide: Any) -> str:
    payload = slide.content_payload
    prompt_text = getattr(payload, "prompt_text", None)
    if prompt_text:
        return str(prompt_text).strip()
    front_text = getattr(payload, "front_text", None)
    if front_text:
        return f"What sound is {front_text}?"
    target_word = getattr(payload, "target_word", None)
    if target_word:
        return f"Build {target_word}."
    dictated_text = getattr(payload, "dictated_text", None)
    if dictated_text:
        return f"Write {dictated_text}."
    return ""


def _resolve_runtime_prompts(runtime: LessonRuntimeStateRecord, slide: Any) -> tuple[str, str, str]:
    state_config = _current_runtime_state_config(runtime, slide)
    fallback_prompt = _build_generic_prompt(slide)
    if not state_config:
        return fallback_prompt, fallback_prompt, fallback_prompt

    board_prompt = str(
        state_config.board_prompt
        or state_config.prompt
        or fallback_prompt
    ).strip()
    teacher_prompt = str(
        state_config.teacher_prompt
        or board_prompt
    ).strip()
    tts_prompt = str(
        state_config.tts_prompt
        or state_config.board_prompt
        or state_config.prompt
        or fallback_prompt
    ).strip()
    return board_prompt, teacher_prompt, tts_prompt


def _compute_marking_mode(session_mode: str, teacher_controls: list[str], has_roster: bool) -> str:
    if session_mode == "oral_check":
        return "sequential"
    if has_roster and any(c.startswith("mark_") for c in teacher_controls):
        return "grid"
    return "none"


def _compute_ui_phase(
    current_state: str,
    prompt_text: str,
    marking_mode: str,
    state_timeout_ms: Optional[int],
    paused: bool,
) -> str:
    if current_state == "complete":
        return "complete"
    if marking_mode == "sequential":
        return "mark_sequential"
    if marking_mode == "grid":
        return "mark_grid"
    if state_timeout_ms and not paused and prompt_text:
        return "observe"
    if prompt_text:
        return "deliver"
    return "ready"


def _compute_outcome_counts(student_outcomes: dict) -> dict[str, int]:
    counts = {"pending": 0, "secure": 0, "mixed": 0, "revisit": 0}
    for status in student_outcomes.values():
        key = status if status in counts else "pending"
        counts[key] += 1
    return counts


def _compute_board_banner(
    ui_phase: str,
    current_student: Optional[str],
    outcome_counts: dict[str, int],
    total_students: int,
) -> tuple[str, str]:
    if ui_phase == "complete":
        secure = outcome_counts.get("secure", 0)
        revisit = outcome_counts.get("revisit", 0)
        mixed = outcome_counts.get("mixed", 0)
        if total_students == 0:
            return "Slide complete", "celebrate"
        if revisit == 0 and mixed == 0:
            return f"All {secure} secure — great work", "celebrate"
        parts = []
        if secure:
            parts.append(f"{secure} secure")
        if mixed:
            parts.append(f"{mixed} mixed")
        if revisit:
            parts.append(f"{revisit} to revisit")
        return " · ".join(parts), "focus"
    if ui_phase == "mark_sequential" and current_student:
        return f"{current_student} — your turn", "focus"
    if ui_phase == "mark_grid":
        if total_students > 0 and outcome_counts.get("pending", 0) == 0 and outcome_counts.get("secure", 0) == total_students:
            return "Class marked secure", "celebrate"
        return "Mark your class", "neutral"
    return "", "neutral"


_OUTCOME_CYCLE = ["pending", "secure", "mixed", "revisit"]


def _cycle_outcome(current: str) -> str:
    try:
        idx = _OUTCOME_CYCLE.index(current)
    except ValueError:
        idx = 0
    return _OUTCOME_CYCLE[(idx + 1) % len(_OUTCOME_CYCLE)]


def _teacher_controls_for_state(current_state: str, session_mode: str) -> list[str]:
    if session_mode == "oral_check":
        if current_state == "complete":
            return ["force_advance"]
        return [
            "mark_secure",
            "mark_shaky",
            "mark_missed",
            "mark_deferred",
            "mark_absent",
            "skip",
            "replay",
            "pause",
            "force_advance",
        ]
    if current_state == "complete":
        return ["force_advance"]
    return ["replay", "pause", "force_advance"]


def _teacher_controls_for_runtime_state(runtime: LessonRuntimeStateRecord, slide: Any) -> list[str]:
    state_config = _current_runtime_state_config(runtime, slide)
    if not state_config:
        return _teacher_controls_for_state(runtime.current_state, "legacy")
    controls = list(state_config.teacher_controls or [])
    if runtime.current_state == "complete" and "force_advance" not in controls:
        controls.append("force_advance")
    return controls or _teacher_controls_for_state(runtime.current_state, "legacy")


def _get_runtime_record(
    db: Session,
    attempt_id: str,
    slide_id: str,
    for_update: bool = False,
) -> Optional[LessonRuntimeStateRecord]:
    q = select(LessonRuntimeStateRecord).where(
        LessonRuntimeStateRecord.attempt_id == attempt_id,
        LessonRuntimeStateRecord.slide_id == slide_id,
    )
    if for_update:
        q = q.with_for_update()
    return db.execute(q).scalars().first()


def _ensure_runtime_record(
    db: Session,
    attempt: LessonAttemptRecord,
    slide: Any,
    for_update: bool = False,
) -> LessonRuntimeStateRecord:
    existing = _get_runtime_record(db, str(attempt.attempt_id), slide.slide_id, for_update=for_update)
    if existing is not None:
        return existing

    state_sequence = []
    if _runtime_state_sequence(slide):
        state_sequence = [item.key for item in _runtime_state_sequence(slide)]
    elif is_oral_check_eligible(slide) and _roster_for_attempt(db, attempt):
        state_sequence = ["individual_turn", "complete"]
    else:
        state_sequence = ["transition", "complete"]

    roster = _roster_for_attempt(db, attempt)
    student_outcomes = {name: "pending" for name in roster} if roster else {}

    record = LessonRuntimeStateRecord(
        attempt_id=attempt.attempt_id,
        slide_id=slide.slide_id,
        block_id=slide.block_id,
        current_state=state_sequence[0] if state_sequence else "idle",
        state_sequence=state_sequence,
        state_index=0,
        student_queue=[],
        queue_position=0,
        reteach_queue=[],
        current_student=None,
        current_prompt_text=None,
        teacher_prompt_text=None,
        current_audio_url=None,
        state_version=1,
        audio_event_id=0,
        ui_event_id=0,
        paused=False,
        student_outcomes=student_outcomes,
    )
    db.add(record)
    db.flush()
    return record


def _ensure_oral_session(db: Session, attempt: LessonAttemptRecord, slide: Any) -> Optional[OralCheckSessionRecord]:
    roster = _roster_for_attempt(db, attempt)
    runtime = resolve_oral_check_runtime(slide, bool(roster))
    if not runtime:
        return None

    existing = (
        db.execute(
            select(OralCheckSessionRecord).where(
                OralCheckSessionRecord.attempt_id == attempt.attempt_id,
                OralCheckSessionRecord.slide_id == slide.slide_id,
            )
        )
        .scalars()
        .first()
    )
    if existing:
        return existing

    started = start_oral_check_session(
        db,
        OralCheckSessionStartRequest(
            attempt_id=str(attempt.attempt_id),
            lesson_id=attempt.lesson_id,
            slide_id=slide.slide_id,
            block_id=slide.block_id,
            roster=roster,
            participation_mode=runtime["participation_mode"],
            text_length_mode=runtime["text_length_mode"],
            required_evidence_count=runtime["required_evidence_count"],
            rehearsal_seconds=runtime["rehearsal_seconds"],
            audit_sample_size=runtime.get("audit_sample_size", 0),
            audit_selection_strategy=runtime.get("audit_selection_strategy", "roster_order"),
            force_restart=False,
        ),
    )
    return db.get(OralCheckSessionRecord, started.session_id)


def _sync_runtime_from_oral(db: Session, runtime: LessonRuntimeStateRecord, attempt: LessonAttemptRecord, slide: Any) -> None:
    session = _ensure_oral_session(db, attempt, slide)
    if session is None:
        return
    session_response = get_oral_check_session(db, str(attempt.attempt_id), slide.slide_id)
    previous_state = runtime.current_state
    previous_prompt = runtime.current_prompt_text or ""

    current_state = session_response.phase
    if session_response.session_status == "complete":
        current_state = "complete"

    prompt_text = ""
    if current_state == "individual_check" and session_response.active_student_name:
        prompt_text = f"{session_response.active_student_name}, your turn. Read."
    elif current_state == "reteach_queue" and session_response.active_student_name:
        prompt_text = f"{session_response.active_student_name}. Again. Read."
    elif current_state == "complete":
        prompt_text = ""

    _STATUS_MAP = {
        "complete": "secure",
        "correction_reread": "mixed",
        "missed": "revisit",
        "deferred": "revisit",
        "absent": "revisit",
    }
    runtime.current_state = current_state
    runtime.current_student = session_response.active_student_name
    runtime.student_queue = [assignment.student_name for assignment in session_response.assignments]
    runtime.queue_position = min(session_response.resolved_student_count + (1 if session_response.active_student_name else 0), session_response.required_student_count)
    runtime.reteach_queue = [
        assignment.student_name
        for assignment in session_response.assignments
        if assignment.performance_type == "correction_reread" and assignment.status in {"pending", "active"}
    ]
    runtime.current_prompt_text = prompt_text
    runtime.teacher_prompt_text = prompt_text
    runtime.current_audio_url = _safe_audio_url(prompt_text) if prompt_text else None
    runtime.student_outcomes = {
        assignment.student_name: _STATUS_MAP.get(assignment.performance_type or assignment.status or "", "pending")
        if assignment.status != "pending"
        else "pending"
        for assignment in session_response.assignments
    }
    if current_state != previous_state:
        runtime.state_version += 1
        runtime.ui_event_id += 1
    if prompt_text and prompt_text != previous_prompt:
        runtime.audio_event_id += 1


def _sync_runtime_generic(runtime: LessonRuntimeStateRecord, slide: Any) -> None:
    previous_state = runtime.current_state
    previous_prompt = runtime.current_prompt_text or ""
    if runtime.current_state == "complete":
        runtime.current_student = None
        runtime.current_prompt_text = ""
        runtime.teacher_prompt_text = ""
        runtime.current_audio_url = None
        return
    prompt_text, teacher_prompt_text, tts_prompt = _resolve_runtime_prompts(runtime, slide)
    runtime.current_student = None
    runtime.current_prompt_text = prompt_text
    runtime.teacher_prompt_text = teacher_prompt_text
    runtime.current_audio_url = _safe_audio_url(tts_prompt) if tts_prompt else None
    if runtime.current_state != previous_state:
        runtime.state_version += 1
        runtime.ui_event_id += 1
    if tts_prompt and tts_prompt != previous_prompt:
        runtime.audio_event_id += 1


def _runtime_to_response(
    runtime: LessonRuntimeStateRecord,
    session_mode: str = "legacy",
    teacher_controls: Optional[list[str]] = None,
    state_timeout_ms: Optional[int] = None,
    has_roster: bool = False,
) -> CommandStateResponse:
    teacher_controls = teacher_controls or _teacher_controls_for_state(runtime.current_state, session_mode)
    mark_required = any(control.startswith("mark_") for control in teacher_controls)
    student_outcomes = dict(getattr(runtime, "student_outcomes", None) or {})
    marking_mode = _compute_marking_mode(session_mode, teacher_controls, has_roster)
    prompt_text = runtime.current_prompt_text or ""
    ui_phase = _compute_ui_phase(runtime.current_state, prompt_text, marking_mode, state_timeout_ms, runtime.paused)
    outcome_counts = _compute_outcome_counts(student_outcomes)
    total_students = len(student_outcomes)
    board_banner_text, board_banner_tone = _compute_board_banner(ui_phase, runtime.current_student, outcome_counts, total_students)
    return CommandStateResponse(
        attempt_id=str(runtime.attempt_id),
        slide_id=runtime.slide_id,
        block_id=runtime.block_id,
        state_version=runtime.state_version,
        audio_event_id=runtime.audio_event_id,
        ui_event_id=runtime.ui_event_id,
        current_state=runtime.current_state,
        current_student=runtime.current_student,
        prompt_text=prompt_text,
        teacher_prompt_text=getattr(runtime, "teacher_prompt_text", None) or prompt_text,
        state_timeout_ms=state_timeout_ms,
        state_started_at=runtime.updated_at.isoformat() if getattr(runtime, "updated_at", None) else None,
        audio_url=runtime.current_audio_url,
        queue_position=runtime.queue_position,
        queue_total=len(runtime.student_queue or []),
        mark_required=mark_required,
        advance_blocked=session_mode == "oral_check" and runtime.current_state != "complete",
        reteach_queue=list(runtime.reteach_queue or []),
        next_students=list((runtime.student_queue or [])[runtime.queue_position : runtime.queue_position + 2]),
        teacher_controls=teacher_controls,
        paused=runtime.paused,
        session_mode=session_mode,
        ui_phase=ui_phase,
        marking_mode=marking_mode,
        student_outcomes=student_outcomes,
        pending_count=outcome_counts["pending"],
        secure_count=outcome_counts["secure"],
        mixed_count=outcome_counts["mixed"],
        revisit_count=outcome_counts["revisit"],
        board_banner_text=board_banner_text,
        board_banner_tone=board_banner_tone,
        auto_advance_at=(
            (runtime.updated_at + timedelta(milliseconds=state_timeout_ms)).isoformat()
            if state_timeout_ms and getattr(runtime, "updated_at", None)
            else None
        ),
    )


def get_command_state(db: Session, lesson_id: str, attempt_id: str, slide_id: Optional[str] = None) -> CommandStateResponse:
    attempt = db.get(LessonAttemptRecord, attempt_id)
    if attempt is None or attempt.lesson_id != lesson_id:
        raise ValueError("Lesson attempt not found")
    if not slide_id:
        slide_id = attempt.current_slide_id
    if not slide_id:
        _runtime_lesson, ordered, _dynamic_review_recommendations, _dynamic_review_error = (
            build_runtime_lesson_for_attempt(db, lesson_id, attempt.class_id)
        )
        if not ordered:
            raise ValueError("Lesson has no slides")
        slide_id = ordered[0]["slide"].slide_id
        attempt.current_slide_id = slide_id
    elif not attempt.current_slide_id:
        attempt.current_slide_id = slide_id
    slide = _load_slide(db, lesson_id, slide_id, attempt.class_id)
    runtime = _ensure_runtime_record(db, attempt, slide)

    roster = _roster_for_attempt(db, attempt)
    session_mode = "legacy"
    if is_oral_check_eligible(slide) and roster:
        session_mode = "oral_check"
        _sync_runtime_from_oral(db, runtime, attempt, slide)
    else:
        _sync_runtime_generic(runtime, slide)
        teacher_controls = _teacher_controls_for_runtime_state(runtime, slide)
        state_config = _current_runtime_state_config(runtime, slide)
        db.commit()
        db.refresh(runtime)
        return _runtime_to_response(
            runtime,
            session_mode=session_mode,
            teacher_controls=teacher_controls,
            state_timeout_ms=getattr(state_config, "timeout_ms", None),
            has_roster=bool(roster),
        )

    db.commit()
    db.refresh(runtime)
    return _runtime_to_response(runtime, session_mode=session_mode, has_roster=bool(roster))


def advance_command_state(db: Session, lesson_id: str, attempt_id: str, request: CommandStateAdvanceRequest) -> CommandStateResponse:
    attempt = db.get(LessonAttemptRecord, attempt_id)
    if attempt is None or attempt.lesson_id != lesson_id:
        raise ValueError("Lesson attempt not found")
    slide_id = attempt.current_slide_id or request.slide_id
    if not slide_id:
        raise ValueError("No active slide for lesson attempt")
    if request.slide_id and attempt.current_slide_id and request.slide_id != attempt.current_slide_id:
        raise ValueError("Slide action does not match the active slide")
    if not attempt.current_slide_id:
        attempt.current_slide_id = slide_id
    slide = _load_slide(db, lesson_id, slide_id, attempt.class_id)
    runtime = _ensure_runtime_record(db, attempt, slide, for_update=True)
    session_mode = "oral_check" if is_oral_check_eligible(slide) and _roster_for_attempt(db, attempt) else "legacy"

    if request.action == "replay":
        runtime.audio_event_id += 1
    elif request.action == "pause":
        runtime.paused = True
        runtime.ui_event_id += 1
    elif request.action == "resume":
        runtime.paused = False
        runtime.ui_event_id += 1
    elif request.action == "hide_answer":
        sequence = list(runtime.state_sequence or [])
        runtime.state_index = 0
        runtime.current_state = sequence[0] if sequence else "idle"
        runtime.current_student = None
        runtime.current_prompt_text = ""
        runtime.teacher_prompt_text = ""
        runtime.current_audio_url = None
        runtime.state_version += 1
        runtime.ui_event_id += 1
    elif request.action in {"force_advance", "begin_slide", "continue"}:
        if _runtime_state_sequence(slide):
            _advance_runtime_state(runtime)
        else:
            runtime.current_state = "complete"
            runtime.current_student = None
            runtime.current_prompt_text = ""
            runtime.teacher_prompt_text = ""
            runtime.current_audio_url = None
        runtime.state_version += 1
        runtime.ui_event_id += 1
    elif request.action == "mark_grid":
        student = request.student
        status = request.status
        if not student or not status:
            raise ValueError("student and status required for mark_grid")
        outcomes = dict(runtime.student_outcomes or {})
        outcomes[student] = status
        runtime.student_outcomes = outcomes
        runtime.state_version += 1
        runtime.ui_event_id += 1
    elif request.action in {"mark", "skip"} and session_mode == "oral_check":
        session = _ensure_oral_session(db, attempt, slide)
        if session is None:
            raise ValueError("Oral check session not found")
        session_response = get_oral_check_session(db, str(attempt.attempt_id), slide.slide_id)
        active_assignment = next(
            (assignment for assignment in session_response.assignments if assignment.assignment_id == session_response.active_assignment_id),
            None,
        )
        if active_assignment is None:
            raise ValueError("No active oral assignment")
        status = "deferred" if request.action == "skip" else request.status
        if not status:
            raise ValueError("status required for mark action")
        mark_oral_check_assignment(
            db,
            OralCheckAssignmentMarkRequest(
                session_id=str(session.id),
                assignment_id=active_assignment.assignment_id,
                status=status,
            ),
        )
    elif request.action in {"mark", "mark_class"}:
        status = request.status or "secure"
        if _runtime_state_sequence(slide):
            _advance_runtime_state(runtime)
        elif status == "secure":
            runtime.current_state = "complete"
        runtime.state_version += 1
    else:
        raise ValueError(f"Unsupported command action {request.action} for current slide")

    roster = _roster_for_attempt(db, attempt)
    if session_mode == "oral_check":
        _sync_runtime_from_oral(db, runtime, attempt, slide)
    else:
        _sync_runtime_generic(runtime, slide)
        teacher_controls = _teacher_controls_for_runtime_state(runtime, slide)
        state_config = _current_runtime_state_config(runtime, slide)
        db.commit()
        db.refresh(runtime)
        return _runtime_to_response(
            runtime,
            session_mode=session_mode,
            teacher_controls=teacher_controls,
            state_timeout_ms=getattr(state_config, "timeout_ms", None),
            has_roster=bool(roster),
        )

    db.commit()
    db.refresh(runtime)
    return _runtime_to_response(runtime, session_mode=session_mode, has_roster=bool(roster))


def set_active_attempt_slide(db: Session, lesson_id: str, attempt_id: str, slide_id: str) -> None:
    attempt = db.get(LessonAttemptRecord, attempt_id)
    if attempt is None or attempt.lesson_id != lesson_id:
        raise ValueError("Lesson attempt not found")
    _load_slide(db, lesson_id, slide_id, attempt.class_id)
    attempt.current_slide_id = slide_id
    db.commit()
