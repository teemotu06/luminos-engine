import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.lesson import LessonRecord
from app.schemas.lesson import Lesson
from app.services.block_registry import BLOCK_REGISTRY
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
    lesson_data.setdefault("json_path", str(get_lesson_file_path(lesson_id).relative_to("app")))
    return parse_lesson(lesson_data)


def list_lesson_ids() -> list[str]:
    lesson_files = LESSONS_DIR.glob("*.json")
    return sorted(file.stem for file in lesson_files)


def load_all_lessons() -> list[Lesson]:
    return [load_lesson(lesson_id) for lesson_id in list_lesson_ids()]


def ordered_blocks(lesson: Lesson):
    return [lesson.blocks[definition.block_id] for definition in BLOCK_REGISTRY]


def sync_lesson_record(db: Session, lesson: Lesson) -> LessonRecord:
    lesson_record = db.get(LessonRecord, lesson.lesson_id)

    if lesson_record is None:
        lesson_record = LessonRecord(
            lesson_id=lesson.lesson_id,
            unit_id=lesson.unit_id,
            target_pattern=lesson.target_pattern,
            content_pack_status=lesson.content_pack_status,
            json_path=lesson.json_path or "",
        )
        db.add(lesson_record)
    else:
        lesson_record.unit_id = lesson.unit_id
        lesson_record.target_pattern = lesson.target_pattern
        lesson_record.content_pack_status = lesson.content_pack_status
        lesson_record.json_path = lesson.json_path or lesson_record.json_path

    db.flush()
    return lesson_record


def sync_all_lessons(db: Session) -> None:
    for lesson in load_all_lessons():
        sync_lesson_record(db, lesson)
    db.commit()
