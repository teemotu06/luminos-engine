import os
import unittest

os.environ["DATABASE_URL"] = "sqlite:////tmp/luminos_engine_test_control_audio.db"
os.environ["LUMINOS_AUTH_REQUIRED"] = "false"

from app.schemas.slide import Slide


class ControlAudioSchemaTests(unittest.TestCase):
    def test_slide_audio_url_serializes(self):
        slide = Slide(
            slide_id="x1",
            block_id="01",
            slide_title="Audio Slide",
            view_type="flashcard",
            content_payload={"front_text": "Sam", "back_text": "/sam/"},
            teacher_cue="Teach it",
            expected_response="Students respond.",
            correction_move="Model again.",
            observation_note=None,
            slide_audio_url="/static/uploads/audio/sam.mp3",
            teacher_prompts=[{"text": "Say the word.", "audio_url": "/static/uploads/audio/prompt.mp3"}],
            korean_interference_flag=None,
            markable=True,
            marking_options=["secure", "shaky", "missed"],
            next_action="manual_next",
        )
        dumped = slide.model_dump()
        self.assertEqual(dumped["slide_audio_url"], "/static/uploads/audio/sam.mp3")
        self.assertEqual(dumped["teacher_prompts"][0]["audio_url"], "/static/uploads/audio/prompt.mp3")
