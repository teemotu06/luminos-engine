from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from app.services.block_registry import get_block_body_partial
from app.services.lesson_service import load_lesson

router = APIRouter(prefix="/lesson", tags=["lesson"])
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["get_block_body_partial"] = get_block_body_partial


@router.get("/{lesson_id}")
def get_lesson(request: Request, lesson_id: str):
    lesson = load_lesson(lesson_id)
    return templates.TemplateResponse(
        "lesson/view.html",
        {
            "request": request,
            "lesson": lesson,
        },
    )