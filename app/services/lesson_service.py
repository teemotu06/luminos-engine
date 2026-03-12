import json
from pathlib import Path

from app.schemas.lesson import Lesson
from app.services.block_validator import validate_lesson_blocks
from app.services.slide_payload_validator import validate_slide_payloads


LESSONS_DIR = Path("app/content/lessons")


def get_lesson_file_path(lesson_id: str) -> Path:
    return LESSONS_DIR / f"{lesson_id}.json"


def read_lesson_data(lesson_id: str) -> dict:
    lesson_file_path = get_lesson_file_path(lesson_id)

    if not lesson_file_path.exists():
        raise FileNotFoundError(f"Lesson file not found: {lesson_file_path}")

    with open(lesson_file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_lesson(lesson_data: dict) -> Lesson:
    lesson = Lesson(**lesson_data)
    validate_lesson_blocks(lesson)
    validate_slide_payloads(lesson)
    return lesson


def load_lesson(lesson_id: str) -> Lesson:
    lesson_data = read_lesson_data(lesson_id)
    return parse_lesson(lesson_data)


def list_lesson_ids() -> list[str]:
    lesson_files = LESSONS_DIR.glob("*.json")
    return sorted(file.stem for file in lesson_files)


def load_all_lessons() -> list[Lesson]:
    return [load_lesson(lesson_id) for lesson_id in list_lesson_ids()]