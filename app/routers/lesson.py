import re
import json
import logging
from itertools import groupby
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.services.lesson_navigation import flatten_lesson_slides
from app.db import get_db
from app.models.lesson import ClassPatternReviewRecord, ClassRecord, LessonAttemptRecord, OralCheckSessionRecord
from app.schemas.marking import SlideMarkRequest, SlideMarkResponse, StudentMarkDeleteRequest, StudentMarkRequest, StudentMarkResponse
from app.schemas.oral_check import (
    OralCheckAssignmentMarkRequest,
    OralCheckAssignmentMarkResponse,
    OralCheckCompleteRequest,
    OralCheckSessionResponse,
    OralCheckSessionStartRequest,
)
from app.schemas.tts import TtsPromptRequest, TtsPromptResponse
from app.services.class_service import get_all_classes, get_students_for_class
from app.services.lesson_service import (
    KI_INSERTION_MAP,
    get_intervention_anchor,
    load_lesson,
    load_all_lessons,
    ordered_blocks,
    sync_lesson_record,
)
from app.services.mastery_gate_service import get_class_lesson_gate_summaries
from app.services.marking_service import create_attempt, delete_student_mark, record_slide_mark, record_student_mark
from app.services.oral_check_service import complete_oral_check_session, get_oral_check_session, mark_oral_check_assignment, start_oral_check_session
from app.services.kokoro_tts_service import KokoroTtsError, ensure_tts_audio
from app.services.review_service import get_review_data
from app.services.review_scheduler_service import (
    build_dynamic_review_slides,
    get_class_review_recommendations,
    inject_dynamic_review_into_lesson,
    update_class_pattern_review,
)

router = APIRouter(prefix="/lesson", tags=["lesson"])
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger(__name__)


def _resolve_roster(db: Session, class_id: Optional[str]) -> tuple[list[str], str]:
    if not class_id:
        return [], ""
    students = get_students_for_class(db, class_id)
    cls = db.get(ClassRecord, class_id)
    class_name = cls.class_name if cls else ""
    return [s.student_name for s in students], class_name


def _natural_key(s: str) -> list:
    """Split a string into text/number chunks for natural sort order.
    e.g. 'G10' → ['G', 10] so G2 < G10.
    """
    return [int(c) if c.isdigit() else c for c in re.split(r"(\d+)", s)]


@router.get("/")
def lesson_index(request: Request, db: Session = Depends(get_db)):
    lessons = load_all_lessons()
    classes = get_all_classes(db)
    sorted_lessons = sorted(lessons, key=lambda l: _natural_key(l.unit_id))
    ki_anchors = {lesson.lesson_id: get_intervention_anchor(lesson.lesson_id) for lesson in lessons}

    # Build class_review_map efficiently:
    # One DB query per class (not one per class × lesson).
    # Individual follow-up flags are skipped here — they're shown on the review page.
    class_review_map = {}
    for cls in classes:
        preloaded = (
            db.execute(
                select(ClassPatternReviewRecord)
                .where(ClassPatternReviewRecord.class_id == cls["id"])
                .order_by(
                    ClassPatternReviewRecord.priority_score.desc(),
                    ClassPatternReviewRecord.updated_at.desc(),
                )
            )
            .scalars()
            .all()
        )
        class_review_map[cls["id"]] = {
            lesson.lesson_id: get_class_review_recommendations(
                db,
                cls["id"],
                lesson.lesson_id,
                preloaded_records=preloaded,
                skip_individual_flags=True,
            )
            for lesson in lessons
            if lesson.lesson_id.startswith("G")
        }

    lesson_groups = [
        {"unit_id": k, "lessons": list(v)}
        for k, v in groupby(sorted_lessons, key=lambda l: l.unit_id)
    ]
    return templates.TemplateResponse(
        "lesson/index.html",
        {
            "request": request,
            "lessons": lessons,
            "lesson_groups": lesson_groups,
            "classes": classes,
            "ki_anchors": ki_anchors,
            "ki_insertion_map": KI_INSERTION_MAP,
            "class_review_map": class_review_map,
            "class_review_map_json": json.dumps(class_review_map),
        },
    )


@router.get("/mastery-gates")
def lesson_mastery_gates(class_id: str, db: Session = Depends(get_db)):
    """Return compact gate summaries for all lessons with any class attempt.

    Used by the lesson library to show per-card gate indicators when a class
    is selected. Returns lesson_id → {gate_level, gate_label, secure_count,
    weak_count, marked_count}.
    """
    return get_class_lesson_gate_summaries(db, class_id)


@router.get("/progress")
def lesson_progress(class_id: str, db: Session = Depends(get_db)):
    """Return teaching progress for each lesson within a class.

    Returns a dict mapping lesson_id → "completed" | "in_progress".
    Lessons with no attempts for this class are omitted.
    """
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
    teacher_key: Optional[str] = None,
    class_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    try:
        lesson = load_lesson(lesson_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Lesson not found")

    sync_lesson_record(db, lesson)
    db.commit()

    roster, class_name = _resolve_roster(db, class_id)
    dynamic_review_recommendations = None
    if class_id and lesson.lesson_id.startswith("G"):
        try:
            dynamic_review_recommendations = get_class_review_recommendations(db, class_id, lesson.lesson_id)
        except Exception:
            logger.exception(
                "Dynamic review recommendation lookup failed for lesson_id=%s class_id=%s",
                lesson.lesson_id,
                class_id,
            )
    runtime_lesson = inject_dynamic_review_into_lesson(lesson, dynamic_review_recommendations)
    ordered_slides = flatten_lesson_slides(runtime_lesson)
    attempt = create_attempt(
        db,
        lesson_id=runtime_lesson.lesson_id,
        learner_key=learner_key,
        teacher_key=teacher_key,
        class_id=class_id,
    )

    return templates.TemplateResponse(
        "lesson/view.html",
        {
            "request": request,
            "lesson": runtime_lesson,
            "ordered_blocks": ordered_blocks(runtime_lesson),
            "ordered_slides": ordered_slides,
            "attempt_id": str(attempt.attempt_id),
            "learner_key": learner_key or "",
            "teacher_key": teacher_key or "",
            "class_id": class_id or "",
            "class_name": class_name,
            "roster": roster,
            "no_class_selected": not class_id,
            "dynamic_review_recommendations": dynamic_review_recommendations,
            "dynamic_review_slides": build_dynamic_review_slides(dynamic_review_recommendations),
        },
    )


@router.get("/{lesson_id}/block/{block_id}")
def get_lesson_block(
    request: Request,
    lesson_id: str,
    block_id: str,
    learner_key: Optional[str] = None,
    teacher_key: Optional[str] = None,
    class_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    try:
        lesson = load_lesson(lesson_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Lesson not found")

    if block_id not in lesson.blocks:
        raise HTTPException(status_code=404, detail="Block not found")

    sync_lesson_record(db, lesson)
    db.commit()

    roster, class_name = _resolve_roster(db, class_id)
    dynamic_review_recommendations = None
    if class_id and lesson.lesson_id.startswith("G"):
        try:
            dynamic_review_recommendations = get_class_review_recommendations(db, class_id, lesson.lesson_id)
        except Exception:
            logger.exception(
                "Dynamic review recommendation lookup failed for block lesson_id=%s class_id=%s",
                lesson.lesson_id,
                class_id,
            )
    runtime_lesson = inject_dynamic_review_into_lesson(lesson, dynamic_review_recommendations)
    ordered_slides = flatten_lesson_slides(runtime_lesson)
    initial_slide_index = next(
        (entry["slide_index"] for entry in ordered_slides if entry["slide"].block_id == block_id),
        0,
    )
    attempt = create_attempt(
        db,
        lesson_id=runtime_lesson.lesson_id,
        learner_key=learner_key,
        teacher_key=teacher_key,
        class_id=class_id,
    )

    return templates.TemplateResponse(
        "lesson/view.html",
        {
            "request": request,
            "lesson": runtime_lesson,
            "ordered_blocks": ordered_blocks(runtime_lesson),
            "ordered_slides": ordered_slides,
            "attempt_id": str(attempt.attempt_id),
            "learner_key": learner_key or "",
            "teacher_key": teacher_key or "",
            "initial_slide_index": initial_slide_index,
            "class_id": class_id or "",
            "class_name": class_name,
            "roster": roster,
            "no_class_selected": not class_id,
            "dynamic_review_recommendations": dynamic_review_recommendations,
            "dynamic_review_slides": build_dynamic_review_slides(dynamic_review_recommendations),
        },
    )


@router.get("/{lesson_id}/review/{attempt_id}")
def lesson_review(
    request: Request,
    lesson_id: str,
    attempt_id: str,
    db: Session = Depends(get_db),
):
    data = get_review_data(db, lesson_id, attempt_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Review not found")
    return templates.TemplateResponse(
        "lesson/review.html",
        {"request": request, **data},
    )


@router.post("/{lesson_id}/mark", response_model=SlideMarkResponse)
def mark_slide(
    lesson_id: str,
    mark: SlideMarkRequest,
    db: Session = Depends(get_db),
):
    if mark.lesson_id != lesson_id:
        raise HTTPException(status_code=400, detail="Lesson ID mismatch")

    try:
        attempt = record_slide_mark(db, mark)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return SlideMarkResponse(
        attempt_id=str(attempt.attempt_id),
        mastery_status=attempt.mastery_status,
        next_recommendation=attempt.next_recommendation,
        phoneme_error_log_size=len(attempt.phoneme_error_log or []),
    )


@router.post("/{lesson_id}/student-mark", response_model=StudentMarkResponse)
def mark_student_slide(
    lesson_id: str,
    mark: StudentMarkRequest,
    db: Session = Depends(get_db),
):
    if mark.lesson_id != lesson_id:
        raise HTTPException(status_code=400, detail="Lesson ID mismatch")

    try:
        record = record_student_mark(db, mark)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return StudentMarkResponse(
        id=str(record.id),
        student_name=record.student_name,
        status=record.status,
    )


@router.delete("/{lesson_id}/student-mark")
def delete_student_slide_mark(
    lesson_id: str,
    mark: StudentMarkDeleteRequest,
    db: Session = Depends(get_db),
):
    if mark.lesson_id != lesson_id:
        raise HTTPException(status_code=400, detail="Lesson ID mismatch")
    delete_student_mark(db, mark.attempt_id, mark.slide_id, mark.student_name)
    return {"ok": True}


@router.post("/{lesson_id}/oral-check/session/start", response_model=OralCheckSessionResponse)
def oral_check_start(
    lesson_id: str,
    request: OralCheckSessionStartRequest,
    db: Session = Depends(get_db),
):
    if request.lesson_id != lesson_id:
        raise HTTPException(status_code=400, detail="Lesson ID mismatch")
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
):
    attempt = db.get(LessonAttemptRecord, attempt_id)
    if attempt is None or attempt.lesson_id != lesson_id:
        raise HTTPException(status_code=404, detail="Lesson attempt not found")
    try:
        return get_oral_check_session(db, attempt_id, slide_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{lesson_id}/oral-check/assignment/mark", response_model=OralCheckAssignmentMarkResponse)
def oral_check_mark(
    lesson_id: str,
    request: OralCheckAssignmentMarkRequest,
    db: Session = Depends(get_db),
):
    try:
        return mark_oral_check_assignment(db, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{lesson_id}/oral-check/session/complete", response_model=OralCheckSessionResponse)
def oral_check_complete(
    lesson_id: str,
    request: OralCheckCompleteRequest,
    db: Session = Depends(get_db),
):
    try:
        session = complete_oral_check_session(db, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if session.session_status != "complete":
        raise HTTPException(status_code=400, detail="Oral check session incomplete")
    return session


@router.post("/tts/prompt", response_model=TtsPromptResponse)
def tts_prompt(request: TtsPromptRequest):
    try:
        payload = ensure_tts_audio(request.text)
    except KokoroTtsError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return TtsPromptResponse(**payload)


@router.post("/{lesson_id}/complete")
def complete_lesson(
    lesson_id: str,
    attempt_id: str = Body(..., embed=True),
    db: Session = Depends(get_db),
):
    attempt = db.get(LessonAttemptRecord, attempt_id)
    if attempt and attempt.lesson_id == lesson_id:
        unresolved_oral_session = (
            db.execute(
                select(OralCheckSessionRecord).where(
                    OralCheckSessionRecord.attempt_id == attempt_id,
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
        attempt.completed = True
        db.flush()
        # Update class review state once at lesson completion rather than on every slide mark.
        update_class_pattern_review(db, attempt)
        db.commit()
    return {"ok": True}
