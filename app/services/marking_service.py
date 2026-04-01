from collections import Counter
from typing import Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.lesson import LessonAttemptRecord, SlideResultRecord, StudentMarkRecord
from app.schemas.marking import SlideMarkRequest, StudentMarkRequest
from app.services.review_scheduler_service import update_class_pattern_review


STATUS_PRIORITY = {"secure": 0, "shaky": 1, "missed": 2, "skipped": 3, "deferred": 3, "absent": 3}
RECOMMENDATION_MAP = {
    "secure": "move_on",
    "shaky": "move_on",
    "missed": "repeat",
    "deferred": "move_on",
    "absent": "move_on",
}


def create_attempt(
    db: Session,
    lesson_id: str,
    learner_key: Optional[str] = None,
    teacher_key: Optional[str] = None,
    class_id: Optional[str] = None,
) -> LessonAttemptRecord:
    attempt = LessonAttemptRecord(
        attempt_id=str(uuid4()),
        lesson_id=lesson_id,
        learner_key=learner_key,
        teacher_key=teacher_key,
        class_id=class_id,
        mastery_status="shaky",
        next_recommendation="move_on",
        phoneme_error_log=[],
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt


def _merge_item_results(mark: SlideMarkRequest) -> tuple[str, list[str], bool]:
    if not mark.item_results:
        return mark.status, mark.error_tags, mark.korean_transfer

    status = max(mark.item_results, key=lambda item: STATUS_PRIORITY[item.status]).status
    error_tags = sorted({tag for item in mark.item_results for tag in item.error_tags})
    korean_transfer = any(item.korean_transfer for item in mark.item_results)
    return status, error_tags, korean_transfer


def _rebuild_attempt_summary(db: Session, attempt: LessonAttemptRecord) -> None:
    results = (
        db.execute(
            select(SlideResultRecord)
            .where(SlideResultRecord.attempt_id == attempt.attempt_id)
            .order_by(SlideResultRecord.block_id, SlideResultRecord.slide_id)
        )
        .scalars()
        .all()
    )

    if not results:
        attempt.mastery_status = "shaky"
        attempt.next_recommendation = "move_on"
        attempt.phoneme_error_log = []
        return

    if any(result.status == "missed" for result in results):
        attempt.mastery_status = "missed"
    elif any(result.status == "shaky" for result in results):
        attempt.mastery_status = "shaky"
    else:
        attempt.mastery_status = "secure"

    phoneme_error_log = []

    for result in results:
        for item in result.item_results:
            phoneme = item.get("phoneme")
            if not phoneme or item.get("status") == "secure":
                continue
            for tag in item.get("error_tags", []):
                phoneme_error_log.append(
                    {
                        "phoneme": phoneme,
                        "error_tag": tag,
                        "korean_transfer": item.get("korean_transfer", False),
                        "lesson_id": attempt.lesson_id,
                        "block_id": result.block_id,
                    }
                )

    if not phoneme_error_log:
        for result in results:
            if result.status == "secure":
                continue
            for tag in result.error_tags:
                phoneme_error_log.append(
                    {
                        "phoneme": None,
                        "error_tag": tag,
                        "korean_transfer": result.korean_transfer,
                        "lesson_id": attempt.lesson_id,
                        "block_id": result.block_id,
                    }
                )

    attempt.phoneme_error_log = phoneme_error_log
    attempt.next_recommendation = RECOMMENDATION_MAP.get(attempt.mastery_status, "move_on")

    if attempt.learner_key:
        current_lesson_number = _lesson_number(attempt.lesson_id)
        if current_lesson_number is not None:
            previous_attempt = (
                db.execute(
                    select(LessonAttemptRecord)
                    .where(
                        LessonAttemptRecord.learner_key == attempt.learner_key,
                        LessonAttemptRecord.lesson_id != attempt.lesson_id,
                    )
                    .order_by(LessonAttemptRecord.attempt_date.desc())
                )
                .scalars()
                .first()
            )
            if previous_attempt and _lesson_number(previous_attempt.lesson_id) == current_lesson_number - 1:
                repeated = _repeated_problem_phoneme(previous_attempt.phoneme_error_log, phoneme_error_log)
                if repeated:
                    attempt.next_recommendation = "support"


def _lesson_number(lesson_id: str) -> Optional[int]:
    try:
        return int(lesson_id.split("-L", 1)[1])
    except (IndexError, ValueError):
        return None


def _repeated_problem_phoneme(previous_log: list, current_log: list) -> Optional[str]:
    previous_phonemes = Counter(item.get("phoneme") for item in previous_log if item.get("phoneme"))
    current_phonemes = Counter(item.get("phoneme") for item in current_log if item.get("phoneme"))

    for phoneme in current_phonemes:
        if phoneme in previous_phonemes:
            return phoneme
    return None


def delete_student_mark(
    db: Session,
    attempt_id: str,
    slide_id: str,
    student_name: str,
) -> None:
    existing = (
        db.execute(
            select(StudentMarkRecord).where(
                StudentMarkRecord.attempt_id == attempt_id,
                StudentMarkRecord.slide_id == slide_id,
                StudentMarkRecord.student_name == student_name,
            )
        )
        .scalars()
        .first()
    )
    if existing is not None:
        db.delete(existing)
        db.commit()


def record_student_mark(db: Session, mark: StudentMarkRequest) -> StudentMarkRecord:
    attempt = db.get(LessonAttemptRecord, mark.attempt_id)
    if attempt is None:
        raise ValueError(f"Unknown attempt_id {mark.attempt_id}")
    if attempt.lesson_id != mark.lesson_id:
        raise ValueError("Attempt lesson_id does not match mark lesson_id")

    existing = (
        db.execute(
            select(StudentMarkRecord).where(
                StudentMarkRecord.attempt_id == mark.attempt_id,
                StudentMarkRecord.slide_id == mark.slide_id,
                StudentMarkRecord.student_name == mark.student_name,
            )
        )
        .scalars()
        .first()
    )

    if existing is None:
        existing = StudentMarkRecord(
            attempt_id=mark.attempt_id,
            lesson_id=mark.lesson_id,
            slide_id=mark.slide_id,
            block_id=mark.block_id,
            student_name=mark.student_name,
            status=mark.status,
            error_tags=mark.error_tags,
            support_level=mark.support_level,
            teacher_note=mark.teacher_note,
        )
        db.add(existing)
    else:
        existing.status = mark.status
        existing.error_tags = mark.error_tags
        existing.support_level = mark.support_level
        existing.teacher_note = mark.teacher_note

    attempt = db.get(LessonAttemptRecord, mark.attempt_id)
    if attempt is not None:
        db.flush()
        _rebuild_attempt_summary(db, attempt)
        # Class review state is updated at lesson completion (complete_lesson endpoint).
        # Not updated here to avoid O(students × slides) repeated DB writes.
    db.commit()
    db.refresh(existing)
    return existing


def record_slide_mark(db: Session, mark: SlideMarkRequest) -> LessonAttemptRecord:
    attempt = db.get(LessonAttemptRecord, mark.attempt_id)
    if attempt is None:
        raise ValueError(f"Unknown attempt_id {mark.attempt_id}")

    if attempt.lesson_id != mark.lesson_id:
        raise ValueError("Attempt lesson_id does not match mark lesson_id")

    status, error_tags, korean_transfer = _merge_item_results(mark)

    existing = (
        db.execute(
            select(SlideResultRecord).where(
                SlideResultRecord.attempt_id == mark.attempt_id,
                SlideResultRecord.slide_id == mark.slide_id,
            )
        )
        .scalars()
        .first()
    )

    item_results = [item.model_dump() for item in mark.item_results]

    if existing is None:
        existing = SlideResultRecord(
            attempt_id=mark.attempt_id,
            slide_id=mark.slide_id,
            block_id=mark.block_id,
            status=status,
            error_tags=error_tags,
            korean_transfer=korean_transfer,
            teacher_note=mark.teacher_note,
            item_results=item_results,
        )
        db.add(existing)
    else:
        existing.status = status
        existing.error_tags = error_tags
        existing.korean_transfer = korean_transfer
        existing.teacher_note = mark.teacher_note
        existing.item_results = item_results

    if mark.lesson_notes:
        attempt.notes = mark.lesson_notes

    if mark.completed:
        attempt.completed = True

    db.flush()
    _rebuild_attempt_summary(db, attempt)
    update_class_pattern_review(db, attempt)
    db.commit()
    db.refresh(attempt)
    return attempt
