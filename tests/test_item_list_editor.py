import json
import os
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:////tmp/luminos_engine_test_item_list_editor.db"
os.environ["LUMINOS_AUTH_REQUIRED"] = "false"

from app.routers.authoring import router as authoring_router


def _lesson_payload():
    return {
        "lesson_id": "G1-L90",
        "unit_id": "G1",
        "target_pattern": "match",
        "title": "Match Lesson",
        "new_units": ["m"],
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


def test_json_encoded_items_array_updates_payload(tmp_path):
    lessons_dir = tmp_path / "lessons"
    backups_dir = tmp_path / "backups"
    groups_file = tmp_path / "groups.json"
    lessons_dir.mkdir()
    backups_dir.mkdir()
    groups_file.write_text(Path("app/content/groups.json").read_text(encoding="utf-8"), encoding="utf-8")
    lesson_path = lessons_dir / "G1-L90.json"
    lesson_path.write_text(json.dumps(_lesson_payload()), encoding="utf-8")

    app = FastAPI()
    app.include_router(authoring_router)
    client = TestClient(app)
    with patch("app.services.lesson_authoring_service.LESSONS_DIR", lessons_dir), \
         patch("app.services.lesson_service.LESSONS_DIR", lessons_dir), \
         patch("app.services.lesson_backup_service.LESSON_BACKUPS_DIR", backups_dir), \
         patch("app.services.group_service.GROUPS_FILE", groups_file):
        client.post("/authoring/lessons/G1-L90/blocks/04/slides/add", data={"view_type": "connect_word_to_picture"})
        data = json.loads(lesson_path.read_text(encoding="utf-8"))
        slide_id = data["blocks"]["04"]["slides"][0]["slide_id"]
        response = client.post(
            "/authoring/lessons/G1-L90/blocks/04/slides/%s" % slide_id,
            data={
                "slide_title": "Match Words",
                "teacher_cue": "Match them",
                "expected_response": "Students connect each word to the correct picture.",
                "correction_move": "Model one match and try again.",
                "observation_note": "Watch whether students read the words first.",
                "payload__instruction_text": "Match each word to its picture",
                "payload__items": json.dumps([
                    {"word": "cat", "image_url": "/static/uploads/images/cat.png", "audio_url": "/static/uploads/audio/cat.mp3"},
                    {"word": "dog", "image_url": "/static/uploads/images/dog.png", "audio_url": ""},
                    {"word": "sun", "image_url": "/static/uploads/images/sun.png", "audio_url": None},
                ]),
            },
        )
        assert response.status_code == 200
        stored = json.loads(lesson_path.read_text(encoding="utf-8"))
        items = stored["blocks"]["04"]["slides"][0]["content_payload"]["items"]
        assert len(items) == 3
        assert items[0]["image_url"] == "/static/uploads/images/cat.png"
        assert items[0]["audio_url"] == "/static/uploads/audio/cat.mp3"
    client.close()


def test_empty_items_list_rejected_by_payload_validation(tmp_path):
    lessons_dir = tmp_path / "lessons"
    backups_dir = tmp_path / "backups"
    groups_file = tmp_path / "groups.json"
    lessons_dir.mkdir()
    backups_dir.mkdir()
    groups_file.write_text(Path("app/content/groups.json").read_text(encoding="utf-8"), encoding="utf-8")
    lesson_path = lessons_dir / "G1-L90.json"
    lesson_path.write_text(json.dumps(_lesson_payload()), encoding="utf-8")

    app = FastAPI()
    app.include_router(authoring_router)
    client = TestClient(app)
    with patch("app.services.lesson_authoring_service.LESSONS_DIR", lessons_dir), \
         patch("app.services.lesson_service.LESSONS_DIR", lessons_dir), \
         patch("app.services.lesson_backup_service.LESSON_BACKUPS_DIR", backups_dir), \
         patch("app.services.group_service.GROUPS_FILE", groups_file):
        client.post("/authoring/lessons/G1-L90/blocks/04/slides/add", data={"view_type": "connect_word_to_picture"})
        data = json.loads(lesson_path.read_text(encoding="utf-8"))
        slide_id = data["blocks"]["04"]["slides"][0]["slide_id"]
        response = client.post(
            "/authoring/lessons/G1-L90/blocks/04/slides/%s" % slide_id,
            data={
                "slide_title": "Match Words",
                "teacher_cue": "Match them",
                "expected_response": "Students connect each word to the correct picture.",
                "correction_move": "Model one match and try again.",
                "observation_note": "Watch whether students read the words first.",
                "payload__instruction_text": "Match each word to its picture",
                "payload__items": json.dumps([]),
            },
        )
        assert response.status_code == 400
    client.close()
