from app.schemas.slide_payloads import WordSortPayload
from app.slide_types.base import SlideTypeDefinition, build_editor_config
from app.slide_types.registry import registry


def _summary(payload: dict) -> str:
    categories = payload.get("categories") or []
    labels = [str(item.get("category_label") or "").strip() for item in categories if isinstance(item, dict)]
    labels = [label for label in labels if label]
    return " vs ".join(labels) if labels else "Word Sort"


registry.register(
    SlideTypeDefinition(
        type_key="word_sort",
        label="Word Sort",
        description="Students categorize words into groups by phoneme pattern, vowel sound, or linguistic feature. Supports 2-4 sorting categories.",
        payload_model=WordSortPayload,
        default_payload={
            "instruction_text": "Sort the words into the correct groups",
            "categories": [
                {"category_label": "Group A", "words": []},
                {"category_label": "Group B", "words": []},
            ],
            "audio_per_word": False,
        },
        teacher_template="view_word_sort.html",
        board_template="board_word_sort.html",
        summary_extractor=_summary,
        command_state_defaults=None,
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
                    "name": "instruction_text",
                    "display_label": "Instructions",
                    "type": "text",
                    "required": True,
                    "help_text": "What students should do when sorting the words.",
                }
            ],
            advanced_fields=[
                {
                    "name": "audio_per_word",
                    "display_label": "Audio Per Word",
                    "type": "bool",
                    "required": False,
                    "help_text": "Turn this on if the runtime should offer audio support for each word.",
                }
            ],
            list_fields=[
                {
                    "name": "categories",
                    "type": "list[object]",
                    "display_label": "Categories",
                    "required": True,
                    "help_text": "Define each sorting category and the words that belong in it.",
                    "sub_fields": [
                        {"name": "category_label", "type": "str", "display_label": "Category Label", "required": True},
                        {"name": "words", "type": "list[str]", "display_label": "Words", "required": True},
                    ],
                }
            ],
        ),
        control_actions=["reveal", "play_sound", "mark_students"],
        default_marking={"markable": True, "marking_options": ["secure", "shaky", "missed"]},
    )
)
