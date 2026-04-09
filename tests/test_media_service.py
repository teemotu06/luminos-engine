import io
import os
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi import UploadFile

from app.services import media_service


def make_upload(filename: str, content: bytes, content_type: str) -> UploadFile:
    return UploadFile(filename=filename, file=io.BytesIO(content), headers={"content-type": content_type})


class MediaServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.upload_dir = Path(self.temp_dir.name)
        self.upload_patch = patch("app.services.media_service.get_upload_dir", return_value=self.upload_dir)
        self.upload_patch.start()

    def tearDown(self):
        self.upload_patch.stop()
        self.temp_dir.cleanup()

    def test_validate_upload_accepts_valid_audio_image_and_video(self):
        media_service.validate_upload(make_upload("sound.mp3", b"abc", "audio/mpeg"), "audio")
        media_service.validate_upload(make_upload("picture.png", b"abc", "image/png"), "image")
        media_service.validate_upload(make_upload("clip.mp4", b"abc", "video/mp4"), "video")

    def test_validate_upload_rejects_wrong_extension_for_media_type(self):
        with self.assertRaises(ValueError):
            media_service.validate_upload(make_upload("picture.png", b"abc", "image/png"), "audio")

    def test_validate_upload_rejects_oversized_files(self):
        oversized = b"a" * (media_service.MAX_AUDIO_SIZE + 1)
        with self.assertRaises(ValueError):
            media_service.validate_upload(make_upload("sound.mp3", oversized, "audio/mpeg"), "audio")

    def test_save_upload_writes_file_and_returns_relative_path(self):
        path = media_service.save_upload(make_upload("sound.mp3", b"hello", "audio/mpeg"), "audio")
        self.assertTrue(path.startswith("/static/uploads/audio/"))
        saved = self.upload_dir / "audio" / Path(path).name
        self.assertTrue(saved.exists())
        self.assertEqual(saved.read_bytes(), b"hello")

    def test_save_upload_sanitizes_filename(self):
        path = media_service.save_upload(
            make_upload("../bad n\u00e4me?.mp3", b"hello", "audio/mpeg"),
            "audio",
        )
        self.assertTrue(path.endswith("_bad_name.mp3") or path.endswith("_bad_nme.mp3") or path.endswith("_bad_name_.mp3"))
        self.assertNotIn("..", path)
        self.assertNotIn(" ", path)

    def test_list_files_returns_sorted_by_modified_desc(self):
        older = self.upload_dir / "audio" / "older.mp3"
        newer = self.upload_dir / "audio" / "newer.mp3"
        older.parent.mkdir(parents=True, exist_ok=True)
        older.write_bytes(b"1")
        time.sleep(0.01)
        newer.write_bytes(b"2")
        files = media_service.list_files("audio")
        self.assertEqual([item["filename"] for item in files], ["newer.mp3", "older.mp3"])

    def test_list_files_returns_empty_list_for_empty_directory(self):
        self.assertEqual(media_service.list_files("audio"), [])

    def test_delete_file_removes_file_and_returns_true(self):
        target = self.upload_dir / "audio" / "sample.mp3"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"123")
        self.assertTrue(media_service.delete_file("audio", "sample.mp3"))
        self.assertFalse(target.exists())

    def test_delete_file_returns_false_for_nonexistent_file(self):
        self.assertFalse(media_service.delete_file("audio", "missing.mp3"))
