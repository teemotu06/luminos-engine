from app.services.block_definition import BlockDefinition


BLOCK_REGISTRY = [
    BlockDefinition(
        block_id="01",
        label="Flashcard Phoneme Review",
        allowed_view_types=("flashcard", "audio_prompt", "quick_check"),
    ),
    BlockDefinition(
        block_id="02",
        label="Listening & Write Review",
        allowed_view_types=("audio_prompt", "writing_encoding", "quick_check"),
    ),
    BlockDefinition(
        block_id="03",
        label="New Sound Introduction",
        allowed_view_types=("flashcard", "audio_prompt", "minimal_pair", "read_respond"),
    ),
    BlockDefinition(
        block_id="04",
        label="Vocabulary Warm-Up",
        allowed_view_types=("flashcard", "audio_prompt", "minimal_pair", "read_respond"),
    ),
    BlockDefinition(
        block_id="05",
        label="Word Building",
        allowed_view_types=("drag_letter", "flashcard", "read_respond", "writing_encoding"),
    ),
    BlockDefinition(
        block_id="06",
        label="Sentence Bridge",
        allowed_view_types=("read_respond", "drag_word", "audio_prompt"),
    ),
    BlockDefinition(
        block_id="07",
        label="Decodable Reader / Fluency",
        allowed_view_types=("read_respond", "audio_prompt", "quick_check"),
    ),
    BlockDefinition(
        block_id="08",
        label="Encoding & Writing",
        allowed_view_types=("writing_encoding", "audio_prompt", "quick_check"),
    ),
    BlockDefinition(
        block_id="09",
        label="Morpheme Moment",
        allowed_view_types=("flashcard", "drag_word", "read_respond"),
    ),
    BlockDefinition(
        block_id="10",
        label="Meaning-Making Close",
        allowed_view_types=("read_respond", "quick_check"),
    ),
]
