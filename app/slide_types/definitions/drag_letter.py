from __future__ import annotations

from app.schemas.command_state import LuminosRuntimeStateConfig
from app.schemas.slide_payloads import DragLetterPayload
from app.services.command_runtime_profiles import BLOCK_RUNTIME_PROFILES
from app.slide_types.base import SlideTypeDefinition, build_editor_config
from app.slide_types.registry import registry


def _summary(payload: dict) -> str:
    return str(payload.get("target_word") or payload.get("slide_title") or "")


def _defaults(slide, block_id) -> list[LuminosRuntimeStateConfig]:
    payload = slide.content_payload
    teacher_cue = slide.teacher_cue or ""
    target_word = getattr(payload, "target_word", "") or "the word"
    profile = BLOCK_RUNTIME_PROFILES.get((str(block_id), "drag_letter"))
    states = [
        LuminosRuntimeStateConfig(
            key="transition",
            board_prompt=f"Get ready to build {target_word}.",
            teacher_prompt=teacher_cue or f"Set the build routine for {target_word}.",
            tts_prompt=f"Get ready to build {target_word}.",
            teacher_controls=["replay", "force_advance"],
        ),
        LuminosRuntimeStateConfig(
            key="build",
            board_prompt=f"Build {target_word}.",
            teacher_prompt=teacher_cue or f"Students build {target_word}.",
            tts_prompt=f"Build {target_word}.",
            teacher_controls=["replay", "force_advance"],
        ),
        LuminosRuntimeStateConfig(
            key="check",
            board_prompt="Check every part.",
            teacher_prompt=teacher_cue or "Confirm the build, then mark the class.",
            tts_prompt="Check every part.",
            teacher_controls=["mark_class", "replay", "force_advance"],
        ),
    ]
    if profile == "word_build":
        states.insert(
            2,
            LuminosRuntimeStateConfig(
                key="partner_practice",
                board_prompt="Work with your partner. Check it together.",
                teacher_prompt="Give them a short check window before class confirmation.",
                tts_prompt="Work with your partner. Check it together.",
                timeout_ms=12000,
                teacher_controls=["pause", "force_advance"],
            ),
        )
    return states


registry.register(
    SlideTypeDefinition(
        type_key="drag_letter",
        label="Build the Word",
        description="Build a word from draggable letters.",
        payload_model=DragLetterPayload,
        default_payload={
            "target_word": "at",
            "target_letters": ["a", "t"],
            "slots": ["", ""],
            "draggable_letters": ["a", "t"],
        },
        teacher_template="view_drag_letter.html",
        board_template="board_drag_letter.html",
        summary_extractor=_summary,
        command_state_defaults=_defaults,
        capability_flags={
            "supports_audio": True,
            "supports_image": True,
            "supports_video": False,
            "supports_reveal": False,
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
                    "help_text": "The word students should build.",
                },
                {
                    "name": "draggable_letters",
                    "display_label": "Letter Tiles",
                    "type": "list[str]",
                    "required": True,
                    "help_text": "The tiles students can move while building.",
                },
                {
                    "name": "image",
                    "display_label": "Image",
                    "type": "str",
                    "required": False,
                    "media_type": "image",
                    "help_text": "Optional picture support for the target word.",
                },
            ],
            task_fields=[
                {
                    "name": "prompt_text",
                    "display_label": "Student Prompt",
                    "type": "text",
                    "required": False,
                    "help_text": "Optional verbal prompt for the build task.",
                    "paired_audio": "audio",
                },
                {
                    "name": "audio",
                    "display_label": "Audio File",
                    "type": "str",
                    "required": False,
                    "media_type": "audio",
                    "help_text": "Optional pronunciation audio for the target word.",
                },
            ],
            advanced_fields=[
                {
                    "name": "target_letters",
                    "display_label": "Letters",
                    "type": "list[str]",
                    "required": False,
                    "help_text": "Usually matches the target word automatically. Edit only for manual control.",
                },
                {
                    "name": "slots",
                    "display_label": "Letter Slots",
                    "type": "list[str]",
                    "required": False,
                    "help_text": "Usually auto-derived. Only edit if you need custom slot placeholders.",
                },
            ],
        ),
        control_actions=["play_sound", "reveal_answer", "mark_students"],
        default_marking={"markable": True, "marking_options": ["secure", "shaky", "missed"]},
    )
)
