import logging
from collections import Counter, defaultdict
from functools import lru_cache
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.models.lesson import ClassPatternReviewRecord, LessonAttemptRecord, StudentMarkRecord
from app.schemas.lesson import Lesson
from app.schemas.slide import Slide
from app.schemas.slide_payloads import VIEW_PAYLOAD_MAP
from app.services.lesson_service import list_lesson_ids, load_lesson


WEAK_STATUSES = {"shaky", "missed"}


def lesson_number(lesson_id: str) -> Optional[int]:
    try:
        return int(lesson_id.split("-L", 1)[1])
    except (IndexError, ValueError):
        return None


@lru_cache(maxsize=256)
def pattern_key_for_lesson(lesson_id: str) -> Optional[str]:
    try:
        lesson = load_lesson(lesson_id)
    except FileNotFoundError:
        return None
    return (lesson.target_pattern or "").strip() or None


def _schedule_gap(mastery_state: str, korean_transfer_count: int) -> int:
    if mastery_state == "missed":
        return 1
    if mastery_state == "shaky":
        return 2
    gap = 5
    if korean_transfer_count > 0:
        gap = 4
    return gap


def _class_review_priority(
    mastery_state: str,
    weak_learner_count: int,
    marked_learner_count: int,
    consecutive_weak_lessons: int,
    korean_transfer_count: int,
    next_due_lesson_number: int,
    current_lesson_number: int,
) -> int:
    ratio_points = 0
    if marked_learner_count > 0:
        weak_ratio = weak_learner_count / marked_learner_count
        if weak_ratio >= 0.5:
            ratio_points = 3
        elif weak_ratio >= 0.3:
            ratio_points = 2
        elif weak_ratio > 0:
            ratio_points = 1

    status_points = {"secure": 0, "shaky": 2, "missed": 4}.get(mastery_state, 0)
    overdue_points = max(0, current_lesson_number - next_due_lesson_number)
    return (
        status_points
        + ratio_points
        + consecutive_weak_lessons
        + korean_transfer_count
        + overdue_points
    )


def update_class_pattern_review(db: Session, attempt: LessonAttemptRecord) -> None:
    if not attempt.class_id:
        return

    pattern_key = pattern_key_for_lesson(attempt.lesson_id)
    current_lesson_number = lesson_number(attempt.lesson_id)
    if not pattern_key or current_lesson_number is None:
        return

    student_marks = (
        db.execute(
            select(StudentMarkRecord).where(StudentMarkRecord.attempt_id == attempt.attempt_id)
        )
        .scalars()
        .all()
    )

    student_statuses: Dict[str, str] = {}
    for mark in student_marks:
        prior = student_statuses.get(mark.student_name)
        if prior == "missed":
            continue
        if prior == "shaky" and mark.status == "secure":
            continue
        student_statuses[mark.student_name] = mark.status

    marked_learner_count = len(student_statuses)
    weak_learner_count = sum(1 for status in student_statuses.values() if status in WEAK_STATUSES)
    korean_transfer_count = sum(
        1 for mark in student_marks if "korean_transfer" in (mark.error_tags or [])
    )

    existing = (
        db.execute(
            select(ClassPatternReviewRecord).where(
                ClassPatternReviewRecord.class_id == attempt.class_id,
                ClassPatternReviewRecord.pattern_key == pattern_key,
            )
        )
        .scalars()
        .first()
    )

    if existing is None:
        existing = ClassPatternReviewRecord(
            class_id=attempt.class_id,
            pattern_key=pattern_key,
            source_lesson_id=attempt.lesson_id,
            first_taught_lesson_id=attempt.lesson_id,
            last_seen_lesson_id=attempt.lesson_id,
            last_reviewed_lesson_id=attempt.lesson_id,
            mastery_state=attempt.mastery_status,
            times_secure=0,
            times_shaky=0,
            times_missed=0,
            consecutive_weak_lessons=0,
            korean_transfer_count=0,
            weak_learner_count=0,
            marked_learner_count=0,
            next_due_lesson_number=current_lesson_number,
            priority_score=0,
        )
        db.add(existing)

    existing.times_secure = existing.times_secure or 0
    existing.times_shaky = existing.times_shaky or 0
    existing.times_missed = existing.times_missed or 0
    existing.consecutive_weak_lessons = existing.consecutive_weak_lessons or 0
    existing.korean_transfer_count = existing.korean_transfer_count or 0
    existing.weak_learner_count = existing.weak_learner_count or 0
    existing.marked_learner_count = existing.marked_learner_count or 0
    existing.next_due_lesson_number = existing.next_due_lesson_number or current_lesson_number
    existing.priority_score = existing.priority_score or 0

    if attempt.mastery_status == "secure":
        existing.times_secure += 1
        existing.consecutive_weak_lessons = 0
    elif attempt.mastery_status == "shaky":
        existing.times_shaky += 1
        existing.consecutive_weak_lessons += 1
    else:
        existing.times_missed += 1
        existing.consecutive_weak_lessons += 1

    existing.source_lesson_id = attempt.lesson_id
    existing.last_seen_lesson_id = attempt.lesson_id
    existing.last_reviewed_lesson_id = attempt.lesson_id
    existing.mastery_state = attempt.mastery_status
    # weak_learner_count / marked_learner_count / korean_transfer_count reflect the
    # most recent session (intentional — priority scoring uses current-session data).
    existing.korean_transfer_count = korean_transfer_count
    existing.weak_learner_count = weak_learner_count
    existing.marked_learner_count = marked_learner_count

    gap = _schedule_gap(attempt.mastery_status, korean_transfer_count)
    existing.next_due_lesson_number = current_lesson_number + gap

    # Compute priority AFTER next_due is updated; overdue_points will be 0 for the
    # current lesson and only accumulate from the next lesson onward (by design).
    existing.priority_score = _class_review_priority(
        mastery_state=attempt.mastery_status,
        weak_learner_count=weak_learner_count,
        marked_learner_count=marked_learner_count,
        consecutive_weak_lessons=existing.consecutive_weak_lessons,
        korean_transfer_count=korean_transfer_count,
        next_due_lesson_number=existing.next_due_lesson_number,
        current_lesson_number=current_lesson_number,
    )

    db.flush()


def rebuild_class_review_records(db: Session) -> None:
    """Seed class_pattern_review from existing attempts.

    Only runs when the table is empty (i.e. first boot or after a manual reset).
    Incremental updates via update_class_pattern_review handle all subsequent changes.
    To force a full rebuild use the admin endpoint POST /admin/rebuild-review-records.
    """
    count = db.query(ClassPatternReviewRecord).count()
    if count > 0:
        return

    attempts = (
        db.execute(
            select(LessonAttemptRecord)
            .where(LessonAttemptRecord.class_id.is_not(None))
            .order_by(LessonAttemptRecord.attempt_date.asc())
        )
        .scalars()
        .all()
    )

    for attempt in attempts:
        update_class_pattern_review(db, attempt)

    db.commit()


def force_rebuild_class_review_records(db: Session) -> int:
    """Full wipe-and-replay. Only called from the admin endpoint."""
    db.query(ClassPatternReviewRecord).delete()
    attempts = (
        db.execute(
            select(LessonAttemptRecord)
            .where(LessonAttemptRecord.class_id.is_not(None))
            .order_by(LessonAttemptRecord.attempt_date.asc())
        )
        .scalars()
        .all()
    )
    for attempt in attempts:
        update_class_pattern_review(db, attempt)
    db.commit()
    return len(attempts)


def previous_lesson_id(upcoming_lesson_id: str) -> Optional[str]:
    lesson_ids = [lid for lid in list_lesson_ids() if lid.startswith("G")]
    if upcoming_lesson_id not in lesson_ids:
        return None
    index = lesson_ids.index(upcoming_lesson_id)
    if index == 0:
        return None
    return lesson_ids[index - 1]


def next_lesson_id(current_lesson_id: str) -> Optional[str]:
    lesson_ids = [lid for lid in list_lesson_ids() if lid.startswith("G")]
    if current_lesson_id not in lesson_ids:
        return None
    index = lesson_ids.index(current_lesson_id)
    if index >= len(lesson_ids) - 1:
        return None
    return lesson_ids[index + 1]


def _recommendations_from_records(
    records: List[ClassPatternReviewRecord],
    upcoming_lesson_id: str,
    *,
    previous_id: Optional[str],
    previous_pattern: Optional[str],
) -> dict:
    current_lesson_number = lesson_number(upcoming_lesson_id)

    recent_target = None
    if previous_id and previous_pattern:
        recent_target = {
            "pattern_key": previous_pattern,
            "source_lesson_id": previous_id,
            "reason": "Recent review",
            "recommended_touch_count": 2,
        }

    due_targets = []
    class_risk_targets = []
    seen_patterns = set()

    for record in records:
        if record.pattern_key in seen_patterns:
            continue

        if current_lesson_number is not None and record.next_due_lesson_number <= current_lesson_number:
            due_targets.append(
                {
                    "pattern_key": record.pattern_key,
                    "source_lesson_id": record.source_lesson_id,
                    "reason": "Due review",
                    "recommended_touch_count": 2 if record.mastery_state == "secure" else 3,
                    "priority_score": record.priority_score,
                }
            )
            seen_patterns.add(record.pattern_key)
            continue

        marked = record.marked_learner_count
        weak = record.weak_learner_count
        class_risk = weak >= 3 or (marked > 0 and (weak / marked) >= 0.3)

        if class_risk:
            class_risk_targets.append(
                {
                    "pattern_key": record.pattern_key,
                    "source_lesson_id": record.source_lesson_id,
                    "reason": "Class-risk review",
                    "recommended_touch_count": 3 if record.mastery_state in WEAK_STATUSES else 2,
                    "weak_learner_count": weak,
                    "marked_learner_count": marked,
                    "priority_score": record.priority_score,
                }
            )
            seen_patterns.add(record.pattern_key)

    return {
        "upcoming_lesson_id": upcoming_lesson_id,
        "recent_review_target": recent_target,
        "due_review_targets": due_targets[:2],
        "class_risk_targets": class_risk_targets[:1],
        "individual_follow_up_flags": [],
    }


def build_lesson_index_review_map(db: Session, class_ids: List[str], lesson_ids: List[str]) -> dict:
    """Build the full lesson-library review map from one bulk review-record query."""
    if not class_ids or not lesson_ids:
        return {}

    records = (
        db.execute(
            select(ClassPatternReviewRecord)
            .where(ClassPatternReviewRecord.class_id.in_(class_ids))
            .order_by(
                ClassPatternReviewRecord.class_id,
                ClassPatternReviewRecord.priority_score.desc(),
                ClassPatternReviewRecord.updated_at.desc(),
            )
        )
        .scalars()
        .all()
    )

    records_by_class: dict[str, List[ClassPatternReviewRecord]] = defaultdict(list)
    for record in records:
        records_by_class[str(record.class_id)].append(record)

    previous_ids = {lesson_id: previous_lesson_id(lesson_id) for lesson_id in lesson_ids}
    previous_patterns = {
        lesson_id: pattern_key_for_lesson(previous_id) if previous_id else None
        for lesson_id, previous_id in previous_ids.items()
    }
    review_map = {
        class_id: {
            lesson_id: _recommendations_from_records(
                records_by_class.get(class_id, []),
                lesson_id,
                previous_id=previous_ids[lesson_id],
                previous_pattern=previous_patterns[lesson_id],
            )
            for lesson_id in lesson_ids
        }
        for class_id in class_ids
    }
    logger.info(
        "review_scheduler.lesson_index_map classes=%s lessons=%s records=%s",
        len(class_ids),
        len(lesson_ids),
        len(records),
    )
    return review_map


def get_class_review_recommendations(
    db: Session,
    class_id: str,
    upcoming_lesson_id: str,
    *,
    preloaded_records: Optional[List[ClassPatternReviewRecord]] = None,
    skip_individual_flags: bool = False,
) -> dict:
    """Compute review recommendations for a class before an upcoming lesson.

    Pass preloaded_records to avoid a per-call DB query (used by lesson_index
    which pre-fetches all records for a class in one query).
    Pass skip_individual_flags=True when individual student flags are not needed
    (e.g. the lesson library card view).
    """
    previous_id = previous_lesson_id(upcoming_lesson_id)

    if preloaded_records is not None:
        records = preloaded_records
    else:
        records = (
            db.execute(
                select(ClassPatternReviewRecord)
                .where(ClassPatternReviewRecord.class_id == class_id)
                .order_by(ClassPatternReviewRecord.priority_score.desc(), ClassPatternReviewRecord.updated_at.desc())
            )
            .scalars()
            .all()
        )

    recommendations = _recommendations_from_records(
        records,
        upcoming_lesson_id,
        previous_id=previous_id,
        previous_pattern=pattern_key_for_lesson(previous_id) if previous_id else None,
    )

    individual_follow_up_flags: List[dict] = []

    if not skip_individual_flags and previous_id:
        attempts = (
            db.execute(
                select(LessonAttemptRecord)
                .where(
                    LessonAttemptRecord.class_id == class_id,
                    LessonAttemptRecord.lesson_id == previous_id,
                )
                .order_by(LessonAttemptRecord.attempt_date.desc())
            )
            .scalars()
            .all()
        )

        if attempts:
            latest_attempt = attempts[0]
            marks = (
                db.execute(
                    select(StudentMarkRecord).where(StudentMarkRecord.attempt_id == latest_attempt.attempt_id)
                )
                .scalars()
                .all()
            )
            by_student = Counter()
            for mark in marks:
                if mark.status in WEAK_STATUSES:
                    by_student[mark.student_name] += 1
            for student_name, weak_count in by_student.most_common():
                if weak_count >= 2:
                    individual_follow_up_flags.append(
                        {
                            "student_name": student_name,
                            "reason": "Repeated weak marks in the most recent class lesson",
                            "weak_mark_count": weak_count,
                        }
                    )

    recommendations["individual_follow_up_flags"] = individual_follow_up_flags[:5]
    return recommendations


def build_dynamic_review_slides(review_recommendations: Optional[dict]) -> List[dict]:
    if not review_recommendations:
        return []

    targets: List[dict] = []
    if review_recommendations.get("recent_review_target"):
        targets.append(review_recommendations["recent_review_target"])
    targets.extend(review_recommendations.get("due_review_targets", []))
    targets.extend(review_recommendations.get("class_risk_targets", []))

    seen = set()
    slides: List[dict] = []
    flash_index = 1
    write_index = 1

    for target in targets:
        pattern_key = target.get("pattern_key")
        if not pattern_key or pattern_key in seen:
            continue
        seen.add(pattern_key)

        slides.append(
            {
                "block_id": "01",
                "slide_id": f"dyn-01-{flash_index:02d}",
                "slide_title": f"Smart Review: {pattern_key}",
                "view_type": "flashcard",
                "content_payload": {
                    "front_text": pattern_key,
                    "back_text": target.get("reason", "Review"),
                },
                "teacher_cue": f"Quick oral review for {pattern_key}. This is included because it is {target.get('reason', 'in review').lower()}.",
                "expected_response": f"Students recall and say the pattern {pattern_key} accurately.",
                "correction_move": "Model the pattern briefly, then have the class repeat and connect it to a known word.",
                "observation_note": "Use this as a fast warm-up, not a full reteach.",
                "korean_interference_flag": None,
                "markable": False,
                "marking_options": [],
                "next_action": "manual_next",
            }
        )
        slides.append(
            {
                "block_id": "02",
                "slide_id": f"dyn-02-{write_index:02d}",
                "slide_title": f"Smart Write Review: {pattern_key}",
                "view_type": "writing_encoding",
                "content_payload": {
                    "prompt_text": f"Quick write review for {pattern_key}.",
                    "dictated_text": pattern_key,
                    "expected_answer": pattern_key,
                },
                "teacher_cue": f"Have students write or encode {pattern_key} as a quick review application.",
                "expected_response": f"Students encode {pattern_key} accurately.",
                "correction_move": "Model the pattern and have students check each part while reading it back.",
                "observation_note": "This is a generated review item and should be adjusted by the teacher if needed.",
                "korean_interference_flag": None,
                "markable": False,
                "marking_options": [],
                "next_action": "manual_next",
            }
        )
        flash_index += 1
        write_index += 1

    return slides


def inject_dynamic_review_into_lesson(
    lesson: Lesson,
    review_recommendations: Optional[dict],
) -> Lesson:
    dynamic_slide_dicts = build_dynamic_review_slides(review_recommendations)
    if not dynamic_slide_dicts:
        return lesson

    runtime_lesson = lesson.model_copy(deep=True)
    grouped_slides: Dict[str, List[Slide]] = {"01": [], "02": []}

    for slide_data in dynamic_slide_dicts:
        payload_cls = VIEW_PAYLOAD_MAP.get(slide_data["view_type"])
        if payload_cls is None:
            logger.warning(
                "inject_dynamic_review: unknown view_type %r for slide %r — skipping. "
                "Check VIEW_PAYLOAD_MAP for missing entries.",
                slide_data.get("view_type"),
                slide_data.get("slide_id"),
            )
            continue
        slide_payload = payload_cls(**slide_data["content_payload"])
        slide = Slide(
            slide_id=slide_data["slide_id"],
            block_id=slide_data["block_id"],
            slide_title=slide_data["slide_title"],
            view_type=slide_data["view_type"],
            content_payload=slide_payload,
            teacher_cue=slide_data["teacher_cue"],
            expected_response=slide_data["expected_response"],
            correction_move=slide_data["correction_move"],
            observation_note=slide_data["observation_note"],
            korean_interference_flag=slide_data["korean_interference_flag"],
            markable=slide_data["markable"],
            marking_options=slide_data["marking_options"],
            next_action=slide_data["next_action"],
        )
        grouped_slides[slide.block_id].append(slide)

    for block_id, slides in grouped_slides.items():
        if not slides:
            continue
        block = runtime_lesson.blocks.get(block_id)
        if block is None:
            logger.warning(
                "inject_dynamic_review: lesson %r has no block %r — skipping injection of %d slide(s). "
                "Dynamic review slides are only injected into blocks 01 and 02.",
                runtime_lesson.lesson_id,
                block_id,
                len(slides),
            )
            continue
        block.slides = slides + block.slides

    return runtime_lesson
