import os
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.staticfiles import StaticFiles

# Force SQLite before any app module imports app.db / app.models.
os.environ["DATABASE_URL"] = "sqlite:////tmp/luminos_engine_test_bootstrap.db"

from tests.support import SqliteTestSession, seed_attempt, seed_lesson
from app.db import get_db
from app.routers.lesson import router as lesson_router
from app.services.kokoro_tts_service import KokoroTtsError


class LessonRouteTests(unittest.TestCase):
    def setUp(self):
        self.session = SqliteTestSession()
        self.db = self.session.db
        seed_lesson(self.db, "G1-L1")
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

    def test_tts_prompt_route_returns_cached_audio_url(self):
        with patch("app.routers.lesson.ensure_tts_audio", return_value={
            "text": "Tom, please read.",
            "audio_url": "/tts-cache/fake1234.wav",
        }):
            response = self.client.post("/lesson/tts/prompt", json={"text": "Tom, please read."})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"text": "Tom, please read.", "audio_url": "/tts-cache/fake1234.wav"},
        )

    def test_tts_prompt_route_returns_503_on_tts_failure(self):
        with patch("app.routers.lesson.ensure_tts_audio", side_effect=KokoroTtsError("tts unavailable")):
            response = self.client.post("/lesson/tts/prompt", json={"text": "Tom, please read."})

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "tts unavailable")

    def test_oral_check_routes_block_lesson_completion_until_resolved(self):
        started = self.client.post(
            "/lesson/G1-L1/oral-check/session/start",
            json={
                "attempt_id": str(self.attempt.attempt_id),
                "lesson_id": "G1-L1",
                "slide_id": "07-01",
                "block_id": "07",
                "roster": ["Tom", "James"],
                "participation_mode": "full_roster",
                "text_length_mode": "normal",
                "required_evidence_count": 1,
            },
        )
        self.assertEqual(started.status_code, 200)
        started_data = started.json()

        blocked = self.client.post(
            "/lesson/G1-L1/complete",
            json={"attempt_id": str(self.attempt.attempt_id)},
        )
        self.assertEqual(blocked.status_code, 400)
        self.assertIn("oral check unresolved", blocked.json()["detail"])

        first_mark = self.client.post(
            "/lesson/G1-L1/oral-check/assignment/mark",
            json={
                "session_id": started_data["session_id"],
                "assignment_id": started_data["active_assignment_id"],
                "status": "secure",
            },
        )
        self.assertEqual(first_mark.status_code, 200)

        session = self.client.get(
            f"/lesson/G1-L1/oral-check/session/{self.attempt.attempt_id}/07-01"
        )
        self.assertEqual(session.status_code, 200)
        session_data = session.json()

        second_mark = self.client.post(
            "/lesson/G1-L1/oral-check/assignment/mark",
            json={
                "session_id": session_data["session_id"],
                "assignment_id": session_data["active_assignment_id"],
                "status": "secure",
            },
        )
        self.assertEqual(second_mark.status_code, 200)
        self.assertEqual(second_mark.json()["session_status"], "complete")

        complete_session = self.client.post(
            "/lesson/G1-L1/oral-check/session/complete",
            json={"session_id": session_data["session_id"]},
        )
        self.assertEqual(complete_session.status_code, 200)

        complete_lesson = self.client.post(
            "/lesson/G1-L1/complete",
            json={"attempt_id": str(self.attempt.attempt_id)},
        )
        self.assertEqual(complete_lesson.status_code, 200)
        self.assertEqual(complete_lesson.json(), {"ok": True})

    def test_get_lesson_fails_open_when_dynamic_review_lookup_breaks(self):
        with patch("app.routers.lesson.get_class_review_recommendations", side_effect=RuntimeError("boom")):
            response = self.client.get("/lesson/G1-L1?class_id=class-1")

        self.assertEqual(response.status_code, 200)
        self.assertIn("lesson-shell", response.text)
