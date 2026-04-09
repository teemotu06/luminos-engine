from app.schemas.lesson import Lesson
from app.slide_types import registry
from app.services.block_registry import BLOCK_REGISTRY


ALTERNATE_BLOCK_LABELS = {
    ("KI", "09"): {"Production Practice"},
}


def validate_lesson_blocks(lesson: Lesson) -> None:
    if not lesson.blocks:
        return

    expected_ids = [block.block_id for block in BLOCK_REGISTRY]
    actual_ids = list(lesson.blocks.keys())

    if actual_ids != expected_ids:
        raise ValueError(
            f"Invalid block order. Expected {expected_ids}, got {actual_ids}."
        )

    registry_by_id = {block.block_id: block for block in BLOCK_REGISTRY}

    for block_id, lesson_block in lesson.blocks.items():
        registry_block = registry_by_id.get(block_id)

        if registry_block is None:
            raise ValueError(f"Unknown block id: {block_id}")

        if lesson_block.block_id != block_id:
            raise ValueError(
                f"Block payload mismatch. Expected block_id {block_id}, got {lesson_block.block_id}."
            )

        allowed_labels = {registry_block.label}
        allowed_labels.update(ALTERNATE_BLOCK_LABELS.get((lesson.unit_id, block_id), set()))

        if lesson_block.label not in allowed_labels:
            raise ValueError(
                f"Invalid block label for block {block_id}. "
                f"Expected one of {sorted(allowed_labels)!r}, got {lesson_block.label!r}."
            )

        for slide in lesson_block.slides:
            if slide.block_id != block_id:
                raise ValueError(
                    f"Slide {slide.slide_id} has block_id {slide.block_id}, expected {block_id}."
                )

            if not registry.exists(str(slide.view_type)):
                raise ValueError(
                    f"Slide {slide.slide_id} uses unknown view_type {slide.view_type!r}."
                )
