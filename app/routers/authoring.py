from __future__ import annotations

import json
import re
from itertools import groupby
from typing import List, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.schemas.authoring import ValidationResult
from app.schemas.group import GroupCreateRequest, GroupUpdateRequest
from app.services.auth_service import require_current_user
from app.services.group_service import (
    create_group,
    get_group,
    get_group_lesson_counts,
    load_groups,
    reorder_groups,
    update_group,
)
from app.services.lesson_authoring_service import get_lesson as get_lesson_data
from app.services.lesson_authoring_service import (
    create_lesson,
    delete_lesson,
    duplicate_lesson,
    list_lessons,
    move_lesson,
    next_lesson_number_for_unit,
    save_lesson_data,
)
from app.services.lesson_service import parse_lesson
from app.services.pattern_noticing_service import (
    DEFAULT_PATTERN_PROMPT,
    adapt_pattern_noticing_payload,
    is_pattern_noticing_slide,
    segments_to_bracket_word,
)
from app.services.slide_editor_service import add_slide, delete_slide, get_slide, reorder_slides, update_slide
from app.slide_types import registry
from app.template_env import templates

router = APIRouter(prefix="/authoring", tags=["authoring"])


def _is_deprecated_block_option(block_id: str, type_key: str) -> bool:
    deprecated_type_keys = {
        "audio_prompt",
        "minimal_pair",
    }
    if str(type_key) in deprecated_type_keys:
        return True
    return str(block_id) == "02" and str(type_key) == "writing_encoding"


def _parse_csv_list(raw: Optional[str]) -> List[str]:
    return [item.strip() for item in (raw or "").split(",") if item.strip()]


def _parse_lines_or_csv(raw: Optional[str]) -> List[str]:
    values = []
    for chunk in (raw or "").replace(",", "\n").splitlines():
        item = chunk.strip()
        if item:
            values.append(item)
    return values


def _parse_json_text(raw: Optional[str]):
    text = (raw or "").strip()
    if not text:
        return None
    return json.loads(text)


def _field_widget(field: dict) -> dict:
    field_type = field["type"]
    widget = "text"
    input_type = "text"
    options: List[str] = list(field.get("options") or [])
    rows = 3
    if field_type == "bool":
        widget = "checkbox"
    elif field_type == "int":
        input_type = "number"
    elif field_type == "float":
        input_type = "number"
    elif field_type == "text":
        widget = "textarea"
    elif field_type == "str" or "Union[str" in field_type:
        if field.get("multiline"):
            widget = "textarea"
    elif field_type == "list[str]":
        widget = "textarea"
        rows = 4
    elif field_type == "list[object]":
        widget = "item_list"
    elif field_type == "select" or "Literal[" in field_type:
        widget = "select"
        if not options:
            match = re.search(r"Literal\[(.+)\]", field_type)
            if match:
                options = [item.strip().strip("'").strip('"') for item in match.group(1).split(",")]
    else:
        widget = "textarea"
        rows = 6
    result = dict(field)
    result.setdefault("display_label", result.get("label", result["name"].replace("_", " ").title()))
    result.setdefault("help_text", "")
    result.update({"widget": widget, "input_type": input_type, "options": options, "rows": rows})
    return result


def _serialize_field_value(field: dict, value):
    widget = field["widget"]
    if widget == "checkbox":
        return bool(value)
    if widget == "item_list":
        return value or []
    if value is None:
        return ""
    if widget == "textarea" and field["type"] == "list[str]":
        return "\n".join(value or [])
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2)
    return value


def _build_section_fields(fields: List[dict], payload_dict: dict) -> List[dict]:
    prepared_fields = []
    for field in fields:
        if field["name"] == "luminos_says":
            continue
        prepared = _field_widget(field)
        prepared["value"] = _serialize_field_value(prepared, payload_dict.get(field["name"]))
        if prepared.get("sub_fields"):
            prepared["sub_fields"] = [_field_widget(sub_field) for sub_field in prepared["sub_fields"]]
        prepared_fields.append(prepared)
    return prepared_fields


def _build_task_groups(task_fields: List[dict]) -> List[dict]:
    groups = []
    field_map = {field["name"]: field for field in task_fields}
    consumed = set()
    for field in task_fields:
        if field["name"] in consumed:
            continue
        paired_name = field.get("paired_audio")
        paired_field = field_map.get(paired_name) if paired_name else None
        if paired_field is not None:
            consumed.add(field["name"])
            consumed.add(paired_field["name"])
            groups.append({"primary": field, "paired": paired_field, "paired_audio": True})
            continue
        groups.append({"primary": field, "paired": None, "paired_audio": False})
        consumed.add(field["name"])
    return groups


def _resolve_slide_audio_value(slide) -> str:
    explicit = getattr(slide, "slide_audio_url", None)
    if explicit:
        return explicit
    payload = getattr(slide, "content_payload", None)
    if payload is None:
        return ""
    payload_dict = payload.model_dump() if hasattr(payload, "model_dump") else dict(payload)
    for field in ("audio_url", "audio", "audio_file", "audio_prompt", "audio_support", "blend_audio", "word_audio"):
        value = payload_dict.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    items = payload_dict.get("items") or []
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict):
                value = item.get("audio_url")
                if isinstance(value, str) and value.strip():
                    return value.strip()
    return ""


def _build_form_context(definition, payload_dict: dict) -> dict:
    editor_config = definition.resolved_editor_config()
    content_fields = _build_section_fields(editor_config.get("content_fields", []), payload_dict)
    task_fields = _build_section_fields(editor_config.get("task_fields", []), payload_dict)
    advanced_fields = _build_section_fields(editor_config.get("advanced_fields", []), payload_dict)
    list_fields = _build_section_fields(editor_config.get("list_fields", []), payload_dict)
    return {
        "editor_config": editor_config,
        "content_fields": content_fields,
        "task_fields": task_fields,
        "task_groups": _build_task_groups(task_fields),
        "advanced_fields": advanced_fields,
        "list_fields": list_fields,
    }


def _effective_slide_definition_and_payload(slide) -> tuple[object, dict]:
    payload_dict = slide.content_payload.model_dump()
    adapted_pattern = adapt_pattern_noticing_payload(str(slide.view_type), payload_dict)
    if adapted_pattern is not None:
        return registry.get("pattern_noticing"), adapted_pattern
    return registry.get(str(slide.view_type)), payload_dict


def _pattern_word_inputs(payload_dict: dict) -> list[str]:
    words = payload_dict.get("words") or []
    rendered = [
        segments_to_bracket_word((word or {}).get("segments") or [])
        for word in words
    ]
    return [word for word in rendered if word]


def _coerce_payload_field(field: dict, raw_value: Optional[str], is_checked: bool):
    field_type = field["type"]
    text = raw_value if raw_value is not None else ""
    if field_type == "bool":
        return bool(is_checked)
    if field_type == "int":
        return int(text) if text.strip() else None
    if field_type == "float":
        return float(text) if text.strip() else None
    if field_type == "list[str]":
        return _parse_lines_or_csv(text)
    if field_type == "list[object]":
        return _parse_json_text(text) or []
    if field_type == "json":
        return _parse_json_text(text)
    if field_type == "select" or "Literal[" in field_type:
        return text or None
    if field_type in {"str", "text"} or "Union[str" in field_type:
        return text.strip() or None
    return _parse_json_text(text)


def _payload_update_from_form(form, definition) -> dict:
    updates = {}
    for field in definition.resolved_editor_fields():
        if field["name"] == "luminos_says":
            continue
        key = "payload__%s" % field["name"]
        raw_value = form.get(key)
        is_checked = key in form
        if field["required"] and field["type"] in {"str", "text"} and (raw_value is None or not str(raw_value).strip()):
            updates[field["name"]] = None
            continue
        coerced = _coerce_payload_field(field, raw_value, is_checked)
        if coerced is None and field["required"]:
            updates[field["name"]] = raw_value
        elif coerced is not None or field["type"] == "bool":
            updates[field["name"]] = coerced
        elif raw_value is not None:
            # Optional form fields must be able to clear previously saved values.
            updates[field["name"]] = None
    return updates


def _luminos_says_from_form(form) -> Optional[dict]:
    if not any(key.startswith("luminos_says__") for key in form.keys()):
        return None
    prompt = (form.get("luminos_says__prompt_text") or "").strip()
    support = (form.get("luminos_says__support_text") or "").strip()
    enabled = "luminos_says__enabled" in form
    auto_speak = "luminos_says__auto_speak" in form
    if not prompt and not support and not enabled and not auto_speak:
        return None
    return {
        "enabled": enabled,
        "prompt_text": prompt or None,
        "support_text": support or None,
        "auto_speak": auto_speak,
    }


def _format_validation_error(exc: Exception) -> list[str]:
    if hasattr(exc, "errors"):
        messages = []
        for item in exc.errors():
            loc = ".".join(str(part) for part in item.get("loc", []))
            messages.append("%s: %s" % (loc, item.get("msg", "Validation error")))
        return messages or [str(exc)]
    return [str(exc)]


def _validate_lesson_data(lesson_data: dict) -> ValidationResult:
    try:
        parse_lesson(lesson_data)
        return ValidationResult(valid=True, errors=[], warnings=[])
    except Exception as exc:
        return ValidationResult(valid=False, errors=_format_validation_error(exc), warnings=[])


def _render_block_panel(request: Request, lesson_id: str, block_id: str, lesson_data: dict, current_user):
    block = lesson_data["blocks"].get(block_id)
    if block is None:
        raise HTTPException(status_code=404, detail="Block not found")
    slide_labels = {}
    slide_summaries = {}
    for slide in block.get("slides", []):
      payload = dict(slide.get("content_payload", {}))
      adapted_pattern = adapt_pattern_noticing_payload(str(slide.get("view_type") or ""), payload)
      if adapted_pattern is not None:
          slide_labels[str(slide.get("slide_id"))] = registry.label_for("pattern_noticing")
          slide_summaries[str(slide.get("slide_id"))] = registry.summary_for("pattern_noticing", adapted_pattern)
      else:
          slide_labels[str(slide.get("slide_id"))] = registry.label_for(str(slide.get("view_type")))
          slide_summaries[str(slide.get("slide_id"))] = registry.summary_for(str(slide.get("view_type")), payload)
    return templates.TemplateResponse(
        request,
        "authoring/lessons/block_panel.html",
        {
            "lesson_id": lesson_id,
            "block": block,
            "slide_definitions": [
                registry.get(type_key)
                for type_key in registry.all_type_keys()
                if str(block_id) in tuple(registry.get(type_key).allowed_blocks or ())
                and not _is_deprecated_block_option(block_id, type_key)
            ],
            "slide_labels": slide_labels,
            "slide_summaries": slide_summaries,
            "current_user": current_user,
        },
    )


def _authoring_redirect(path: str) -> RedirectResponse:
    return RedirectResponse(url=path, status_code=303)


@router.get("/")
def authoring_home(current_user=Depends(require_current_user)):
    del current_user
    return _authoring_redirect("/authoring/lessons")


@router.get("/media")
def authoring_media_page(request: Request, current_user=Depends(require_current_user)):
    return templates.TemplateResponse(
        request,
        "authoring/media/index.html",
        {"current_user": current_user},
    )


@router.get("/groups")
def authoring_groups(request: Request, current_user=Depends(require_current_user)):
    groups = load_groups()
    counts = get_group_lesson_counts(list_lessons())
    return templates.TemplateResponse(
        request,
        "authoring/groups/index.html",
        {
            "groups": groups,
            "lesson_counts": counts,
            "current_user": current_user,
        },
    )


@router.get("/groups/new")
def authoring_group_new(request: Request, current_user=Depends(require_current_user)):
    groups = load_groups()
    next_number = max((group.group_number for group in groups), default=0) + 1
    suggested_unit_id = "G%s" % next_number
    return templates.TemplateResponse(
        request,
        "authoring/groups/form.html",
        {
            "group": None,
            "form_action": "/authoring/groups",
            "suggested_unit_id": suggested_unit_id,
            "current_user": current_user,
        },
    )


@router.post("/groups")
def authoring_group_create(
    unit_id: str = Form(...),
    title: str = Form(...),
    description: str = Form(""),
    target_phonemes: str = Form(""),
    current_user=Depends(require_current_user),
):
    del current_user
    try:
        create_group(
            GroupCreateRequest(
                unit_id=unit_id,
                title=title,
                description=description,
                target_phonemes=_parse_csv_list(target_phonemes),
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _authoring_redirect("/authoring/groups")


@router.get("/groups/{unit_id}/edit")
def authoring_group_edit(request: Request, unit_id: str, current_user=Depends(require_current_user)):
    group = get_group(unit_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    return templates.TemplateResponse(
        request,
        "authoring/groups/form.html",
        {
            "group": group,
            "form_action": "/authoring/groups/%s" % unit_id,
            "suggested_unit_id": unit_id,
            "current_user": current_user,
        },
    )


@router.post("/groups/{unit_id}")
def authoring_group_update(
    unit_id: str,
    title: str = Form(...),
    description: str = Form(""),
    target_phonemes: str = Form(""),
    current_user=Depends(require_current_user),
):
    del current_user
    try:
        update_group(
            unit_id,
            GroupUpdateRequest(
                title=title,
                description=description,
                target_phonemes=_parse_csv_list(target_phonemes),
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _authoring_redirect("/authoring/groups")


@router.post("/groups/reorder")
def authoring_group_reorder(
    unit_ids: List[str] = Form(...),
    current_user=Depends(require_current_user),
):
    del current_user
    reorder_groups(unit_ids)
    return _authoring_redirect("/authoring/groups")


@router.get("/lessons")
def authoring_lessons(
    request: Request,
    unit_id: Optional[str] = None,
    current_user=Depends(require_current_user),
):
    groups = load_groups()
    lessons = list_lessons(unit_id=unit_id)
    lesson_groups = [
        {"unit_id": key, "lessons": list(items)}
        for key, items in groupby(lessons, key=lambda lesson: lesson["unit_id"])
    ]
    return templates.TemplateResponse(
        request,
        "authoring/lessons/index.html",
        {
            "groups": groups,
            "lessons": lessons,
            "lesson_groups": lesson_groups,
            "selected_unit_id": unit_id or "",
            "current_user": current_user,
        },
    )


@router.get("/lessons/new")
def authoring_lesson_new(
    request: Request,
    unit_id: Optional[str] = None,
    current_user=Depends(require_current_user),
):
    groups = load_groups()
    selected_unit_id = unit_id or (groups[0].unit_id if groups else "")
    suggested_number = next_lesson_number_for_unit(selected_unit_id) if selected_unit_id else 1
    return templates.TemplateResponse(
        request,
        "authoring/lessons/new.html",
        {
            "groups": groups,
            "selected_unit_id": selected_unit_id,
            "suggested_lesson_number": suggested_number,
            "current_user": current_user,
        },
    )


@router.post("/lessons")
def authoring_lesson_create(
    unit_id: str = Form(...),
    lesson_number: int = Form(...),
    title: str = Form(...),
    target_pattern: str = Form(...),
    new_units: str = Form(""),
    new_sight_words: str = Form(""),
    current_user=Depends(require_current_user),
):
    del current_user
    try:
        create_lesson(
            unit_id=unit_id,
            lesson_number=lesson_number,
            title=title,
            target_pattern=target_pattern,
            new_units=_parse_csv_list(new_units),
            new_sight_words=_parse_csv_list(new_sight_words),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _authoring_redirect("/authoring/lessons?unit_id=%s" % unit_id)


@router.post("/lessons/{lesson_id}/duplicate")
def authoring_lesson_duplicate(
    lesson_id: str,
    current_user=Depends(require_current_user),
):
    del current_user
    summaries = [item for item in list_lessons() if item["lesson_id"] == lesson_id]
    if not summaries:
        raise HTTPException(status_code=404, detail="Lesson not found")
    source = summaries[0]
    next_number = next_lesson_number_for_unit(source["unit_id"])
    new_lesson_id = "%s-L%s" % (source["unit_id"], next_number)
    try:
        duplicate_lesson(lesson_id, new_lesson_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _authoring_redirect("/authoring/lessons?unit_id=%s" % source["unit_id"])


@router.post("/lessons/{lesson_id}/move")
def authoring_lesson_move(
    lesson_id: str,
    new_unit_id: str = Form(...),
    current_user=Depends(require_current_user),
):
    del current_user
    try:
        moved = move_lesson(lesson_id, new_unit_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _authoring_redirect("/authoring/lessons?unit_id=%s" % moved["unit_id"])


@router.post("/lessons/{lesson_id}/delete")
def authoring_lesson_delete(
    lesson_id: str,
    current_user=Depends(require_current_user),
):
    del current_user
    if not delete_lesson(lesson_id):
        raise HTTPException(status_code=404, detail="Lesson not found")
    return _authoring_redirect("/authoring/lessons")


@router.get("/lessons/{lesson_id}/edit")
def authoring_lesson_edit(request: Request, lesson_id: str, current_user=Depends(require_current_user)):
    try:
        lesson = parse_lesson(get_lesson_data(lesson_id))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Lesson not found")
    blocks = []
    for block_id, block in lesson.blocks.items():
        blocks.append({"block_id": block_id, "label": block.label, "slide_count": len(block.slides)})
    return templates.TemplateResponse(
        request,
        "authoring/lessons/editor.html",
        {
            "lesson": lesson,
            "blocks": blocks,
            "current_user": current_user,
        },
    )


@router.get("/lessons/{lesson_id}/blocks/{block_id}")
def authoring_lesson_block(request: Request, lesson_id: str, block_id: str, current_user=Depends(require_current_user)):
    try:
        lesson_data = get_lesson_data(lesson_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return _render_block_panel(request, lesson_id, block_id, lesson_data, current_user)


@router.post("/lessons/{lesson_id}/blocks/{block_id}/slides/add")
def authoring_add_slide(
    request: Request,
    lesson_id: str,
    block_id: str,
    view_type: str = Form(...),
    position: Optional[int] = Form(None),
    current_user=Depends(require_current_user),
):
    lesson_data = get_lesson_data(lesson_id)
    try:
        definition = registry.get(view_type)
        if _is_deprecated_block_option(block_id, view_type):
            raise ValueError("Write It is no longer available for new Block 02 slides. Use Listen & Spell instead.")
        if str(block_id) not in tuple(definition.allowed_blocks or ()):
            raise ValueError(f"{definition.label} is not available in Block {block_id}.")
        add_slide(lesson_data, block_id, view_type, position=position)
        save_lesson_data(lesson_id, lesson_data, backup=False)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _render_block_panel(request, lesson_id, block_id, lesson_data, current_user)


@router.post("/lessons/{lesson_id}/blocks/{block_id}/slides/reorder")
def authoring_reorder_slides(
    request: Request,
    lesson_id: str,
    block_id: str,
    slide_id: Optional[str] = Form(None),
    direction: Optional[str] = Form(None),
    slide_ids: Optional[List[str]] = Form(None),
    current_user=Depends(require_current_user),
):
    lesson_data = get_lesson_data(lesson_id)
    block = lesson_data["blocks"].get(block_id)
    if block is None:
        raise HTTPException(status_code=404, detail="Block not found")
    target_order = slide_ids or [slide.get("slide_id") for slide in block.get("slides", [])]
    if slide_id and direction:
        try:
            index = target_order.index(slide_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Slide not found")
        swap_index = index - 1 if direction == "up" else index + 1
        if 0 <= swap_index < len(target_order):
            target_order[index], target_order[swap_index] = target_order[swap_index], target_order[index]
    try:
        reorder_slides(lesson_data, block_id, target_order)
        save_lesson_data(lesson_id, lesson_data, backup=False)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _render_block_panel(request, lesson_id, block_id, lesson_data, current_user)


@router.get("/lessons/{lesson_id}/blocks/{block_id}/slides/{slide_id}")
def authoring_slide_form(request: Request, lesson_id: str, block_id: str, slide_id: str, current_user=Depends(require_current_user)):
    lesson = parse_lesson(get_lesson_data(lesson_id))
    block = lesson.blocks.get(block_id)
    if block is None:
        raise HTTPException(status_code=404, detail="Block not found")
    slide = next((item for item in block.slides if item.slide_id == slide_id), None)
    if slide is None:
        raise HTTPException(status_code=404, detail="Slide not found")
    definition, payload_dict = _effective_slide_definition_and_payload(slide)
    form_context = _build_form_context(definition, payload_dict)
    teacher_prompts = [prompt.model_dump() for prompt in slide.teacher_prompts]
    if str(slide.view_type) == "read_respond" and not teacher_prompts and payload_dict.get("comprehension_prompt"):
        teacher_prompts = [{"text": payload_dict.get("comprehension_prompt"), "audio_url": None}]
    return templates.TemplateResponse(
        request,
        "authoring/lessons/slide_form.html",
        {
            "lesson_id": lesson_id,
            "block_id": block_id,
            "slide": slide,
            "definition": definition,
            "capability_flags": definition.capability_flags,
            "default_marking": definition.default_marking,
            "luminos_says": payload_dict.get("luminos_says"),
            "slide_audio_url": _resolve_slide_audio_value(slide),
            "effective_slide_type": definition.type_key,
            "initialPatternWordInputs": _pattern_word_inputs(payload_dict) if definition.type_key == "pattern_noticing" else [],
            "initialPatternPrompt": payload_dict.get("prompt", DEFAULT_PATTERN_PROMPT) if definition.type_key == "pattern_noticing" else "",
            "initialPatternRevealMode": payload_dict.get("reveal_mode", "sequential") if definition.type_key == "pattern_noticing" else "sequential",
            "teacher_prompts": teacher_prompts,
            "audio_fields": ["audio", "audio_file", "audio_prompt", "audio_support", "blend_audio", "word_audio"],
            "image_fields": ["image"],
            "image_field_values": {
                field["name"]: field.get("value", "")
                for field in (form_context.get("content_fields", []) + form_context.get("advanced_fields", []))
                if field.get("media_type") == "image"
            },
            "audio_field_values": {
                key: value
                for key, value in payload_dict.items()
                if "audio" in str(key) and isinstance(value, str)
            },
            "video_fields": ["video", "video_url"],
            **form_context,
            "current_user": current_user,
        },
    )


@router.post("/lessons/{lesson_id}/blocks/{block_id}/slides/{slide_id}")
async def authoring_update_slide(
    request: Request,
    lesson_id: str,
    block_id: str,
    slide_id: str,
    current_user=Depends(require_current_user),
):
    lesson_data = get_lesson_data(lesson_id)
    slide = get_slide(lesson_data, block_id, slide_id)
    if slide is None:
        raise HTTPException(status_code=404, detail="Slide not found")
    effective_pattern = adapt_pattern_noticing_payload(str(slide["view_type"]), slide.get("content_payload", {}))
    is_pattern_slide = effective_pattern is not None
    definition = registry.get("pattern_noticing") if is_pattern_slide else registry.get(str(slide["view_type"]))
    form = await request.form()
    payload_updates = _payload_update_from_form(form, definition)
    merged_payload = dict(effective_pattern or slide.get("content_payload", {}))
    merged_payload.update(payload_updates)
    luminos_says = _luminos_says_from_form(form)
    if luminos_says is not None:
        if any(value not in (None, "", False) for value in luminos_says.values()):
            merged_payload["luminos_says"] = luminos_says
        else:
            merged_payload.pop("luminos_says", None)
    try:
        validated_payload = definition.payload_model(**merged_payload)
        if str(slide["view_type"]) == "drag_letter" or is_pattern_slide:
            merged_payload = validated_payload.model_dump()
    except Exception as exc:
        return JSONResponse(status_code=400, content={"success": False, "errors": _format_validation_error(exc)})
    teacher_prompts = _parse_json_text(form.get("teacher_prompts"))
    if teacher_prompts is None:
        teacher_prompts = []
    if str(slide["view_type"]) == "read_respond" and not is_pattern_slide:
        if not teacher_prompts:
            return JSONResponse(
                status_code=400,
                content={"success": False, "errors": ["Read & Respond requires at least one Teacher Prompt."]},
            )
        first_prompt_text = str((teacher_prompts[0] or {}).get("text") or "").strip()
        merged_payload["comprehension_prompt"] = first_prompt_text or None
    updates = {
        "payload": merged_payload,
        "view_type": "pattern_noticing" if is_pattern_slide else slide["view_type"],
        "slide_title": (form.get("slide_title") or "").strip(),
        "teacher_cue": (form.get("teacher_cue") or "").strip(),
        "expected_response": (form.get("expected_response") or "").strip(),
        "correction_move": (form.get("correction_move") or "").strip(),
        "observation_note": (form.get("observation_note") or "").strip() or None,
        "slide_audio_url": (form.get("slide_audio_url") or "").strip() or None,
        "teacher_prompts": teacher_prompts,
        "markable": "markable" in form,
    }
    try:
        update_slide(lesson_data, block_id, slide_id, updates)
        save_lesson_data(lesson_id, lesson_data, backup=False)
    except Exception as exc:
        return JSONResponse(status_code=400, content={"success": False, "errors": _format_validation_error(exc)})
    return _render_block_panel(request, lesson_id, block_id, lesson_data, current_user)


@router.post("/lessons/{lesson_id}/blocks/{block_id}/slides/{slide_id}/delete")
def authoring_delete_slide(request: Request, lesson_id: str, block_id: str, slide_id: str, current_user=Depends(require_current_user)):
    lesson_data = get_lesson_data(lesson_id)
    try:
        delete_slide(lesson_data, block_id, slide_id)
        save_lesson_data(lesson_id, lesson_data, backup=False)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _render_block_panel(request, lesson_id, block_id, lesson_data, current_user)


@router.post("/lessons/{lesson_id}/validate")
def authoring_validate_lesson(lesson_id: str, current_user=Depends(require_current_user)):
    del current_user
    lesson_data = get_lesson_data(lesson_id)
    result = _validate_lesson_data(lesson_data)
    if result.valid:
        return HTMLResponse('<div style="padding:10px; border:1px solid #cde; background:#f4fbff;">Lesson is valid.</div>')
    items = "".join("<li>%s</li>" % error for error in result.errors)
    return HTMLResponse('<div style="padding:10px; border:1px solid #f2c2c2; background:#fff5f5;"><strong>Validation failed</strong><ul>%s</ul></div>' % items)


@router.post("/lessons/{lesson_id}/save")
def authoring_save_lesson(lesson_id: str, current_user=Depends(require_current_user)):
    del current_user
    lesson_data = get_lesson_data(lesson_id)
    result = _validate_lesson_data(lesson_data)
    if not result.valid:
        return JSONResponse(status_code=400, content=result.model_dump())
    save_lesson_data(lesson_id, lesson_data, backup=True)
    return HTMLResponse('<div style="padding:10px; border:1px solid #cde; background:#f4fbff;">Lesson saved and backup created.</div>')


@router.get("/lessons/{lesson_id}/preview/{block_id}/{slide_id}/teacher")
def authoring_teacher_preview(request: Request, lesson_id: str, block_id: str, slide_id: str, current_user=Depends(require_current_user)):
    lesson = parse_lesson(get_lesson_data(lesson_id))
    block = lesson.blocks.get(block_id)
    if block is None:
        raise HTTPException(status_code=404, detail="Block not found")
    slide = next((item for item in block.slides if item.slide_id == slide_id), None)
    if slide is None:
        raise HTTPException(status_code=404, detail="Slide not found")
    return templates.TemplateResponse(
        request,
        "authoring/lessons/preview_frame.html",
        {"slide": slide, "mode": "teacher", "current_user": current_user},
    )


@router.get("/lessons/{lesson_id}/preview/{block_id}/{slide_id}/board")
def authoring_board_preview(request: Request, lesson_id: str, block_id: str, slide_id: str, current_user=Depends(require_current_user)):
    lesson = parse_lesson(get_lesson_data(lesson_id))
    block = lesson.blocks.get(block_id)
    if block is None:
        raise HTTPException(status_code=404, detail="Block not found")
    slide = next((item for item in block.slides if item.slide_id == slide_id), None)
    if slide is None:
        raise HTTPException(status_code=404, detail="Slide not found")
    return templates.TemplateResponse(
        request,
        "authoring/lessons/preview_frame.html",
        {"slide": slide, "mode": "board", "current_user": current_user},
    )
