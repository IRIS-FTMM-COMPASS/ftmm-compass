"""Edit jadwal kelas, finalisasi per prodi, dan pembukaan kunci KRS.

Perubahan manual tetap disimpan walaupun menghasilkan bentrok; bentrok
dilaporkan kembali supaya PJ Prodi dapat menindaklanjutinya. Aturan bentrok
di sini mengikuti Papan Jadwal Bersama: dosen yang sama atau ruang yang sama
dengan blok jam yang bertabrakan.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime, time as time_value, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.errors import error_response
from auth import get_current_user
from database import get_db
from models import (
    AcademicPeriod,
    ClassSchedule,
    ClassSection,
    Course,
    CourseInstructorReference,
    CourseOffering,
    CourseOfferingEligibility,
    Curriculum,
    CurriculumCourse,
    OfferingComponent,
    Room,
    ScheduleEditLog,
    SchedulePeriodLock,
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
    EditLogResponse,
    FinalizeResponse,
    UnlockRequest,
)
from scheduling_common import (
    all_study_program_ids,
    blocks_overlap,
    hour_end,
    is_valid_block,
)

router = APIRouter()

_UNPROCESSABLE = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)
DEFAULT_SECTION_CAPACITY = 40


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


def _hour(value: time_value | None, *, ceiling: bool = False) -> int:
    if value is None:
        return 0
    minutes = value.hour * 60 + value.minute
    return math.ceil(minutes / 60) if ceiling else minutes // 60


def _deny(status_code: int, code: str, message: str) -> JSONResponse:
    return error_response(status_code, code, message, detail=message)


def _field_error(field_name: str, message: str, code: str) -> JSONResponse:
    return error_response(
        _UNPROCESSABLE,
        "validation_error",
        message,
        detail=message,
        details=[{"field": field_name, "message": message, "code": code}],
    )


def _actor_program_id(
    current_user: User,
) -> UUID | None | JSONResponse:
    """None berarti admin; UUID berarti PJ prodi; sisanya penolakan."""
    if current_user.role == "admin":
        return None
    profile = current_user.lecturer_profile
    if (
        current_user.role != "lecturer"
        or profile is None
        or not profile.is_program_coordinator
        or profile.study_program_id is None
    ):
        return _deny(
            status.HTTP_403_FORBIDDEN,
            "forbidden",
            "Perubahan jadwal hanya tersedia untuk admin dan PJ Prodi.",
        )
    return profile.study_program_id


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
            .join(Course, Course.course_id == CourseOffering.course_id)
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
            )
            blocks[key] = block
        if row.program_id is not None:
            block.program_ids.add(row.program_id)
        if row.curriculum_course_id is not None:
            block.curriculum_course_ids.add(row.curriculum_course_id)

    course_ids = {
        course_id
        for block in blocks.values()
        for course_id in block.curriculum_course_ids
    }
    references: dict[UUID, list[tuple[str, str]]] = {}
    if course_ids:
        ref_rows = (
            await db.execute(
                select(
                    CourseInstructorReference.curriculum_course_id.label("course_id"),
                    CourseInstructorReference.user_id.label("user_id"),
                    CourseInstructorReference.instructor_name.label("instructor_name"),
                    User.full_name.label("full_name"),
                )
                .outerjoin(User, User.user_id == CourseInstructorReference.user_id)
                .where(CourseInstructorReference.curriculum_course_id.in_(course_ids))
                .order_by(CourseInstructorReference.instructor_name)
            )
        ).all()
        for ref in ref_rows:
            name = ref.instructor_name or ref.full_name or ""
            key = (
                str(ref.user_id)
                if ref.user_id is not None
                else f"name:{name.strip().casefold()}"
            )
            references.setdefault(ref.course_id, []).append(
                (key, ref.full_name or name)
            )

    for block in blocks.values():
        names: dict[str, str] = {}
        for course_id in sorted(block.curriculum_course_ids, key=str):
            for key, name in references.get(course_id, []):
                names.setdefault(key, name)
        block.lecturer_keys = set(names)
        block.lecturer_names = [names[key] for key in sorted(names, key=lambda k: names[k])]
    return list(blocks.values())


def _conflicts(blocks: list[_Block]) -> list[BoardConflictItem]:
    scheduled = [block for block in blocks if block.day and block.end > block.start]
    conflicts: list[BoardConflictItem] = []
    for index, first in enumerate(scheduled):
        for second in scheduled[index + 1 :]:
            if first.day != second.day or not blocks_overlap(
                first.start, first.end, second.start, second.end
            ):
                continue
            shared = {
                "day_of_week": first.day,
                "start_hour": max(first.start, second.start),
                "end_hour": min(first.end, second.end),
            }
            if first.room_key and first.room_key == second.room_key:
                conflicts.append(
                    BoardConflictItem(
                        class_section_a_id=str(first.section_id),
                        class_section_b_id=str(second.section_id),
                        kind="room",
                        **shared,
                    )
                )
            if first.lecturer_keys & second.lecturer_keys:
                conflicts.append(
                    BoardConflictItem(
                        class_section_a_id=str(first.section_id),
                        class_section_b_id=str(second.section_id),
                        kind="lecturer",
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


def _class_item(block: _Block, state: str) -> BoardClassItem:
    return BoardClassItem(
        class_section_id=str(block.section_id),
        section_code=block.section_code,
        course_code=block.course_code,
        course_name=block.course_name,
        credits=block.credits,
        study_program_id=str(block.program_id) if block.program_id else "",
        study_program_code=block.program_code,
        day_of_week=block.day,
        start_hour=block.start,
        end_hour=block.end,
        room_id=str(block.room_id) if block.room_id else None,
        room_code=block.room_label or None,
        lecturers=block.lecturer_names,
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


@router.patch("/scheduling/classes/{section_id}", response_model=ClassMoveResponse)
async def move_class(
    section_id: UUID,
    payload: ClassMoveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    reason = payload.reason.strip()
    if not reason:
        return _field_error("reason", "Alasan perubahan jadwal wajib diisi.", "required")

    actor_program = _actor_program_id(current_user)
    if isinstance(actor_program, JSONResponse):
        return actor_program

    section_context = await _section_period(db, section_id)
    if section_context is None:
        return _deny(
            status.HTTP_404_NOT_FOUND,
            "class_section_not_found",
            "Kelas MK tidak ditemukan.",
        )
    section, period = section_context

    blocks = await _load_blocks(db, period.academic_period_id)
    block = next((item for item in blocks if item.section_id == section_id), None)
    if block is None:
        return _deny(
            status.HTTP_404_NOT_FOUND,
            "class_section_not_found",
            "Kelas MK tidak ditemukan pada periode ini.",
        )

    if actor_program is not None and actor_program not in block.program_ids:
        return _deny(
            status.HTTP_403_FORBIDDEN,
            "akses_prodi_ditolak",
            "PJ Prodi hanya dapat mengubah jadwal kelas prodinya sendiri.",
        )

    lock = await db.get(SchedulePeriodLock, period.academic_period_id)
    if lock is not None and lock.krs_open:
        return _deny(
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
        return _deny(
            status.HTTP_409_CONFLICT,
            "schedule_final",
            "Jadwal sudah final; perubahan memerlukan pembukaan kunci oleh admin.",
        )

    if not payload.room_id.strip():
        return _field_error("room_id", "Ruang kuliah wajib dipilih.", "required")
    room_value = payload.room_id.strip()
    try:
        room_id = UUID(room_value)
    except (ValueError, TypeError, AttributeError):
        return _field_error("room_id", "Ruang kuliah tidak valid.", "invalid_uuid")
    room = await db.get(Room, room_id)
    if room is None or not room.is_active:
        return _field_error("room_id", "Ruang kuliah tidak tersedia.", "room_not_found")
    if room.owner_study_program_id is not None and (
        room.owner_study_program_id not in block.program_ids
    ):
        return _deny(
            status.HTTP_403_FORBIDDEN,
            "invalid_room_owner",
            "Ruang kuliah tidak dimiliki oleh program studi ini.",
        )
    capacity = section.capacity or DEFAULT_SECTION_CAPACITY
    if room.capacity < capacity:
        return _field_error(
            "room_id",
            "Kapasitas ruang kurang dari kapasitas kelas.",
            "insufficient_capacity",
        )

    if not is_valid_block(payload.start_hour, block.credits):
        return _field_error(
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
            changed_by=current_user.user_id,
            reason=reason,
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
    await db.commit()
    return ClassMoveResponse(class_=item, conflicts=conflicts)


@router.post(
    "/scheduling/periods/{period_id}/finalize", response_model=FinalizeResponse
)
async def finalize_period(
    period_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    actor_program = _actor_program_id(current_user)
    if isinstance(actor_program, JSONResponse):
        return actor_program
    if actor_program is None:
        return _deny(
            status.HTTP_403_FORBIDDEN,
            "forbidden",
            "Finalisasi jadwal dilakukan oleh PJ Prodi untuk prodinya sendiri.",
        )

    period = await db.get(AcademicPeriod, period_id)
    if period is None:
        return _deny(
            status.HTTP_404_NOT_FOUND,
            "period_not_found",
            "Periode akademik tidak ditemukan.",
        )

    blocks = await _load_blocks(db, period_id)
    blocks_by_section = {block.section_id: block for block in blocks}
    conflicts = [
        conflict
        for conflict in _conflicts(blocks)
        if actor_program
        in (
            blocks_by_section[UUID(conflict.class_section_a_id)].program_ids
            | blocks_by_section[UUID(conflict.class_section_b_id)].program_ids
        )
    ]
    if conflicts:
        return error_response(
            _UNPROCESSABLE,
            "conflicts_exist",
            "Jadwal prodi masih memiliki bentrok dan belum dapat difinalisasi.",
            conflicts=[conflict.model_dump() for conflict in conflicts],
            details=[conflict.model_dump() for conflict in conflicts],
        )

    states = await _program_states(db, period_id)
    status_row = states.get(actor_program)
    if status_row is None:
        status_row = ScheduleProgramStatus(
            academic_period_id=period_id,
            study_program_id=actor_program,
            state="draft",
        )
        db.add(status_row)
    status_row.state = "final"
    status_row.finalized_by = current_user.user_id
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
        lock.locked_by = current_user.user_id
    await db.commit()
    return FinalizeResponse(
        study_program_id=str(actor_program),
        state=status_row.state,
        all_final=all_final,
    )


@router.post("/scheduling/periods/{period_id}/unlock")
async def unlock_period(
    period_id: UUID,
    payload: UnlockRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "admin":
        return _deny(
            status.HTTP_403_FORBIDDEN,
            "forbidden",
            "Pembukaan kunci jadwal hanya tersedia untuk admin.",
        )
    reason = payload.reason.strip()
    if not reason:
        return _field_error("reason", "Alasan pembukaan kunci wajib diisi.", "required")

    period = await db.get(AcademicPeriod, period_id)
    if period is None:
        return _deny(
            status.HTTP_404_NOT_FOUND,
            "period_not_found",
            "Periode akademik tidak ditemukan.",
        )

    lock = await db.get(SchedulePeriodLock, period_id)
    if lock is None:
        lock = SchedulePeriodLock(academic_period_id=period_id)
        db.add(lock)
    was_open = bool(lock.krs_open)
    lock.krs_open = False
    lock.locked_at = datetime.now(timezone.utc)
    lock.locked_by = current_user.user_id

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
                CourseOffering.course_offering_id
                == OfferingComponent.course_offering_id,
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
                changed_by=current_user.user_id,
                reason=reason,
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


@router.get("/scheduling/edit-log", response_model=EditLogResponse)
async def get_edit_log(
    period_id: str | None = Query(default=None),
    class_section_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    actor_program = _actor_program_id(current_user)
    if isinstance(actor_program, JSONResponse):
        return actor_program

    try:
        period_uuid = UUID(period_id) if period_id else None
        section_uuid = UUID(class_section_id) if class_section_id else None
    except (ValueError, AttributeError, TypeError):
        return _deny(
            status.HTTP_404_NOT_FOUND,
            "not_found",
            "Periode atau kelas MK tidak ditemukan.",
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
    entries = [
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
    return EditLogResponse(data=entries, meta={"total": len(entries)})
