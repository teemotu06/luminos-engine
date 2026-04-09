from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.requests import Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.auth_service import require_class_access, require_current_user
from app.services.student_service import get_student_profile
from app.template_env import templates

router = APIRouter(prefix="/students", tags=["students"])


@router.get("/{student_name}/profile")
def student_profile(
    request: Request,
    student_name: str,
    class_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    if class_id is None:
        raise HTTPException(status_code=400, detail="class_id is required")
    require_class_access(db, current_user, class_id, include_deleted=True)
    profile = get_student_profile(db, student_name, class_id=class_id)
    return templates.TemplateResponse(
        request,
        "students/profile.html",
        {
            **profile,
            "current_user": current_user,
        },
    )
