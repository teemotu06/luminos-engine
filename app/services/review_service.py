from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.lesson import ClassRecord, LessonAttemptRecord, StudentMarkRecord
from app.services.class_service import get_students_for_class
from app.services.lesson_service import load_lesson


def get_review_data(db: Session, lesson_id: str, attempt_id: str) -> dict:
    attempt = db.get(LessonAttemptRecord, attempt_id)
    if attempt is None or attempt.lesson_id != lesson_id:
        return None

    try:
        lesson = load_lesson(lesson_id)
    except FileNotFoundError:
        return None

    # Class name
    class_name: Optional[str] = None
    roster: list[str] = []
    if attempt.class_id:
        cls = db.get(ClassRecord, attempt.class_id)
        if cls:
            class_name = cls.class_name
        students = get_students_for_class(db, attempt.class_id)
        roster = [s.student_name for s in students]

    # Markable blocks: only blocks that have at least one markable slide
    markable_blocks: dict = {}
    for block_id, block in lesson.blocks.items():
        markable_slides = [s for s in block.slides if s.markable]
        if markable_slides:
            markable_blocks[block_id] = {
                "label": block.label,
                "slides": [
                    {"slide_id": s.slide_id, "slide_title": s.slide_title, "block_id": s.block_id}
                    for s in markable_slides
                ],
            }

    # Load all student marks for this attempt
    marks = (
        db.execute(
            select(StudentMarkRecord).where(StudentMarkRecord.attempt_id == attempt_id)
        )
        .scalars()
        .all()
    )

    # marks_json keyed by "slide_id__student_name"
    marks_json: dict = {}
    for m in marks:
        key = f"{m.slide_id}__{m.student_name}"
        marks_json[key] = {
            "id": str(m.id),
            "status": m.status,
            "error_tags": m.error_tags or [],
            "support_level": m.support_level,
            "teacher_note": m.teacher_note or "",
        }

    return {
        "lesson": lesson,
        "attempt_id": attempt_id,
        "attempt_date": attempt.attempt_date,
        "class_id": attempt.class_id or "",
        "class_name": class_name or "",
        "mastery_status": attempt.mastery_status,
        "next_recommendation": attempt.next_recommendation,
        "roster": roster,
        "markable_blocks": markable_blocks,
        "marks_json": marks_json,
    }
