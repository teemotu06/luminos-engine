from __future__ import annotations

from app.schemas.command_state import LuminosRuntimeStateConfig
from app.schemas.slide_payloads import SpellWordPayload
from app.slide_types.base import SlideTypeDefinition, build_editor_config
from app.slide_types.registry import registry


def _summary(payload: dict) -> str:
    return str(payload.get("correct_word") or payload.get("slide_title") or "Spell the Word")


def _defaults(slide, block_id) -> list[LuminosRuntimeStateConfig]:
    del block_id
    payload = slide.content_payload
    teacher_cue = slide.teacher_cue or ""
    correct_word = getattr(payload, "correct_word", "") or "the word"
    return [
        LuminosRuntimeStateConfig(
            key="transition",
            board_prompt="",
            teacher_prompt=teacher_cue or f"Play the word and let students spell {correct_word}.",
            tts_prompt="",
            teacher_controls=["replay", "force_advance"],
        ),
        LuminosRuntimeStateConfig(
            key="answer",
            board_prompt="",
            teacher_prompt=teacher_cue or f"Show the answer for {correct_word}.",
            tts_prompt="",
            teacher_controls=["mark_class", "replay", "force_advance"],
        ),
    ]


registry.register(
    SlideTypeDefinition(
        type_key="spell_word",
        label="Spell the Word",
        description="Audio-first spelling slide with a letter pool around a central answer box.",
        payload_model=SpellWordPayload,
        default_payload={"correct_word": "sat", "letter_pool": ["s", "a", "t"]},
        teacher_template="view_spell_word.html",
        board_template="board_spell_word.html",
        summary_extractor=_summary,
        command_state_defaults=_defaults,
        capability_flags={
            "supports_audio": True,
            "supports_image": False,
            "supports_video": False,
            "supports_reveal": True,
            "supports_teacher_notes": True,
            "supports_expected_response": True,
            "supports_teacher_says": False,
        },
        editor_config=build_editor_config(
            content_fields=[
                {
                    "name": "correct_word",
                    "display_label": "Correct Word",
                    "type": "str",
                    "required": True,
                },
                {
                    "name": "letter_pool",
                    "display_label": "Letter Pool",
                    "type": "list[str]",
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
        control_actions=["play_sound", "reveal_answer", "mark_students"],
        default_marking={"markable": True, "marking_options": ["secure", "shaky", "missed"]},
    )
)
