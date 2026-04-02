MARK_STATUSES = ("secure", "shaky", "missed", "deferred", "absent")
LEGACY_MARK_STATUS_ALIASES = {"skipped": "deferred"}


def normalize_mark_status(status: str) -> str:
    normalized = LEGACY_MARK_STATUS_ALIASES.get((status or "").strip().lower(), (status or "").strip().lower())
    if normalized not in MARK_STATUSES:
        return normalized
    return normalized
