from __future__ import annotations

from app.schemas.command_state import LuminosRuntimeStateConfig
from app.schemas.slide_payloads import ReadRespondPayload
from app.services.command_runtime_profiles import BLOCK_RUNTIME_PROFILES
from app.slide_types.base import SlideTypeDefinition, build_editor_config
from app.slide_types.registry import registry


def _summary(payload: dict) -> str:
    return str(payload.get("text_content") or payload.get("slide_title") or "")


def _defaults(slide, block_id) -> list[LuminosRuntimeStateConfig]:
    payload = slide.content_payload
    teacher_cue = slide.teacher_cue or ""
    prompt_text = getattr(payload, "prompt_text", None)
    display_mode = getattr(payload, "display_mode", "") or ""
    comprehension_prompt = getattr(payload, "comprehension_prompt", "") or ""
    profile = BLOCK_RUNTIME_PROFILES.get((str(block_id), "read_respond"))

    if display_mode == "sentence":
        states = [
            LuminosRuntimeStateConfig(
                key="transition",
                board_prompt="Eyes on the sentence.",
                teacher_prompt=teacher_cue or "Set tracking and attention.",
                tts_prompt="Eyes on the sentence.",
                teacher_controls=["replay", "force_advance"],
            ),
            LuminosRuntimeStateConfig(
                key="choral",
                board_prompt="Everyone. Read the sentence.",
                teacher_prompt=teacher_cue or "Take a choral sentence read.",
                tts_prompt="Everyone. Read the sentence.",
                teacher_controls=["mark_class", "replay", "force_advance"],
            ),
        ]
        if profile == "sentence_bridge":
            states.insert(
                1,
                LuminosRuntimeStateConfig(
                    key="partner_practice",
                    board_prompt="Read with your partner.",
                    teacher_prompt="Give a short partner read before whole-class check.",
                    tts_prompt="Read with your partner.",
                    timeout_ms=12000,
                    teacher_controls=["pause", "force_advance"],
                ),
            )
        if comprehension_prompt:
            states.append(
                LuminosRuntimeStateConfig(
                    key="check",
                    board_prompt=comprehension_prompt,
                    teacher_prompt=teacher_cue or "Take a brief oral answer, then mark the class.",
                    tts_prompt=comprehension_prompt,
                    teacher_controls=["mark_class", "replay", "force_advance"],
                )
            )
        return states

    if display_mode == "spot_part":
        support_text = getattr(payload, "support_text", "") or prompt_text or slide.slide_title
        states = [
            LuminosRuntimeStateConfig(
                key="transition",
                board_prompt="Look carefully.",
                teacher_prompt=teacher_cue or "Set attention on the displayed words.",
                tts_prompt="Look carefully.",
                teacher_controls=["replay", "force_advance"],
            ),
            LuminosRuntimeStateConfig(
                key="check",
                board_prompt=support_text,
                teacher_prompt=teacher_cue or "Take one or two oral answers, then mark the class.",
                tts_prompt=support_text,
                teacher_controls=["mark_class", "replay", "force_advance"],
            ),
        ]
        if profile == "pattern_notice":
            states[1].board_prompt = support_text
            states[1].teacher_prompt = teacher_cue or "Take one or two oral answers, then mark the class."
        return states

    return []


registry.register(
    SlideTypeDefinition(
        type_key="read_respond",
        label="Read & Respond",
        description="Read text, respond, and optionally run oral-check behaviors.",
        payload_model=ReadRespondPayload,
        default_payload={"text_content": "I sat."},
        teacher_template="view_read_respond.html",
        board_template="board_read_respond.html",
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
                    "name": "text_content",
                    "display_label": "Reader Text",
                    "type": "text",
                    "required": False,
                    "help_text": "The sentence, passage, or text students read on screen.",
                },
                {
                    "name": "comprehension_prompt",
                    "display_label": "Comprehension Question",
                    "type": "text",
                    "required": False,
                    "help_text": "Optional question students answer after reading.",
                },
                {
                    "name": "image",
                    "display_label": "Image",
                    "type": "str",
                    "required": False,
                    "media_type": "image",
                    "help_text": "Optional image support for the reading task.",
                },
            ],
            task_fields=[
                {
                    "name": "prompt_text",
                    "display_label": "Student Prompt",
                    "type": "text",
                    "required": False,
                    "help_text": "Optional prompt for what students should do with the text.",
                    "paired_audio": "audio_support",
                },
                {
                    "name": "audio_support",
                    "display_label": "Audio File",
                    "type": "str",
                    "required": False,
                    "media_type": "audio",
                    "help_text": "Optional audio support for the reading task.",
                },
            ],
            advanced_fields=[
                {
                    "name": "display_mode",
                    "display_label": "Display Mode",
                    "type": "str",
                    "required": False,
                    "help_text": "Usually set automatically. Only edit if you need a specific runtime display pattern.",
                },
                {
                    "name": "displayed_words",
                    "display_label": "Displayed Words",
                    "type": "list[str]",
                    "required": False,
                    "help_text": "Only edit if you need a manual word list on screen.",
                },
                {
                    "name": "highlight_pattern",
                    "display_label": "Highlight Pattern",
                    "type": "str",
                    "required": False,
                    "help_text": "Optional pattern to highlight in the text.",
                },
                {
                    "name": "highlighted_chunk",
                    "display_label": "Highlighted Chunk",
                    "type": "str",
                    "required": False,
                    "help_text": "Optional chunk to emphasize for teacher-led notice work.",
                },
                {
                    "name": "support_text",
                    "display_label": "Support Text",
                    "type": "text",
                    "required": False,
                    "help_text": "Optional supporting text shown during response routines.",
                },
                {
                    "name": "comprehension_questions",
                    "display_label": "Comprehension Questions",
                    "type": "list[str]",
                    "required": False,
                    "help_text": "Optional question set for comprehension discussion.",
                },
                {
                    "name": "show_font_controls",
                    "display_label": "Show Font Controls",
                    "type": "bool",
                    "required": False,
                    "help_text": "Advanced runtime option. Usually left off.",
                },
                {
                    "name": "word_types",
                    "display_label": "Word Types",
                    "type": "json",
                    "required": False,
                    "help_text": "Validation metadata used for decodable and sight-word tracking.",
                },
                {
                    "name": "token_units",
                    "display_label": "Token Units",
                    "type": "json",
                    "required": False,
                    "help_text": "Validation metadata for phoneme-level token mapping.",
                },
                {
                    "name": "oral_enforcement",
                    "display_label": "Oral Enforcement",
                    "type": "json",
                    "required": False,
                    "help_text": "Advanced oral-check configuration. Only edit if you need manual control.",
                },
                {
                    "name": "target_word",
                    "display_label": "Target Word",
                    "type": "str",
                    "required": False,
                    "help_text": "Optional target word for spot-part or pattern focus routines.",
                },
                {
                    "name": "phoneme_parts",
                    "display_label": "Phoneme Parts",
                    "type": "list[str]",
                    "required": False,
                    "help_text": "Optional phoneme breakdown for manual blend work.",
                },
                {
                    "name": "blend_audio",
                    "display_label": "Blend Audio",
                    "type": "str",
                    "required": False,
                    "media_type": "audio",
                    "help_text": "Optional audio for blended reading support.",
                },
                {
                    "name": "word_audio",
                    "display_label": "Word Audio",
                    "type": "str",
                    "required": False,
                    "media_type": "audio",
                    "help_text": "Optional audio for the target word.",
                },
            ],
        ),
        control_actions=["read_sentence", "reveal", "mark_students"],
        default_marking={"markable": True, "marking_options": ["secure", "shaky", "missed"]},
    )
)
