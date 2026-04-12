from __future__ import annotations

from app.schemas.command_state import LuminosRuntimeStateConfig
from app.schemas.slide_payloads import SoundMatchPayload
from app.slide_types.base import SlideTypeDefinition, build_editor_config
from app.slide_types.registry import registry


def _summary(payload: dict) -> str:
    a = str(payload.get("pair_a_label") or "").strip()
    b = str(payload.get("pair_b_label") or "").strip()
    return f"{a} / {b}" if a and b else str(payload.get("slide_title") or "Sound Match")


def _defaults(slide, block_id) -> list[LuminosRuntimeStateConfig]:
    del block_id
    payload = slide.content_payload
    teacher_cue = slide.teacher_cue or ""
    correct_choice = getattr(payload, "correct_choice", "A")
    correct_word = getattr(payload, "pair_a_example_word" if correct_choice == "A" else "pair_b_example_word", "") or "the word"
    return [
        LuminosRuntimeStateConfig(
            key="listening",
            board_prompt="",
            teacher_prompt=teacher_cue or "Play the target sound. Students choose which card matches.",
            tts_prompt="",
            teacher_controls=["replay", "force_advance"],
        ),
        LuminosRuntimeStateConfig(
            key="revealed",
            board_prompt="",
            teacher_prompt=teacher_cue or "Reveal the correct option and mark the class.",
            tts_prompt="",
            teacher_controls=["replay", "mark_class", "force_advance"],
        ),
        LuminosRuntimeStateConfig(
            key="produce",
            board_prompt="",
            teacher_prompt=teacher_cue or f"Model {correct_word} and run the production routine.",
            tts_prompt="",
            teacher_controls=["replay", "mark_class"],
        ),
    ]


registry.register(
    SlideTypeDefinition(
        type_key="sound_match",
        label="Sound Match",
        description="Students hear a target sound, choose the matching card, then move into production.",
        payload_model=SoundMatchPayload,
        default_payload={
            "pair_a_label": "/f/",
            "pair_a_example_word": "fan",
            "pair_a_audio": "/static/audio/example-f.mp3",
            "pair_b_label": "/p/",
            "pair_b_example_word": "pan",
            "pair_b_audio": "/static/audio/example-p.mp3",
            "correct_choice": "A",
            "production_cue": "Top teeth on lower lip. Air flows continuously.",
        },
        teacher_template="view_sound_match.html",
        board_template="board_sound_match.html",
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
                {"name": "pair_a_label", "display_label": "Pair A Label", "type": "str", "required": True},
                {"name": "pair_a_example_word", "display_label": "Pair A Example Word", "type": "str", "required": True},
                {"name": "pair_a_audio", "display_label": "Pair A Audio", "type": "str", "required": True},
                {"name": "pair_b_label", "display_label": "Pair B Label", "type": "str", "required": True},
                {"name": "pair_b_example_word", "display_label": "Pair B Example Word", "type": "str", "required": True},
                {"name": "pair_b_audio", "display_label": "Pair B Audio", "type": "str", "required": True},
                {
                    "name": "correct_choice",
                    "display_label": "Correct Choice",
                    "type": "select",
                    "options": ["A", "B"],
                    "required": True,
                },
                {
                    "name": "production_cue",
                    "display_label": "Production Cue",
                    "type": "text",
                    "required": True,
                },
            ],
            advanced_fields=[
                {
                    "name": "korean_flag",
                    "display_label": "Korean Interference Flag",
                    "type": "str",
                    "required": False,
                },
            ],
        ),
        control_actions=["play_sound", "reveal_answer", "produce_phase", "play_model", "mark_students"],
        default_marking={"markable": True, "marking_options": ["secure", "shaky", "missed"]},
    )
)
