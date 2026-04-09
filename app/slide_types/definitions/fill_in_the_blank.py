from app.schemas.slide_payloads import FillInTheBlankPayload
from app.slide_types.base import SlideTypeDefinition, build_editor_config
from app.slide_types.registry import registry


def _summary(payload: dict) -> str:
    text = str(payload.get("sentence_template") or payload.get("slide_title") or "")
    return text if len(text) <= 60 else text[:57] + "..."


registry.register(
    SlideTypeDefinition(
        type_key="fill_in_the_blank",
        label="Fill in the Blank",
        description="Students complete a sentence by filling in a missing word. Supports multiple-choice distractors and audio/image context.",
        payload_model=FillInTheBlankPayload,
        default_payload={
            "sentence_template": "The ___ is red.",
            "correct_answer": "cat",
            "distractors": [],
            "hint_text": None,
            "audio_url": None,
            "image_url": None,
        },
        teacher_template="view_fill_in_the_blank.html",
        board_template="board_fill_in_the_blank.html",
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
                    "name": "sentence_template",
                    "display_label": "Sentence with Blank",
                    "type": "text",
                    "required": True,
                    "help_text": "Write the sentence with a blank marker like ___ where students fill in the missing word.",
                },
                {
                    "name": "correct_answer",
                    "display_label": "Correct Answer",
                    "type": "str",
                    "required": True,
                    "help_text": "The word that correctly fills the blank.",
                },
                {
                    "name": "image_url",
                    "display_label": "Image",
                    "type": "str",
                    "required": False,
                    "media_type": "image",
                    "help_text": "Optional picture support for sentence meaning.",
                },
                {
                    "name": "audio_url",
                    "display_label": "Audio File",
                    "type": "str",
                    "required": False,
                    "media_type": "audio",
                    "help_text": "Optional audio of the full sentence.",
                },
            ],
            advanced_fields=[
                {
                    "name": "distractors",
                    "display_label": "Wrong Answers (optional)",
                    "type": "list[str]",
                    "required": False,
                    "help_text": "Optional multiple-choice distractors for the blank.",
                },
                {
                    "name": "hint_text",
                    "display_label": "Hint (optional)",
                    "type": "str",
                    "required": False,
                    "help_text": "Optional hint if students need support.",
                },
            ],
        ),
        control_actions=["reveal", "play_audio", "mark_students"],
        default_marking={"markable": True, "marking_options": ["secure", "shaky", "missed"]},
    )
)
