from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.auth_service import (
    SESSION_COOKIE_NAME,
    authenticate_user,
    auth_required,
    create_session_cookie,
    get_current_user_optional,
)


router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/login")
def login_form(
    request: Request,
    next: str = "/lesson/",
    error: str = "",
    current_user=Depends(get_current_user_optional),
):
    if current_user is not None:
        return RedirectResponse(url=next or "/lesson/", status_code=303)
    if not auth_required():
        return RedirectResponse(url="/lesson/", status_code=303)
    return templates.TemplateResponse(
        request,
        "auth/login.html",
        {
            "error": error,
            "next": next or "/lesson/",
            "current_user": None,
        },
    )


@router.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/lesson/"),
    db: Session = Depends(get_db),
):
    if not auth_required():
        return RedirectResponse(url="/lesson/", status_code=303)
    user = authenticate_user(db, username=username, password=password)
    if user is None:
        login_target = f"/auth/login?next={quote(next or '/lesson/')}&error={quote('Invalid username or password')}"
        return RedirectResponse(url=login_target, status_code=303)
    response = RedirectResponse(url=next or "/lesson/", status_code=303)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        create_session_cookie(str(user.id)),
        httponly=True,
        samesite="lax",
    )
    return response


@router.post("/logout")
def logout(request: Request):
    response = RedirectResponse(url="/auth/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response
