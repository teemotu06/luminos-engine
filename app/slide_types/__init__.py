from app.slide_types.registry import registry

# Import definitions for module-level side effects so the singleton registry is
# fully populated anywhere `app.slide_types` is imported.
from app.slide_types.definitions import flashcard  # noqa: F401
from app.slide_types.definitions import phonemes  # noqa: F401
from app.slide_types.definitions import spell_word  # noqa: F401
from app.slide_types.definitions import listen_spell  # noqa: F401
from app.slide_types.definitions import sound_match  # noqa: F401
from app.slide_types.definitions import pattern_noticing  # noqa: F401
from app.slide_types.definitions import audio_prompt  # noqa: F401
from app.slide_types.definitions import minimal_pair  # noqa: F401
from app.slide_types.definitions import drag_letter  # noqa: F401
from app.slide_types.definitions import drag_word  # noqa: F401
from app.slide_types.definitions import read_respond  # noqa: F401
from app.slide_types.definitions import writing_encoding  # noqa: F401
from app.slide_types.definitions import quick_check  # noqa: F401
from app.slide_types.definitions import connect_word_to_picture  # noqa: F401
from app.slide_types.definitions import fill_in_the_blank  # noqa: F401
from app.slide_types.definitions import word_sort  # noqa: F401
from app.slide_types.definitions import sentence_builder  # noqa: F401

__all__ = ["registry"]
