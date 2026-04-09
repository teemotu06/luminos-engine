import os
from pathlib import Path
from typing import Iterable


def env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_csv(name: str) -> list[str]:
    raw = os.getenv(name, "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def get_admin_secret() -> str:
    return os.getenv("LUMINOS_ADMIN_SECRET", "").strip()


def allowed_origins() -> list[str]:
    return env_csv("ALLOWED_ORIGINS")


def json_log_format_enabled() -> bool:
    return os.getenv("LOG_FORMAT", "text").strip().lower() == "json"


def parse_rate_limit_specs(value: str, default: Iterable[tuple[str, int, int]]) -> list[tuple[str, int, int]]:
    specs: list[tuple[str, int, int]] = []
    raw = (value or "").strip()
    if not raw:
        return list(default)

    for chunk in raw.split(","):
        item = chunk.strip()
        if not item:
            continue
        try:
            path, limit, window = item.split(":", 2)
            specs.append((path.strip(), int(limit), int(window)))
        except ValueError as exc:
            raise RuntimeError(
                f"Invalid rate limit spec '{item}'. Expected '<path-prefix>:<limit>:<window-seconds>'."
            ) from exc
    return specs


def get_upload_dir() -> Path:
    raw = os.getenv("UPLOAD_DIR", "").strip()
    if raw:
        return Path(raw)
    return Path(__file__).resolve().parent / "static" / "uploads"
