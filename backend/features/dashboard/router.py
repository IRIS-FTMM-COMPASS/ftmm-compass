"""Dashboard telemetry per peran. Semua angka berasal dari database."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from academics import TOTAL_SKS_FOR_GRADUATION, grade_points
from features.scheduling.routers.scheduling_board import _program_statuses
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
    DegreePlan,
    DegreePlanItem,
    LecturerSchedulePreference,
    OfferingComponent,
    Room,
    SchedulePeriodSettings,
    ScheduleProgramStatus,
    StudentCourseRecord,
    StudentProfile as StudentProfileModel,
    StudyProgram,
    Timetable,
    TimetableItem,
    User,
)
from schemas import AdminDashboardStats, StudentDashboardStats
from scheduling_common import current_period_id, status_label


class DashboardScheduleItem(BaseModel):
    id: str
    class_section_id: str = ""
    assignment_id: str = ""
    course_id: str
    course_code: str
    course_name: str
    credits: int
    study_program_ids: list[str] = Field(default_factory=list)
    study_program_codes: list[str] = Field(default_factory=list)
    study_program_names: list[str] = Field(default_factory=list)
    schedule_state: Literal["draft", "final"] = "draft"
    day: str
    day_of_week: int = 0
    start_time: str
    end_time: str
    time: str
    room: str
    lecturer: str | None = None
    class_name: str | None = None
    color: str | None = "teal"


class DashboardAssignedClass(BaseModel):
    assignment_id: str
    class_section_id: str
    course_id: str
    course_code: str
    course_name: str
    credits: int
    class_name: str
    study_program_ids: list[str]
    study_program_codes: list[str]
    study_program_names: list[str]
    schedule_state: Literal["draft", "final"]
    schedules: list[DashboardScheduleItem]


class LecturerDashboardStats(BaseModel):
    type: Literal["lecturer"] = "lecturer"
    assigned_classes: int
    scheduled_classes: int
    unscheduled_classes: int


class LecturerPreferenceStatus(BaseModel):
    academic_period_id: str | None
    status: Literal["empty", "filled"]
    preferred_count: int
    unavailable_count: int
    deadline: datetime | None
    deadline_scope: Literal["program", "global"] | None


class DashboardMeResponse(BaseModel):
    user_id: str
    full_name: str
    role: str
    email: str
    student_number: str | None = None
    study_program: str | None = None
    stats: StudentDashboardStats | LecturerDashboardStats | AdminDashboardStats
    schedule: list[DashboardScheduleItem] = Field(default_factory=list)
    schedule_status: str = "Jadwal masih dalam proses"
    academic_period_id: str | None = None
    today: date | None = None
    today_schedule: list[DashboardScheduleItem] = Field(default_factory=list)
    assigned_classes: list[DashboardAssignedClass] = Field(default_factory=list)
    unscheduled_classes: list[DashboardAssignedClass] = Field(default_factory=list)
    preference: LecturerPreferenceStatus | None = None


router = APIRouter()

DAY_NAMES = {1: "Senin", 2: "Selasa", 3: "Rabu", 4: "Kamis", 5: "Jumat"}
COLOR_PALETTE = ["teal", "navy", "gold", "orange"]


def _schedule_item(
    index: int,
    schedule: ClassSchedule,
    section: ClassSection,
    course: Course,
    *,
    credits: int = 0,
    lecturer: str | None = None,
    class_section_id: str = "",
    assignment_id: str = "",
    program_ids: list[str] | None = None,
    program_codes: list[str] | None = None,
    program_names: list[str] | None = None,
    schedule_state: Literal["draft", "final"] = "draft",
    room: Room | None = None,
) -> DashboardScheduleItem:
    start = schedule.start_time.strftime("%H:%M")
    end = schedule.end_time.strftime("%H:%M")
    return DashboardScheduleItem(
        id=f"sch-{schedule.class_schedule_id}",
        class_section_id=class_section_id or str(schedule.class_section_id),
        assignment_id=assignment_id,
        course_id=str(course.course_id),
        course_code=course.course_code,
        course_name=course.course_name,
        credits=credits,
        study_program_ids=program_ids or [],
        study_program_codes=program_codes or [],
        study_program_names=program_names or [],
        schedule_state=schedule_state,
        day=DAY_NAMES.get(schedule.day_of_week, ""),
        day_of_week=schedule.day_of_week,
        start_time=start,
        end_time=end,
        time=f"{start} - {end}",
        room=schedule.room_name or (room.room_code if room else ""),
        lecturer=lecturer,
        class_name=section.section_code,
        color=COLOR_PALETTE[index % len(COLOR_PALETTE)],
    )


async def _lecturer_preference_status(
    db: AsyncSession,
    user: User,
    period_id: UUID | None,
) -> LecturerPreferenceStatus:
    profile = user.lecturer_profile
    program_id = profile.study_program_id if profile else None
    if period_id is None:
        return LecturerPreferenceStatus(
            academic_period_id=None,
            status="empty",
            preferred_count=0,
            unavailable_count=0,
            deadline=None,
            deadline_scope=None,
        )

    counts = {
        row.kind: row.count
        for row in (
            await db.execute(
                select(
                    LecturerSchedulePreference.kind,
                    func.count(LecturerSchedulePreference.preference_id),
                )
                .where(
                    LecturerSchedulePreference.user_id == user.user_id,
                    LecturerSchedulePreference.academic_period_id == period_id,
                )
                .group_by(LecturerSchedulePreference.kind)
            )
        ).all()
    }
    settings = {
        row.study_program_id: row.preference_deadline
        for row in (
            await db.execute(
                select(SchedulePeriodSettings).where(
                    SchedulePeriodSettings.academic_period_id == period_id
                )
            )
        ).scalars().all()
    }
    deadline = settings.get(program_id) or settings.get(None)
    scope = "program" if settings.get(program_id) else "global" if deadline else None
    preferred_count = counts.get("preferred", 0)
    unavailable_count = counts.get("unavailable", 0)
    return LecturerPreferenceStatus(
        academic_period_id=str(period_id),
        status="filled" if preferred_count or unavailable_count else "empty",
        preferred_count=preferred_count,
        unavailable_count=unavailable_count,
        deadline=deadline,
        deadline_scope=scope,
    )


async def _lecturer_dashboard(
    db: AsyncSession,
    user: User,
) -> DashboardMeResponse:
    period_id = await current_period_id(db)
    profile = user.lecturer_profile
    program = profile.study_program if profile else None
    preference = await _lecturer_preference_status(db, user, period_id)
    empty = DashboardMeResponse(
        user_id=str(user.user_id),
        full_name=user.full_name,
        role=user.role,
        email=user.email,
        study_program=program.program_name if program else None,
        stats=LecturerDashboardStats(
            assigned_classes=0, scheduled_classes=0, unscheduled_classes=0
        ),
        academic_period_id=str(period_id) if period_id else None,
        today=date.today(),
        preference=preference,
    )
    if period_id is None:
        return empty

    rows = (
        await db.execute(
            select(
                ClassInstructorAssignment,
                ClassSection,
                CourseOffering,
                Course,
                CurriculumCourse,
                StudyProgram,
            )
            .join(
                ClassSection,
                ClassSection.class_section_id
                == ClassInstructorAssignment.class_section_id,
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
            .join(
                Curriculum,
                Curriculum.curriculum_id == CurriculumCourse.curriculum_id,
            )
            .join(
                StudyProgram,
                StudyProgram.study_program_id == Curriculum.study_program_id,
            )
            .where(
                ClassInstructorAssignment.user_id == user.user_id,
                ClassInstructorAssignment.academic_period_id == period_id,
                ClassInstructorAssignment.is_active.is_(True),
                CourseOffering.academic_period_id == period_id,
            )
            .order_by(
                StudyProgram.program_code,
                Course.course_code,
                ClassSection.section_code,
            )
        )
    ).all()
    if not rows:
        return empty

    schedule_rows = (
        await db.execute(
            select(ClassSchedule, Room)
            .outerjoin(Room, Room.room_id == ClassSchedule.room_id)
            .join(
                ClassInstructorAssignment,
                ClassInstructorAssignment.class_section_id
                == ClassSchedule.class_section_id,
            )
            .where(
                ClassInstructorAssignment.user_id == user.user_id,
                ClassInstructorAssignment.academic_period_id == period_id,
                ClassInstructorAssignment.is_active.is_(True),
            )
            .order_by(ClassSchedule.day_of_week, ClassSchedule.start_time)
        )
    ).all()
    schedules_by_class: dict[UUID, list[tuple[ClassSchedule, Room | None]]] = {}
    for schedule, room in schedule_rows:
        schedules_by_class.setdefault(schedule.class_section_id, []).append(
            (schedule, room)
        )

    program_ids = {row.StudyProgram.study_program_id for row in rows}
    state_rows = (
        await db.execute(
            select(ScheduleProgramStatus).where(
                ScheduleProgramStatus.academic_period_id == period_id,
                ScheduleProgramStatus.study_program_id.in_(program_ids),
            )
        )
    ).scalars().all()
    states = {row.study_program_id: row.state for row in state_rows}

    grouped: dict[UUID, list] = {}
    for row in rows:
        grouped.setdefault(row.ClassInstructorAssignment.assignment_id, []).append(row)

    assigned_classes: list[DashboardAssignedClass] = []
    schedule_index = 0
    for assignment_rows in grouped.values():
        first = assignment_rows[0]
        assignment = first.ClassInstructorAssignment
        section = first.ClassSection
        course = first.Course
        credits = {row.CurriculumCourse.credits_total for row in assignment_rows}
        class_program_ids = sorted(
            {row.StudyProgram.study_program_id for row in assignment_rows}
        )
        class_programs = {
            row.StudyProgram.study_program_id: row.StudyProgram
            for row in assignment_rows
        }
        schedule_state = (
            "final"
            if class_program_ids
            and all(
                states.get(program_id) == "final"
                for program_id in class_program_ids
            )
            else "draft"
        )
        common = {
            "class_section_id": str(section.class_section_id),
            "assignment_id": str(assignment.assignment_id),
            "course_id": str(course.course_id),
            "course_code": course.course_code,
            "course_name": course.course_name,
            "class_name": section.section_code,
            "credits": max(credits),
            "study_program_ids": [str(program_id) for program_id in class_program_ids],
            "study_program_codes": [
                class_programs[program_id].program_code
                for program_id in class_program_ids
            ],
            "study_program_names": [
                class_programs[program_id].program_name
                for program_id in class_program_ids
            ],
            "schedule_state": schedule_state,
        }
        class_schedules = [
            _schedule_item(
                schedule_index + index,
                schedule,
                section,
                course,
                credits=common["credits"],
                lecturer=user.full_name,
                class_section_id=common["class_section_id"],
                assignment_id=common["assignment_id"],
                program_ids=common["study_program_ids"],
                program_codes=common["study_program_codes"],
                program_names=common["study_program_names"],
                schedule_state=schedule_state,
                room=room,
            )
            for index, (schedule, room) in enumerate(
                schedules_by_class.get(section.class_section_id, [])
            )
        ]
        schedule_index += len(class_schedules)
        assigned_classes.append(
            DashboardAssignedClass(**common, schedules=class_schedules)
        )

    schedule = [
        item
        for assigned_class in assigned_classes
        for item in assigned_class.schedules
    ]
    schedule.sort(
        key=lambda item: (
            item.day_of_week,
            item.start_time,
            item.course_code,
            item.class_name or "",
        )
    )
    today = date.today()
    unscheduled = [item for item in assigned_classes if not item.schedules]
    return DashboardMeResponse(
        user_id=str(user.user_id),
        full_name=user.full_name,
        role=user.role,
        email=user.email,
        study_program=program.program_name if program else None,
        stats=LecturerDashboardStats(
            assigned_classes=len(assigned_classes),
            scheduled_classes=len(assigned_classes) - len(unscheduled),
            unscheduled_classes=len(unscheduled),
        ),
        schedule=schedule,
        schedule_status=status_label(
            "final"
            if states
            and all(states.get(program_id) == "final" for program_id in program_ids)
            else "draft"
        ),
        academic_period_id=str(period_id),
        today=today,
        today_schedule=[
            item for item in schedule if item.day_of_week == today.isoweekday()
        ],
        assigned_classes=assigned_classes,
        unscheduled_classes=unscheduled,
        preference=preference,
    )


async def _student_schedule(db: AsyncSession, user_id) -> list[DashboardScheduleItem]:
    active_period_id = select(AcademicPeriod.academic_period_id).where(
        AcademicPeriod.is_active.is_(True)
    ).scalar_subquery()
    timetable = (
        await db.execute(
            select(Timetable).where(
                Timetable.user_id == user_id,
                Timetable.is_active.is_(True),
                Timetable.academic_period_id == active_period_id,
            )
        )
    ).scalars().first()
    if timetable is None:
        return []

    rows = (
        await db.execute(
            select(ClassSchedule, ClassSection, OfferingComponent, CourseOffering, Course)
            .join(ClassSection, ClassSection.class_section_id == ClassSchedule.class_section_id)
            .join(TimetableItem, TimetableItem.class_section_id == ClassSection.class_section_id)
            .join(OfferingComponent, OfferingComponent.offering_component_id == ClassSection.offering_component_id)
            .join(CourseOffering, CourseOffering.course_offering_id == OfferingComponent.course_offering_id)
            .join(Course, Course.course_id == CourseOffering.course_id)
            .where(TimetableItem.timetable_id == timetable.timetable_id)
            .order_by(ClassSchedule.day_of_week, ClassSchedule.start_time)
        )
    ).all()
    return [
        _schedule_item(index, schedule, section, course)
        for index, (schedule, section, _component, _offering, course) in enumerate(rows)
    ]


async def _schedule_status(db: AsyncSession) -> str:
    """Status global final bila seluruh program studi aktif sudah final."""
    period_id = await current_period_id(db)
    if period_id is None:
        return status_label("draft")
    _, state_by_program = await _program_statuses(db, period_id)
    all_final = bool(state_by_program) and all(
        state == "final" for state in state_by_program.values()
    )
    return status_label("final") if all_final else status_label("draft")


@router.get("/dashboard/me", response_model=DashboardMeResponse)
async def get_dashboard_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role == "lecturer":
        return await _lecturer_dashboard(db, current_user)

    if current_user.role == "student":
        profile = (
            await db.execute(
                select(StudentProfileModel)
                .options(selectinload(StudentProfileModel.study_program))
                .where(StudentProfileModel.user_id == current_user.user_id)
            )
        ).scalars().first()

        records = (
            await db.execute(
                select(StudentCourseRecord)
                .options(
                    selectinload(StudentCourseRecord.curriculum_course).selectinload(
                        CurriculumCourse.course
                    )
                )
                .where(StudentCourseRecord.user_id == current_user.user_id)
            )
        ).scalars().all()

        sks_completed = 0
        quality_points = 0.0
        for record in records:
            credits = (
                record.curriculum_course.credits_total
                if record.curriculum_course
                else 0
            )
            if record.record_status == "passed":
                sks_completed += credits
                quality_points += grade_points(record.final_grade) * credits

        # "Direncanakan" = item rencana studi aktif yang belum lulus, bukan
        # `student_course_records.record_status='taking'` (lihat plan §9.2).
        passed_course_ids = {
            record.curriculum_course_id
            for record in records
            if record.record_status == "passed"
        }
        plan_items = (
            await db.execute(
                select(DegreePlanItem)
                .join(
                    DegreePlan,
                    DegreePlan.degree_plan_id == DegreePlanItem.degree_plan_id,
                )
                .options(selectinload(DegreePlanItem.curriculum_course))
                .where(
                    DegreePlan.user_id == current_user.user_id,
                    DegreePlan.status == "active",
                    DegreePlanItem.planning_status == "planned",
                )
            )
        ).scalars().all()
        planned = [
            item
            for item in plan_items
            if item.curriculum_course_id not in passed_course_ids
        ]
        courses_planned = len(planned)
        sks_planned = sum(
            item.curriculum_course.credits_total if item.curriculum_course else 0
            for item in planned
        )

        gpa = round(quality_points / sks_completed, 2) if sks_completed else 0.0
        stats = StudentDashboardStats(
            type="student",
            sks_completed=sks_completed,
            sks_target=TOTAL_SKS_FOR_GRADUATION,
            completion_percentage=round(
                sks_completed / TOTAL_SKS_FOR_GRADUATION * 100, 2
            )
            if sks_completed
            else 0.0,
            current_semester=profile.current_semester if profile else 1,
            courses_planned=courses_planned,
            sks_planned=sks_planned,
            gpa=gpa,
            predicate=(
                "Dengan Pujian (Cumlaude)"
                if gpa >= 3.5
                else "Sangat Memuaskan"
                if sks_completed
                else "Belum ada nilai"
            ),
        )

        return DashboardMeResponse(
            user_id=str(current_user.user_id),
            full_name=current_user.full_name,
            role=current_user.role,
            email=current_user.email,
            student_number=profile.student_number if profile else None,
            study_program=(
                profile.study_program.program_name
                if (profile and profile.study_program)
                else ""
            ),
            stats=stats,
            schedule=await _student_schedule(db, current_user.user_id),
            schedule_status=await _schedule_status(db),
        )

    total_students = (
        await db.execute(select(func.count(User.user_id)).where(User.role == "student"))
    ).scalar() or 0
    total_lecturers = (
        await db.execute(select(func.count(User.user_id)).where(User.role == "lecturer"))
    ).scalar() or 0
    total_courses = (
        await db.execute(select(func.count(Course.course_id)).where(Course.is_active.is_(True)))
    ).scalar() or 0
    total_programs = (
        await db.execute(select(func.count(StudyProgram.study_program_id)))
    ).scalar() or 0

    stats = AdminDashboardStats(
        type="admin",
        total_active_students=total_students,
        total_lecturers=total_lecturers,
        total_courses=total_courses,
        total_study_programs=total_programs,
        system_status="Database & API aktif",
    )
    return DashboardMeResponse(
        user_id=str(current_user.user_id),
        full_name=current_user.full_name,
        role=current_user.role,
        email=current_user.email,
        stats=stats,
        schedule=[],
    )
