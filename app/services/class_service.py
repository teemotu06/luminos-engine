import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.lesson import ClassRecord, StudentRecord

logger = logging.getLogger(__name__)


def create_class(
    db: Session,
    class_name: str,
    description: Optional[str] = None,
    *,
    owner_user_id: Optional[str] = None,
) -> ClassRecord:
    """Create a class owned by the current teacher or left admin-managed."""
    record = ClassRecord(
        class_name=class_name.strip(),
        description=description or None,
        owner_user_id=owner_user_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    logger.info("class.created class_id=%s owner_user_id=%s", record.id, owner_user_id)
    return record


def get_all_classes(
    db: Session,
    *,
    owner_user_id: Optional[str] = None,
    include_deleted: bool = False,
) -> list[dict]:
    """Return active or archived classes in one aggregate query."""
    query = (
        select(ClassRecord, func.count(StudentRecord.id))
        .outerjoin(StudentRecord, StudentRecord.class_id == ClassRecord.id)
        .group_by(ClassRecord.id)
        .order_by(ClassRecord.created_at)
    )
    if owner_user_id is not None:
        query = query.where(ClassRecord.owner_user_id == owner_user_id)
    if not include_deleted:
        query = query.where(ClassRecord.deleted_at.is_(None))
    rows = db.execute(query).all()
    return [
        {
            "id": str(cls.id),
            "class_name": cls.class_name,
            "description": cls.description,
            "student_count": student_count or 0,
            "created_at": cls.created_at,
            "deleted_at": cls.deleted_at,
            "owner_user_id": str(cls.owner_user_id) if cls.owner_user_id else None,
        }
        for cls, student_count in rows
    ]


def get_class_with_students(db: Session, class_id: str, *, include_deleted: bool = False) -> Optional[dict]:
    """Return one class plus its sorted roster when it is visible."""
    cls = db.get(ClassRecord, class_id)
    if cls is None or (cls.deleted_at is not None and not include_deleted):
        return None
    students = (
        db.execute(
            select(StudentRecord)
            .where(StudentRecord.class_id == cls.id)
            .order_by(StudentRecord.student_name)
        )
        .scalars()
        .all()
    )
    return {
        "id": str(cls.id),
        "class_name": cls.class_name,
        "description": cls.description,
        "created_at": cls.created_at,
        "deleted_at": cls.deleted_at,
        "owner_user_id": str(cls.owner_user_id) if cls.owner_user_id else None,
        "students": [{"id": str(s.id), "student_name": s.student_name} for s in students],
    }


def add_student_to_class(db: Session, class_id: str, student_name: str) -> StudentRecord:
    """Add a single student to a class while preserving uniqueness per class."""
    cls = db.get(ClassRecord, class_id)
    if cls is None:
        raise ValueError("Class not found")

    name = student_name.strip()
    if not name:
        raise ValueError("Student name cannot be empty")

    existing = db.execute(
        select(StudentRecord).where(
            StudentRecord.class_id == cls.id,
            StudentRecord.student_name == name,
        )
    ).scalars().first()

    if existing is not None:
        raise ValueError(f"A student named '{name}' already exists in this class")

    record = StudentRecord(class_id=cls.id, student_name=name)
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError(f"A student named '{name}' already exists in this class")
    db.refresh(record)
    logger.info("class.student_added class_id=%s student_name=%s", class_id, name)
    return record


def get_students_for_class(db: Session, class_id: str) -> list[StudentRecord]:
    return (
        db.execute(
            select(StudentRecord)
            .where(StudentRecord.class_id == class_id)
            .order_by(StudentRecord.student_name)
        )
        .scalars()
        .all()
    )


def archive_class(db: Session, class_id: str) -> Optional[ClassRecord]:
    """Soft delete a class so historical attempts remain restorable."""
    cls = db.get(ClassRecord, class_id)
    if cls is None:
        return None
    cls.deleted_at = datetime.utcnow()
    db.commit()
    db.refresh(cls)
    logger.info("class.archived class_id=%s", class_id)
    return cls


def restore_class(db: Session, class_id: str) -> Optional[ClassRecord]:
    """Restore a previously archived class."""
    cls = db.get(ClassRecord, class_id)
    if cls is None:
        return None
    cls.deleted_at = None
    db.commit()
    db.refresh(cls)
    logger.info("class.restored class_id=%s", class_id)
    return cls
