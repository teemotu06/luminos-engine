from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = REPO_ROOT / "app" / "static"
DIST_ROOT = STATIC_ROOT / "dist"
ASSETS = [
    "styles.css",
    "lesson.css",
    "oral_prompt_helper.js",
    "lesson.js",
    "lesson_launcher.js",
    "lesson_teacher.js",
    "lesson_review.js",
]

# Vendored third-party assets — copied as-is (no minification)
VENDOR_ASSETS = [
    "alpinejs.min.js",
]


def minify_css(source: str) -> str:
    without_comments = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    collapsed = re.sub(r"\s+", " ", without_comments)
    tightened = re.sub(r"\s*([{}:;,>])\s*", r"\1", collapsed)
    return tightened.strip() + "\n"


def minify_js(source: str) -> str:
    lines = [line.strip() for line in source.splitlines() if line.strip()]
    return "\n".join(lines) + "\n"


def fingerprint(contents: str) -> str:
    return hashlib.sha256(contents.encode("utf-8")).hexdigest()[:12]


def build_asset(relative_path: str) -> tuple[Path, str]:
    source_path = STATIC_ROOT / relative_path
    destination_path = DIST_ROOT / relative_path
    original = source_path.read_text(encoding="utf-8")
    if source_path.suffix == ".css":
        built = minify_css(original)
    else:
        built = minify_js(original)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    destination_path.write_text(built, encoding="utf-8")
    return destination_path, fingerprint(built)


def check_asset(relative_path: str) -> bool:
    source_path = STATIC_ROOT / relative_path
    destination_path = DIST_ROOT / relative_path
    if not destination_path.exists():
        print(f"Missing built asset: {destination_path}")
        return False
    original = source_path.read_text(encoding="utf-8")
    current = destination_path.read_text(encoding="utf-8")
    expected = minify_css(original) if source_path.suffix == ".css" else minify_js(original)
    if current != expected:
        print(f"Out-of-date built asset: {destination_path}")
        return False
    return True


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    if args.check:
        ok = all(check_asset(asset) for asset in ASSETS)
        return 0 if ok else 1

    built_assets = [build_asset(asset) for asset in ASSETS]
    for path, digest in built_assets:
        print(f"built {path.relative_to(REPO_ROOT)} {digest}")

    for vendor in VENDOR_ASSETS:
        src = STATIC_ROOT / vendor
        dst = DIST_ROOT / vendor
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())
        print(f"copied {dst.relative_to(REPO_ROOT)}")

    manifest: dict[str, str] = {}
    for asset, (_, digest) in zip(ASSETS, built_assets):
        name = Path(asset).name
        manifest[name] = f"/static/dist/{name}?v={digest}"
    for vendor in VENDOR_ASSETS:
        manifest[vendor] = f"/static/dist/{vendor}"

    manifest_path = DIST_ROOT / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {manifest_path.relative_to(REPO_ROOT)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
