from __future__ import annotations

import json
import re
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import List, Optional

from app.schemas.group import GroupCreateRequest, GroupMeta, GroupUpdateRequest

GROUPS_FILE = Path("app/content/groups.json")
UNIT_ID_RE = re.compile(r"^G(?P<number>\d+)$")


def _write_groups(groups: List[GroupMeta]) -> None:
    GROUPS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=str(GROUPS_FILE.parent), delete=False) as handle:
        json.dump([group.model_dump() for group in groups], handle, indent=2)
        handle.write("\n")
        temp_path = Path(handle.name)
    temp_path.replace(GROUPS_FILE)


def load_groups() -> List[GroupMeta]:
    if not GROUPS_FILE.exists():
        return []
    data = json.loads(GROUPS_FILE.read_text(encoding="utf-8"))
    groups = [GroupMeta(**item) for item in data]
    return sorted(groups, key=lambda group: (group.sort_order, group.group_number, group.unit_id))


def get_group(unit_id: str) -> Optional[GroupMeta]:
    for group in load_groups():
        if group.unit_id == unit_id:
            return group
    return None


def create_group(request: GroupCreateRequest) -> GroupMeta:
    groups = load_groups()
    if any(group.unit_id == request.unit_id for group in groups):
        raise ValueError("Group unit_id already exists.")

    match = UNIT_ID_RE.match(request.unit_id)
    if not match:
        raise ValueError("unit_id must follow the pattern G{number}.")

    next_number = (max((group.group_number for group in groups), default=0) + 1)
    requested_number = int(match.group("number"))
    if requested_number != next_number:
        raise ValueError("New group unit_id must use the next sequential group number.")

    group = GroupMeta(
        unit_id=request.unit_id,
        group_number=next_number,
        title=request.title.strip(),
        description=(request.description or "").strip(),
        target_phonemes=[item.strip() for item in request.target_phonemes if item.strip()],
        sort_order=(max((group.sort_order for group in groups), default=0) + 1),
    )
    groups.append(group)
    _write_groups(groups)
    return group


def update_group(unit_id: str, request: GroupUpdateRequest) -> GroupMeta:
    groups = load_groups()
    updated = None
    new_groups = []
    for group in groups:
        if group.unit_id == unit_id:
            updated = GroupMeta(
                unit_id=group.unit_id,
                group_number=group.group_number,
                title=request.title.strip(),
                description=(request.description or "").strip(),
                target_phonemes=[item.strip() for item in request.target_phonemes if item.strip()],
                sort_order=group.sort_order,
            )
            new_groups.append(updated)
        else:
            new_groups.append(group)
    if updated is None:
        raise ValueError("Group not found.")
    _write_groups(new_groups)
    return updated


def reorder_groups(unit_ids: List[str]) -> List[GroupMeta]:
    groups = load_groups()
    group_map = {group.unit_id: group for group in groups}
    ordered_ids = []
    for unit_id in unit_ids:
        if unit_id in group_map and unit_id not in ordered_ids:
            ordered_ids.append(unit_id)
    for group in groups:
        if group.unit_id not in ordered_ids:
            ordered_ids.append(group.unit_id)

    reordered = []
    for index, unit_id in enumerate(ordered_ids, start=1):
        group = group_map[unit_id]
        reordered.append(
            GroupMeta(
                unit_id=group.unit_id,
                group_number=group.group_number,
                title=group.title,
                description=group.description,
                target_phonemes=list(group.target_phonemes),
                sort_order=index,
            )
        )

    _write_groups(reordered)
    return reordered


def get_group_lesson_counts(lessons: list) -> dict[str, int]:
    counts = {}
    for lesson in lessons:
        unit_id = getattr(lesson, "unit_id", None) if not isinstance(lesson, dict) else lesson.get("unit_id")
        if not unit_id:
            continue
        counts[unit_id] = counts.get(unit_id, 0) + 1
    return counts
