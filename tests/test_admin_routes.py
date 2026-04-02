import os
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

# Force SQLite before any app module imports app.db / app.models.
os.environ["DATABASE_URL"] = "sqlite:////tmp/luminos_engine_test_bootstrap.db"
os.environ["LUMINOS_ADMIN_SECRET"] = "test-admin-secret"
os.environ["LUMINOS_AUTH_REQUIRED"] = "false"

from app.routers.admin import router as admin_router


class AdminRouteTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(admin_router)
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()

    def test_tts_health_route_returns_snapshot(self):
        with patch("app.routers.admin.get_tts_health_snapshot", return_value={
            "ready": True,
            "voice": "af_heart",
            "sample_rate": 24000,
            "cache_dir": "/tmp/tts",
            "cache_file_count": 3,
            "cache_size_bytes": 1200,
            "prewarm_text": "Luminos is ready.",
            "check_elapsed_ms": 42,
            "last_audio_url": "/tts-cache/abc.wav",
            "error": None,
        }):
            response = self.client.get("/admin/tts-health", headers={"X-Admin-Secret": "test-admin-secret"})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ready"])
        self.assertEqual(response.json()["cache_file_count"], 3)

    def test_tts_prune_route_returns_deleted_counts(self):
        with patch("app.routers.admin.prune_tts_cache", return_value={
            "deleted": 2,
            "kept": 5,
            "bytes_freed": 2048,
        }):
            response = self.client.post(
                "/admin/tts-prune-cache?max_age_days=15",
                headers={"X-Admin-Secret": "test-admin-secret"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"ok": True, "deleted": 2, "kept": 5, "bytes_freed": 2048},
        )
