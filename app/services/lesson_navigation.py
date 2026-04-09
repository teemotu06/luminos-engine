import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.services.lesson_service import ordered_blocks
from app.services.lesson_service import load_lesson
from app.services.review_scheduler_service import get_class_review_recommendations, inject_dynamic_review_into_lesson

logger = logging.getLogger(__name__)


RUNTIME_INACTIVE_BLOCKS = {
    "G1-L1": {"01", "02"},
}


def build_runtime_lesson_for_attempt(
    db: Optional[Session],
    lesson_id: str,
    class_id: Optional[str] = None,
) -> tuple[Any, list[dict], Optional[dict], bool]:
    lesson = load_lesson(lesson_id)
    dynamic_review_recommendations = None
    dynamic_review_error = False
    if db is not None and class_id and lesson.lesson_id.startswith("G"):
        try:
            dynamic_review_recommendations = get_class_review_recommendations(db, class_id, lesson.lesson_id)
        except Exception:
            dynamic_review_error = True
            logger.exception(
                "Dynamic review recommendation lookup failed for lesson_id=%s class_id=%s",
                lesson.lesson_id,
                class_id,
            )
    runtime_lesson = inject_dynamic_review_into_lesson(lesson, dynamic_review_recommendations)
    ordered_slides = flatten_lesson_slides(runtime_lesson)
    return runtime_lesson, ordered_slides, dynamic_review_recommendations, dynamic_review_error

def flatten_lesson_slides(lesson: Any) -> list[dict]:
    ordered_slides = []
    slide_index = 0
    inactive_blocks = RUNTIME_INACTIVE_BLOCKS.get(str(getattr(lesson, "lesson_id", "") or ""), set())

    for block in ordered_blocks(lesson):
        if str(block.block_id) in inactive_blocks:
            continue
        block_start_index = slide_index

        for slide in block.slides:
            ordered_slides.append(
                {
                    "block": block,
                    "slide": slide,
                    "block_first_slide_index": block_start_index,
                    "slide_index": slide_index,
                }
            )
            slide_index += 1

    return ordered_slides
