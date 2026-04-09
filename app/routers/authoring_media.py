from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.requests import Request
from fastapi.responses import JSONResponse

from app.services.auth_service import require_current_user
from app.services.media_service import (
    delete_file,
    human_readable_size,
    list_files,
    normalize_media_type,
    save_upload,
)
from app.template_env import templates

router = APIRouter(prefix="/authoring/media", tags=["authoring"])


def _accept_for(media_type: str) -> str:
    normalized = normalize_media_type(media_type)
    if normalized == "audio":
        return ".mp3,.wav,.ogg,.m4a,audio/*"
    if normalized == "image":
        return ".png,.jpg,.jpeg,.gif,.webp,.svg,image/*"
    return ".mp4,.webm,video/*"


@router.post("/upload")
def upload_media(
    request: Request,
    file: UploadFile = File(...),
    media_type: str = Form(...),
    subfolder: Optional[str] = Form(default=None),
    show_library: str = Form(default="true"),
    current_user=Depends(require_current_user),
):
    del current_user
    normalized = normalize_media_type(media_type)
    show_library_bool = str(show_library).strip().lower() != "false"
    try:
        stored_path = save_upload(file, normalized, subfolder=subfolder)
    except ValueError as exc:
        if request.headers.get("HX-Request") == "true":
            return templates.TemplateResponse(
                request,
                "authoring/media/browser.html",
                {
                    "media_type": normalized,
                    "files": list_files(normalized, subfolder=subfolder),
                    "human_readable_size": human_readable_size,
                    "accept_value": _accept_for(normalized),
                    "subfolder": subfolder or "",
                    "upload_error": str(exc),
                    "show_library": show_library_bool,
                    "recent_upload_path": "",
                },
                status_code=400,
            )
        return JSONResponse(status_code=400, content={"success": False, "error": str(exc)})

    if request.headers.get("HX-Request") == "true":
        files = list_files(normalized, subfolder=subfolder)
        if not show_library_bool:
            files = [item for item in files if item.get("path") == stored_path]
        return templates.TemplateResponse(
            request,
            "authoring/media/browser.html",
            {
                "media_type": normalized,
                "files": files,
                "human_readable_size": human_readable_size,
                "accept_value": _accept_for(normalized),
                "subfolder": subfolder or "",
                "upload_error": "",
                "show_library": show_library_bool,
                "recent_upload_path": stored_path,
            },
        )
    return {
        "success": True,
        "path": stored_path,
        "filename": Path(stored_path).name,
    }


@router.get("/browse/{media_type}")
def browse_media(
    request: Request,
    media_type: str,
    subfolder: Optional[str] = None,
    show_library: str = "true",
    current_user=Depends(require_current_user),
):
    del current_user
    normalized = normalize_media_type(media_type)
    files = list_files(normalized, subfolder=subfolder)
    show_library_bool = str(show_library).strip().lower() != "false"
    if not show_library_bool:
        files = []
    return templates.TemplateResponse(
        request,
        "authoring/media/browser.html",
        {
            "media_type": normalized,
            "files": files,
            "human_readable_size": human_readable_size,
            "accept_value": _accept_for(normalized),
            "subfolder": subfolder or "",
            "upload_error": "",
            "show_library": show_library_bool,
            "recent_upload_path": "",
        },
    )


@router.delete("/{media_type}/{filename}")
def delete_media(
    media_type: str,
    filename: str,
    current_user=Depends(require_current_user),
):
    del current_user
    normalized = normalize_media_type(media_type)
    deleted = delete_file(normalized, filename)
    return {"success": deleted, "deleted": deleted, "filename": Path(filename).name}
