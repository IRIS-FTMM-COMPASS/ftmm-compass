"""Papan Jadwal Bersama lima prodi: kelas MK, status, dan konflik."""

import math
from dataclasses import dataclass, field
from datetime import time as time_value
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
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
    ScheduleProgramStatus,
    ScheduleRun,
    StudyProgram,
    UnassignedClass,
    User,
)
from schemas import (
    BoardClassItem,
    BoardConflictItem,
    BoardData,
    BoardProgramStatus,
    BoardResponse,
    ConflictListResponse,
    UnassignedItem,
)
from scheduling_common import (
    all_study_program_ids,
    blocks_overlap,
    current_period_id,
    status_label,
)

router = APIRouter()

NOT_FOUND = status.HTTP_404_NOT_FOUND


@dataclass
class _Block:
    class_section_id: UUID
    section_code: str
    course_code: str
    course_name: str
    course_id: UUID
    credits: int
    study_program_id: UUID | None
    study_program_code: str
    class_schedule_id: UUID | None
    day_of_week: int = 0
    start_hour: int = 0
    end_hour: int = 0
    room_id: UUID | None = None
    room_label: str = ""
    curriculum_course_ids: set[UUID] = field(default_factory=set)
    study_program_ids: set[UUID] = field(default_factory=set)
    lecturer_keys: set[str] = field(default_factory=set)
    lecturers: list[str] = field(default_factory=list)
    state: str = "draft"
    is_manually_edited: bool = False

    @property
    def room_key(self) -> str:
        if self.room_id is not None:
            return f"id:{self.room_id}"
        if self.room_label:
            return f"name:{self.room_label.strip().casefold()}"
        return ""


@dataclass
class _BoardContext:
    period: AcademicPeriod
    classes: list[BoardClassItem]
    conflicts: list[BoardConflictItem]
    programs: list[BoardProgramStatus]
    unassigned: list[UnassignedItem]


def _hour(value: time_value | None, *, ceiling: bool = False) -> int:
    if value is None:
        return 0
    minutes = value.hour * 60 + value.minute
    return math.ceil(minutes / 60) if ceiling else minutes // 60


def _period_label(period: AcademicPeriod) -> str:
    return f"{period.academic_year_start}/{period.academic_year_start + 1} {period.term.title()}"


def _deny(code: str, message: str, status_code: int) -> JSONResponse:
    return error_response(status_code, code, message, detail=message)


def _actor_study_program_id(user: User) -> str | None:
    """Prodi PJ Prodi untuk penyaringan affordance edit pada UI."""
    if user.role != "lecturer":
        return None
    profile = user.lecturer_profile
    if profile is None or not profile.is_program_coordinator:
        return None
    return str(profile.study_program_id) if profile.study_program_id else None


async def _resolve_period(
    db: AsyncSession, period_id: str | None
) -> AcademicPeriod | None:
    if period_id:
        try:
            requested = UUID(period_id)
        except (ValueError, AttributeError, TypeError):
            return None
        return (
            await db.execute(
                select(AcademicPeriod).where(
                    AcademicPeriod.academic_period_id == requested
                )
            )
        ).scalars().first()

    active_id = await current_period_id(db)
    if active_id is None:
        return None
    return await db.get(AcademicPeriod, active_id)


async def _program_statuses(
    db: AsyncSession, period_id: UUID
) -> tuple[list[BoardProgramStatus], dict[UUID, str]]:
    program_ids = await all_study_program_ids(db)
    code_rows = (
        await db.execute(
            select(StudyProgram.study_program_id, StudyProgram.program_code).where(
                StudyProgram.study_program_id.in_(program_ids)
            )
        )
    ).all()
    codes = {row.study_program_id: row.program_code for row in code_rows}

    if program_ids:
        await db.execute(
            pg_insert(ScheduleProgramStatus)
            .values(
                [
                    {
                        "academic_period_id": period_id,
                        "study_program_id": program_id,
                        "state": "draft",
                    }
                    for program_id in program_ids
                ]
            )
            .on_conflict_do_nothing(
                index_elements=("academic_period_id", "study_program_id")
            )
        )

    existing = (
        await db.execute(
            select(ScheduleProgramStatus).where(
                ScheduleProgramStatus.academic_period_id == period_id
            )
        )
    ).scalars().all()
    by_program = {row.study_program_id: row for row in existing}

    programs = [
        BoardProgramStatus(
            study_program_id=str(program_id),
            study_program_code=codes.get(program_id, ""),
            state=by_program[program_id].state,
            label=status_label(by_program[program_id].state),
            finalized_at=(
                by_program[program_id].finalized_at.isoformat()
                if by_program[program_id].finalized_at
                else None
            ),
        )
        for program_id in program_ids
    ]
    return programs, {program_id: by_program[program_id].state for program_id in program_ids}


async def _blocks(
    db: AsyncSession, period_id: UUID, state_by_program: dict[UUID, str]
) -> list[_Block]:
    edited = select(ScheduleEditLog.id).where(
        ScheduleEditLog.class_section_id == ClassSection.class_section_id
    ).exists()
    rows = (
        await db.execute(
            select(
                ClassSection.class_section_id.label("class_section_id"),
                ClassSection.section_code.label("section_code"),
                Course.course_id.label("course_id"),
                Course.course_code.label("course_code"),
                Course.course_name.label("course_name"),
                CurriculumCourse.credits_total.label("credits"),
                StudyProgram.study_program_id.label("study_program_id"),
                StudyProgram.program_code.label("study_program_code"),
                ClassSchedule.class_schedule_id.label("class_schedule_id"),
                ClassSchedule.day_of_week.label("day_of_week"),
                ClassSchedule.start_time.label("start_time"),
                ClassSchedule.end_time.label("end_time"),
                ClassSchedule.room_id.label("room_id"),
                ClassSchedule.room_name.label("room_name"),
                Room.room_code.label("room_code"),
                CurriculumCourse.curriculum_course_id.label("curriculum_course_id"),
                edited.label("is_manually_edited"),
            )
            .join(
                OfferingComponent,
                ClassSection.offering_component_id
                == OfferingComponent.offering_component_id,
            )
            .join(
                CourseOffering,
                OfferingComponent.course_offering_id
                == CourseOffering.course_offering_id,
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
    program_ids_by_section: dict[UUID, set[UUID]] = {}
    for row in rows:
        if row.study_program_id is not None:
            program_ids_by_section.setdefault(row.class_section_id, set()).add(
                row.study_program_id
            )
        key = (row.class_section_id, row.class_schedule_id)
        block = blocks.get(key)
        if block is None:
            block = _Block(
                class_section_id=row.class_section_id,
                section_code=row.section_code,
                course_code=row.course_code,
                course_name=row.course_name,
                course_id=row.course_id,
                credits=row.credits or 0,
                study_program_id=row.study_program_id,
                study_program_code=row.study_program_code or "",
                class_schedule_id=row.class_schedule_id,
                day_of_week=row.day_of_week or 0,
                start_hour=_hour(row.start_time),
                end_hour=_hour(row.end_time, ceiling=True),
                room_id=row.room_id,
                room_label=row.room_code or row.room_name or "",
                state=state_by_program.get(row.study_program_id, "draft"),
                is_manually_edited=bool(row.is_manually_edited),
            )
            blocks[key] = block
        if row.curriculum_course_id is not None:
            block.curriculum_course_ids.add(row.curriculum_course_id)
    for block in blocks.values():
        block.study_program_ids = program_ids_by_section.get(
            block.class_section_id, set()
        )

    all_course_ids = set()
    for block in blocks.values():
        all_course_ids.update(block.curriculum_course_ids)

    references: dict[UUID, list[tuple[str, str]]] = {}
    if all_course_ids:
        ref_rows = (
            await db.execute(
                select(
                    CourseInstructorReference.curriculum_course_id.label("course_id"),
                    CourseInstructorReference.user_id.label("user_id"),
                    CourseInstructorReference.instructor_name.label("instructor_name"),
                    User.full_name.label("full_name"),
                )
                .outerjoin(User, User.user_id == CourseInstructorReference.user_id)
                .where(
                    CourseInstructorReference.curriculum_course_id.in_(all_course_ids)
                )
                .order_by(CourseInstructorReference.instructor_name)
            )
        ).all()
        for ref in ref_rows:
            name = ref.instructor_name or (ref.full_name if ref.full_name else "")
            key = (
                str(ref.user_id)
                if ref.user_id is not None
                else f"name:{name.strip().casefold()}"
            )
            references.setdefault(ref.course_id, []).append((key, ref.full_name or name))

    for block in blocks.values():
        names: dict[str, str] = {}
        for course_id in sorted(block.curriculum_course_ids, key=str):
            for key, name in references.get(course_id, []):
                names.setdefault(key, name)
        block.lecturer_keys = set(names)
        block.lecturers = [names[key] for key in sorted(names, key=lambda k: names[k])]

    return list(blocks.values())


def _conflicts(blocks: list[_Block]) -> list[BoardConflictItem]:
    scheduled = [
        block for block in blocks if block.day_of_week and block.end_hour > block.start_hour
    ]
    conflicts: list[BoardConflictItem] = []
    for index, first in enumerate(scheduled):
        for second in scheduled[index + 1 :]:
            if first.class_section_id == second.class_section_id:
                continue
            if first.day_of_week != second.day_of_week or not blocks_overlap(
                first.start_hour,
                first.end_hour,
                second.start_hour,
                second.end_hour,
            ):
                continue
            shared = first.day_of_week, max(first.start_hour, second.start_hour), min(
                first.end_hour, second.end_hour
            )
            for kind in ("lecturer", "room"):
                if kind == "lecturer" and not (first.lecturer_keys & second.lecturer_keys):
                    continue
                if kind == "room" and not (
                    first.room_key and first.room_key == second.room_key
                ):
                    continue
                conflicts.append(
                    BoardConflictItem(
                        class_section_a_id=str(first.class_section_id),
                        class_section_b_id=str(second.class_section_id),
                        kind=kind,
                        day_of_week=shared[0],
                        start_hour=shared[1],
                        end_hour=shared[2],
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


async def _unassigned(db: AsyncSession, period_id: UUID) -> list[UnassignedItem]:
    latest_run_id = (
        await db.execute(
            select(ScheduleRun.run_id)
            .where(ScheduleRun.academic_period_id == period_id)
            .order_by(ScheduleRun.started_at.desc(), ScheduleRun.run_id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if latest_run_id is None:
        return []

    rows = (
        await db.execute(
            select(
                UnassignedClass.class_section_id.label("class_section_id"),
                UnassignedClass.reason.label("reason"),
                Course.course_code.label("course_code"),
            )
            .join(
                ClassSection,
                ClassSection.class_section_id == UnassignedClass.class_section_id,
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
            .where(UnassignedClass.run_id == latest_run_id)
            .order_by(Course.course_code, ClassSection.section_code)
        )
    ).all()
    return [
        UnassignedItem(
            class_section_id=str(row.class_section_id),
            course_code=row.course_code,
            reason=row.reason,
        )
        for row in rows
    ]


async def _board_context(
    db: AsyncSession, period_id: str | None
) -> _BoardContext | JSONResponse:
    period = await _resolve_period(db, period_id)
    if period is None:
        return _deny(
            "period_not_found",
            "Periode akademik yang diminta tidak ditemukan.",
            NOT_FOUND,
        )

    programs, state_by_program = await _program_statuses(
        db, period.academic_period_id
    )
    blocks = await _blocks(db, period.academic_period_id, state_by_program)
    classes = [
        BoardClassItem(
            class_section_id=str(block.class_section_id),
            section_code=block.section_code,
            course_code=block.course_code,
            course_name=block.course_name,
            course_id=str(block.course_id),
            credits=block.credits,
            face_to_face_minutes=block.credits * 50,
            study_program_id=(
                str(block.study_program_id) if block.study_program_id else ""
            ),
            study_program_code=block.study_program_code,
            program_ids=[
                str(program_id)
                for program_id in sorted(block.study_program_ids, key=str)
            ],
            start_hour=block.start_hour,
            end_hour=block.end_hour,
            room_id=str(block.room_id) if block.room_id else None,
            room_code=block.room_label or None,
            lecturers=block.lecturers,
            is_manually_edited=block.is_manually_edited,
            state=block.state,
        )
        for block in blocks
    ]
    return _BoardContext(
        period=period,
        classes=classes,
        conflicts=_conflicts(blocks),
        programs=programs,
        unassigned=await _unassigned(db, period.academic_period_id),
    )


def _meta(context: _BoardContext, actor_study_program_id: str | None = None) -> dict[str, Any]:
    return {
        "period_label": _period_label(context.period),
        "class_count": len(context.classes),
        "conflict_count": len(context.conflicts),
        "program_count": len(context.programs),
        "unassigned_count": len(context.unassigned),
        "actor_study_program_id": actor_study_program_id,
    }


@router.get("/scheduling/board", response_model=BoardResponse)
async def get_board(
    period_id: str | None = Query(default=None),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    context = await _board_context(db, period_id)
    if isinstance(context, JSONResponse):
        return context
    return BoardResponse(
        data=BoardData(
            academic_period_id=str(context.period.academic_period_id),
            period_label=_period_label(context.period),
            classes=context.classes,
            conflicts=context.conflicts,
            programs=context.programs,
            unassigned=context.unassigned,
        ),
        meta=_meta(context, _actor_study_program_id(_user)),
    )


@router.get("/scheduling/conflicts", response_model=ConflictListResponse)
async def get_conflicts(
    period_id: str | None = Query(default=None),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    context = await _board_context(db, period_id)
    if isinstance(context, JSONResponse):
        return context
    return ConflictListResponse(data=context.conflicts, meta=_meta(context, _actor_study_program_id(_user)))
