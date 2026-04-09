import json
import os
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:////tmp/luminos_engine_test_slide_form_validation.db"
os.environ["LUMINOS_AUTH_REQUIRED"] = "false"

from app.routers.authoring import router as authoring_router


def _lesson_payload():
    return {
        "lesson_id": "G1-L92",
        "unit_id": "G1",
        "target_pattern": "oa",
        "title": "Validation Lesson",
        "new_units": ["oa"],
        "new_sight_words": [],
        "korean_interference_active": [],
        "content_pack_status": "draft",
        "blocks": {
            "01": {
                "block_id": "01",
                "label": "Flashcard Phoneme Review",
                "slides": [
                    {
                        "slide_id": "flashcard_1234abcd",
                        "block_id": "01",
                        "slide_title": "Card 1",
                        "view_type": "flashcard",
                        "content_payload": {"front_text": "oa", "back_text": "/oa/"},
                        "teacher_cue": "",
                        "expected_response": "",
                        "correction_move": "",
                        "observation_note": "",
                        "korean_interference_flag": None,
                        "markable": False,
                        "marking_options": [],
                        "next_action": "manual_next",
                    }
                ],
            },
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


def test_slide_form_validation_rules(tmp_path):
    lessons_dir = tmp_path / "lessons"
    backups_dir = tmp_path / "backups"
    groups_file = tmp_path / "groups.json"
    lessons_dir.mkdir()
    backups_dir.mkdir()
    groups_file.write_text(Path("app/content/groups.json").read_text(encoding="utf-8"), encoding="utf-8")
    lesson_path = lessons_dir / "G1-L92.json"
    lesson_path.write_text(json.dumps(_lesson_payload()), encoding="utf-8")

    app = FastAPI()
    app.include_router(authoring_router)
    client = TestClient(app)

    with patch("app.services.lesson_authoring_service.LESSONS_DIR", lessons_dir), \
         patch("app.services.lesson_service.LESSONS_DIR", lessons_dir), \
         patch("app.services.lesson_backup_service.LESSON_BACKUPS_DIR", backups_dir), \
         patch("app.services.group_service.GROUPS_FILE", groups_file):
        base_payload = {
            "slide_title": "Updated Card",
            "teacher_cue": "Teach it",
            "expected_response": "Students say the sound.",
            "correction_move": "Model and repeat.",
            "observation_note": "Watch for accuracy.",
            "payload__front_text": "Updated",
            "payload__back_text": "/updated/",
        }

        missing_teacher_cue = client.post(
            "/authoring/lessons/G1-L92/blocks/01/slides/flashcard_1234abcd",
            data=dict(base_payload, teacher_cue=""),
        )
        assert missing_teacher_cue.status_code == 400

        missing_expected = client.post(
            "/authoring/lessons/G1-L92/blocks/01/slides/flashcard_1234abcd",
            data=dict(base_payload, expected_response=""),
        )
        assert missing_expected.status_code == 200

        defaults_applied = client.post(
            "/authoring/lessons/G1-L92/blocks/01/slides/flashcard_1234abcd",
            data=dict(base_payload, markable="true", marking_options="custom\nwrong"),
        )
        assert defaults_applied.status_code == 200
        stored = json.loads(lesson_path.read_text(encoding="utf-8"))
        slide = stored["blocks"]["01"]["slides"][0]
        assert slide["markable"] is True
        assert slide["marking_options"] == ["secure", "shaky", "missed"]

        markable_off = client.post(
            "/authoring/lessons/G1-L92/blocks/01/slides/flashcard_1234abcd",
            data=dict(base_payload),
        )
        assert markable_off.status_code == 200
        stored = json.loads(lesson_path.read_text(encoding="utf-8"))
        slide = stored["blocks"]["01"]["slides"][0]
        assert slide["markable"] is False
        assert slide["marking_options"] == []

        markable_on_again = client.post(
            "/authoring/lessons/G1-L92/blocks/01/slides/flashcard_1234abcd",
            data=dict(base_payload, markable="true"),
        )
        assert markable_on_again.status_code == 200
        stored = json.loads(lesson_path.read_text(encoding="utf-8"))
        slide = stored["blocks"]["01"]["slides"][0]
        assert slide["markable"] is True
        assert slide["marking_options"] == ["secure", "shaky", "missed"]

        advanced_saved = client.post(
            "/authoring/lessons/G1-L92/blocks/01/slides/flashcard_1234abcd",
            data=dict(base_payload, markable="true", payload__blend_units=json.dumps([{"grapheme": "oa", "phoneme": "/oa/"}])),
        )
        assert advanced_saved.status_code == 200
        stored = json.loads(lesson_path.read_text(encoding="utf-8"))
        slide = stored["blocks"]["01"]["slides"][0]
        assert slide["teacher_cue"] == "Teach it"
        assert slide["content_payload"]["blend_units"] == [{"grapheme": "oa", "phoneme": "/oa/"}]

        image_only_front = client.post(
            "/authoring/lessons/G1-L92/blocks/01/slides/flashcard_1234abcd",
            data={
                "slide_title": "Image Front Card",
                "teacher_cue": "Teach it",
                "expected_response": "Students say the sound.",
                "correction_move": "Model and repeat.",
                "observation_note": "Watch for accuracy.",
                "payload__front_text": "",
                "payload__front_image": "/static/uploads/images/front.png",
                "payload__back_text": "/updated/",
                "payload__back_image": "",
            },
        )
        assert image_only_front.status_code == 200
        stored = json.loads(lesson_path.read_text(encoding="utf-8"))
        slide = stored["blocks"]["01"]["slides"][0]
        assert slide["content_payload"]["front_text"] is None
        assert slide["content_payload"]["front_image"] == "/static/uploads/images/front.png"

    client.close()
