from __future__ import annotations

from app.schemas.command_state import LuminosRuntimeStateConfig
from app.schemas.slide_payloads import FlashcardPayload
from app.services.command_runtime_profiles import BLOCK_RUNTIME_PROFILES
from app.slide_types.base import SlideTypeDefinition, build_editor_config
from app.slide_types.registry import registry


def _summary(payload: dict) -> str:
    return str(payload.get("front_text") or payload.get("slide_title") or "Flashcard")


def _defaults(slide, block_id) -> list[LuminosRuntimeStateConfig]:
    payload = slide.content_payload
    teacher_cue = slide.teacher_cue or ""
    front_text = getattr(payload, "front_text", "") or slide.slide_title
    spoken_unit = getattr(payload, "back_text", "") or front_text
    profile = BLOCK_RUNTIME_PROFILES.get((str(block_id), "flashcard"))
    states = [
        LuminosRuntimeStateConfig(
            key="transition",
            board_prompt="",
            teacher_prompt=teacher_cue or f"Set attention on {front_text}.",
            tts_prompt="",
            teacher_controls=["replay", "force_advance"],
        ),
        LuminosRuntimeStateConfig(
            key="model",
            board_prompt="",
            teacher_prompt=teacher_cue or f"Model {spoken_unit} once.",
            tts_prompt="",
            teacher_controls=["replay", "force_advance"],
        ),
        LuminosRuntimeStateConfig(
            key="choral",
            board_prompt="",
            teacher_prompt=teacher_cue or "Take a choral response, then mark the class.",
            tts_prompt="",
            teacher_controls=["mark_class", "replay", "force_advance"],
        ),
    ]
    if profile == "sound_intro":
        states[0].board_prompt = ""
        states[0].tts_prompt = ""
    elif profile == "vocab_warmup":
        states[0].board_prompt = ""
        states[0].tts_prompt = ""
    return states


registry.register(
    SlideTypeDefinition(
        type_key="flashcard",
        label="Flashcard",
        description="Show front and back card content, using text or image on either side.",
        payload_model=FlashcardPayload,
        default_payload={"front_text": "Example", "back_text": "Example", "front_image": None, "back_image": None},
        teacher_template="view_flashcard.html",
        board_template="board_flashcard.html",
        summary_extractor=_summary,
        command_state_defaults=_defaults,
        capability_flags={
            "supports_audio": True,
            "supports_image": True,
            "supports_video": False,
            "supports_reveal": True,
            "supports_teacher_notes": True,
            "supports_expected_response": True,
            "supports_teacher_says": True,
        },
        editor_config=build_editor_config(
            content_fields=[
                {
                    "name": "front_text",
                    "display_label": "Front Text",
                    "type": "str",
                    "required": False,
                    "help_text": "Optional text on the front of the card. Use text or front image.",
                },
                {
                    "name": "front_image",
                    "display_label": "Front Image",
                    "type": "str",
                    "required": False,
                    "media_type": "image",
                    "help_text": "Optional image on the front of the card.",
                },
                {
                    "name": "back_text",
                    "display_label": "Back Text",
                    "type": "str",
                    "required": False,
                    "help_text": "Optional text on the back of the card. Use text or back image.",
                },
                {
                    "name": "back_image",
                    "display_label": "Back Image",
                    "type": "str",
                    "required": False,
                    "media_type": "image",
                    "help_text": "Optional image on the back of the card.",
                },
                {
                    "name": "audio",
                    "display_label": "Audio File",
                    "type": "str",
                    "required": False,
                    "media_type": "audio",
                    "help_text": "Optional pronunciation audio for this card.",
                },
            ],
            advanced_fields=[
                {
                    "name": "image",
                    "display_label": "Legacy Image",
                    "type": "str",
                    "required": False,
                    "media_type": "image",
                    "help_text": "Legacy flashcard image support. Prefer front image or back image for new cards.",
                },
                {
                    "name": "blend_units",
                    "display_label": "Blend Units",
                    "type": "json",
                    "required": False,
                    "help_text": "Usually auto-derived. Only edit if you need manual blending control.",
                },
                {
                    "name": "word_types",
                    "display_label": "Word Types",
                    "type": "json",
                    "required": False,
                    "help_text": "Validation metadata for decodable and sight-word tracking.",
                },
            ],
        ),
        control_actions=["reveal", "play_sound", "mark_students"],
        default_marking={"markable": True, "marking_options": ["secure", "shaky", "missed"]},
    )
)
