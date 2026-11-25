"""Penjadwal Kelas MK lintas prodi.

Algoritmanya sengaja biasa: bangkitkan kandidat blok, isi secara greedy, lalu
perbaiki dengan backtracking terbatas. Tidak ada dependensi baru dan tidak ada
pengecualian untuk kasus yang tidak memungkinkan — kelas yang gagal menjadi
baris ``UnassignedClass`` beserta alasannya.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, time, timezone
from math import ceil
from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from section_codes import format_section_code, section_prefix
from audit import record_admin_action
from models import (
    AcademicPeriod,
    ClassCountOverride,
    ClassInstructorAssignment,
    ClassSchedule,
    ClassSection,
    Course,
    CourseInstructorReference,
    CourseOffering,
    CourseOfferingEligibility,
    Curriculum,
    CurriculumCourse,
    ElectiveCourseVote,
    ElectivePollingPeriod,
    LecturerProfile,
    LecturerSchedulePreference,
    OfferingComponent,
    Room,
    ScheduleEditLog,
    SchedulePeriodLock,
    SchedulePeriodSettings,
    ScheduleProgramStatus,
    ScheduleRun,
    StudentCourseRecord,
    StudentProfile,
    StudyProgram,
    TimetableItem,
    UnassignedClass,
    User,
)
from scheduling_common import (
    END_HOUR_MAX,
    START_HOUR_MIN,
    blocks_overlap,
    hour_end,
    is_valid_block,
)
from schemas import (
    CurriculumContextItem,
    GenerateResponse,
    StudyProgramIdentity,
    UnassignedItem,
)
from .conflicts import ConflictBlock, detect_conflicts

REASON_CAPACITY = "room_capacity"
REASON_LOCKED = "course_locked"
REASON_LECTURER = "no_valid_slot"
REASON_NO_ROOM = "no_room"
REASON_PARITY = "parity_mismatch"
REASON_MISSING_PJMK = "missing_pjmk"
REASON_EMPTY_POOL = "empty_pool"
REASON_MISSING_ASSIGNMENT = "missing_assignment"
REASON_INELIGIBLE_ASSIGNMENT = "ineligible_assignment"
REASON_PINNED_NO_SLOT = "pinned_no_slot"
REASON_MANUAL_NO_SLOT = "manual_no_slot"
REASON_POOL_EXHAUSTED = "pool_exhausted"
REASON_CURRICULUM_CONTEXT = "curriculum_context_required"
DEFAULT_SECTION_CAPACITY = 40
MAX_SEARCH_NODES = 30_000

REASON_LABELS = {
    REASON_CAPACITY: "kapasitas ruang",
    REASON_LOCKED: "mk terkunci",
    REASON_LECTURER: "dosen tidak tersedia",
    REASON_NO_ROOM: "tidak ada ruang milik prodi",
    REASON_PARITY: "paritas tidak sesuai",
    REASON_MISSING_PJMK: "PJ MK aktif belum lengkap",
    REASON_EMPTY_POOL: "Tim Pengajar belum tersedia",
    REASON_MISSING_ASSIGNMENT: "Assignment Pengajar belum tersedia",
    REASON_INELIGIBLE_ASSIGNMENT: "Assignment Pengajar tidak memenuhi syarat",
    REASON_PINNED_NO_SLOT: "Dosen yang di-pin tidak memiliki slot valid",
    REASON_MANUAL_NO_SLOT: "Dosen assignment manual tidak memiliki slot valid",
    REASON_POOL_EXHAUSTED: "Seluruh dosen dalam Tim Pengajar tidak memiliki slot valid",
    REASON_CURRICULUM_CONTEXT: "Konteks kurikulum kelas harus ditentukan",
}
LEGACY_REASON_CODES = {label: code for code, label in REASON_LABELS.items()}


def reason_code(value: str) -> str:
    if value in REASON_LABELS:
        return value
    return LEGACY_REASON_CODES.get(value, REASON_LECTURER)


def reason_label(value: str) -> str:
    return REASON_LABELS.get(reason_code(value), value)


@dataclass(frozen=True)
class CurriculumContext:
    class_section_id: UUID
    section_code: str
    curriculum_course_id: UUID
    curriculum_id: UUID
    study_program_id: UUID
    study_program_code: str
    study_program_name: str
    course_id: UUID
    course_code: str
    course_name: str


async def load_curriculum_contexts(
    db: AsyncSession,
    period_id: UUID,
    class_ids: set[UUID] | None = None,
) -> dict[UUID, list[CurriculumContext]]:
    stmt = (
        select(
            ClassSection.class_section_id,
            ClassSection.section_code,
            CurriculumCourse.curriculum_course_id,
            CurriculumCourse.curriculum_id,
            Curriculum.study_program_id,
            StudyProgram.program_code,
            StudyProgram.program_name,
            Course.course_id,
            Course.course_code,
            Course.course_name,
        )
        .select_from(ClassSection)
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
            CourseOfferingEligibility,
            CourseOfferingEligibility.course_offering_id
            == CourseOffering.course_offering_id,
        )
        .join(
            CurriculumCourse,
            CurriculumCourse.curriculum_course_id
            == CourseOfferingEligibility.curriculum_course_id,
        )
        .join(Curriculum, Curriculum.curriculum_id == CurriculumCourse.curriculum_id)
        .join(Course, Course.course_id == CourseOffering.course_id)
        .join(StudyProgram, StudyProgram.study_program_id == Curriculum.study_program_id)
        .where(CourseOffering.academic_period_id == period_id)
        .order_by(
            ClassSection.class_section_id,
            StudyProgram.program_code,
            CurriculumCourse.curriculum_course_id,
        )
    )
    if class_ids is not None:
        stmt = stmt.where(ClassSection.class_section_id.in_(class_ids))
    rows = (await db.execute(stmt)).all()
    contexts: dict[UUID, list[CurriculumContext]] = defaultdict(list)
    for row in rows:
        contexts[row.class_section_id].append(
            CurriculumContext(
                class_section_id=row.class_section_id,
                section_code=row.section_code,
                curriculum_course_id=row.curriculum_course_id,
                curriculum_id=row.curriculum_id,
                study_program_id=row.study_program_id,
                study_program_code=row.program_code,
                study_program_name=row.program_name,
                course_id=row.course_id,
                course_code=row.course_code,
                course_name=row.course_name,
            )
        )
    return contexts


def unassigned_action(reason: str, pjmk_reference_id: str | None) -> str:
    if reason in {"missing_assignment", "ineligible_assignment", REASON_CURRICULUM_CONTEXT}:
        return "open_assignment"
    if reason in {REASON_CAPACITY, REASON_NO_ROOM}:
        return "open_room_detail"
    if reason in {REASON_LOCKED, REASON_PARITY}:
        return "open_course_detail"
    return "edit_pjmk" if pjmk_reference_id else "open_pjmk_form"


async def enrich_unassigned_items(
    db: AsyncSession,
    period_id: UUID,
    entries: list[tuple[UUID, str, str]],
) -> list[UnassignedItem]:
    if not entries:
        return []
    class_ids = {class_section_id for class_section_id, _, _ in entries}
    contexts_by_class = await load_curriculum_contexts(db, period_id, class_ids)
    metadata_rows = (
        await db.execute(
            select(
                ClassSection.class_section_id,
                ClassSection.section_code,
                Course.course_id,
                Course.course_code,
                Course.course_name,
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
            .where(ClassSection.class_section_id.in_(class_ids))
        )
    ).all()
    metadata_by_class = {row.class_section_id: row for row in metadata_rows}
    curriculum_course_ids = {
        context.curriculum_course_id
        for contexts in contexts_by_class.values()
        for context in contexts
    }
    pjmk_by_context: dict[UUID, UUID] = {}
    if curriculum_course_ids:
        reference_rows = (
            await db.execute(
                select(
                    CourseInstructorReference.curriculum_course_id,
                    CourseInstructorReference.instructor_reference_id,
                )
                .where(
                    CourseInstructorReference.curriculum_course_id.in_(
                        curriculum_course_ids
                    ),
                    CourseInstructorReference.academic_period_id == period_id,
                    CourseInstructorReference.instructor_role == "pjmk",
                )
                .order_by(
                    CourseInstructorReference.curriculum_course_id,
                    CourseInstructorReference.instructor_reference_id,
                )
            )
        ).all()
        pjmk_by_context = {
            row.curriculum_course_id: row.instructor_reference_id
            for row in reference_rows
        }

    items: list[UnassignedItem] = []
    for class_section_id, course_code, reason in entries:
        code = reason_code(reason)
        contexts = contexts_by_class.get(class_section_id, [])
        context_items = [
            CurriculumContextItem(
                curriculum_course_id=str(context.curriculum_course_id),
                curriculum_id=str(context.curriculum_id),
                study_program_id=str(context.study_program_id),
                study_program_code=context.study_program_code,
                study_program_name=context.study_program_name,
                course_code=context.course_code,
                course_name=context.course_name,
                pjmk_reference_id=(
                    str(pjmk_by_context[context.curriculum_course_id])
                    if context.curriculum_course_id in pjmk_by_context
                    else None
                ),
            )
            for context in contexts
        ]
        programs_by_id = {
            context.study_program_id: StudyProgramIdentity(
                study_program_id=str(context.study_program_id),
                study_program_code=context.study_program_code,
                study_program_name=context.study_program_name,
            )
            for context in contexts
        }
        pjmk_reference_id = next(
            (item.pjmk_reference_id for item in context_items if item.pjmk_reference_id),
            None,
        )
        first = contexts[0] if contexts else None
        metadata = metadata_by_class.get(class_section_id)
        items.append(
            UnassignedItem(
                class_section_id=str(class_section_id),
                course_id=(
                    str(first.course_id)
                    if first
                    else str(metadata.course_id)
                    if metadata
                    else ""
                ),
                course_code=course_code
                or (first.course_code if first else metadata.course_code if metadata else ""),
                course_name=(
                    first.course_name
                    if first
                    else metadata.course_name
                    if metadata
                    else ""
                ),
                section_code=(
                    first.section_code
                    if first
                    else metadata.section_code
                    if metadata
                    else ""
                ),
                reason=reason_label(code),
                reason_code=code,
                programs=list(programs_by_id.values()),
                eligible_curriculum_contexts=context_items,
                action=unassigned_action(code, pjmk_reference_id),
                pjmk_reference_id=pjmk_reference_id,
            )
        )
    return items


def _schedule_snapshot(schedule: ClassSchedule) -> dict[str, object]:
    """Ringkasan blok yang dapat diaudit pada ScheduleEditLog."""
    return {
        "day_of_week": schedule.day_of_week,
        "start_hour": schedule.start_time.hour,
        "end_hour": schedule.end_time.hour,
        "end_time": schedule.end_time.strftime("%H:%M"),
        "room_id": str(schedule.room_id) if schedule.room_id else None,
        "room_code": schedule.room_name or None,
    }


def _assignment_snapshot(assignment: ClassInstructorAssignment) -> dict[str, object]:
    return {
        "assignment_id": str(assignment.assignment_id),
        "class_section_id": str(assignment.class_section_id),
        "academic_period_id": str(assignment.academic_period_id),
        "curriculum_course_id": (
            str(assignment.curriculum_course_id)
            if assignment.curriculum_course_id
            else None
        ),
        "user_id": str(assignment.user_id),
        "source": assignment.source,
        "is_pinned": assignment.is_pinned,
        "is_active": assignment.is_active,
        "assigned_by": str(assignment.assigned_by),
        "assigned_at": assignment.assigned_at.isoformat(),
    }


@dataclass(frozen=True)
class ClassTask:
    section_id: UUID
    course_code: str
    section_code: str
    credits: int
    capacity: int
    study_program_id: UUID | None
    lecturers: tuple[UUID, ...]
    curriculum_course_id: UUID | None = None
    source: str = "auto"
    is_pinned: bool = False
    blocked_reason: str | None = None

    @property
    def failure_reason(self) -> str:
        if self.is_pinned:
            return REASON_PINNED_NO_SLOT
        if self.source == "manual":
            return REASON_MANUAL_NO_SLOT
        return REASON_POOL_EXHAUSTED


@dataclass(frozen=True)
class RoomOption:
    room_id: UUID
    room_code: str
    capacity: int


@dataclass(frozen=True)
class Placement:
    day: int
    start: int
    end: int
    room: RoomOption
    lecturer_id: UUID
    preference_score: int = 0


@dataclass(frozen=True)
class Block:
    day: int
    start: int
    end: int
    room_id: UUID | None
    lecturers: frozenset[UUID]
    section_id: UUID


@dataclass
class SolveResult:
    assignments: dict[UUID, Placement]
    unassigned: list[tuple[UUID, str]]
    explored: int = 0
    preferred_matches: int = 0


@dataclass(frozen=True)
class _Preference:
    day: int
    start: int
    end: int
    kind: str


@dataclass(frozen=True)
class _Eligibility:
    course: CurriculumCourse
    program: StudyProgram


def _candidates(
    task: ClassTask,
    rooms_by_program: dict[UUID | None, tuple[RoomOption, ...]],
    preferences: dict[UUID, tuple[_Preference, ...]],
) -> tuple[list[Placement], str | None]:
    """Kandidat blok per dosen, dengan fallback dan skor preferensi biner."""
    rooms = rooms_by_program.get(task.study_program_id, ())
    if not rooms:
        return [], REASON_NO_ROOM

    fitting = [room for room in rooms if room.capacity >= task.capacity]
    if not fitting:
        return [], REASON_CAPACITY

    lecturer_order = {
        user_id: index for index, user_id in enumerate(task.lecturers)
    }
    placements: list[Placement] = []
    for user_id in task.lecturers:
        windows = preferences.get(user_id, ())
        unavailable = tuple(window for window in windows if window.kind == "unavailable")
        preferred = tuple(window for window in windows if window.kind == "preferred")
        for day in range(1, 6):
            for start in range(START_HOUR_MIN, END_HOUR_MAX - task.credits + 1):
                end = hour_end(start, task.credits)
                if any(
                    window.day == day
                    and window.start < end
                    and start < window.end
                    for window in unavailable
                ):
                    continue
                score = int(
                    any(
                        window.day == day
                        and window.start <= start
                        and end <= window.end
                        for window in preferred
                    )
                )
                for room in fitting:
                    placements.append(
                        Placement(day, start, end, room, user_id, score)
                    )
    placements.sort(
        key=lambda placement: (
            lecturer_order[placement.lecturer_id],
            -placement.preference_score,
            placement.day,
            placement.start,
            placement.room.room_code,
            str(placement.room.room_id),
        )
    )
    return placements, None if placements else REASON_LECTURER


def _collides(
    day: int,
    start: int,
    end: int,
    room_id: UUID,
    lecturers: tuple[UUID, ...],
    room_busy: dict[UUID, list[Block]],
    lecturer_busy: dict[UUID, list[Block]],
    *,
    timetable_ids: tuple[UUID, ...] = (),
    timetable_busy: dict[UUID, list[Block]] | None = None,
) -> bool:
    if any(
        block.day == day and blocks_overlap(start, end, block.start, block.end)
        for block in room_busy.get(room_id, ())
    ):
        return True
    if any(
        block.day == day and blocks_overlap(start, end, block.start, block.end)
        for user_id in lecturers
        for block in lecturer_busy.get(user_id, ())
    ):
        return True
    if timetable_busy:
        for timetable_id in timetable_ids:
            if any(
                block.day == day and blocks_overlap(start, end, block.start, block.end)
                for block in timetable_busy.get(timetable_id, ())
            ):
                return True
    return False


def solve(
    tasks: list[ClassTask],
    rooms_by_program: dict[UUID | None, tuple[RoomOption, ...]],
    preferences: dict[UUID, tuple[_Preference, ...]],
    occupied: tuple[Block, ...] = (),
    *,
    section_timetables: dict[UUID, tuple[UUID, ...]] | None = None,
    timetable_busy: dict[UUID, list[Block]] | None = None,
    max_nodes: int = MAX_SEARCH_NODES,
) -> SolveResult:
    """Greedy dengan backtracking; fallback dosen ikut dalam state pencarian."""
    section_timetables = section_timetables or {}
    if timetable_busy is None:
        timetable_busy = {}
    candidates: dict[UUID, list[Placement]] = {}
    reasons: dict[UUID, str] = {}
    pending: list[ClassTask] = []
    for task in tasks:
        if task.blocked_reason is not None:
            continue
        placements, reason = _candidates(task, rooms_by_program, preferences)
        candidates[task.section_id] = placements
        if reason is not None:
            reasons[task.section_id] = (
                task.failure_reason if reason == REASON_LECTURER else reason
            )
            continue
        pending.append(task)

    room_busy: dict[UUID, list[Block]] = defaultdict(list)
    lecturer_busy: dict[UUID, list[Block]] = defaultdict(list)
    for block in occupied:
        if block.room_id is not None:
            room_busy[block.room_id].append(block)
        for user_id in block.lecturers:
            lecturer_busy[user_id].append(block)

    order = sorted(
        pending,
        key=lambda task: (
            -max(
                (
                    placement.preference_score
                    for placement in candidates[task.section_id]
                    if placement.lecturer_id == task.lecturers[0]
                ),
                default=0,
            ),
            len(candidates[task.section_id]),
            -task.credits,
            task.course_code,
            task.section_code,
            str(task.section_id),
        ),
    )
    assigned: dict[UUID, Placement] = {}
    best: dict[UUID, Placement] = {}
    best_depth = -1
    explored = 0

    def place(task: ClassTask, placement: Placement) -> None:
        assigned[task.section_id] = placement
        block = Block(
            day=placement.day,
            start=placement.start,
            end=placement.end,
            room_id=placement.room.room_id,
            lecturers=frozenset((placement.lecturer_id,)),
            section_id=task.section_id,
        )
        room_busy[placement.room.room_id].append(block)
        lecturer_busy[placement.lecturer_id].append(block)
        for timetable_id in section_timetables.get(task.section_id, ()):
            timetable_busy.setdefault(timetable_id, []).append(block)

    def unplace(task: ClassTask, placement: Placement) -> None:
        del assigned[task.section_id]
        room_busy[placement.room.room_id].pop()
        lecturer_busy[placement.lecturer_id].pop()
        for timetable_id in section_timetables.get(task.section_id, ()):
            timetable_busy[timetable_id].pop()

    def search(depth: int) -> bool:
        nonlocal explored, best, best_depth
        if depth > best_depth:
            best = dict(assigned)
            best_depth = depth
        if depth == len(order):
            return True
        explored += 1
        if explored > max_nodes:
            return False

        task = order[depth]
        for placement in candidates[task.section_id]:
            if _collides(
                placement.day,
                placement.start,
                placement.end,
                placement.room.room_id,
                (placement.lecturer_id,),
                room_busy,
                lecturer_busy,
                timetable_ids=section_timetables.get(task.section_id, ()),
                timetable_busy=timetable_busy,
            ):
                continue
            place(task, placement)
            if search(depth + 1):
                return True
            unplace(task, placement)
        return False

    search(0)

    unassigned: list[tuple[UUID, str]] = [
        (task.section_id, task.blocked_reason or "")
        for task in tasks
        if task.blocked_reason is not None
    ]
    for task in tasks:
        if task.blocked_reason is not None or task.section_id in best:
            continue
        unassigned.append(
            (task.section_id, reasons.get(task.section_id, task.failure_reason))
        )

    return SolveResult(
        assignments=best,
        unassigned=unassigned,
        explored=explored,
        preferred_matches=sum(
            placement.preference_score for placement in best.values()
        ),
    )


def _parity_matches(course_term: str | None, period_term: str) -> bool:
    if not course_term or not course_term.strip():
        return True
    return course_term.strip().lower() == (period_term or "").strip().lower()


async def _period_section_ids(db: AsyncSession, period_id: UUID) -> list[UUID]:
    result = await db.execute(
        select(ClassSection.class_section_id)
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
    return list(result.scalars().all())


async def current_input_revision(
    db: AsyncSession, period_id: UUID, study_program_id: UUID | None = None
) -> int:
    stmt = select(SchedulePeriodSettings.input_revision).where(
        SchedulePeriodSettings.academic_period_id == period_id,
    )
    if study_program_id is not None:
        stmt = stmt.where(
            SchedulePeriodSettings.study_program_id == study_program_id,
        )
        revision = (await db.execute(stmt)).scalar_one_or_none()
        if revision is not None:
            return revision
        stmt = select(SchedulePeriodSettings.input_revision).where(
            SchedulePeriodSettings.academic_period_id == period_id,
            SchedulePeriodSettings.study_program_id.is_(None),
        )
    revisions = (await db.execute(stmt)).scalars().all()
    return max(revisions, default=0)


async def bump_input_revisions(
    db: AsyncSession,
    period_id: UUID,
    study_program_ids: set[UUID] | None,
) -> None:
    if study_program_ids is not None and not study_program_ids:
        return
    await db.execute(
        select(AcademicPeriod.academic_period_id)
        .where(AcademicPeriod.academic_period_id == period_id)
        .with_for_update()
    )
    rows = (
        await db.execute(
            select(SchedulePeriodSettings)
            .where(SchedulePeriodSettings.academic_period_id == period_id)
            .with_for_update()
        )
    ).scalars().all()
    existing = {row.study_program_id: row for row in rows}
    if study_program_ids is None:
        next_revision = max((row.input_revision for row in rows), default=0) + 1
        for row in rows:
            row.input_revision = next_revision
        if existing.get(None) is None:
            db.add(
                SchedulePeriodSettings(
                    academic_period_id=period_id,
                    study_program_id=None,
                    input_revision=next_revision,
                )
            )
        return
    for program_id in study_program_ids:
        settings = existing.get(program_id)
        if settings is None:
            db.add(
                SchedulePeriodSettings(
                    academic_period_id=period_id,
                    study_program_id=program_id,
                    input_revision=1,
                )
            )
        else:
            settings.input_revision += 1


async def scheduling_input_lock(
    db: AsyncSession,
    period_id: UUID,
    study_program_ids: set[UUID] | None = None,
) -> tuple[str, str] | None:
    lock = await db.get(SchedulePeriodLock, period_id)
    if lock is not None and lock.krs_open:
        return (
            "krs_open",
            "KRS sudah dibuka; input jadwal tidak dapat diubah sebelum kunci dibuka admin.",
        )
    stmt = select(ScheduleProgramStatus.study_program_id).where(
        ScheduleProgramStatus.academic_period_id == period_id,
        ScheduleProgramStatus.state == "final",
    )
    if study_program_ids is not None:
        if not study_program_ids:
            return None
        stmt = stmt.where(
            ScheduleProgramStatus.study_program_id.in_(study_program_ids)
        )
    if (await db.execute(stmt.limit(1))).first() is not None:
        return (
            "schedule_final",
            "Jadwal sudah final; perubahan memerlukan pembukaan kunci oleh admin.",
        )
    return None


async def latest_completed_run(
    db: AsyncSession, period_id: UUID, study_program_id: UUID | None = None
) -> ScheduleRun | None:
    stmt = select(ScheduleRun).where(
        ScheduleRun.academic_period_id == period_id,
        ScheduleRun.status == "completed",
        or_(
            ScheduleRun.study_program_id.is_(None),
            ScheduleRun.study_program_id == study_program_id,
        ),
    )
    if study_program_id is None:
        stmt = stmt.where(ScheduleRun.study_program_id.is_(None))
    return (
        await db.execute(
            stmt.order_by(
                func.coalesce(ScheduleRun.ended_at, ScheduleRun.started_at).desc(),
                ScheduleRun.run_id.desc(),
            ).limit(1)
        )
    ).scalars().first()


async def _demand_class_counts(
    db: AsyncSession,
    period: AcademicPeriod,
    eligible_by_offering: dict[UUID, list[_Eligibility]],
    course_by_offering: dict[UUID, Course],
    study_program_id: UUID | None = None,
) -> dict[tuple[UUID, UUID], int]:
    """Hitung Kelas MK yang dibutuhkan dari peminat; kuota 40 per kelas."""
    codes_by_target: dict[tuple[UUID, UUID], set[str]] = defaultdict(set)
    failed_ids_by_target: dict[tuple[UUID, UUID], set[UUID]] = defaultdict(set)
    mandatory_targets: set[tuple[UUID, UUID]] = set()
    program_ids: set[UUID] = set()
    for offering_id, rows in eligible_by_offering.items():
        course = course_by_offering.get(offering_id)
        if course is None:
            continue
        for row in rows:
            if (
                study_program_id is not None
                and row.program.study_program_id != study_program_id
            ):
                continue
            if not row.course.is_active or not _parity_matches(row.course.term, period.term):
                continue
            course_type = (row.course.course_type or "").strip().lower()
            target = (course.course_id, row.program.study_program_id)
            if course_type in {"pilihan", "pilihan_terbatas"}:
                codes_by_target[target].add(course.course_code)
            elif course_type == "wajib":
                failed_ids_by_target[target].add(row.course.curriculum_course_id)
                mandatory_targets.add(target)
                program_ids.add(row.program.study_program_id)
            else:
                continue

    codes = {code for values in codes_by_target.values() for code in values}
    votes_by_code: dict[str, int] = {}
    if codes:
        polling_period = (
            await db.execute(
                select(ElectivePollingPeriod)
                .where(ElectivePollingPeriod.status == "open")
                .order_by(ElectivePollingPeriod.created_at.desc())
                .limit(1)
            )
        ).scalars().first()
        if polling_period is None:
            polling_period = (
                await db.execute(
                    select(ElectivePollingPeriod)
                    .order_by(ElectivePollingPeriod.created_at.desc())
                    .limit(1)
                )
            ).scalars().first()
        if polling_period is not None:
            vote_rows = (
                await db.execute(
                    select(
                        ElectiveCourseVote.course_code,
                        func.count(ElectiveCourseVote.vote_id),
                    )
                    .where(
                        ElectiveCourseVote.polling_period_id
                        == polling_period.polling_period_id,
                        ElectiveCourseVote.course_code.in_(codes),
                    )
                    .group_by(ElectiveCourseVote.course_code)
                )
            ).all()
            votes_by_code = {code: count for code, count in vote_rows}

    failed_ids = {
        course_id for values in failed_ids_by_target.values() for course_id in values
    }
    failed_by_course: dict[UUID, int] = {}
    if failed_ids:
        failed_rows = (
            await db.execute(
                select(
                    StudentCourseRecord.curriculum_course_id,
                    func.count(StudentCourseRecord.student_course_record_id),
                )
                .where(
                    StudentCourseRecord.curriculum_course_id.in_(failed_ids),
                    StudentCourseRecord.record_status == "failed",
                )
                .group_by(StudentCourseRecord.curriculum_course_id)
            )
        ).all()
        failed_by_course = {course_id: count for course_id, count in failed_rows}

    students_by_program: dict[UUID, int] = {}
    if program_ids:
        student_rows = (
            await db.execute(
                select(
                    StudentProfile.study_program_id,
                    func.count(StudentProfile.user_id),
                )
                .join(User, User.user_id == StudentProfile.user_id)
                .where(
                    StudentProfile.study_program_id.in_(program_ids),
                    User.is_active.is_(True),
                )
                .group_by(StudentProfile.study_program_id)
            )
        ).all()
        students_by_program = {program_id: count for program_id, count in student_rows}

    counts: dict[tuple[UUID, UUID], int] = {}
    for target in set(codes_by_target) | set(failed_ids_by_target):
        expected = sum(votes_by_code.get(code, 0) for code in codes_by_target[target])
        expected += sum(
            failed_by_course.get(course_id, 0)
            for course_id in failed_ids_by_target[target]
        )
        if target in mandatory_targets:
            expected += students_by_program.get(target[1], 0)
        counts[target] = min(max(ceil(expected / DEFAULT_SECTION_CAPACITY), 1), 3)
    return counts


async def _create_override_sections(
    db: AsyncSession,
    period: AcademicPeriod,
    eligible_by_offering: dict[UUID, list[_Eligibility]],
    components: dict[UUID, list[OfferingComponent]],
    demand_counts: dict[tuple[UUID, UUID], int] | None = None,
    study_program_id: UUID | None = None,
) -> int:
    """Buat Kelas MK tambahan sesuai override atau kebutuhan peminat."""
    class_counts: dict[tuple[UUID, UUID], int] = dict(demand_counts or {})
    if study_program_id is not None:
        class_counts = {
            target: count
            for target, count in class_counts.items()
            if target[1] == study_program_id
        }
    overrides = (
        await db.execute(
            select(ClassCountOverride).where(
                ClassCountOverride.academic_period_id == period.academic_period_id
            )
        )
    ).scalars().all()
    if study_program_id is not None:
        overrides = [
            row
            for row in overrides
            if row.study_program_id == study_program_id
        ]
    for override in overrides:
        class_counts[(override.course_id, override.study_program_id)] = min(
            max(override.class_count, 1), 3
        )
    if not class_counts:
        return 0

    created = 0
    for (course_id, program_id), target_count in class_counts.items():
        matching_offering: UUID | None = None
        has_active_eligibility = False
        for offering_id, rows in eligible_by_offering.items():
            matched = [
                row
                for row in rows
                if row.course.course_id == course_id
                and row.program.study_program_id == program_id
            ]
            if not matched:
                continue
            if matching_offering is None:
                matching_offering = offering_id
            if any(row.course.is_active for row in matched):
                has_active_eligibility = True
                break
        if matching_offering is None or not has_active_eligibility:
            continue
        component = next(iter(components.get(matching_offering, ())), None)
        if component is None:
            continue

        existing_codes = set(
            (
                await db.execute(
                    select(ClassSection.section_code).where(
                        ClassSection.offering_component_id
                        == component.offering_component_id
                    )
                )
            ).scalars().all()
        )
        needed = target_count - len(existing_codes)
        if needed <= 0:
            continue
        eligibility_rows = eligible_by_offering[matching_offering]
        prefix = section_prefix(
            {row.program.program_code for row in eligibility_rows},
            {row.course.course_scope for row in eligibility_rows},
        )
        ordinal = len(existing_codes) + 1
        for _ in range(needed):
            section_code = format_section_code(prefix, ordinal)
            db.add(
                ClassSection(
                    offering_component_id=component.offering_component_id,
                    section_code=section_code,
                    capacity=DEFAULT_SECTION_CAPACITY,
                    enrollment_status="open",
                )
            )
            existing_codes.add(section_code)
            created += 1
            ordinal += 1
    if created:
        await db.flush()
    return created


async def generate_schedule(
    db: AsyncSession,
    period: AcademicPeriod,
    *,
    mode: str,
    triggered_by: UUID,
    study_program_id: UUID | None = None,
) -> GenerateResponse:
    """Buat satu blok per kelas dan simpan hasil serta diagnosisnya."""
    run = ScheduleRun(
        academic_period_id=period.academic_period_id,
        study_program_id=study_program_id,
        mode=mode,
        input_revision=await current_input_revision(
            db, period.academic_period_id, study_program_id
        ),
        triggered_by=triggered_by,
        status="running",
        stats={},
    )
    db.add(run)
    await db.flush()
    protected_schedule_ids: set[UUID] = set()
    if mode == "full_reset":
        section_ids = await _period_section_ids(db, period.academic_period_id)
        if section_ids:
            timetabled = (
                select(TimetableItem.timetable_item_id)
                .where(TimetableItem.class_section_id == ClassSchedule.class_section_id)
                .exists()
                .label("has_timetable_item")
            )
            existing = (
                await db.execute(
                    select(ClassSchedule, timetabled).where(
                        ClassSchedule.class_section_id.in_(section_ids)
                    )
                )
            ).all()
            removed_ids: list[UUID] = []
            for row in existing:
                schedule = row.ClassSchedule
                if row.has_timetable_item:
                    protected_schedule_ids.add(schedule.class_schedule_id)
                    continue
                removed_ids.append(schedule.class_schedule_id)
                db.add(
                    ScheduleEditLog(
                        class_section_id=schedule.class_section_id,
                        changed_by=triggered_by,
                        reason="full_reset",
                        is_manual_edit=False,
                        before_state=_schedule_snapshot(schedule),
                        after_state=None,
                    )
                )
            if removed_ids:
                await db.execute(
                    delete(ClassSchedule).where(
                        ClassSchedule.class_schedule_id.in_(removed_ids)
                    )
                )
            await db.flush()

    offering_rows = (
        await db.execute(
            select(CourseOffering, Course)
            .join(Course, Course.course_id == CourseOffering.course_id)
            .where(
                CourseOffering.academic_period_id == period.academic_period_id,
                Course.is_active.is_(True),
            )
            .order_by(Course.course_code, CourseOffering.offering_code)
        )
    ).all()
    offering_ids = [offering.course_offering_id for offering, _ in offering_rows]
    course_by_offering = {
        offering.course_offering_id: course for offering, course in offering_rows
    }

    eligible_by_offering: dict[UUID, list[_Eligibility]] = defaultdict(list)
    program_ids_by_offering: dict[UUID, set[UUID]] = defaultdict(set)
    program_codes_by_id: dict[UUID, str] = {}
    if offering_ids:
        eligibility_rows = (
            await db.execute(
                select(
                    CourseOfferingEligibility,
                    CurriculumCourse,
                    Curriculum,
                    StudyProgram,
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
                .where(
                    CourseOfferingEligibility.course_offering_id.in_(offering_ids)
                )
                .order_by(
                    StudyProgram.program_code,
                    CurriculumCourse.curriculum_course_id,
                )
            )
        ).all()
        for mapping, course, curriculum, program in eligibility_rows:
            eligible_by_offering[mapping.course_offering_id].append(
                _Eligibility(course=course, program=program)
            )
            program_ids_by_offering[mapping.course_offering_id].add(
                program.study_program_id
            )
            program_codes_by_id[program.study_program_id] = program.program_code

    curriculum_course_ids = sorted(
        {
            row.course.curriculum_course_id
            for rows in eligible_by_offering.values()
            for row in rows
        }
    )
    pools_by_course: dict[UUID, tuple[UUID, ...]] = {}
    pjmk_counts: dict[UUID, int] = defaultdict(int)
    has_pool_reference: dict[UUID, bool] = defaultdict(bool)
    if curriculum_course_ids:
        reference_rows = (
            await db.execute(
                select(
                    CourseInstructorReference.curriculum_course_id,
                    CourseInstructorReference.instructor_role,
                    CourseInstructorReference.position,
                    CourseInstructorReference.instructor_reference_id,
                    User.user_id,
                    User.role,
                    User.is_active,
                    LecturerProfile.user_id.label("profile_user_id"),
                )
                .outerjoin(
                    User, User.user_id == CourseInstructorReference.user_id
                )
                .outerjoin(
                    LecturerProfile, LecturerProfile.user_id == User.user_id
                )
                .where(
                    CourseInstructorReference.curriculum_course_id.in_(
                        curriculum_course_ids
                    ),
                    CourseInstructorReference.academic_period_id
                    == period.academic_period_id,
                    CourseInstructorReference.instructor_role.in_(
                        ("pjmk", "teaching_team")
                    ),
                )
                .order_by(
                    CourseInstructorReference.curriculum_course_id,
                    CourseInstructorReference.instructor_role != "pjmk",
                    CourseInstructorReference.position.is_(None),
                    CourseInstructorReference.position,
                    CourseInstructorReference.instructor_reference_id,
                )
            )
        ).all()
        pool_rows: dict[UUID, list[UUID]] = defaultdict(list)
        seen: dict[UUID, set[UUID]] = defaultdict(set)
        for row in reference_rows:
            course_id = row.curriculum_course_id
            has_pool_reference[course_id] = True
            eligible = (
                row.user_id is not None
                and row.role == "lecturer"
                and row.is_active
                and row.profile_user_id is not None
            )
            if not eligible:
                continue
            if row.instructor_role == "pjmk":
                pjmk_counts[course_id] += 1
            if row.user_id not in seen[course_id]:
                seen[course_id].add(row.user_id)
                pool_rows[course_id].append(row.user_id)
        pools_by_course = {
            course_id: tuple(users) for course_id, users in pool_rows.items()
        }

    components_by_offering: dict[UUID, list[OfferingComponent]] = defaultdict(list)
    offering_by_component: dict[UUID, UUID] = {}
    if offering_ids:
        components = (
            await db.execute(
                select(OfferingComponent)
                .where(OfferingComponent.course_offering_id.in_(offering_ids))
                .order_by(OfferingComponent.component_code)
            )
        ).scalars().all()
        for component in components:
            components_by_offering[component.course_offering_id].append(component)
            offering_by_component[component.offering_component_id] = (
                component.course_offering_id
            )

    demand_counts = await _demand_class_counts(
        db,
        period,
        eligible_by_offering,
        course_by_offering,
        study_program_id,
    )
    created_sections = await _create_override_sections(
        db,
        period,
        eligible_by_offering,
        components_by_offering,
        demand_counts,
        study_program_id,
    )

    sections: list[ClassSection] = []
    if offering_by_component:
        sections = (
            await db.execute(
                select(ClassSection)
                .where(
                    ClassSection.offering_component_id.in_(list(offering_by_component))
                )
                .order_by(ClassSection.section_code)
            )
        ).scalars().all()

    rooms_by_program: dict[UUID | None, tuple[RoomOption, ...]] = {}
    room_rows: dict[UUID | None, list[RoomOption]] = defaultdict(list)
    rooms = (
        await db.execute(
            select(Room).where(Room.is_active.is_(True)).order_by(Room.room_code)
        )
    ).scalars().all()
    for room in rooms:
        room_rows[room.owner_study_program_id].append(
            RoomOption(room.room_id, room.room_code, room.capacity)
        )
    shared_rooms = room_rows.pop(None, [])
    room_codes = {room.room_id: room.room_code for room in rooms}

    section_ids = [section.class_section_id for section in sections]
    assignments_by_section: dict[UUID, ClassInstructorAssignment] = {}
    if section_ids:
        assignment_rows = (
            await db.execute(
                select(ClassInstructorAssignment)
                .where(
                    ClassInstructorAssignment.class_section_id.in_(section_ids),
                    ClassInstructorAssignment.academic_period_id
                    == period.academic_period_id,
                    ClassInstructorAssignment.is_active.is_(True),
                )
                .order_by(ClassInstructorAssignment.class_section_id)
                .with_for_update()
            )
        ).scalars().all()
        assignments_by_section = {
            assignment.class_section_id: assignment
            for assignment in assignment_rows
        }

    lecturer_ids = {
        user_id for pool in pools_by_course.values() for user_id in pool
    }
    lecturer_names = dict(
        (
            await db.execute(
                select(User.user_id, User.full_name).where(
                    User.user_id.in_(lecturer_ids)
                )
            )
        ).all()
    )
    preferences_by_user: dict[UUID, tuple[_Preference, ...]] = {}
    if lecturer_ids:
        preference_rows = (
            await db.execute(
                select(LecturerSchedulePreference).where(
                    LecturerSchedulePreference.academic_period_id
                    == period.academic_period_id,
                    LecturerSchedulePreference.user_id.in_(lecturer_ids),
                )
            )
        ).scalars().all()
        windows_by_user: dict[UUID, list[_Preference]] = defaultdict(list)
        for window in preference_rows:
            windows_by_user[window.user_id].append(
                _Preference(
                    window.day_of_week,
                    window.start_time.hour,
                    window.end_time.hour,
                    window.kind,
                )
            )
        preferences_by_user = {
            user_id: tuple(windows)
            for user_id, windows in windows_by_user.items()
        }

    tasks: list[ClassTask] = []
    task_by_section: dict[UUID, ClassTask] = {}
    for section in sections:
        offering_id = offering_by_component[section.offering_component_id]
        course = course_by_offering[offering_id]
        eligibilities = eligible_by_offering.get(offering_id, [])
        matching = [
            row
            for row in eligibilities
            if row.course.is_active
            and _parity_matches(row.course.term, period.term)
        ]
        assignment = assignments_by_section.get(section.class_section_id)
        selected: _Eligibility | None = None
        credits = matching[0].course.credits_total if matching else 0
        lecturers: tuple[UUID, ...] = ()
        source = "auto"
        is_pinned = False
        blocked_reason: str | None = None
        if len(matching) > 1:
            if assignment is None or assignment.curriculum_course_id is None:
                blocked_reason = REASON_CURRICULUM_CONTEXT
            else:
                selected = next(
                    (
                        row
                        for row in matching
                        if row.course.curriculum_course_id
                        == assignment.curriculum_course_id
                    ),
                    None,
                )
                if selected is None:
                    blocked_reason = REASON_INELIGIBLE_ASSIGNMENT
        elif matching:
            selected = matching[0]
            if (
                assignment is not None
                and assignment.curriculum_course_id is not None
                and assignment.curriculum_course_id
                != selected.course.curriculum_course_id
            ):
                blocked_reason = REASON_INELIGIBLE_ASSIGNMENT
        elif eligibilities and all(not row.course.is_active for row in eligibilities):
            blocked_reason = REASON_LOCKED
        else:
            blocked_reason = REASON_NO_ROOM if not eligibilities else REASON_PARITY

        if selected is not None:
            credits = selected.course.credits_total
        if blocked_reason is None and selected is not None:
            if not is_valid_block(START_HOUR_MIN, credits):
                blocked_reason = REASON_PARITY
            else:
                pool_list: list[UUID] = []
                seen_users: set[UUID] = set()
                for row in matching:
                    for user_id in pools_by_course.get(row.course.curriculum_course_id, ()):
                        if user_id not in seen_users:
                            seen_users.add(user_id)
                            pool_list.append(user_id)
                pool = tuple(pool_list)
                matching_course_ids = {
                    row.course.curriculum_course_id for row in matching
                }
                if not any(has_pool_reference[course_id] for course_id in matching_course_ids):
                    blocked_reason = REASON_EMPTY_POOL
                elif any(pjmk_counts[course_id] != 1 for course_id in matching_course_ids):
                    blocked_reason = REASON_MISSING_PJMK
                elif not pool:
                    blocked_reason = REASON_EMPTY_POOL
                elif assignment is None:
                    blocked_reason = REASON_MISSING_ASSIGNMENT
                elif assignment.user_id not in pool:
                    blocked_reason = REASON_INELIGIBLE_ASSIGNMENT
                else:
                    source = assignment.source
                    is_pinned = assignment.is_pinned
                    can_fallback = source == "auto" and not is_pinned
                    lecturers = (assignment.user_id,) + (
                        tuple(user_id for user_id in pool if user_id != assignment.user_id)
                        if can_fallback
                        else ()
                    )

        task = ClassTask(
            section_id=section.class_section_id,
            course_code=course.course_code,
            section_code=section.section_code,
            credits=credits,
            capacity=section.capacity or DEFAULT_SECTION_CAPACITY,
            study_program_id=(
                selected.program.study_program_id if selected is not None else None
            ),
            lecturers=lecturers,
            curriculum_course_id=(
                selected.course.curriculum_course_id if selected is not None else None
            ),
            source=source,
            is_pinned=is_pinned,
            blocked_reason=blocked_reason,
        )
        tasks.append(task)
        task_by_section[task.section_id] = task
    class_labels = {
        task.section_id: (
            f"{task.course_code} {task.section_code} "
            f"({program_codes_by_id.get(task.study_program_id, '')})"
        ).rstrip(" ()")
        for task in tasks
    }
    section_program_ids = {
        section.class_section_id: program_ids_by_offering.get(
            offering_by_component[section.offering_component_id], set()
        )
        for section in sections
    }
    final_program_ids = set(
        (
            await db.execute(
                select(ScheduleProgramStatus.study_program_id).where(
                    ScheduleProgramStatus.academic_period_id
                    == period.academic_period_id,
                    ScheduleProgramStatus.state == "final",
                )
            )
        ).scalars().all()
    )
    final_section_ids = {
        section_id
        for section_id, program_ids in section_program_ids.items()
        if program_ids & final_program_ids
    }
    manual_section_ids = set(
        (
            await db.execute(
                select(ScheduleEditLog.class_section_id).where(
                    ScheduleEditLog.class_section_id.in_(section_ids),
                    ScheduleEditLog.is_manual_edit.is_(True),
                    ScheduleEditLog.before_state.has_key("day_of_week"),
                )
            )
        ).scalars().all()
    )
    target_section_ids = {
        section_id
        for section_id, program_ids in section_program_ids.items()
        if (
            study_program_id is None
            or study_program_id in program_ids
        )
        and section_id not in final_section_ids
    }
    if mode == "full_reset":
        target_section_ids = set(section_ids)
    preserved_final_sections: set[UUID] = set()
    preserved_manual_sections: set[UUID] = set()
    program_ids = {task.study_program_id for task in tasks} | set(room_rows)
    rooms_by_program = {
        program_id: tuple(room_rows.get(program_id, []) + shared_rooms)
        for program_id in program_ids
    }

    occupied: list[Block] = []
    filled: set[UUID] = set()
    repair_ids: set[UUID] = set()
    normalized = False
    if sections:
        timetabled = (
            select(TimetableItem.timetable_item_id)
            .where(TimetableItem.class_section_id == ClassSchedule.class_section_id)
            .exists()
            .label("has_timetable_item")
        )
        existing_schedules = (
            await db.execute(
                select(ClassSchedule, timetabled)
                .where(
                    ClassSchedule.class_section_id.in_(
                        [section.class_section_id for section in sections]
                    )
                )
                .order_by(ClassSchedule.day_of_week, ClassSchedule.start_time)
            )
        ).all()
        for row in existing_schedules:
            schedule = row.ClassSchedule
            section_id = schedule.class_section_id
            program_ids = section_program_ids.get(section_id, set())
            in_scope = study_program_id is None or study_program_id in program_ids
            is_final = section_id in final_section_ids
            is_manual = section_id in manual_section_ids
            preserve_final = mode != "full_reset" and is_final
            preserve_manual = mode == "regenerate" and is_manual
            preserve_scope = mode != "full_reset" and not in_scope
            task = task_by_section.get(section_id)
            if preserve_final or preserve_manual or preserve_scope:
                if preserve_final:
                    preserved_final_sections.add(section_id)
                if preserve_manual:
                    preserved_manual_sections.add(section_id)
                filled.add(section_id)
                occupied.append(
                    Block(
                        day=schedule.day_of_week,
                        start=schedule.start_time.hour,
                        end=schedule.end_time.hour
                        + (1 if schedule.end_time.minute else 0),
                        room_id=schedule.room_id,
                        lecturers=(
                            frozenset((task.lecturers[0],))
                            if task and task.lecturers
                            else frozenset()
                        ),
                        section_id=section_id,
                    )
                )
                continue
            if mode == "regenerate":
                db.add(
                    ScheduleEditLog(
                        class_section_id=section_id,
                        changed_by=triggered_by,
                        reason="regenerate",
                        is_manual_edit=False,
                        before_state=_schedule_snapshot(schedule),
                        after_state=None,
                    )
                )
                await db.delete(schedule)
                continue
            if mode == "full_reset":
                if row.has_timetable_item:
                    protected_schedule_ids.add(schedule.class_schedule_id)
                else:
                    db.add(
                        ScheduleEditLog(
                            class_section_id=section_id,
                            changed_by=triggered_by,
                            reason="full_reset",
                            is_manual_edit=False,
                            before_state=_schedule_snapshot(schedule),
                            after_state=None,
                        )
                    )
                    await db.delete(schedule)
                    continue
            if (
                mode == "fill_empty"
                and in_scope
                and schedule.room_id is None
                and not (schedule.room_name or "").strip()
                and not row.has_timetable_item
            ):
                repair_ids.add(section_id)
                db.add(
                    ScheduleEditLog(
                        class_section_id=section_id,
                        changed_by=triggered_by,
                        reason="perbaikan jadwal tanpa ruang maupun nama ruang",
                        is_manual_edit=False,
                        before_state=_schedule_snapshot(schedule),
                        after_state=None,
                    )
                )
                await db.delete(schedule)
                continue
            filled.add(section_id)
            credits = task.credits if task is not None else 0
            if is_valid_block(schedule.start_time.hour, credits):
                end = hour_end(schedule.start_time.hour, credits)
            else:
                end = schedule.end_time.hour + (1 if schedule.end_time.minute else 0)
                end = max(schedule.start_time.hour + 1, min(end, 23))
            normalized_end = time(hour=end)
            if schedule.end_time != normalized_end:
                before_state = _schedule_snapshot(schedule)
                schedule.end_time = normalized_end
                normalized = True
                db.add(
                    ScheduleEditLog(
                        class_section_id=section_id,
                        changed_by=triggered_by,
                        reason="normalisasi blok",
                        is_manual_edit=False,
                        before_state=before_state,
                        after_state=_schedule_snapshot(schedule),
                    )
                )
            occupied.append(
                Block(
                    day=schedule.day_of_week,
                    start=schedule.start_time.hour,
                    end=end,
                    room_id=schedule.room_id,
                    lecturers=(
                        frozenset((task.lecturers[0],))
                        if task and task.lecturers
                        else frozenset()
                    ),
                    section_id=section_id,
                )
            )
    if normalized or repair_ids:
        await db.flush()

    timetable_rows = (
        await db.execute(
            select(TimetableItem.class_section_id, TimetableItem.timetable_id)
        )
    ).all()
    timetables_by_section: dict[UUID, list[UUID]] = defaultdict(list)
    for section_id, timetable_id in timetable_rows:
        timetables_by_section[section_id].append(timetable_id)
    section_timetables = {
        section_id: tuple(timetable_ids)
        for section_id, timetable_ids in timetables_by_section.items()
    }
    timetable_busy: dict[UUID, list[Block]] = defaultdict(list)
    for block in occupied:
        for timetable_id in section_timetables.get(block.section_id, ()):
            timetable_busy[timetable_id].append(block)

    result = solve(
        [
            task
            for task in tasks
            if task.section_id not in filled
            and task.section_id in target_section_ids
        ],
        rooms_by_program,
        preferences_by_user,
        tuple(occupied),
        section_timetables=section_timetables,
        timetable_busy=timetable_busy,
    )

    new_blocks: list[Block] = []
    fallback_assignments = 0
    fallback_program_ids: set[UUID] = set()
    actor = await db.get(User, triggered_by)
    now = datetime.now(timezone.utc)
    for section_id, placement in result.assignments.items():
        task = task_by_section[section_id]
        if placement.lecturer_id != task.lecturers[0]:
            assignment = assignments_by_section[section_id]
            before = _assignment_snapshot(assignment)
            assignment.user_id = placement.lecturer_id
            assignment.assigned_by = triggered_by
            assignment.assigned_at = now
            await db.flush()
            if actor is not None:
                await record_admin_action(
                    db,
                    actor=actor,
                    target=actor,
                    action="class_instructor_assignment_solver_fallback",
                    reason=(
                        f"class_section_id={section_id} "
                        f"academic_period_id={period.academic_period_id}"
                    ),
                    field_name=str(section_id),
                    old_value=json.dumps(before, sort_keys=True, default=str),
                    new_value=json.dumps(
                        _assignment_snapshot(assignment), sort_keys=True, default=str
                    ),
                )
            fallback_assignments += 1
            fallback_program_ids.update(
                section_program_ids.get(section_id, set())
            )
        schedule = ClassSchedule(
            class_section_id=section_id,
            day_of_week=placement.day,
            start_time=time(hour=placement.start),
            end_time=time(hour=placement.end),
            room_id=placement.room.room_id,
            room_name=placement.room.room_code,
        )
        db.add(schedule)
        db.add(
            ScheduleEditLog(
                class_section_id=section_id,
                changed_by=triggered_by,
                reason="regenerate" if mode == "regenerate" else "generate",
                is_manual_edit=False,
                before_state=None,
                after_state=_schedule_snapshot(schedule),
            )
        )
        new_blocks.append(
            Block(
                day=placement.day,
                start=placement.start,
                end=placement.end,
                room_id=placement.room.room_id,
                lecturers=frozenset((placement.lecturer_id,)),
                section_id=section_id,
            )
        )
    if fallback_program_ids:
        await bump_input_revisions(
            db, period.academic_period_id, fallback_program_ids
        )
        run.input_revision = await current_input_revision(
            db, period.academic_period_id, study_program_id
        )

    unassigned_entries: list[tuple[UUID, str, str]] = []
    for section_id, reason in result.unassigned:
        code = reason_code(reason)
        db.add(
            UnassignedClass(
                run_id=run.run_id,
                class_section_id=section_id,
                reason=code,
            )
        )
        task = task_by_section.get(section_id)
        unassigned_entries.append(
            (section_id, task.course_code if task else "", code)
        )
    unassigned_items = await enrich_unassigned_items(
        db, period.academic_period_id, unassigned_entries
    )

    conflicts = detect_conflicts(
        [
            ConflictBlock(
                section_id=block.section_id,
                day=block.day,
                start=block.start,
                end=block.end,
                room_id=block.room_id,
                room_code=(
                    room_codes.get(block.room_id, "")
                    if block.room_id is not None
                    else ""
                ),
                lecturer_ids=block.lecturers,
                lecturer_names=lecturer_names,
                section_label=class_labels.get(
                    block.section_id, str(block.section_id)
                ),
            )
            for block in [*occupied, *new_blocks]
        ]
    )
    run.stats = {
        "assigned": len(result.assignments),
        "unassigned": len(unassigned_items),
        "conflicts": len(conflicts),
        "created_sections": created_sections,
        "kept_schedules": len(occupied),
        "repaired_schedules": len(repair_ids),
        "protected_schedules": len(protected_schedule_ids),
        "regenerated": len(target_section_ids - preserved_manual_sections),
        "preserved_final": len(preserved_final_sections),
        "preserved_manual": len(preserved_manual_sections),
        "study_program_id": str(study_program_id) if study_program_id else None,
        "search_nodes": result.explored,
        "preferred_matches": result.preferred_matches,
        "fallback_assignments": fallback_assignments,
    }
    run.status = "completed"
    run.ended_at = datetime.now(timezone.utc)
    await db.flush()

    return GenerateResponse(
        run_id=str(run.run_id),
        assigned=len(result.assignments),
        unassigned=unassigned_items,
        conflicts=conflicts,
        mode=mode,
        assigned_count=len(result.assignments),
        unassigned_count=len(unassigned_items),
        conflict_count=len(conflicts),
        input_revision=run.input_revision,
        study_program_id=(
            str(study_program_id) if study_program_id is not None else None
        ),
        regenerated_count=len(target_section_ids - preserved_manual_sections),
        preserved_final_count=len(preserved_final_sections),
        preserved_manual_count=len(preserved_manual_sections),
    )
