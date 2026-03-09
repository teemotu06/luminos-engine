from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from app.services.lesson_navigation import flatten_lesson_slides
from app.services.lesson_service import load_lesson

router = APIRouter(prefix="/lesson", tags=["lesson"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/{lesson_id}")
def get_lesson(request: Request, lesson_id: str, slide_index: int = 0):
    lesson = load_lesson(lesson_id)
    ordered_slides = flatten_lesson_slides(lesson)

    if not ordered_slides:
        current_index = 0
    else:
        current_index = max(0, min(slide_index, len(ordered_slides) - 1))

    return templates.TemplateResponse(
        "lesson/view.html",
        {
            "request": request,
            "lesson": lesson,
            "ordered_slides": ordered_slides,
            "current_index": current_index,
        },
    )