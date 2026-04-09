import re
import json
import logging
from itertools import groupby
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import DataError, StatementError
from sqlalchemy.orm import Session

from app.slide_types import registry
from app.services.lesson_navigation import build_runtime_lesson_for_attempt
from app.db import get_db, SessionLocal
from app.models.lesson import ClassRecord, LessonAttemptRecord, OralCheckSessionRecord
from app.services.auth_service import (
    require_attempt_access,
    require_class_access,
    require_current_user,
    require_oral_check_session_access,
)
from app.schemas.command_state import ActiveSlideRequest, CommandStateAdvanceRequest, CommandStateResponse
from app.schemas.marking import (
    LessonCompleteRequest,
    LessonCompleteResponse,
    SlideMarkRequest,
    SlideMarkResponse,
    StudentMarkDeleteRequest,
    StudentMarkRequest,
    StudentMarkResponse,
)
from app.schemas.oral_check import (
    OralCheckAssignmentMarkRequest,
    OralCheckAssignmentMarkResponse,
    OralCheckCompleteRequest,
    OralCheckSessionResponse,
    OralCheckSessionStartRequest,
)
from app.schemas.tts import TtsPromptRequest, TtsPromptResponse
from app.services.class_service import get_all_classes, get_students_for_class
from app.services.class_session_service import get_class_session, set_class_session_slide
from app.services.command_state_service import advance_command_state, get_command_state, set_active_attempt_slide
from app.services.lesson_service import (
    KI_INSERTION_MAP,
    get_intervention_anchor,
    load_lesson,
    load_all_lessons,
    ordered_blocks,
    sync_lesson_record,
)
from app.services.mastery_gate_service import get_class_lesson_gate_summaries
from app.services.marking_service import (
    create_attempt,
    delete_student_mark,
    finalize_attempt_summary,
    get_marks_for_slide,
    OptimisticLockError,
    record_slide_mark,
    record_student_mark,
)
from app.services.oral_check_service import complete_oral_check_session, get_oral_check_session, mark_oral_check_assignment, start_oral_check_session
from app.services.pattern_noticing_service import adapt_pattern_noticing_payload
from app.services.kokoro_tts_service import KokoroTtsError, ensure_tts_audio
from app.services.review_service import get_review_data
from app.services.review_scheduler_service import build_dynamic_review_slides, build_lesson_index_review_map
from app.services.ws_manager import manager as ws_manager
from app.template_env import templates

router = APIRouter(prefix="/lesson", tags=["lesson"])
logger = logging.getLogger(__name__)


def _effective_slide_view_type_and_payload(slide):
    payload = slide.content_payload.model_dump() if hasattr(slide.content_payload, "model_dump") else dict(slide.content_payload)
    adapted_pattern = adapt_pattern_noticing_payload(str(slide.view_type), payload)
    if adapted_pattern is not None:
        return "pattern_noticing", adapted_pattern
    return str(slide.view_type), payload


def _resolve_roster(db: Session, class_id: Optional[str]) -> tuple[list[str], str]:
    if not class_id:
        return [], ""
    try:
        students = get_students_for_class(db, class_id)
        cls = db.get(ClassRecord, class_id)
    except (DataError, StatementError, ValueError):
        logger.warning("Invalid class_id for roster resolution: %s", class_id)
        return [], ""
    class_name = cls.class_name if cls else ""
    return [s.student_name for s in students], class_name


def _resolve_class_context(db: Session, current_user, class_id: Optional[str]) -> tuple[list[str], str]:
    if not class_id:
        return [], ""
    if class_id.startswith("YOUR_"):
        return [], ""
    require_class_access(db, current_user, class_id, include_deleted=True)
    return _resolve_roster(db, class_id)


def _safe_get_attempt(db: Session, attempt_id: Optional[str]) -> Optional[LessonAttemptRecord]:
    if not attempt_id:
        return None
    try:
        return db.get(LessonAttemptRecord, attempt_id)
    except (DataError, StatementError, ValueError):
        logger.warning("Invalid attempt_id for lesson runtime: %s", attempt_id)
        return None


def _natural_key(s: str) -> list:
    """Split a string into text/number chunks for natural sort order.
    e.g. 'G10' → ['G', 10] so G2 < G10.
    """
    return [int(c) if c.isdigit() else c for c in re.split(r"(\d+)", s)]


@router.get("/")
def lesson_index(request: Request, db: Session = Depends(get_db), current_user=Depends(require_current_user)):
    lessons = load_all_lessons()
    owner_user_id = None if current_user.role == "admin" else str(current_user.id)
    classes = get_all_classes(db, owner_user_id=owner_user_id)
    sorted_lessons = sorted(lessons, key=lambda lesson: _natural_key(lesson.unit_id))
    ki_anchors = {lesson.lesson_id: get_intervention_anchor(lesson.lesson_id) for lesson in lessons}
    review_lesson_ids = [lesson.lesson_id for lesson in lessons if lesson.lesson_id.startswith("G")]
    class_review_map = build_lesson_index_review_map(
        db,
        [cls["id"] for cls in classes],
        review_lesson_ids,
    )

    lesson_groups = [
        {"unit_id": k, "lessons": list(v)}
        for k, v in groupby(sorted_lessons, key=lambda lesson: lesson.unit_id)
    ]
    return templates.TemplateResponse(
        request,
        "lesson/index.html",
        {
            "lessons": lessons,
            "lesson_groups": lesson_groups,
            "classes": classes,
            "ki_anchors": ki_anchors,
            "ki_insertion_map": KI_INSERTION_MAP,
            "class_review_map": class_review_map,
            "class_review_map_json": json.dumps(class_review_map),
            "current_user": current_user,
        },
    )


@router.get("/mastery-gates")
def lesson_mastery_gates(class_id: str, db: Session = Depends(get_db), current_user=Depends(require_current_user)):
    """Return compact gate summaries for all lessons with any class attempt.

    Used by the lesson library to show per-card gate indicators when a class
    is selected. Returns lesson_id → {gate_level, gate_label, secure_count,
    weak_count, marked_count}.
    """
    require_class_access(db, current_user, class_id, include_deleted=True)
    return get_class_lesson_gate_summaries(db, class_id)


@router.get("/progress")
def lesson_progress(class_id: str, db: Session = Depends(get_db), current_user=Depends(require_current_user)):
    """Return teaching progress for each lesson within a class.

    Returns a dict mapping lesson_id → "completed" | "in_progress".
    Lessons with no attempts for this class are omitted.
    """
    require_class_access(db, current_user, class_id, include_deleted=True)
    attempts = (
        db.query(LessonAttemptRecord.lesson_id, LessonAttemptRecord.completed)
        .filter(LessonAttemptRecord.class_id == class_id)
        .all()
    )
    progress: dict[str, str] = {}
    for lesson_id, completed in attempts:
        if completed:
            progress[lesson_id] = "completed"
        elif lesson_id not in progress:
            progress[lesson_id] = "in_progress"
    return progress


@router.get("/{lesson_id}")
def get_lesson(
    request: Request,
    lesson_id: str,
    learner_key: Optional[str] = None,
    class_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    try:
        runtime_lesson, ordered_slides, dynamic_review_recommendations, dynamic_review_error = (
            build_runtime_lesson_for_attempt(db, lesson_id, class_id)
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Lesson not found")

    sync_lesson_record(db, runtime_lesson)
    db.commit()

    roster, class_name = _resolve_class_context(db, current_user, class_id)
    attempt = create_attempt(
        db,
        lesson_id=runtime_lesson.lesson_id,
        learner_key=learner_key,
        teacher_key=current_user.username,
        class_id=class_id,
    )

    return templates.TemplateResponse(
        request,
        "lesson/view.html",
        {
            "lesson": runtime_lesson,
            "ordered_blocks": ordered_blocks(runtime_lesson),
            "ordered_slides": ordered_slides,
            "attempt_id": str(attempt.attempt_id),
            "attempt_version": attempt.version,
            "learner_key": learner_key or "",
            "teacher_key": current_user.username,
            "class_id": class_id or "",
            "class_name": class_name,
            "roster": roster,
            "slide_versions": {result.slide_id: result.version for result in attempt.slide_results},
            "no_class_selected": not class_id,
            "dynamic_review_recommendations": dynamic_review_recommendations,
            "dynamic_review_slides": build_dynamic_review_slides(dynamic_review_recommendations),
            "dynamic_review_error": dynamic_review_error,
            "current_user": current_user,
        },
    )


@router.get("/{lesson_id}/block/{block_id}")
def get_lesson_block(
    request: Request,
    lesson_id: str,
    block_id: str,
    learner_key: Optional[str] = None,
    class_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    try:
        runtime_lesson, ordered_slides, dynamic_review_recommendations, dynamic_review_error = (
            build_runtime_lesson_for_attempt(db, lesson_id, class_id)
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Lesson not found")

    if block_id not in runtime_lesson.blocks:
        raise HTTPException(status_code=404, detail="Block not found")

    sync_lesson_record(db, runtime_lesson)
    db.commit()

    roster, class_name = _resolve_class_context(db, current_user, class_id)
    initial_slide_index = next(
        (entry["slide_index"] for entry in ordered_slides if entry["slide"].block_id == block_id),
        0,
    )
    attempt = create_attempt(
        db,
        lesson_id=runtime_lesson.lesson_id,
        learner_key=learner_key,
        teacher_key=current_user.username,
        class_id=class_id,
    )

    return templates.TemplateResponse(
        request,
        "lesson/view.html",
        {
            "lesson": runtime_lesson,
            "ordered_blocks": ordered_blocks(runtime_lesson),
            "ordered_slides": ordered_slides,
            "attempt_id": str(attempt.attempt_id),
            "attempt_version": attempt.version,
            "learner_key": learner_key or "",
            "teacher_key": current_user.username,
            "initial_slide_index": initial_slide_index,
            "class_id": class_id or "",
            "class_name": class_name,
            "roster": roster,
            "slide_versions": {result.slide_id: result.version for result in attempt.slide_results},
            "no_class_selected": not class_id,
            "dynamic_review_recommendations": dynamic_review_recommendations,
            "dynamic_review_slides": build_dynamic_review_slides(dynamic_review_recommendations),
            "dynamic_review_error": dynamic_review_error,
            "current_user": current_user,
        },
    )


@router.get("/{lesson_id}/teacher")
def get_lesson_teacher(
    request: Request,
    lesson_id: str,
    learner_key: Optional[str] = None,
    class_id: Optional[str] = None,
    attempt_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    try:
        lesson, ordered_slides, _dynamic_review_recommendations, _dynamic_review_error = (
            build_runtime_lesson_for_attempt(db, lesson_id, class_id)
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Lesson not found")

    sync_lesson_record(db, lesson)
    db.commit()

    roster, class_name = _resolve_class_context(db, current_user, class_id)
    attempt = _safe_get_attempt(db, attempt_id)
    if attempt is not None:
        attempt = require_attempt_access(db, current_user, str(attempt.attempt_id), lesson_id=lesson_id)
    if (attempt is None or attempt.lesson_id != lesson_id) and class_id:
        # Resume the existing in-progress attempt for this class+lesson rather
        # than creating a duplicate when the teacher navigates back mid-lesson.
        attempt = (
            db.execute(
                select(LessonAttemptRecord)
                .where(
                    LessonAttemptRecord.class_id == class_id,
                    LessonAttemptRecord.lesson_id == lesson_id,
                    LessonAttemptRecord.completed.is_(False),
                )
                .order_by(LessonAttemptRecord.attempt_date.desc())
            )
            .scalars()
            .first()
        )
    if attempt is None or attempt.lesson_id != lesson_id:
        attempt = create_attempt(
            db,
            lesson_id=lesson.lesson_id,
            learner_key=learner_key,
            teacher_key=current_user.username,
            class_id=class_id,
        )
    initial_slide_id = attempt.current_slide_id or (ordered_slides[0]["slide"].slide_id if ordered_slides else "")
    initial_slide_index = next(
        (entry["slide_index"] for entry in ordered_slides if entry["slide"].slide_id == initial_slide_id),
        0,
    )
    initial_command_state = (
        get_command_state(db, lesson.lesson_id, str(attempt.attempt_id), initial_slide_id).model_dump()
        if initial_slide_id
        else None
    )
    effective_slide_view_types = {}
    effective_slide_payloads = {}
    effective_slide_control_actions = {}
    for entry in ordered_slides:
        effective_type, effective_payload = _effective_slide_view_type_and_payload(entry["slide"])
        effective_slide_view_types[entry["slide"].slide_id] = effective_type
        effective_slide_payloads[entry["slide"].slide_id] = effective_payload
        effective_slide_control_actions[entry["slide"].slide_id] = registry.control_actions_for(effective_type)

    owner_user_id = None if current_user.role == "admin" else str(current_user.id)
    all_classes = get_all_classes(db, owner_user_id=owner_user_id, include_deleted=False)

    return templates.TemplateResponse(
        request,
        "lesson/teacher.html",
        {
            "lesson": lesson,
            "attempt_id": str(attempt.attempt_id),
            "initial_slide_id": initial_slide_id,
            "initial_slide_index": initial_slide_index,
            "initial_command_state": initial_command_state,
            "class_id": class_id or "",
            "class_name": class_name,
            "roster": roster,
            "ordered_slides": ordered_slides,
            "effective_slide_view_types": effective_slide_view_types,
            "effective_slide_payloads": effective_slide_payloads,
            "effective_slide_control_actions": effective_slide_control_actions,
            "all_classes": all_classes,
            "shell_mode": "teacher",
            "current_user": current_user,
        },
    )


@router.get("/{lesson_id}/board")
def get_lesson_board(
    lesson_id: str,
    learner_key: Optional[str] = None,
    class_id: Optional[str] = None,
    attempt_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    if not class_id:
        raise HTTPException(status_code=400, detail="Use the class board URL for board display")
    _resolve_class_context(db, current_user, class_id)
    return RedirectResponse(url=f"/classes/{class_id}/board", status_code=302)


@router.get("/{lesson_id}/review/{attempt_id}")
def lesson_review(
    request: Request,
    lesson_id: str,
    attempt_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    require_attempt_access(db, current_user, attempt_id, lesson_id=lesson_id)
    data = get_review_data(db, lesson_id, attempt_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Review not found")
    return templates.TemplateResponse(
        request,
        "lesson/review.html",
        {**data, "current_user": current_user},
    )


@router.post("/{lesson_id}/mark", response_model=SlideMarkResponse)
def mark_slide(
    lesson_id: str,
    mark: SlideMarkRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    if mark.lesson_id != lesson_id:
        raise HTTPException(status_code=400, detail="Lesson ID mismatch")

    require_attempt_access(db, current_user, mark.attempt_id, lesson_id=lesson_id)
    try:
        attempt = record_slide_mark(db, mark)
    except OptimisticLockError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    slide_result = next((result for result in attempt.slide_results if result.slide_id == mark.slide_id), None)
    return SlideMarkResponse(
        attempt_id=str(attempt.attempt_id),
        attempt_version=attempt.version,
        slide_version=slide_result.version if slide_result is not None else 1,
        mastery_status=attempt.mastery_status,
        next_recommendation=attempt.next_recommendation,
        phoneme_error_log_size=len(attempt.phoneme_error_log or []),
        summary_finalized=False,
    )


@router.post("/{lesson_id}/student-mark", response_model=StudentMarkResponse)
def mark_student_slide(
    lesson_id: str,
    mark: StudentMarkRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    if mark.lesson_id != lesson_id:
        raise HTTPException(status_code=400, detail="Lesson ID mismatch")

    require_attempt_access(db, current_user, mark.attempt_id, lesson_id=lesson_id)
    try:
        record = record_student_mark(db, mark)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return StudentMarkResponse(
        id=str(record.id),
        student_name=record.student_name,
        status=record.status,
    )


@router.get("/{lesson_id}/student-marks")
def get_student_slide_marks(
    lesson_id: str,
    attempt_id: str,
    slide_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    require_attempt_access(db, current_user, attempt_id, lesson_id=lesson_id)
    try:
        records = get_marks_for_slide(db, attempt_id=attempt_id, lesson_id=lesson_id, slide_id=slide_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [
        {
            "id": str(record.id),
            "student_name": record.student_name,
            "status": record.status,
            "timestamp": record.timestamp.isoformat() if record.timestamp else None,
        }
        for record in records
    ]


@router.delete("/{lesson_id}/student-mark")
def delete_student_slide_mark(
    lesson_id: str,
    mark: StudentMarkDeleteRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    if mark.lesson_id != lesson_id:
        raise HTTPException(status_code=400, detail="Lesson ID mismatch")
    require_attempt_access(db, current_user, mark.attempt_id, lesson_id=lesson_id)
    delete_student_mark(db, mark.attempt_id, mark.slide_id, mark.student_name)
    return {"ok": True}


@router.post("/{lesson_id}/oral-check/session/start", response_model=OralCheckSessionResponse)
def oral_check_start(
    lesson_id: str,
    request: OralCheckSessionStartRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    if request.lesson_id != lesson_id:
        raise HTTPException(status_code=400, detail="Lesson ID mismatch")
    require_attempt_access(db, current_user, request.attempt_id, lesson_id=lesson_id)
    try:
        return start_oral_check_session(db, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{lesson_id}/oral-check/session/{attempt_id}/{slide_id}", response_model=OralCheckSessionResponse)
def oral_check_get(
    lesson_id: str,
    attempt_id: str,
    slide_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    require_attempt_access(db, current_user, attempt_id, lesson_id=lesson_id)
    try:
        return get_oral_check_session(db, attempt_id, slide_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{lesson_id}/oral-check/assignment/mark", response_model=OralCheckAssignmentMarkResponse)
def oral_check_mark(
    lesson_id: str,
    request: OralCheckAssignmentMarkRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    session = require_oral_check_session_access(db, current_user, request.session_id)
    if session.lesson_id != lesson_id:
        raise HTTPException(status_code=404, detail="Oral check session not found")
    try:
        return mark_oral_check_assignment(db, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{lesson_id}/oral-check/session/complete", response_model=OralCheckSessionResponse)
def oral_check_complete(
    lesson_id: str,
    request: OralCheckCompleteRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    session_record = require_oral_check_session_access(db, current_user, request.session_id)
    if session_record.lesson_id != lesson_id:
        raise HTTPException(status_code=404, detail="Oral check session not found")
    try:
        session = complete_oral_check_session(db, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if session.session_status != "complete":
        raise HTTPException(status_code=400, detail="Oral check session incomplete")
    return session


@router.post("/tts/prompt", response_model=TtsPromptResponse)
def tts_prompt(request: TtsPromptRequest, current_user=Depends(require_current_user)):
    try:
        payload = ensure_tts_audio(request.text)
    except KokoroTtsError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return TtsPromptResponse(**payload)


@router.get("/{lesson_id}/command-state/{attempt_id}", response_model=CommandStateResponse)
def command_state_get(
    lesson_id: str,
    attempt_id: str,
    slide_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    # Public — the state is projected on a classroom board and not sensitive.
    # Attempt IDs are UUIDs, so enumeration is not a practical concern.
    try:
        return get_command_state(db, lesson_id, attempt_id, slide_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.websocket("/{lesson_id}/ws/{attempt_id}")
async def lesson_ws(lesson_id: str, attempt_id: str, ws: WebSocket):
    """Real-time state push. Public — data is shown on the projected board.

    The DB session is opened, used, and closed before entering the keepalive
    loop so it never blocks other requests for the WebSocket's lifetime.
    Keepalive: client sends "ping", server responds "pong".
    """
    await ws_manager.connect(ws, attempt_id)
    try:
        # Use a short-lived session — close it before entering the keepalive loop
        db = SessionLocal()
        try:
            current = get_command_state(db, lesson_id, attempt_id, None)
            await ws.send_json(current.model_dump())
        except Exception:
            pass  # DB miss or invalid IDs — client falls back to polling
        finally:
            db.close()

        while True:
            msg = await ws.receive_text()
            if msg == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(ws, attempt_id)
    except Exception:
        ws_manager.disconnect(ws, attempt_id)


@router.post("/{lesson_id}/attempt")
def ensure_lesson_attempt(
    lesson_id: str,
    learner_key: Optional[str] = None,
    class_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    try:
        lesson = load_lesson(lesson_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Lesson not found") from exc

    sync_lesson_record(db, lesson)
    db.commit()
    if class_id:
        _resolve_class_context(db, current_user, class_id)
    attempt = create_attempt(
        db,
        lesson_id=lesson.lesson_id,
        learner_key=learner_key,
        teacher_key=current_user.username,
        class_id=class_id,
    )
    return {"attempt_id": str(attempt.attempt_id)}


@router.post("/{lesson_id}/command-state/{attempt_id}/active-slide")
def command_state_set_active_slide(
    lesson_id: str,
    attempt_id: str,
    request: ActiveSlideRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    require_attempt_access(db, current_user, attempt_id, lesson_id=lesson_id)
    try:
        set_active_attempt_slide(db, lesson_id, attempt_id, request.slide_id)
        attempt = db.get(LessonAttemptRecord, attempt_id)
        if attempt is not None and attempt.class_id:
            session = get_class_session(db, str(attempt.class_id))
            if session is not None and session.status != "idle" and session.lesson_id == lesson_id:
                set_class_session_slide(db, class_id=str(attempt.class_id), slide_id=request.slide_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return get_command_state(db, lesson_id, attempt_id, request.slide_id)


@router.post("/{lesson_id}/command-state/{attempt_id}/advance", response_model=CommandStateResponse)
async def command_state_advance(
    lesson_id: str,
    attempt_id: str,
    request: CommandStateAdvanceRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    require_attempt_access(db, current_user, attempt_id, lesson_id=lesson_id)
    try:
        result = advance_command_state(db, lesson_id, attempt_id, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # Push to all WebSocket clients watching this attempt (board + teacher)
    background_tasks.add_task(ws_manager.broadcast, attempt_id, result.model_dump())
    return result


@router.post("/{lesson_id}/complete", response_model=LessonCompleteResponse)
def complete_lesson(
    lesson_id: str,
    request: LessonCompleteRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    attempt = require_attempt_access(db, current_user, request.attempt_id, lesson_id=lesson_id)
    if attempt and attempt.lesson_id == lesson_id:
        unresolved_oral_session = (
            db.execute(
                select(OralCheckSessionRecord).where(
                    OralCheckSessionRecord.attempt_id == request.attempt_id,
                    OralCheckSessionRecord.unresolved_student_count > 0,
                )
            )
            .scalars()
            .first()
        )
        if unresolved_oral_session is not None:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot complete lesson: oral check unresolved for slide {unresolved_oral_session.slide_id}",
            )
        if request.expected_attempt_version is not None and attempt.version != request.expected_attempt_version:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Lesson attempt conflict: expected version {request.expected_attempt_version}, "
                    f"found {attempt.version}"
                ),
            )
        attempt.completed = True
        attempt.version += 1
        db.flush()
        finalize_attempt_summary(db, attempt)
        return LessonCompleteResponse(ok=True, attempt_version=attempt.version)
    return LessonCompleteResponse(ok=True, attempt_version=0)
