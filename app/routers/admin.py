"""Admin-only endpoints. Intended for use by the server operator, not teachers."""
import logging
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import get_admin_secret
from app.db import get_db
from app.services.kokoro_tts_service import get_tts_health_snapshot, prune_tts_cache
from app.services.lesson_service import invalidate_lesson_id_cache
from app.services.review_scheduler_service import force_rebuild_class_review_records

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

def _check_secret(x_admin_secret: Optional[str] = Header(default=None)) -> None:
    secret = get_admin_secret()
    if not secret:
        logger.error("Admin endpoint requested while LUMINOS_ADMIN_SECRET is unset")
        raise HTTPException(status_code=503, detail="Admin endpoints unavailable")
    if not x_admin_secret or not secrets.compare_digest(x_admin_secret, secret):
        raise HTTPException(status_code=403, detail="Forbidden")


@router.post("/rebuild-review-records")
def admin_rebuild_review_records(
    _authorized: None = Depends(_check_secret),
    db: Session = Depends(get_db),
):
    """Wipe and replay all class_pattern_review records from existing attempt history.
    Also clears the lesson-ID cache so any new lesson files on disk are picked up.

    Requires the X-Admin-Secret header to match LUMINOS_ADMIN_SECRET.
    """
    invalidate_lesson_id_cache()
    count = force_rebuild_class_review_records(db)
    return {"ok": True, "attempts_processed": count}


@router.post("/clear-lesson-cache")
def admin_clear_lesson_cache(_authorized: None = Depends(_check_secret)):
    """Invalidate the lesson-ID cache so new or removed lesson files are picked up
    without a full server restart.
    """
    invalidate_lesson_id_cache()
    return {"ok": True}


@router.get("/tts-health")
def admin_tts_health(run_check: bool = True, _authorized: None = Depends(_check_secret)):
    """Return a TTS readiness snapshot for operators.

    Requires the X-Admin-Secret header to match LUMINOS_ADMIN_SECRET.
    """
    return get_tts_health_snapshot(run_check=run_check)


@router.post("/tts-prune-cache")
def admin_tts_prune_cache(max_age_days: int = 30, _authorized: None = Depends(_check_secret)):
    """Delete old cached TTS WAV files.

    Requires the X-Admin-Secret header to match LUMINOS_ADMIN_SECRET.
    """
    return {"ok": True, **prune_tts_cache(max_age_days=max_age_days)}
