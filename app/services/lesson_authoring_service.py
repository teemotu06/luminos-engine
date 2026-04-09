from __future__ import annotations

import json
import re
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Dict, List, Optional

from app.services import lesson_backup_service
from app.services.lesson_service import (
    LESSON_ID_RE,
    LESSONS_DIR as RUNTIME_LESSONS_DIR,
    get_lesson_file_path,
    invalidate_lesson_id_cache,
    lesson_sort_key,
    parse_lesson,
    read_lesson_data,
)
from app.services.lesson_skeleton_service import generate_skeleton

LESSONS_DIR = RUNTIME_LESSONS_DIR
DEFAULT_LESSON_BACKUPS_DIR = Path("app/content/lesson_backups")
LESSON_BACKUPS_DIR = DEFAULT_LESSON_BACKUPS_DIR


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), delete=False) as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
        temp_path = Path(handle.name)
    temp_path.replace(path)


def _invalidate_cache() -> None:
    invalidate_lesson_id_cache()


def _backup_lesson(lesson_id: str) -> Path:
    if LESSON_BACKUPS_DIR != DEFAULT_LESSON_BACKUPS_DIR:
        lesson_backup_service.LESSON_BACKUPS_DIR = LESSON_BACKUPS_DIR
    return Path(lesson_backup_service.backup_lesson(lesson_id))


def _slide_count(lesson_data: dict) -> int:
    return sum(len(block.get("slides", [])) for block in lesson_data.get("blocks", {}).values())


def list_lessons(unit_id: Optional[str] = None) -> List[dict]:
    summaries = []
    lesson_ids = sorted((path.stem for path in LESSONS_DIR.glob("*.json")), key=lesson_sort_key)
    for lesson_id in lesson_ids:
        lesson_data = read_lesson_data(lesson_id)
        if unit_id and lesson_data.get("unit_id") != unit_id:
            continue
        summaries.append(
            {
                "lesson_id": lesson_data.get("lesson_id", lesson_id),
                "unit_id": lesson_data.get("unit_id", ""),
                "title": lesson_data.get("title", ""),
                "target_pattern": lesson_data.get("target_pattern", ""),
                "slide_count": _slide_count(lesson_data),
                "content_pack_status": lesson_data.get("content_pack_status", "draft"),
            }
        )
    return summaries


def get_lesson(lesson_id: str) -> dict:
    return read_lesson_data(lesson_id)


def create_lesson(
    unit_id: str,
    lesson_number: int,
    title: str,
    target_pattern: str,
    new_units: Optional[List[str]] = None,
    new_sight_words: Optional[List[str]] = None,
) -> dict:
    lesson = generate_skeleton(
        unit_id=unit_id,
        lesson_number=lesson_number,
        title=title,
        target_pattern=target_pattern,
        new_units=new_units,
        new_sight_words=new_sight_words,
    )
    destination = get_lesson_file_path(lesson["lesson_id"])
    if destination.exists():
        raise ValueError("Lesson already exists.")
    _write_json_atomic(destination, lesson)
    _invalidate_cache()
    return lesson


def duplicate_lesson(source_lesson_id: str, new_lesson_id: str) -> dict:
    source_data = get_lesson(source_lesson_id)
    destination = get_lesson_file_path(new_lesson_id)
    if destination.exists():
        raise ValueError("Lesson already exists.")
    duplicated = json.loads(json.dumps(source_data))
    duplicated["lesson_id"] = new_lesson_id
    match = LESSON_ID_RE.match(new_lesson_id)
    if match:
        duplicated["unit_id"] = "G%s" % int(match.group("group"))
    parse_lesson(duplicated)
    _write_json_atomic(destination, duplicated)
    _invalidate_cache()
    return duplicated


def move_lesson(lesson_id: str, new_unit_id: str) -> dict:
    lesson = get_lesson(lesson_id)
    source = get_lesson_file_path(lesson_id)
    match = LESSON_ID_RE.match(lesson_id)
    if match and LESSON_ID_RE.match("%s-L%s" % (new_unit_id, match.group("lesson"))):
        new_lesson_id = "%s-L%s" % (new_unit_id, int(match.group("lesson")))
    else:
        new_lesson_id = lesson_id
    destination = get_lesson_file_path(new_lesson_id)
    if destination.exists() and destination != source:
        raise ValueError("Destination lesson already exists.")

    updated = json.loads(json.dumps(lesson))
    updated["unit_id"] = new_unit_id
    updated["lesson_id"] = new_lesson_id
    parse_lesson(updated)
    _write_json_atomic(destination, updated)
    if destination != source and source.exists():
        source.unlink()
    _invalidate_cache()
    return updated


def delete_lesson(lesson_id: str) -> bool:
    source = get_lesson_file_path(lesson_id)
    if not source.exists():
        return False
    _backup_lesson(lesson_id)
    source.unlink()
    _invalidate_cache()
    return True


def next_lesson_number_for_unit(unit_id: str) -> int:
    numbers = []
    for summary in list_lessons(unit_id=unit_id):
        match = LESSON_ID_RE.match(summary["lesson_id"])
        if match:
            numbers.append(int(match.group("lesson")))
    return (max(numbers) + 1) if numbers else 1


def save_lesson_data(lesson_id: str, lesson_data: dict, backup: bool = False) -> dict:
    parse_lesson(lesson_data)
    if backup and get_lesson_file_path(lesson_id).exists():
        _backup_lesson(lesson_id)
    _write_json_atomic(get_lesson_file_path(lesson_id), lesson_data)
    _invalidate_cache()
    return lesson_data
