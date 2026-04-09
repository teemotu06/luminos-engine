from __future__ import annotations

from typing import Dict, List, Optional

from app.services.block_registry import BLOCK_REGISTRY
from app.services.lesson_service import parse_lesson


def generate_skeleton(
    unit_id: str,
    lesson_number: int,
    title: str,
    target_pattern: str,
    new_units: Optional[List[str]] = None,
    new_sight_words: Optional[List[str]] = None,
) -> dict:
    lesson = {
        "lesson_id": "%s-L%s" % (unit_id, lesson_number),
        "unit_id": unit_id,
        "target_pattern": target_pattern,
        "title": title,
        "new_units": new_units or [],
        "new_sight_words": new_sight_words or [],
        "korean_interference_active": [],
        "content_pack_status": "draft",
        "blocks": {
            definition.block_id: {
                "block_id": definition.block_id,
                "label": definition.label,
                "slides": [],
            }
            for definition in BLOCK_REGISTRY
        },
    }
    parse_lesson(lesson)
    return lesson
