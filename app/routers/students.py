from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.requests import Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.student_service import get_student_profile

router = APIRouter(prefix="/students", tags=["students"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/{student_name}/profile")
def student_profile(
    request: Request,
    student_name: str,
    class_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    profile = get_student_profile(db, student_name, class_id=class_id)
    return templates.TemplateResponse(
        "students/profile.html",
        {
            "request": request,
            **profile,
        },
    )
