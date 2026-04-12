from __future__ import annotations

from app.schemas.command_state import LuminosRuntimeStateConfig
from app.schemas.slide_payloads import ListenSpellPayload
from app.slide_types.base import SlideTypeDefinition, build_editor_config
from app.slide_types.registry import registry


def _summary(payload: dict) -> str:
    return str(payload.get("target_word") or payload.get("slide_title") or "Listen & Spell")


def _defaults(slide, block_id) -> list[LuminosRuntimeStateConfig]:
    del block_id
    payload = slide.content_payload
    teacher_cue = slide.teacher_cue or ""
    target_word = getattr(payload, "target_word", "") or "the word"
    return [
        LuminosRuntimeStateConfig(
            key="listening",
            board_prompt="",
            teacher_prompt=teacher_cue or f"Play or say {target_word}. Students write it independently.",
            tts_prompt="",
            teacher_controls=["replay", "force_advance"],
        ),
        LuminosRuntimeStateConfig(
            key="revealed",
            board_prompt="",
            teacher_prompt=teacher_cue or f"Reveal {target_word} so students can self-check.",
            tts_prompt="",
            teacher_controls=["mark_class", "replay", "force_advance"],
        ),
    ]


registry.register(
    SlideTypeDefinition(
        type_key="listen_spell",
        label="Listen & Spell",
        description="Audio-first spelling check with a blank board before reveal and a large self-check word after reveal.",
        payload_model=ListenSpellPayload,
        default_payload={"target_word": "ship", "target_pattern": "sh"},
        teacher_template="view_listen_spell.html",
        board_template="board_listen_spell.html",
        summary_extractor=_summary,
        command_state_defaults=_defaults,
        capability_flags={
            "supports_audio": True,
            "supports_image": False,
            "supports_video": False,
            "supports_reveal": True,
            "supports_teacher_notes": True,
            "supports_expected_response": True,
            "supports_teacher_says": True,
        },
        editor_config=build_editor_config(
            content_fields=[
                {
                    "name": "target_word",
                    "display_label": "Target Word",
                    "type": "str",
                    "required": True,
                },
                {
                    "name": "target_pattern",
                    "display_label": "Target Phoneme Pattern",
                    "type": "str",
                    "required": False,
                },
            ],
        ),
        control_actions=["play_sound", "reveal_answer", "mark_students"],
        default_marking={"markable": True, "marking_options": ["secure", "shaky", "missed"]},
        allowed_blocks=("02",),
    )
)
