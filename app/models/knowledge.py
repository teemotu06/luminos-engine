import uuid
from datetime import date, datetime
from typing import Optional, Union

from sqlalchemy import Date, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.lesson import JsonType, UuidType, new_uuid_value


class PublicHolidayRecord(Base):
    __tablename__ = "public_holiday"

    id: Mapped[Union[str, uuid.UUID]] = mapped_column(UuidType, primary_key=True, default=new_uuid_value)
    holiday_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    region: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("holiday_date", "region", name="uq_holiday_date_region"),)


class CoursePlanRecord(Base):
    __tablename__ = "course_plan"

    id: Mapped[Union[str, uuid.UUID]] = mapped_column(UuidType, primary_key=True, default=new_uuid_value)
    class_id: Mapped[Union[str, uuid.UUID]] = mapped_column(
        ForeignKey("class_group.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    curriculum_id: Mapped[str] = mapped_column(String(50), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    # List of weekday ints (0=Monday … 6=Sunday) indicating teaching days
    teaching_days: Mapped[list] = mapped_column(JsonType, nullable=False, default=list)
    # [{lesson_id, lesson_index, unit_id, scheduled_date}, ...]
    lesson_schedule: Mapped[list] = mapped_column(JsonType, nullable=False, default=list)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
