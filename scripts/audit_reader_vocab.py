import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LESSON_DIR = ROOT / "app" / "content" / "lessons"
SUPPORT_BANK_PATH = ROOT / "app" / "content" / "reader_support_bank.json"
WORD_RE = re.compile(r"[A-Za-z]+(?:-[A-Za-z]+)?")


def lesson_number(path: Path) -> int:
    match = re.search(r"L(\d+)", path.stem)
    return int(match.group(1)) if match else 0


def normalize(word: str) -> str:
    return word.lower()


def extract_words(text: str) -> list[str]:
    return [normalize(match.group(0)) for match in WORD_RE.finditer(text or "")]


def block04_vocab(lesson: dict) -> set[str]:
    vocab: set[str] = set()
    for slide in lesson["blocks"]["04"]["slides"]:
        payload = slide.get("content_payload", {})
        for key in ("front_text", "target_word", "dictated_text", "expected_answer"):
            value = payload.get(key)
            if isinstance(value, str):
                vocab.update(extract_words(value))
    return vocab


def reader_text(lesson: dict) -> str:
    return "\n".join(
        slide.get("content_payload", {}).get("text_content", "")
        for slide in lesson["blocks"]["07"]["slides"]
    )


def main() -> None:
    support_bank = set(
        json.loads(SUPPORT_BANK_PATH.read_text()).get("approved_words", [])
    )
    cumulative_vocab: set[str] = set()

    results = []
    for path in sorted(LESSON_DIR.glob("*.json"), key=lesson_number):
        lesson = json.loads(path.read_text())
        lesson_id = lesson["lesson_id"]
        sight_words = {normalize(word) for word in (lesson.get("sight_words") or [])}
        current_block04 = block04_vocab(lesson)
        allowed = cumulative_vocab | current_block04 | sight_words | support_bank

        unknown = []
        seen = set()
        for word in extract_words(reader_text(lesson)):
            if word not in allowed and word not in seen:
                unknown.append(word)
                seen.add(word)

        results.append((lesson_id, len(unknown), unknown))
        cumulative_vocab |= current_block04

    failing = [row for row in results if row[1] > 0]
    print(f"lessons_with_reader_vocab_violations\t{len(failing)}")
    print(f"total_lessons\t{len(results)}")
    print("lesson_id\tunknown_count\tunknown_words")
    for lesson_id, count, words in failing:
        print(f"{lesson_id}\t{count}\t{', '.join(words)}")


if __name__ == "__main__":
    main()
