"""knowledge_service — curriculum definitions, course planning, and lesson scheduling.

Scheduling contract:
  - One lesson is assigned per teaching day (no doubling up).
  - Teaching days are weekday indices: 0=Monday … 6=Sunday.
  - Public holidays are skipped; the lesson moves to the next available teaching day.
  - The schedule is stored as JSON on CoursePlanRecord so it can be read without
    re-running the algorithm on every page load.
"""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.knowledge import CoursePlanRecord, PublicHolidayRecord
from app.services.lesson_service import list_lesson_ids

logger = logging.getLogger(__name__)

CURRICULA_PATH = Path("app/content/curricula.json")

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


# ── Curriculum helpers ────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def _load_curricula_raw() -> list[dict]:
    return json.loads(CURRICULA_PATH.read_text(encoding="utf-8"))


def list_curricula() -> list[dict]:
    """Return all curriculum definitions enriched with lesson_count."""
    raw = _load_curricula_raw()
    result = []
    for c in raw:
        lesson_ids = _curriculum_lesson_ids(c["id"])
        result.append({**c, "lesson_count": len(lesson_ids)})
    return result


def get_curriculum(curriculum_id: str) -> Optional[dict]:
    for c in list_curricula():
        if c["id"] == curriculum_id:
            return c
    return None


def _curriculum_lesson_ids(curriculum_id: str) -> list[str]:
    """Return the ordered lesson IDs for a curriculum, derived from lesson files."""
    raw = _load_curricula_raw()
    curriculum = next((c for c in raw if c["id"] == curriculum_id), None)
    if curriculum is None:
        return []
    unit_ids = set(curriculum.get("unit_ids", []))
    all_ids = list_lesson_ids()
    return [lid for lid in all_ids if _lesson_unit(lid) in unit_ids]


def _lesson_unit(lesson_id: str) -> str:
    """Extract the unit prefix from a lesson_id, e.g. 'G1-L3' → 'G1'."""
    return lesson_id.split("-")[0] if "-" in lesson_id else ""


# ── Schedule calculation ──────────────────────────────────────────────────────


def calculate_lesson_schedule(
    lesson_ids: list[str],
    start_date: date,
    teaching_days: list[int],
    holiday_dates: set[date],
) -> tuple[list[dict], Optional[date]]:
    """Assign one lesson per teaching day, skipping holidays.

    Returns (schedule, end_date) where schedule is a list of dicts:
      {lesson_id, lesson_index, unit_id, scheduled_date (ISO string)}
    """
    if not lesson_ids or not teaching_days:
        return [], None

    teaching_day_set = set(teaching_days)
    schedule: list[dict] = []

    def next_teaching_date(from_date: date) -> date:
        d = from_date
        for _ in range(5 * 365):  # guard: never loop beyond 5 years
            if d.weekday() in teaching_day_set and d not in holiday_dates:
                return d
            d += timedelta(days=1)
        raise ValueError("Could not find an available teaching date within 5 years")

    current = next_teaching_date(start_date)

    for idx, lesson_id in enumerate(lesson_ids):
        schedule.append({
            "lesson_index": idx + 1,
            "lesson_id": lesson_id,
            "unit_id": _lesson_unit(lesson_id),
            "scheduled_date": current.isoformat(),
        })
        current = next_teaching_date(current + timedelta(days=1))

    end_date = date.fromisoformat(schedule[-1]["scheduled_date"]) if schedule else start_date
    return schedule, end_date


# ── Holiday helpers ───────────────────────────────────────────────────────────


def list_holidays(db: Session, *, region: Optional[str] = None) -> list[PublicHolidayRecord]:
    query = select(PublicHolidayRecord).order_by(PublicHolidayRecord.holiday_date)
    if region is not None:
        query = query.where(PublicHolidayRecord.region == region)
    return db.execute(query).scalars().all()


def get_holiday_date_set(db: Session) -> set[date]:
    """Return all holiday dates as a set for fast membership testing."""
    rows = db.execute(select(PublicHolidayRecord.holiday_date)).scalars().all()
    return set(rows)


def add_holiday(
    db: Session,
    holiday_date: date,
    name: str,
    region: Optional[str] = None,
) -> PublicHolidayRecord:
    record = PublicHolidayRecord(holiday_date=holiday_date, name=name.strip(), region=region or None)
    db.add(record)
    db.commit()
    db.refresh(record)
    logger.info("holiday.added date=%s name=%s", holiday_date, name)
    return record


def delete_holiday(db: Session, holiday_id: str) -> bool:
    record = db.get(PublicHolidayRecord, holiday_id)
    if record is None:
        return False
    db.delete(record)
    db.commit()
    logger.info("holiday.deleted id=%s date=%s", holiday_id, record.holiday_date)
    return True


# ── Course plan CRUD ──────────────────────────────────────────────────────────


def get_course_plan(db: Session, class_id: str) -> Optional[CoursePlanRecord]:
    return db.execute(
        select(CoursePlanRecord).where(CoursePlanRecord.class_id == class_id)
    ).scalars().first()


def create_or_update_course_plan(
    db: Session,
    class_id: str,
    curriculum_id: str,
    start_date: date,
    teaching_days: list[int],
) -> CoursePlanRecord:
    """Build the full lesson schedule and persist the course plan.

    If a plan already exists for the class it is replaced in-place.
    """
    lesson_ids = _curriculum_lesson_ids(curriculum_id)
    if not lesson_ids:
        raise ValueError(f"Curriculum '{curriculum_id}' has no lessons")

    holidays = get_holiday_date_set(db)
    schedule, end_date = calculate_lesson_schedule(
        lesson_ids=lesson_ids,
        start_date=start_date,
        teaching_days=sorted(set(teaching_days)),
        holiday_dates=holidays,
    )

    existing = get_course_plan(db, class_id)
    if existing is not None:
        existing.curriculum_id = curriculum_id
        existing.start_date = start_date
        existing.teaching_days = sorted(set(teaching_days))
        existing.lesson_schedule = schedule
        existing.end_date = end_date
        db.commit()
        db.refresh(existing)
        logger.info("course_plan.updated class_id=%s curriculum=%s", class_id, curriculum_id)
        return existing

    record = CoursePlanRecord(
        class_id=class_id,
        curriculum_id=curriculum_id,
        start_date=start_date,
        teaching_days=sorted(set(teaching_days)),
        lesson_schedule=schedule,
        end_date=end_date,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    logger.info("course_plan.created class_id=%s curriculum=%s lessons=%d", class_id, curriculum_id, len(schedule))
    return record


def teaching_day_labels(teaching_days: list[int]) -> list[str]:
    """Convert [0, 2, 4] to ['Mon', 'Wed', 'Fri']."""
    return [DAY_NAMES[d] for d in sorted(teaching_days) if 0 <= d <= 6]


def plan_summary(plan: CoursePlanRecord, curriculum: Optional[dict] = None) -> dict:
    """Return a display-friendly summary dict for the plan."""
    total = len(plan.lesson_schedule)
    completed = sum(1 for e in plan.lesson_schedule if e.get("status") == "completed")
    return {
        "id": str(plan.id),
        "curriculum_title": curriculum["title"] if curriculum else plan.curriculum_id,
        "curriculum_subtitle": curriculum.get("subtitle", "") if curriculum else "",
        "start_date": plan.start_date,
        "end_date": plan.end_date,
        "teaching_day_labels": teaching_day_labels(plan.teaching_days),
        "total_lessons": total,
        "completed_lessons": completed,
    }
