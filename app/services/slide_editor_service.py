from __future__ import annotations

import copy
from uuid import uuid4
from typing import Optional

from app.schemas.slide_payloads import TeacherPrompt
from app.slide_types import registry


REQUIRED_TEACHING_FIELDS = (
    "teacher_cue",
)


def _clean_marking_options(value) -> list[str]:
    options = []
    for item in value or []:
        text = str(item).strip()
        if text:
            options.append(text)
    return options


def _apply_marking_defaults(slide: dict) -> None:
    definition = registry.get(str(slide.get("view_type")))
    default_marking = dict(definition.default_marking or {})
    markable = bool(slide.get("markable"))
    slide["markable"] = markable
    # Marking options are locked to registry defaults to ensure Smart Review data consistency.
    if markable and not slide["marking_options"]:
        slide["marking_options"] = _clean_marking_options(
            default_marking.get("marking_options") or ["secure", "shaky", "missed"]
        )
    elif markable:
        slide["marking_options"] = _clean_marking_options(
            default_marking.get("marking_options") or ["secure", "shaky", "missed"]
        )
    else:
        slide["marking_options"] = []


def _validate_teaching_fields(slide: dict) -> None:
    missing = [field for field in REQUIRED_TEACHING_FIELDS if not str(slide.get(field) or "").strip()]
    if missing:
        raise ValueError("Missing required teaching script fields: %s" % ", ".join(missing))


def _validate_teacher_prompts(slide: dict) -> None:
    prompts = slide.get("teacher_prompts") or []
    validated = []
    for prompt in prompts:
        validated.append(TeacherPrompt(**prompt).model_dump())
    slide["teacher_prompts"] = validated


def _get_block(lesson_data: dict, block_id: str) -> dict:
    try:
        return lesson_data["blocks"][block_id]
    except KeyError as exc:
        raise ValueError("Unknown block_id: %s" % block_id) from exc


def get_slide(lesson_data: dict, block_id: str, slide_id: str) -> Optional[dict]:
    block = _get_block(lesson_data, block_id)
    for slide in block.get("slides", []):
        if slide.get("slide_id") == slide_id:
            return slide
    return None


def add_slide(lesson_data: dict, block_id: str, view_type: str, payload: Optional[dict] = None, position: Optional[int] = None) -> dict:
    block = _get_block(lesson_data, block_id)
    definition = registry.get(view_type)
    slide_payload = copy.deepcopy(payload if payload is not None else definition.default_payload)
    slide = {
        "slide_id": "%s_%s" % (view_type, uuid4().hex[:8]),
        "block_id": block_id,
        "slide_title": definition.label,
        "view_type": view_type,
        "content_payload": slide_payload,
        "teacher_cue": "",
        "expected_response": "",
        "correction_move": "",
        "observation_note": "",
        "slide_audio_url": None,
        "teacher_prompts": [],
        "korean_interference_flag": None,
        "markable": bool(definition.default_marking.get("markable", True)),
        "marking_options": _clean_marking_options(
            definition.default_marking.get("marking_options", ["secure", "shaky", "missed"])
        ),
        "next_action": "manual_next",
    }
    slides = block.setdefault("slides", [])
    if position is None or position >= len(slides):
        slides.append(slide)
    else:
        slides.insert(max(position, 0), slide)
    return lesson_data


def update_slide(lesson_data: dict, block_id: str, slide_id: str, updates: dict) -> dict:
    slide = get_slide(lesson_data, block_id, slide_id)
    if slide is None:
        raise ValueError("Slide not found: %s" % slide_id)

    for key, value in updates.items():
        if key == "payload":
            current_payload = copy.deepcopy(slide.get("content_payload", {}))
            current_payload.update(copy.deepcopy(value or {}))
            slide["content_payload"] = current_payload
        elif key == "luminos_says":
            current_payload = copy.deepcopy(slide.get("content_payload", {}))
            if value:
                current_payload["luminos_says"] = copy.deepcopy(value)
            else:
                current_payload.pop("luminos_says", None)
            slide["content_payload"] = current_payload
        else:
            slide[key] = value
    _apply_marking_defaults(slide)
    _validate_teaching_fields(slide)
    _validate_teacher_prompts(slide)
    return lesson_data


def delete_slide(lesson_data: dict, block_id: str, slide_id: str) -> dict:
    block = _get_block(lesson_data, block_id)
    slides = block.get("slides", [])
    filtered = [slide for slide in slides if slide.get("slide_id") != slide_id]
    if len(filtered) == len(slides):
        raise ValueError("Slide not found: %s" % slide_id)
    block["slides"] = filtered
    return lesson_data


def reorder_slides(lesson_data: dict, block_id: str, slide_ids: list[str]) -> dict:
    block = _get_block(lesson_data, block_id)
    slides = block.get("slides", [])
    current_ids = [slide.get("slide_id") for slide in slides]
    if sorted(current_ids) != sorted(slide_ids):
        raise ValueError("slide_ids must match the block's current slide set exactly.")
    slide_map = {slide.get("slide_id"): slide for slide in slides}
    block["slides"] = [slide_map[slide_id] for slide_id in slide_ids]
    return lesson_data
