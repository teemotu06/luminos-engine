from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.services.lesson_navigation import flatten_lesson_slides
from app.db import get_db
from app.schemas.marking import SlideMarkRequest, SlideMarkResponse
from app.services.lesson_service import load_lesson, load_all_lessons, ordered_blocks, sync_lesson_record
from app.services.marking_service import create_attempt, record_slide_mark

router = APIRouter(prefix="/lesson", tags=["lesson"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def lesson_index(request: Request):
    lessons = load_all_lessons()
    return templates.TemplateResponse(
        "lesson/index.html",
        {
            "request": request,
            "lessons": lessons,
        },
    )


@router.get("/{lesson_id}")
def get_lesson(
    request: Request,
    lesson_id: str,
    learner_key: Optional[str] = None,
    teacher_key: Optional[str] = None,
    db: Session = Depends(get_db),
):
    try:
        lesson = load_lesson(lesson_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Lesson not found")

    sync_lesson_record(db, lesson)
    db.commit()

    ordered_slides = flatten_lesson_slides(lesson)
    attempt = create_attempt(db, lesson_id=lesson.lesson_id, learner_key=learner_key, teacher_key=teacher_key)

    return templates.TemplateResponse(
        "lesson/view.html",
        {
            "request": request,
            "lesson": lesson,
            "ordered_blocks": ordered_blocks(lesson),
            "ordered_slides": ordered_slides,
            "attempt_id": str(attempt.attempt_id),
            "learner_key": learner_key or "",
            "teacher_key": teacher_key or "",
        },
    )


@router.get("/{lesson_id}/block/{block_id}")
def get_lesson_block(
    request: Request,
    lesson_id: str,
    block_id: str,
    learner_key: Optional[str] = None,
    teacher_key: Optional[str] = None,
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

    ordered_slides = flatten_lesson_slides(lesson)
    initial_slide_index = next(
        (entry["slide_index"] for entry in ordered_slides if entry["slide"].block_id == block_id),
        0,
    )
    attempt = create_attempt(db, lesson_id=lesson.lesson_id, learner_key=learner_key, teacher_key=teacher_key)

    return templates.TemplateResponse(
        "lesson/view.html",
        {
            "request": request,
            "lesson": lesson,
            "ordered_blocks": ordered_blocks(lesson),
            "ordered_slides": ordered_slides,
            "attempt_id": str(attempt.attempt_id),
            "learner_key": learner_key or "",
            "teacher_key": teacher_key or "",
            "initial_slide_index": initial_slide_index,
        },
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
