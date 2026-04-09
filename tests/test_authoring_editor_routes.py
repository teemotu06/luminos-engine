import json
import os
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:////tmp/luminos_engine_test_authoring_editor.db"
os.environ["LUMINOS_AUTH_REQUIRED"] = "false"

from app.routers.authoring import router as authoring_router


def _lesson_payload():
    return {
        "lesson_id": "G1-L99",
        "unit_id": "G1",
        "target_pattern": "oa",
        "title": "Test Lesson",
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


def _write_lesson(path: Path):
    path.write_text(json.dumps(_lesson_payload()), encoding="utf-8")


def test_authoring_editor_routes(tmp_path):
    lessons_dir = tmp_path / "lessons"
    backups_dir = tmp_path / "backups"
    groups_file = tmp_path / "groups.json"
    lessons_dir.mkdir()
    backups_dir.mkdir()
    groups_file.write_text(Path("app/content/groups.json").read_text(encoding="utf-8"), encoding="utf-8")
    _write_lesson(lessons_dir / "G1-L99.json")

    app = FastAPI()
    app.include_router(authoring_router)
    client = TestClient(app)
    with patch("app.services.lesson_authoring_service.LESSONS_DIR", lessons_dir), \
         patch("app.services.lesson_service.LESSONS_DIR", lessons_dir), \
         patch("app.services.lesson_backup_service.LESSON_BACKUPS_DIR", backups_dir), \
         patch("app.services.group_service.GROUPS_FILE", groups_file):
        response = client.get("/authoring/lessons/G1-L99/edit")
        assert response.status_code == 200
        assert "Test Lesson" in response.text

        panel = client.get("/authoring/lessons/G1-L99/blocks/01")
        assert panel.status_code == 200
        assert "flashcard_1234abcd" in panel.text

        added = client.post("/authoring/lessons/G1-L99/blocks/01/slides/add", data={"view_type": "audio_prompt"})
        assert added.status_code == 200
        assert "Listen" in added.text

        form = client.get("/authoring/lessons/G1-L99/blocks/01/slides/flashcard_1234abcd")
        assert form.status_code == 200
        assert 'name="slide_title"' in form.text
        assert "Students Should" not in form.text
        assert "If They Struggle" not in form.text

        updated = client.post(
            "/authoring/lessons/G1-L99/blocks/01/slides/flashcard_1234abcd",
            data={
                "slide_title": "Updated Card",
                "teacher_cue": "Teach it",
                "expected_response": "Students say the sound.",
                "correction_move": "Model and repeat.",
                "observation_note": "Watch for accuracy.",
                "payload__front_text": "Updated",
                "payload__back_text": "/updated/",
            },
        )
        assert updated.status_code == 200
        assert "Updated" in updated.text

        invalid = client.post(
            "/authoring/lessons/G1-L99/blocks/01/slides/flashcard_1234abcd",
            data={
                "slide_title": "Bad Card",
                "teacher_cue": "Teach it",
                "observation_note": "Watch for accuracy.",
                "payload__front_text": "",
                "payload__back_text": "/updated/",
            },
        )
        assert invalid.status_code == 400

        validate = client.post("/authoring/lessons/G1-L99/validate")
        assert validate.status_code == 200

        preview = client.get("/authoring/lessons/G1-L99/preview/01/flashcard_1234abcd/teacher")
        assert preview.status_code == 200
        assert "lesson-flashcard" in preview.text

        deleted = client.post("/authoring/lessons/G1-L99/blocks/01/slides/flashcard_1234abcd/delete")
        assert deleted.status_code == 200
        assert "flashcard_1234abcd" not in deleted.text

        saved = client.post("/authoring/lessons/G1-L99/save")
        assert saved.status_code == 200
        assert list(backups_dir.glob("G1-L99.*.json"))

    client.close()


def test_block_two_writing_review_form_uses_audio_first_labels(tmp_path):
    lessons_dir = tmp_path / "lessons"
    backups_dir = tmp_path / "backups"
    groups_file = tmp_path / "groups.json"
    lessons_dir.mkdir()
    backups_dir.mkdir()
    groups_file.write_text(Path("app/content/groups.json").read_text(encoding="utf-8"), encoding="utf-8")
    lesson = _lesson_payload()
    lesson["blocks"]["02"]["slides"] = [
        {
            "slide_id": "02-01",
            "block_id": "02",
            "slide_title": "Listen and Write",
            "view_type": "writing_encoding",
            "content_payload": {"dictated_text": "s", "expected_answer": "s"},
            "teacher_cue": "",
            "expected_response": "",
            "correction_move": "",
            "observation_note": "",
            "korean_interference_flag": None,
            "markable": False,
            "marking_options": [],
            "next_action": "manual_next",
        }
    ]
    (lessons_dir / "G1-L99.json").write_text(json.dumps(lesson), encoding="utf-8")

    app = FastAPI()
    app.include_router(authoring_router)
    client = TestClient(app)
    with patch("app.services.lesson_authoring_service.LESSONS_DIR", lessons_dir), \
         patch("app.services.lesson_service.LESSONS_DIR", lessons_dir), \
         patch("app.services.lesson_backup_service.LESSON_BACKUPS_DIR", backups_dir), \
         patch("app.services.group_service.GROUPS_FILE", groups_file):
        form = client.get("/authoring/lessons/G1-L99/blocks/02/slides/02-01")
        assert form.status_code == 200
        assert "Audio Transcript" in form.text
        assert "Shown on the board only after the teacher reveals the answer." in form.text
        assert "Dictation Word" not in form.text

    client.close()


def test_slide_audio_field_uses_direct_upload_ui(tmp_path):
    lessons_dir = tmp_path / "lessons"
    backups_dir = tmp_path / "backups"
    groups_file = tmp_path / "groups.json"
    lessons_dir.mkdir()
    backups_dir.mkdir()
    groups_file.write_text(Path("app/content/groups.json").read_text(encoding="utf-8"), encoding="utf-8")
    _write_lesson(lessons_dir / "G1-L99.json")

    app = FastAPI()
    app.include_router(authoring_router)
    client = TestClient(app)
    with patch("app.services.lesson_authoring_service.LESSONS_DIR", lessons_dir), \
         patch("app.services.lesson_service.LESSONS_DIR", lessons_dir), \
         patch("app.services.lesson_backup_service.LESSON_BACKUPS_DIR", backups_dir), \
         patch("app.services.group_service.GROUPS_FILE", groups_file):
        form = client.get("/authoring/lessons/G1-L99/blocks/01/slides/flashcard_1234abcd")
        assert form.status_code == 200
        assert "Upload Audio" in form.text
        assert 'data-slide-audio-file-input' in form.text
        assert "Audio Picker" not in form.text
        assert 'media-browser-flashcard_1234abcd-slide-audio' not in form.text

    client.close()


def test_image_field_uses_direct_upload_ui(tmp_path):
    lessons_dir = tmp_path / "lessons"
    backups_dir = tmp_path / "backups"
    groups_file = tmp_path / "groups.json"
    lessons_dir.mkdir()
    backups_dir.mkdir()
    groups_file.write_text(Path("app/content/groups.json").read_text(encoding="utf-8"), encoding="utf-8")
    lesson = _lesson_payload()
    lesson["blocks"]["07"]["slides"] = [
        {
            "slide_id": "07-01",
            "block_id": "07",
            "slide_title": "Read & Respond",
            "view_type": "read_respond",
            "content_payload": {"text_content": "I sat.", "image": "/static/images/readers/i_sat.png"},
            "teacher_cue": "Read the sentence.",
            "expected_response": "",
            "correction_move": "",
            "observation_note": "",
            "korean_interference_flag": None,
            "markable": True,
            "marking_options": ["secure", "shaky", "missed"],
            "next_action": "manual_next",
            "teacher_prompts": [{"text": "Who sat?", "audio_url": None}],
        }
    ]
    (lessons_dir / "G1-L99.json").write_text(json.dumps(lesson), encoding="utf-8")

    app = FastAPI()
    app.include_router(authoring_router)
    client = TestClient(app)
    with patch("app.services.lesson_authoring_service.LESSONS_DIR", lessons_dir), \
         patch("app.services.lesson_service.LESSONS_DIR", lessons_dir), \
         patch("app.services.lesson_backup_service.LESSON_BACKUPS_DIR", backups_dir), \
         patch("app.services.group_service.GROUPS_FILE", groups_file):
        form = client.get("/authoring/lessons/G1-L99/blocks/07/slides/07-01")
        assert form.status_code == 200
        assert "Browse Image" not in form.text
        assert "Replace Image" in form.text
        assert 'data-image-upload-input="image"' in form.text

    client.close()


def test_drag_letter_form_uses_single_build_units_input(tmp_path):
    lessons_dir = tmp_path / "lessons"
    backups_dir = tmp_path / "backups"
    groups_file = tmp_path / "groups.json"
    lessons_dir.mkdir()
    backups_dir.mkdir()
    groups_file.write_text(Path("app/content/groups.json").read_text(encoding="utf-8"), encoding="utf-8")
    lesson = _lesson_payload()
    lesson["blocks"]["05"]["slides"] = [
        {
            "slide_id": "05-01",
            "block_id": "05",
            "slide_title": "Build the Word",
            "view_type": "drag_letter",
            "content_payload": {
                "target_word": "back",
                "target_letters": ["b", "a", "ck"],
                "slots": ["b", "a", "ck"],
                "draggable_letters": ["b", "a", "ck"],
            },
            "teacher_cue": "Build back.",
            "expected_response": "",
            "correction_move": "",
            "observation_note": "",
            "korean_interference_flag": None,
            "markable": True,
            "marking_options": ["secure", "shaky", "missed"],
            "next_action": "manual_next",
        }
    ]
    (lessons_dir / "G1-L99.json").write_text(json.dumps(lesson), encoding="utf-8")

    app = FastAPI()
    app.include_router(authoring_router)
    client = TestClient(app)
    with patch("app.services.lesson_authoring_service.LESSONS_DIR", lessons_dir), \
         patch("app.services.lesson_service.LESSONS_DIR", lessons_dir), \
         patch("app.services.lesson_backup_service.LESSON_BACKUPS_DIR", backups_dir), \
         patch("app.services.group_service.GROUPS_FILE", groups_file):
        form = client.get("/authoring/lessons/G1-L99/blocks/05/slides/05-01")
        assert form.status_code == 200
        assert "Build Units" in form.text
        assert "b | a | ck" in form.text
        assert "Target Word" not in form.text
        assert "Letter Tiles" not in form.text

    client.close()


def test_drag_letter_save_normalizes_units_from_target_word(tmp_path):
    lessons_dir = tmp_path / "lessons"
    backups_dir = tmp_path / "backups"
    groups_file = tmp_path / "groups.json"
    lessons_dir.mkdir()
    backups_dir.mkdir()
    groups_file.write_text(Path("app/content/groups.json").read_text(encoding="utf-8"), encoding="utf-8")
    lesson = _lesson_payload()
    lesson["blocks"]["05"]["slides"] = [
        {
            "slide_id": "05-01",
            "block_id": "05",
            "slide_title": "Build the Word",
            "view_type": "drag_letter",
            "content_payload": {
                "target_word": "pink",
                "target_letters": ["a", "t"],
                "slots": ["a", "t"],
                "draggable_letters": ["a", "t"],
            },
            "teacher_cue": "Build pink.",
            "expected_response": "",
            "correction_move": "",
            "observation_note": "",
            "korean_interference_flag": None,
            "markable": True,
            "marking_options": ["secure", "shaky", "missed"],
            "next_action": "manual_next",
        }
    ]
    lesson_path = lessons_dir / "G1-L99.json"
    lesson_path.write_text(json.dumps(lesson), encoding="utf-8")

    app = FastAPI()
    app.include_router(authoring_router)
    client = TestClient(app)
    with patch("app.services.lesson_authoring_service.LESSONS_DIR", lessons_dir), \
         patch("app.services.lesson_service.LESSONS_DIR", lessons_dir), \
         patch("app.services.lesson_backup_service.LESSON_BACKUPS_DIR", backups_dir), \
         patch("app.services.group_service.GROUPS_FILE", groups_file):
        form = client.get("/authoring/lessons/G1-L99/blocks/05/slides/05-01")
        assert form.status_code == 200
        assert "pink" in form.text
        assert "value=\"a | t\"" not in form.text

        updated = client.post(
            "/authoring/lessons/G1-L99/blocks/05/slides/05-01",
            data={
                "slide_title": "Build the Word",
                "teacher_cue": "Build pink.",
                "payload__target_word": "pink",
                "payload__draggable_letters": "p, i, n, k",
                "payload__target_letters": "p, i, n, k",
                "payload__slots": "p, i, n, k",
            },
        )
        assert updated.status_code == 200

        stored = json.loads(lesson_path.read_text(encoding="utf-8"))
        payload = stored["blocks"]["05"]["slides"][0]["content_payload"]
        assert payload["target_word"] == "pink"
        assert payload["target_letters"] == ["p", "i", "n", "k"]
        assert payload["slots"] == ["p", "i", "n", "k"]
        assert payload["draggable_letters"] == ["p", "i", "n", "k"]

    client.close()


def test_spell_word_form_uses_compact_word_and_letter_pool_fields(tmp_path):
    lessons_dir = tmp_path / "lessons"
    backups_dir = tmp_path / "backups"
    groups_file = tmp_path / "groups.json"
    lessons_dir.mkdir()
    backups_dir.mkdir()
    groups_file.write_text(Path("app/content/groups.json").read_text(encoding="utf-8"), encoding="utf-8")
    lesson = _lesson_payload()
    lesson["blocks"]["05"]["slides"] = [
        {
            "slide_id": "05-02",
            "block_id": "05",
            "slide_title": "Spell the Word",
            "view_type": "spell_word",
            "content_payload": {
                "correct_word": "pink",
                "letter_pool": ["p", "i", "n", "k"],
            },
            "teacher_cue": "Play the word and let students spell it.",
            "expected_response": "",
            "correction_move": "",
            "observation_note": "",
            "korean_interference_flag": None,
            "markable": True,
            "marking_options": ["secure", "shaky", "missed"],
            "next_action": "manual_next",
        }
    ]
    (lessons_dir / "G1-L99.json").write_text(json.dumps(lesson), encoding="utf-8")

    app = FastAPI()
    app.include_router(authoring_router)
    client = TestClient(app)
    with patch("app.services.lesson_authoring_service.LESSONS_DIR", lessons_dir), \
         patch("app.services.lesson_service.LESSONS_DIR", lessons_dir), \
         patch("app.services.lesson_backup_service.LESSON_BACKUPS_DIR", backups_dir), \
         patch("app.services.group_service.GROUPS_FILE", groups_file):
        form = client.get("/authoring/lessons/G1-L99/blocks/05/slides/05-02")
        assert form.status_code == 200
        assert "Correct Word" in form.text
        assert "Letter Pool" in form.text
        assert "pink" in form.text
        assert "p | i | n | k" in form.text

    client.close()


def test_read_respond_uses_teacher_prompts_for_comprehension(tmp_path):
    lessons_dir = tmp_path / "lessons"
    backups_dir = tmp_path / "backups"
    groups_file = tmp_path / "groups.json"
    lessons_dir.mkdir()
    backups_dir.mkdir()
    groups_file.write_text(Path("app/content/groups.json").read_text(encoding="utf-8"), encoding="utf-8")
    lesson = _lesson_payload()
    lesson["blocks"]["07"]["slides"] = [
        {
            "slide_id": "07-01",
            "block_id": "07",
            "slide_title": "Read & Respond",
            "view_type": "read_respond",
            "content_payload": {
                "text_content": "I sat.",
                "comprehension_prompt": "Who sat?",
                "display_mode": "sentence",
            },
            "teacher_cue": "Read the sentence.",
            "expected_response": "",
            "correction_move": "",
            "observation_note": "",
            "korean_interference_flag": None,
            "markable": True,
            "marking_options": ["secure", "shaky", "missed"],
            "next_action": "manual_next",
            "teacher_prompts": [],
        }
    ]
    lesson_path = lessons_dir / "G1-L99.json"
    lesson_path.write_text(json.dumps(lesson), encoding="utf-8")

    app = FastAPI()
    app.include_router(authoring_router)
    client = TestClient(app)
    with patch("app.services.lesson_authoring_service.LESSONS_DIR", lessons_dir), \
         patch("app.services.lesson_service.LESSONS_DIR", lessons_dir), \
         patch("app.services.lesson_backup_service.LESSON_BACKUPS_DIR", backups_dir), \
         patch("app.services.group_service.GROUPS_FILE", groups_file):
        form = client.get("/authoring/lessons/G1-L99/blocks/07/slides/07-01")
        assert form.status_code == 200
        assert "Comprehension Question" not in form.text
        assert "Comprehension Questions" not in form.text
        assert "Who sat?" in form.text

        invalid = client.post(
            "/authoring/lessons/G1-L99/blocks/07/slides/07-01",
            data={
                "slide_title": "Read & Respond",
                "teacher_cue": "Read the sentence.",
                "payload__text_content": "I sat.",
                "teacher_prompts": "[]",
            },
        )
        assert invalid.status_code == 400

        updated = client.post(
            "/authoring/lessons/G1-L99/blocks/07/slides/07-01",
            data={
                "slide_title": "Read & Respond",
                "teacher_cue": "Read the sentence.",
                "payload__text_content": "I sat.",
                "teacher_prompts": json.dumps([{"text": "Who sat now?", "audio_url": None}]),
            },
        )
        assert updated.status_code == 200

        stored = json.loads(lesson_path.read_text(encoding="utf-8"))
        slide = stored["blocks"]["07"]["slides"][0]
        assert slide["teacher_prompts"][0]["text"] == "Who sat now?"
        assert slide["content_payload"]["comprehension_prompt"] == "Who sat now?"

    client.close()
