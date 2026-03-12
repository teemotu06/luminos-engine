from app.schemas.lesson import Lesson
from app.schemas.slide_payloads import VIEW_PAYLOAD_MAP


def validate_slide_payloads(lesson: Lesson) -> None:
    for block in lesson.blocks:
        for slide in block.slides:

            view_type = slide.view_type

            if view_type not in VIEW_PAYLOAD_MAP:
                raise ValueError(
                    f"Unknown view_type '{view_type}' in slide {slide.slide_id}"
                )

            payload_model = VIEW_PAYLOAD_MAP[view_type]

            try:
                payload_model(**slide.content_payload.dict())
            except Exception as e:
                raise ValueError(
                    f"Invalid payload in lesson '{lesson.lesson_id}', "
                    f"block {block.block_no}, slide '{slide.slide_id}', "
                    f"view_type '{view_type}': {e}"
                )