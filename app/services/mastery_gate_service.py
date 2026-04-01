"""Adaptive mastery gating and re-teach recommendations.

Computes a class readiness verdict after each lesson attempt and generates
specific reteach actions for the teacher. No new database tables are needed —
this uses existing StudentMarkRecord, SlideResultRecord, and
ClassPatternReviewRecord.

Gate levels (based on per-student worst-status distribution):

  proceed  — ≥75% of marked students are secure, no repeated weakness
  caution  — ≥50% secure (or ≥75% but consecutive_weak ≥ 1)
  reteach  — ≥25% secure but under the caution threshold
  repeat   — <25% secure, or missed_rate ≥ 40%, or consecutive_weak ≥ 2
  no_data  — no student marks recorded; falls back to attempt.mastery_status

When no student marks exist the attempt-level mastery_status is used as a
fallback: secure→proceed, shaky→caution, missed→reteach.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.lesson import (
    ClassPatternReviewRecord,
    LessonAttemptRecord,
    SlideResultRecord,
    StudentMarkRecord,
)

logger = logging.getLogger(__name__)

GateLevel = Literal["proceed", "caution", "reteach", "repeat", "no_data"]

# Worst-wins ranking: higher number = worse status.
_STATUS_RANK: Dict[str, int] = {"secure": 0, "skipped": 1, "shaky": 2, "missed": 3}

GATE_LABELS: Dict[str, str] = {
    "proceed": "Ready to move on",
    "caution": "Proceed with caution",
    "reteach": "Re-teach recommended",
    "repeat": "Repeat this lesson",
    "no_data": "No class data yet",
}

GATE_DESCRIPTIONS: Dict[str, str] = {
    "proceed": (
        "Most students are secure on today's patterns. "
        "The class is ready for the next lesson."
    ),
    "caution": (
        "More than half the class is secure, but some students need "
        "targeted support before the next lesson."
    ),
    "reteach": (
        "A significant portion of the class is still shaky. "
        "Re-teach the weak blocks before introducing new content."
    ),
    "repeat": (
        "The class has not reached sufficient mastery. "
        "Consider repeating this lesson before moving forward."
    ),
    "no_data": (
        "No student marks have been recorded for this attempt. "
        "Class response marks are used as a fallback."
    ),
}


@dataclass
class ReteachAction:
    action_type: str  # repeat_lesson | reteach_blocks | small_group | monitor | escalate
    label: str
    detail: str = ""
    blocks: List[str] = field(default_factory=list)
    students: List[str] = field(default_factory=list)


@dataclass
class ClassMasteryGate:
    gate_level: GateLevel
    gate_label: str
    gate_description: str
    marked_count: int
    secure_count: int
    shaky_count: int
    missed_count: int
    secure_rate: float
    weak_rate: float
    missed_rate: float
    consecutive_weak_lessons: int
    weak_blocks: List[str]
    students_needing_support: List[Dict]
    reteach_actions: List[ReteachAction]
    pattern_key: str = ""
    lesson_id: str = ""
    attempt_id: str = ""


# ── Internal helpers ──────────────────────────────────────────────────────────

def _per_student_worst_status(marks: List[StudentMarkRecord]) -> Dict[str, str]:
    """Collapse all marks for each student to their single worst status."""
    result: Dict[str, str] = {}
    for mark in marks:
        current = result.get(mark.student_name)
        if current is None or _STATUS_RANK.get(mark.status, 0) > _STATUS_RANK.get(current, 0):
            result[mark.student_name] = mark.status
    return result


def _gate_level_from_rates(
    secure_rate: float,
    missed_rate: float,
    weak_rate: float,
    consecutive_weak_lessons: int,
    marked_count: int,
) -> GateLevel:
    if marked_count == 0:
        return "no_data"
    if consecutive_weak_lessons >= 2 or missed_rate >= 0.40 or secure_rate < 0.25:
        return "repeat"
    if secure_rate < 0.50 or weak_rate >= 0.50:
        return "reteach"
    if secure_rate < 0.75 or consecutive_weak_lessons >= 1:
        return "caution"
    return "proceed"


def _fallback_gate_from_mastery_status(mastery_status: str) -> GateLevel:
    """Used when no student marks exist."""
    return {"secure": "proceed", "shaky": "caution", "missed": "reteach"}.get(
        mastery_status, "caution"
    )


def _compute_weak_blocks(
    student_marks: List[StudentMarkRecord],
    slide_results: List[SlideResultRecord],
) -> List[str]:
    """Identify blocks where ≥40% of marks are weak (shaky or missed).

    Prefers student marks; falls back to class-level slide results.
    Blocks with fewer than 2 data points are excluded to avoid noise.
    """
    if student_marks:
        # Aggregate per-student worst status per block.
        block_student_status: Dict[str, Dict[str, str]] = defaultdict(dict)
        for mark in student_marks:
            current = block_student_status[mark.block_id].get(mark.student_name)
            if current is None or _STATUS_RANK.get(mark.status, 0) > _STATUS_RANK.get(current, 0):
                block_student_status[mark.block_id][mark.student_name] = mark.status

        weak_blocks = []
        for block_id, student_statuses in block_student_status.items():
            if len(student_statuses) < 2:
                continue
            weak_count = sum(
                1 for s in student_statuses.values() if s in {"shaky", "missed"}
            )
            if weak_count / len(student_statuses) >= 0.40:
                weak_blocks.append(block_id)
        return sorted(weak_blocks)

    # Fallback: class-level slide results.
    block_slide_statuses: Dict[str, List[str]] = defaultdict(list)
    for result in slide_results:
        if result.status in {"secure", "shaky", "missed"}:
            block_slide_statuses[result.block_id].append(result.status)

    weak_blocks = []
    for block_id, statuses in block_slide_statuses.items():
        if len(statuses) < 2:
            continue
        weak_count = sum(1 for s in statuses if s in {"shaky", "missed"})
        if weak_count / len(statuses) >= 0.40:
            weak_blocks.append(block_id)
    return sorted(weak_blocks)


def _compute_student_support_list(student_marks: List[StudentMarkRecord]) -> List[Dict]:
    """
    Flag students who need individual follow-up.

    High urgency: any slide marked "missed".
    Medium urgency: ≥50% of their marked slides are shaky or missed
                    (minimum 2 slides to flag).
    """
    marks_by_student: Dict[str, Dict[str, str]] = defaultdict(dict)
    for mark in student_marks:
        current = marks_by_student[mark.student_name].get(mark.slide_id)
        if current is None or _STATUS_RANK.get(mark.status, 0) > _STATUS_RANK.get(current, 0):
            marks_by_student[mark.student_name][mark.slide_id] = mark.status

    support_list = []
    for student_name in sorted(marks_by_student):
        slide_statuses = marks_by_student[student_name]
        total = len(slide_statuses)
        missed = sum(1 for s in slide_statuses.values() if s == "missed")
        shaky = sum(1 for s in slide_statuses.values() if s == "shaky")
        weak = missed + shaky

        if missed >= 1:
            urgency = "high"
        elif total >= 2 and weak / total >= 0.50:
            urgency = "medium"
        else:
            continue

        support_list.append(
            {
                "student_name": student_name,
                "urgency": urgency,
                "missed_count": missed,
                "shaky_count": shaky,
                "total_slides": total,
            }
        )

    # Sort: high urgency first, then by missed count desc, then shaky desc.
    return sorted(
        support_list,
        key=lambda x: (0 if x["urgency"] == "high" else 1, -x["missed_count"], -x["shaky_count"]),
    )


def _build_reteach_actions(
    gate_level: GateLevel,
    weak_blocks: List[str],
    students_needing_support: List[Dict],
    consecutive_weak_lessons: int,
) -> List[ReteachAction]:
    actions: List[ReteachAction] = []

    if gate_level == "proceed":
        return actions

    if gate_level == "repeat":
        actions.append(
            ReteachAction(
                action_type="repeat_lesson",
                label="Repeat this lesson",
                detail=(
                    "The class has not reached sufficient mastery. "
                    "Run the full lesson again before introducing new content."
                ),
            )
        )

    if weak_blocks:
        block_labels = [f"Block {b}" for b in weak_blocks]
        blocks_str = ", ".join(block_labels)
        if gate_level in ("reteach", "repeat"):
            actions.append(
                ReteachAction(
                    action_type="reteach_blocks",
                    label=f"Re-teach {blocks_str}",
                    detail=(
                        "These blocks had the highest rate of weak marks. "
                        "Focus your reteach here before moving forward."
                    ),
                    blocks=weak_blocks,
                )
            )
        else:  # caution
            actions.append(
                ReteachAction(
                    action_type="review_blocks",
                    label=f"Warm-up review of {blocks_str} at the start of the next lesson",
                    detail=(
                        "A short revisit of these blocks as a warm-up "
                        "will help consolidate before the new lesson content."
                    ),
                    blocks=weak_blocks,
                )
            )

    high_urgency = [s for s in students_needing_support if s["urgency"] == "high"]
    medium_urgency = [s for s in students_needing_support if s["urgency"] == "medium"]

    if high_urgency:
        n = len(high_urgency)
        actions.append(
            ReteachAction(
                action_type="small_group",
                label=f"Small-group follow-up for {n} student{'s' if n != 1 else ''}",
                detail=(
                    "These students missed at least one slide. "
                    "A short small-group session before the next class lesson is recommended."
                ),
                students=[s["student_name"] for s in high_urgency],
            )
        )

    if medium_urgency:
        n = len(medium_urgency)
        actions.append(
            ReteachAction(
                action_type="monitor",
                label=f"Monitor {n} student{'s' if n != 1 else ''} closely",
                detail=(
                    "These students were shaky on more than half of their marked slides. "
                    "Watch for continued difficulty in the next lesson."
                ),
                students=[s["student_name"] for s in medium_urgency],
            )
        )

    if consecutive_weak_lessons >= 2:
        actions.append(
            ReteachAction(
                action_type="escalate",
                label=f"Pattern weak across {consecutive_weak_lessons} consecutive lessons",
                detail=(
                    "This pattern has not consolidated across multiple sessions. "
                    "Consider a targeted reteach sequence or a KI intervention lesson "
                    "before continuing with new material."
                ),
            )
        )

    return actions


# ── Public API ────────────────────────────────────────────────────────────────

def compute_class_mastery_gate(
    db: Session,
    class_id: str,
    lesson_id: str,
    attempt_id: Optional[str] = None,
) -> ClassMasteryGate:
    """Compute the full mastery gate for a specific attempt (review page).

    If attempt_id is given, that exact attempt is used.
    Otherwise the most recent completed attempt for class + lesson is used.
    """
    if attempt_id:
        attempt = db.get(LessonAttemptRecord, attempt_id)
        if attempt is None or attempt.lesson_id != lesson_id:
            attempt = None
    else:
        attempt = (
            db.execute(
                select(LessonAttemptRecord)
                .where(
                    LessonAttemptRecord.class_id == class_id,
                    LessonAttemptRecord.lesson_id == lesson_id,
                )
                .order_by(LessonAttemptRecord.attempt_date.desc())
            )
            .scalars()
            .first()
        )

    if attempt is None:
        return ClassMasteryGate(
            gate_level="no_data",
            gate_label=GATE_LABELS["no_data"],
            gate_description=GATE_DESCRIPTIONS["no_data"],
            marked_count=0,
            secure_count=0,
            shaky_count=0,
            missed_count=0,
            secure_rate=0.0,
            weak_rate=0.0,
            missed_rate=0.0,
            consecutive_weak_lessons=0,
            weak_blocks=[],
            students_needing_support=[],
            reteach_actions=[],
            lesson_id=lesson_id,
        )

    student_marks = (
        db.execute(
            select(StudentMarkRecord).where(
                StudentMarkRecord.attempt_id == attempt.attempt_id
            )
        )
        .scalars()
        .all()
    )

    slide_results = (
        db.execute(
            select(SlideResultRecord).where(
                SlideResultRecord.attempt_id == attempt.attempt_id
            )
        )
        .scalars()
        .all()
    )

    # Class pattern record provides consecutive_weak_lessons.
    pattern_rec = (
        db.execute(
            select(ClassPatternReviewRecord).where(
                ClassPatternReviewRecord.class_id == class_id,
                ClassPatternReviewRecord.source_lesson_id == lesson_id,
            )
        )
        .scalars()
        .first()
    )
    consecutive_weak = pattern_rec.consecutive_weak_lessons if pattern_rec else 0
    pattern_key = pattern_rec.pattern_key if pattern_rec else ""

    # Compute per-student worst status.
    student_statuses = _per_student_worst_status(student_marks)
    marked_count = len(student_statuses)
    secure_count = sum(1 for s in student_statuses.values() if s == "secure")
    shaky_count = sum(1 for s in student_statuses.values() if s == "shaky")
    missed_count = sum(1 for s in student_statuses.values() if s == "missed")

    if marked_count == 0:
        gate_level = _fallback_gate_from_mastery_status(attempt.mastery_status)
        secure_rate = weak_rate = missed_rate = 0.0
    else:
        secure_rate = secure_count / marked_count
        weak_rate = (shaky_count + missed_count) / marked_count
        missed_rate = missed_count / marked_count
        gate_level = _gate_level_from_rates(
            secure_rate=secure_rate,
            missed_rate=missed_rate,
            weak_rate=weak_rate,
            consecutive_weak_lessons=consecutive_weak,
            marked_count=marked_count,
        )

    weak_blocks = _compute_weak_blocks(student_marks, slide_results)
    students_needing_support = _compute_student_support_list(student_marks)
    reteach_actions = _build_reteach_actions(
        gate_level=gate_level,
        weak_blocks=weak_blocks,
        students_needing_support=students_needing_support,
        consecutive_weak_lessons=consecutive_weak,
    )

    return ClassMasteryGate(
        gate_level=gate_level,
        gate_label=GATE_LABELS[gate_level],
        gate_description=GATE_DESCRIPTIONS[gate_level],
        marked_count=marked_count,
        secure_count=secure_count,
        shaky_count=shaky_count,
        missed_count=missed_count,
        secure_rate=round(secure_rate, 3),
        weak_rate=round(weak_rate, 3),
        missed_rate=round(missed_rate, 3),
        consecutive_weak_lessons=consecutive_weak,
        weak_blocks=weak_blocks,
        students_needing_support=students_needing_support,
        reteach_actions=reteach_actions,
        pattern_key=pattern_key,
        lesson_id=lesson_id,
        attempt_id=str(attempt.attempt_id),
    )


def get_class_lesson_gate_summaries(db: Session, class_id: str) -> Dict[str, dict]:
    """Return compact gate summaries for all lessons that have any attempt for this class.

    Used by the lesson library API endpoint. Returns a dict of
    lesson_id → {gate_level, gate_label, secure_count, weak_count, marked_count}.

    All completed attempts are batched into two queries to avoid N+1.
    """
    attempts = (
        db.execute(
            select(LessonAttemptRecord)
            .where(LessonAttemptRecord.class_id == class_id)
            .order_by(LessonAttemptRecord.attempt_date.desc())
        )
        .scalars()
        .all()
    )
    if not attempts:
        return {}

    # Keep only the most recent attempt per lesson.
    latest_by_lesson: Dict[str, LessonAttemptRecord] = {}
    for attempt in attempts:
        if attempt.lesson_id not in latest_by_lesson:
            latest_by_lesson[attempt.lesson_id] = attempt

    attempt_ids = [str(a.attempt_id) for a in latest_by_lesson.values()]

    # Batch-fetch all student marks for those attempts.
    all_marks = (
        db.execute(
            select(StudentMarkRecord).where(
                StudentMarkRecord.attempt_id.in_(attempt_ids)
            )
        )
        .scalars()
        .all()
    )
    marks_by_attempt: Dict[str, List[StudentMarkRecord]] = defaultdict(list)
    for mark in all_marks:
        marks_by_attempt[str(mark.attempt_id)].append(mark)

    # Batch-fetch ClassPatternReviewRecord for consecutive_weak_lessons.
    pattern_records = (
        db.execute(
            select(ClassPatternReviewRecord).where(
                ClassPatternReviewRecord.class_id == class_id
            )
        )
        .scalars()
        .all()
    )
    pattern_by_source: Dict[str, ClassPatternReviewRecord] = {
        r.source_lesson_id: r for r in pattern_records
    }

    summaries: Dict[str, dict] = {}
    for lesson_id, attempt in latest_by_lesson.items():
        marks = marks_by_attempt.get(str(attempt.attempt_id), [])
        pattern_rec = pattern_by_source.get(lesson_id)
        consecutive_weak = pattern_rec.consecutive_weak_lessons if pattern_rec else 0

        student_statuses = _per_student_worst_status(marks)
        marked_count = len(student_statuses)
        secure_count = sum(1 for s in student_statuses.values() if s == "secure")
        shaky_count = sum(1 for s in student_statuses.values() if s == "shaky")
        missed_count = sum(1 for s in student_statuses.values() if s == "missed")
        weak_count = shaky_count + missed_count

        if marked_count == 0:
            gate_level = _fallback_gate_from_mastery_status(attempt.mastery_status)
        else:
            secure_rate = secure_count / marked_count
            weak_rate = weak_count / marked_count
            missed_rate = missed_count / marked_count
            gate_level = _gate_level_from_rates(
                secure_rate=secure_rate,
                missed_rate=missed_rate,
                weak_rate=weak_rate,
                consecutive_weak_lessons=consecutive_weak,
                marked_count=marked_count,
            )

        summaries[lesson_id] = {
            "gate_level": gate_level,
            "gate_label": GATE_LABELS[gate_level],
            "secure_count": secure_count,
            "weak_count": weak_count,
            "marked_count": marked_count,
        }

    return summaries
