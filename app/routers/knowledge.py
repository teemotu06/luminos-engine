"""knowledge router — course plan and public holiday management."""
from __future__ import annotations

import json
import logging
from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.requests import Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.lesson import ClassRecord
from app.services.auth_service import require_class_access, require_current_user
from app.services.knowledge_service import (
    add_holiday,
    create_or_update_course_plan,
    delete_holiday,
    get_course_plan,
    get_curriculum,
    list_curricula,
    list_holidays,
    plan_summary,
    teaching_day_labels,
)
from app.template_env import templates

router = APIRouter(prefix="/knowledge", tags=["knowledge"])
logger = logging.getLogger(__name__)

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


# ── Plan preview (JSON) ───────────────────────────────────────────────────────

@router.get("/plan/preview")
def plan_preview(
    curriculum_id: str,
    start_date: str,
    teaching_days: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    """Return a quick schedule summary without persisting anything.
    teaching_days is a comma-separated list of ints, e.g. '0,2,4'.
    """
    try:
        parsed_date = date.fromisoformat(start_date)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid start_date")

    try:
        td = [int(d.strip()) for d in teaching_days.split(",") if d.strip()]
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid teaching_days")

    curriculum = get_curriculum(curriculum_id)
    if curriculum is None:
        raise HTTPException(status_code=422, detail="Unknown curriculum")

    if not td:
        raise HTTPException(status_code=422, detail="No teaching days selected")

    from app.services.knowledge_service import (
        _curriculum_lesson_ids,
        calculate_lesson_schedule,
        get_holiday_date_set,
    )
    lesson_ids = _curriculum_lesson_ids(curriculum_id)
    holidays = get_holiday_date_set(db)
    schedule, end_date = calculate_lesson_schedule(lesson_ids, parsed_date, td, holidays)

    return {
        "total_lessons": len(schedule),
        "end_date": end_date.isoformat() if end_date else None,
        "teaching_day_labels": teaching_day_labels(td),
    }


# ── Course plan view ──────────────────────────────────────────────────────────

@router.get("/plan/{class_id}")
def view_plan(
    request: Request,
    class_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    cls = require_class_access(db, current_user, class_id, include_deleted=True)
    plan = get_course_plan(db, class_id)
    curriculum = get_curriculum(plan.curriculum_id) if plan else None

    # Group schedule entries by unit for display
    schedule_by_unit: list[dict] = []
    if plan:
        current_unit = None
        for entry in plan.lesson_schedule:
            if entry["unit_id"] != current_unit:
                current_unit = entry["unit_id"]
                schedule_by_unit.append({"unit_id": current_unit, "lessons": []})
            schedule_by_unit[-1]["lessons"].append(entry)

    summary = plan_summary(plan, curriculum) if plan else None

    return templates.TemplateResponse(
        request,
        "knowledge/plan.html",
        {
            "cls": cls,
            "class_id": class_id,
            "plan": plan,
            "summary": summary,
            "schedule_by_unit": schedule_by_unit,
            "curricula": list_curricula(),
            "day_names": DAY_NAMES,
            "current_user": current_user,
        },
    )


@router.post("/plan/{class_id}")
def save_plan(
    request: Request,
    class_id: str,
    curriculum_id: str = Form(...),
    start_date_str: str = Form(..., alias="start_date"),
    teaching_days_json: str = Form("[]"),
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    require_class_access(db, current_user, class_id)

    try:
        start_date = date.fromisoformat(start_date_str)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid start date")

    try:
        teaching_days = json.loads(teaching_days_json)
        teaching_days = [int(d) for d in teaching_days]
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail="Invalid teaching days")

    if not teaching_days:
        raise HTTPException(status_code=422, detail="Select at least one teaching day")

    curriculum = get_curriculum(curriculum_id)
    if curriculum is None:
        raise HTTPException(status_code=422, detail="Unknown curriculum")

    try:
        create_or_update_course_plan(
            db,
            class_id=class_id,
            curriculum_id=curriculum_id,
            start_date=start_date,
            teaching_days=teaching_days,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return RedirectResponse(url=f"/knowledge/plan/{class_id}", status_code=303)


# ── Holiday management ────────────────────────────────────────────────────────

@router.get("/holidays")
def holiday_list(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    holidays = list_holidays(db)
    return templates.TemplateResponse(
        request,
        "knowledge/holidays.html",
        {"holidays": holidays, "error": None, "current_user": current_user},
    )


@router.post("/holidays")
def add_holiday_submit(
    request: Request,
    holiday_date_str: str = Form(..., alias="holiday_date"),
    name: str = Form(...),
    region: str = Form(""),
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    try:
        hdate = date.fromisoformat(holiday_date_str)
    except ValueError:
        holidays = list_holidays(db)
        return templates.TemplateResponse(
            request,
            "knowledge/holidays.html",
            {"holidays": holidays, "error": "Invalid date format", "current_user": current_user},
            status_code=422,
        )

    name = name.strip()
    if not name:
        holidays = list_holidays(db)
        return templates.TemplateResponse(
            request,
            "knowledge/holidays.html",
            {"holidays": holidays, "error": "Holiday name cannot be empty", "current_user": current_user},
            status_code=422,
        )

    try:
        add_holiday(db, hdate, name, region.strip() or None)
    except Exception:
        holidays = list_holidays(db)
        return templates.TemplateResponse(
            request,
            "knowledge/holidays.html",
            {"holidays": holidays, "error": "That date is already registered", "current_user": current_user},
            status_code=409,
        )

    return RedirectResponse(url="/knowledge/holidays", status_code=303)


@router.post("/holidays/{holiday_id}/delete")
def delete_holiday_submit(
    holiday_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user),
):
    delete_holiday(db, holiday_id)
    return RedirectResponse(url="/knowledge/holidays", status_code=303)
