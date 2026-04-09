import os
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:////tmp/luminos_engine_test_teacher_control_marking.db"
os.environ["LUMINOS_AUTH_REQUIRED"] = "false"

from app.db import get_db
from app.routers.lesson import router as lesson_router
from tests.support import SqliteTestSession, seed_attempt, seed_class_with_students, seed_lesson


class TeacherControlMarkingTests(unittest.TestCase):
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

    def test_student_mark_persists_and_fetches_for_slide(self):
        response = self.client.post(
            "/lesson/G1-L1/student-mark",
            json={
                "attempt_id": str(self.attempt.attempt_id),
                "lesson_id": "G1-L1",
                "slide_id": "03-01",
                "block_id": "03",
                "student_name": "Tom",
                "status": "secure",
                "error_tags": [],
                "support_level": None,
                "teacher_note": None,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "secure")

        fetched = self.client.get(
            f"/lesson/G1-L1/student-marks?attempt_id={self.attempt.attempt_id}&slide_id=03-01"
        )
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(
            fetched.json(),
            [
                {
                    "id": fetched.json()[0]["id"],
                    "student_name": "Tom",
                    "status": "secure",
                    "timestamp": fetched.json()[0]["timestamp"],
                }
            ],
        )

    def test_student_mark_upserts_instead_of_duplicate(self):
        first = self.client.post(
            "/lesson/G1-L1/student-mark",
            json={
                "attempt_id": str(self.attempt.attempt_id),
                "lesson_id": "G1-L1",
                "slide_id": "03-01",
                "block_id": "03",
                "student_name": "Tom",
                "status": "shaky",
                "error_tags": [],
                "support_level": None,
                "teacher_note": None,
            },
        )
        self.assertEqual(first.status_code, 200)

        second = self.client.post(
            "/lesson/G1-L1/student-mark",
            json={
                "attempt_id": str(self.attempt.attempt_id),
                "lesson_id": "G1-L1",
                "slide_id": "03-01",
                "block_id": "03",
                "student_name": "Tom",
                "status": "missed",
                "error_tags": [],
                "support_level": None,
                "teacher_note": None,
            },
        )
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["status"], "missed")

        fetched = self.client.get(
            f"/lesson/G1-L1/student-marks?attempt_id={self.attempt.attempt_id}&slide_id=03-01"
        )
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(len(fetched.json()), 1)
        self.assertEqual(fetched.json()[0]["student_name"], "Tom")
        self.assertEqual(fetched.json()[0]["status"], "missed")

    def test_teacher_shell_marks_are_guarded_to_load_once_per_slide_change(self):
        source = Path("app/static/lesson_teacher.js").read_text(encoding="utf-8")
        self.assertIn("lastLoadedMarkSlideId", source)
        self.assertIn("slideId === this.lastLoadedMarkSlideId", source)

    def test_teacher_template_uses_single_visible_marking_panel(self):
        template = Path("app/templates/lesson/teacher.html").read_text(encoding="utf-8")
        self.assertIn("Mark students", template)
        self.assertIn('x-show="false"', template)
        self.assertNotIn('x-show="teachingMode === \'mark_grid\'"', template)
        self.assertIn('x-show="manualMarkingOpen"', template)
        self.assertNotIn('manualMarkingOpen && currentSlideMarkable', template)

    def test_teacher_shell_marking_is_not_gated_by_slide_markable(self):
        source = Path("app/static/lesson_teacher.js").read_text(encoding="utf-8")
        self.assertIn("return this.currentSlideMarkable && this.roster.length > 0;", source)
        self.assertNotIn('actions.push("mark_students")', source)


if __name__ == "__main__":
    unittest.main()
