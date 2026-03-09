from app.schemas.lesson import Lesson
from app.services.block_registry import BLOCK_REGISTRY


def validate_lesson_blocks(lesson: Lesson) -> None:
    if not lesson.blocks:
        return

    expected_numbers = [block.block_no for block in BLOCK_REGISTRY]
    actual_numbers = [block.block_no for block in lesson.blocks]

    if actual_numbers != expected_numbers:
        raise ValueError(
            f"Invalid block order. Expected {expected_numbers}, got {actual_numbers}."
        )

    registry_by_number = {block.block_no: block for block in BLOCK_REGISTRY}

    for lesson_block in lesson.blocks:
        registry_block = registry_by_number.get(lesson_block.block_no)

        if registry_block is None:
            raise ValueError(f"Unknown block number: {lesson_block.block_no}")

        if lesson_block.code != registry_block.code:
            raise ValueError(
                f"Invalid block code for block {lesson_block.block_no}. "
                f"Expected {registry_block.code}, got {lesson_block.code}."
            )

        if lesson_block.label != registry_block.label:
            raise ValueError(
                f"Invalid block label for block {lesson_block.block_no}. "
                f"Expected {registry_block.label!r}, got {lesson_block.label!r}."
            )