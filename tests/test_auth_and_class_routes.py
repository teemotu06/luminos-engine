import os
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import get_db
from app.models.lesson import ClassRecord, UserRecord
from app.routers.auth import router as auth_router
from app.routers.classes import router as classes_router
from app.services.auth_service import hash_password
from tests.support import SqliteTestSession


class AuthAndClassRouteTests(unittest.TestCase):
    def setUp(self):
        self.previous_env = {
            "LUMINOS_AUTH_REQUIRED": os.environ.get("LUMINOS_AUTH_REQUIRED"),
            "LUMINOS_SESSION_SECRET": os.environ.get("LUMINOS_SESSION_SECRET"),
            "LUMINOS_BOOTSTRAP_ADMIN_USERNAME": os.environ.get("LUMINOS_BOOTSTRAP_ADMIN_USERNAME"),
            "LUMINOS_BOOTSTRAP_ADMIN_PASSWORD": os.environ.get("LUMINOS_BOOTSTRAP_ADMIN_PASSWORD"),
            "LUMINOS_BOOTSTRAP_TEACHER_USERNAME": os.environ.get("LUMINOS_BOOTSTRAP_TEACHER_USERNAME"),
            "LUMINOS_BOOTSTRAP_TEACHER_PASSWORD": os.environ.get("LUMINOS_BOOTSTRAP_TEACHER_PASSWORD"),
        }
        os.environ["LUMINOS_AUTH_REQUIRED"] = "true"
        os.environ["LUMINOS_SESSION_SECRET"] = "test-session-secret"
        os.environ["LUMINOS_BOOTSTRAP_ADMIN_USERNAME"] = "admin"
        os.environ["LUMINOS_BOOTSTRAP_ADMIN_PASSWORD"] = "admin-pass"
        os.environ["LUMINOS_BOOTSTRAP_TEACHER_USERNAME"] = "teacher-one"
        os.environ["LUMINOS_BOOTSTRAP_TEACHER_PASSWORD"] = "teacher-pass"

        self.session = SqliteTestSession()
        self.db = self.session.db
        self.db.add(UserRecord(username="teacher-two", password_hash=hash_password("teacher-two-pass"), role="teacher"))
        self.db.commit()

        self.app = FastAPI()
        self.app.include_router(auth_router)
        self.app.include_router(classes_router)

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
        for key, value in self.previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _login(self, username: str, password: str) -> None:
        response = self.client.post(
            "/auth/login",
            data={"username": username, "password": password, "next": "/classes/"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)

    def test_classes_require_login(self):
        response = self.client.get("/classes/")
        self.assertEqual(response.status_code, 401)

    def test_teacher_ownership_and_soft_delete(self):
        self._login("teacher-one", "teacher-pass")

        create_response = self.client.post(
            "/classes/new",
            data={"class_name": "Blue Group", "description": "Monday"},
            follow_redirects=False,
        )
        self.assertEqual(create_response.status_code, 303)

        teacher_one = self.db.execute(select(UserRecord).where(UserRecord.username == "teacher-one")).scalars().one()
        class_record = self.db.execute(select(ClassRecord).where(ClassRecord.class_name == "Blue Group")).scalars().one()
        self.assertEqual(str(class_record.owner_user_id), str(teacher_one.id))

        self.client.post(f"/classes/{class_record.id}/archive", follow_redirects=False)
        archived_index = self.client.get("/classes/")
        self.assertNotIn("View class", archived_index.text)
        self.assertIn("Restorable classes", archived_index.text)

        self.client.post(f"/auth/logout", follow_redirects=False)
        self._login("teacher-two", "teacher-two-pass")
        other_teacher_detail = self.client.get(f"/classes/{class_record.id}")
        self.assertEqual(other_teacher_detail.status_code, 404)

        self.client.post("/auth/logout", follow_redirects=False)
        self._login("admin", "admin-pass")
        admin_restore = self.client.post(f"/classes/{class_record.id}/restore", follow_redirects=False)
        self.assertEqual(admin_restore.status_code, 303)
        restored_detail = self.client.get(f"/classes/{class_record.id}")
        self.assertEqual(restored_detail.status_code, 200)
