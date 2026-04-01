import os
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.services import kokoro_tts_service


class KokoroTtsServiceTests(unittest.TestCase):
    def test_cached_prompt_reuses_existing_wav_without_resynthesis(self):
        with TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            synth_calls = []

            def fake_synthesize(text):
                synth_calls.append(text)
                return [0.0, 0.0], 24000

            def fake_write(path, audio, sample_rate):
                path.write_bytes(b"RIFFfake")

            with patch.object(kokoro_tts_service, "TTS_CACHE_DIR", cache_dir), patch.object(
                kokoro_tts_service, "_synthesize_audio", side_effect=fake_synthesize
            ), patch.object(kokoro_tts_service, "_write_wav_atomic", side_effect=fake_write):
                first = kokoro_tts_service.ensure_tts_audio("Tom, please read.")
                second = kokoro_tts_service.ensure_tts_audio("Tom, please read.")

            self.assertEqual(first, second)
            self.assertEqual(synth_calls, ["Tom, please read."])
            self.assertTrue((cache_dir / Path(first["audio_url"]).name).exists())

    def test_atomic_write_replaces_temp_file_and_cleans_up(self):
        with TemporaryDirectory() as tmpdir:
            final_path = Path(tmpdir) / "prompt.wav"

            def fake_write(path, audio, sample_rate):
                path.write_bytes(b"temporary-wav")

            with patch.object(kokoro_tts_service, "_write_wav", side_effect=fake_write):
                kokoro_tts_service._write_wav_atomic(final_path, [0.0], 24000)

            self.assertTrue(final_path.exists())
            self.assertEqual(final_path.read_bytes(), b"temporary-wav")
            leftovers = list(final_path.parent.glob("*.tmp.*"))
            self.assertEqual(leftovers, [])

    def test_prune_tts_cache_deletes_old_wavs_only(self):
        with TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            old_file = cache_dir / "old.wav"
            fresh_file = cache_dir / "fresh.wav"
            old_file.write_bytes(b"old")
            fresh_file.write_bytes(b"fresh")

            old_mtime = time.time() - (40 * 86400)
            os.utime(old_file, (old_mtime, old_mtime))

            with patch.object(kokoro_tts_service, "TTS_CACHE_DIR", cache_dir):
                result = kokoro_tts_service.prune_tts_cache(max_age_days=30)

            self.assertEqual(result["deleted"], 1)
            self.assertEqual(result["kept"], 1)
            self.assertFalse(old_file.exists())
            self.assertTrue(fresh_file.exists())
