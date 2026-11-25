"""Aturan bentrok bersama untuk generate, papan, dan edit jadwal."""

from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from schemas import BoardConflictItem
from scheduling_common import DAY_NAMES, blocks_overlap


@dataclass(frozen=True)
class ConflictBlock:
    section_id: UUID
    day: int
    start: int
    end: int
    room_id: UUID | None = None
    room_code: str = ""
    lecturer_ids: frozenset[UUID] = frozenset()
    lecturer_names: dict[UUID, str] = field(default_factory=dict)
    section_label: str = ""
    detailed: bool = True

    @property
    def room_identity(self) -> UUID | str | None:
        """UUID bila ada, atau kode ruang yang dinormalisasi."""
        if self.room_id is not None:
            return self.room_id
        if self.room_code:
            return f"name:{self.room_code.strip().casefold()}"
        return None


def build_conflict_item(
    *,
    kind: Literal["lecturer", "room"],
    first: ConflictBlock,
    second: ConflictBlock,
    object_id: UUID | str | None,
    object_name: str,
    day_of_week: int,
    start_hour: int,
    end_hour: int,
) -> BoardConflictItem:
    if not first.detailed:
        return BoardConflictItem(
            class_section_a_id=str(first.section_id),
            class_section_b_id=str(second.section_id),
            kind=kind,
            day_of_week=day_of_week,
            start_hour=start_hour,
            end_hour=end_hour,
        )
    object_type = "Dosen" if kind == "lecturer" else "Ruangan"
    object_label = f"{object_type} {object_name}".strip()
    day_name = DAY_NAMES.get(day_of_week, str(day_of_week))
    label = (
        f"{object_label}: {first.section_label} dan {second.section_label}, "
        f"{day_name} {start_hour:02d}.00-{end_hour:02d}.00"
    )
    return BoardConflictItem(
        class_section_a_id=str(first.section_id),
        class_section_b_id=str(second.section_id),
        kind=kind,
        day_of_week=day_of_week,
        start_hour=start_hour,
        end_hour=end_hour,
        object_id=str(object_id) if object_id is not None else None,
        object_name=object_name,
        object_label=object_label,
        class_section_a_label=first.section_label,
        class_section_b_label=second.section_label,
        day_name=day_name,
        label=label,
    )


def detect_conflicts(blocks: list[ConflictBlock]) -> list[BoardConflictItem]:
    scheduled = [block for block in blocks if block.day and block.end > block.start]
    conflicts: list[BoardConflictItem] = []
    for index, first in enumerate(scheduled):
        for second in scheduled[index + 1 :]:
            if first.section_id == second.section_id:
                continue
            if first.day != second.day or not blocks_overlap(
                first.start, first.end, second.start, second.end
            ):
                continue
            shared = {
                "day_of_week": first.day,
                "start_hour": max(first.start, second.start),
                "end_hour": min(first.end, second.end),
            }
            if (
                first.room_identity is not None
                and first.room_identity == second.room_identity
            ):
                conflicts.append(
                    build_conflict_item(
                        kind="room",
                        first=first,
                        second=second,
                        object_id=first.room_identity,
                        object_name=first.room_code or second.room_code,
                        **shared,
                    )
                )
            shared_lecturers = first.lecturer_ids & second.lecturer_ids
            if shared_lecturers:
                lecturer_id = sorted(shared_lecturers)[0]
                conflicts.append(
                    build_conflict_item(
                        kind="lecturer",
                        first=first,
                        second=second,
                        object_id=lecturer_id,
                        object_name=first.lecturer_names.get(lecturer_id, ""),
                        **shared,
                    )
                )
    conflicts.sort(
        key=lambda item: (
            item.day_of_week,
            item.start_hour,
            item.kind,
            item.class_section_a_id,
            item.class_section_b_id,
        )
    )
    return conflicts
