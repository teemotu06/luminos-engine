import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

os.environ["DATABASE_URL"] = "sqlite:////tmp/luminos_engine_test_teacher_prompts.db"
os.environ["LUMINOS_AUTH_REQUIRED"] = "false"

from app.routers.authoring import router as authoring_router
from app.services.block_registry import BLOCK_REGISTRY
from app.schemas.slide import Slide
from app.schemas.slide_payloads import TeacherPrompt
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_teacher_prompt_model_validates():
    prompt = TeacherPrompt(text="Read the word.", audio_url="/static/uploads/audio/read.mp3")
    assert prompt.text == "Read the word."


def test_teacher_prompt_rejects_empty_text():
    with pytest.raises(Exception):
        TeacherPrompt(text="")


def test_slide_model_accepts_teacher_prompts_and_slide_audio_url():
    slide = Slide(
        slide_id="flashcard_1",
        block_id="01",
        slide_title="Flashcard",
        view_type="flashcard",
        content_payload={"front_text": "s", "back_text": "/s/"},
        teacher_cue="Teach it",
        expected_response="Students say /s/.",
        correction_move="Model again.",
        observation_note=None,
        slide_audio_url="/static/uploads/audio/s.mp3",
        teacher_prompts=[{"text": "Make a snake sound.", "audio_url": "/static/uploads/audio/snake.mp3"}],
        korean_interference_flag=None,
        markable=True,
        marking_options=["secure", "shaky", "missed"],
        next_action="manual_next",
    )
    assert slide.slide_audio_url == "/static/uploads/audio/s.mp3"
    assert len(slide.teacher_prompts) == 1


def test_slide_model_defaults_are_backward_compatible():
    slide = Slide(
        slide_id="flashcard_1",
        block_id="01",
        slide_title="Flashcard",
        view_type="flashcard",
        content_payload={"front_text": "s", "back_text": "/s/"},
        teacher_cue="Teach it",
        expected_response="Students say /s/.",
        correction_move="Model again.",
        observation_note=None,
        korean_interference_flag=None,
        markable=True,
        marking_options=["secure", "shaky", "missed"],
        next_action="manual_next",
    )
    assert slide.teacher_prompts == []
    assert slide.slide_audio_url is None


def test_authoring_add_slide_initializes_prompt_fields(tmp_path):
    lessons_dir = tmp_path / "lessons"
    backups_dir = tmp_path / "backups"
    groups_file = tmp_path / "groups.json"
    lessons_dir.mkdir()
    backups_dir.mkdir()
    groups_file.write_text(Path("app/content/groups.json").read_text(encoding="utf-8"), encoding="utf-8")
    lesson_path = lessons_dir / "G1-L95.json"
    lesson_path.write_text(json.dumps({
        "lesson_id": "G1-L95",
        "unit_id": "G1",
        "target_pattern": "s",
        "title": "Prompt Test",
        "new_units": [],
        "new_sight_words": [],
        "korean_interference_active": [],
        "content_pack_status": "draft",
        "blocks": {
            definition.block_id: {"block_id": definition.block_id, "label": definition.label, "slides": []}
            for definition in BLOCK_REGISTRY
        }
    }), encoding="utf-8")

    app = FastAPI()
    app.include_router(authoring_router)
    client = TestClient(app)
    with patch("app.services.lesson_authoring_service.LESSONS_DIR", lessons_dir), \
         patch("app.services.lesson_service.LESSONS_DIR", lessons_dir), \
         patch("app.services.lesson_backup_service.LESSON_BACKUPS_DIR", backups_dir), \
         patch("app.services.group_service.GROUPS_FILE", groups_file):
        response = client.post("/authoring/lessons/G1-L95/blocks/01/slides/add", data={"view_type": "flashcard"})
        assert response.status_code == 200
        data = json.loads(lesson_path.read_text(encoding="utf-8"))
        slide = data["blocks"]["01"]["slides"][0]
        assert slide["teacher_prompts"] == []
        assert slide["slide_audio_url"] is None
    client.close()
