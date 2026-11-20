"""Penjadwal Kelas MK lintas prodi.

Algoritmanya sengaja biasa: bangkitkan kandidat blok, isi secara greedy, lalu
perbaiki dengan backtracking terbatas. Tidak ada dependensi baru dan tidak ada
pengecualian untuk kasus yang tidak memungkinkan — kelas yang gagal menjadi
baris ``UnassignedClass`` beserta alasannya.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, time, timezone
from math import ceil
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    AcademicPeriod,
    ClassCountOverride,
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
    LecturerAvailability,
    OfferingComponent,
    Room,
    ScheduleEditLog,
    ScheduleRun,
    StudentCourseRecord,
    StudentProfile,
    StudyProgram,
    UnassignedClass,
    User,
)
from schemas import BoardConflictItem, GenerateResponse, UnassignedItem
from scheduling_common import (
    END_HOUR_MAX,
    START_HOUR_MIN,
    blocks_overlap,
    hour_end,
    is_valid_block,
)

REASON_CAPACITY = "kapasitas ruang"
REASON_LOCKED = "mk terkunci"
REASON_NO_AVAILABILITY = "tidak ada availabilitas dosen"
REASON_LECTURER = "dosen tidak tersedia"
REASON_NO_ROOM = "tidak ada ruang milik prodi"
REASON_PARITY = "paritas tidak sesuai"
DEFAULT_SECTION_CAPACITY = 40
SECTION_LETTERS = ("A", "B", "C")
MAX_SEARCH_NODES = 30_000


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


@dataclass(frozen=True)
class ClassTask:
    section_id: UUID
    course_code: str
    section_code: str
    credits: int
    capacity: int
    study_program_id: UUID | None
    lecturers: tuple[UUID, ...]
    blocked_reason: str | None = None


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


@dataclass(frozen=True)
class _Availability:
    day: int
    start: int
    end: int


@dataclass(frozen=True)
class _Eligibility:
    course: CurriculumCourse
    program: StudyProgram


def _lecturer_is_free(
    lecturers: tuple[UUID, ...],
    day: int,
    start: int,
    end: int,
    availability: dict[UUID, tuple[_Availability, ...]],
) -> bool:
    for user_id in lecturers:
        windows = availability.get(user_id, ())
        if not windows or not any(
            window.day == day and window.start <= start and end <= window.end
            for window in windows
        ):
            return False
    return True


def _candidates(
    task: ClassTask,
    rooms_by_program: dict[UUID | None, tuple[RoomOption, ...]],
    availability: dict[UUID, tuple[_Availability, ...]],
) -> tuple[list[Placement], str | None]:
    """Kandidat blok untuk satu kelas, atau alasan mengapa tidak ada."""
    rooms = rooms_by_program.get(task.study_program_id, ())
    if any(not availability.get(user_id) for user_id in task.lecturers):
        return [], REASON_NO_AVAILABILITY

    if not rooms:
        return [], REASON_NO_ROOM

    fitting = [room for room in rooms if room.capacity >= task.capacity]
    if not fitting:
        return [], REASON_CAPACITY

    placements: list[Placement] = []
    blocked_by_availability = False
    for day in range(1, 6):
        for start in range(START_HOUR_MIN, END_HOUR_MAX - task.credits + 1):
            end = hour_end(start, task.credits)
            if not _lecturer_is_free(task.lecturers, day, start, end, availability):
                blocked_by_availability = bool(task.lecturers)
                continue
            for room in fitting:
                placements.append(Placement(day, start, end, room))
    if not placements and blocked_by_availability:
        return [], REASON_LECTURER
    return placements, None


def _collides(
    day: int,
    start: int,
    end: int,
    room_id: UUID,
    lecturers: tuple[UUID, ...],
    room_busy: dict[UUID, list[Block]],
    lecturer_busy: dict[UUID, list[Block]],
) -> bool:
    if any(
        blocks_overlap(start, end, block.start, block.end)
        for block in room_busy.get(room_id, ())
    ):
        return True
    return any(
        blocks_overlap(start, end, block.start, block.end)
        for user_id in lecturers
        for block in lecturer_busy.get(user_id, ())
    )


def solve(
    tasks: list[ClassTask],
    rooms_by_program: dict[UUID | None, tuple[RoomOption, ...]],
    availability: dict[UUID, tuple[_Availability, ...]],
    occupied: tuple[Block, ...] = (),
    *,
    max_nodes: int = MAX_SEARCH_NODES,
) -> SolveResult:
    """Greedy dengan backtracking; blok lama bersifat tetap."""
    candidates: dict[UUID, list[Placement]] = {}
    reasons: dict[UUID, str] = {}
    pending: list[ClassTask] = []
    for task in tasks:
        if task.blocked_reason is not None:
            continue
        placements, reason = _candidates(task, rooms_by_program, availability)
        candidates[task.section_id] = placements
        if reason is not None:
            reasons[task.section_id] = reason
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
            lecturers=frozenset(task.lecturers),
            section_id=task.section_id,
        )
        room_busy[placement.room.room_id].append(block)
        for user_id in task.lecturers:
            lecturer_busy[user_id].append(block)

    def unplace(task: ClassTask, placement: Placement) -> None:
        del assigned[task.section_id]
        room_busy[placement.room.room_id].pop()
        for user_id in task.lecturers:
            lecturer_busy[user_id].pop()

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
                task.lecturers,
                room_busy,
                lecturer_busy,
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
        unassigned.append((task.section_id, reasons.get(task.section_id, REASON_LECTURER)))

    return SolveResult(assignments=best, unassigned=unassigned, explored=explored)


def _detect_conflicts(blocks: list[Block]) -> list[BoardConflictItem]:
    conflicts: list[BoardConflictItem] = []
    for index, first in enumerate(blocks):
        for second in blocks[index + 1 :]:
            if first.day != second.day or not blocks_overlap(
                first.start, first.end, second.start, second.end
            ):
                continue
            shared = {
                "day_of_week": first.day,
                "start_hour": max(first.start, second.start),
                "end_hour": min(first.end, second.end),
            }
            if first.room_id is not None and first.room_id == second.room_id:
                conflicts.append(
                    BoardConflictItem(
                        class_section_a_id=str(first.section_id),
                        class_section_b_id=str(second.section_id),
                        kind="room",
                        **shared,
                    )
                )
            if first.lecturers & second.lecturers:
                conflicts.append(
                    BoardConflictItem(
                        class_section_a_id=str(first.section_id),
                        class_section_b_id=str(second.section_id),
                        kind="lecturer",
                        **shared,
                    )
                )
    return conflicts


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


async def _demand_class_counts(
    db: AsyncSession,
    period: AcademicPeriod,
    eligible_by_offering: dict[UUID, list[_Eligibility]],
    course_by_offering: dict[UUID, Course],
) -> dict[tuple[UUID, UUID], int]:
    """Hitung Kelas MK yang dibutuhkan dari peminat; kuota 40 per kelas."""
    codes_by_target: dict[tuple[UUID, UUID], set[str]] = defaultdict(set)
    failed_ids_by_target: dict[tuple[UUID, UUID], set[UUID]] = defaultdict(set)
    program_ids: set[UUID] = set()
    for offering_id, rows in eligible_by_offering.items():
        course = course_by_offering.get(offering_id)
        if course is None:
            continue
        for row in rows:
            if not row.course.is_active or not _parity_matches(row.course.term, period.term):
                continue
            course_type = (row.course.course_type or "").strip().lower()
            target = (course.course_id, row.program.study_program_id)
            if course_type in {"pilihan", "pilihan_terbatas"}:
                codes_by_target[target].add(course.course_code)
            elif course_type == "wajib":
                failed_ids_by_target[target].add(row.course.curriculum_course_id)
            else:
                continue
            program_ids.add(row.program.study_program_id)

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
        expected += students_by_program.get(target[1], 0)
        counts[target] = min(max(ceil(expected / DEFAULT_SECTION_CAPACITY), 1), 3)
    return counts


async def _create_override_sections(
    db: AsyncSession,
    period: AcademicPeriod,
    eligible_by_offering: dict[UUID, list[_Eligibility]],
    components: dict[UUID, list[OfferingComponent]],
    demand_counts: dict[tuple[UUID, UUID], int] | None = None,
) -> int:
    """Buat Kelas MK tambahan sesuai override atau kebutuhan peminat."""
    class_counts: dict[tuple[UUID, UUID], int] = dict(demand_counts or {})
    overrides = (
        await db.execute(
            select(ClassCountOverride).where(
                ClassCountOverride.academic_period_id == period.academic_period_id
            )
        )
    ).scalars().all()
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
        for _ in range(max(needed, 0)):
            letter = next(
                (code for code in SECTION_LETTERS if code not in existing_codes),
                None,
            )
            if letter is None:
                break
            db.add(
                ClassSection(
                    offering_component_id=component.offering_component_id,
                    section_code=letter,
                    capacity=DEFAULT_SECTION_CAPACITY,
                    enrollment_status="open",
                )
            )
            existing_codes.add(letter)
            created += 1
    if created:
        await db.flush()
    return created


async def generate_schedule(
    db: AsyncSession,
    period: AcademicPeriod,
    *,
    mode: str,
    triggered_by: UUID,
) -> GenerateResponse:
    """Buat satu blok per kelas dan simpan hasil serta diagnosisnya."""
    run = ScheduleRun(
        academic_period_id=period.academic_period_id,
        mode=mode,
        triggered_by=triggered_by,
        status="running",
        stats={},
    )
    db.add(run)
    await db.flush()

    if mode == "full_reset":
        section_ids = await _period_section_ids(db, period.academic_period_id)
        if section_ids:
            existing = (
                await db.execute(
                    select(ClassSchedule).where(
                        ClassSchedule.class_section_id.in_(section_ids)
                    )
                )
            ).scalars().all()
            for schedule in existing:
                db.add(
                    ScheduleEditLog(
                        class_section_id=schedule.class_section_id,
                        changed_by=triggered_by,
                        reason="full_reset",
                        before_state=_schedule_snapshot(schedule),
                        after_state=None,
                    )
                )
            await db.execute(
                delete(ClassSchedule).where(
                    ClassSchedule.class_section_id.in_(section_ids)
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

    curriculum_course_ids = sorted(
        {
            row.course.curriculum_course_id
            for rows in eligible_by_offering.values()
            for row in rows
        }
    )
    lecturers_by_course: dict[UUID, set[UUID]] = defaultdict(set)
    if curriculum_course_ids:
        references = (
            await db.execute(
                select(CourseInstructorReference).where(
                    CourseInstructorReference.curriculum_course_id.in_(
                        curriculum_course_ids
                    ),
                    CourseInstructorReference.user_id.is_not(None),
                )
            )
        ).scalars().all()
        for reference in references:
            lecturers_by_course[reference.curriculum_course_id].add(
                reference.user_id
            )

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
        db, period, eligible_by_offering, course_by_offering
    )
    created_sections = await _create_override_sections(
        db,
        period,
        eligible_by_offering,
        components_by_offering,
        demand_counts,
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

    lecturer_ids = {
        user_id for users in lecturers_by_course.values() for user_id in users
    }
    availability_by_user: dict[UUID, tuple[_Availability, ...]] = {}
    if lecturer_ids:
        availability_rows = (
            await db.execute(
                select(LecturerAvailability).where(
                    LecturerAvailability.user_id.in_(lecturer_ids)
                )
            )
        ).scalars().all()
        windows_by_user: dict[UUID, list[_Availability]] = defaultdict(list)
        for window in availability_rows:
            windows_by_user[window.user_id].append(
                _Availability(window.day_of_week, window.start_hour, window.end_hour)
            )
        availability_by_user = {
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
        primary = matching[0] if matching else (eligibilities[0] if eligibilities else None)
        credits = primary.course.credits_total if primary is not None else 0
        lecturers = tuple(
            sorted(
                {
                    user_id
                    for row in matching
                    for user_id in lecturers_by_course.get(
                        row.course.curriculum_course_id, ()
                    )
                },
                key=str,
            )
        )
        blocked_reason: str | None = None
        if not matching:
            if eligibilities and all(not row.course.is_active for row in eligibilities):
                blocked_reason = REASON_LOCKED
            else:
                blocked_reason = REASON_NO_ROOM if not eligibilities else REASON_PARITY
        elif not is_valid_block(START_HOUR_MIN, credits):
            blocked_reason = REASON_PARITY
        elif lecturers and any(
            not availability_by_user.get(user_id) for user_id in lecturers
        ):
            blocked_reason = REASON_NO_AVAILABILITY

        task = ClassTask(
            section_id=section.class_section_id,
            course_code=course.course_code,
            section_code=section.section_code,
            credits=credits,
            capacity=section.capacity or DEFAULT_SECTION_CAPACITY,
            study_program_id=(
                primary.program.study_program_id if primary is not None else None
            ),
            lecturers=lecturers,
            blocked_reason=blocked_reason,
        )
        tasks.append(task)
        task_by_section[task.section_id] = task
    program_ids = {task.study_program_id for task in tasks} | set(room_rows)
    rooms_by_program = {
        program_id: tuple(room_rows.get(program_id, []) + shared_rooms)
        for program_id in program_ids
    }

    occupied: list[Block] = []
    filled: set[UUID] = set()
    normalized = False
    if sections:
        existing_schedules = (
            await db.execute(
                select(ClassSchedule)
                .where(
                    ClassSchedule.class_section_id.in_(
                        [section.class_section_id for section in sections]
                    )
                )
                .order_by(ClassSchedule.day_of_week, ClassSchedule.start_time)
            )
        ).scalars().all()
        for schedule in existing_schedules:
            filled.add(schedule.class_section_id)
            task = task_by_section.get(schedule.class_section_id)
            # ADR 0004: blok lama 100/150 menit dipersistenkan ke jam penuh.
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
                        class_section_id=schedule.class_section_id,
                        changed_by=triggered_by,
                        reason="normalisasi blok",
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
                    lecturers=frozenset(task.lecturers) if task else frozenset(),
                    section_id=schedule.class_section_id,
                )
            )
    if normalized:
        await db.flush()

    result = solve(
        [task for task in tasks if task.section_id not in filled],
        rooms_by_program,
        availability_by_user,
        tuple(occupied),
    )

    new_blocks: list[Block] = []
    for section_id, placement in result.assignments.items():
        task = task_by_section[section_id]
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
                reason="generate",
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
                lecturers=frozenset(task.lecturers),
                section_id=section_id,
            )
        )

    unassigned_items: list[UnassignedItem] = []
    for section_id, reason in result.unassigned:
        db.add(
            UnassignedClass(
                run_id=run.run_id,
                class_section_id=section_id,
                reason=reason[:200],
            )
        )
        task = task_by_section.get(section_id)
        unassigned_items.append(
            UnassignedItem(
                class_section_id=str(section_id),
                course_code=task.course_code if task else "",
                reason=reason,
            )
        )

    conflicts = _detect_conflicts([*occupied, *new_blocks])
    run.stats = {
        "assigned": len(result.assignments),
        "unassigned": len(unassigned_items),
        "conflicts": len(conflicts),
        "created_sections": created_sections,
        "kept_schedules": len(occupied),
        "search_nodes": result.explored,
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
    )
