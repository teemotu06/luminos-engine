from app.schemas.slide_payloads import QuickCheckPayload
from app.slide_types.base import SlideTypeDefinition, build_editor_config
from app.slide_types.registry import registry


def _summary(payload: dict) -> str:
    return str(payload.get("title") or payload.get("slide_title") or "")


registry.register(
    SlideTypeDefinition(
        type_key="quick_check",
        label="Quick Check",
        description="Mark one or more quick-check items.",
        payload_model=QuickCheckPayload,
        default_payload={"title": "Quick Check", "check_items": [{"label": "Check 1", "phoneme": None}]},
        teacher_template="view_quick_check.html",
        board_template="board_quick_check.html",
        summary_extractor=_summary,
        command_state_defaults=None,
        capability_flags={
            "supports_audio": False,
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
                    "name": "title",
                    "display_label": "Title",
                    "type": "str",
                    "required": False,
                    "help_text": "Short title for the quick check.",
                },
            ],
            advanced_fields=[
                {
                    "name": "display_mode",
                    "display_label": "Display Mode",
                    "type": "str",
                    "required": False,
                    "help_text": "Advanced runtime setting. Usually left alone.",
                },
                {
                    "name": "notes_field",
                    "display_label": "Teacher Notes",
                    "type": "text",
                    "required": False,
                    "help_text": "Optional note for the teacher about this check.",
                },
                {
                    "name": "marking_options",
                    "display_label": "Quick Check Marking Options",
                    "type": "list[str]",
                    "required": False,
                    "help_text": "Optional per-item marking options used by the quick check slide itself.",
                },
            ],
            list_fields=[
                {
                    "name": "check_items",
                    "display_label": "Check Items",
                    "type": "list[object]",
                    "required": True,
                    "help_text": "The items you want to quickly check.",
                    "sub_fields": [
                        {"name": "label", "type": "str", "display_label": "Label", "required": True},
                        {"name": "phoneme", "type": "str", "display_label": "Phoneme", "required": False},
                    ],
                }
            ],
        ),
        control_actions=["reveal", "mark_students"],
        default_marking={"markable": False, "marking_options": []},
    )
)
