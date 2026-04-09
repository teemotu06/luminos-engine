import json
import os
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:////tmp/luminos_engine_test_new_types_authoring.db"
os.environ["LUMINOS_AUTH_REQUIRED"] = "false"

from app.routers.authoring import router as authoring_router


def _lesson_payload():
    return {
        "lesson_id": "G1-L91",
        "unit_id": "G1",
        "target_pattern": "test",
        "title": "Integration Lesson",
        "new_units": ["t"],
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


def test_new_types_authoring_integration(tmp_path):
    lessons_dir = tmp_path / "lessons"
    backups_dir = tmp_path / "backups"
    groups_file = tmp_path / "groups.json"
    lessons_dir.mkdir()
    backups_dir.mkdir()
    groups_file.write_text(Path("app/content/groups.json").read_text(encoding="utf-8"), encoding="utf-8")
    lesson_path = lessons_dir / "G1-L91.json"
    lesson_path.write_text(json.dumps(_lesson_payload()), encoding="utf-8")

    app = FastAPI()
    app.include_router(authoring_router)
    client = TestClient(app)
    with patch("app.services.lesson_authoring_service.LESSONS_DIR", lessons_dir), \
         patch("app.services.lesson_service.LESSONS_DIR", lessons_dir), \
         patch("app.services.lesson_backup_service.LESSON_BACKUPS_DIR", backups_dir), \
         patch("app.services.group_service.GROUPS_FILE", groups_file):
        specs = [
            (
                "fill_in_the_blank",
                "03",
                {
                    "payload__sentence_template": "The ___ is red.",
                    "payload__correct_answer": "cat",
                    "payload__distractors": "dog\nsun",
                },
            ),
            (
                "word_sort",
                "04",
                {
                    "payload__instruction_text": "Sort the words",
                    "payload__categories": json.dumps([
                        {"category_label": "Short a", "words": ["cat", "map"]},
                        {"category_label": "Long a", "words": ["cake", "gate"]},
                    ]),
                },
            ),
            (
                "sentence_builder",
                "05",
                {
                    "payload__target_sentence": "I can read.",
                    "payload__word_tiles": "I\ncan\nread.",
                    "payload__image_url": "/static/uploads/images/book.png",
                },
            ),
        ]
        for type_key, block_id, payload in specs:
            client.post("/authoring/lessons/G1-L91/blocks/%s/slides/add" % block_id, data={"view_type": type_key})
            current = json.loads(lesson_path.read_text(encoding="utf-8"))
            slide_id = current["blocks"][block_id]["slides"][0]["slide_id"]
            response = client.post(
                "/authoring/lessons/G1-L91/blocks/%s/slides/%s" % (block_id, slide_id),
                data=dict(
                    {
                        "slide_title": type_key,
                        "teacher_cue": "Cue",
                        "expected_response": "Students complete the task correctly.",
                        "correction_move": "Model and retry.",
                        "observation_note": "Watch for accuracy.",
                    },
                    **payload
                ),
            )
            assert response.status_code == 200

        saved = client.post("/authoring/lessons/G1-L91/save")
        assert saved.status_code == 200
        stored = json.loads(lesson_path.read_text(encoding="utf-8"))
        assert stored["blocks"]["03"]["slides"][0]["view_type"] == "fill_in_the_blank"
        assert stored["blocks"]["04"]["slides"][0]["view_type"] == "word_sort"
        assert stored["blocks"]["05"]["slides"][0]["view_type"] == "sentence_builder"
    client.close()
