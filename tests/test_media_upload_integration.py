import io
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:////tmp/luminos_engine_test_media_integration.db"
os.environ["LUMINOS_AUTH_REQUIRED"] = "false"

from app.routers.authoring_media import router as authoring_media_router


class MediaUploadIntegrationTests(unittest.TestCase):
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

    def test_browse_partial_includes_upload_form(self):
        response = self.client.get("/authoring/media/browse/audio")
        self.assertEqual(response.status_code, 200)
        self.assertIn('hx-post="/authoring/media/upload"', response.text)
        self.assertIn('name="media_type" value="audio"', response.text)

    def test_htmx_upload_returns_updated_browser_partial(self):
        response = self.client.post(
            "/authoring/media/upload",
            headers={"HX-Request": "true"},
            files={"file": ("new_sound.mp3", io.BytesIO(b"audio"), "audio/mpeg")},
            data={"media_type": "audio"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("new_sound.mp3", response.text)
        self.assertIn("/static/uploads/audio/", response.text)

    def test_htmx_upload_invalid_type_renders_inline_error(self):
        response = self.client.post(
            "/authoring/media/upload",
            headers={"HX-Request": "true"},
            files={"file": ("bad.txt", io.BytesIO(b"text"), "text/plain")},
            data={"media_type": "audio"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid file extension", response.text)
        self.assertIn('hx-post="/authoring/media/upload"', response.text)
