from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Tuple


WORD_RE = re.compile(r"[A-Za-z]+(?:-[A-Za-z]+)?")
LESSON_ID_RE = re.compile(r"^G(?P<group>\d+)-L(?P<lesson>\d+)$")
KI_LESSON_ID_RE = re.compile(r"^KI-L(?P<lesson>\d+)$")
STUDENT_FACING_BLOCKS = {"04", "05", "06", "07", "08", "09", "10"}
REVIEW_ONLY_BLOCKS = {"01", "02"}
INTERVENTION_UNIT_IDS = {"KI"}
REQUIRED_INTERVENTION_BLOCKS = {"01", "02", "03", "04", "05", "06", "07", "08", "09", "10"}
INTERVENTION_PRACTICE_BLOCKS = {"06", "07", "09"}
KI_INSERTION_AFTER = {
    "KI-L1": "G2-L7",
    "KI-L2": "G3-L15",
    "KI-L3": "G7-L43",
    "KI-L4": "G2-L11",
    "KI-L5": "G6-L39",
}


@dataclass
class ControlledTextError:
    code: str
    lesson_id: str
    block_id: Optional[str]
    slide_id: Optional[str]
    token: Optional[str]
    message: str


@dataclass
class ControlledTextReport:
    lesson_id: str
    errors: list[ControlledTextError] = field(default_factory=list)


@dataclass
class CorpusValidationResult:
    reports: list[ControlledTextReport] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(len(report.errors) for report in self.reports)


def normalize_token(value: str) -> str:
    return value.strip().lower()


def lesson_sort_key(lesson_id: str) -> Tuple[int, int, int, int, str]:
    match = LESSON_ID_RE.match(lesson_id)
    if match:
        return (int(match.group("group")), int(match.group("lesson")), 0, 0, lesson_id)
    ki_match = KI_LESSON_ID_RE.match(lesson_id)
    if ki_match and lesson_id in KI_INSERTION_AFTER:
        anchor_match = LESSON_ID_RE.match(KI_INSERTION_AFTER[lesson_id])
        if anchor_match:
            return (
                int(anchor_match.group("group")),
                int(anchor_match.group("lesson")),
                1,
                int(ki_match.group("lesson")),
                lesson_id,
            )
    return (10**9, 10**9, 0, 0, lesson_id)


def extract_tokens(text: Optional[str]) -> List[str]:
    return [match.group(0) for match in WORD_RE.finditer(text or "")]


def is_intervention_lesson(lesson: dict) -> bool:
    return lesson.get("unit_id") in INTERVENTION_UNIT_IDS or lesson.get("lesson_id", "").startswith("KI-")


def intervention_read_respond_count(block: dict) -> int:
    return sum(1 for slide in block.get("slides", []) if slide.get("view_type") == "read_respond")


def lesson_token_classes(lesson: dict) -> dict[str, set[str]]:
    classes: dict[str, set[str]] = {}
    for block in lesson.get("blocks", {}).values():
        for slide in block.get("slides", []):
            payload = slide.get("content_payload", {})
            word_types = payload.get("word_types", {}) or {}
            for token, token_type in word_types.items():
                classes.setdefault(normalize_token(token), set()).add(token_type)
    return classes


def validate_lessons_strict(lessons: Iterable[dict]) -> CorpusValidationResult:
    result = CorpusValidationResult()
    allowed_units: set[str] = set()
    allowed_sight_words: set[str] = set()
    known_token_classes: dict[str, set[str]] = {}

    ordered_lessons = sorted(lessons, key=lambda lesson: lesson_sort_key(lesson["lesson_id"]))

    for lesson in ordered_lessons:
        report = ControlledTextReport(lesson_id=lesson["lesson_id"])
        intervention_lesson = is_intervention_lesson(lesson)
        current_units = {normalize_token(unit) for unit in lesson.get("new_units", [])}
        current_sight_words = {normalize_token(word) for word in lesson.get("new_sight_words", [])}

        if not (lesson.get("target_pattern") or "").strip():
            report.errors.append(
                ControlledTextError(
                    code="DC001",
                    lesson_id=lesson["lesson_id"],
                    block_id=None,
                    slide_id=None,
                    token=None,
                    message="Lesson target_pattern is blank.",
                )
            )

        if not intervention_lesson and not lesson.get("new_units"):
            report.errors.append(
                ControlledTextError(
                    code="DC002",
                    lesson_id=lesson["lesson_id"],
                    block_id=None,
                    slide_id=None,
                    token=None,
                    message="Lesson is missing new_units.",
                )
            )

        if not (lesson.get("title") or "").strip():
            report.errors.append(
                ControlledTextError(
                    code="DC017",
                    lesson_id=lesson["lesson_id"],
                    block_id=None,
                    slide_id=None,
                    token=None,
                    message="Lesson title is blank.",
                )
            )

        if "new_sight_words" not in lesson:
            report.errors.append(
                ControlledTextError(
                    code="DC003",
                    lesson_id=lesson["lesson_id"],
                    block_id=None,
                    slide_id=None,
                    token=None,
                    message="Lesson is missing new_sight_words.",
                )
            )

        if intervention_lesson:
            present_blocks = set(lesson.get("blocks", {}))
            missing_blocks = sorted(REQUIRED_INTERVENTION_BLOCKS - present_blocks)
            if missing_blocks:
                report.errors.append(
                    ControlledTextError(
                        code="DC018",
                        lesson_id=lesson["lesson_id"],
                        block_id=None,
                        slide_id=None,
                        token=None,
                        message=f"Intervention lesson is missing required blocks: {missing_blocks}.",
                    )
                )
            for block_id in sorted(INTERVENTION_PRACTICE_BLOCKS):
                block = lesson.get("blocks", {}).get(block_id)
                if not block or intervention_read_respond_count(block) == 0:
                    report.errors.append(
                        ControlledTextError(
                            code="DC019",
                            lesson_id=lesson["lesson_id"],
                            block_id=block_id,
                            slide_id=None,
                            token=None,
                            message="Intervention lesson is missing read_respond practice in a required block.",
                        )
                    )

        current_token_classes = lesson_token_classes(lesson)
        for token, classes in current_token_classes.items():
            prior_classes = known_token_classes.get(token, set())
            combined = prior_classes | classes
            if "decodable" in combined and "sight" in combined:
                report.errors.append(
                    ControlledTextError(
                        code="DC014",
                        lesson_id=lesson["lesson_id"],
                        block_id=None,
                        slide_id=None,
                        token=token,
                        message=f"Token {token!r} is classified inconsistently across slides or lessons: {sorted(combined)}.",
                    )
                )

        for block in lesson.get("blocks", {}).values():
            block_allowed_units = set(allowed_units)
            block_allowed_sight = set(allowed_sight_words)
            if block["block_id"] not in REVIEW_ONLY_BLOCKS:
                block_allowed_units |= current_units
                block_allowed_sight |= current_sight_words

            for slide in block.get("slides", []):
                payload = slide.get("content_payload", {})

                if not intervention_lesson and block["block_id"] == "03":
                    declared = set()
                    if payload.get("blend_units"):
                        declared.update(
                            normalize_token(unit["grapheme"])
                            for unit in payload["blend_units"]
                            if unit.get("grapheme")
                        )
                    if declared and not declared.issubset(current_units):
                        report.errors.append(
                            ControlledTextError(
                                code="DC015",
                                lesson_id=lesson["lesson_id"],
                                block_id=block["block_id"],
                                slide_id=slide["slide_id"],
                                token=None,
                                message=f"Block 03 slide declares units outside new_units: {sorted(declared - current_units)}.",
                            )
                        )

                word_types = payload.get("word_types", {}) or {}
                token_units = payload.get("token_units", {}) or {}

                if (
                    not intervention_lesson
                    and slide.get("view_type") == "read_respond"
                    and block["block_id"] in STUDENT_FACING_BLOCKS
                ):
                    text_tokens = extract_tokens(payload.get("text_content"))
                    normalized_word_types = {
                        normalize_token(token): token_type for token, token_type in word_types.items()
                    }
                    normalized_token_units = {
                        normalize_token(token): [normalize_token(unit) for unit in units]
                        for token, units in token_units.items()
                    }

                    for raw_token in text_tokens:
                        token = normalize_token(raw_token)
                        token_type = normalized_word_types.get(token)

                        if token_type is None:
                            report.errors.append(
                                ControlledTextError(
                                    code="DC010",
                                    lesson_id=lesson["lesson_id"],
                                    block_id=block["block_id"],
                                    slide_id=slide["slide_id"],
                                    token=raw_token,
                                    message=f"Student-facing token {raw_token!r} is missing from word_types.",
                                )
                            )
                            continue

                        if token_type == "decodable":
                            units = normalized_token_units.get(token)
                            if not units:
                                report.errors.append(
                                    ControlledTextError(
                                        code="DC011",
                                        lesson_id=lesson["lesson_id"],
                                        block_id=block["block_id"],
                                        slide_id=slide["slide_id"],
                                        token=raw_token,
                                        message=f"Decodable token {raw_token!r} is missing token_units.",
                                    )
                                )
                                continue

                            unknown_units = [unit for unit in units if unit not in block_allowed_units]
                            if unknown_units:
                                report.errors.append(
                                    ControlledTextError(
                                        code="DC012",
                                        lesson_id=lesson["lesson_id"],
                                        block_id=block["block_id"],
                                        slide_id=slide["slide_id"],
                                        token=raw_token,
                                        message=f"Decodable token {raw_token!r} uses untaught units: {unknown_units}.",
                                    )
                                )
                        elif token_type == "sight":
                            if token not in block_allowed_sight:
                                report.errors.append(
                                    ControlledTextError(
                                        code="DC013",
                                        lesson_id=lesson["lesson_id"],
                                        block_id=block["block_id"],
                                        slide_id=slide["slide_id"],
                                        token=raw_token,
                                        message=f"Sight token {raw_token!r} is not declared in cumulative sight inventory.",
                                    )
                                )

                if not intervention_lesson and block["block_id"] in REVIEW_ONLY_BLOCKS:
                    for candidate in list(word_types):
                        token = normalize_token(candidate)
                        if token in current_units or token in current_sight_words:
                            report.errors.append(
                                ControlledTextError(
                                    code="DC016",
                                    lesson_id=lesson["lesson_id"],
                                    block_id=block["block_id"],
                                    slide_id=slide["slide_id"],
                                    token=candidate,
                                    message=f"Review block uses current-lesson unit or sight word {candidate!r}.",
                                )
                            )

        result.reports.append(report)
        allowed_units |= current_units
        allowed_sight_words |= current_sight_words
        for token, classes in current_token_classes.items():
            known_token_classes.setdefault(token, set()).update(classes)

    return result
