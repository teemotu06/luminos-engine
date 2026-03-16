#!/usr/bin/env python3
import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from app.services.lesson_service import parse_lesson


ROOT = Path(__file__).resolve().parents[1]
LESSONS_DIR = ROOT / "app" / "content" / "lessons"
DEFAULT_CLOSE_MARKING_OPTIONS = ["secure", "shaky", "missed"]


def canonicalize_grapheme(value: str) -> str:
    return value.replace(" ", "")


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def dump_json(path: Path, data: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def build_sound_map(source_files: list[Path]) -> dict[str, str]:
    sound_map: dict[str, str] = {}

    for lesson_path in sorted(LESSONS_DIR.glob("*.json")) + source_files:
        try:
            lesson = load_json(lesson_path)
        except Exception:
            continue

        for block in lesson.get("blocks", {}).values():
            for slide in block.get("slides", []):
                if slide.get("view_type") != "flashcard":
                    continue
                payload = slide.get("content_payload", {})
                front_text = payload.get("front_text")
                back_text = payload.get("back_text")
                if isinstance(front_text, str) and isinstance(back_text, str) and back_text.startswith("/"):
                    sound_map[canonicalize_grapheme(front_text)] = back_text

    return sound_map


def split_review_flashcards(lesson_id: str, block: dict[str, Any], sound_map: dict[str, str]) -> list[str]:
    errors: list[str] = []
    slides = block.get("slides", [])
    if len(slides) != 1:
        return errors

    slide = slides[0]
    payload = slide.get("content_payload", {})
    review_phonemes = payload.get("review_phonemes")
    if not isinstance(review_phonemes, list):
        return errors

    new_slides = []
    for idx, grapheme in enumerate(review_phonemes, start=1):
        sound_key = canonicalize_grapheme(grapheme)
        if sound_key not in sound_map:
            errors.append(
                f"{lesson_id} block 01 cannot map review phoneme {grapheme!r} to current flashcard back_text."
            )
            continue

        new_slide = deepcopy(slide)
        new_slide["slide_id"] = f"01-{idx:02d}"
        new_slide["slide_title"] = "Review Known Sounds"
        new_slide["content_payload"] = {
            "front_text": grapheme,
            "back_text": sound_map[sound_key],
            "audio": None,
        }
        new_slides.append(new_slide)

    if not errors:
        block["slides"] = new_slides

    return errors


def split_dictation_words(lesson_id: str, block: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    slides = block.get("slides", [])
    if len(slides) != 1:
        return errors

    slide = slides[0]
    payload = slide.get("content_payload", {})
    dictation_words = payload.get("dictation_words")
    if not isinstance(dictation_words, list):
        return errors

    new_slides = []
    for idx, word in enumerate(dictation_words, start=1):
        if not isinstance(word, str) or not word.strip():
            errors.append(f"{lesson_id} block 02 has invalid dictation word {word!r}.")
            continue

        clean_word = word.strip()
        new_slide = deepcopy(slide)
        new_slide["slide_id"] = f"02-{idx:02d}"
        new_slide["slide_title"] = "Listen and Write"
        new_slide["content_payload"] = {
            "dictated_text": clean_word,
            "expected_answer": clean_word,
            "elkonin_boxes": len(clean_word.replace(" ", "")),
        }
        new_slides.append(new_slide)

    if not errors:
        block["slides"] = new_slides

    return errors


def normalize_flashcards(block: dict[str, Any]) -> None:
    for slide in block.get("slides", []):
        if slide.get("view_type") != "flashcard":
            continue
        payload = slide.get("content_payload", {})
        if payload.get("front_text") is None:
            payload["front_text"] = ""


def normalize_read_respond(block: dict[str, Any]) -> None:
    for slide in block.get("slides", []):
        if slide.get("view_type") != "read_respond":
            continue
        payload = slide.get("content_payload", {})

        text_content = payload.get("text_content")
        if not text_content:
            reader_sentences = payload.get("reader_sentences")
            note = payload.get("note")
            if isinstance(reader_sentences, list) and reader_sentences:
                payload["text_content"] = "\n".join(reader_sentences)
            elif isinstance(note, str) and note.strip():
                payload["text_content"] = note.strip()

        if not payload.get("comprehension_prompt"):
            after_reading_prompt = payload.get("after_reading_prompt")
            if isinstance(after_reading_prompt, str) and after_reading_prompt.strip():
                payload["comprehension_prompt"] = after_reading_prompt.strip()


def normalize_lesson_close(lesson_id: str, block: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for slide in block.get("slides", []):
        if slide.get("view_type") != "quick_check":
            continue
        payload = slide.get("content_payload", {})
        if payload.get("display_mode") != "lesson_close":
            continue

        if not payload.get("marking_options"):
            payload["marking_options"] = list(DEFAULT_CLOSE_MARKING_OPTIONS)

        check_items = payload.get("check_items")
        if isinstance(check_items, list) and check_items:
            continue

        oral_prompt = payload.get("oral_prompt")
        if isinstance(oral_prompt, str) and oral_prompt.strip():
            payload["check_items"] = [{"label": oral_prompt.strip(), "phoneme": None}]
            continue

        errors.append(
            f"{lesson_id} block 10 has no lesson-close prompts in check_items or oral_prompt."
        )

    return errors


def repair_lesson(data: dict[str, Any], sound_map: dict[str, str]) -> tuple[dict[str, Any], list[str]]:
    lesson = deepcopy(data)
    lesson_id = lesson.get("lesson_id", "<unknown>")
    errors: list[str] = []
    blocks = lesson.get("blocks", {})

    block_01 = blocks.get("01")
    if isinstance(block_01, dict):
        errors.extend(split_review_flashcards(lesson_id, block_01, sound_map))

    block_02 = blocks.get("02")
    if isinstance(block_02, dict):
        errors.extend(split_dictation_words(lesson_id, block_02))

    block_04 = blocks.get("04")
    if isinstance(block_04, dict):
        normalize_flashcards(block_04)

    block_06 = blocks.get("06")
    if isinstance(block_06, dict):
        normalize_read_respond(block_06)

    block_07 = blocks.get("07")
    if isinstance(block_07, dict):
        normalize_read_respond(block_07)

    block_10 = blocks.get("10")
    if isinstance(block_10, dict):
        errors.extend(normalize_lesson_close(lesson_id, block_10))

    return lesson, errors


def validate_lesson_data(data: dict[str, Any]) -> None:
    parse_lesson(data)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--write-source", action="store_true")
    parser.add_argument("--import-new", action="store_true")
    args = parser.parse_args()

    source_files = sorted(args.source_dir.glob("G*.json"))
    sound_map = build_sound_map(source_files)

    imported: list[str] = []
    skipped_existing: list[str] = []
    rejected: list[tuple[str, list[str]]] = []

    for source_path in source_files:
        original = load_json(source_path)
        repaired, repair_errors = repair_lesson(original, sound_map)

        if repair_errors:
            rejected.append((source_path.name, repair_errors))
            continue

        try:
            validate_lesson_data(repaired)
        except Exception as exc:
            rejected.append((source_path.name, [str(exc)]))
            continue

        if args.write_source:
            dump_json(source_path, repaired)

        if args.import_new:
            destination = LESSONS_DIR / source_path.name
            if destination.exists():
                skipped_existing.append(source_path.name)
            else:
                dump_json(destination, repaired)
                imported.append(source_path.name)

    print("IMPORTED")
    for name in imported:
        print(name)

    print("SKIPPED_EXISTING")
    for name in skipped_existing:
        print(name)

    print("REJECTED")
    for name, reasons in rejected:
        print(name)
        for reason in reasons:
            print(f"  - {reason}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
