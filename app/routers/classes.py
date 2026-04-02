from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.requests import Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.auth_service import require_class_access, require_current_user
from app.services.class_service import (
    add_student_to_class,
    archive_class,
    create_class,
    get_all_classes,
    get_class_with_students,
    restore_class,
)

router = APIRouter(prefix="/classes", tags=["classes"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def class_list(request: Request, db: Session = Depends(get_db), current_user=Depends(require_current_user)):
    owner_user_id = None if current_user.role == "admin" else str(current_user.id)
    classes = get_all_classes(db, owner_user_id=owner_user_id, include_deleted=False)
    archived_classes = get_all_classes(db, owner_user_id=owner_user_id, include_deleted=True)
    archived_classes = [cls for cls in archived_classes if cls["deleted_at"] is not None]
    return templates.TemplateResponse(
        request,
        "classes/index.html",
        {"classes": classes, "archived_classes": archived_classes, "current_user": current_user},
    )


@router.get("/new")
def new_class_form(request: Request, current_user=Depends(require_current_user)):
    return templates.TemplateResponse(
        request,
        "classes/new.html",
        {"error": None, "current_user": current_user},
    )


@router.post("/new")
def create_class_submit(
    request: Request,
    class_name: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    name = class_name.strip()
    if not name:
        return templates.TemplateResponse(
            request,
            "classes/new.html",
            {"error": "Class name cannot be empty", "current_user": current_user},
            status_code=422,
        )
    cls = create_class(
        db,
        class_name=name,
        description=description.strip() or None,
        owner_user_id=None if current_user.role == "admin" else str(current_user.id),
    )
    return RedirectResponse(url=f"/classes/{cls.id}", status_code=303)


@router.get("/{class_id}")
def class_detail(
    request: Request,
    class_id: str,
    error: str = "",
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    require_class_access(db, current_user, class_id, include_deleted=True)
    cls = get_class_with_students(db, class_id, include_deleted=True)
    if cls is None:
        raise HTTPException(status_code=404, detail="Class not found")
    return templates.TemplateResponse(
        request,
        "classes/detail.html",
        {"cls": cls, "error": error, "current_user": current_user},
    )


@router.post("/{class_id}/students")
def add_student(
    class_id: str,
    student_name: str = Form(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    require_class_access(db, current_user, class_id)
    try:
        add_student_to_class(db, class_id=class_id, student_name=student_name)
    except ValueError as exc:
        return RedirectResponse(
            url=f"/classes/{class_id}?error={str(exc)}",
            status_code=303,
        )
    return RedirectResponse(url=f"/classes/{class_id}", status_code=303)


@router.post("/{class_id}/archive")
def archive_class_submit(
    class_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    require_class_access(db, current_user, class_id)
    archive_class(db, class_id)
    return RedirectResponse(url="/classes/", status_code=303)


@router.post("/{class_id}/restore")
def restore_class_submit(
    class_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    require_class_access(db, current_user, class_id, include_deleted=True)
    restore_class(db, class_id)
    return RedirectResponse(url=f"/classes/{class_id}", status_code=303)
