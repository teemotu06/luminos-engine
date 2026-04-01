"""Admin-only endpoints. Intended for use by the server operator, not teachers."""
import logging
import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.kokoro_tts_service import get_tts_health_snapshot, prune_tts_cache
from app.services.lesson_service import invalidate_lesson_id_cache
from app.services.review_scheduler_service import force_rebuild_class_review_records

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

_ADMIN_SECRET = os.environ.get("LUMINOS_ADMIN_SECRET", "")

if not _ADMIN_SECRET:
    logger.warning(
        "LUMINOS_ADMIN_SECRET is not set. Admin endpoints are unprotected. "
        "Set this environment variable before deploying to production."
    )


def _check_secret(secret: str = "") -> None:
    if _ADMIN_SECRET and secret != _ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.post("/rebuild-review-records")
def admin_rebuild_review_records(
    secret: str = "",
    db: Session = Depends(get_db),
):
    """Wipe and replay all class_pattern_review records from existing attempt history.
    Also clears the lesson-ID cache so any new lesson files on disk are picked up.

    Requires LUMINOS_ADMIN_SECRET env var to be set, then pass ?secret=<value>.
    """
    _check_secret(secret)
    invalidate_lesson_id_cache()
    count = force_rebuild_class_review_records(db)
    return {"ok": True, "attempts_processed": count}


@router.post("/clear-lesson-cache")
def admin_clear_lesson_cache(secret: str = ""):
    """Invalidate the lesson-ID cache so new or removed lesson files are picked up
    without a full server restart.
    """
    _check_secret(secret)
    invalidate_lesson_id_cache()
    return {"ok": True}


@router.get("/tts-health")
def admin_tts_health(secret: str = "", run_check: bool = True):
    """Return a TTS readiness snapshot for operators.

    Requires LUMINOS_ADMIN_SECRET env var to be set, then pass ?secret=<value>.
    """
    _check_secret(secret)
    return get_tts_health_snapshot(run_check=run_check)


@router.post("/tts-prune-cache")
def admin_tts_prune_cache(secret: str = "", max_age_days: int = 30):
    """Delete old cached TTS WAV files.

    Requires LUMINOS_ADMIN_SECRET env var to be set, then pass ?secret=<value>.
    """
    _check_secret(secret)
    return {"ok": True, **prune_tts_cache(max_age_days=max_age_days)}
