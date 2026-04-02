import logging
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.lesson import LessonAttemptRecord, LessonRuntimeStateRecord, OralCheckSessionRecord, StudentRecord
from app.schemas.command_state import CommandStateAdvanceRequest, CommandStateResponse, LuminosRuntimeStateConfig
from app.services.command_runtime_profiles import BLOCK_RUNTIME_PROFILES
from app.schemas.oral_check import OralCheckAssignmentMarkRequest, OralCheckSessionStartRequest
from app.services.kokoro_tts_service import KokoroTtsError, ensure_tts_audio
from app.services.lesson_navigation import flatten_lesson_slides
from app.services.lesson_service import load_lesson
from app.services.oral_check_service import (
    get_oral_check_session,
    is_oral_check_eligible,
    mark_oral_check_assignment,
    resolve_oral_check_runtime,
    start_oral_check_session,
)

logger = logging.getLogger(__name__)


def _load_slide(lesson_id: str, slide_id: str) -> Any:
    lesson = load_lesson(lesson_id)
    for entry in flatten_lesson_slides(lesson):
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
    profile = BLOCK_RUNTIME_PROFILES.get((block_id, view_type))

    if view_type == "flashcard":
        front_text = getattr(payload, "front_text", "") or slide.slide_title
        spoken_unit = getattr(payload, "back_text", "") or front_text
        states = [
            LuminosRuntimeStateConfig(
                key="transition",
                board_prompt=f"Look at {front_text}.",
                teacher_prompt=teacher_cue or f"Set attention on {front_text}.",
                tts_prompt=f"Look at {front_text}.",
                teacher_controls=["replay", "force_advance"],
            ),
            LuminosRuntimeStateConfig(
                key="model",
                board_prompt=f"Listen. {spoken_unit}",
                teacher_prompt=teacher_cue or f"Model {spoken_unit} once.",
                tts_prompt=f"Listen. {spoken_unit}",
                teacher_controls=["replay", "force_advance"],
            ),
            LuminosRuntimeStateConfig(
                key="choral",
                board_prompt=f"Everyone. Say {spoken_unit}.",
                teacher_prompt=teacher_cue or "Take a choral response, then mark the class.",
                tts_prompt=f"Everyone. Say {spoken_unit}.",
                teacher_controls=["mark_class", "replay", "force_advance"],
            ),
        ]
        if profile == "sound_intro":
            states[0].board_prompt = "Look at the letter."
            states[0].tts_prompt = "Look at the letter."
        elif profile == "vocab_warmup":
            states[0].board_prompt = "Look. New word."
            states[0].tts_prompt = "Look. New word."
        return states

    if view_type == "drag_letter":
        target_word = getattr(payload, "target_word", "") or "the word"
        states = [
            LuminosRuntimeStateConfig(
                key="transition",
                board_prompt=f"Get ready to build {target_word}.",
                teacher_prompt=teacher_cue or f"Set the build routine for {target_word}.",
                tts_prompt=f"Get ready to build {target_word}.",
                teacher_controls=["replay", "force_advance"],
            ),
            LuminosRuntimeStateConfig(
                key="build",
                board_prompt=f"Build {target_word}.",
                teacher_prompt=teacher_cue or f"Students build {target_word}.",
                tts_prompt=f"Build {target_word}.",
                teacher_controls=["replay", "force_advance"],
            ),
            LuminosRuntimeStateConfig(
                key="check",
                board_prompt="Check every part.",
                teacher_prompt=teacher_cue or "Confirm the build, then mark the class.",
                tts_prompt="Check every part.",
                teacher_controls=["mark_class", "replay", "force_advance"],
            ),
        ]
        if profile == "word_build":
            states.insert(
                2,
                LuminosRuntimeStateConfig(
                    key="partner_practice",
                    board_prompt="Work with your partner. Check it together.",
                    teacher_prompt="Give them a short check window before class confirmation.",
                    tts_prompt="Work with your partner. Check it together.",
                    timeout_ms=12000,
                    teacher_controls=["pause", "force_advance"],
                ),
            )
        return states

    if view_type == "writing_encoding":
        dictated_text = getattr(payload, "dictated_text", "") or "the word"
        states = [
            LuminosRuntimeStateConfig(
                key="transition",
                board_prompt="Get ready to write.",
                teacher_prompt=teacher_cue or "Prepare students to encode.",
                tts_prompt="Get ready to write.",
                teacher_controls=["replay", "force_advance"],
            ),
            LuminosRuntimeStateConfig(
                key="dictate",
                board_prompt=f"Write {dictated_text}.",
                teacher_prompt=teacher_cue or f"Dictate {dictated_text}.",
                tts_prompt=f"Write {dictated_text}.",
                teacher_controls=["replay", "force_advance"],
            ),
            LuminosRuntimeStateConfig(
                key="check",
                board_prompt="Check every sound.",
                teacher_prompt=teacher_cue or "Confirm the writing, then mark the class.",
                tts_prompt="Check every sound.",
                teacher_controls=["mark_class", "replay", "force_advance"],
            ),
        ]
        if profile == "encoding_write":
            states.insert(
                2,
                LuminosRuntimeStateConfig(
                    key="write",
                    board_prompt="Write now.",
                    teacher_prompt="Give a short silent writing window.",
                    tts_prompt="Write now.",
                    timeout_ms=15000,
                    teacher_controls=["pause", "force_advance"],
                ),
            )
        return states

    if view_type == "read_respond":
        display_mode = getattr(payload, "display_mode", "") or ""
        comprehension_prompt = getattr(payload, "comprehension_prompt", "") or ""
        if display_mode == "sentence":
            states = [
                LuminosRuntimeStateConfig(
                    key="transition",
                    board_prompt="Eyes on the sentence.",
                    teacher_prompt=teacher_cue or "Set tracking and attention.",
                    tts_prompt="Eyes on the sentence.",
                    teacher_controls=["replay", "force_advance"],
                ),
                LuminosRuntimeStateConfig(
                    key="choral",
                    board_prompt="Everyone. Read the sentence.",
                    teacher_prompt=teacher_cue or "Take a choral sentence read.",
                    tts_prompt="Everyone. Read the sentence.",
                    teacher_controls=["mark_class", "replay", "force_advance"],
                ),
            ]
            if profile == "sentence_bridge":
                states.insert(
                    1,
                    LuminosRuntimeStateConfig(
                        key="partner_practice",
                        board_prompt="Read with your partner.",
                        teacher_prompt="Give a short partner read before whole-class check.",
                        tts_prompt="Read with your partner.",
                        timeout_ms=12000,
                        teacher_controls=["pause", "force_advance"],
                    ),
                )
            if comprehension_prompt:
                states.append(
                    LuminosRuntimeStateConfig(
                        key="check",
                        board_prompt=comprehension_prompt,
                        teacher_prompt=teacher_cue or "Take a brief oral answer, then mark the class.",
                        tts_prompt=comprehension_prompt,
                        teacher_controls=["mark_class", "replay", "force_advance"],
                    )
                )
            return states
        if display_mode == "spot_part":
            support_text = getattr(payload, "support_text", "") or prompt_text or slide.slide_title
            states = [
                LuminosRuntimeStateConfig(
                    key="transition",
                    board_prompt="Look carefully.",
                    teacher_prompt=teacher_cue or "Set attention on the displayed words.",
                    tts_prompt="Look carefully.",
                    teacher_controls=["replay", "force_advance"],
                ),
                LuminosRuntimeStateConfig(
                    key="check",
                    board_prompt=support_text,
                    teacher_prompt=teacher_cue or "Take one or two oral answers, then mark the class.",
                    tts_prompt=support_text,
                    teacher_controls=["mark_class", "replay", "force_advance"],
                ),
            ]
            if profile == "pattern_notice":
                states[1].board_prompt = support_text
                states[1].teacher_prompt = teacher_cue or "Take one or two oral answers, then mark the class."
            return states

    if prompt_text or teacher_cue:
        return [
            LuminosRuntimeStateConfig(
                key="transition",
                board_prompt=prompt_text or teacher_cue,
                teacher_prompt=teacher_cue or prompt_text or slide.slide_title,
                tts_prompt=prompt_text or teacher_cue,
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
    if slide.teacher_cue:
        return str(slide.teacher_cue).strip()
    front_text = getattr(payload, "front_text", None)
    if front_text:
        return f"What sound is {front_text}?"
    target_word = getattr(payload, "target_word", None)
    if target_word:
        return f"Build {target_word}."
    dictated_text = getattr(payload, "dictated_text", None)
    if dictated_text:
        return f"Write {dictated_text}."
    return slide.slide_title


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


def _get_runtime_record(db: Session, attempt_id: str, slide_id: str) -> Optional[LessonRuntimeStateRecord]:
    return (
        db.execute(
            select(LessonRuntimeStateRecord).where(
                LessonRuntimeStateRecord.attempt_id == attempt_id,
                LessonRuntimeStateRecord.slide_id == slide_id,
            )
        )
        .scalars()
        .first()
    )


def _ensure_runtime_record(
    db: Session,
    attempt: LessonAttemptRecord,
    slide: Any,
) -> LessonRuntimeStateRecord:
    existing = _get_runtime_record(db, str(attempt.attempt_id), slide.slide_id)
    if existing is not None:
        return existing

    state_sequence = []
    if _runtime_state_sequence(slide):
        state_sequence = [item.key for item in _runtime_state_sequence(slide)]
    elif is_oral_check_eligible(slide) and _roster_for_attempt(db, attempt):
        state_sequence = ["individual_turn", "complete"]
    else:
        state_sequence = ["transition", "complete"]

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
) -> CommandStateResponse:
    teacher_controls = teacher_controls or _teacher_controls_for_state(runtime.current_state, session_mode)
    mark_required = any(control.startswith("mark_") for control in teacher_controls)
    return CommandStateResponse(
        attempt_id=str(runtime.attempt_id),
        slide_id=runtime.slide_id,
        block_id=runtime.block_id,
        state_version=runtime.state_version,
        audio_event_id=runtime.audio_event_id,
        ui_event_id=runtime.ui_event_id,
        current_state=runtime.current_state,
        current_student=runtime.current_student,
        prompt_text=runtime.current_prompt_text or "",
        teacher_prompt_text=getattr(runtime, "teacher_prompt_text", None) or runtime.current_prompt_text or "",
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
    )


def get_command_state(db: Session, lesson_id: str, attempt_id: str, slide_id: Optional[str] = None) -> CommandStateResponse:
    attempt = db.get(LessonAttemptRecord, attempt_id)
    if attempt is None or attempt.lesson_id != lesson_id:
        raise ValueError("Lesson attempt not found")
    if not slide_id:
        slide_id = attempt.current_slide_id
    if not slide_id:
        lesson = load_lesson(lesson_id)
        ordered = flatten_lesson_slides(lesson)
        if not ordered:
            raise ValueError("Lesson has no slides")
        slide_id = ordered[0]["slide"].slide_id
        attempt.current_slide_id = slide_id
    slide = _load_slide(lesson_id, slide_id)
    runtime = _ensure_runtime_record(db, attempt, slide)

    session_mode = "legacy"
    if is_oral_check_eligible(slide) and _roster_for_attempt(db, attempt):
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
        )

    db.commit()
    db.refresh(runtime)
    return _runtime_to_response(runtime, session_mode=session_mode)


def advance_command_state(db: Session, lesson_id: str, attempt_id: str, request: CommandStateAdvanceRequest) -> CommandStateResponse:
    attempt = db.get(LessonAttemptRecord, attempt_id)
    if attempt is None or attempt.lesson_id != lesson_id:
        raise ValueError("Lesson attempt not found")
    slide = _load_slide(lesson_id, request.slide_id)
    runtime = _ensure_runtime_record(db, attempt, slide)
    session_mode = "oral_check" if is_oral_check_eligible(slide) and _roster_for_attempt(db, attempt) else "legacy"

    if request.action == "replay":
        runtime.audio_event_id += 1
    elif request.action == "pause":
        runtime.paused = True
        runtime.ui_event_id += 1
    elif request.action == "resume":
        runtime.paused = False
        runtime.ui_event_id += 1
    elif request.action == "force_advance":
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
        )

    db.commit()
    db.refresh(runtime)
    return _runtime_to_response(runtime, session_mode=session_mode)


def set_active_attempt_slide(db: Session, lesson_id: str, attempt_id: str, slide_id: str) -> None:
    attempt = db.get(LessonAttemptRecord, attempt_id)
    if attempt is None or attempt.lesson_id != lesson_id:
        raise ValueError("Lesson attempt not found")
    _load_slide(lesson_id, slide_id)
    attempt.current_slide_id = slide_id
    db.commit()
