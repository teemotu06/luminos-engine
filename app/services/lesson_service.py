import json
from pathlib import Path

from app.schemas.lesson import Lesson


LESSONS_DIR = Path("app/content/lessons")


def load_lesson(lesson_id: str) -> Lesson:
    file_path = LESSONS_DIR / f"{lesson_id}.json"

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return Lesson(**data)