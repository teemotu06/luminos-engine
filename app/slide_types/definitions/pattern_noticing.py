from __future__ import annotations

from app.schemas.slide_payloads import PatternNoticingPayload
from app.services.pattern_noticing_service import DEFAULT_PATTERN_PROMPT, segments_to_bracket_word
from app.slide_types.base import SlideTypeDefinition, build_editor_config
from app.slide_types.registry import registry


def _summary(payload: dict) -> str:
    words = payload.get("words") or []
    rendered = [
        segments_to_bracket_word((word or {}).get("segments") or [])
        for word in words
    ]
    rendered = [word for word in rendered if word]
    return " · ".join(rendered[:2]) or "Pattern Noticing"


registry.register(
    SlideTypeDefinition(
        type_key="pattern_noticing",
        label="Pattern Noticing",
        description="Compare words and notice the shared sound part.",
        payload_model=PatternNoticingPayload,
        default_payload={
            "words": [
                {"segments": [{"text": "s", "highlight": False}, {"text": "at", "highlight": True}]},
                {"segments": [{"text": "at", "highlight": True}]},
            ],
            "prompt": DEFAULT_PATTERN_PROMPT,
            "reveal_mode": "sequential",
        },
        teacher_template="view_pattern_noticing.html",
        board_template="board_pattern_noticing.html",
        summary_extractor=_summary,
        command_state_defaults=None,
        capability_flags={
            "supports_audio": False,
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
                    "name": "words",
                    "display_label": "Words",
                    "type": "list[object]",
                    "required": True,
                    "help_text": "Enter each word in bracket notation, like s[at].",
                },
                {
                    "name": "prompt",
                    "display_label": "Prompt",
                    "type": "text",
                    "required": True,
                    "help_text": "Student-facing pattern noticing prompt.",
                },
                {
                    "name": "reveal_mode",
                    "display_label": "Reveal Mode",
                    "type": "select",
                    "required": True,
                    "options": ["sequential", "all_at_once"],
                    "help_text": "Choose whether words appear one by one or all at once.",
                },
            ],
        ),
        control_actions=["reveal_answer", "mark_students"],
        default_marking={"markable": True, "marking_options": ["secure", "shaky", "missed"]},
        allowed_blocks=("09",),
    )
)
