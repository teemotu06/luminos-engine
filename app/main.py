import logging
import os

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.db import Base, DATABASE_URL, SessionLocal, engine
from app.models import (
    ClassPatternReviewRecord,
    ClassRecord,
    LessonAttemptRecord,
    LessonRecord,
    OralCheckAssignmentRecord,
    OralCheckSessionRecord,
    SlideResultRecord,
    StudentMarkRecord,
    StudentRecord,
)
from app.routers.admin import router as admin_router
from app.routers.classes import router as classes_router
from app.routers.lesson import router as lesson_router
from app.routers.students import router as students_router
from app.services.kokoro_tts_service import KokoroTtsError, TTS_CACHE_DIR, prune_tts_cache, warmup_tts_runtime
from app.services.lesson_service import sync_all_lessons
from app.services.review_scheduler_service import rebuild_class_review_records

logger = logging.getLogger(__name__)
TTS_PREWARM_ENABLED = os.getenv("LUMINOS_TTS_PREWARM_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
TTS_STRICT_STARTUP = os.getenv("LUMINOS_TTS_STRICT_STARTUP", "false").lower() in {"1", "true", "yes", "on"}
TTS_PRUNE_ON_STARTUP = os.getenv("LUMINOS_TTS_CACHE_PRUNE_ON_STARTUP", "true").lower() in {"1", "true", "yes", "on"}

app = FastAPI(title="LUMINOS Lesson Engine")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/tts-cache", StaticFiles(directory=str(TTS_CACHE_DIR)), name="tts-cache")
app.include_router(lesson_router)
app.include_router(students_router)
app.include_router(classes_router)
app.include_router(admin_router)


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)

    try:
        with engine.connect() as conn:
            if DATABASE_URL.startswith("postgresql"):
                # Add class_id column if missing.
                conn.execute(
                    text("ALTER TABLE lesson_attempt ADD COLUMN IF NOT EXISTS class_id VARCHAR(36)")
                )
                conn.commit()
            else:
                # SQLite: check via PRAGMA before attempting ALTER to avoid swallowing real errors.
                result = conn.execute(text("PRAGMA table_info(lesson_attempt)"))
                existing_cols = [row[1] for row in result.fetchall()]
                if "class_id" not in existing_cols:
                    conn.execute(text("ALTER TABLE lesson_attempt ADD COLUMN class_id TEXT"))
                    conn.commit()
                # SQLite does not support ALTER TABLE ADD CONSTRAINT — the FK declared in the
                # model only takes effect on newly created tables. Existing SQLite databases
                # retain the old column definition; referential integrity is enforced at the
                # application layer (rebuild_class_review_records, cascade deletes in service
                # layer) rather than at the DB level.
    except Exception as exc:
        logger.warning("Startup migration warning (may be safe to ignore): %s", exc)

    with SessionLocal() as db:
        sync_all_lessons(db)
        rebuild_class_review_records(db)

    if TTS_PRUNE_ON_STARTUP:
        prune_tts_cache()

    if TTS_PREWARM_ENABLED:
        try:
            warmup_tts_runtime()
        except KokoroTtsError as exc:
            if TTS_STRICT_STARTUP:
                raise
            logger.warning("Kokoro TTS warmup warning: %s", exc)


@app.get("/")
def root():
    return RedirectResponse(url="/lesson/")
