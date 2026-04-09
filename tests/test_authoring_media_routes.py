import io
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:////tmp/luminos_engine_test_media.db"
os.environ["LUMINOS_AUTH_REQUIRED"] = "false"
os.environ["LUMINOS_ADMIN_SECRET"] = "test-admin-secret"

from app.routers.authoring_media import router as authoring_media_router


class AuthoringMediaRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.upload_dir = Path(self.temp_dir.name)
        self.upload_patch = patch("app.services.media_service.get_upload_dir", return_value=self.upload_dir)
        self.upload_patch.start()
        self.app = FastAPI()
        self.app.include_router(authoring_media_router)
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.upload_patch.stop()
        self.temp_dir.cleanup()

    def test_upload_endpoint_accepts_valid_file(self):
        response = self.client.post(
            "/authoring/media/upload",
            files={"file": ("sample.mp3", io.BytesIO(b"audio"), "audio/mpeg")},
            data={"media_type": "audio"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertTrue(payload["path"].startswith("/static/uploads/audio/"))

    def test_upload_endpoint_rejects_invalid_file_type(self):
        response = self.client.post(
            "/authoring/media/upload",
            files={"file": ("sample.txt", io.BytesIO(b"text"), "text/plain")},
            data={"media_type": "audio"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])

    def test_browse_endpoint_returns_html_with_file_listing(self):
        target = self.upload_dir / "audio" / "sample.mp3"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"audio")
        response = self.client.get("/authoring/media/browse/audio")
        self.assertEqual(response.status_code, 200)
        self.assertIn("sample.mp3", response.text)
        self.assertIn("/static/uploads/audio/sample.mp3", response.text)

    def test_delete_endpoint_removes_file(self):
        target = self.upload_dir / "audio" / "sample.mp3"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"audio")
        response = self.client.delete("/authoring/media/audio/sample.mp3")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["deleted"])
        self.assertFalse(target.exists())
