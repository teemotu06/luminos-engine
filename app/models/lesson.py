import uuid
from datetime import datetime
from typing import Optional, Union

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db import Base, DATABASE_URL


JsonType = JSONB if DATABASE_URL.startswith("postgresql") else JSON
UuidType = UUID(as_uuid=True) if DATABASE_URL.startswith("postgresql") else String(36)


def new_uuid_value():
    return uuid.uuid4() if DATABASE_URL.startswith("postgresql") else str(uuid.uuid4())


class ClassRecord(Base):
    __tablename__ = "class_group"

    id: Mapped[Union[str, uuid.UUID]] = mapped_column(UuidType, primary_key=True, default=new_uuid_value)
    class_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    students: Mapped[list["StudentRecord"]] = relationship(
        back_populates="class_group",
        cascade="all, delete-orphan",
        order_by="StudentRecord.student_name",
    )


class StudentRecord(Base):
    __tablename__ = "student_record"

    id: Mapped[Union[str, uuid.UUID]] = mapped_column(UuidType, primary_key=True, default=new_uuid_value)
    class_id: Mapped[Union[str, uuid.UUID]] = mapped_column(
        ForeignKey("class_group.id", ondelete="CASCADE"), nullable=False
    )
    student_name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    class_group: Mapped["ClassRecord"] = relationship(back_populates="students")

    __table_args__ = (UniqueConstraint("class_id", "student_name", name="uq_student_per_class"),)


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
    class_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
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


class StudentMarkRecord(Base):
    __tablename__ = "student_mark"

    id: Mapped[Union[str, uuid.UUID]] = mapped_column(UuidType, primary_key=True, default=new_uuid_value)
    attempt_id: Mapped[Union[str, uuid.UUID]] = mapped_column(ForeignKey("lesson_attempt.attempt_id"), nullable=False)
    lesson_id: Mapped[str] = mapped_column(String(20), nullable=False)
    slide_id: Mapped[str] = mapped_column(String(20), nullable=False)
    block_id: Mapped[str] = mapped_column(String(2), nullable=False)
    student_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_tags: Mapped[Optional[list]] = mapped_column(JsonType, default=None, nullable=True)
    support_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    teacher_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    attempt: Mapped["LessonAttemptRecord"] = relationship()


class OralCheckSessionRecord(Base):
    __tablename__ = "oral_check_session"

    id: Mapped[Union[str, uuid.UUID]] = mapped_column(UuidType, primary_key=True, default=new_uuid_value)
    attempt_id: Mapped[Union[str, uuid.UUID]] = mapped_column(ForeignKey("lesson_attempt.attempt_id"), nullable=False)
    lesson_id: Mapped[str] = mapped_column(String(20), nullable=False)
    slide_id: Mapped[str] = mapped_column(String(20), nullable=False)
    block_id: Mapped[str] = mapped_column(String(2), nullable=False)
    participation_mode: Mapped[str] = mapped_column(String(40), nullable=False)
    audit_selection_strategy: Mapped[str] = mapped_column(String(40), nullable=False, default="roster_order")
    text_length_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="normal")
    required_evidence_count: Mapped[int] = mapped_column(default=1, nullable=False)
    roster_size: Mapped[int] = mapped_column(default=0, nullable=False)
    required_student_count: Mapped[int] = mapped_column(default=0, nullable=False)
    resolved_student_count: Mapped[int] = mapped_column(default=0, nullable=False)
    unresolved_student_count: Mapped[int] = mapped_column(default=0, nullable=False)
    session_status: Mapped[str] = mapped_column(String(20), default="in_progress", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    assignments: Mapped[list["OralCheckAssignmentRecord"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="OralCheckAssignmentRecord.queue_order",
    )

    __table_args__ = (UniqueConstraint("attempt_id", "slide_id", name="uq_oral_check_session_attempt_slide"),)


class OralCheckAssignmentRecord(Base):
    __tablename__ = "oral_check_assignment"

    id: Mapped[Union[str, uuid.UUID]] = mapped_column(UuidType, primary_key=True, default=new_uuid_value)
    session_id: Mapped[Union[str, uuid.UUID]] = mapped_column(
        ForeignKey("oral_check_session.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attempt_id: Mapped[Union[str, uuid.UUID]] = mapped_column(ForeignKey("lesson_attempt.attempt_id"), nullable=False)
    lesson_id: Mapped[str] = mapped_column(String(20), nullable=False)
    slide_id: Mapped[str] = mapped_column(String(20), nullable=False)
    block_id: Mapped[str] = mapped_column(String(2), nullable=False)
    student_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    performance_type: Mapped[str] = mapped_column(String(40), nullable=False)
    attempt_number: Mapped[int] = mapped_column(default=1, nullable=False)
    queue_order: Mapped[int] = mapped_column(default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    requires_reteach: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    resolved_in_block: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    teacher_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    override_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    session: Mapped["OralCheckSessionRecord"] = relationship(back_populates="assignments")
    attempt: Mapped["LessonAttemptRecord"] = relationship()


class ClassPatternReviewRecord(Base):
    __tablename__ = "class_pattern_review"

    id: Mapped[Union[str, uuid.UUID]] = mapped_column(UuidType, primary_key=True, default=new_uuid_value)
    # Persist as String(36) to stay compatible with legacy Postgres databases
    # where this column was created as VARCHAR rather than UUID.
    class_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    pattern_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_lesson_id: Mapped[str] = mapped_column(String(20), nullable=False)
    first_taught_lesson_id: Mapped[str] = mapped_column(String(20), nullable=False)
    last_seen_lesson_id: Mapped[str] = mapped_column(String(20), nullable=False)
    last_reviewed_lesson_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    mastery_state: Mapped[str] = mapped_column(String(20), nullable=False, default="shaky")
    times_secure: Mapped[int] = mapped_column(default=0, nullable=False)
    times_shaky: Mapped[int] = mapped_column(default=0, nullable=False)
    times_missed: Mapped[int] = mapped_column(default=0, nullable=False)
    consecutive_weak_lessons: Mapped[int] = mapped_column(default=0, nullable=False)
    korean_transfer_count: Mapped[int] = mapped_column(default=0, nullable=False)
    weak_learner_count: Mapped[int] = mapped_column(default=0, nullable=False)
    marked_learner_count: Mapped[int] = mapped_column(default=0, nullable=False)
    next_due_lesson_number: Mapped[int] = mapped_column(default=1, nullable=False)
    priority_score: Mapped[int] = mapped_column(default=0, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("class_id", "pattern_key", name="uq_class_pattern_review"),
    )
