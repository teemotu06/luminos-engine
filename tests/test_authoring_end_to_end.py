import json
import os
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:////tmp/luminos_engine_test_authoring_e2e.db"
os.environ["LUMINOS_AUTH_REQUIRED"] = "false"

from app.routers.authoring import router as authoring_router
from app.schemas.slide_payloads import ConnectWordToPicturePayload
from app.services.lesson_service import parse_lesson
from app.slide_types import registry


def _seed_groups(tmp_path: Path) -> Path:
    groups_file = tmp_path / "groups.json"
    groups_file.write_text(Path("app/content/groups.json").read_text(encoding="utf-8"), encoding="utf-8")
    return groups_file


def _make_client():
    app = FastAPI()
    app.include_router(authoring_router)
    return TestClient(app)


def test_new_slide_type_registered_without_central_edits():
    assert "connect_word_to_picture" in registry.all_type_keys()
    assert registry.label_for("connect_word_to_picture") == "Connect Word to Picture"
    assert registry.payload_model_for("connect_word_to_picture") is ConnectWordToPicturePayload
    teacher_template = registry.teacher_template_for("connect_word_to_picture")
    board_template = registry.board_template_for("connect_word_to_picture")
    assert Path("app/templates/%s" % teacher_template).exists()
    assert Path("app/templates/%s" % board_template).exists()
    summary = registry.summary_for("connect_word_to_picture", registry.get("connect_word_to_picture").default_payload)
    assert isinstance(summary, str)


def test_create_group_and_lesson_end_to_end(tmp_path):
    lessons_dir = tmp_path / "lessons"
    backups_dir = tmp_path / "backups"
    lessons_dir.mkdir()
    backups_dir.mkdir()
    groups_file = _seed_groups(tmp_path)
    client = _make_client()
    with patch("app.services.group_service.GROUPS_FILE", groups_file), \
         patch("app.services.lesson_authoring_service.LESSONS_DIR", lessons_dir), \
         patch("app.services.lesson_service.LESSONS_DIR", lessons_dir), \
         patch("app.services.lesson_backup_service.LESSON_BACKUPS_DIR", backups_dir):
        created_group = client.post(
            "/authoring/groups",
            data={"unit_id": "G11", "title": "Phase 7 Test Group", "description": "", "target_phonemes": ""},
            follow_redirects=False,
        )
        assert created_group.status_code == 303
        group_list = client.get("/authoring/groups")
        assert "Phase 7 Test Group" in group_list.text

        created_lesson = client.post(
            "/authoring/lessons",
            data={
                "unit_id": "G11",
                "lesson_number": "72",
                "title": "Test Lesson",
                "target_pattern": "test",
                "new_units": "test",
                "new_sight_words": "",
            },
            follow_redirects=False,
        )
        assert created_lesson.status_code == 303
        lesson_path = lessons_dir / "G11-L72.json"
        assert lesson_path.exists()
        lesson_data = json.loads(lesson_path.read_text(encoding="utf-8"))
        parse_lesson(lesson_data)
        library = client.get("/authoring/lessons?unit_id=G11")
        assert "G11-L72" in library.text
    client.close()


def test_add_slides_and_save_end_to_end(tmp_path):
    lessons_dir = tmp_path / "lessons"
    backups_dir = tmp_path / "backups"
    lessons_dir.mkdir()
    backups_dir.mkdir()
    groups_file = _seed_groups(tmp_path)
    client = _make_client()
    with patch("app.services.group_service.GROUPS_FILE", groups_file), \
         patch("app.services.lesson_authoring_service.LESSONS_DIR", lessons_dir), \
         patch("app.services.lesson_service.LESSONS_DIR", lessons_dir), \
         patch("app.services.lesson_backup_service.LESSON_BACKUPS_DIR", backups_dir):
        client.post(
            "/authoring/lessons",
            data={"unit_id": "G1", "lesson_number": "99", "title": "Workflow Lesson", "target_pattern": "test", "new_units": "test", "new_sight_words": ""},
            follow_redirects=False,
        )
        client.post("/authoring/lessons/G1-L99/blocks/03/slides/add", data={"view_type": "flashcard"})
        client.post("/authoring/lessons/G1-L99/blocks/04/slides/add", data={"view_type": "connect_word_to_picture"})

        lesson_data = json.loads((lessons_dir / "G1-L99.json").read_text(encoding="utf-8"))
        flashcard_id = lesson_data["blocks"]["03"]["slides"][0]["slide_id"]
        connect_id = lesson_data["blocks"]["04"]["slides"][0]["slide_id"]

        client.post(
            "/authoring/lessons/G1-L99/blocks/03/slides/%s" % flashcard_id,
            data={
                "slide_title": "Flashcard Test",
                "teacher_cue": "Cue",
                "expected_response": "Students say /t/.",
                "correction_move": "Model and repeat.",
                "observation_note": "Watch for clean production.",
                "payload__front_text": "Test phoneme",
                "payload__back_text": "/t/",
            },
        )
        client.post(
            "/authoring/lessons/G1-L99/blocks/04/slides/%s" % connect_id,
            data={
                "slide_title": "Connect Slide",
                "teacher_cue": "Match them",
                "expected_response": "Students match each word to its picture.",
                "correction_move": "Model one match and retry.",
                "observation_note": "Watch for word reading before matching.",
                "payload__instruction_text": "Match each word to its picture",
                "payload__items": json.dumps(
                    [
                        {"word": "cat", "image_url": "/static/uploads/images/cat.png"},
                        {"word": "dog", "image_url": "/static/uploads/images/dog.png"},
                        {"word": "sun", "image_url": "/static/uploads/images/sun.png"},
                    ]
                ),
            },
        )
        saved = client.post("/authoring/lessons/G1-L99/save")
        assert saved.status_code == 200
        assert list(backups_dir.glob("G1-L99.*.json"))

        reloaded = json.loads((lessons_dir / "G1-L99.json").read_text(encoding="utf-8"))
        assert reloaded["blocks"]["03"]["slides"][0]["content_payload"]["front_text"] == "Test phoneme"
        assert len(reloaded["blocks"]["04"]["slides"][0]["content_payload"]["items"]) == 3
        parse_lesson(reloaded)
    client.close()


def test_authored_lesson_loads_through_runtime(tmp_path):
    lessons_dir = tmp_path / "lessons"
    backups_dir = tmp_path / "backups"
    lessons_dir.mkdir()
    backups_dir.mkdir()
    groups_file = _seed_groups(tmp_path)
    client = _make_client()
    with patch("app.services.group_service.GROUPS_FILE", groups_file), \
         patch("app.services.lesson_authoring_service.LESSONS_DIR", lessons_dir), \
         patch("app.services.lesson_service.LESSONS_DIR", lessons_dir), \
         patch("app.services.lesson_backup_service.LESSON_BACKUPS_DIR", backups_dir):
        client.post(
            "/authoring/lessons",
            data={"unit_id": "G1", "lesson_number": "88", "title": "Runtime Lesson", "target_pattern": "runtime", "new_units": "runtime", "new_sight_words": ""},
            follow_redirects=False,
        )
        client.post("/authoring/lessons/G1-L88/blocks/03/slides/add", data={"view_type": "flashcard"})
        authored = json.loads((lessons_dir / "G1-L88.json").read_text(encoding="utf-8"))
        lesson = parse_lesson(authored)
        assert lesson.lesson_id == "G1-L88"
        assert (lessons_dir / "G1-L88.json").exists()
    client.close()


def test_duplicate_and_delete_end_to_end(tmp_path):
    lessons_dir = tmp_path / "lessons"
    backups_dir = tmp_path / "backups"
    lessons_dir.mkdir()
    backups_dir.mkdir()
    groups_file = _seed_groups(tmp_path)
    client = _make_client()
    with patch("app.services.group_service.GROUPS_FILE", groups_file), \
         patch("app.services.lesson_authoring_service.LESSONS_DIR", lessons_dir), \
         patch("app.services.lesson_service.LESSONS_DIR", lessons_dir), \
         patch("app.services.lesson_backup_service.LESSON_BACKUPS_DIR", backups_dir):
        client.post(
            "/authoring/lessons",
            data={"unit_id": "G1", "lesson_number": "77", "title": "Duplicate Lesson", "target_pattern": "dup", "new_units": "dup", "new_sight_words": ""},
            follow_redirects=False,
        )
        client.post("/authoring/lessons/G1-L77/blocks/03/slides/add", data={"view_type": "flashcard"})

        duplicate = client.post("/authoring/lessons/G1-L77/duplicate", follow_redirects=False)
        assert duplicate.status_code == 303
        duplicates = sorted(path.stem for path in lessons_dir.glob("G1-L*.json"))
        assert "G1-L77" in duplicates
        assert len(duplicates) == 2

        original_data = json.loads((lessons_dir / "G1-L77.json").read_text(encoding="utf-8"))
        duplicate_id = [lesson_id for lesson_id in duplicates if lesson_id != "G1-L77"][0]
        duplicate_data = json.loads((lessons_dir / ("%s.json" % duplicate_id)).read_text(encoding="utf-8"))
        assert duplicate_data["lesson_id"] != original_data["lesson_id"]
        assert duplicate_data["blocks"]["03"]["slides"][0]["view_type"] == original_data["blocks"]["03"]["slides"][0]["view_type"]

        deleted = client.post("/authoring/lessons/G1-L77/delete", follow_redirects=False)
        assert deleted.status_code == 303
        assert not (lessons_dir / "G1-L77.json").exists()
        assert list(backups_dir.glob("G1-L77.*.json"))
        parse_lesson(duplicate_data)
    client.close()
