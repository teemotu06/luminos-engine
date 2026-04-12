from pathlib import Path

import pytest

from app.schemas.slide_payloads import FillInTheBlankPayload, ListenSpellPayload, SentenceBuilderPayload, WordSortPayload
from app.slide_types import registry


@pytest.mark.parametrize(
    "type_key,label",
    [
        ("listen_spell", "Listen & Spell"),
        ("fill_in_the_blank", "Fill in the Blank"),
        ("word_sort", "Word Sort"),
        ("sentence_builder", "Sentence Builder"),
    ],
)
def test_new_types_registered_and_templates_exist(type_key, label):
    assert type_key in registry.all_type_keys()
    definition = registry.get(type_key)
    assert definition.label == label
    definition.payload_model(**definition.default_payload)
    assert isinstance(registry.summary_for(type_key, definition.default_payload), str)
    assert Path("app/templates/%s" % registry.teacher_template_for(type_key)).exists()
    assert Path("app/templates/%s" % registry.board_template_for(type_key)).exists()


def test_fill_in_the_blank_payload_rules():
    FillInTheBlankPayload(sentence_template="The ___ is red.", correct_answer="cat")
    with pytest.raises(Exception):
        FillInTheBlankPayload(sentence_template="The ___ is red.")


def test_word_sort_payload_validates_with_two_categories():
    payload = WordSortPayload(categories=[{"category_label": "Short a", "words": ["cat"]}, {"category_label": "Long a", "words": ["cake"]}])
    assert len(payload.categories) == 2


def test_sentence_builder_payload_validates():
    payload = SentenceBuilderPayload(target_sentence="I can read.", word_tiles=["I", "can", "read."])
    assert payload.target_sentence == "I can read."


def test_listen_spell_payload_validates():
    payload = ListenSpellPayload(target_word="ship", target_pattern="sh")
    assert payload.target_word == "ship"
