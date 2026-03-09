from typing import Any


def flatten_lesson_slides(lesson: Any) -> list[dict]:
    ordered_slides = []

    for block in lesson.blocks:
        for slide in block.slides:
            ordered_slides.append(
                {
                    "block": block,
                    "slide": slide,
                }
            )

    return ordered_slides