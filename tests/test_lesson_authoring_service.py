import json
from pathlib import Path
from unittest.mock import patch

from app.services import lesson_authoring_service


def _write_lesson(path: Path, lesson_id: str, unit_id: str = "G1") -> None:
    payload = {
        "lesson_id": lesson_id,
        "unit_id": unit_id,
        "target_pattern": "a",
        "title": lesson_id,
        "new_units": [],
        "new_sight_words": [],
        "korean_interference_active": [],
        "content_pack_status": "draft",
        "blocks": {
            "01": {"block_id": "01", "label": "Flashcard Phoneme Review", "slides": []},
            "02": {"block_id": "02", "label": "Listening & Write Review", "slides": []},
            "03": {"block_id": "03", "label": "New Sound Introduction", "slides": []},
            "04": {"block_id": "04", "label": "Vocabulary Warm-Up", "slides": []},
            "05": {"block_id": "05", "label": "Word Building", "slides": []},
            "06": {"block_id": "06", "label": "Sentence Bridge", "slides": []},
            "07": {"block_id": "07", "label": "Decodable Reader / Fluency", "slides": []},
            "08": {"block_id": "08", "label": "Encoding & Writing", "slides": []},
            "09": {"block_id": "09", "label": "Morpheme Moment", "slides": []},
            "10": {"block_id": "10", "label": "Meaning-Making Close", "slides": []},
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_create_lesson_writes_valid_json_file(tmp_path):
    lessons_dir = tmp_path / "lessons"
    backups_dir = tmp_path / "lesson_backups"
    lessons_dir.mkdir()
    with patch("app.services.lesson_authoring_service.LESSONS_DIR", lessons_dir), \
         patch("app.services.lesson_service.LESSONS_DIR", lessons_dir):
        lesson = lesson_authoring_service.create_lesson("G11", 72, "Title", "oa", ["oa"], ["the"])
        target = lessons_dir / "G11-L72.json"
        assert target.exists()
        assert lesson["lesson_id"] == "G11-L72"


def test_duplicate_lesson_creates_independent_copy(tmp_path):
    lessons_dir = tmp_path / "lessons"
    lessons_dir.mkdir()
    _write_lesson(lessons_dir / "G1-L1.json", "G1-L1", "G1")
    with patch("app.services.lesson_authoring_service.LESSONS_DIR", lessons_dir), \
         patch("app.services.lesson_service.LESSONS_DIR", lessons_dir):
        duplicate = lesson_authoring_service.duplicate_lesson("G1-L1", "G1-L2")
        assert duplicate["lesson_id"] == "G1-L2"
        assert (lessons_dir / "G1-L2.json").exists()


def test_delete_lesson_creates_backup_and_removes_original(tmp_path):
    lessons_dir = tmp_path / "lessons"
    backups_dir = tmp_path / "lesson_backups"
    lessons_dir.mkdir()
    backups_dir.mkdir()
    _write_lesson(lessons_dir / "G1-L1.json", "G1-L1", "G1")
    with patch("app.services.lesson_authoring_service.LESSON_BACKUPS_DIR", backups_dir), \
         patch("app.services.lesson_authoring_service.LESSONS_DIR", lessons_dir), \
         patch("app.services.lesson_service.LESSONS_DIR", lessons_dir):
        deleted = lesson_authoring_service.delete_lesson("G1-L1")
        assert deleted is True
        assert not (lessons_dir / "G1-L1.json").exists()
        assert list(backups_dir.glob("G1-L1.*.json"))


def test_list_lessons_returns_correct_summaries_and_filter(tmp_path):
    lessons_dir = tmp_path / "lessons"
    lessons_dir.mkdir()
    _write_lesson(lessons_dir / "G1-L1.json", "G1-L1", "G1")
    _write_lesson(lessons_dir / "G2-L2.json", "G2-L2", "G2")
    with patch("app.services.lesson_authoring_service.LESSONS_DIR", lessons_dir), \
         patch("app.services.lesson_service.LESSONS_DIR", lessons_dir):
        all_lessons = lesson_authoring_service.list_lessons()
        g1_lessons = lesson_authoring_service.list_lessons(unit_id="G1")
        assert len(all_lessons) == 2
        assert len(g1_lessons) == 1
        assert g1_lessons[0]["lesson_id"] == "G1-L1"
