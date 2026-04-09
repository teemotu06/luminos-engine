from app.schemas.slide_payloads import AudioPromptPayload
from app.slide_types.base import SlideTypeDefinition, build_editor_config
from app.slide_types.registry import registry


def _summary(payload: dict) -> str:
    return str(payload.get("prompt_text") or payload.get("slide_title") or "")


registry.register(
    SlideTypeDefinition(
        type_key="audio_prompt",
        label="Listen",
        description="Play audio and optionally reveal supporting text or image.",
        payload_model=AudioPromptPayload,
        default_payload={"audio_file": "/static/audio/example.mp3", "prompt_text": "Listen."},
        teacher_template="view_audio_prompt.html",
        board_template="board_audio_prompt.html",
        summary_extractor=_summary,
        command_state_defaults=None,
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
                    "name": "reveal_text",
                    "display_label": "Reveal Text",
                    "type": "text",
                    "required": False,
                    "help_text": "Optional text you reveal after students listen.",
                },
                {
                    "name": "image",
                    "display_label": "Image",
                    "type": "str",
                    "required": False,
                    "media_type": "image",
                    "help_text": "Optional image shown with the listening prompt.",
                },
            ],
            task_fields=[
                {
                    "name": "prompt_text",
                    "display_label": "Student Prompt",
                    "type": "text",
                    "required": True,
                    "help_text": "What students should do while listening.",
                    "paired_audio": "audio_file",
                },
                {
                    "name": "audio_file",
                    "display_label": "Audio File",
                    "type": "str",
                    "required": True,
                    "media_type": "audio",
                    "help_text": "The audio students hear for this listening task.",
                },
            ],
        ),
        control_actions=["play_audio", "reveal_answer", "mark_students"],
        default_marking={"markable": True, "marking_options": ["secure", "shaky", "missed"]},
    )
)
