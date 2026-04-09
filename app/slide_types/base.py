from __future__ import annotations

from typing import Any, Callable, Optional, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field


def _annotation_name(annotation: Any) -> str:
    origin = get_origin(annotation)
    if origin is None:
        if isinstance(annotation, type):
            return annotation.__name__
        return str(annotation)
    if origin is list:
        args = get_args(annotation)
        inner = _annotation_name(args[0]) if args else "Any"
        return f"list[{inner}]"
    if origin is dict:
        args = get_args(annotation)
        if len(args) == 2:
            return f"dict[{_annotation_name(args[0])}, {_annotation_name(args[1])}]"
        return "dict"
    if origin is tuple:
        args = get_args(annotation)
        inner = ", ".join(_annotation_name(arg) for arg in args)
        return f"tuple[{inner}]"
    if origin is Callable:
        return "callable"
    if origin is Optional:
        args = get_args(annotation)
        inner = _annotation_name(args[0]) if args else "Any"
        return f"optional[{inner}]"
    args = get_args(annotation)
    if args:
        return f"{getattr(origin, '__name__', str(origin))}[{', '.join(_annotation_name(arg) for arg in args)}]"
    return getattr(origin, "__name__", str(origin))


def build_editor_fields(payload_model: type[BaseModel]) -> list[dict]:
    fields: list[dict] = []
    for name, field in payload_model.model_fields.items():
        fields.append(
            {
                "name": name,
                "type": _annotation_name(field.annotation),
                "label": name.replace("_", " ").title(),
                "required": field.is_required(),
            }
        )
    return fields


def build_editor_config(
    *,
    content_fields: Optional[list[dict]] = None,
    task_fields: Optional[list[dict]] = None,
    advanced_fields: Optional[list[dict]] = None,
    list_fields: Optional[list[dict]] = None,
) -> dict:
    return {
        "content_fields": list(content_fields or []),
        "task_fields": list(task_fields or []),
        "advanced_fields": list(advanced_fields or []),
        "list_fields": list(list_fields or []),
    }


def _is_audio_field(field: dict) -> bool:
    name = str(field.get("name") or "")
    if field.get("media_type") == "audio":
        return True
    if name == "audio_per_word":
        return False
    return "audio" in name


def _filter_list_field(field: dict) -> dict:
    filtered = dict(field)
    sub_fields = []
    for sub_field in filtered.get("sub_fields", []) or []:
        if _is_audio_field(sub_field):
            continue
        sub_fields.append(dict(sub_field))
    filtered["sub_fields"] = sub_fields
    return filtered


def legacy_editor_config(editor_fields: Optional[list[dict]]) -> dict:
    content_fields = []
    list_fields = []
    for field in editor_fields or []:
        normalized = dict(field)
        if "display_label" not in normalized and "label" in normalized:
            normalized["display_label"] = normalized["label"]
        normalized.setdefault("help_text", "")
        if normalized.get("type") == "list[object]":
            list_fields.append(normalized)
        else:
            content_fields.append(normalized)
    return build_editor_config(content_fields=content_fields, list_fields=list_fields)


def flatten_editor_config(editor_config: Optional[dict]) -> list[dict]:
    if not editor_config:
        return []
    fields: list[dict] = []
    for section_name in ("content_fields", "task_fields", "advanced_fields", "list_fields"):
        for field in editor_config.get(section_name, []) or []:
            item = dict(field)
            item.setdefault("section", section_name)
            fields.append(item)
    return fields


class SlideTypeDefinition(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    type_key: str
    label: str
    description: str
    payload_model: type[BaseModel]
    default_payload: dict
    teacher_template: str
    board_template: str
    summary_extractor: Callable[[Any], str]
    command_state_defaults: Optional[Callable[[Any, Any], list]]
    capability_flags: dict[str, bool]
    editor_config: dict = Field(default_factory=dict)
    editor_fields: Optional[list[dict]] = None
    control_actions: list[str] = Field(default_factory=list)
    default_marking: dict = Field(
        default_factory=lambda: {"markable": True, "marking_options": ["secure", "shaky"]}
    )
    cognitive_load_profile: Optional[dict] = None
    allowed_blocks: tuple[str, ...] = (
        "01",
        "02",
        "03",
        "04",
        "05",
        "06",
        "07",
        "08",
        "09",
        "10",
    )

    def resolved_editor_config(self) -> dict:
        if self.editor_config:
            content_fields = [dict(field) for field in self.editor_config.get("content_fields", []) if not _is_audio_field(field)]
            advanced_fields = [dict(field) for field in self.editor_config.get("advanced_fields", []) if not _is_audio_field(field)]
            list_fields = [_filter_list_field(field) for field in self.editor_config.get("list_fields", [])]
            return build_editor_config(
                content_fields=content_fields,
                task_fields=[],
                advanced_fields=advanced_fields,
                list_fields=list_fields,
            )
        return legacy_editor_config(self.editor_fields or build_editor_fields(self.payload_model))

    def resolved_editor_fields(self) -> list[dict]:
        return flatten_editor_config(self.resolved_editor_config())
