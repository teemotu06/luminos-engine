import pytest

from app.services.slide_editor_service import add_slide, delete_slide, get_slide, reorder_slides, update_slide


def _lesson():
    return {
        "blocks": {
            "01": {"block_id": "01", "label": "Flashcard Phoneme Review", "slides": []},
        }
    }


def _teaching_updates():
    return {
        "slide_title": "Updated Slide",
        "teacher_cue": "Teach it.",
        "expected_response": "Students respond.",
        "correction_move": "Model and retry.",
        "observation_note": "Watch for accuracy.",
    }


def test_add_slide_to_empty_block_creates_default_payload():
    lesson = _lesson()
    add_slide(lesson, "01", "flashcard")
    slide = lesson["blocks"]["01"]["slides"][0]
    assert slide["view_type"] == "flashcard"
    assert slide["content_payload"]["front_text"] == "Example"


def test_add_slide_at_specific_position_inserts_correctly():
    lesson = _lesson()
    add_slide(lesson, "01", "flashcard")
    first_id = lesson["blocks"]["01"]["slides"][0]["slide_id"]
    add_slide(lesson, "01", "audio_prompt", position=0)
    assert lesson["blocks"]["01"]["slides"][0]["view_type"] == "audio_prompt"
    assert lesson["blocks"]["01"]["slides"][1]["slide_id"] == first_id


def test_update_slide_merges_payload_fields():
    lesson = _lesson()
    add_slide(lesson, "01", "flashcard")
    slide_id = lesson["blocks"]["01"]["slides"][0]["slide_id"]
    updates = _teaching_updates()
    updates["payload"] = {"front_text": "Updated"}
    update_slide(lesson, "01", slide_id, updates)
    assert get_slide(lesson, "01", slide_id)["content_payload"]["front_text"] == "Updated"


def test_update_slide_with_luminos_says_updates_correctly():
    lesson = _lesson()
    add_slide(lesson, "01", "flashcard")
    slide_id = lesson["blocks"]["01"]["slides"][0]["slide_id"]
    updates = _teaching_updates()
    updates["luminos_says"] = {"prompt_text": "Say it", "auto_speak": True}
    update_slide(lesson, "01", slide_id, updates)
    assert get_slide(lesson, "01", slide_id)["content_payload"]["luminos_says"]["prompt_text"] == "Say it"


def test_delete_slide_removes_it_from_block():
    lesson = _lesson()
    add_slide(lesson, "01", "flashcard")
    slide_id = lesson["blocks"]["01"]["slides"][0]["slide_id"]
    delete_slide(lesson, "01", slide_id)
    assert lesson["blocks"]["01"]["slides"] == []


def test_reorder_slides_changes_order():
    lesson = _lesson()
    add_slide(lesson, "01", "flashcard")
    add_slide(lesson, "01", "audio_prompt")
    slide_ids = [slide["slide_id"] for slide in lesson["blocks"]["01"]["slides"]]
    reorder_slides(lesson, "01", list(reversed(slide_ids)))
    assert [slide["slide_id"] for slide in lesson["blocks"]["01"]["slides"]] == list(reversed(slide_ids))


def test_reorder_with_mismatched_ids_raises():
    lesson = _lesson()
    add_slide(lesson, "01", "flashcard")
    with pytest.raises(ValueError):
        reorder_slides(lesson, "01", ["missing"])


def test_get_slide_returns_correct_slide_or_none():
    lesson = _lesson()
    add_slide(lesson, "01", "flashcard")
    slide_id = lesson["blocks"]["01"]["slides"][0]["slide_id"]
    assert get_slide(lesson, "01", slide_id)["slide_id"] == slide_id
    assert get_slide(lesson, "01", "missing") is None
