from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.models.lesson import ClassRecord, ClassSessionRecord, LessonAttemptRecord
from app.slide_types import registry
from app.services.lesson_navigation import build_runtime_lesson_for_attempt
from app.services.pattern_noticing_service import adapt_pattern_noticing_payload
from app.services.lesson_service import load_all_lessons, sync_lesson_record
from app.services.marking_service import create_attempt


@dataclass
class SessionSlideView:
    lesson_id: str
    lesson_title: str
    slide_id: str
    slide_title: str
    slide_index: int
    slide_count: int
    block_slide_index: int
    block_slide_count: int
    block_id: str
    view_type: str
    payload: dict
    audio_url: str
    content: str
    prompt: str
    current_state: str = ""
    revealed: bool = False
    paused: bool = False


def _ordered_slides_for_session(db: Session, session: ClassSessionRecord):
    if not session.lesson_id:
        raise ValueError("Class session has no lesson")
    lesson, ordered_slides, _, _ = build_runtime_lesson_for_attempt(db, session.lesson_id, str(session.class_id))
    sync_lesson_record(db, lesson)
    return lesson, ordered_slides


def _slide_primary_text(slide: object) -> str:
    payload = getattr(slide, "content_payload", None)
    if payload is None:
        return str(getattr(slide, "slide_title", ""))
    payload_dict = payload.model_dump() if hasattr(payload, "model_dump") else dict(payload)
    adapted_pattern = adapt_pattern_noticing_payload(str(getattr(slide, "view_type", "")), payload_dict)
    if adapted_pattern is not None:
        payload_dict = adapted_pattern
        view_type = "pattern_noticing"
    else:
        view_type = str(getattr(slide, "view_type", ""))
    payload_dict.setdefault("slide_title", str(getattr(slide, "slide_title", "")))
    return registry.summary_for(view_type, payload_dict)


def _slide_prompt(slide: object) -> str:
    view_type = str(getattr(slide, "view_type", "") or "")
    if view_type == "flashcard":
        return ""
    payload = getattr(slide, "content_payload", None)
    payload_dict = payload.model_dump() if payload is not None and hasattr(payload, "model_dump") else dict(payload) if payload is not None else {}
    adapted_pattern = adapt_pattern_noticing_payload(view_type, payload_dict)
    if adapted_pattern is not None:
        return str(adapted_pattern.get("prompt") or "")
    prompt_text = getattr(payload, "prompt_text", None) if payload is not None else None
    return str(prompt_text or "")


def _runtime_projection(db: Session, session: ClassSessionRecord, slide_id: str):
    if not session.attempt_id or not session.lesson_id or not slide_id:
        return None
    try:
        from app.services.command_state_service import get_command_state

        return get_command_state(db, str(session.lesson_id), str(session.attempt_id), slide_id)
    except Exception:
        return None


def _slide_audio_url(slide: object) -> str:
    explicit = getattr(slide, "slide_audio_url", None)
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    payload = getattr(slide, "content_payload", None)
    if payload is None:
        return ""
    payload_dict = payload.model_dump() if hasattr(payload, "model_dump") else dict(payload)
    for field in ("audio_url", "audio", "audio_file", "audio_prompt", "audio_support", "blend_audio", "word_audio"):
        value = payload_dict.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _is_runtime_revealed(runtime_state, slide: object | None = None) -> bool:
    if runtime_state is None:
        return False
    view_type = str(getattr(slide, "view_type", "") or "")
    if view_type == "listen_spell":
        return str(getattr(runtime_state, "current_state", "") or "") == "revealed"
    if view_type == "sound_match":
        return str(getattr(runtime_state, "current_state", "") or "") in {"revealed", "produce"}
    return str(getattr(runtime_state, "current_state", "") or "") not in {"", "idle", "transition"}


def ensure_class_session(db: Session, class_id: str) -> ClassSessionRecord:
    session = db.get(ClassSessionRecord, class_id)
    if session is not None:
        return session
    session = ClassSessionRecord(class_id=class_id, status="idle", paused=False, version=1)
    db.add(session)
    db.flush()
    return session


def get_class_session(db: Session, class_id: str) -> Optional[ClassSessionRecord]:
    return db.get(ClassSessionRecord, class_id)


def start_class_session(
    db: Session,
    *,
    class_id: str,
    lesson_id: str,
    teacher_key: Optional[str],
) -> ClassSessionRecord:
    attempt = create_attempt(db, lesson_id=lesson_id, teacher_key=teacher_key, class_id=class_id)
    lesson, ordered_slides, _, _ = build_runtime_lesson_for_attempt(db, lesson_id, class_id)
    sync_lesson_record(db, lesson)
    if not ordered_slides:
        raise ValueError(f"Lesson {lesson_id} has no slides")
    first_slide_id = ordered_slides[0]["slide"].slide_id
    session = ensure_class_session(db, class_id)
    session.lesson_id = lesson.lesson_id
    session.attempt_id = attempt.attempt_id
    session.current_slide_id = attempt.current_slide_id or first_slide_id
    session.status = "active"
    session.paused = False
    session.display_message = None
    session.drag_letter_selection = []
    session.drag_letter_slide_id = session.current_slide_id
    session.spell_word_selection = []
    session.spell_word_slide_id = session.current_slide_id
    session.pattern_noticing_reveal_count = 0
    session.pattern_noticing_slide_id = session.current_slide_id
    session.version += 1
    attempt.current_slide_id = session.current_slide_id
    db.commit()
    db.refresh(session)
    return session


def stop_class_session(db: Session, *, class_id: str) -> ClassSessionRecord:
    session = ensure_class_session(db, class_id)
    if session.attempt_id:
        attempt = db.get(LessonAttemptRecord, session.attempt_id)
        if attempt is not None:
            attempt.completed = True
    session.lesson_id = None
    session.attempt_id = None
    session.current_slide_id = None
    session.status = "idle"
    session.paused = False
    session.display_message = None
    session.drag_letter_selection = []
    session.drag_letter_slide_id = None
    session.spell_word_selection = []
    session.spell_word_slide_id = None
    session.pattern_noticing_reveal_count = 0
    session.pattern_noticing_slide_id = None
    session.version += 1
    db.commit()
    db.refresh(session)
    return session


def pause_class_session(db: Session, *, class_id: str, paused: bool) -> ClassSessionRecord:
    session = ensure_class_session(db, class_id)
    if session.status == "idle":
        return session
    session.paused = paused
    session.status = "paused" if paused else "active"
    session.version += 1
    db.commit()
    db.refresh(session)
    return session


def set_class_session_slide(db: Session, *, class_id: str, slide_id: str) -> ClassSessionRecord:
    session = ensure_class_session(db, class_id)
    if session.status == "idle" or not session.lesson_id:
        raise ValueError("No active class session")
    _lesson, ordered_slides = _ordered_slides_for_session(db, session)
    if slide_id not in {entry["slide"].slide_id for entry in ordered_slides}:
        raise ValueError(f"Unknown slide {slide_id}")
    session.current_slide_id = slide_id
    session.letter_reveal_count = 0
    session.letter_reveal_slide_id = slide_id
    session.drag_letter_selection = []
    session.drag_letter_slide_id = slide_id
    session.pattern_noticing_reveal_count = 0
    session.pattern_noticing_slide_id = slide_id
    session.spell_word_selection = []
    session.spell_word_slide_id = slide_id
    session.version += 1
    if session.attempt_id:
        attempt = db.get(LessonAttemptRecord, session.attempt_id)
        if attempt is not None:
            attempt.current_slide_id = slide_id
    db.commit()
    db.refresh(session)
    return session


def move_class_session_slide(db: Session, *, class_id: str, step: int) -> ClassSessionRecord:
    session = ensure_class_session(db, class_id)
    if session.status == "idle" or not session.lesson_id:
        raise ValueError("No active class session")
    _lesson, ordered_slides = _ordered_slides_for_session(db, session)
    slide_ids = [entry["slide"].slide_id for entry in ordered_slides]
    if not slide_ids:
        raise ValueError("Lesson has no slides")
    current_slide_id = session.current_slide_id or slide_ids[0]
    try:
        current_index = slide_ids.index(current_slide_id)
    except ValueError:
        current_index = 0
    next_index = max(0, min(len(slide_ids) - 1, current_index + step))
    return set_class_session_slide(db, class_id=class_id, slide_id=slide_ids[next_index])


def set_letter_reveal_count(db: Session, *, class_id: str, count: int) -> ClassSessionRecord:
    session = ensure_class_session(db, class_id)
    if session.status == "idle" or not session.lesson_id:
        raise ValueError("No active class session")
    # If the reveal slide has changed, reset
    current_slide = session.current_slide_id or ""
    if (session.letter_reveal_slide_id or "") != current_slide:
        session.letter_reveal_slide_id = current_slide
        session.letter_reveal_count = 0
    session.letter_reveal_count = max(0, count)
    session.letter_reveal_slide_id = current_slide
    session.version += 1
    db.commit()
    db.refresh(session)
    return session


def set_drag_letter_selection(db: Session, *, class_id: str, letters: list[str | None]) -> ClassSessionRecord:
    session = ensure_class_session(db, class_id)
    if session.status == "idle" or not session.lesson_id:
        raise ValueError("No active class session")
    current_slide = session.current_slide_id or ""
    if (session.drag_letter_slide_id or "") != current_slide:
        session.drag_letter_slide_id = current_slide
        session.drag_letter_selection = []
    normalized = []
    for item in letters or []:
        if item is None:
            normalized.append(None)
            continue
        text = str(item).strip()
        normalized.append(text if text else None)
    session.drag_letter_selection = normalized
    session.drag_letter_slide_id = current_slide
    session.version += 1
    db.commit()
    db.refresh(session)
    return session


def set_pattern_noticing_reveal_count(db: Session, *, class_id: str, count: int) -> ClassSessionRecord:
    session = ensure_class_session(db, class_id)
    if session.status == "idle" or not session.lesson_id:
        raise ValueError("No active class session")
    current_slide = session.current_slide_id or ""
    if (session.pattern_noticing_slide_id or "") != current_slide:
        session.pattern_noticing_slide_id = current_slide
        session.pattern_noticing_reveal_count = 0
    session.pattern_noticing_reveal_count = max(0, count)
    session.pattern_noticing_slide_id = current_slide
    session.version += 1
    db.commit()
    db.refresh(session)
    return session


def set_spell_word_selection(db: Session, *, class_id: str, letters: list[str]) -> ClassSessionRecord:
    session = ensure_class_session(db, class_id)
    if session.status == "idle" or not session.lesson_id:
        raise ValueError("No active class session")
    current_slide = session.current_slide_id or ""
    normalized = [str(item or "").strip() for item in (letters or []) if str(item or "").strip()]
    if (session.spell_word_slide_id or "") != current_slide:
        session.spell_word_slide_id = current_slide
        session.spell_word_selection = []
    session.spell_word_selection = normalized
    session.spell_word_slide_id = current_slide
    session.version += 1
    db.commit()
    db.refresh(session)
    return session


def set_class_session_message(db: Session, *, class_id: str, message: Optional[str]) -> ClassSessionRecord:
    session = ensure_class_session(db, class_id)
    session.display_message = (message or "").strip() or None
    session.version += 1
    db.commit()
    db.refresh(session)
    return session


def list_control_lessons():
    lessons = load_all_lessons()
    return [
        {
            "lesson_id": lesson.lesson_id,
            "title": lesson.title,
            "target_pattern": lesson.target_pattern,
        }
        for lesson in lessons
    ]


def session_slide_view(db: Session, class_id: str) -> Optional[SessionSlideView]:
    session = get_class_session(db, class_id)
    if session is None or session.status == "idle" or not session.lesson_id:
        return None
    lesson, ordered_slides = _ordered_slides_for_session(db, session)
    if not ordered_slides:
        return None
    slide_ids = [entry["slide"].slide_id for entry in ordered_slides]
    current_slide_id = session.current_slide_id or slide_ids[0]
    try:
        slide_index = slide_ids.index(current_slide_id)
    except ValueError:
        slide_index = 0
        current_slide_id = slide_ids[0]
    slide = ordered_slides[slide_index]["slide"]
    current_block_slides = [entry["slide"] for entry in ordered_slides if str(entry["slide"].block_id) == str(slide.block_id)]
    current_block_slide_ids = [item.slide_id for item in current_block_slides]
    try:
        block_slide_index = current_block_slide_ids.index(current_slide_id)
    except ValueError:
        block_slide_index = 0
    raw_payload = slide.content_payload.model_dump() if hasattr(slide.content_payload, "model_dump") else dict(slide.content_payload)
    adapted_pattern = adapt_pattern_noticing_payload(str(slide.view_type), raw_payload)
    payload = adapted_pattern or raw_payload
    effective_view_type = "pattern_noticing" if adapted_pattern is not None else slide.view_type
    runtime_state = _runtime_projection(db, session, current_slide_id)
    if runtime_state is not None:
        # Keep the board anchored to authored slide content. Runtime banner text
        # like "Mark your class" or "All secure — great work" is useful in the
        # teacher shell, but it should not replace the student-facing slide.
        content = _slide_primary_text(slide)
        prompt = "" if str(getattr(slide, "view_type", "") or "") == "flashcard" else (runtime_state.prompt_text or _slide_prompt(slide))
        paused = bool(session.paused or runtime_state.paused)
        revealed = _is_runtime_revealed(runtime_state, slide)
        current_state = str(getattr(runtime_state, "current_state", "") or "")
    else:
        content = _slide_primary_text(slide)
        prompt = _slide_prompt(slide)
        paused = bool(session.paused)
        revealed = False
        current_state = ""
    return SessionSlideView(
        lesson_id=lesson.lesson_id,
        lesson_title=lesson.title,
        slide_id=current_slide_id,
        slide_title=slide.slide_title,
        slide_index=slide_index,
        slide_count=len(ordered_slides),
        block_slide_index=block_slide_index,
        block_slide_count=len(current_block_slide_ids),
        block_id=slide.block_id,
        view_type=effective_view_type,
        payload=payload,
        audio_url=_slide_audio_url(slide),
        content=content,
        prompt=prompt,
        current_state=current_state,
        revealed=revealed,
        paused=paused,
    )


def class_session_payload(db: Session, class_id: str) -> dict:
    cls = db.get(ClassRecord, class_id)
    if cls is None:
        raise ValueError("Class not found")
    session = ensure_class_session(db, class_id)
    slide_view = session_slide_view(db, class_id)
    # letter_reveal_count is only valid for the current slide
    current_slide_id = session.current_slide_id or ""
    letter_reveal_count = 0
    if (session.letter_reveal_slide_id or "") == current_slide_id and current_slide_id:
        letter_reveal_count = session.letter_reveal_count or 0
    pattern_noticing_reveal_count = 0
    if (session.pattern_noticing_slide_id or "") == current_slide_id and current_slide_id:
        pattern_noticing_reveal_count = session.pattern_noticing_reveal_count or 0
    spell_word_selection = []
    if (session.spell_word_slide_id or "") == current_slide_id and current_slide_id:
        spell_word_selection = list(session.spell_word_selection or [])
    drag_letter_selection = []
    if (session.drag_letter_slide_id or "") == current_slide_id and current_slide_id:
        drag_letter_selection = list(session.drag_letter_selection or [])

    payload = {
        "class_id": class_id,
        "class_name": cls.class_name,
        "active": slide_view is not None and session.status != "idle",
        "status": "paused" if slide_view is not None and slide_view.paused else session.status,
        "paused": bool(slide_view.paused) if slide_view is not None else bool(session.paused),
        "version": session.version,
        "attempt_id": str(session.attempt_id) if session.attempt_id else None,
        "display_message": session.display_message or "",
        "letter_reveal_count": letter_reveal_count,
        "drag_letter_selection": drag_letter_selection,
        "pattern_noticing_reveal_count": pattern_noticing_reveal_count,
        "spell_word_selection": spell_word_selection,
    }
    if slide_view is None:
        payload.update(
            {
                "lesson_id": None,
                "lesson_title": None,
                "slide_id": None,
                "slide_title": None,
                "slide_index": 0,
                "slide_count": 0,
                "block_slide_index": 0,
                "block_slide_count": 0,
                "block_id": None,
                "view_type": None,
                "payload": {},
                "audio_url": "",
                "content": "",
                "prompt": "",
                "current_state": "",
                "revealed": False,
            }
        )
        return payload
    payload.update(
        {
            "lesson_id": slide_view.lesson_id,
            "lesson_title": slide_view.lesson_title,
            "slide_id": slide_view.slide_id,
            "slide_title": slide_view.slide_title,
            "slide_index": slide_view.slide_index,
            "slide_count": slide_view.slide_count,
            "block_slide_index": slide_view.block_slide_index,
            "block_slide_count": slide_view.block_slide_count,
            "block_id": slide_view.block_id,
            "view_type": slide_view.view_type,
            "payload": slide_view.payload,
            "audio_url": slide_view.audio_url,
            "content": slide_view.content,
            "prompt": slide_view.prompt,
            "current_state": slide_view.current_state,
            "revealed": slide_view.revealed,
        }
    )
    return payload
