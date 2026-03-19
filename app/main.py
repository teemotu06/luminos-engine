from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.db import Base, DATABASE_URL, SessionLocal, engine
from app.models import ClassRecord, LessonAttemptRecord, LessonRecord, SlideResultRecord, StudentMarkRecord, StudentRecord
from app.routers.classes import router as classes_router
from app.routers.lesson import router as lesson_router
from app.routers.students import router as students_router
from app.services.lesson_service import sync_all_lessons

app = FastAPI(title="LUMINOS Lesson Engine")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(lesson_router)
app.include_router(students_router)
app.include_router(classes_router)


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    # Migrate class_id column onto existing lesson_attempt tables
    try:
        with engine.connect() as conn:
            if DATABASE_URL.startswith("postgresql"):
                conn.execute(
                    text("ALTER TABLE lesson_attempt ADD COLUMN IF NOT EXISTS class_id VARCHAR(36)")
                )
            else:
                conn.execute(
                    text("ALTER TABLE lesson_attempt ADD COLUMN class_id TEXT")
                )
            conn.commit()
    except Exception:
        pass  # Column already exists

    with SessionLocal() as db:
        sync_all_lessons(db)


@app.get("/")
def root():
    return RedirectResponse(url="/lesson/")
