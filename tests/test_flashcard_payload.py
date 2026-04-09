from app.schemas.slide_payloads import FlashcardPayload


def test_flashcard_payload_supports_explicit_front_and_back_images():
    payload = FlashcardPayload(
        front_image="/static/uploads/images/front-snake.png",
        back_image="/static/uploads/images/back-snake.png",
    )

    assert payload.front_text is None
    assert payload.front_image == "/static/uploads/images/front-snake.png"
    assert payload.back_image == "/static/uploads/images/back-snake.png"


def test_flashcard_payload_keeps_legacy_image_field_for_backward_compatibility():
    payload = FlashcardPayload(
        front_text="s",
        back_text="/s/",
        image="/static/uploads/images/legacy-snake.png",
    )

    assert payload.image == "/static/uploads/images/legacy-snake.png"
    assert payload.front_image is None
    assert payload.back_image is None


def test_flashcard_payload_rejects_text_and_image_on_same_side():
    try:
        FlashcardPayload(
            front_text="s",
            front_image="/static/uploads/images/front.png",
            back_text="/s/",
        )
    except Exception as exc:
        assert "front must use either text or image" in str(exc)
    else:
        raise AssertionError("Expected validation error for mixed front content")
