"""Shared Jinja2 templates instance with asset fingerprinting support.

All routers should import `templates` from here instead of creating their own
Jinja2Templates instances, so that the `asset_url` global is available everywhere.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi.templating import Jinja2Templates
from app.slide_types import registry

_MANIFEST_PATH = Path(__file__).parent / "static" / "dist" / "manifest.json"
_manifest: dict[str, str] = {}
_manifest_mtime_ns: int | None = None


def _refresh_manifest_if_needed() -> None:
    global _manifest, _manifest_mtime_ns
    try:
        current_mtime_ns = _MANIFEST_PATH.stat().st_mtime_ns
    except FileNotFoundError:
        _manifest = {}
        _manifest_mtime_ns = None
        return

    if _manifest_mtime_ns == current_mtime_ns:
        return

    _manifest = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    _manifest_mtime_ns = current_mtime_ns


def asset_url(name: str) -> str:
    """Return the versioned URL for a static asset.

    Falls back to the bare path if no manifest is present (e.g. fresh checkout
    before running build_static.py).
    """
    _refresh_manifest_if_needed()
    return _manifest.get(name, f"/static/dist/{name}")


def slide_display_content(slide: object) -> str:
    """Extract the primary stimulus text from a slide for board center display."""
    payload = getattr(slide, "content_payload", None)
    if payload is None:
        return str(getattr(slide, "slide_title", ""))
    payload_dict = payload.model_dump() if hasattr(payload, "model_dump") else dict(payload)
    payload_dict.setdefault("slide_title", str(getattr(slide, "slide_title", "")))
    return registry.summary_for(str(getattr(slide, "view_type", "")), payload_dict)


def view_type_label(view_type: str) -> str:
    return registry.label_for(str(view_type))


templates = Jinja2Templates(directory="app/templates")
templates.env.globals["asset_url"] = asset_url
templates.env.globals["slide_display_content"] = slide_display_content
templates.env.globals["view_type_label"] = view_type_label
templates.env.globals["registry_helper"] = registry
