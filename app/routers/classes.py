from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.requests import Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.class_service import (
    add_student_to_class,
    create_class,
    get_all_classes,
    get_class_with_students,
)

router = APIRouter(prefix="/classes", tags=["classes"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def class_list(request: Request, db: Session = Depends(get_db)):
    classes = get_all_classes(db)
    return templates.TemplateResponse(
        "classes/index.html",
        {"request": request, "classes": classes},
    )


@router.get("/new")
def new_class_form(request: Request):
    return templates.TemplateResponse(
        "classes/new.html",
        {"request": request, "error": None},
    )


@router.post("/new")
def create_class_submit(
    request: Request,
    class_name: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    name = class_name.strip()
    if not name:
        return templates.TemplateResponse(
            "classes/new.html",
            {"request": request, "error": "Class name cannot be empty"},
            status_code=422,
        )
    cls = create_class(db, class_name=name, description=description.strip() or None)
    return RedirectResponse(url=f"/classes/{cls.id}", status_code=303)


@router.get("/{class_id}")
def class_detail(request: Request, class_id: str, error: str = "", db: Session = Depends(get_db)):
    cls = get_class_with_students(db, class_id)
    if cls is None:
        raise HTTPException(status_code=404, detail="Class not found")
    return templates.TemplateResponse(
        "classes/detail.html",
        {"request": request, "cls": cls, "error": error},
    )


@router.post("/{class_id}/students")
def add_student(
    class_id: str,
    student_name: str = Form(...),
    db: Session = Depends(get_db),
):
    try:
        add_student_to_class(db, class_id=class_id, student_name=student_name)
    except ValueError as exc:
        return RedirectResponse(
            url=f"/classes/{class_id}?error={str(exc)}",
            status_code=303,
        )
    return RedirectResponse(url=f"/classes/{class_id}", status_code=303)
