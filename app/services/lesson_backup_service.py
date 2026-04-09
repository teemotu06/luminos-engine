from __future__ import annotations

import shutil
from pathlib import Path

from app.services.lesson_service import get_lesson_file_path

LESSON_BACKUPS_DIR = Path("app/content/lesson_backups")


def backup_lesson(lesson_id: str) -> str:
    source = get_lesson_file_path(lesson_id)
    if not source.exists():
        raise FileNotFoundError("Lesson not found: %s" % lesson_id)
    LESSON_BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = LESSON_BACKUPS_DIR / ("%s.%s.json" % (lesson_id, int(source.stat().st_mtime_ns)))
    shutil.copy2(source, backup_path)
    return str(backup_path)


def list_backups(lesson_id: str) -> list[dict]:
    LESSON_BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    backups = []
    prefix = "%s." % lesson_id
    for path in sorted(LESSON_BACKUPS_DIR.glob("%s*.json" % lesson_id), key=lambda item: item.stat().st_mtime, reverse=True):
        timestamp = path.name[len(prefix):-5] if path.name.startswith(prefix) else ""
        backups.append({"path": str(path), "filename": path.name, "timestamp": timestamp})
    return backups
