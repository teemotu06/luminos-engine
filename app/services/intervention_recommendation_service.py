from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Union

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.lesson import LessonAttemptRecord, SlideResultRecord, StudentMarkRecord
from app.services.lesson_service import KI_INSERTION_MAP, load_lesson


@dataclass(frozen=True)
class InterventionSignal:
    lesson_id: str
    reason: str
    count: int


def _lesson_title(lesson_id: str) -> str:
    try:
        return load_lesson(lesson_id).title
    except FileNotFoundError:
        return lesson_id


def _build_recommendation(lesson_id: str, reason: str, count: int, class_id: str = "") -> Dict[str, Union[str, int]]:
    href = f"/lesson/{lesson_id}"
    if class_id:
        href = f"{href}?class_id={class_id}"
    anchor = KI_INSERTION_MAP.get(lesson_id, {})
    return {
        "lesson_id": lesson_id,
        "title": _lesson_title(lesson_id),
        "reason": reason,
        "count": count,
        "href": href,
        "after": anchor.get("after", ""),
    }


def _signal_from_counters(
    *,
    tag_counts: Counter[str],
    korean_transfer_count: int,
    lesson_id: str,
    target_pattern: str,
    interference_flags: Iterable[str],
) -> list[InterventionSignal]:
    lesson_number = _lesson_number(lesson_id)
    target_lower = (target_pattern or "").lower()
    flags = set(interference_flags or [])
    signals: list[InterventionSignal] = []

    if tag_counts["sound_substitution"] and ("r_l" in flags or "r" in target_lower or "l" in target_lower):
        ki_lesson = "KI-L2" if lesson_number is not None and lesson_number >= 15 else "KI-L1"
        reason = "repeated liquid confusion in print or oral response"
        signals.append(InterventionSignal(ki_lesson, reason, tag_counts["sound_substitution"]))

    if tag_counts["omission"] and (korean_transfer_count or lesson_number is not None and lesson_number <= 15):
        signals.append(
            InterventionSignal(
                "KI-L4",
                "final consonants are being dropped or weakened",
                tag_counts["omission"] + korean_transfer_count,
            )
        )

    if tag_counts["insertion"] and ("cluster" in flags or korean_transfer_count):
        signals.append(
            InterventionSignal(
                "KI-L3",
                "clusters are being broken apart with an inserted vowel",
                tag_counts["insertion"] + korean_transfer_count,
            )
        )

    if tag_counts["vowel_confusion"]:
        signals.append(
            InterventionSignal(
                "KI-L5",
                "high-risk vowel contrasts are collapsing in reading or dictation",
                tag_counts["vowel_confusion"],
            )
        )

    unique_signals: dict[str, InterventionSignal] = {}
    for signal in signals:
        existing = unique_signals.get(signal.lesson_id)
        if existing is None or signal.count > existing.count:
            unique_signals[signal.lesson_id] = signal
    return sorted(unique_signals.values(), key=lambda item: (-item.count, item.lesson_id))


def _lesson_number(lesson_id: str) -> Optional[int]:
    try:
        return int(lesson_id.split("-L", 1)[1])
    except (IndexError, ValueError):
        return None


def recommend_interventions_for_attempt(db: Session, attempt: LessonAttemptRecord, lesson) -> dict:
    slide_results = (
        db.execute(
            select(SlideResultRecord).where(SlideResultRecord.attempt_id == attempt.attempt_id)
        )
        .scalars()
        .all()
    )
    student_marks = (
        db.execute(
            select(StudentMarkRecord).where(StudentMarkRecord.attempt_id == attempt.attempt_id)
        )
        .scalars()
        .all()
    )

    session_tags = Counter()
    session_korean_transfer = 0
    for result in slide_results:
        session_tags.update(result.error_tags or [])
        if result.korean_transfer:
            session_korean_transfer += 1
        for item in result.item_results or []:
            session_tags.update(item.get("error_tags", []))
            if item.get("korean_transfer"):
                session_korean_transfer += 1

    session_signals = _signal_from_counters(
        tag_counts=session_tags,
        korean_transfer_count=session_korean_transfer,
        lesson_id=attempt.lesson_id,
        target_pattern=lesson.target_pattern,
        interference_flags=lesson.korean_interference_active,
    )

    session_recommendations = [
        _build_recommendation(signal.lesson_id, signal.reason, signal.count, attempt.class_id or "")
        for signal in session_signals
    ]

    student_recommendations: Dict[str, List[Dict[str, Union[str, int]]]] = {}
    marks_by_student: Dict[str, List[StudentMarkRecord]] = defaultdict(list)
    for mark in student_marks:
        marks_by_student[mark.student_name].append(mark)

    for student_name, marks in sorted(marks_by_student.items()):
        tag_counts = Counter()
        korean_transfer_count = 0
        for mark in marks:
            tag_counts.update(mark.error_tags or [])
            if "korean_transfer" in (mark.error_tags or []):
                korean_transfer_count += 1
            if (mark.support_level or "") in {"prompted", "modeled"}:
                tag_counts["sound_substitution"] += 1

        signals = _signal_from_counters(
            tag_counts=tag_counts,
            korean_transfer_count=korean_transfer_count,
            lesson_id=attempt.lesson_id,
            target_pattern=lesson.target_pattern,
            interference_flags=lesson.korean_interference_active,
        )
        if signals:
            student_recommendations[student_name] = [
                _build_recommendation(signal.lesson_id, signal.reason, signal.count, attempt.class_id or "")
                for signal in signals
            ]

    return {
        "session_recommendations": session_recommendations,
        "student_recommendations": student_recommendations,
    }
