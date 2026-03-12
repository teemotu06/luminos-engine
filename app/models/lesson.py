import uuid
from datetime import datetime
from typing import Optional, Union

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db import Base, DATABASE_URL


JsonType = JSONB if DATABASE_URL.startswith("postgresql") else JSON
UuidType = UUID(as_uuid=True) if DATABASE_URL.startswith("postgresql") else String(36)


def new_uuid_value():
    return uuid.uuid4() if DATABASE_URL.startswith("postgresql") else str(uuid.uuid4())


class LessonRecord(Base):
    __tablename__ = "lesson"

    lesson_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    unit_id: Mapped[str] = mapped_column(String(10), nullable=False)
    target_pattern: Mapped[str] = mapped_column(String(50), nullable=False)
    content_pack_status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    json_path: Mapped[str] = mapped_column(String(200), nullable=False)

    attempts: Mapped[list["LessonAttemptRecord"]] = relationship(back_populates="lesson")


class LessonAttemptRecord(Base):
    __tablename__ = "lesson_attempt"

    attempt_id: Mapped[Union[str, uuid.UUID]] = mapped_column(UuidType, primary_key=True, default=new_uuid_value)
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lesson.lesson_id"), nullable=False)
    learner_key: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    teacher_key: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    attempt_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mastery_status: Mapped[str] = mapped_column(String(20), default="shaky", nullable=False)
    phoneme_error_log: Mapped[list] = mapped_column(JsonType, default=list, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    next_recommendation: Mapped[str] = mapped_column(String(20), default="move_on", nullable=False)

    lesson: Mapped["LessonRecord"] = relationship(back_populates="attempts")
    slide_results: Mapped[list["SlideResultRecord"]] = relationship(
        back_populates="attempt",
        cascade="all, delete-orphan",
    )


class SlideResultRecord(Base):
    __tablename__ = "slide_result"

    result_id: Mapped[Union[str, uuid.UUID]] = mapped_column(UuidType, primary_key=True, default=new_uuid_value)
    attempt_id: Mapped[Union[str, uuid.UUID]] = mapped_column(ForeignKey("lesson_attempt.attempt_id"), nullable=False)
    slide_id: Mapped[str] = mapped_column(String(20), nullable=False)
    block_id: Mapped[str] = mapped_column(String(2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_tags: Mapped[list[str]] = mapped_column(JsonType, default=list, nullable=False)
    korean_transfer: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    teacher_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    item_results: Mapped[list] = mapped_column(JsonType, default=list, nullable=False)

    attempt: Mapped["LessonAttemptRecord"] = relationship(back_populates="slide_results")
