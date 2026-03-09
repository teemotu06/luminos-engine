from typing import Optional, List

from pydantic import BaseModel, Field


class Slide(BaseModel):
    id: str
    block_no: int = Field(ge=1, le=10)
    teacher_note: Optional[str] = None
    text: Optional[str] = None
    prompt: Optional[str] = None
    items: List[str] = Field(default_factory=list)
    dictation_items: List[str] = Field(default_factory=list)
    minimal_pairs: List[str] = Field(default_factory=list)
    vocab_items: List[str] = Field(default_factory=list)
    word_build_items: List[str] = Field(default_factory=list)
    sentence_items: List[str] = Field(default_factory=list)
    reader_lines: List[str] = Field(default_factory=list)
    encoding_items: List[str] = Field(default_factory=list)
    morpheme_items: List[str] = Field(default_factory=list)
    close_questions: List[str] = Field(default_factory=list)