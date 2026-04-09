from app.services.block_registry import BLOCK_REGISTRY
from app.services.lesson_service import parse_lesson
from app.services.lesson_skeleton_service import generate_skeleton


def test_generated_skeleton_has_all_blocks_with_correct_labels():
    skeleton = generate_skeleton("G11", 72, "Group 11, Lesson 72: oa", "oa")
    assert list(skeleton["blocks"].keys()) == [block.block_id for block in BLOCK_REGISTRY]
    for definition in BLOCK_REGISTRY:
        assert skeleton["blocks"][definition.block_id]["label"] == definition.label


def test_generated_skeleton_passes_parse_lesson():
    skeleton = generate_skeleton("G11", 72, "Group 11, Lesson 72: oa", "oa")
    lesson = parse_lesson(skeleton)
    assert lesson.lesson_id == "G11-L72"


def test_generated_skeleton_has_required_top_level_fields_and_empty_slides():
    skeleton = generate_skeleton("G11", 72, "Group 11, Lesson 72: oa", "oa", ["oa"], ["the"])
    assert skeleton["lesson_id"] == "G11-L72"
    assert skeleton["unit_id"] == "G11"
    assert skeleton["target_pattern"] == "oa"
    assert skeleton["new_units"] == ["oa"]
    assert skeleton["new_sight_words"] == ["the"]
    for block in skeleton["blocks"].values():
        assert block["slides"] == []
