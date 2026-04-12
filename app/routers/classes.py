import json
import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.requests import Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.lesson import ClassRecord, ClassSessionRecord, LessonAttemptRecord
from app.services.auth_service import require_class_access, require_current_user
from app.services.class_service import (
    add_student_to_class,
    archive_class,
    create_class,
    get_all_classes,
    get_class_with_students,
    restore_class,
)
from app.services.knowledge_service import (
    create_or_update_course_plan,
    get_course_plan,
    get_curriculum,
    list_curricula,
    plan_summary,
)

logger = logging.getLogger(__name__)
from app.services.class_session_service import (
    class_session_payload,
    ensure_class_session,
    get_class_session,
    list_control_lessons,
    move_class_session_slide,
    pause_class_session,
    set_drag_letter_selection,
    set_class_session_message,
    set_class_session_slide,
    set_letter_reveal_count,
    set_pattern_noticing_reveal_count,
    set_spell_word_selection,
    start_class_session,
    stop_class_session,
)
from app.template_env import templates

router = APIRouter(prefix="/classes", tags=["classes"])


@router.get("/")
def class_list(request: Request, db: Session = Depends(get_db), current_user=Depends(require_current_user)):
    owner_user_id = None if current_user.role == "admin" else str(current_user.id)
    classes = get_all_classes(db, owner_user_id=owner_user_id, include_deleted=False)
    archived_classes = get_all_classes(db, owner_user_id=owner_user_id, include_deleted=True)
    archived_classes = [cls for cls in archived_classes if cls["deleted_at"] is not None]
    return templates.TemplateResponse(
        request,
        "classes/index.html",
        {"classes": classes, "archived_classes": archived_classes, "current_user": current_user},
    )


@router.get("/new")
def new_class_form(request: Request, current_user=Depends(require_current_user)):
    return templates.TemplateResponse(
        request,
        "classes/new.html",
        {"error": None, "curricula": list_curricula(), "current_user": current_user},
    )


@router.post("/new")
def create_class_submit(
    request: Request,
    class_name: str = Form(...),
    description: str = Form(""),
    # Optional course plan fields
    with_plan: str = Form(""),
    curriculum_id: str = Form(""),
    start_date: str = Form(""),
    teaching_days_json: str = Form("[]"),
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    name = class_name.strip()
    if not name:
        return templates.TemplateResponse(
            request,
            "classes/new.html",
            {"error": "Class name cannot be empty", "curricula": list_curricula(), "current_user": current_user},
            status_code=422,
        )
    cls = create_class(
        db,
        class_name=name,
        description=description.strip() or None,
        owner_user_id=None if current_user.role == "admin" else str(current_user.id),
    )

    # Attach a course plan if the toggle was checked and all plan fields are present
    if with_plan == "1" and curriculum_id and start_date:
        try:
            parsed_date = date.fromisoformat(start_date)
            teaching_days = json.loads(teaching_days_json)
            teaching_days = [int(d) for d in teaching_days]
            if teaching_days:
                create_or_update_course_plan(
                    db,
                    class_id=str(cls.id),
                    curriculum_id=curriculum_id,
                    start_date=parsed_date,
                    teaching_days=teaching_days,
                )
        except Exception:
            logger.warning("course_plan.attach_failed class_id=%s", cls.id, exc_info=True)

    return RedirectResponse(url=f"/classes/{cls.id}", status_code=303)


@router.get("/{class_id}")
def class_detail(
    request: Request,
    class_id: str,
    error: str = "",
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    require_class_access(db, current_user, class_id, include_deleted=True)
    cls = get_class_with_students(db, class_id, include_deleted=True)
    if cls is None:
        raise HTTPException(status_code=404, detail="Class not found")
    plan = get_course_plan(db, class_id)
    curriculum = get_curriculum(plan.curriculum_id) if plan else None
    return templates.TemplateResponse(
        request,
        "classes/detail.html",
        {
            "cls": cls,
            "error": error,
            "plan_summary": plan_summary(plan, curriculum) if plan else None,
            "current_user": current_user,
        },
    )


@router.post("/{class_id}/students")
def add_student(
    class_id: str,
    student_name: str = Form(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    require_class_access(db, current_user, class_id)
    try:
        add_student_to_class(db, class_id=class_id, student_name=student_name)
    except ValueError as exc:
        return RedirectResponse(
            url=f"/classes/{class_id}?error={str(exc)}",
            status_code=303,
        )
    return RedirectResponse(url=f"/classes/{class_id}", status_code=303)


@router.post("/{class_id}/archive")
def archive_class_submit(
    class_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    require_class_access(db, current_user, class_id)
    archive_class(db, class_id)
    return RedirectResponse(url="/classes/", status_code=303)


@router.post("/{class_id}/restore")
def restore_class_submit(
    class_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    require_class_access(db, current_user, class_id, include_deleted=True)
    restore_class(db, class_id)
    return RedirectResponse(url=f"/classes/{class_id}", status_code=303)


def _get_active_attempt_for_class(db: Session, class_id: str) -> Optional[LessonAttemptRecord]:
    """Return the most recent non-completed attempt for a class, or None."""
    return (
        db.execute(
            select(LessonAttemptRecord)
            .where(
                LessonAttemptRecord.class_id == class_id,
                LessonAttemptRecord.completed.is_(False),
            )
            .order_by(LessonAttemptRecord.attempt_date.desc())
        )
        .scalars()
        .first()
    )


def _get_active_session_for_class(db: Session, class_id: str) -> Optional[ClassSessionRecord]:
    session = get_class_session(db, class_id)
    if session is None or session.status == "idle" or not session.lesson_id:
        return None
    return session


@router.get("/{class_id}/active-lesson")
def class_active_lesson(
    class_id: str,
    db: Session = Depends(get_db),
):
    """Return the current active lesson/attempt for a class. Used by the board to detect lesson switches.
    Public endpoint — the board display has no auth session."""
    session = _get_active_session_for_class(db, class_id)
    if session is None:
        return {"lesson_id": None, "attempt_id": None, "slide_id": None}
    return {
        "lesson_id": session.lesson_id,
        "attempt_id": str(session.attempt_id) if session.attempt_id else None,
        "slide_id": session.current_slide_id,
    }


@router.get("/{class_id}/session-state")
def class_session_state(
    class_id: str,
    db: Session = Depends(get_db),
):
    try:
        return class_session_payload(db, class_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{class_id}/board")
def class_board(
    request: Request,
    class_id: str,
    db: Session = Depends(get_db),
):
    """Public board display backed by the class_session control plane."""
    cls = db.get(ClassRecord, class_id)
    if cls is None:
        raise HTTPException(status_code=404, detail="Class not found")
    ensure_class_session(db, class_id)
    response = templates.TemplateResponse(
        request,
        "classes/board.html",
        {
            "class_id": class_id,
            "class_name": cls.class_name,
            "current_user": None,
        },
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/{class_id}/control")
def class_control(
    request: Request,
    class_id: str,
    lesson_id: str = "",
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    cls = require_class_access(db, current_user, class_id, include_deleted=True)
    ensure_class_session(db, class_id)
    response = templates.TemplateResponse(
        request,
        "classes/control.html",
        {
            "class_id": class_id,
            "class_name": cls.class_name,
            "suggested_lesson_id": lesson_id,
            "lessons": list_control_lessons(),
            "current_user": current_user,
        },
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@router.post("/{class_id}/control/start")
def class_control_start(
    class_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    require_class_access(db, current_user, class_id, include_deleted=True)
    lesson_id = str(payload.get("lesson_id", "")).strip()
    if not lesson_id:
        raise HTTPException(status_code=422, detail="lesson_id is required")
    try:
        start_class_session(db, class_id=class_id, lesson_id=lesson_id, teacher_key=current_user.username)
        return class_session_payload(db, class_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{class_id}/control/stop")
def class_control_stop(
    class_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    require_class_access(db, current_user, class_id, include_deleted=True)
    stop_class_session(db, class_id=class_id)
    return class_session_payload(db, class_id)


@router.post("/{class_id}/control/next")
def class_control_next(
    class_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    require_class_access(db, current_user, class_id, include_deleted=True)
    try:
        move_class_session_slide(db, class_id=class_id, step=1)
        return class_session_payload(db, class_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{class_id}/control/previous")
def class_control_previous(
    class_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    require_class_access(db, current_user, class_id, include_deleted=True)
    try:
        move_class_session_slide(db, class_id=class_id, step=-1)
        return class_session_payload(db, class_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{class_id}/control/pause")
def class_control_pause(
    class_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    require_class_access(db, current_user, class_id, include_deleted=True)
    paused = bool(payload.get("paused", True))
    pause_class_session(db, class_id=class_id, paused=paused)
    return class_session_payload(db, class_id)


@router.post("/{class_id}/control/slide")
def class_control_set_slide(
    class_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    require_class_access(db, current_user, class_id, include_deleted=True)
    slide_id = str(payload.get("slide_id", "")).strip()
    if not slide_id:
        raise HTTPException(status_code=422, detail="slide_id is required")
    try:
        set_class_session_slide(db, class_id=class_id, slide_id=slide_id)
        return class_session_payload(db, class_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{class_id}/control/message")
def class_control_set_message(
    class_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    require_class_access(db, current_user, class_id, include_deleted=True)
    set_class_session_message(db, class_id=class_id, message=payload.get("message"))
    return class_session_payload(db, class_id)


@router.post("/{class_id}/control/letter-reveal")
def class_control_letter_reveal(
    class_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    require_class_access(db, current_user, class_id, include_deleted=True)
    count = int(payload.get("count", 0))
    try:
        set_letter_reveal_count(db, class_id=class_id, count=count)
        return class_session_payload(db, class_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{class_id}/control/drag-letter-selection")
def class_control_drag_letter_selection(
    class_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    require_class_access(db, current_user, class_id, include_deleted=True)
    letters = payload.get("letters") or []
    if not isinstance(letters, list):
        raise HTTPException(status_code=422, detail="letters must be a list")
    try:
        set_drag_letter_selection(db, class_id=class_id, letters=letters)
        return class_session_payload(db, class_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{class_id}/control/pattern-noticing-reveal")
def class_control_pattern_noticing_reveal(
    class_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    require_class_access(db, current_user, class_id, include_deleted=True)
    count = int(payload.get("count", 0))
    try:
        set_pattern_noticing_reveal_count(db, class_id=class_id, count=count)
        return class_session_payload(db, class_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{class_id}/control/spell-word-selection")
def class_control_spell_word_selection(
    class_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    require_class_access(db, current_user, class_id, include_deleted=True)
    letters = payload.get("letters") or []
    if not isinstance(letters, list):
        raise HTTPException(status_code=422, detail="letters must be a list")
    try:
        set_spell_word_selection(db, class_id=class_id, letters=letters)
        return class_session_payload(db, class_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
