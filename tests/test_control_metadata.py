import os
import unittest

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:////tmp/luminos_engine_test_control_metadata.db"
os.environ["LUMINOS_AUTH_REQUIRED"] = "false"

from app.db import get_db
from app.routers.lesson import router as lesson_router
from app.slide_types import registry
from tests.support import SqliteTestSession, seed_attempt, seed_class_with_students, seed_lesson


class ControlMetadataTests(unittest.TestCase):
    def setUp(self):
        self.session = SqliteTestSession()
        self.db = self.session.db
        seed_lesson(self.db, "G1-L1")
        seed_class_with_students(self.db, class_id="class-1", students=["Tom", "James"])
        self.attempt = seed_attempt(self.db, "G1-L1", class_id="class-1")

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

    def test_registry_control_actions_match_expected_types(self):
        self.assertEqual(registry.control_actions_for("flashcard"), ["reveal", "play_sound", "mark_students"])
        self.assertEqual(registry.control_actions_for("audio_prompt"), ["play_audio", "reveal_answer", "mark_students"])
        self.assertEqual(registry.control_actions_for("read_respond"), ["read_sentence", "reveal", "mark_students"])
        self.assertEqual(registry.control_actions_for("quick_check"), ["reveal", "mark_students"])

    def test_teacher_template_exports_labels_and_control_actions(self):
        response = self.client.get(
            f"/lesson/G1-L1/teacher?class_id=class-1&attempt_id={self.attempt.attempt_id}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("slideTypeLabels", response.text)
        self.assertIn("slideTypeControlActions", response.text)
        self.assertIn("slideTeacherPrompts", response.text)
        self.assertIn("slideAudioUrls", response.text)
        for type_key in registry.all_type_keys():
            self.assertIn(type_key, response.text)
        self.assertEqual(
            registry.all_labels(),
            {type_key: registry.label_for(type_key) for type_key in registry.all_type_keys()},
        )


if __name__ == "__main__":
    unittest.main()
