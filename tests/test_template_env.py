import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from types import SimpleNamespace

# Force SQLite before app modules resolve DATABASE_URL and JSON column types.
os.environ["DATABASE_URL"] = "sqlite:////tmp/luminos_engine_test_bootstrap.db"
os.environ["LUMINOS_AUTH_REQUIRED"] = "false"

from app import template_env


class TemplateEnvTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = TemporaryDirectory()
        self.manifest_path = Path(self.tmpdir.name) / "manifest.json"
        self.manifest_path.write_text('{"styles.css": "/static/dist/styles.css?v=old"}\n', encoding="utf-8")
        template_env._manifest = {}
        template_env._manifest_mtime_ns = None

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_asset_url_refreshes_when_manifest_changes(self):
        with patch.object(template_env, "_MANIFEST_PATH", self.manifest_path):
            first_url = template_env.asset_url("styles.css")
            self.assertEqual(first_url, "/static/dist/styles.css?v=old")

            self.manifest_path.write_text(
                '{"styles.css": "/static/dist/styles.css?v=new"}\n',
                encoding="utf-8",
            )

            second_url = template_env.asset_url("styles.css")
            self.assertEqual(second_url, "/static/dist/styles.css?v=new")

    def test_asset_url_falls_back_when_manifest_missing(self):
        missing_path = Path(self.tmpdir.name) / "missing-manifest.json"
        with patch.object(template_env, "_MANIFEST_PATH", missing_path):
            self.assertEqual(
                template_env.asset_url("styles.css"),
                "/static/dist/styles.css",
            )

    def test_view_type_label_uses_registry(self):
        self.assertEqual(template_env.view_type_label("flashcard"), "Flashcard")

    def test_slide_display_content_uses_registry(self):
        slide = SimpleNamespace(
            view_type="drag_letter",
            slide_title="Fallback",
            content_payload=SimpleNamespace(model_dump=lambda: {"target_word": "sat"}),
        )
        self.assertEqual(template_env.slide_display_content(slide), "sat")


if __name__ == "__main__":
    unittest.main()
