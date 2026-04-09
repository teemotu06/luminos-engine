from app.schemas.slide_payloads import ConnectWordToPicturePayload
from app.slide_types.base import SlideTypeDefinition, build_editor_config
from app.slide_types.registry import registry


def _summary(payload: dict) -> str:
    items = payload.get("items") or []
    words = [str(item.get("word") or "").strip() for item in items if isinstance(item, dict)]
    words = [word for word in words if word]
    return ", ".join(words) if words else "No items"


registry.register(
    SlideTypeDefinition(
        type_key="connect_word_to_picture",
        label="Connect Word to Picture",
        description="Students match written words to corresponding images. Supports audio pronunciation playback per item.",
        payload_model=ConnectWordToPicturePayload,
        default_payload={
            "instruction_text": "Match each word to its picture",
            "shuffle_items": True,
            "items": [
                {"word": "", "image_url": "", "audio_url": None},
                {"word": "", "image_url": "", "audio_url": None},
            ],
        },
        teacher_template="view_connect_word_to_picture.html",
        board_template="board_connect_word_to_picture.html",
        summary_extractor=_summary,
        command_state_defaults=None,
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
                    "name": "instruction_text",
                    "display_label": "Instructions",
                    "type": "text",
                    "required": True,
                    "help_text": "What students should do on this matching slide.",
                },
            ],
            advanced_fields=[
                {
                    "name": "shuffle_items",
                    "display_label": "Shuffle Items",
                    "type": "bool",
                    "required": False,
                    "help_text": "Turn this on to randomize the order of words and pictures.",
                }
            ],
            list_fields=[
                {
                    "name": "items",
                    "type": "list[object]",
                    "display_label": "Match Items",
                    "required": True,
                    "help_text": "Each row pairs a word with its picture and optional pronunciation audio.",
                    "sub_fields": [
                        {"name": "word", "type": "str", "display_label": "Word", "required": True},
                        {
                            "name": "image_url",
                            "type": "str",
                            "display_label": "Image",
                            "required": True,
                            "media_type": "image",
                        },
                        {
                            "name": "audio_url",
                            "type": "str",
                            "display_label": "Audio",
                            "required": False,
                            "media_type": "audio",
                        },
                    ],
                }
            ],
        ),
        control_actions=["reveal", "play_sound", "mark_students"],
        default_marking={"markable": True, "marking_options": ["secure", "shaky", "missed"]},
    )
)
