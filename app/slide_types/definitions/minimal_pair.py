from app.schemas.slide_payloads import MinimalPairPayload
from app.slide_types.base import SlideTypeDefinition, build_editor_config
from app.slide_types.registry import registry


def _summary(payload: dict) -> str:
    pair_a = payload.get("pair_A") or {}
    pair_b = payload.get("pair_B") or {}
    a = str(pair_a.get("label", ""))
    b = str(pair_b.get("label", ""))
    return f"{a} / {b}" if a and b else str(payload.get("slide_title") or "")


registry.register(
    SlideTypeDefinition(
        type_key="minimal_pair",
        label="Listen & Choose",
        description="Choose between two contrasting audio labels.",
        payload_model=MinimalPairPayload,
        default_payload={
            "pair_A": {"label": "A", "audio": "/static/audio/a.mp3"},
            "pair_B": {"label": "B", "audio": "/static/audio/b.mp3"},
            "correct_choice": "A",
        },
        teacher_template="view_minimal_pair.html",
        board_template="board_minimal_pair.html",
        summary_extractor=_summary,
        command_state_defaults=None,
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
                    "name": "pair_A",
                    "display_label": "Choice A",
                    "type": "json",
                    "required": True,
                    "help_text": "Label and audio for the first choice.",
                },
                {
                    "name": "pair_B",
                    "display_label": "Choice B",
                    "type": "json",
                    "required": True,
                    "help_text": "Label and audio for the second choice.",
                },
                {
                    "name": "correct_choice",
                    "display_label": "Correct Choice",
                    "type": "select",
                    "options": ["A", "B"],
                    "required": True,
                    "help_text": "Which choice is correct.",
                },
            ],
            advanced_fields=[
                {
                    "name": "korean_flag",
                    "display_label": "Korean Interference Flag",
                    "type": "str",
                    "required": False,
                    "help_text": "Only edit if you are tracking a known transfer pattern.",
                },
                {
                    "name": "correction_routine",
                    "display_label": "Correction Routine",
                    "type": "text",
                    "required": False,
                    "help_text": "Optional custom correction wording for this listening contrast.",
                },
            ],
        ),
        control_actions=["play_sound", "reveal_answer", "mark_students"],
        default_marking={"markable": True, "marking_options": ["secure", "shaky", "missed"]},
    )
)
