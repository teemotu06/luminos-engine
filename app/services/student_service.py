from collections import Counter, defaultdict
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.lesson import LessonAttemptRecord, StudentMarkRecord
from app.services.lesson_service import load_lesson


def get_student_profile(
    db: Session,
    student_name: str,
    class_id: Optional[str] = None,
) -> dict:
    query = (
        select(StudentMarkRecord, LessonAttemptRecord)
        .join(LessonAttemptRecord, StudentMarkRecord.attempt_id == LessonAttemptRecord.attempt_id)
        .where(StudentMarkRecord.student_name == student_name)
    )

    if class_id is not None:
        query = query.where(LessonAttemptRecord.class_id == class_id)

    query = query.order_by(
        StudentMarkRecord.lesson_id,
        StudentMarkRecord.block_id,
        StudentMarkRecord.slide_id,
    )

    rows = db.execute(query).all()
    marks = [row[0] for row in rows]
    attempt_map = {str(row[0].attempt_id): row[1] for row in rows}

    # Cache lesson metadata from JSON files
    lesson_cache: dict = {}
    for mark in marks:
        if mark.lesson_id not in lesson_cache:
            try:
                lesson = load_lesson(mark.lesson_id)
                lesson_cache[mark.lesson_id] = {
                    "title": lesson.title,
                    "target_pattern": lesson.target_pattern,
                }
            except FileNotFoundError:
                lesson_cache[mark.lesson_id] = {
                    "title": mark.lesson_id,
                    "target_pattern": "",
                }

    # Build lessons dict: lesson_id -> lesson group
    lessons: dict = {}
    for mark in marks:
        lid = mark.lesson_id
        if lid not in lessons:
            attempt = attempt_map.get(str(mark.attempt_id))
            lessons[lid] = {
                "lesson_id": lid,
                "lesson_title": lesson_cache[lid]["title"],
                "target_pattern": lesson_cache[lid]["target_pattern"],
                "attempt_date": attempt.attempt_date if attempt else None,
                "blocks": {},
            }
        blocks = lessons[lid]["blocks"]
        blocks.setdefault(mark.block_id, {})
        blocks[mark.block_id][mark.slide_id] = mark

    # Overall status counts
    status_counts = dict(Counter(mark.status for mark in marks))

    # Missed/shaky pattern summary
    pattern_tally: dict = defaultdict(lambda: {"missed": 0, "shaky": 0})
    for mark in marks:
        if mark.status in ("missed", "shaky"):
            raw_pattern = lesson_cache.get(mark.lesson_id, {}).get("target_pattern", "")
            if raw_pattern:
                for part in raw_pattern.split(" · "):
                    pattern_tally[part.strip()][mark.status] += 1

    missed_shaky_patterns = sorted(
        [
            {
                "pattern": p,
                "missed": counts["missed"],
                "shaky": counts["shaky"],
                "total": counts["missed"] + counts["shaky"],
            }
            for p, counts in pattern_tally.items()
        ],
        key=lambda x: -x["total"],
    )

    return {
        "student_name": student_name,
        "class_id": class_id,
        "lessons": lessons,
        "status_counts": status_counts,
        "missed_shaky_patterns": missed_shaky_patterns,
        "total_marks": len(marks),
    }
