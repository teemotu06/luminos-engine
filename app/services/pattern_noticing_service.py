from __future__ import annotations

from typing import Iterable, Optional


DEFAULT_PATTERN_PROMPT = "What do you notice? Which sound part do they share?"


def parse_bracket_word(raw_word: str) -> list[dict]:
    text = str(raw_word or "").strip()
    if not text:
        return []
    segments: list[dict] = []
    buffer = ""
    highlight_buffer = ""
    in_highlight = False
    for char in text:
        if char == "[" and not in_highlight:
            if buffer:
                segments.append({"text": buffer, "highlight": False})
                buffer = ""
            in_highlight = True
            highlight_buffer = ""
            continue
        if char == "]" and in_highlight:
            if highlight_buffer:
                segments.append({"text": highlight_buffer, "highlight": True})
            highlight_buffer = ""
            in_highlight = False
            continue
        if in_highlight:
            highlight_buffer += char
        else:
            buffer += char
    if highlight_buffer:
        segments.append({"text": highlight_buffer, "highlight": True})
    if buffer:
        segments.append({"text": buffer, "highlight": False})
    if not segments:
        segments.append({"text": text.replace("[", "").replace("]", ""), "highlight": False})
    return [segment for segment in segments if str(segment.get("text") or "").strip()]


def segments_to_bracket_word(segments: Iterable[dict]) -> str:
    parts: list[str] = []
    for segment in segments or []:
        text = str((segment or {}).get("text") or "").strip()
        if not text:
            continue
        if bool((segment or {}).get("highlight")):
            parts.append(f"[{text}]")
        else:
            parts.append(text)
    return "".join(parts)


def segments_to_plain_word(segments: Iterable[dict]) -> str:
    return "".join(str((segment or {}).get("text") or "") for segment in (segments or [])).strip()


def build_highlight_segments(word: str, highlighted_chunk: Optional[str]) -> list[dict]:
    raw_word = str(word or "").strip()
    chunk = str(highlighted_chunk or "").strip()
    if not raw_word:
        return []
    if not chunk or chunk not in raw_word:
        return [{"text": raw_word, "highlight": False}]
    prefix, suffix = raw_word.split(chunk, 1)
    segments: list[dict] = []
    if prefix:
        segments.append({"text": prefix, "highlight": False})
    segments.append({"text": chunk, "highlight": True})
    if suffix:
        segments.append({"text": suffix, "highlight": False})
    return segments


def adapt_pattern_noticing_payload(view_type: str, payload: Optional[dict]) -> Optional[dict]:
    payload_dict = dict(payload or {})
    if str(view_type or "") == "pattern_noticing":
        words = payload_dict.get("words") or []
        return {
            "words": [
                {"segments": parse_bracket_word(segments_to_bracket_word((word or {}).get("segments") or []))}
                for word in words
            ],
            "prompt": str(payload_dict.get("prompt") or DEFAULT_PATTERN_PROMPT).strip() or DEFAULT_PATTERN_PROMPT,
            "reveal_mode": str(payload_dict.get("reveal_mode") or "sequential").strip() or "sequential",
        }
    if str(view_type or "") == "read_respond" and str(payload_dict.get("display_mode") or "") == "spot_part":
        displayed_words = payload_dict.get("displayed_words") or []
        highlighted_chunk = payload_dict.get("highlighted_chunk")
        support_text = str(
            payload_dict.get("support_text")
            or payload_dict.get("prompt")
            or payload_dict.get("prompt_text")
            or DEFAULT_PATTERN_PROMPT
        ).strip() or DEFAULT_PATTERN_PROMPT
        return {
            "words": [
                {"segments": build_highlight_segments(word, highlighted_chunk)}
                for word in displayed_words
                if str(word or "").strip()
            ],
            "prompt": support_text,
            "reveal_mode": str(payload_dict.get("reveal_mode") or "sequential").strip() or "sequential",
        }
    return None


def is_pattern_noticing_slide(view_type: str, payload: Optional[dict]) -> bool:
    return adapt_pattern_noticing_payload(view_type, payload) is not None

