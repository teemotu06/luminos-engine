import unittest

from app.schemas.command_state import LuminosRuntimeConfig, LuminosRuntimeStateConfig
from app.services.lesson_service import load_lesson
from app.services.slide_payload_validator import validate_slide_payloads


class SlidePayloadValidatorTests(unittest.TestCase):
    def test_luminos_runtime_rejects_invalid_teacher_controls(self):
        lesson = load_lesson("G1-L1")
        slide = lesson.blocks["03"].slides[0]
        slide.luminos_runtime = LuminosRuntimeConfig(
            enabled=True,
            state_sequence=[
                LuminosRuntimeStateConfig(
                    key="transition",
                    board_prompt="Look here.",
                    teacher_controls=["launch_missiles"],
                )
            ],
        )

        with self.assertRaises(ValueError) as context:
            validate_slide_payloads(lesson)

        self.assertIn("invalid teacher_controls", str(context.exception))

    def test_g1_l2_luminos_runtime_validates_cleanly(self):
        lesson = load_lesson("G1-L2")

        validate_slide_payloads(lesson)

