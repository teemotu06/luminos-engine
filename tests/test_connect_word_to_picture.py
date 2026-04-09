import pytest

from app.schemas.slide_payloads import ConnectWordToPicturePayload
from app.slide_types import registry


def test_connect_word_to_picture_payload_validates_with_valid_items():
    payload = ConnectWordToPicturePayload(
        items=[
            {"word": "cat", "image_url": "/static/uploads/images/cat.png"},
            {"word": "dog", "image_url": "/static/uploads/images/dog.png", "audio_url": "/static/uploads/audio/dog.mp3"},
        ]
    )
    assert len(payload.items) == 2


def test_connect_word_to_picture_payload_rejects_empty_items_list():
    with pytest.raises(Exception):
        ConnectWordToPicturePayload(items=[])


def test_connect_word_to_picture_payload_validates_with_optional_audio():
    payload = ConnectWordToPicturePayload(
        items=[{"word": "sun", "image_url": "/static/uploads/images/sun.png", "audio_url": None}]
    )
    assert payload.items[0].audio_url is None


def test_default_payload_from_registry_validates_against_model():
    definition = registry.get("connect_word_to_picture")
    payload = definition.payload_model(**definition.default_payload)
    assert len(payload.items) == 2


def test_summary_extractor_returns_comma_joined_words():
    summary = registry.summary_for(
        "connect_word_to_picture",
        {
            "items": [
                {"word": "cat", "image_url": "/a.png"},
                {"word": "dog", "image_url": "/b.png"},
            ]
        },
    )
    assert summary == "cat, dog"


def test_summary_extractor_handles_empty_items_gracefully():
    summary = registry.summary_for(
        "connect_word_to_picture",
        {"items": [{"word": "", "image_url": ""}, {"word": "", "image_url": ""}]},
    )
    assert summary == "No items"
