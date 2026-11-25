"""Papan Jadwal Bersama lima prodi: kelas MK, status, dan konflik."""

import math
from dataclasses import dataclass, field
from datetime import time as time_value
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.errors import error_response
from auth import get_current_user
from database import get_db
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
    BoardClassProgram,
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
from ..scheduler import (
    build_conflict_item,
    current_input_revision,
    enrich_unassigned_items,
    latest_completed_run,
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
    study_program_name: str
    class_schedule_id: UUID | None
    day_of_week: int = 0
    start_hour: int = 0
    end_hour: int = 0
    room_id: UUID | None = None
    room_label: str = ""
    curriculum_course_ids: set[UUID] = field(default_factory=set)
    curriculum_program_ids: dict[UUID, UUID] = field(default_factory=dict)
    study_program_ids: set[UUID] = field(default_factory=set)
    study_program_codes: dict[UUID, str] = field(default_factory=dict)
    study_program_names: dict[UUID, str] = field(default_factory=dict)
    lecturer_keys: set[str] = field(default_factory=set)
    lecturers: list[str] = field(default_factory=list)
    assigned_lecturer_id: UUID | None = None
    assigned_lecturer_name: str | None = None
    assigned_curriculum_course_id: UUID | None = None
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


def _can_edit(user: User, program_ids: set[UUID]) -> bool:
    if user.role == "admin" and user.is_active:
        return True
    actor_program_id = _actor_study_program_id(user)
    return actor_program_id is not None and UUID(actor_program_id) in program_ids


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
    db: AsyncSession,
    period_id: UUID,
    run_by_program: dict[UUID, ScheduleRun | None] | None = None,
    revision_by_program: dict[UUID, int] | None = None,
) -> tuple[list[BoardProgramStatus], dict[UUID, str]]:
    program_ids = await all_study_program_ids(db)
    if run_by_program is None or revision_by_program is None:
        computed_runs: dict[UUID, ScheduleRun | None] = {}
        computed_revisions: dict[UUID, int] = {}
        for program_id in program_ids:
            computed_runs[program_id] = await latest_completed_run(
                db, period_id, program_id
            )
            computed_revisions[program_id] = await current_input_revision(
                db, period_id, program_id
            )
        run_by_program = computed_runs
        revision_by_program = computed_revisions
    code_rows = (
        await db.execute(
            select(
                StudyProgram.study_program_id,
                StudyProgram.program_code,
                StudyProgram.program_name,
            ).where(StudyProgram.study_program_id.in_(program_ids))
        )
    ).all()
    codes = {row.study_program_id: row.program_code for row in code_rows}
    names = {row.study_program_id: row.program_name for row in code_rows}

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
            study_program_name=names.get(program_id, ""),
            state=by_program[program_id].state,
            label=status_label(by_program[program_id].state),
            finalized_at=(
                by_program[program_id].finalized_at.isoformat()
                if by_program[program_id].finalized_at
                else None
            ),
            is_stale=(
                run_by_program.get(program_id) is None
                or run_by_program[program_id].input_revision
                != revision_by_program.get(program_id, 0)
            ),
            run_id=(
                str(run_by_program[program_id].run_id)
                if run_by_program.get(program_id) is not None
                else None
            ),
            input_revision=revision_by_program.get(program_id, 0),
        )
        for program_id in program_ids
    ]
    return programs, {program_id: by_program[program_id].state for program_id in program_ids}


async def _blocks(
    db: AsyncSession, period_id: UUID, state_by_program: dict[UUID, str]
) -> list[_Block]:
    edited = (
        select(ScheduleEditLog.id)
        .where(
            ScheduleEditLog.class_section_id == ClassSection.class_section_id,
            ScheduleEditLog.is_manual_edit.is_(True),
            ScheduleEditLog.before_state.has_key("day_of_week"),
        )
        .exists()
    )
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
                StudyProgram.program_name.label("study_program_name"),
                ClassSchedule.class_schedule_id.label("class_schedule_id"),
                ClassSchedule.day_of_week.label("day_of_week"),
                ClassSchedule.start_time.label("start_time"),
                ClassSchedule.end_time.label("end_time"),
                ClassSchedule.room_id.label("room_id"),
                ClassSchedule.room_name.label("room_name"),
                Room.room_code.label("room_code"),
                CurriculumCourse.curriculum_course_id.label("curriculum_course_id"),
                edited.label("is_manually_edited"),
                ClassInstructorAssignment.user_id.label("assigned_user_id"),
                ClassInstructorAssignment.curriculum_course_id.label(
                    "assigned_curriculum_course_id"
                ),
                User.full_name.label("assigned_name"),
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
                User.user_id == ClassInstructorAssignment.user_id,
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
                study_program_name=row.study_program_name or "",
                class_schedule_id=row.class_schedule_id,
                day_of_week=row.day_of_week or 0,
                start_hour=_hour(row.start_time),
                end_hour=_hour(row.end_time, ceiling=True),
                room_id=row.room_id,
                room_label=row.room_code or row.room_name or "",
                is_manually_edited=bool(row.is_manually_edited),
                lecturer_keys=(
                    {str(row.assigned_user_id)} if row.assigned_user_id else set()
                ),
                lecturers=[row.assigned_name] if row.assigned_name else [],
                assigned_lecturer_id=row.assigned_user_id,
                assigned_lecturer_name=row.assigned_name,
                assigned_curriculum_course_id=row.assigned_curriculum_course_id,
            )
            blocks[key] = block
        if row.study_program_id is not None:
            block.study_program_ids.add(row.study_program_id)
            block.study_program_codes[row.study_program_id] = row.study_program_code or ""
            block.study_program_names[row.study_program_id] = row.study_program_name or ""
        if row.curriculum_course_id is not None:
            block.curriculum_course_ids.add(row.curriculum_course_id)
            if row.study_program_id is not None:
                block.curriculum_program_ids[row.curriculum_course_id] = row.study_program_id

    return list(blocks.values())





def _class_label(block: _Block) -> str:
    programs = "/".join(
        block.study_program_codes[program_id]
        for program_id in sorted(block.study_program_ids, key=str)
        if block.study_program_codes.get(program_id)
    )
    label = f"{block.course_code} {block.section_code}".strip()
    return f"{label} ({programs})" if programs else label


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
            shared_lecturers = first.lecturer_keys & second.lecturer_keys
            if shared_lecturers:
                lecturer_key = sorted(shared_lecturers)[0]
                conflicts.append(
                    build_conflict_item(
                        kind="lecturer",
                        class_section_a_id=first.class_section_id,
                        class_section_b_id=second.class_section_id,
                        object_id=UUID(lecturer_key),
                        object_name=first.lecturers[0] if first.lecturers else "",
                        class_section_a_label=_class_label(first),
                        class_section_b_label=_class_label(second),
                        day_of_week=shared[0],
                        start_hour=shared[1],
                        end_hour=shared[2],
                    )
                )
            if first.room_key and first.room_key == second.room_key:
                conflicts.append(
                    build_conflict_item(
                        kind="room",
                        class_section_a_id=first.class_section_id,
                        class_section_b_id=second.class_section_id,
                        object_id=first.room_id or first.room_key,
                        object_name=first.room_label or second.room_label,
                        class_section_a_label=_class_label(first),
                        class_section_b_label=_class_label(second),
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
    rows = (
        await db.execute(
            select(
                UnassignedClass.class_section_id.label("class_section_id"),
                UnassignedClass.reason.label("reason"),
                Course.course_code.label("course_code"),
            )
            .join(ScheduleRun, ScheduleRun.run_id == UnassignedClass.run_id)
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
            .where(
                ScheduleRun.academic_period_id == period_id,
                ScheduleRun.status == "completed",
            )
            .order_by(
                func.coalesce(ScheduleRun.ended_at, ScheduleRun.started_at).desc(),
                Course.course_code,
                ClassSection.section_code,
            )
        )
    ).all()
    entries: list[tuple[UUID, str, str]] = []
    seen: set[UUID] = set()
    for row in rows:
        if row.class_section_id in seen:
            continue
        seen.add(row.class_section_id)
        entries.append((row.class_section_id, row.course_code, row.reason))
    return await enrich_unassigned_items(db, period_id, entries)


def _block_run_status(
    block: _Block,
    global_run: ScheduleRun | None,
    global_revision: int,
    run_by_program: dict[UUID, ScheduleRun | None],
    revision_by_program: dict[UUID, int],
) -> tuple[ScheduleRun | None, int]:
    current_revision = max(
        [
            global_revision,
            *(
                revision_by_program.get(program_id, 0)
                for program_id in block.study_program_ids
            ),
        ]
    )
    candidates = [global_run] + [
        run_by_program.get(program_id) for program_id in block.study_program_ids
    ]
    runs = [run for run in candidates if run is not None]
    latest = max(
        runs,
        key=lambda run: (
            run.ended_at or run.started_at,
            str(run.run_id),
        ),
        default=None,
    )
    return latest, current_revision


async def _board_context(
    db: AsyncSession, period_id: str | None, user: User
) -> _BoardContext | JSONResponse:
    period = await _resolve_period(db, period_id)
    if period is None:
        return _deny(
            "period_not_found",
            "Periode akademik yang diminta tidak ditemukan.",
            NOT_FOUND,
        )

    program_ids = await all_study_program_ids(db)
    global_run = await latest_completed_run(db, period.academic_period_id)
    global_revision = await current_input_revision(db, period.academic_period_id)
    revision_by_program = {
        program_id: await current_input_revision(
            db, period.academic_period_id, program_id
        )
        for program_id in program_ids
    }
    run_by_program = {
        program_id: await latest_completed_run(
            db, period.academic_period_id, program_id
        )
        for program_id in program_ids
    }
    program_statuses, state_by_program = await _program_statuses(
        db,
        period.academic_period_id,
        run_by_program,
        revision_by_program,
    )
    blocks = await _blocks(db, period.academic_period_id, state_by_program)
    classes = []
    for block in blocks:
        run, current_revision = _block_run_status(
            block,
            global_run,
            global_revision,
            run_by_program,
            revision_by_program,
        )
        ordered_program_ids = sorted(
            block.study_program_ids,
            key=lambda program_id: (
                block.study_program_codes.get(program_id, ""),
                str(program_id),
            ),
        )
        class_programs = [
            BoardClassProgram(
                study_program_id=str(program_id),
                study_program_code=block.study_program_codes.get(program_id, ""),
                study_program_name=block.study_program_names.get(program_id, ""),
                state=state_by_program.get(program_id, "draft"),
                label=status_label(state_by_program.get(program_id, "draft")),
            )
            for program_id in ordered_program_ids
        ]
        states = {program.state for program in class_programs}
        state = next(iter(states)) if len(states) == 1 else ("mixed" if states else "draft")
        lead_program_id = block.curriculum_program_ids.get(
            block.assigned_curriculum_course_id or UUID(int=0)
        )
        if lead_program_id not in block.study_program_ids:
            lead_program_id = ordered_program_ids[0] if ordered_program_ids else block.study_program_id
        can_edit = _can_edit(user, block.study_program_ids)
        classes.append(
            BoardClassItem(
                class_section_id=str(block.class_section_id),
                section_code=block.section_code,
                course_code=block.course_code,
                course_name=block.course_name,
                course_id=str(block.course_id),
                credits=block.credits,
                face_to_face_minutes=block.credits * 50,
                study_program_id=str(lead_program_id) if lead_program_id else "",
                study_program_code=block.study_program_codes.get(lead_program_id, ""),
                study_program_name=block.study_program_names.get(lead_program_id, ""),
                program_ids=[str(program_id) for program_id in ordered_program_ids],
                programs=class_programs,
                day_of_week=block.day_of_week,
                start_hour=block.start_hour,
                end_hour=block.end_hour,
                room_id=str(block.room_id) if block.room_id else None,
                room_code=block.room_label or None,
                lecturers=block.lecturers,
                assigned_lecturer_id=(
                    str(block.assigned_lecturer_id)
                    if block.assigned_lecturer_id
                    else None
                ),
                assigned_lecturer_name=block.assigned_lecturer_name,
                assigned_curriculum_course_id=(
                    str(block.assigned_curriculum_course_id)
                    if block.assigned_curriculum_course_id
                    else None
                ),
                can_edit=can_edit,
                read_only=not can_edit,
                is_manually_edited=block.is_manually_edited,
                state=state,
                is_stale=run is None or run.input_revision != current_revision,
                run_id=str(run.run_id) if run is not None else None,
                input_revision=current_revision,
            )
        )
    return _BoardContext(
        period=period,
        classes=classes,
        conflicts=_conflicts(blocks),
        programs=program_statuses,
        unassigned=await _unassigned(db, period.academic_period_id),
    )


def _meta(context: _BoardContext, user: User) -> dict[str, Any]:
    actor_study_program_id = _actor_study_program_id(user)
    can_edit = user.role == "admin" or actor_study_program_id is not None
    return {
        "period_label": _period_label(context.period),
        "class_count": len(context.classes),
        "conflict_count": len(context.conflicts),
        "blocking_conflict_count": len(context.conflicts),
        "program_count": len(context.programs),
        "input_revision": max(
            [item.input_revision for item in context.classes]
            + [program.input_revision for program in context.programs],
            default=0,
        ),
        "stale_count": sum(1 for item in context.classes if item.is_stale),
        "unassigned_count": len(context.unassigned),
        "unmapped_room_count": sum(
            1 for item in context.classes if item.room_id is None
        ),
        "unmapped_lecturer_count": sum(
            1 for item in context.classes if not item.lecturers
        ),
        "empty_section_count": sum(
            1 for item in context.classes if item.day_of_week == 0
        ),
        "actor_study_program_id": actor_study_program_id,
        "can_edit": can_edit,
        "read_only": not can_edit,
    }


def _board_payload(response: BoardResponse) -> dict[str, Any]:
    return response.model_dump(mode="json")


@router.get("/scheduling/board", response_model=BoardResponse)
async def get_board(
    period_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    context = await _board_context(db, period_id, current_user)
    if isinstance(context, JSONResponse):
        return context
    response = BoardResponse(
        data=BoardData(
            academic_period_id=str(context.period.academic_period_id),
            period_label=_period_label(context.period),
            classes=context.classes,
            conflicts=context.conflicts,
            programs=context.programs,
            unassigned=context.unassigned,
        ),
        meta=_meta(context, current_user),
    )
    return JSONResponse(content=_board_payload(response))


@router.get("/scheduling/conflicts", response_model=ConflictListResponse)
async def get_conflicts(
    period_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    context = await _board_context(db, period_id, current_user)
    if isinstance(context, JSONResponse):
        return context
    return ConflictListResponse(data=context.conflicts, meta=_meta(context, current_user))
