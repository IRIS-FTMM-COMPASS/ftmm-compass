"""Edit manual, finalisasi, pembukaan kunci, dan catatan perubahan jadwal."""

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, time as time_value, timezone
from typing import Any
from uuid import UUID

from fastapi import status
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    AcademicPeriod,
    ClassInstructorAssignment,
    ClassSchedule,
    ClassSection,
    Course,
    CourseOffering,
    CourseOfferingEligibility,
    Curriculum,
    CurriculumCourse,
    LecturerSchedulePreference,
    OfferingComponent,
    Room,
    ScheduleEditLog,
    SchedulePeriodLock,
    SchedulePeriodSettings,
    ScheduleProgramStatus,
    StudyProgram,
    User,
)
from schemas import (
    BoardClassItem,
    BoardConflictItem,
    ClassMoveRequest,
    ClassMoveResponse,
    EditLogEntry,
    FinalizeClassCompleteness,
    FinalizeCompleteness,
    FinalizePreferenceCompleteness,
    FinalizeResponse,
    FinalizeWarning,
    UnlockRequest,
)
from scheduling_common import all_study_program_ids, hour_end, is_valid_block

from ..conflicts import ConflictBlock, detect_conflicts
from ..scheduler import current_input_revision, latest_completed_run
from . import UNPROCESSABLE
from .errors import ServiceError


@dataclass
class _Block:
    section_id: UUID
    section_code: str
    course_code: str
    course_name: str
    credits: int
    schedule_id: UUID | None
    program_id: UUID | None
    program_code: str
    program_ids: set[UUID] = field(default_factory=set)
    day: int = 0
    start: int = 0
    end: int = 0
    room_id: UUID | None = None
    room_label: str = ""
    curriculum_course_ids: set[UUID] = field(default_factory=set)
    lecturer_keys: set[str] = field(default_factory=set)
    lecturer_names: list[str] = field(default_factory=list)

    @property
    def room_key(self) -> str:
        if self.room_id is not None:
            return f"id:{self.room_id}"
        if self.room_label:
            return f"name:{self.room_label.strip().casefold()}"
        return ""


def _failure(
    status_code: int, code: str, message: str, details: Any = ()
) -> ServiceError:
    return ServiceError(status_code, code, message, details)


def field_failure(field_name: str, message: str, code: str) -> ServiceError:
    return ServiceError(
        UNPROCESSABLE,
        "validation_error",
        message,
        [{"field": field_name, "message": message, "code": code}],
    )


def _hour(value: time_value | None, *, ceiling: bool = False) -> int:
    if value is None:
        return 0
    minutes = value.hour * 60 + value.minute
    return math.ceil(minutes / 60) if ceiling else minutes // 60


async def _section_period(
    db: AsyncSession, section_id: UUID
) -> tuple[ClassSection, AcademicPeriod] | None:
    row = (
        await db.execute(
            select(ClassSection, AcademicPeriod)
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
            .join(
                AcademicPeriod,
                AcademicPeriod.academic_period_id
                == CourseOffering.academic_period_id,
            )
            .where(ClassSection.class_section_id == section_id)
        )
    ).first()
    if row is None:
        return None
    return row.ClassSection, row.AcademicPeriod


async def _load_blocks(db: AsyncSession, period_id: UUID) -> list[_Block]:
    rows = (
        await db.execute(
            select(
                ClassSection.class_section_id.label("section_id"),
                ClassSection.section_code.label("section_code"),
                Course.course_code.label("course_code"),
                Course.course_name.label("course_name"),
                CurriculumCourse.credits_total.label("credits"),
                StudyProgram.study_program_id.label("program_id"),
                StudyProgram.program_code.label("program_code"),
                ClassSchedule.class_schedule_id.label("schedule_id"),
                ClassSchedule.day_of_week.label("day"),
                ClassSchedule.start_time.label("start_time"),
                ClassSchedule.end_time.label("end_time"),
                ClassSchedule.room_id.label("room_id"),
                ClassSchedule.room_name.label("room_name"),
                Room.room_code.label("room_code"),
                CurriculumCourse.curriculum_course_id.label("curriculum_course_id"),
                ClassInstructorAssignment.user_id.label("assigned_user_id"),
                User.full_name.label("assigned_name"),
            )
            .join(
                OfferingComponent,
                ClassSection.offering_component_id
                == OfferingComponent.offering_component_id,
            )
            .join(
                CourseOffering,
                CourseOffering.course_offering_id
                == OfferingComponent.course_offering_id,
            )
            .join(Course, CourseOffering.course_id == Course.course_id)
            .outerjoin(
                CourseOfferingEligibility,
                CourseOfferingEligibility.course_offering_id
                == CourseOffering.course_offering_id,
            )
            .outerjoin(
                CurriculumCourse,
                CurriculumCourse.curriculum_course_id
                == CourseOfferingEligibility.curriculum_course_id,
            )
            .outerjoin(
                Curriculum,
                Curriculum.curriculum_id == CurriculumCourse.curriculum_id,
            )
            .outerjoin(
                StudyProgram,
                StudyProgram.study_program_id == Curriculum.study_program_id,
            )
            .outerjoin(
                ClassSchedule,
                ClassSchedule.class_section_id == ClassSection.class_section_id,
            )
            .outerjoin(Room, Room.room_id == ClassSchedule.room_id)
            .outerjoin(
                ClassInstructorAssignment,
                and_(
                    ClassInstructorAssignment.class_section_id
                    == ClassSection.class_section_id,
                    ClassInstructorAssignment.academic_period_id == period_id,
                    ClassInstructorAssignment.is_active.is_(True),
                ),
            )
            .outerjoin(
                User,
                and_(
                    User.user_id == ClassInstructorAssignment.user_id,
                    User.is_active.is_(True),
                    User.role == "lecturer",
                ),
            )
            .where(CourseOffering.academic_period_id == period_id)
            .order_by(
                StudyProgram.program_code,
                Course.course_code,
                ClassSection.section_code,
                ClassSchedule.day_of_week,
                ClassSchedule.start_time,
            )
        )
    ).all()

    blocks: dict[tuple[UUID, UUID | None], _Block] = {}
    for row in rows:
        key = (row.section_id, row.schedule_id)
        block = blocks.get(key)
        if block is None:
            block = _Block(
                section_id=row.section_id,
                section_code=row.section_code,
                course_code=row.course_code,
                course_name=row.course_name,
                credits=row.credits or 0,
                schedule_id=row.schedule_id,
                program_id=row.program_id,
                program_code=row.program_code or "",
                day=row.day or 0,
                start=_hour(row.start_time),
                end=_hour(row.end_time, ceiling=True),
                room_id=row.room_id,
                room_label=row.room_code or row.room_name or "",
                lecturer_keys=(
                    {str(row.assigned_user_id)}
                    if row.assigned_user_id is not None and row.assigned_name
                    else set()
                ),
                lecturer_names=(
                    [row.assigned_name]
                    if row.assigned_user_id is not None and row.assigned_name
                    else []
                ),
            )
            blocks[key] = block
        if row.program_id is not None:
            block.program_ids.add(row.program_id)
        if row.curriculum_course_id is not None:
            block.curriculum_course_ids.add(row.curriculum_course_id)

    return list(blocks.values())


def _conflicts(blocks: list[_Block]) -> list[BoardConflictItem]:
    return detect_conflicts(
        [
            ConflictBlock(
                section_id=block.section_id,
                day=block.day,
                start=block.start,
                end=block.end,
                room_id=block.room_id,
                room_code=block.room_label,
                lecturer_ids=frozenset(UUID(key) for key in block.lecturer_keys),
                detailed=False,
            )
            for block in blocks
        ]
    )


def _class_item(block: _Block, state: str) -> BoardClassItem:
    return BoardClassItem(
        class_section_id=str(block.section_id),
        section_code=block.section_code,
        course_code=block.course_code,
        course_name=block.course_name,
        credits=block.credits,
        face_to_face_minutes=block.credits * 50,
        study_program_id=str(block.program_id) if block.program_id else "",
        study_program_code=block.program_code,
        program_ids=[str(program_id) for program_id in sorted(block.program_ids, key=str)],
        day_of_week=block.day,
        start_hour=block.start,
        end_hour=block.end,
        room_id=str(block.room_id) if block.room_id else None,
        room_code=block.room_label or None,
        lecturers=block.lecturer_names,
        assigned_lecturer_id=(
            next(iter(block.lecturer_keys)) if block.lecturer_keys else None
        ),
        assigned_lecturer_name=(
            block.lecturer_names[0] if block.lecturer_names else None
        ),
        can_edit=True,
        read_only=False,
        is_manually_edited=True,
        state=state,
    )


def _snapshot(block: _Block) -> dict[str, object]:
    return {
        "day_of_week": block.day,
        "start_hour": block.start,
        "end_hour": block.end,
        "room_id": str(block.room_id) if block.room_id else None,
        "room_code": block.room_label or None,
    }


async def _program_states(
    db: AsyncSession, period_id: UUID
) -> dict[UUID, ScheduleProgramStatus]:
    rows = (
        await db.execute(
            select(ScheduleProgramStatus).where(
                ScheduleProgramStatus.academic_period_id == period_id
            )
        )
    ).scalars().all()
    return {row.study_program_id: row for row in rows}


def _has_valid_schedule(block: _Block) -> bool:
    return (
        block.day > 0
        and block.end > block.start
        and bool(block.room_key)
        and bool(block.lecturer_keys)
    )


def _unassigned_details(
    blocks: list[_Block], study_program_id: UUID
) -> list[dict[str, object]]:
    grouped: dict[UUID, list[_Block]] = defaultdict(list)
    for block in blocks:
        if study_program_id in block.program_ids:
            grouped.setdefault(block.section_id, []).append(block)
    details: list[dict[str, object]] = []
    for section_id, rows in grouped.items():
        if any(_has_valid_schedule(block) for block in rows):
            continue
        reasons: list[str] = []
        if not any(block.day and block.end > block.start for block in rows):
            reasons.append("missing_schedule")
        if not any(block.room_key for block in rows):
            reasons.append("missing_room")
        if not any(block.lecturer_keys for block in rows):
            reasons.append("missing_assignment")
        details.append(
            {
                "class_section_id": str(section_id),
                "course_code": rows[0].course_code,
                "reasons": reasons,
            }
        )
    return details


async def _preference_assessment(
    db: AsyncSession,
    period_id: UUID,
    study_program_id: UUID,
    blocks: list[_Block],
) -> tuple[list[FinalizeWarning], FinalizeCompleteness]:
    valid_by_section: dict[UUID, _Block] = {}
    for block in blocks:
        if (
            study_program_id in block.program_ids
            and _has_valid_schedule(block)
        ):
            valid_by_section.setdefault(block.section_id, block)
    assigned_ids = {
        next(iter(block.lecturer_keys))
        for block in valid_by_section.values()
    }
    preference_rows = (
        await db.execute(
            select(LecturerSchedulePreference).where(
                LecturerSchedulePreference.academic_period_id == period_id,
                LecturerSchedulePreference.user_id.in_(
                    {UUID(user_id) for user_id in assigned_ids}
                ),
            )
        )
    ).scalars().all() if assigned_ids else []
    slots_by_user: dict[str, list[LecturerSchedulePreference]] = defaultdict(list)
    for row in preference_rows:
        slots_by_user[str(row.user_id)].append(row)

    warnings: list[FinalizeWarning] = []
    complete_users = {
        user_id
        for user_id, slots in slots_by_user.items()
        if any(slot.kind == "preferred" for slot in slots)
    }
    missing_ids = sorted(assigned_ids - complete_users)
    for user_id in missing_ids:
        warnings.append(
            FinalizeWarning(
                code="preferences_incomplete",
                message="Preferensi dosen belum lengkap.",
                user_id=user_id,
            )
        )

    for block in valid_by_section.values():
        user_id = next(iter(block.lecturer_keys))
        slots = slots_by_user.get(user_id, [])
        preferred = [slot for slot in slots if slot.kind == "preferred"]
        unavailable = [slot for slot in slots if slot.kind == "unavailable"]
        if preferred and not any(
            slot.day_of_week == block.day
            and slot.start_time.hour <= block.start
            and slot.end_time.hour >= block.end
            for slot in preferred
        ):
            warnings.append(
                FinalizeWarning(
                    code="outside_preferred_window",
                    message=(
                        f"{block.course_code} kelas {block.section_code} "
                        "dijadwalkan di luar jam preferensi."
                    ),
                    class_section_id=str(block.section_id),
                    user_id=user_id,
                )
            )
        if any(
            slot.day_of_week == block.day
            and slot.start_time.hour < block.end
            and slot.end_time.hour > block.start
            for slot in unavailable
        ):
            warnings.append(
                FinalizeWarning(
                    code="unavailable_overlap",
                    message=(
                        f"{block.course_code} kelas {block.section_code} "
                        "bertabrakan dengan blok tidak tersedia."
                    ),
                    class_section_id=str(block.section_id),
                    user_id=user_id,
                )
            )

    total = len(
        {
            block.section_id
            for block in blocks
            if study_program_id in block.program_ids
        }
    )
    completeness = FinalizeCompleteness(
        classes=FinalizeClassCompleteness(
            total=total,
            scheduled=len(valid_by_section),
        ),
        preferences=FinalizePreferenceCompleteness(
            expected=len(assigned_ids),
            submitted=len(slots_by_user),
            complete=len(complete_users),
            missing_user_ids=missing_ids,
        ),
    )
    return warnings, completeness


async def move_class(
    db: AsyncSession,
    section_id: UUID,
    payload: ClassMoveRequest,
    reason: str,
    actor_program: UUID | None,
    actor_user_id: UUID,
) -> ClassMoveResponse | ServiceError:
    section_context = await _section_period(db, section_id)
    if section_context is None:
        return _failure(
            status.HTTP_404_NOT_FOUND,
            "class_section_not_found",
            "Kelas MK tidak ditemukan.",
        )
    section, period = section_context

    blocks = await _load_blocks(db, period.academic_period_id)
    block = next((item for item in blocks if item.section_id == section_id), None)
    if block is None:
        return _failure(
            status.HTTP_404_NOT_FOUND,
            "class_section_not_found",
            "Kelas MK tidak ditemukan pada periode ini.",
        )

    if actor_program is not None and actor_program not in block.program_ids:
        return _failure(
            status.HTTP_403_FORBIDDEN,
            "akses_prodi_ditolak",
            "PJ Prodi hanya dapat mengubah jadwal kelas prodinya sendiri.",
        )

    lock = await db.get(SchedulePeriodLock, period.academic_period_id)
    if lock is not None and lock.krs_open:
        return _failure(
            status.HTTP_409_CONFLICT,
            "krs_open",
            "KRS sudah dibuka; jadwal tidak dapat diubah sebelum kunci dibuka admin.",
        )
    states = await _program_states(db, period.academic_period_id)
    if any(
        states[program_id].state == "final"
        for program_id in block.program_ids
        if program_id in states
    ):
        return _failure(
            status.HTTP_409_CONFLICT,
            "schedule_final",
            "Jadwal sudah final; perubahan memerlukan pembukaan kunci oleh admin.",
        )

    if not payload.room_id.strip():
        return field_failure("room_id", "Ruang kuliah wajib dipilih.", "required")
    room_value = payload.room_id.strip()
    try:
        room_id = UUID(room_value)
    except (ValueError, TypeError, AttributeError):
        return field_failure("room_id", "Ruang kuliah tidak valid.", "invalid_uuid")
    room = await db.get(Room, room_id)
    if room is None or not room.is_active:
        return field_failure("room_id", "Ruang kuliah tidak tersedia.", "room_not_found")
    if room.owner_study_program_id is not None and (
        room.owner_study_program_id not in block.program_ids
    ):
        return _failure(
            status.HTTP_403_FORBIDDEN,
            "invalid_room_owner",
            "Ruang kuliah tidak dimiliki oleh program studi ini.",
        )
    capacity = section.capacity or 40
    if room.capacity < capacity:
        return field_failure(
            "room_id",
            "Kapasitas ruang kurang dari kapasitas kelas.",
            "insufficient_capacity",
        )

    if not is_valid_block(payload.start_hour, block.credits):
        return field_failure(
            "start_hour",
            "Blok jadwal harus berada dalam rentang 07:00–17:00.",
            "invalid_time_block",
        )

    before = _snapshot(block)
    end_hour = hour_end(payload.start_hour, block.credits)
    schedules = (
        await db.execute(
            select(ClassSchedule)
            .where(ClassSchedule.class_section_id == section_id)
            .order_by(ClassSchedule.day_of_week, ClassSchedule.start_time)
        )
    ).scalars().all()
    schedule = schedules[0] if schedules else None
    if schedule is None:
        schedule = ClassSchedule(class_section_id=section_id)
        db.add(schedule)
    schedule.day_of_week = payload.day_of_week
    schedule.start_time = time_value(hour=payload.start_hour)
    schedule.end_time = time_value(hour=end_hour)
    schedule.room_id = room.room_id
    schedule.room_name = room.room_code
    await db.flush()

    block.day = payload.day_of_week
    block.start = payload.start_hour
    block.end = end_hour
    block.room_id = room.room_id
    block.room_label = room.room_code
    after = _snapshot(block)

    db.add(
        ScheduleEditLog(
            class_section_id=section_id,
            changed_by=actor_user_id,
            reason=reason,
            is_manual_edit=True,
            before_state=before,
            after_state=after,
        )
    )
    conflicts = [
        conflict
        for conflict in _conflicts(blocks)
        if section_id
        in {UUID(conflict.class_section_a_id), UUID(conflict.class_section_b_id)}
    ]
    state = "final" if any(
        states[program_id].state == "final"
        for program_id in block.program_ids
        if program_id in states
    ) else "in_progress"
    item = _class_item(block, state)
    input_revision = await current_input_revision(
        db, period.academic_period_id, actor_program
    )
    run = await latest_completed_run(db, period.academic_period_id, actor_program)
    item.is_stale = run is None or run.input_revision != input_revision
    item.run_id = str(run.run_id) if run is not None else None
    item.input_revision = input_revision
    await db.commit()
    return ClassMoveResponse(class_=item, conflicts=conflicts)


async def finalize_period(
    db: AsyncSession, period_id: UUID, actor_program: UUID, actor_user_id: UUID
) -> FinalizeResponse | ServiceError:
    period = await db.get(AcademicPeriod, period_id)
    if period is None:
        return _failure(
            status.HTTP_404_NOT_FOUND, "period_not_found", "Periode akademik tidak ditemukan."
        )

    states = await _program_states(db, period_id)
    status_row = states.get(actor_program)
    if status_row is not None and status_row.state == "final":
        return _failure(409, "schedule_final", "Jadwal prodi sudah final.")

    blocks = await _load_blocks(db, period_id)
    blocks_by_section = {block.section_id: block for block in blocks}
    hard_conflicts = [
        conflict
        for conflict in _conflicts(blocks)
        if actor_program
        in (
            blocks_by_section[UUID(conflict.class_section_a_id)].program_ids
            | blocks_by_section[UUID(conflict.class_section_b_id)].program_ids
        )
    ]
    if hard_conflicts:
        payload = [conflict.model_dump() for conflict in hard_conflicts]
        return _failure(
            UNPROCESSABLE,
            "conflicts_exist",
            "Jadwal prodi masih memiliki bentrok dan belum dapat difinalisasi.",
            payload,
        )

    input_revision = await current_input_revision(db, period_id, actor_program)
    run = await latest_completed_run(db, period_id, actor_program)
    if run is None or run.input_revision != input_revision:
        return _failure(
            409,
            "schedule_stale",
            "Jadwal stale; regenerate prodi sebelum finalisasi.",
            {
                "current_input_revision": input_revision,
                "run_input_revision": run.input_revision if run is not None else None,
                "run_id": str(run.run_id) if run is not None else None,
            },
        )
    unassigned = _unassigned_details(blocks, actor_program)
    if unassigned:
        return _failure(
            UNPROCESSABLE,
            "unassigned_classes",
            "Masih ada kelas yang belum memiliki jadwal operasional lengkap.",
            unassigned,
        )

    warnings, completeness = await _preference_assessment(
        db, period_id, actor_program, blocks
    )
    if status_row is None:
        status_row = ScheduleProgramStatus(
            academic_period_id=period_id,
            study_program_id=actor_program,
            state="draft",
        )
        db.add(status_row)
    status_row.state = "final"
    status_row.finalized_by = actor_user_id
    status_row.finalized_at = datetime.now(timezone.utc)

    program_ids = await all_study_program_ids(db)
    final_ids = {program_id for program_id, row in states.items() if row.state == "final"}
    final_ids.add(actor_program)
    all_final = bool(program_ids) and all(
        program_id in final_ids for program_id in program_ids
    )
    if all_final:
        lock = await db.get(SchedulePeriodLock, period_id)
        if lock is None:
            lock = SchedulePeriodLock(academic_period_id=period_id)
            db.add(lock)
        lock.krs_open = True
        lock.locked_at = datetime.now(timezone.utc)
        lock.locked_by = actor_user_id

    settings_rows = (
        await db.execute(
            select(SchedulePeriodSettings)
            .where(
                SchedulePeriodSettings.academic_period_id == period_id,
                or_(
                    SchedulePeriodSettings.study_program_id == actor_program,
                    SchedulePeriodSettings.study_program_id.is_(None),
                ),
            )
            .with_for_update()
        )
    ).scalars().all()
    for settings in settings_rows:
        if settings.study_program_id == actor_program or all_final:
            settings.finalized_by = actor_user_id
            settings.finalized_at = status_row.finalized_at

    for section_id, block in blocks_by_section.items():
        if actor_program not in block.program_ids:
            continue
        db.add(
            ScheduleEditLog(
                class_section_id=section_id,
                changed_by=actor_user_id,
                reason="finalize",
                is_manual_edit=False,
                before_state=_snapshot(block),
                after_state={
                    "state": "final",
                    "run_id": str(run.run_id),
                    "input_revision": input_revision,
                    "warnings": [item.model_dump(mode="json") for item in warnings],
                    "completeness": completeness.model_dump(mode="json"),
                },
            )
        )
    await db.commit()
    return FinalizeResponse(
        study_program_id=str(actor_program),
        state=status_row.state,
        all_final=all_final,
        warnings=warnings,
        completeness=completeness,
    )


async def unlock_period(
    db: AsyncSession, period_id: UUID, payload: UnlockRequest, actor_user_id: UUID
) -> dict[str, Any] | ServiceError:
    reason = payload.reason.strip()
    if not reason:
        return field_failure("reason", "Alasan pembukaan kunci wajib diisi.", "required")

    period = await db.get(AcademicPeriod, period_id)
    if period is None:
        return _failure(
            status.HTTP_404_NOT_FOUND, "period_not_found", "Periode akademik tidak ditemukan."
        )

    lock = await db.get(SchedulePeriodLock, period_id)
    if lock is None:
        lock = SchedulePeriodLock(academic_period_id=period_id)
        db.add(lock)
    was_open = bool(lock.krs_open)
    lock.krs_open = False
    lock.locked_at = datetime.now(timezone.utc)
    lock.locked_by = actor_user_id

    statuses = (
        await db.execute(
            select(ScheduleProgramStatus).where(
                ScheduleProgramStatus.academic_period_id == period_id
            )
        )
    ).scalars().all()
    state_before = {row.study_program_id: row.state for row in statuses}
    final_count = 0
    for status_row in statuses:
        if status_row.state != "final":
            continue
        final_count += 1
        status_row.state = "in_progress"
        status_row.finalized_by = None
        status_row.finalized_at = None
    settings_rows = (
        await db.execute(
            select(SchedulePeriodSettings).where(
                SchedulePeriodSettings.academic_period_id == period_id
            )
        )
    ).scalars().all()
    for settings in settings_rows:
        settings.finalized_by = None
        settings.finalized_at = None

    section_ids = (
        await db.execute(
            select(ClassSection.class_section_id.label("section_id"))
            .join(
                OfferingComponent,
                OfferingComponent.offering_component_id
                == ClassSection.offering_component_id,
            )
            .join(
                CourseOffering,
                CourseOffering.course_offering_id == OfferingComponent.course_offering_id,
            )
            .where(CourseOffering.academic_period_id == period_id)
        )
    ).scalars().all()
    blocks = await _load_blocks(db, period_id)
    state_by_section = {block.section_id: block.program_id for block in blocks}
    for section_id in section_ids:
        db.add(
            ScheduleEditLog(
                class_section_id=section_id,
                changed_by=actor_user_id,
                reason=reason,
                is_manual_edit=False,
                before_state={
                    "krs_open": was_open,
                    "state": state_before.get(state_by_section.get(section_id), "draft"),
                },
                after_state={"krs_open": False, "state": "in_progress"},
            )
        )
    await db.commit()
    return {
        "state": "in_progress",
        "message": "Kunci jadwal dibuka; jadwal kembali dapat diubah.",
        "unlocked_count": final_count,
        "audit_count": len(section_ids),
    }


def _scoped_section_ids(actor_program: UUID | None, period_id: UUID | None):
    """Kelas yang boleh dibaca actor, dibatasi periode dan prodi PJ."""
    statement = (
        select(ClassSection.class_section_id)
        .join(
            OfferingComponent,
            ClassSection.offering_component_id
            == OfferingComponent.offering_component_id,
        )
        .join(
            CourseOffering,
            CourseOffering.course_offering_id == OfferingComponent.course_offering_id,
        )
    )
    if period_id is not None:
        statement = statement.where(CourseOffering.academic_period_id == period_id)
    if actor_program is not None:
        statement = (
            statement.join(
                CourseOfferingEligibility,
                CourseOfferingEligibility.course_offering_id
                == CourseOffering.course_offering_id,
            )
            .join(
                CurriculumCourse,
                CurriculumCourse.curriculum_course_id
                == CourseOfferingEligibility.curriculum_course_id,
            )
            .join(
                Curriculum,
                Curriculum.curriculum_id == CurriculumCourse.curriculum_id,
            )
            .join(
                StudyProgram,
                StudyProgram.study_program_id == Curriculum.study_program_id,
            )
            .where(StudyProgram.study_program_id == actor_program)
        )
    return statement


async def get_edit_log(
    db: AsyncSession,
    period_id: str | None,
    class_section_id: str | None,
    actor_program: UUID | None,
) -> list[EditLogEntry] | ServiceError:
    try:
        period_uuid = UUID(period_id) if period_id else None
        section_uuid = UUID(class_section_id) if class_section_id else None
    except (ValueError, AttributeError, TypeError):
        return _failure(
            status.HTTP_404_NOT_FOUND, "not_found", "Periode atau kelas MK tidak ditemukan."
        )

    statement = (
        select(ScheduleEditLog, User.full_name)
        .outerjoin(User, User.user_id == ScheduleEditLog.changed_by)
        .where(
            ScheduleEditLog.class_section_id.in_(
                _scoped_section_ids(actor_program, period_uuid)
            )
        )
        .order_by(ScheduleEditLog.created_at.desc(), ScheduleEditLog.id.desc())
    )
    if section_uuid is not None:
        statement = statement.where(ScheduleEditLog.class_section_id == section_uuid)

    rows = (await db.execute(statement)).all()
    return [
        EditLogEntry(
            id=str(log.id),
            class_section_id=str(log.class_section_id),
            changed_by=str(log.changed_by),
            changed_by_name=name or "",
            reason=log.reason,
            before_state=log.before_state,
            after_state=log.after_state,
            created_at=log.created_at.isoformat(),
        )
        for log, name in rows
    ]
