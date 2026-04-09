from app.schemas.slide_payloads import DragWordPayload
from app.slide_types.base import SlideTypeDefinition, build_editor_config
from app.slide_types.registry import registry


def _summary(payload: dict) -> str:
    return str(payload.get("target_sentence") or payload.get("slide_title") or "")


registry.register(
    SlideTypeDefinition(
        type_key="drag_word",
        label="Arrange",
        description="Arrange words into the target sentence.",
        payload_model=DragWordPayload,
        default_payload={"target_sentence": "I sat", "word_cards": ["I", "sat"]},
        teacher_template="view_drag_word.html",
        board_template="board_drag_word.html",
        summary_extractor=_summary,
        command_state_defaults=None,
        capability_flags={
            "supports_audio": False,
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
                    "name": "target_sentence",
                    "display_label": "Target Sentence",
                    "type": "text",
                    "required": True,
                    "help_text": "The sentence students should build in order.",
                },
                {
                    "name": "word_cards",
                    "display_label": "Word Tiles",
                    "type": "list[str]",
                    "required": True,
                    "help_text": "The words available for arranging the sentence.",
                },
                {
                    "name": "image",
                    "display_label": "Image",
                    "type": "str",
                    "required": False,
                    "media_type": "image",
                    "help_text": "Optional picture support for the sentence.",
                },
            ],
            advanced_fields=[
                {
                    "name": "punctuation_card",
                    "display_label": "Punctuation Tile",
                    "type": "str",
                    "required": False,
                    "help_text": "Optional punctuation tile if you want students to place punctuation separately.",
                },
            ],
        ),
        control_actions=["reveal", "mark_students"],
        default_marking={"markable": True, "marking_options": ["secure", "shaky", "missed"]},
    )
)
