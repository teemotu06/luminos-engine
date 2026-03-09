from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routers.lesson import router as lesson_router

app = FastAPI(title="LUMINOS Lesson Engine")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(lesson_router)


@app.get("/")
def root():
    return {"status": "ok", "app": "LUMINOS Lesson Engine"}