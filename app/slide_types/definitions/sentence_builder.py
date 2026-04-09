from app.schemas.slide_payloads import SentenceBuilderPayload
from app.slide_types.base import SlideTypeDefinition, build_editor_config
from app.slide_types.registry import registry


def _summary(payload: dict) -> str:
    text = str(payload.get("target_sentence") or payload.get("slide_title") or "")
    return text if len(text) <= 60 else text[:57] + "..."


registry.register(
    SlideTypeDefinition(
        type_key="sentence_builder",
        label="Sentence Builder",
        description="Students arrange word tiles into the correct sentence order. Supports distractor tiles and audio/image context. Aligned with structured sentence construction research.",
        payload_model=SentenceBuilderPayload,
        default_payload={
            "target_sentence": "I can read.",
            "word_tiles": ["I", "can", "read."],
            "has_distractors": False,
            "image_url": None,
            "audio_url": None,
        },
        teacher_template="view_sentence_builder.html",
        board_template="board_sentence_builder.html",
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
                    "name": "target_sentence",
                    "display_label": "Target Sentence",
                    "type": "text",
                    "required": True,
                    "help_text": "The correct sentence students should build.",
                },
                {
                    "name": "word_tiles",
                    "display_label": "Word Tiles",
                    "type": "list[str]",
                    "required": True,
                    "help_text": "The word or phrase tiles students arrange into the sentence.",
                },
                {
                    "name": "image_url",
                    "display_label": "Image",
                    "type": "str",
                    "required": False,
                    "media_type": "image",
                    "help_text": "Optional image support for sentence meaning.",
                },
                {
                    "name": "audio_url",
                    "display_label": "Audio File",
                    "type": "str",
                    "required": False,
                    "media_type": "audio",
                    "help_text": "Optional audio of the completed sentence.",
                },
            ],
            advanced_fields=[
                {
                    "name": "has_distractors",
                    "display_label": "Has Distractors",
                    "type": "bool",
                    "required": False,
                    "help_text": "Turn this on if some tiles are distractors and do not belong in the sentence.",
                }
            ],
        ),
        control_actions=["reveal", "play_audio", "mark_students"],
        default_marking={"markable": True, "marking_options": ["secure", "shaky", "missed"]},
    )
)
