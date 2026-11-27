"""Hapus kelas MK universitas di luar wewenang penjadwalan FTMM."""

import asyncio
import sys

from sqlalchemy import delete, exists, func, select, update
from sqlalchemy.exc import SQLAlchemyError

from database import AsyncSessionLocal
from models import (
    ClassCountOverride,
    ClassSchedule,
    ClassSection,
    CourseOffering,
    OfferingComponent,
    Timetable,
    TimetableItem,
)
from scheduling_common import UNIVERSITY_SCOPE, university_course_ids


def section_ids():
    return (
        select(ClassSection.class_section_id)
        .join(
            OfferingComponent,
            ClassSection.offering_component_id == OfferingComponent.offering_component_id,
        )
        .join(
            CourseOffering,
            OfferingComponent.course_offering_id == CourseOffering.course_offering_id,
        )
        .where(CourseOffering.course_id.in_(university_course_ids()))
    )


async def timetable_impact(session) -> tuple[list, int]:
    ids = section_ids()
    rows = await session.execute(
        select(TimetableItem.timetable_id)
        .distinct()
        .where(TimetableItem.class_section_id.in_(ids))
    )
    timetable_ids = [row[0] for row in rows]
    if not timetable_ids:
        return [], 0
    remaining = await session.execute(
        select(TimetableItem.timetable_id)
        .distinct()
        .where(TimetableItem.timetable_id.in_(timetable_ids))
        .where(TimetableItem.class_section_id.not_in(ids))
    )
    return timetable_ids, len(timetable_ids) - len(remaining.all())


async def count(session, statement) -> int:
    result = await session.execute(select(func.count()).select_from(statement.subquery()))
    return result.scalar_one()


async def snapshot(session) -> dict[str, int]:
    ids = section_ids()
    timetable_ids, left_empty = await timetable_impact(session)
    return {
        "sections": await count(session, ids),
        "schedules": await count(
            session,
            select(ClassSchedule.class_schedule_id).where(
                ClassSchedule.class_section_id.in_(ids)
            ),
        ),
        "timetable_items": await count(
            session,
            select(TimetableItem.timetable_item_id).where(
                TimetableItem.class_section_id.in_(ids)
            ),
        ),
        "class_count_overrides": await count(
            session,
            select(ClassCountOverride.id).where(
                ClassCountOverride.course_id.in_(university_course_ids())
            ),
        ),
        "timetables_deactivated": len(timetable_ids),
        "timetables_left_empty": left_empty,
    }


def print_counts(tag: str, label: str, counts: dict[str, int]) -> None:
    detail = " ".join(f"{name}={value}" for name, value in counts.items())
    print(f"{tag} {label}: {detail}")


async def purge(apply: bool) -> None:
    tag = "[CLEANUP]" if apply else "[DRY-RUN]"
    async with AsyncSessionLocal() as session:
        print(f"{tag} course_scope={UNIVERSITY_SCOPE}")
        print_counts(tag, "before", await snapshot(session))

        if apply:
            ids = section_ids()
            timetable_ids, _ = await timetable_impact(session)
            active_ids = (
                (
                    await session.execute(
                        select(Timetable.timetable_id).where(
                            Timetable.timetable_id.in_(timetable_ids),
                            Timetable.is_active.is_(True),
                        )
                    )
                ).scalars().all()
                if timetable_ids
                else []
            )
            deleted = {}
            if timetable_ids:
                await session.execute(
                    update(Timetable)
                    .where(Timetable.timetable_id.in_(timetable_ids))
                    .values(is_active=False)
                )

            for name, statement in (
                (
                    "timetable_items",
                    delete(TimetableItem).where(TimetableItem.class_section_id.in_(ids)),
                ),
                (
                    "schedules",
                    delete(ClassSchedule).where(ClassSchedule.class_section_id.in_(ids)),
                ),
                (
                    "sections",
                    delete(ClassSection).where(ClassSection.class_section_id.in_(ids)),
                ),
                (
                    "class_count_overrides",
                    delete(ClassCountOverride).where(
                        ClassCountOverride.course_id.in_(university_course_ids())
                    ),
                ),
            ):
                deleted[name] = (await session.execute(statement)).rowcount
            if active_ids:
                await session.execute(
                    update(Timetable)
                    .where(Timetable.timetable_id.in_(active_ids))
                    .where(
                        exists(
                            select(1).where(
                                TimetableItem.timetable_id == Timetable.timetable_id
                            )
                        )
                    )
                    .values(is_active=True)
                )

            await session.commit()
            print_counts(tag, "deleted", deleted)

        print_counts(tag, "after", await snapshot(session))

    state = "complete" if apply else "complete, no writes"
    print(f"[DONE] {state}")


def main() -> int:
    apply = "--apply" in sys.argv[1:]
    try:
        asyncio.run(purge(apply))
    except SQLAlchemyError as exc:
        print(f"[DONE] database error ({type(exc).__name__}): {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
