from typing import Literal

from pydantic import BaseModel


BlockCode = Literal[
    "B1_REVIEW_FLASHCARDS",
    "B2_REVIEW_LISTEN_WRITE",
    "B3_NEW_SOUND",
    "B4_VOCAB_WARMUP",
    "B5_WORD_BUILDING",
    "B6_SENTENCE_BRIDGE",
    "B7_DECODABLE_READER",
    "B8_ENCODING_WRITING",
    "B9_MORPHEME_MOMENT",
    "B10_MEANING_CLOSE",
]


class BlockDefinition(BaseModel):
    block_no: int
    code: BlockCode
    label: str
    body_partial: str
