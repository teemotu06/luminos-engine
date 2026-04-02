import base64
import hashlib
import hmac
import os
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import env_flag
from app.db import get_db
from app.models.lesson import ClassRecord, LessonAttemptRecord, OralCheckSessionRecord, UserRecord


PASSWORD_ITERATIONS = 390000
SESSION_COOKIE_NAME = "luminos_session"


@dataclass(frozen=True)
class DevUser:
    id: str = "dev-user"
    username: str = "dev"
    role: str = "admin"


def auth_required() -> bool:
    return env_flag("LUMINOS_AUTH_REQUIRED", True)


def session_secret() -> str:
    return os.getenv("LUMINOS_SESSION_SECRET", "").strip()


def validate_auth_configuration() -> None:
    if not auth_required():
        return
    if not session_secret():
        raise RuntimeError("LUMINOS_SESSION_SECRET must be set before the application starts.")
    if not os.getenv("LUMINOS_BOOTSTRAP_ADMIN_USERNAME", "").strip():
        raise RuntimeError("LUMINOS_BOOTSTRAP_ADMIN_USERNAME must be set when auth is enabled.")
    if not os.getenv("LUMINOS_BOOTSTRAP_ADMIN_PASSWORD", "").strip():
        raise RuntimeError("LUMINOS_BOOTSTRAP_ADMIN_PASSWORD must be set when auth is enabled.")


def hash_password(password: str, *, salt: Optional[bytes] = None) -> str:
    password_bytes = password.encode("utf-8")
    salt_bytes = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password_bytes, salt_bytes, PASSWORD_ITERATIONS)
    return (
        "pbkdf2_sha256"
        f"${PASSWORD_ITERATIONS}"
        f"${base64.b64encode(salt_bytes).decode('ascii')}"
        f"${base64.b64encode(digest).decode('ascii')}"
    )


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations, encoded_salt, encoded_digest = stored_hash.split("$", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        base64.b64decode(encoded_salt),
        int(iterations),
    )
    return hmac.compare_digest(base64.b64decode(encoded_digest), derived)


def ensure_bootstrap_users(db: Session) -> None:
    bootstrap_specs = [
        (
            os.getenv("LUMINOS_BOOTSTRAP_ADMIN_USERNAME", "").strip(),
            os.getenv("LUMINOS_BOOTSTRAP_ADMIN_PASSWORD", "").strip(),
            "admin",
        ),
        (
            os.getenv("LUMINOS_BOOTSTRAP_TEACHER_USERNAME", "").strip(),
            os.getenv("LUMINOS_BOOTSTRAP_TEACHER_PASSWORD", "").strip(),
            "teacher",
        ),
    ]
    changed = False
    for username, password, role in bootstrap_specs:
        if not username or not password:
            continue
        user = db.execute(select(UserRecord).where(UserRecord.username == username)).scalars().first()
        password_hash = hash_password(password)
        if user is None:
            db.add(UserRecord(username=username, password_hash=password_hash, role=role))
            changed = True
            continue
        updates_required = user.role != role or not verify_password(password, user.password_hash)
        if updates_required:
            user.role = role
            user.password_hash = password_hash
            changed = True
    if changed:
        db.commit()


def authenticate_user(db: Session, username: str, password: str) -> Optional[UserRecord]:
    ensure_bootstrap_users(db)
    user = db.execute(select(UserRecord).where(UserRecord.username == username.strip())).scalars().first()
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user


def create_session_cookie(user_id: str) -> str:
    signature = hmac.new(
        session_secret().encode("utf-8"),
        user_id.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{user_id}.{signature}"


def read_session_cookie(cookie_value: Optional[str]) -> Optional[str]:
    if not cookie_value or "." not in cookie_value:
        return None
    user_id, signature = cookie_value.rsplit(".", 1)
    expected_signature = hmac.new(
        session_secret().encode("utf-8"),
        user_id.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        return None
    return user_id


def get_current_user_optional(request: Request, db: Session = Depends(get_db)):
    if not auth_required():
        return DevUser()
    user_id = read_session_cookie(request.cookies.get(SESSION_COOKIE_NAME))
    if not user_id:
        return None
    return db.get(UserRecord, user_id)


def require_current_user(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return user


def require_class_access(db: Session, current_user, class_id: str, *, include_deleted: bool = False) -> ClassRecord:
    class_record = db.get(ClassRecord, class_id)
    if class_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    if class_record.deleted_at is not None and not include_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    if current_user.role != "admin" and str(class_record.owner_user_id or "") != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    return class_record


def require_attempt_access(
    db: Session,
    current_user,
    attempt_id: str,
    *,
    lesson_id: Optional[str] = None,
) -> LessonAttemptRecord:
    attempt = db.get(LessonAttemptRecord, attempt_id)
    if attempt is None or (lesson_id is not None and attempt.lesson_id != lesson_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson attempt not found")
    if attempt.class_id:
        require_class_access(db, current_user, attempt.class_id, include_deleted=True)
        return attempt
    if current_user.role == "admin":
        return attempt
    if attempt.teacher_key and attempt.teacher_key != current_user.username:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson attempt not found")
    return attempt


def require_oral_check_session_access(db: Session, current_user, session_id: str) -> OralCheckSessionRecord:
    session = db.get(OralCheckSessionRecord, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Oral check session not found")
    require_attempt_access(db, current_user, str(session.attempt_id), lesson_id=session.lesson_id)
    return session
