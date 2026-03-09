from app.services.block_definition import BlockDefinition


BLOCK_REGISTRY = [
    BlockDefinition(
        block_no=1,
        code="B1_REVIEW_FLASHCARDS",
        label="Flashcard Phoneme Review",
        body_partial="lesson/partials/bodies/block_body_flashcards.html",
    ),
    BlockDefinition(
        block_no=2,
        code="B2_REVIEW_LISTEN_WRITE",
        label="Listening & Write Review",
        body_partial="lesson/partials/bodies/block_body_listen_write.html",
    ),
    BlockDefinition(
        block_no=3,
        code="B3_NEW_SOUND",
        label="New Sound Introduction",
        body_partial="lesson/partials/bodies/block_body_new_sound.html",
    ),
    BlockDefinition(
        block_no=4,
        code="B4_VOCAB_WARMUP",
        label="Vocabulary Warm-Up",
        body_partial="lesson/partials/bodies/block_body_vocab_warmup.html",
    ),
    BlockDefinition(
        block_no=5,
        code="B5_WORD_BUILDING",
        label="Word Building",
        body_partial="lesson/partials/bodies/block_body_word_building.html",
    ),
    BlockDefinition(
        block_no=6,
        code="B6_SENTENCE_BRIDGE",
        label="Sentence Bridge",
        body_partial="lesson/partials/bodies/block_body_sentence_bridge.html",
    ),
    BlockDefinition(
        block_no=7,
        code="B7_DECODABLE_READER",
        label="Decodable Reader / Fluency",
        body_partial="lesson/partials/bodies/block_body_decodable_reader.html",
    ),
    BlockDefinition(
        block_no=8,
        code="B8_ENCODING_WRITING",
        label="Encoding & Writing",
        body_partial="lesson/partials/bodies/block_body_encoding_writing.html",
    ),
    BlockDefinition(
        block_no=9,
        code="B9_MORPHEME_MOMENT",
        label="Morpheme Moment",
        body_partial="lesson/partials/bodies/block_body_morpheme_moment.html",
    ),
    BlockDefinition(
        block_no=10,
        code="B10_MEANING_CLOSE",
        label="Meaning-Making Close",
        body_partial="lesson/partials/bodies/block_body_meaning_close.html",
    ),
]

BLOCK_REGISTRY_BY_NUMBER = {block.block_no: block for block in BLOCK_REGISTRY}


def get_block_body_partial(block_no: int) -> str:
    block = BLOCK_REGISTRY_BY_NUMBER.get(block_no)

    if block is None:
        raise ValueError(f"Unknown block number: {block_no}")

    return block.body_partial