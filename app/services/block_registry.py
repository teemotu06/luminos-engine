from app.services.block_definition import BlockDefinition


BLOCK_REGISTRY = [
    BlockDefinition(
        block_no=1,
        code="B1_REVIEW_FLASHCARDS",
        label="Flashcard Phoneme Review",
    ),
    BlockDefinition(
        block_no=2,
        code="B2_REVIEW_LISTEN_WRITE",
        label="Listening & Write Review",
    ),
    BlockDefinition(
        block_no=3,
        code="B3_NEW_SOUND",
        label="New Sound Introduction",
    ),
    BlockDefinition(
        block_no=4,
        code="B4_VOCAB_WARMUP",
        label="Vocabulary Warm-Up",
    ),
    BlockDefinition(
        block_no=5,
        code="B5_WORD_BUILDING",
        label="Word Building",
    ),
    BlockDefinition(
        block_no=6,
        code="B6_SENTENCE_BRIDGE",
        label="Sentence Bridge",
    ),
    BlockDefinition(
        block_no=7,
        code="B7_DECODABLE_READER",
        label="Decodable Reader / Fluency",
    ),
    BlockDefinition(
        block_no=8,
        code="B8_ENCODING_WRITING",
        label="Encoding & Writing",
    ),
    BlockDefinition(
        block_no=9,
        code="B9_MORPHEME_MOMENT",
        label="Morpheme Moment",
    ),
    BlockDefinition(
        block_no=10,
        code="B10_MEANING_CLOSE",
        label="Meaning-Making Close",
    ),
]