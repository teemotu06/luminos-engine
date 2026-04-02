import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Force SQLite before app modules resolve DATABASE_URL and JSON column types.
os.environ["DATABASE_URL"] = "sqlite:////tmp/luminos_engine_test_bootstrap.db"
os.environ["LUMINOS_AUTH_REQUIRED"] = "false"

from app.db import Base
from app.models.lesson import ClassRecord, LessonAttemptRecord, LessonRecord, StudentRecord


class SqliteTestSession:
    def __init__(self):
        self._tmpdir = TemporaryDirectory()
        self.db_path = Path(self._tmpdir.name) / "test.db"
        self.engine = create_engine(
            f"sqlite:///{self.db_path}",
            future=True,
            connect_args={"check_same_thread": False},
        )
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
            future=True,
        )
        Base.metadata.create_all(bind=self.engine)
        self.db = self.SessionLocal()

    def close(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()
        self._tmpdir.cleanup()


def seed_lesson(db, lesson_id: str = "G1-L1") -> LessonRecord:
    lesson = LessonRecord(
        lesson_id=lesson_id,
        unit_id="U1",
        target_pattern="sat",
        content_pack_status="draft",
        json_path=f"app/content/lessons/{lesson_id}.json",
    )
    db.add(lesson)
    db.commit()
    db.refresh(lesson)
    return lesson


def seed_attempt(db, lesson_id: str = "G1-L1", class_id: Optional[str] = None) -> LessonAttemptRecord:
    attempt = LessonAttemptRecord(
        attempt_id=str(uuid4()),
        lesson_id=lesson_id,
        class_id=class_id,
        learner_key="test-learner",
        teacher_key="test-teacher",
        mastery_status="shaky",
        next_recommendation="move_on",
        phoneme_error_log=[],
        completed=False,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt


def seed_class_with_students(db, class_id: str = "class-1", class_name: str = "Class 1", students: Optional[list[str]] = None):
    students = students or ["Tom", "James", "Mina"]
    class_record = ClassRecord(id=class_id, class_name=class_name)
    db.add(class_record)
    db.flush()
    for student_name in students:
        db.add(StudentRecord(class_id=class_id, student_name=student_name))
    db.commit()
    return class_record
