from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.lesson import (
    ClassRecord,
    LessonAttemptRecord,
    OralCheckAssignmentRecord,
    OralCheckSessionRecord,
    StudentMarkRecord,
)
from app.services.class_service import get_students_for_class
from app.services.intervention_recommendation_service import recommend_interventions_for_attempt
from app.services.lesson_service import load_lesson
from app.services.mastery_gate_service import compute_class_mastery_gate
from app.services.review_scheduler_service import get_class_review_recommendations, next_lesson_id


def get_review_data(db: Session, lesson_id: str, attempt_id: str) -> dict:
    attempt = db.get(LessonAttemptRecord, attempt_id)
    if attempt is None or attempt.lesson_id != lesson_id:
        return None

    try:
        lesson = load_lesson(lesson_id)
    except FileNotFoundError:
        return None

    slide_title_map = {
        slide.slide_id: slide.slide_title
        for block in lesson.blocks.values()
        for slide in block.slides
    }

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

    oral_sessions = (
        db.execute(
            select(OralCheckSessionRecord)
            .where(OralCheckSessionRecord.attempt_id == attempt_id)
            .order_by(OralCheckSessionRecord.slide_id)
        )
        .scalars()
        .all()
    )

    oral_check_reviews = []
    for session in oral_sessions:
        assignments = (
            db.execute(
                select(OralCheckAssignmentRecord)
                .where(OralCheckAssignmentRecord.session_id == session.id)
                .order_by(OralCheckAssignmentRecord.queue_order)
            )
            .scalars()
            .all()
        )
        counts = {"secure": 0, "shaky": 0, "missed": 0, "deferred": 0, "absent": 0}
        student_rows = []
        seen_students = set()
        for assignment in assignments:
            if assignment.resolved_in_block and assignment.status in counts:
                counts[assignment.status] += 1
            if assignment.student_name in seen_students:
                continue
            seen_students.add(assignment.student_name)
            student_assignments = [item for item in assignments if item.student_name == assignment.student_name]
            final_assignment = next((item for item in reversed(student_assignments) if item.resolved_in_block), student_assignments[-1])
            student_rows.append(
                {
                    "student_name": assignment.student_name,
                    "status": final_assignment.status,
                    "performance_type": final_assignment.performance_type,
                    "attempt_count": len(student_assignments),
                    "teacher_note": final_assignment.teacher_note or "",
                    "override_reason": final_assignment.override_reason or "",
                    "had_reteach": any(item.requires_reteach for item in student_assignments),
                }
            )

        oral_check_reviews.append(
            {
                "slide_id": session.slide_id,
                "slide_title": slide_title_map.get(session.slide_id, session.slide_id),
                "block_id": session.block_id,
                "participation_mode": session.participation_mode,
                "audit_selection_strategy": session.audit_selection_strategy,
                "text_length_mode": session.text_length_mode,
                "session_status": session.session_status,
                "roster_size": session.roster_size,
                "required_student_count": session.required_student_count,
                "resolved_student_count": session.resolved_student_count,
                "unresolved_student_count": session.unresolved_student_count,
                "counts": counts,
                "students": student_rows,
            }
        )

    class_mastery_gate = (
        compute_class_mastery_gate(db, attempt.class_id, lesson_id, attempt_id=attempt_id)
        if attempt.class_id
        else None
    )

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
        "oral_check_reviews": oral_check_reviews,
        "intervention_recommendations": recommend_interventions_for_attempt(db, attempt, lesson),
        "class_review_recommendations": (
            get_class_review_recommendations(db, attempt.class_id, next_lesson_id(lesson_id))
            if attempt.class_id and next_lesson_id(lesson_id)
            else None
        ),
        "class_mastery_gate": class_mastery_gate,
    }
