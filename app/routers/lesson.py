from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.services.lesson_navigation import flatten_lesson_slides
from app.db import get_db
from app.models.lesson import ClassRecord, LessonAttemptRecord
from app.schemas.marking import SlideMarkRequest, SlideMarkResponse, StudentMarkDeleteRequest, StudentMarkRequest, StudentMarkResponse
from app.services.class_service import get_all_classes, get_students_for_class
from app.services.lesson_service import load_lesson, load_all_lessons, ordered_blocks, sync_lesson_record
from app.services.marking_service import create_attempt, delete_student_mark, record_slide_mark, record_student_mark
from app.services.review_service import get_review_data

router = APIRouter(prefix="/lesson", tags=["lesson"])
templates = Jinja2Templates(directory="app/templates")


def _resolve_roster(db: Session, class_id: Optional[str]) -> tuple[list[str], str]:
    if not class_id:
        return [], ""
    students = get_students_for_class(db, class_id)
    cls = db.get(ClassRecord, class_id)
    class_name = cls.class_name if cls else ""
    return [s.student_name for s in students], class_name


@router.get("/")
def lesson_index(request: Request, db: Session = Depends(get_db)):
    lessons = load_all_lessons()
    classes = get_all_classes(db)
    return templates.TemplateResponse(
        "lesson/index.html",
        {
            "request": request,
            "lessons": lessons,
            "classes": classes,
        },
    )


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
    ordered_slides = flatten_lesson_slides(lesson)
    attempt = create_attempt(
        db,
        lesson_id=lesson.lesson_id,
        learner_key=learner_key,
        teacher_key=teacher_key,
        class_id=class_id,
    )

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
            "class_id": class_id or "",
            "class_name": class_name,
            "roster": roster,
            "no_class_selected": not class_id,
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
    ordered_slides = flatten_lesson_slides(lesson)
    initial_slide_index = next(
        (entry["slide_index"] for entry in ordered_slides if entry["slide"].block_id == block_id),
        0,
    )
    attempt = create_attempt(
        db,
        lesson_id=lesson.lesson_id,
        learner_key=learner_key,
        teacher_key=teacher_key,
        class_id=class_id,
    )

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
            "class_id": class_id or "",
            "class_name": class_name,
            "roster": roster,
            "no_class_selected": not class_id,
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


@router.post("/{lesson_id}/complete")
def complete_lesson(
    lesson_id: str,
    attempt_id: str = Body(..., embed=True),
    db: Session = Depends(get_db),
):
    attempt = db.get(LessonAttemptRecord, attempt_id)
    if attempt and attempt.lesson_id == lesson_id:
        attempt.completed = True
        db.commit()
    return {"ok": True}
