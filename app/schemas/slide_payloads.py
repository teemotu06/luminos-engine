from typing import Dict, List, Optional, Union, Literal

from pydantic import BaseModel, Field


class LuminosSaysConfig(BaseModel):
    enabled: bool = True
    prompt_text: Optional[str] = None
    support_text: Optional[str] = None
    auto_speak: bool = True


class BlendUnit(BaseModel):
    grapheme: str
    phoneme: Optional[str] = None
    audio: Optional[str] = None


class FlashcardPayload(BaseModel):
    front_text: str
    back_text: Optional[str] = None
    image: Optional[str] = None
    audio: Optional[str] = None
    blend_units: Optional[List[BlendUnit]] = None
    word_types: Dict[str, str] = Field(default_factory=dict)
    luminos_says: Optional[LuminosSaysConfig] = None


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


SlidePayload = Union[
    FlashcardPayload,
    AudioPromptPayload,
    MinimalPairPayload,
    DragLetterPayload,
    DragWordPayload,
    ReadRespondPayload,
    WritingEncodingPayload,
    QuickCheckPayload,
]

VIEW_PAYLOAD_MAP = {
    "flashcard": FlashcardPayload,
    "audio_prompt": AudioPromptPayload,
    "minimal_pair": MinimalPairPayload,
    "drag_letter": DragLetterPayload,
    "drag_word": DragWordPayload,
    "read_respond": ReadRespondPayload,
    "writing_encoding": WritingEncodingPayload,
    "quick_check": QuickCheckPayload,
}
