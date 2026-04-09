from __future__ import annotations

from app.schemas.command_state import LuminosRuntimeStateConfig
from app.schemas.slide_payloads import WritingEncodingPayload
from app.services.command_runtime_profiles import BLOCK_RUNTIME_PROFILES
from app.slide_types.base import SlideTypeDefinition, build_editor_config
from app.slide_types.registry import registry


def _summary(payload: dict) -> str:
    return str(payload.get("dictated_text") or payload.get("slide_title") or "")


def _defaults(slide, block_id) -> list[LuminosRuntimeStateConfig]:
    payload = slide.content_payload
    teacher_cue = slide.teacher_cue or ""
    dictated_text = getattr(payload, "dictated_text", "") or "the word"
    profile = BLOCK_RUNTIME_PROFILES.get((str(block_id), "writing_encoding"))
    states = [
        LuminosRuntimeStateConfig(
            key="transition",
            board_prompt="Get ready to write.",
            teacher_prompt=teacher_cue or "Prepare students to encode.",
            tts_prompt="Get ready to write.",
            teacher_controls=["replay", "force_advance"],
        ),
        LuminosRuntimeStateConfig(
            key="dictate",
            board_prompt=f"Write {dictated_text}.",
            teacher_prompt=teacher_cue or f"Dictate {dictated_text}.",
            tts_prompt=f"Write {dictated_text}.",
            teacher_controls=["replay", "force_advance"],
        ),
        LuminosRuntimeStateConfig(
            key="check",
            board_prompt="Check every sound.",
            teacher_prompt=teacher_cue or "Confirm the writing, then mark the class.",
            tts_prompt="Check every sound.",
            teacher_controls=["mark_class", "replay", "force_advance"],
        ),
    ]
    if profile == "encoding_write":
        states.insert(
            2,
            LuminosRuntimeStateConfig(
                key="write",
                board_prompt="Write now.",
                teacher_prompt="Give a short silent writing window.",
                tts_prompt="Write now.",
                timeout_ms=15000,
                teacher_controls=["pause", "force_advance"],
            ),
        )
    return states


registry.register(
    SlideTypeDefinition(
        type_key="writing_encoding",
        label="Write It",
        description="Dictation and encoding practice.",
        payload_model=WritingEncodingPayload,
        default_payload={"dictated_text": "sat", "expected_answer": "sat"},
        teacher_template="view_writing_encoding.html",
        board_template="board_writing_encoding.html",
        summary_extractor=_summary,
        command_state_defaults=_defaults,
        capability_flags={
            "supports_audio": True,
            "supports_image": False,
            "supports_video": False,
            "supports_reveal": False,
            "supports_teacher_notes": True,
            "supports_expected_response": True,
            "supports_teacher_says": True,
        },
        editor_config=build_editor_config(
            content_fields=[
                {
                    "name": "dictated_text",
                    "display_label": "Dictation Word",
                    "type": "str",
                    "required": True,
                    "help_text": "The word or phrase students should write.",
                },
                {
                    "name": "expected_answer",
                    "display_label": "Correct Answer",
                    "type": "str",
                    "required": True,
                    "help_text": "What correct student writing should match.",
                },
            ],
            task_fields=[
                {
                    "name": "prompt_text",
                    "display_label": "Student Prompt",
                    "type": "text",
                    "required": False,
                    "help_text": "Optional teacher wording for the dictation task.",
                    "paired_audio": "audio_prompt",
                },
                {
                    "name": "audio_prompt",
                    "display_label": "Audio File",
                    "type": "str",
                    "required": False,
                    "media_type": "audio",
                    "help_text": "Optional audio version of the dictation prompt.",
                },
            ],
            advanced_fields=[
                {
                    "name": "display_mode",
                    "display_label": "Display Mode",
                    "type": "str",
                    "required": False,
                    "help_text": "Usually uses the default writing flow. Only change if you need manual runtime control.",
                },
                {
                    "name": "elkonin_boxes",
                    "display_label": "Elkonin Boxes",
                    "type": "int",
                    "required": False,
                    "help_text": "Usually auto-derived. Only edit if you need a specific box count.",
                },
                {
                    "name": "grapheme_units",
                    "display_label": "Grapheme Units",
                    "type": "list[str]",
                    "required": False,
                    "help_text": "Usually auto-derived. Only edit if you need manual grapheme segmentation.",
                },
            ],
        ),
        control_actions=["play_audio", "reveal_answer", "mark_students"],
        default_marking={"markable": True, "marking_options": ["secure", "shaky", "missed"]},
    )
)
