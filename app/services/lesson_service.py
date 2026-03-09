import json
from pathlib import Path

from app.schemas.lesson import Lesson
from app.schemas.lesson_block import LessonBlock
from app.services.block_registry import BLOCK_REGISTRY_BY_NUMBER
from app.services.block_validator import validate_lesson_blocks


LESSONS_DIR = Path("app/content/lessons")


def _build_lesson_blocks(blocks_payload: dict) -> list[LessonBlock]:
    lesson_blocks = []

    for block_data in blocks_payload["blocks"]:
        block_number = block_data["block_no"]

        if block_number not in BLOCK_REGISTRY_BY_NUMBER:
            raise ValueError(f"Unknown block number: {block_number}")

        lesson_blocks.append(LessonBlock(**block_data))

    return lesson_blocks


def load_lesson(lesson_id: str) -> Lesson:
    lesson_file_path = LESSONS_DIR / f"{lesson_id}.json"
    blocks_file_path = LESSONS_DIR / f"{lesson_id}_blocks.json"

    with open(lesson_file_path, "r", encoding="utf-8") as f:
        lesson_data = json.load(f)

    with open(blocks_file_path, "r", encoding="utf-8") as f:
        blocks_payload = json.load(f)

    lesson = Lesson(**lesson_data)
    lesson.blocks = _build_lesson_blocks(blocks_payload)

    validate_lesson_blocks(lesson)
    return lesson