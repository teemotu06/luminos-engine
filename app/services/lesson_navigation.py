from typing import Any

from app.services.lesson_service import ordered_blocks

def flatten_lesson_slides(lesson: Any) -> list[dict]:
    ordered_slides = []
    slide_index = 0

    for block in ordered_blocks(lesson):
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
