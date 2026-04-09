import os
import unittest

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:////tmp/luminos_engine_test_teacher_shell_session_sync.db"
os.environ["LUMINOS_AUTH_REQUIRED"] = "false"

from app.db import get_db
from app.routers.classes import router as classes_router
from app.routers.lesson import router as lesson_router
from tests.support import SqliteTestSession, seed_class_with_students, seed_lesson


class TeacherShellSessionSyncTests(unittest.TestCase):
    def setUp(self):
        self.session = SqliteTestSession()
        self.db = self.session.db
        seed_lesson(self.db, "G1-L1")
        seed_class_with_students(self.db, class_id="class-1", students=["Tom", "James"])

        self.app = FastAPI()
        self.app.mount("/static", StaticFiles(directory="app/static"), name="static")
        self.app.include_router(lesson_router)
        self.app.include_router(classes_router)

        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        self.app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(self.app)
        started = self.client.post("/classes/class-1/control/start", json={"lesson_id": "G1-L1"})
        self.assertEqual(started.status_code, 200)
        self.attempt_id = started.json()["attempt_id"]

    def tearDown(self):
        self.client.close()
        self.session.close()

    def test_teacher_shell_navigation_updates_session_state(self):
        initial_state = self.client.get("/classes/class-1/session-state")
        self.assertEqual(initial_state.status_code, 200)
        self.assertEqual(initial_state.json()["block_id"], "03")
        self.assertEqual(initial_state.json()["slide_id"], "phonemes_1179a7e9")

        response = self.client.post(
            f"/lesson/G1-L1/command-state/{self.attempt_id}/active-slide",
            json={"slide_id": "phonemes_1179a7e9"},
        )
        self.assertEqual(response.status_code, 200)

        session_state = self.client.get("/classes/class-1/session-state")
        self.assertEqual(session_state.status_code, 200)
        self.assertEqual(session_state.json()["slide_id"], "phonemes_1179a7e9")
        self.assertEqual(session_state.json()["block_id"], "03")

    def test_teacher_shell_can_navigate_to_long_generated_slide_id(self):
        move_to_other_slide = self.client.post(
            f"/lesson/G1-L1/command-state/{self.attempt_id}/active-slide",
            json={"slide_id": "04-01"},
        )
        self.assertEqual(move_to_other_slide.status_code, 200)

        response = self.client.post(
            f"/lesson/G1-L1/command-state/{self.attempt_id}/active-slide",
            json={"slide_id": "phonemes_1179a7e9"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["slide_id"], "phonemes_1179a7e9")

        session_state = self.client.get("/classes/class-1/session-state")
        self.assertEqual(session_state.status_code, 200)
        self.assertEqual(session_state.json()["slide_id"], "phonemes_1179a7e9")

    def test_board_prompt_does_not_fallback_to_teacher_cue_before_runtime_projection(self):
        state = self.client.get("/classes/class-1/session-state")
        self.assertEqual(state.status_code, 200)
        data = state.json()
        self.assertNotEqual(data["prompt"], "Say Ssssss like Snake")
        self.assertNotIn("teacher_cue", data)
        self.assertNotIn("expected_response", data)
        self.assertNotIn("correction_move", data)
        self.assertNotIn("teacher_prompts", data)

    def test_flashcard_board_session_does_not_invent_caption_without_board_prompt(self):
        set_slide = self.client.post(
            f"/lesson/G1-L1/command-state/{self.attempt_id}/active-slide",
            json={"slide_id": "04-01"},
        )
        self.assertEqual(set_slide.status_code, 200)
        state = self.client.get("/classes/class-1/session-state")
        self.assertEqual(state.status_code, 200)
        data = state.json()
        self.assertEqual(data["block_id"], "04")
        self.assertEqual(data["view_type"], "flashcard")
        self.assertEqual(data["prompt"], "")

    def test_flashcard_board_session_ignores_runtime_prompt_text(self):
        set_slide = self.client.post(
            f"/lesson/G1-L1/command-state/{self.attempt_id}/active-slide",
            json={"slide_id": "04-01"},
        )
        self.assertEqual(set_slide.status_code, 200)
        state = self.client.get("/classes/class-1/session-state")
        self.assertEqual(state.status_code, 200)
        data = state.json()
        self.assertEqual(data["view_type"], "flashcard")
        self.assertEqual(data["prompt"], "")

    def test_teacher_shell_reveal_updates_board_facing_session_projection(self):
        set_slide = self.client.post(
            f"/lesson/G1-L1/command-state/{self.attempt_id}/active-slide",
            json={"slide_id": "08-01"},
        )
        self.assertEqual(set_slide.status_code, 200)
        before = self.client.get("/classes/class-1/session-state").json()

        revealed = self.client.post(
            f"/lesson/G1-L1/command-state/{self.attempt_id}/advance",
            json={"slide_id": "08-01", "action": "force_advance"},
        )
        self.assertEqual(revealed.status_code, 200)

        after = self.client.get("/classes/class-1/session-state").json()
        self.assertEqual(after["slide_id"], "08-01")
        self.assertTrue(
            after["content"] != before["content"] or after["prompt"] != before["prompt"]
        )

    def test_teacher_shell_reveal_keeps_board_content_on_authored_slide(self):
        set_slide = self.client.post(
            f"/lesson/G1-L1/command-state/{self.attempt_id}/active-slide",
            json={"slide_id": "08-01"},
        )
        self.assertEqual(set_slide.status_code, 200)

        before = self.client.get("/classes/class-1/session-state").json()
        self.assertEqual(before["content"], "sat")

        first_advance = self.client.post(
            f"/lesson/G1-L1/command-state/{self.attempt_id}/advance",
            json={"slide_id": "08-01", "action": "force_advance"},
        )
        self.assertEqual(first_advance.status_code, 200)

        second_advance = self.client.post(
            f"/lesson/G1-L1/command-state/{self.attempt_id}/advance",
            json={"slide_id": "08-01", "action": "force_advance"},
        )
        self.assertEqual(second_advance.status_code, 200)

        after = self.client.get("/classes/class-1/session-state").json()
        self.assertEqual(after["slide_id"], "08-01")
        self.assertEqual(after["content"], "sat")
        self.assertNotEqual(after["content"], "Mark your class")

    def test_hide_answer_resets_reveal_state_for_board_projection(self):
        set_slide = self.client.post(
            f"/lesson/G1-L1/command-state/{self.attempt_id}/active-slide",
            json={"slide_id": "04-01"},
        )
        self.assertEqual(set_slide.status_code, 200)

        revealed = self.client.post(
            f"/lesson/G1-L1/command-state/{self.attempt_id}/advance",
            json={"slide_id": "04-01", "action": "force_advance"},
        )
        self.assertEqual(revealed.status_code, 200)

        revealed_state = self.client.get("/classes/class-1/session-state").json()
        self.assertTrue(revealed_state["revealed"])

        hidden = self.client.post(
            f"/lesson/G1-L1/command-state/{self.attempt_id}/advance",
            json={"slide_id": "04-01", "action": "hide_answer"},
        )
        self.assertEqual(hidden.status_code, 200)

        hidden_state = self.client.get("/classes/class-1/session-state").json()
        self.assertEqual(hidden_state["slide_id"], "04-01")
        self.assertFalse(hidden_state["revealed"])

    def test_teacher_shell_pause_updates_session_state(self):
        set_slide = self.client.post(
            f"/lesson/G1-L1/command-state/{self.attempt_id}/active-slide",
            json={"slide_id": "08-01"},
        )
        self.assertEqual(set_slide.status_code, 200)
        paused = self.client.post(
            f"/lesson/G1-L1/command-state/{self.attempt_id}/advance",
            json={"slide_id": "08-01", "action": "pause"},
        )
        self.assertEqual(paused.status_code, 200)

        paused_state = self.client.get("/classes/class-1/session-state")
        self.assertEqual(paused_state.status_code, 200)
        self.assertTrue(paused_state.json()["paused"])

        resumed = self.client.post(
            f"/lesson/G1-L1/command-state/{self.attempt_id}/advance",
            json={"slide_id": "08-01", "action": "resume"},
        )
        self.assertEqual(resumed.status_code, 200)

        resumed_state = self.client.get("/classes/class-1/session-state")
        self.assertEqual(resumed_state.status_code, 200)
        self.assertFalse(resumed_state.json()["paused"])


if __name__ == "__main__":
    unittest.main()
