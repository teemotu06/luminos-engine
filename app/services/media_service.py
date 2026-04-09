from __future__ import annotations

import os
import re
import shutil
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import UploadFile

from app.config import get_upload_dir

ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a"}
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".webm"}

MAX_AUDIO_SIZE = 10 * 1024 * 1024
MAX_IMAGE_SIZE = 5 * 1024 * 1024
MAX_VIDEO_SIZE = 50 * 1024 * 1024

ALLOWED_MIME_TYPES = {
    "audio": {
        "audio/mpeg",
        "audio/mp3",
        "audio/wav",
        "audio/x-wav",
        "audio/wave",
        "audio/ogg",
        "audio/mp4",
        "audio/x-m4a",
        "audio/aac",
    },
    "image": {
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/webp",
        "image/svg+xml",
    },
    "video": {
        "video/mp4",
        "video/webm",
    },
}

MEDIA_CONFIG = {
    "audio": {
        "folder": "audio",
        "extensions": ALLOWED_AUDIO_EXTENSIONS,
        "max_size": MAX_AUDIO_SIZE,
    },
    "image": {
        "folder": "images",
        "extensions": ALLOWED_IMAGE_EXTENSIONS,
        "max_size": MAX_IMAGE_SIZE,
    },
    "video": {
        "folder": "video",
        "extensions": ALLOWED_VIDEO_EXTENSIONS,
        "max_size": MAX_VIDEO_SIZE,
    },
}


def normalize_media_type(media_type: str) -> str:
    value = (media_type or "").strip().lower()
    if value == "images":
        return "image"
    if value not in MEDIA_CONFIG:
        raise ValueError("media_type must be one of: audio, image, images, video")
    return value


def _media_root() -> Path:
    root = get_upload_dir()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _media_dir(media_type: str, subfolder: Optional[str] = None) -> Path:
    normalized = normalize_media_type(media_type)
    folder = MEDIA_CONFIG[normalized]["folder"]
    base = _media_root() / folder
    if subfolder:
        safe_subfolder = _sanitize_subfolder(subfolder)
        if safe_subfolder:
            base = base / safe_subfolder
    base.mkdir(parents=True, exist_ok=True)
    return base


def _sanitize_subfolder(subfolder: str) -> str:
    parts = []
    for raw_part in Path(subfolder).parts:
        part = sanitize_filename(raw_part, preserve_extension=False)
        if part and part not in {".", ".."}:
            parts.append(part)
    return "/".join(parts)


def _file_size(file: UploadFile) -> int:
    stream = file.file
    current = stream.tell()
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(current, os.SEEK_SET)
    return size


def sanitize_filename(filename: str, preserve_extension: bool = True) -> str:
    base_name = Path(filename or "").name
    if preserve_extension:
        stem = Path(base_name).stem
        suffix = Path(base_name).suffix.lower()
    else:
        stem = base_name
        suffix = ""

    ascii_stem = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode("ascii")
    ascii_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", ascii_stem)
    ascii_stem = ascii_stem.strip("._-")
    if not ascii_stem:
        ascii_stem = "upload"
    return ascii_stem + suffix


def validate_upload(file: UploadFile, media_type: str) -> None:
    normalized = normalize_media_type(media_type)
    config = MEDIA_CONFIG[normalized]
    filename = file.filename or ""
    extension = Path(filename).suffix.lower()
    if extension not in config["extensions"]:
        allowed = ", ".join(sorted(config["extensions"]))
        raise ValueError("Invalid file extension for %s. Allowed: %s" % (normalized, allowed))

    content_type = (file.content_type or "").strip().lower()
    if content_type not in ALLOWED_MIME_TYPES[normalized]:
        allowed_types = ", ".join(sorted(ALLOWED_MIME_TYPES[normalized]))
        raise ValueError("Invalid MIME type for %s. Allowed: %s" % (normalized, allowed_types))

    size = _file_size(file)
    if size > int(config["max_size"]):
        raise ValueError("%s file is too large. Maximum size is %s bytes" % (normalized.capitalize(), config["max_size"]))


def save_upload(file: UploadFile, media_type: str, subfolder: Optional[str] = None) -> str:
    normalized = normalize_media_type(media_type)
    validate_upload(file, normalized)
    upload_dir = _media_dir(normalized, subfolder=subfolder)

    safe_name = sanitize_filename(file.filename or "upload")
    timestamp = str(int(time.time()))
    stored_name = "%s_%s" % (timestamp, safe_name)
    destination = upload_dir / stored_name

    file.file.seek(0)
    with destination.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)

    relative_parts = ["", "static", "uploads", MEDIA_CONFIG[normalized]["folder"]]
    if subfolder:
        safe_subfolder = _sanitize_subfolder(subfolder)
        if safe_subfolder:
            relative_parts.extend(safe_subfolder.split("/"))
    relative_parts.append(stored_name)
    return "/".join(relative_parts)


def list_files(media_type: str, subfolder: Optional[str] = None) -> List[Dict[str, object]]:
    directory = _media_dir(media_type, subfolder=subfolder)
    if not directory.exists():
        return []

    files = []
    for path in directory.iterdir():
        if not path.is_file() or path.name.startswith("."):
            continue
        stat = path.stat()
        relative_parts = ["", "static", "uploads", MEDIA_CONFIG[normalize_media_type(media_type)]["folder"]]
        if subfolder:
            safe_subfolder = _sanitize_subfolder(subfolder)
            if safe_subfolder:
                relative_parts.extend(safe_subfolder.split("/"))
        relative_parts.append(path.name)
        files.append({
            "filename": path.name,
            "path": "/".join(relative_parts),
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "_modified_ts": stat.st_mtime,
        })

    files.sort(key=lambda item: item["_modified_ts"], reverse=True)
    for item in files:
        item.pop("_modified_ts", None)
    return files


def delete_file(media_type: str, filename: str) -> bool:
    normalized = normalize_media_type(media_type)
    safe_name = sanitize_filename(filename)
    target = _media_dir(normalized) / safe_name
    if not target.exists() or not target.is_file():
        return False
    target.unlink()
    return True


def human_readable_size(size: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    value = float(size)
    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            if unit == "B":
                return "%d %s" % (int(value), unit)
            return "%.1f %s" % (value, unit)
        value /= 1024.0
    return "%d B" % int(size)
