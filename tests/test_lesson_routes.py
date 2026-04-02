import os
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.staticfiles import StaticFiles

# Force SQLite before any app module imports app.db / app.models.
os.environ["DATABASE_URL"] = "sqlite:////tmp/luminos_engine_test_bootstrap.db"
os.environ["LUMINOS_AUTH_REQUIRED"] = "false"

from tests.support import SqliteTestSession, seed_attempt, seed_class_with_students, seed_lesson
from app.db import get_db
from app.routers.lesson import router as lesson_router
from app.services.kokoro_tts_service import KokoroTtsError


class LessonRouteTests(unittest.TestCase):
    def setUp(self):
        self.session = SqliteTestSession()
        self.db = self.session.db
        seed_lesson(self.db, "G1-L1")
        seed_lesson(self.db, "G1-L2")
        seed_class_with_students(self.db, class_id="class-1", students=["Tom", "James"])
        self.attempt = seed_attempt(self.db, "G1-L1", class_id="class-1")
        self.attempt_g1_l2 = seed_attempt(self.db, "G1-L2", class_id="class-1")
        self.command_tts_patcher = patch(
            "app.services.command_state_service.ensure_tts_audio",
            return_value={"audio_url": "/tts-cache/test.wav"},
        )
        self.command_tts_patcher.start()

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
        self.command_tts_patcher.stop()
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
        self.assertEqual(complete_lesson.json(), {"ok": True, "attempt_version": 2})

    def test_slide_mark_summary_is_deferred_until_lesson_completion(self):
        marked = self.client.post(
            "/lesson/G1-L1/mark",
            json={
                "attempt_id": str(self.attempt.attempt_id),
                "lesson_id": "G1-L1",
                "slide_id": "03-01",
                "block_id": "03",
                "status": "secure",
                "error_tags": [],
                "korean_transfer": False,
                "completed": False,
                "item_results": [],
            },
        )

        self.assertEqual(marked.status_code, 200)
        self.assertFalse(marked.json()["summary_finalized"])
        self.assertEqual(marked.json()["slide_version"], 1)
        self.assertEqual(marked.json()["attempt_version"], 2)

        self.db.refresh(self.attempt)
        self.assertEqual(self.attempt.mastery_status, "shaky")
        self.assertEqual(self.attempt.next_recommendation, "move_on")
        self.assertEqual(self.attempt.version, 2)

        completed = self.client.post(
            "/lesson/G1-L1/complete",
            json={"attempt_id": str(self.attempt.attempt_id), "expected_attempt_version": 2},
        )

        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.json()["attempt_version"], 3)
        self.db.refresh(self.attempt)
        self.assertTrue(self.attempt.completed)
        self.assertEqual(self.attempt.mastery_status, "secure")
        self.assertEqual(self.attempt.next_recommendation, "move_on")
        self.assertEqual(self.attempt.version, 3)

    def test_slide_mark_rejects_stale_version(self):
        first = self.client.post(
            "/lesson/G1-L1/mark",
            json={
                "attempt_id": str(self.attempt.attempt_id),
                "lesson_id": "G1-L1",
                "slide_id": "03-01",
                "block_id": "03",
                "status": "secure",
                "error_tags": [],
                "korean_transfer": False,
                "expected_slide_version": None,
                "item_results": [],
            },
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["slide_version"], 1)

        second = self.client.post(
            "/lesson/G1-L1/mark",
            json={
                "attempt_id": str(self.attempt.attempt_id),
                "lesson_id": "G1-L1",
                "slide_id": "03-01",
                "block_id": "03",
                "status": "shaky",
                "error_tags": [],
                "korean_transfer": False,
                "expected_slide_version": 1,
                "item_results": [],
            },
        )
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["slide_version"], 2)

        stale = self.client.post(
            "/lesson/G1-L1/mark",
            json={
                "attempt_id": str(self.attempt.attempt_id),
                "lesson_id": "G1-L1",
                "slide_id": "03-01",
                "block_id": "03",
                "status": "missed",
                "error_tags": [],
                "korean_transfer": False,
                "expected_slide_version": 1,
                "item_results": [],
            },
        )
        self.assertEqual(stale.status_code, 409)
        self.assertIn("expected version 1, found 2", stale.json()["detail"])

    def test_complete_lesson_rejects_stale_attempt_version(self):
        marked = self.client.post(
            "/lesson/G1-L1/mark",
            json={
                "attempt_id": str(self.attempt.attempt_id),
                "lesson_id": "G1-L1",
                "slide_id": "03-01",
                "block_id": "03",
                "status": "secure",
                "error_tags": [],
                "korean_transfer": False,
                "item_results": [],
            },
        )
        self.assertEqual(marked.status_code, 200)

        stale_complete = self.client.post(
            "/lesson/G1-L1/complete",
            json={"attempt_id": str(self.attempt.attempt_id), "expected_attempt_version": 1},
        )
        self.assertEqual(stale_complete.status_code, 409)
        self.assertIn("expected version 1, found 2", stale_complete.json()["detail"])

    def test_get_lesson_fails_open_when_dynamic_review_lookup_breaks(self):
        with patch("app.routers.lesson.get_class_review_recommendations", side_effect=RuntimeError("boom")):
            response = self.client.get("/lesson/G1-L1?class_id=class-1")

        self.assertEqual(response.status_code, 200)
        self.assertIn("lesson-shell", response.text)

    def test_get_teacher_shell_renders(self):
        response = self.client.get(
            f"/lesson/G1-L1/teacher?class_id=class-1&attempt_id={self.attempt.attempt_id}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Teacher Control", response.text)
        self.assertIn("teacher-shell", response.text)

    def test_teacher_shell_ignores_invalid_placeholder_ids(self):
        response = self.client.get(
            "/lesson/G1-L1/teacher?class_id=YOUR_CLASS_ID&attempt_id=YOUR_ATTEMPT_ID"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Teacher Control", response.text)

    def test_get_board_shell_renders(self):
        response = self.client.get(
            f"/lesson/G1-L1/board?class_id=class-1&attempt_id={self.attempt.attempt_id}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("board-shell", response.text)
        self.assertIn("board-command__surface", response.text)

    def test_board_shell_ignores_invalid_placeholder_ids(self):
        response = self.client.get(
            "/lesson/G1-L1/board?class_id=YOUR_CLASS_ID&attempt_id=YOUR_ATTEMPT_ID"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("board-shell", response.text)

    def test_command_state_route_returns_generic_slide_runtime(self):
        response = self.client.get(
            f"/lesson/G1-L1/command-state/{self.attempt.attempt_id}?slide_id=01-01"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["slide_id"], "01-01")
        self.assertEqual(data["current_state"], "transition")
        self.assertEqual(data["session_mode"], "legacy")
        self.assertEqual(data["audio_url"], "/tts-cache/test.wav")
        self.assertIn("replay", data["teacher_controls"])

    def test_command_state_route_returns_oral_runtime_and_supports_replay_and_mark(self):
        started = self.client.get(
            f"/lesson/G1-L1/command-state/{self.attempt.attempt_id}?slide_id=07-01"
        )
        self.assertEqual(started.status_code, 200)
        started_data = started.json()
        self.assertEqual(started_data["session_mode"], "oral_check")
        self.assertEqual(started_data["current_state"], "individual_check")
        first_audio_event_id = started_data["audio_event_id"]

        replayed = self.client.post(
            f"/lesson/G1-L1/command-state/{self.attempt.attempt_id}/advance",
            json={"slide_id": "07-01", "action": "replay"},
        )
        self.assertEqual(replayed.status_code, 200)
        self.assertEqual(replayed.json()["audio_event_id"], first_audio_event_id + 1)

        marked = self.client.post(
            f"/lesson/G1-L1/command-state/{self.attempt.attempt_id}/advance",
            json={"slide_id": "07-01", "action": "mark", "status": "secure"},
        )
        self.assertEqual(marked.status_code, 200)
        marked_data = marked.json()
        self.assertEqual(marked_data["session_mode"], "oral_check")
        self.assertIn(marked_data["current_state"], {"individual_check", "complete"})

    def test_authored_runtime_slide_advances_through_defined_states(self):
        started = self.client.get(
            f"/lesson/G1-L1/command-state/{self.attempt.attempt_id}?slide_id=03-01"
        )
        self.assertEqual(started.status_code, 200)
        self.assertEqual(started.json()["current_state"], "transition")
        self.assertEqual(started.json()["teacher_controls"], ["replay", "force_advance"])
        self.assertEqual(started.json()["prompt_text"], "Look at the letter. Listen.")
        self.assertEqual(started.json()["teacher_prompt_text"], "Look at the letter. Listen.")

        model = self.client.post(
            f"/lesson/G1-L1/command-state/{self.attempt.attempt_id}/advance",
            json={"slide_id": "03-01", "action": "force_advance"},
        )
        self.assertEqual(model.status_code, 200)
        self.assertEqual(model.json()["current_state"], "model")

        choral = self.client.post(
            f"/lesson/G1-L1/command-state/{self.attempt.attempt_id}/advance",
            json={"slide_id": "03-01", "action": "force_advance"},
        )
        self.assertEqual(choral.status_code, 200)
        self.assertEqual(choral.json()["current_state"], "choral")
        self.assertIn("mark_class", choral.json()["teacher_controls"])

        complete = self.client.post(
            f"/lesson/G1-L1/command-state/{self.attempt.attempt_id}/advance",
            json={"slide_id": "03-01", "action": "mark_class", "status": "secure"},
        )
        self.assertEqual(complete.status_code, 200)
        self.assertEqual(complete.json()["current_state"], "complete")

    def test_teacher_prompt_can_differ_from_board_prompt(self):
        response = self.client.get(
            f"/lesson/G1-L1/command-state/{self.attempt.attempt_id}?slide_id=04-03"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["prompt_text"], "Look. New word.")
        self.assertEqual(data["teacher_prompt_text"], "Introduce sat. Keep it oral first, then reveal print.")

    def test_default_drag_letter_runtime_template_progresses_without_authored_runtime(self):
        started = self.client.get(
            f"/lesson/G1-L1/command-state/{self.attempt.attempt_id}?slide_id=05-02"
        )

        self.assertEqual(started.status_code, 200)
        started_data = started.json()
        self.assertEqual(started_data["current_state"], "transition")
        self.assertEqual(started_data["prompt_text"], "Get ready to build at.")
        self.assertEqual(started_data["teacher_prompt_text"], "Build at left to right.")

        build = self.client.post(
            f"/lesson/G1-L1/command-state/{self.attempt.attempt_id}/advance",
            json={"slide_id": "05-02", "action": "force_advance"},
        )
        self.assertEqual(build.status_code, 200)
        self.assertEqual(build.json()["current_state"], "build")

        partner = self.client.post(
            f"/lesson/G1-L1/command-state/{self.attempt.attempt_id}/advance",
            json={"slide_id": "05-02", "action": "force_advance"},
        )
        self.assertEqual(partner.status_code, 200)
        self.assertEqual(partner.json()["current_state"], "partner_practice")
        self.assertEqual(partner.json()["state_timeout_ms"], 12000)
        self.assertIn("pause", partner.json()["teacher_controls"])

        check = self.client.post(
            f"/lesson/G1-L1/command-state/{self.attempt.attempt_id}/advance",
            json={"slide_id": "05-02", "action": "force_advance"},
        )
        self.assertEqual(check.status_code, 200)
        self.assertEqual(check.json()["current_state"], "check")
        self.assertIn("mark_class", check.json()["teacher_controls"])

    def test_default_writing_runtime_template_includes_timed_write_state(self):
        started = self.client.get(
            f"/lesson/G1-L1/command-state/{self.attempt.attempt_id}?slide_id=08-02"
        )

        self.assertEqual(started.status_code, 200)
        self.assertEqual(started.json()["current_state"], "transition")

        dictate = self.client.post(
            f"/lesson/G1-L1/command-state/{self.attempt.attempt_id}/advance",
            json={"slide_id": "08-02", "action": "force_advance"},
        )
        self.assertEqual(dictate.status_code, 200)
        self.assertEqual(dictate.json()["current_state"], "dictate")

        write = self.client.post(
            f"/lesson/G1-L1/command-state/{self.attempt.attempt_id}/advance",
            json={"slide_id": "08-02", "action": "force_advance"},
        )
        self.assertEqual(write.status_code, 200)
        self.assertEqual(write.json()["current_state"], "write")
        self.assertEqual(write.json()["state_timeout_ms"], 15000)
        self.assertIn("pause", write.json()["teacher_controls"])

    def test_active_slide_route_updates_attempt_and_default_command_state(self):
        set_active = self.client.post(
            f"/lesson/G1-L1/command-state/{self.attempt.attempt_id}/active-slide",
            json={"slide_id": "07-01"},
        )
        self.assertEqual(set_active.status_code, 200)
        self.assertEqual(set_active.json(), {"ok": True, "slide_id": "07-01"})

        response = self.client.get(
            f"/lesson/G1-L1/command-state/{self.attempt.attempt_id}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["slide_id"], "07-01")

    def test_g1_l2_authored_runtime_progresses_on_second_migrated_lesson(self):
        started = self.client.get(
            f"/lesson/G1-L2/command-state/{self.attempt_g1_l2.attempt_id}?slide_id=05-01"
        )

        self.assertEqual(started.status_code, 200)
        started_data = started.json()
        self.assertEqual(started_data["current_state"], "transition")
        self.assertEqual(started_data["prompt_text"], "Get ready to write.")
        self.assertEqual(
            started_data["teacher_prompt_text"],
            "Prepare students to encode sit.",
        )

        practice = self.client.post(
            f"/lesson/G1-L2/command-state/{self.attempt_g1_l2.attempt_id}/advance",
            json={"slide_id": "05-01", "action": "force_advance"},
        )
        self.assertEqual(practice.status_code, 200)
        practice_data = practice.json()
        self.assertEqual(practice_data["current_state"], "dictate")
        self.assertEqual(practice_data["prompt_text"], "Write sit.")

        write = self.client.post(
            f"/lesson/G1-L2/command-state/{self.attempt_g1_l2.attempt_id}/advance",
            json={"slide_id": "05-01", "action": "force_advance"},
        )
        self.assertEqual(write.status_code, 200)
        write_data = write.json()
        self.assertEqual(write_data["current_state"], "write")
        self.assertEqual(write_data["state_timeout_ms"], 15000)
        self.assertIn("pause", write_data["teacher_controls"])
