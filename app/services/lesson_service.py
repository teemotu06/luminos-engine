import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.lesson import LessonRecord
from app.schemas.lesson import Lesson
from app.services.block_registry import BLOCK_REGISTRY
from app.services.block_validator import validate_lesson_blocks
from app.services.slide_payload_validator import validate_slide_payloads


LESSONS_DIR = Path("app/content/lessons")
LESSON_ID_RE = re.compile(r"^G(?P<group>\d+)-L(?P<lesson>\d+)$")
KI_LESSON_ID_RE = re.compile(r"^KI-L(?P<lesson>\d+)$")

KI_INSERTION_MAP: Dict[str, Dict[str, str]] = {
    "KI-L1": {
        "after": "G2-L7",
        "label": "Insert before the first sustained /r/ decoding load.",
        "policy": "Required when flagged. Skippable when stable.",
        "assign_when": "Assign if the learner confuses /r/ and /l/ in listening, oral response, or word repetition.",
        "skip_when": "Skip or shorten if the learner can discriminate /r/ and /l/ accurately across minimal pairs.",
    },
    "KI-L2": {
        "after": "G3-L15",
        "label": "Insert after initial liquid instruction to stabilize print-to-speech transfer.",
        "policy": "Required when flagged. Skippable when stable.",
        "assign_when": "Assign if the learner can hear the contrast but still reads or says r/l words inaccurately from print.",
        "skip_when": "Skip or shorten if print-to-speech production is already stable in words and short sentences.",
    },
    "KI-L3": {
        "after": "G7-L43",
        "label": "Insert before the cluster-heavy band in G8.",
        "policy": "Required when flagged. Skippable when stable.",
        "assign_when": "Assign if the learner inserts a vowel in clusters like /st/, /bl/, /tr/, or breaks the cluster apart.",
        "skip_when": "Skip or shorten if clusters are produced cleanly without epenthesis in words and sentences.",
    },
    "KI-L4": {
        "after": "G2-L11",
        "label": "Insert once simple codas are established and before denser final-cluster pressure builds.",
        "policy": "Required when flagged. Skippable when stable.",
        "assign_when": "Assign if the learner drops or weakens final consonants in CVC words or simple codas during reading or repetition.",
        "skip_when": "Skip or shorten if final stops and nasals are preserved consistently in connected speech.",
    },
    "KI-L5": {
        "after": "G6-L39",
        "label": "Insert before the later vowel-heavy sequence to reduce contrast collapse.",
        "policy": "Required when flagged. Skippable when stable.",
        "assign_when": "Assign if the learner collapses high-risk vowel contrasts such as ship/sheep or pen/pan in reading or dictation.",
        "skip_when": "Skip or shorten if those vowel contrasts are already stable in listening, reading, and encoding.",
    },
}


def get_lesson_file_path(lesson_id: str) -> Path:
    return LESSONS_DIR / f"{lesson_id}.json"


def lesson_sort_key(lesson_id: str) -> Tuple[int, int, int, int, str]:
    match = LESSON_ID_RE.match(lesson_id)
    if match:
        return (int(match.group("group")), int(match.group("lesson")), 0, 0, lesson_id)
    ki_match = KI_LESSON_ID_RE.match(lesson_id)
    if ki_match and lesson_id in KI_INSERTION_MAP:
        anchor_match = LESSON_ID_RE.match(KI_INSERTION_MAP[lesson_id]["after"])
        if anchor_match:
            return (
                int(anchor_match.group("group")),
                int(anchor_match.group("lesson")),
                1,
                int(ki_match.group("lesson")),
                lesson_id,
            )
    return (10**9, 10**9, 0, 0, lesson_id)


def get_intervention_anchor(lesson_id: str) -> Optional[Dict[str, str]]:
    return KI_INSERTION_MAP.get(lesson_id)


def read_lesson_data(lesson_id: str) -> dict:
    lesson_file_path = get_lesson_file_path(lesson_id)

    if not lesson_file_path.exists():
        raise FileNotFoundError(f"Lesson file not found: {lesson_file_path}")

    with open(lesson_file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_lesson(lesson_data: dict) -> Lesson:
    lesson = Lesson(**lesson_data)
    validate_lesson_blocks(lesson)
    validate_slide_payloads(lesson)
    return lesson


def load_lesson(lesson_id: str) -> Lesson:
    lesson_data = read_lesson_data(lesson_id)
    lesson_data.setdefault("json_path", str(get_lesson_file_path(lesson_id).relative_to("app")))
    return parse_lesson(lesson_data)


@lru_cache(maxsize=1)
def _lesson_ids_cached() -> tuple[str, ...]:
    """Cached filesystem glob — only scanned once per process lifetime.

    Trade-off: lesson JSON files added or removed while the server is running
    will not be picked up until the cache is cleared (call invalidate_lesson_id_cache())
    or the process is restarted. This is acceptable because lesson content changes
    happen during deployment, not mid-session. The admin rebuild endpoint clears
    this cache as part of its work.
    """
    lesson_files = LESSONS_DIR.glob("*.json")
    return tuple(sorted((file.stem for file in lesson_files), key=lesson_sort_key))


def invalidate_lesson_id_cache() -> None:
    """Clear the lesson-ID cache so the next call to list_lesson_ids() re-scans disk."""
    _lesson_ids_cached.cache_clear()


def list_lesson_ids() -> list[str]:
    return list(_lesson_ids_cached())


def load_all_lessons() -> list[Lesson]:
    return [load_lesson(lesson_id) for lesson_id in list_lesson_ids()]


def ordered_blocks(lesson: Lesson):
    return [lesson.blocks[definition.block_id] for definition in BLOCK_REGISTRY]


def sync_lesson_record(db: Session, lesson: Lesson) -> LessonRecord:
    lesson_record = db.get(LessonRecord, lesson.lesson_id)

    if lesson_record is None:
        lesson_record = LessonRecord(
            lesson_id=lesson.lesson_id,
            unit_id=lesson.unit_id,
            target_pattern=lesson.target_pattern,
            content_pack_status=lesson.content_pack_status,
            json_path=lesson.json_path or "",
        )
        db.add(lesson_record)
    else:
        lesson_record.unit_id = lesson.unit_id
        lesson_record.target_pattern = lesson.target_pattern
        lesson_record.content_pack_status = lesson.content_pack_status
        lesson_record.json_path = lesson.json_path or lesson_record.json_path

    db.flush()
    return lesson_record


def sync_all_lessons(db: Session) -> None:
    for lesson in load_all_lessons():
        sync_lesson_record(db, lesson)
    db.commit()
