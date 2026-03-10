from typing import List, Optional, Union
from typing_extensions import Literal

from pydantic import BaseModel, Field


class FlashcardPayload(BaseModel):
    front_text: str
    back_text: Optional[str] = None
    audio: Optional[str] = None


class AudioPromptPayload(BaseModel):
    audio_file: str
    prompt_text: str
    reveal_text: Optional[str] = None
    image: Optional[str] = None


class MinimalPairChoice(BaseModel):
    label: str
    audio: str


class MinimalPairPayload(BaseModel):
    pair_A: MinimalPairChoice
    pair_B: MinimalPairChoice
    correct_choice: Literal["A", "B"]
    korean_flag: Optional[str] = None
    correction_routine: Optional[str] = None


class DragLetterPayload(BaseModel):
    prompt_text: str
    target_word: str
    slots: List[str] = Field(default_factory=list)
    draggable_letters: List[str] = Field(default_factory=list)
    image: Optional[str] = None
    audio: Optional[str] = None


class DragWordPayload(BaseModel):
    target_sentence: str
    word_cards: List[str] = Field(default_factory=list)
    punctuation_card: Optional[str] = None
    image: Optional[str] = None


class ReadRespondPayload(BaseModel):
    text_content: str
    highlight_pattern: Optional[str] = None
    audio_support: Optional[str] = None
    comprehension_prompt: Optional[str] = None


class WritingEncodingPayload(BaseModel):
    audio_prompt: Optional[str] = None
    dictated_text: str
    expected_answer: str
    elkonin_boxes: Optional[int] = None


class QuickCheckItem(BaseModel):
    label: str
    phoneme: Optional[str] = None


class QuickCheckPayload(BaseModel):
    check_items: List[QuickCheckItem] = Field(default_factory=list)
    marking_options: List[str] = Field(default_factory=list)
    notes_field: Optional[str] = None


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