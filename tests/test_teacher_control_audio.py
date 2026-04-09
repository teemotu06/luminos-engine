import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:////tmp/luminos_engine_test_teacher_control_audio.db"
os.environ["LUMINOS_AUTH_REQUIRED"] = "false"

from app.db import get_db
from app.routers.lesson import router as lesson_router
from app.services.lesson_skeleton_service import generate_skeleton
from app.services.lesson_service import parse_lesson
from tests.support import SqliteTestSession, seed_attempt, seed_class_with_students, seed_lesson


class TeacherControlAudioTests(unittest.TestCase):
    def setUp(self):
        self.session = SqliteTestSession()
        self.db = self.session.db
        seed_lesson(self.db, "G9-L99")
        seed_class_with_students(self.db, class_id="class-1", students=["Tom"])
        self.attempt = seed_attempt(self.db, "G9-L99", class_id="class-1")

        self.app = FastAPI()
        self.app.mount("/static", StaticFiles(directory="app/static"), name="static")
        self.app.include_router(lesson_router)

        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        self.app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.session.close()

    def test_teacher_page_exports_slide_audio_and_teacher_prompts(self):
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmpdir:
            lessons_dir = Path(tmpdir)
            lesson = generate_skeleton("G9", 99, "Audio Lesson", "s")
            lesson["json_path"] = "app/content/lessons/G9-L99.json"
            lesson["blocks"]["03"]["slides"] = [
                {
                    "slide_id": "03-01",
                    "block_id": "03",
                    "slide_title": "Introduce s",
                    "view_type": "flashcard",
                    "content_payload": {"front_text": "s", "back_text": "/s/", "audio": "/static/payload-s.mp3"},
                    "teacher_cue": "Teach the sound.",
                    "expected_response": "Students say /s/.",
                    "correction_move": "Model and repeat.",
                    "observation_note": "",
                    "slide_audio_url": "/static/slide-s.mp3",
                    "teacher_prompts": [{"text": "Make a snake sound.", "audio_url": "/static/prompt-s.mp3"}],
                    "korean_interference_flag": None,
                    "markable": True,
                    "marking_options": ["secure", "shaky", "missed"],
                    "next_action": "manual_next",
                },
                {
                    "slide_id": "03-02",
                    "block_id": "03",
                    "slide_title": "Introduce m",
                    "view_type": "flashcard",
                    "content_payload": {"front_text": "m", "back_text": "/m/", "audio": "/static/payload-m.mp3"},
                    "teacher_cue": "Teach the sound.",
                    "expected_response": "Students say /m/.",
                    "correction_move": "Model and repeat.",
                    "observation_note": "",
                    "korean_interference_flag": None,
                    "markable": True,
                    "marking_options": ["secure", "shaky", "missed"],
                    "next_action": "manual_next",
                },
            ]
            (lessons_dir / "G9-L99.json").write_text(json.dumps(lesson), encoding="utf-8")

            def _load_temp_lesson(_lesson_id: str):
                return parse_lesson(json.loads((lessons_dir / "G9-L99.json").read_text(encoding="utf-8")))

            with patch("app.services.lesson_navigation.load_lesson", side_effect=_load_temp_lesson):
                response = self.client.get(
                    f"/lesson/G9-L99/teacher?attempt_id={self.attempt.attempt_id}"
                )

        self.assertEqual(response.status_code, 200)
        self.assertIn("slideTeacherPrompts", response.text)
        self.assertIn("/static/slide-s.mp3", response.text)
        self.assertIn("/static/prompt-s.mp3", response.text)
        self.assertIn("/static/payload-m.mp3", response.text)

    def test_audio_priority_order_is_present_in_teacher_js(self):
        source = Path("app/static/lesson_teacher.js").read_text(encoding="utf-8")
        self.assertIn('"audio_url"', source)
        self.assertIn('"audio_prompt"', source)
        self.assertIn('"audio_support"', source)
        self.assertIn('"blend_audio"', source)
        self.assertIn('"word_audio"', source)


if __name__ == "__main__":
    unittest.main()
