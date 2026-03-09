import json
from pathlib import Path

from app.schemas.lesson import Lesson
from app.services.block_validator import validate_lesson_blocks


LESSONS_DIR = Path("app/content/lessons")


def load_lesson(lesson_id: str) -> Lesson:
    lesson_file_path = LESSONS_DIR / f"{lesson_id}.json"

    with open(lesson_file_path, "r", encoding="utf-8") as f:
        lesson_data = json.load(f)

    lesson = Lesson(**lesson_data)
    validate_lesson_blocks(lesson)
    return lesson