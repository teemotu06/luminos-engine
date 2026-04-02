#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from typing import List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.controlled_text_validator import validate_lessons_strict


LESSONS_DIR = ROOT / "app" / "content" / "lessons"


def load_raw_lessons(*, include_ki: bool = False) -> list[dict]:
    lessons = []
    patterns = ["G*.json"]
    if include_ki:
        patterns.append("KI*.json")
    for pattern in patterns:
        for path in sorted(LESSONS_DIR.glob(pattern)):
            with path.open("r", encoding="utf-8") as handle:
                lesson = json.load(handle)
            lesson.setdefault("json_path", str(path.relative_to(ROOT / "app")))
            lessons.append(lesson)
    return lessons


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate controlled text compliance.")
    parser.add_argument(
        "--include-ki",
        action="store_true",
        help="Include Korean intervention lessons using the intervention validation profile.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    lessons = load_raw_lessons(include_ki=args.include_ki)
    result = validate_lessons_strict(lessons)

    code_counts = Counter()
    failing_reports = [report for report in result.reports if report.errors]

    print(f"total_lessons\t{len(result.reports)}")
    print(f"failing_lessons\t{len(failing_reports)}")
    print(f"total_errors\t{result.error_count}")
    print(f"include_ki\t{str(args.include_ki).lower()}")

    for report in failing_reports:
        print(f"\n[{report.lesson_id}]")
        for error in report.errors:
            code_counts[error.code] += 1
            location = " / ".join(
                part
                for part in [error.block_id, error.slide_id]
                if part
            )
            if location:
                print(f"- {error.code} @ {location}: {error.message}")
            else:
                print(f"- {error.code}: {error.message}")

    if code_counts:
        print("\nerror_code_counts")
        for code, count in sorted(code_counts.items()):
            print(f"{code}\t{count}")

    return 1 if failing_reports else 0


if __name__ == "__main__":
    raise SystemExit(main())
