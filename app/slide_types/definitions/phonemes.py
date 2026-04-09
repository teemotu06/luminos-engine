from __future__ import annotations

from app.schemas.slide_payloads import PhonemePayload
from app.slide_types.base import SlideTypeDefinition, build_editor_config
from app.slide_types.registry import registry


def _summary(payload: dict) -> str:
    return str(payload.get("symbol") or payload.get("slide_title") or "Phoneme")


registry.register(
    SlideTypeDefinition(
        type_key="phonemes",
        label="Phonemes",
        description="One large phoneme card with audio playback.",
        payload_model=PhonemePayload,
        default_payload={"symbol": "s"},
        teacher_template="view_phonemes.html",
        board_template="board_phonemes.html",
        summary_extractor=_summary,
        command_state_defaults=None,
        capability_flags={
            "supports_audio": True,
            "supports_image": False,
            "supports_video": False,
            "supports_reveal": False,
            "supports_teacher_notes": True,
            "supports_expected_response": True,
            "supports_teacher_says": False,
        },
        editor_config=build_editor_config(
            content_fields=[
                {
                    "name": "symbol",
                    "display_label": "Phoneme",
                    "type": "str",
                    "required": True,
                },
            ],
            advanced_fields=[
                {
                    "name": "prompt_text",
                    "display_label": "Board Prompt",
                    "type": "str",
                    "required": False,
                    "help_text": "Optional student-facing prompt shown on the board.",
                },
            ],
        ),
        control_actions=["play_sound", "mark_students"],
        default_marking={"markable": True, "marking_options": ["secure", "shaky", "missed"]},
    )
)
