"""Period-scoped lecturer preference rules and persistence."""

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from academics import period_payload
from models import (
    AcademicPeriod,
    ClassInstructorAssignment,
    ClassSchedule,
    ClassSection,
    Course,
    CourseOffering,
    LecturerProfile,
    LecturerSchedulePreference,
    OfferingComponent,
    SchedulePeriodSettings,
    StudyProgram,
    User,
)
from scheduling_common import DAY_NAMES, current_period_id
from ..scheduler import bump_input_revisions, scheduling_input_lock
from .errors import ServiceError

_UNPROCESSABLE = 422


@dataclass(frozen=True)
class PreferenceSlot:
    day_of_week: int
    start_time: time
    end_time: time
    kind: Literal["preferred", "unavailable"]


def _deny(
    status_code: int,
    code: str,
    message: str,
    *,
    details: list[dict[str, Any]] | None = None,
) -> ServiceError:
    return ServiceError(status_code, code, message, details=details or [])


async def _period_deadlines(
    db: AsyncSession, period_id: UUID
) -> tuple[datetime | None, dict[UUID, datetime]]:
    rows = list(
        (
            await db.execute(
                select(SchedulePeriodSettings).where(
                    SchedulePeriodSettings.academic_period_id == period_id
                )
            )
        )
        .scalars()
        .all()
    )
    global_deadline = None
    program_deadlines: dict[UUID, datetime] = {}
    for row in rows:
        if row.study_program_id is None:
            global_deadline = row.preference_deadline
        elif row.preference_deadline is not None:
            program_deadlines[row.study_program_id] = row.preference_deadline
    return global_deadline, program_deadlines


async def _effective_deadline(
    db: AsyncSession, period_id: UUID, study_program_id: UUID | None
) -> datetime | None:
    global_deadline, program_deadlines = await _period_deadlines(db, period_id)
    if study_program_id is None:
        return global_deadline
    return program_deadlines.get(study_program_id, global_deadline)


def _preference_response(
    period_id: UUID,
    user_id: UUID,
    slots: list[PreferenceSlot],
    *,
    warnings: list[dict[str, Any]] | None = None,
    deadline: datetime | None = None,
) -> dict[str, Any]:
    ordered = sorted(
        slots, key=lambda slot: (slot.day_of_week, slot.start_time, slot.kind)
    )
    preferred_count = sum(slot.kind == "preferred" for slot in ordered)
    unavailable_count = sum(slot.kind == "unavailable" for slot in ordered)
    filled = bool(ordered)
    return {
        "academic_period_id": str(period_id),
        "user_id": str(user_id),
        "data": [
            {
                "day_of_week": slot.day_of_week,
                "day_name": DAY_NAMES[slot.day_of_week],
                "start_time": slot.start_time,
                "end_time": slot.end_time,
                "kind": slot.kind,
            }
            for slot in ordered
        ],
        "meta": {
            "count": len(ordered),
            "status": "filled" if filled else "empty",
            "preferred_count": preferred_count,
            "unavailable_count": unavailable_count,
            "completeness": {
                "filled": filled,
                "preferred_count": preferred_count,
                "unavailable_count": unavailable_count,
            },
            "deadline": deadline,
            "warnings": warnings or [],
        },
    }


def _slots_from_rows(
    rows: list[LecturerSchedulePreference],
) -> list[PreferenceSlot]:
    return [
        PreferenceSlot(
            day_of_week=row.day_of_week,
            start_time=row.start_time,
            end_time=row.end_time,
            kind=row.kind,
        )
        for row in rows
    ]


def _overlapping_slots(slots: list[PreferenceSlot]) -> list[dict[str, Any]]:
    ordered = sorted(slots, key=lambda slot: (slot.day_of_week, slot.start_time))
    for index, slot in enumerate(ordered):
        for other in ordered[index + 1 :]:
            if other.day_of_week != slot.day_of_week:
                break
            if slot.start_time < other.end_time and other.start_time < slot.end_time:
                return [
                    {
                        "day_of_week": slot.day_of_week,
                        "first_start_time": slot.start_time.isoformat(),
                        "first_end_time": slot.end_time.isoformat(),
                        "second_start_time": other.start_time.isoformat(),
                        "second_end_time": other.end_time.isoformat(),
                    }
                ]
    return []


def _slot_key(slot: PreferenceSlot) -> tuple[int, time, time, str]:
    return (slot.day_of_week, slot.start_time, slot.end_time, slot.kind)


async def _assignment_warnings(
    db: AsyncSession,
    user_id: UUID,
    period_id: UUID,
    slots: list[PreferenceSlot],
) -> list[dict[str, Any]]:
    unavailable = sorted(
        (slot for slot in slots if slot.kind == "unavailable"),
        key=lambda slot: (slot.day_of_week, slot.start_time, slot.end_time),
    )
    if not unavailable:
        return []
    rows = (
        await db.execute(
            select(
                ClassSchedule,
                ClassSection.section_code,
                Course.course_code,
                Course.course_name,
            )
            .select_from(ClassInstructorAssignment)
            .join(
                ClassSchedule,
                ClassSchedule.class_section_id
                == ClassInstructorAssignment.class_section_id,
            )
            .join(
                ClassSection,
                ClassSection.class_section_id == ClassSchedule.class_section_id,
            )
            .join(
                OfferingComponent,
                OfferingComponent.offering_component_id
                == ClassSection.offering_component_id,
            )
            .join(
                CourseOffering,
                CourseOffering.course_offering_id
                == OfferingComponent.course_offering_id,
            )
            .join(Course, Course.course_id == CourseOffering.course_id)
            .where(
                ClassInstructorAssignment.user_id == user_id,
                ClassInstructorAssignment.academic_period_id == period_id,
                ClassInstructorAssignment.is_active.is_(True),
                CourseOffering.academic_period_id == period_id,
            )
            .order_by(
                ClassSchedule.day_of_week,
                ClassSchedule.start_time,
                ClassSchedule.class_schedule_id,
            )
        )
    ).all()
    warnings: list[dict[str, Any]] = []
    for slot in unavailable:
        for schedule, section_code, course_code, course_name in rows:
            if schedule.day_of_week != slot.day_of_week:
                continue
            if not (
                slot.start_time < schedule.end_time
                and schedule.start_time < slot.end_time
            ):
                continue
            warnings.append(
                {
                    "code": "assigned_class_overlap",
                    "message": (
                        f"Blok tidak tersedia bertabrakan dengan {course_code} "
                        f"kelas {section_code}."
                    ),
                    "class_section_id": str(schedule.class_section_id),
                    "course_code": course_code,
                    "course_name": course_name,
                    "section_code": section_code,
                    "day_of_week": slot.day_of_week,
                    "day_name": DAY_NAMES[slot.day_of_week],
                    "unavailable_start_time": slot.start_time,
                    "unavailable_end_time": slot.end_time,
                    "class_start_time": schedule.start_time,
                    "class_end_time": schedule.end_time,
                    "overlap_start_time": max(slot.start_time, schedule.start_time),
                    "overlap_end_time": min(slot.end_time, schedule.end_time),
                }
            )
    return warnings


async def _load_slots(
    db: AsyncSession, period_id: UUID, user_id: UUID
) -> list[PreferenceSlot]:
    rows = list(
        (
            await db.execute(
                select(LecturerSchedulePreference)
                .where(
                    LecturerSchedulePreference.user_id == user_id,
                    LecturerSchedulePreference.academic_period_id == period_id,
                )
                .order_by(
                    LecturerSchedulePreference.day_of_week,
                    LecturerSchedulePreference.start_time,
                    LecturerSchedulePreference.kind,
                )
            )
        )
        .scalars()
        .all()
    )
    return _slots_from_rows(rows)


async def list_periods(db: AsyncSession) -> dict[str, Any]:
    current_id = await current_period_id(db)
    periods = list((await db.execute(select(AcademicPeriod))).scalars().all())
    term_order = {"ganjil": 0, "genap": 1, "pendek": 2}
    periods.sort(
        key=lambda period: (
            period.academic_year_start,
            term_order.get(period.term, 3),
            str(period.academic_period_id),
        )
    )
    today = date.today()
    return {
        "data": [
            {
                "academic_period_id": str(period.academic_period_id),
                "academic_year_start": period.academic_year_start,
                "semester_number": period.semester_number,
                "term": period.term,
                "label": (
                    f"{period.academic_year_start}/{period.academic_year_start + 1} "
                    f"{(period.term or '').title()}"
                ),
                "start_date": period.start_date,
                "end_date": period.end_date,
                "is_active": period.is_active,
                "is_current": period.academic_period_id == current_id,
            }
            for period in periods
        ],
        "meta": {
            "total": len(periods),
            "current_academic_period_id": (
                str(current_id) if current_id is not None else None
            ),
        },
    }


async def preference_summary(
    db: AsyncSession, period_id: UUID, scope: UUID | None
) -> dict[str, Any]:
    lecturer_query = (
        select(
            User.user_id,
            User.full_name,
            LecturerProfile.study_program_id,
            StudyProgram.program_code,
            StudyProgram.program_name,
        )
        .join(LecturerProfile, LecturerProfile.user_id == User.user_id)
        .join(
            StudyProgram,
            StudyProgram.study_program_id == LecturerProfile.study_program_id,
        )
        .where(User.role == "lecturer", User.is_active.is_(True))
        .order_by(
            StudyProgram.program_code,
            User.full_name,
            User.user_id,
        )
    )
    if scope is not None:
        lecturer_query = lecturer_query.where(LecturerProfile.study_program_id == scope)
    lecturers = (await db.execute(lecturer_query)).all()
    counts: dict[UUID, list[int]] = {row.user_id: [0, 0] for row in lecturers}
    if counts:
        preference_rows = (
            await db.execute(
                select(
                    LecturerSchedulePreference.user_id,
                    LecturerSchedulePreference.kind,
                ).where(
                    LecturerSchedulePreference.academic_period_id == period_id,
                    LecturerSchedulePreference.user_id.in_(counts),
                )
            )
        ).all()
        for user_id, kind in preference_rows:
            counts[user_id][0 if kind == "preferred" else 1] += 1

    global_deadline, program_deadlines = await _period_deadlines(db, period_id)
    items = []
    filled_count = 0
    for row in lecturers:
        preferred_count, unavailable_count = counts[row.user_id]
        filled = bool(preferred_count or unavailable_count)
        filled_count += int(filled)
        items.append(
            {
                "user_id": str(row.user_id),
                "full_name": row.full_name,
                "study_program_id": str(row.study_program_id),
                "study_program_code": row.program_code,
                "study_program_name": row.program_name,
                "status": "filled" if filled else "empty",
                "preferred_count": preferred_count,
                "unavailable_count": unavailable_count,
                "deadline": program_deadlines.get(
                    row.study_program_id, global_deadline
                ),
            }
        )
    return {
        "data": items,
        "meta": {
            "total": len(items),
            "filled": filled_count,
            "empty": len(items) - filled_count,
        },
    }


async def get_preferences(
    db: AsyncSession,
    period_id: UUID,
    user_id: UUID,
    study_program_id: UUID | None,
) -> dict[str, Any]:
    slots = await _load_slots(db, period_id, user_id)
    return _preference_response(
        period_id,
        user_id,
        slots,
        warnings=await _assignment_warnings(db, user_id, period_id, slots),
        deadline=await _effective_deadline(db, period_id, study_program_id),
    )


async def replace_preferences(
    db: AsyncSession,
    period_id: UUID,
    user_id: UUID,
    study_program_id: UUID | None,
    slots: list[PreferenceSlot],
) -> dict[str, Any] | ServiceError:
    program_ids = {study_program_id}
    locked = await scheduling_input_lock(db, period_id, program_ids)
    if locked is not None:
        code, message = locked
        return _deny(409, code, message)

    overlap = _overlapping_slots(slots)
    if overlap:
        return _deny(
            _UNPROCESSABLE,
            "overlapping_preference",
            "Preferensi dan blok tidak tersedia tidak boleh bertabrakan.",
            details=overlap,
        )

    previous_rows = (
        (
            await db.execute(
                select(LecturerSchedulePreference).where(
                    LecturerSchedulePreference.user_id == user_id,
                    LecturerSchedulePreference.academic_period_id == period_id,
                )
            )
        )
        .scalars()
        .all()
    )
    previous_slots = _slots_from_rows(previous_rows)
    changed = sorted(previous_slots, key=_slot_key) != sorted(slots, key=_slot_key)
    await db.execute(
        select(User.user_id).where(User.user_id == user_id).with_for_update()
    )
    await db.execute(
        delete(LecturerSchedulePreference).where(
            LecturerSchedulePreference.user_id == user_id,
            LecturerSchedulePreference.academic_period_id == period_id,
        )
    )
    db.add_all(
        [
            LecturerSchedulePreference(
                user_id=user_id,
                academic_period_id=period_id,
                day_of_week=slot.day_of_week,
                start_time=slot.start_time,
                end_time=slot.end_time,
                kind=slot.kind,
            )
            for slot in slots
        ]
    )
    if changed:
        await bump_input_revisions(db, period_id, program_ids)
    try:
        warnings = await _assignment_warnings(db, user_id, period_id, slots)
        deadline = await _effective_deadline(db, period_id, study_program_id)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return _deny(
            _UNPROCESSABLE,
            "overlapping_preference",
            "Preferensi dan blok tidak tersedia tidak boleh bertabrakan.",
        )
    return _preference_response(
        period_id, user_id, slots, warnings=warnings, deadline=deadline
    )


async def copy_preferences(
    db: AsyncSession,
    source_period_id: UUID,
    target_period_id: UUID,
    user_id: UUID,
    study_program_id: UUID | None,
    overwrite: bool,
) -> dict[str, Any] | ServiceError:
    locked = await scheduling_input_lock(db, target_period_id, {study_program_id})
    if locked is not None:
        code, message = locked
        return _deny(409, code, message)

    await db.execute(
        select(User.user_id).where(User.user_id == user_id).with_for_update()
    )
    source_slots = await _load_slots(db, source_period_id, user_id)
    target_slots = await _load_slots(db, target_period_id, user_id)
    source_overlap = _overlapping_slots(source_slots)
    if source_overlap:
        return _deny(
            _UNPROCESSABLE,
            "overlapping_preference",
            "Preferensi dan blok tidak tersedia pada periode sumber bertabrakan.",
            details=source_overlap,
        )
    if sorted(source_slots, key=_slot_key) == sorted(target_slots, key=_slot_key):
        return _preference_response(
            target_period_id,
            user_id,
            target_slots,
            warnings=await _assignment_warnings(
                db, user_id, target_period_id, target_slots
            ),
            deadline=await _effective_deadline(db, target_period_id, study_program_id),
        )
    if target_slots and not overwrite:
        return _deny(
            409,
            "preferences_exist",
            "Preferensi periode tujuan sudah terisi. Gunakan overwrite untuk menimpanya.",
            details=[
                {
                    "field": "academic_period_id",
                    "academic_period_id": str(target_period_id),
                    "existing_count": len(target_slots),
                }
            ],
        )

    await db.execute(
        delete(LecturerSchedulePreference).where(
            LecturerSchedulePreference.user_id == user_id,
            LecturerSchedulePreference.academic_period_id == target_period_id,
        )
    )
    db.add_all(
        [
            LecturerSchedulePreference(
                user_id=user_id,
                academic_period_id=target_period_id,
                day_of_week=slot.day_of_week,
                start_time=slot.start_time,
                end_time=slot.end_time,
                kind=slot.kind,
            )
            for slot in source_slots
        ]
    )
    await bump_input_revisions(db, target_period_id, {study_program_id})
    try:
        warnings = await _assignment_warnings(
            db, user_id, target_period_id, source_slots
        )
        deadline = await _effective_deadline(db, target_period_id, study_program_id)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return _deny(
            _UNPROCESSABLE,
            "overlapping_preference",
            "Preferensi dan blok tidak tersedia pada periode sumber bertabrakan.",
        )
    return _preference_response(
        target_period_id,
        user_id,
        source_slots,
        warnings=warnings,
        deadline=deadline,
    )
