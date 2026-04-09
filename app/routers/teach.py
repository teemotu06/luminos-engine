import re
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.lesson import LessonAttemptRecord
from app.services.auth_service import require_class_access, require_current_user
from app.services.class_service import get_all_classes
from app.services.lesson_service import load_all_lessons
from app.template_env import templates

router = APIRouter(tags=["teach"])
logger = logging.getLogger(__name__)


def _natural_key(s: str) -> list:
    return [int(c) if c.isdigit() else c for c in re.split(r"(\d+)", s)]


def _load_ordered_lessons() -> list:
    return sorted(load_all_lessons(), key=lambda l: _natural_key(l.lesson_id))


def _next_lesson_for_class(
    db: Session,
    class_id: str,
    all_lessons: list,
    lesson_index: dict,
    lesson_map: dict,
) -> tuple[Optional[object], str]:
    """Return (lesson, status) for the given class.

    status is one of: in_progress, ready, not_started, finished.
    lesson is None only when status == finished.
    """
    in_progress = (
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
    if in_progress:
        return lesson_map.get(in_progress.lesson_id) or (all_lessons[0] if all_lessons else None), "in_progress"

    last_completed = (
        db.execute(
            select(LessonAttemptRecord)
            .where(
                LessonAttemptRecord.class_id == class_id,
                LessonAttemptRecord.completed.is_(True),
            )
            .order_by(LessonAttemptRecord.attempt_date.desc())
        )
        .scalars()
        .first()
    )
    if last_completed:
        last_idx = lesson_index.get(last_completed.lesson_id, -1)
        next_lesson = all_lessons[last_idx + 1] if 0 <= last_idx + 1 < len(all_lessons) else None
        if next_lesson:
            return next_lesson, "ready"
        return None, "finished"

    return all_lessons[0] if all_lessons else None, "not_started"


@router.get("/teach")
def teach_home(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    owner_user_id = None if current_user.role == "admin" else str(current_user.id)
    classes = get_all_classes(db, owner_user_id=owner_user_id, include_deleted=False)

    all_lessons = _load_ordered_lessons()
    lesson_index = {l.lesson_id: i for i, l in enumerate(all_lessons)}
    lesson_map = {l.lesson_id: l for l in all_lessons}

    class_ids = [cls["id"] for cls in classes]

    # Bulk-fetch all attempts in two queries rather than 2N
    if class_ids:
        in_progress_rows = (
            db.execute(
                select(LessonAttemptRecord)
                .where(
                    LessonAttemptRecord.class_id.in_(class_ids),
                    LessonAttemptRecord.completed.is_(False),
                )
                .order_by(LessonAttemptRecord.attempt_date.desc())
            )
            .scalars()
            .all()
        )
        completed_rows = (
            db.execute(
                select(LessonAttemptRecord)
                .where(
                    LessonAttemptRecord.class_id.in_(class_ids),
                    LessonAttemptRecord.completed.is_(True),
                )
                .order_by(LessonAttemptRecord.attempt_date.desc())
            )
            .scalars()
            .all()
        )
        in_progress_by_class: dict = {}
        for a in in_progress_rows:
            if a.class_id not in in_progress_by_class:
                in_progress_by_class[a.class_id] = a

        last_completed_by_class: dict = {}
        for a in completed_rows:
            if a.class_id not in last_completed_by_class:
                last_completed_by_class[a.class_id] = a
    else:
        in_progress_by_class = {}
        last_completed_by_class = {}

    class_cards = []
    for cls in classes:
        cid = cls["id"]
        in_progress = in_progress_by_class.get(cid)
        last_completed = last_completed_by_class.get(cid)

        if in_progress:
            lesson = lesson_map.get(in_progress.lesson_id)
            status = "in_progress"
            cta = "Resume teaching"
        elif last_completed:
            last_idx = lesson_index.get(last_completed.lesson_id, -1)
            next_lesson = all_lessons[last_idx + 1] if 0 <= last_idx + 1 < len(all_lessons) else None
            if next_lesson:
                lesson = next_lesson
                status = "ready"
                cta = "Start teaching"
            else:
                lesson = None
                status = "finished"
                cta = "All lessons taught"
        else:
            lesson = all_lessons[0] if all_lessons else None
            status = "not_started"
            cta = "Start teaching"

        phonemes = []
        if lesson and lesson.target_pattern:
            phonemes = [p.strip() for p in lesson.target_pattern.split("·") if p.strip()]

        class_cards.append({
            "id": cid,
            "class_name": cls["class_name"],
            "student_count": cls["student_count"],
            "lesson_id": lesson.lesson_id if lesson else None,
            "lesson_title": lesson.title if lesson else None,
            "phonemes": phonemes,
            "status": status,
            "cta": cta,
        })

    return templates.TemplateResponse(
        request,
        "teach/index.html",
        {"class_cards": class_cards, "current_user": current_user},
    )


@router.get("/teach/class/{class_id}/start")
def start_teaching_class(
    class_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    """Redirect to the right teacher view for a class based on its current progress."""
    require_class_access(db, current_user, class_id, include_deleted=False)

    all_lessons = _load_ordered_lessons()
    lesson_index = {l.lesson_id: i for i, l in enumerate(all_lessons)}
    lesson_map = {l.lesson_id: l for l in all_lessons}

    lesson, status = _next_lesson_for_class(db, class_id, all_lessons, lesson_index, lesson_map)

    if lesson is None:
        # All lessons finished — send to lesson library for this class
        return RedirectResponse(url=f"/lesson/?class_id={class_id}", status_code=302)

    return RedirectResponse(
        url=f"/classes/{class_id}/control?lesson_id={lesson.lesson_id}",
        status_code=302,
    )
