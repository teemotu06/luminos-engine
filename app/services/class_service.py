from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.lesson import ClassRecord, StudentRecord


def create_class(db: Session, class_name: str, description: Optional[str] = None) -> ClassRecord:
    record = ClassRecord(class_name=class_name.strip(), description=description or None)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_all_classes(db: Session) -> list[dict]:
    classes = (
        db.execute(select(ClassRecord).order_by(ClassRecord.created_at))
        .scalars()
        .all()
    )
    result = []
    for cls in classes:
        count = db.execute(
            select(func.count()).select_from(StudentRecord).where(StudentRecord.class_id == cls.id)
        ).scalar() or 0
        result.append(
            {
                "id": str(cls.id),
                "class_name": cls.class_name,
                "description": cls.description,
                "student_count": count,
                "created_at": cls.created_at,
            }
        )
    return result


def get_class_with_students(db: Session, class_id: str) -> Optional[dict]:
    cls = db.get(ClassRecord, class_id)
    if cls is None:
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
        "students": [{"id": str(s.id), "student_name": s.student_name} for s in students],
    }


def add_student_to_class(db: Session, class_id: str, student_name: str) -> StudentRecord:
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
