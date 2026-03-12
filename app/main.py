from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db import Base, SessionLocal, engine
from app.models import LessonAttemptRecord, LessonRecord, SlideResultRecord
from app.routers.lesson import router as lesson_router
from app.services.lesson_service import sync_all_lessons

app = FastAPI(title="LUMINOS Lesson Engine")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(lesson_router)


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        sync_all_lessons(db)


@app.get("/")
def root():
    return {"status": "ok", "app": "LUMINOS Lesson Engine"}
