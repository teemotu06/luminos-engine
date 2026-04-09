from typing import Dict, List, Optional, Union, Literal

from pydantic import BaseModel, Field, model_validator

from app.services.pattern_noticing_service import (
    DEFAULT_PATTERN_PROMPT,
    adapt_pattern_noticing_payload,
    parse_bracket_word,
)


def _normalize_drag_units(raw_units: List[str]) -> List[str]:
    return [str(item).strip() for item in (raw_units or []) if str(item).strip()]


def _auto_segment_drag_word(raw_word: str) -> List[str]:
    word = str(raw_word or "").strip()
    if not word:
        return []
    graphemes = [
        "tch", "igh", "dge",
        "ck", "sh", "ch", "th", "wh", "ph", "ng", "nk", "qu",
        "ee", "oo", "ai", "ay", "oa", "ow", "oi", "oy", "ar", "or", "er", "ir", "ur", "ea", "ie",
    ]
    units: List[str] = []
    index = 0
    lower = word.lower()
    while index < len(word):
        match = next((item for item in graphemes if lower.startswith(item, index)), None)
        if match:
            units.append(word[index : index + len(match)])
            index += len(match)
        else:
            units.append(word[index : index + 1])
            index += 1
    return units


class LuminosSaysConfig(BaseModel):
    enabled: bool = True
    prompt_text: Optional[str] = None
    support_text: Optional[str] = None
    auto_speak: bool = True


class TeacherPrompt(BaseModel):
    text: str = Field(..., min_length=1)
    audio_url: Optional[str] = None


class PhonemePayload(BaseModel):
    symbol: str = Field(..., min_length=1)
    prompt_text: Optional[str] = None
    luminos_says: Optional[LuminosSaysConfig] = None


class SpellWordPayload(BaseModel):
    correct_word: str = Field(..., min_length=1)
    letter_pool: List[str] = Field(default_factory=list)
    prompt_text: Optional[str] = None
    luminos_says: Optional[LuminosSaysConfig] = None

    @model_validator(mode="after")
    def normalize_spell_word_fields(self):
        correct_word = str(self.correct_word or "").strip()
        if not correct_word:
            raise ValueError("Spell the Word requires a correct word.")

        pool = _normalize_drag_units(self.letter_pool)
        if not pool:
            pool = list(correct_word.replace(" ", ""))
        if not pool:
            raise ValueError("Spell the Word requires at least one letter tile.")

        self.correct_word = correct_word
        self.letter_pool = pool
        return self


class PatternNoticingSegment(BaseModel):
    text: str = Field(..., min_length=1)
    highlight: bool = False


class PatternNoticingWord(BaseModel):
    segments: List[PatternNoticingSegment] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_segments(self):
        segments = [segment for segment in self.segments if str(segment.text or "").strip()]
        if not segments:
            raise ValueError("Pattern Noticing words require at least one segment.")
        self.segments = segments
        return self


class PatternNoticingPayload(BaseModel):
    words: List[PatternNoticingWord] = Field(..., min_length=2, max_length=4)
    prompt: str = Field(default=DEFAULT_PATTERN_PROMPT, min_length=1)
    reveal_mode: Literal["sequential", "all_at_once"] = "sequential"
    luminos_says: Optional[LuminosSaysConfig] = None

    @model_validator(mode="before")
    @classmethod
    def adapt_legacy_spot_part_payload(cls, value):
        if isinstance(value, dict):
            adapted = adapt_pattern_noticing_payload(str(value.get("view_type") or "pattern_noticing"), value)
            if adapted is not None:
                return adapted
        return value

    @model_validator(mode="after")
    def normalize_pattern_words(self):
        if len(self.words) < 2 or len(self.words) > 4:
            raise ValueError("Pattern Noticing requires between 2 and 4 words.")
        cleaned_words: List[PatternNoticingWord] = []
        for word in self.words:
            segments = [
                PatternNoticingSegment(text=str(segment.text).strip(), highlight=bool(segment.highlight))
                for segment in word.segments
                if str(segment.text or "").strip()
            ]
            if not segments:
                continue
            cleaned_words.append(PatternNoticingWord(segments=segments))
        if len(cleaned_words) < 2:
            raise ValueError("Pattern Noticing requires at least two words.")
        self.words = cleaned_words[:4]
        self.prompt = str(self.prompt or DEFAULT_PATTERN_PROMPT).strip() or DEFAULT_PATTERN_PROMPT
        self.reveal_mode = str(self.reveal_mode or "sequential").strip() or "sequential"
        return self


class BlendUnit(BaseModel):
    grapheme: str
    phoneme: Optional[str] = None
    audio: Optional[str] = None


class FlashcardPayload(BaseModel):
    front_text: Optional[str] = None
    front_image: Optional[str] = None
    back_text: Optional[str] = None
    back_image: Optional[str] = None
    image: Optional[str] = None
    audio: Optional[str] = None
    blend_units: Optional[List[BlendUnit]] = None
    word_types: Dict[str, str] = Field(default_factory=dict)
    luminos_says: Optional[LuminosSaysConfig] = None

    @model_validator(mode="after")
    def validate_flashcard_sides(self):
        front_text = (self.front_text or "").strip() or None
        front_image = (self.front_image or "").strip() or None
        back_text = (self.back_text or "").strip() or None
        back_image = (self.back_image or "").strip() or None

        if front_text and front_image:
            raise ValueError("Flashcard front must use either text or image, not both.")
        if back_text and back_image:
            raise ValueError("Flashcard back must use either text or image, not both.")
        if not front_text and not front_image and not self.image:
            raise ValueError("Flashcard front requires text or image.")
        if not back_text and not back_image and not self.image:
            raise ValueError("Flashcard back requires text or image.")
        return self


class AudioPromptPayload(BaseModel):
    audio_file: str
    prompt_text: str
    reveal_text: Optional[str] = None
    image: Optional[str] = None
    luminos_says: Optional[LuminosSaysConfig] = None


class MinimalPairChoice(BaseModel):
    label: str
    audio: str


class MinimalPairPayload(BaseModel):
    pair_A: MinimalPairChoice
    pair_B: MinimalPairChoice
    correct_choice: Literal["A", "B"]
    korean_flag: Optional[str] = None
    correction_routine: Optional[str] = None
    luminos_says: Optional[LuminosSaysConfig] = None


class DragLetterPayload(BaseModel):
    prompt_text: Optional[str] = None
    target_word: str
    target_letters: List[str] = Field(default_factory=list)
    slots: List[str] = Field(default_factory=list)
    draggable_letters: List[str] = Field(default_factory=list)
    image: Optional[str] = None
    audio: Optional[str] = None
    luminos_says: Optional[LuminosSaysConfig] = None

    @model_validator(mode="after")
    def normalize_drag_letter_fields(self):
        target_word = str(self.target_word or "").strip()
        target_letters = _normalize_drag_units(self.target_letters)
        slots = _normalize_drag_units(self.slots)
        draggable_letters = _normalize_drag_units(self.draggable_letters)

        canonical_units: List[str] = []
        if target_word:
            lower_target = target_word.lower()
            for candidate in (target_letters, slots, draggable_letters):
                if candidate and "".join(candidate).lower() == lower_target:
                    canonical_units = candidate
                    break
            if not canonical_units:
                canonical_units = _auto_segment_drag_word(target_word)
        else:
            canonical_units = target_letters or slots or draggable_letters
            target_word = "".join(canonical_units)

        if not canonical_units:
            raise ValueError("Build the Word requires at least one unit.")

        self.target_word = target_word or "".join(canonical_units)
        self.target_letters = list(canonical_units)
        self.slots = list(canonical_units)
        self.draggable_letters = list(canonical_units)
        return self


class DragWordPayload(BaseModel):
    target_sentence: str
    word_cards: List[str] = Field(default_factory=list)
    punctuation_card: Optional[str] = None
    image: Optional[str] = None
    luminos_says: Optional[LuminosSaysConfig] = None


class ReadRespondPayload(BaseModel):
    text_content: Optional[str] = None
    highlight_pattern: Optional[str] = None
    audio_support: Optional[str] = None
    image: Optional[str] = None
    comprehension_prompt: Optional[str] = None
    comprehension_questions: List[str] = Field(default_factory=list)
    display_mode: Optional[str] = None
    displayed_words: List[str] = Field(default_factory=list)
    highlighted_chunk: Optional[str] = None
    support_text: Optional[str] = None
    show_font_controls: bool = False
    word_types: Dict[str, str] = Field(default_factory=dict)
    token_units: Dict[str, List[str]] = Field(default_factory=dict)
    oral_enforcement: Optional["OralEnforcementConfig"] = None

    prompt_text: Optional[str] = None
    target_word: Optional[str] = None
    phoneme_parts: List[str] = Field(default_factory=list)
    blend_audio: Optional[str] = None
    word_audio: Optional[str] = None
    luminos_says: Optional[LuminosSaysConfig] = None


class OralEnforcementConfig(BaseModel):
    enabled: bool = False
    participation_mode: Literal["full_roster", "short_reader_full_roster", "audit_roster"] = "full_roster"
    text_length_mode: Literal["normal", "short"] = "normal"
    prompt_mode: Optional[Literal["read_story", "answer_question", "answer_with_story", "retell", "show_and_explain"]] = None
    prompt_text: Optional[str] = None
    rehearsal_seconds: int = 30
    required_evidence_count: int = 1
    allow_teacher_override: bool = True
    require_resolution_for_all: bool = True
    fluency_retry_on_shaky: bool = True
    auto_queue_missed_for_reteach: bool = True
    audit_sample_size: int = 0
    audit_selection_strategy: Literal["roster_order", "least_recently_checked"] = "roster_order"
    performance_types: List[str] = Field(default_factory=list)

class WritingEncodingPayload(BaseModel):
    audio_prompt: Optional[str] = None
    prompt_text: Optional[str] = None
    dictated_text: str
    expected_answer: str
    display_mode: Optional[str] = None
    elkonin_boxes: Optional[int] = None
    grapheme_units: List[str] = Field(default_factory=list)
    luminos_says: Optional[LuminosSaysConfig] = None


class QuickCheckItem(BaseModel):
    label: str
    phoneme: Optional[str] = None


class QuickCheckPayload(BaseModel):
    display_mode: Optional[str] = None
    title: Optional[str] = None
    check_items: List[QuickCheckItem] = Field(default_factory=list)
    marking_options: List[str] = Field(default_factory=list)
    notes_field: Optional[str] = None
    luminos_says: Optional[LuminosSaysConfig] = None


class MatchItem(BaseModel):
    word: str
    image_url: str
    audio_url: Optional[str] = None


class ConnectWordToPicturePayload(BaseModel):
    items: List[MatchItem] = Field(..., min_length=1)
    instruction_text: str = "Match each word to its picture"
    shuffle_items: bool = True
    luminos_says: Optional[LuminosSaysConfig] = None


class FillInTheBlankPayload(BaseModel):
    sentence_template: str
    correct_answer: str
    distractors: List[str] = Field(default_factory=list)
    hint_text: Optional[str] = None
    audio_url: Optional[str] = None
    image_url: Optional[str] = None
    luminos_says: Optional[LuminosSaysConfig] = None


class SortCategory(BaseModel):
    category_label: str
    words: List[str] = Field(default_factory=list)


class WordSortPayload(BaseModel):
    instruction_text: str = "Sort the words into the correct groups"
    categories: List[SortCategory] = Field(..., min_length=2)
    audio_per_word: bool = False
    luminos_says: Optional[LuminosSaysConfig] = None


class SentenceBuilderPayload(BaseModel):
    target_sentence: str
    word_tiles: List[str] = Field(default_factory=list)
    has_distractors: bool = False
    image_url: Optional[str] = None
    audio_url: Optional[str] = None
    luminos_says: Optional[LuminosSaysConfig] = None


SlidePayload = Union[
    PhonemePayload,
    SpellWordPayload,
    PatternNoticingPayload,
    FlashcardPayload,
    AudioPromptPayload,
    MinimalPairPayload,
    DragLetterPayload,
    DragWordPayload,
    ReadRespondPayload,
    WritingEncodingPayload,
    QuickCheckPayload,
    ConnectWordToPicturePayload,
    FillInTheBlankPayload,
    WordSortPayload,
    SentenceBuilderPayload,
]


def get_payload_model(view_type: str) -> type[BaseModel]:
    from app.slide_types import registry

    return registry.payload_model_for(view_type)
