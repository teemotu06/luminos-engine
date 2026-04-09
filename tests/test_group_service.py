from pathlib import Path
from unittest.mock import patch

from app.schemas.group import GroupCreateRequest, GroupUpdateRequest
from app.services import group_service


def test_load_groups_from_seeded_json(tmp_path):
    groups_file = tmp_path / "groups.json"
    groups_file.write_text(Path("app/content/groups.json").read_text(encoding="utf-8"), encoding="utf-8")
    with patch("app.services.group_service.GROUPS_FILE", groups_file):
        groups = group_service.load_groups()
    assert groups
    assert groups[0].unit_id == "G1"


def test_create_group_with_valid_unit_id(tmp_path):
    groups_file = tmp_path / "groups.json"
    groups_file.write_text(Path("app/content/groups.json").read_text(encoding="utf-8"), encoding="utf-8")
    with patch("app.services.group_service.GROUPS_FILE", groups_file):
        created = group_service.create_group(
            GroupCreateRequest(unit_id="G11", title="New Group", description="", target_phonemes=["oa"])
        )
        assert created.group_number == 11
        assert created.sort_order == 11


def test_reject_duplicate_group_unit_id(tmp_path):
    groups_file = tmp_path / "groups.json"
    groups_file.write_text(Path("app/content/groups.json").read_text(encoding="utf-8"), encoding="utf-8")
    with patch("app.services.group_service.GROUPS_FILE", groups_file):
        try:
            group_service.create_group(GroupCreateRequest(unit_id="G1", title="Dup", description="", target_phonemes=[]))
            assert False, "Expected duplicate unit_id error"
        except ValueError as exc:
            assert "already exists" in str(exc)


def test_update_group_metadata(tmp_path):
    groups_file = tmp_path / "groups.json"
    groups_file.write_text(Path("app/content/groups.json").read_text(encoding="utf-8"), encoding="utf-8")
    with patch("app.services.group_service.GROUPS_FILE", groups_file):
        updated = group_service.update_group(
            "G1",
            GroupUpdateRequest(title="Updated", description="Desc", target_phonemes=["sh", "th"]),
        )
        assert updated.title == "Updated"
        assert updated.target_phonemes == ["sh", "th"]


def test_reorder_groups_updates_sort_order(tmp_path):
    groups_file = tmp_path / "groups.json"
    groups_file.write_text(Path("app/content/groups.json").read_text(encoding="utf-8"), encoding="utf-8")
    with patch("app.services.group_service.GROUPS_FILE", groups_file):
        reordered = group_service.reorder_groups(["G2", "G1"])
        assert reordered[0].unit_id == "G2"
        assert reordered[0].sort_order == 1
        assert reordered[1].unit_id == "G1"
        assert reordered[1].sort_order == 2
