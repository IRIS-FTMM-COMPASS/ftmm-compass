"""Period-scoped lecturer preferences and class instructor assignments."""

from datetime import date, datetime, time, timezone
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from academics import period_payload
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
    LecturerProfile,
    LecturerSchedulePreference,
    OfferingComponent,
    SchedulePeriodSettings,
    StudyProgram,
    User,
)
from scheduling_common import DAY_NAMES, current_period_id
from ..assignment_pool import class_assignment_pools
from ..scheduler import (
    bump_input_revisions,
    load_curriculum_contexts,
    scheduling_input_lock,
)

router = APIRouter()

_UNPROCESSABLE = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)


class PreferenceSlotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day_of_week: int = Field(..., ge=1, le=5)
    start_time: time
    end_time: time
    kind: Literal["preferred", "unavailable"]

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_whole_hour(cls, value: time) -> time:
        if value.tzinfo is not None or value.minute or value.second or value.microsecond:
            raise ValueError("Jam mulai dan selesai harus berupa jam penuh tanpa zona waktu")
        return value

    @model_validator(mode="after")
    def validate_range(self) -> "PreferenceSlotRequest":
        if not time(7) <= self.start_time < time(17):
            raise ValueError("Jam mulai harus antara 07:00 dan 17:00")
        if not time(7) < self.end_time <= time(17):
            raise ValueError("Jam selesai harus antara 07:00 dan 17:00")
        if self.end_time <= self.start_time:
            raise ValueError("Jam selesai harus setelah jam mulai")
        return self


class PreferenceReplaceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slots: list[PreferenceSlotRequest] = Field(default_factory=list)
    academic_period_id: UUID | None = None


class PreferenceItemResponse(BaseModel):
    day_of_week: int
    day_name: str
    start_time: time
    end_time: time
    kind: Literal["preferred", "unavailable"]


class PreferenceWarning(BaseModel):
    code: Literal["assigned_class_overlap"]
    message: str
    class_section_id: str
    course_code: str
    course_name: str
    section_code: str
    day_of_week: int
    day_name: str
    unavailable_start_time: time
    unavailable_end_time: time
    class_start_time: time
    class_end_time: time
    overlap_start_time: time
    overlap_end_time: time


class PreferenceCompleteness(BaseModel):
    filled: bool
    preferred_count: int
    unavailable_count: int


class PreferenceMeta(BaseModel):
    count: int
    status: Literal["empty", "filled"]
    preferred_count: int
    unavailable_count: int
    completeness: PreferenceCompleteness
    deadline: datetime | None
    warnings: list[PreferenceWarning]


class PreferenceListResponse(BaseModel):
    academic_period_id: str
    user_id: str
    data: list[PreferenceItemResponse]
    meta: PreferenceMeta


class PreferenceCopyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_academic_period_id: UUID
    academic_period_id: UUID
    overwrite: bool = False


class PreferencePeriodResponse(BaseModel):
    academic_period_id: str
    academic_year_start: int
    semester_number: int | None
    term: str
    label: str
    start_date: date | None
    end_date: date | None
    is_active: bool
    is_current: bool


class PreferencePeriodListResponse(BaseModel):
    data: list[PreferencePeriodResponse]
    meta: dict[str, Any]


class PeriodSettingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    academic_period_id: UUID
    study_program_id: UUID | None = None
    preference_deadline: datetime | None = None


class PeriodSettingsResponse(BaseModel):
    academic_period_id: str
    study_program_id: str | None
    study_program_code: str | None
    study_program_name: str | None
    preference_deadline: datetime | None
    input_revision: int
    finalized_at: datetime | None
    updated_at: datetime | None


class PreferenceSummaryItem(BaseModel):
    user_id: str
    full_name: str
    study_program_id: str
    study_program_code: str
    study_program_name: str
    status: Literal["empty", "filled"]
    preferred_count: int
    unavailable_count: int
    deadline: datetime | None


class PreferenceSummaryResponse(BaseModel):
    data: list[PreferenceSummaryItem]
    meta: dict[str, int]


class AssignmentUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    academic_period_id: UUID
    user_id: UUID
    source: Literal["auto", "manual"] = "manual"
    is_pinned: bool = False


class AssignmentResponse(BaseModel):
    assignment_id: str
    class_section_id: str
    academic_period_id: str
    user_id: str
    lecturer_name: str
    source: Literal["auto", "manual"]
    is_pinned: bool
    is_active: bool
    assigned_by: str
    assigned_at: str


class AssignmentEnvelope(BaseModel):
    data: AssignmentResponse | None


def _error(
    status_code: int,
    code: str,
    message: str,
    *,
    details: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    return error_response(
        status_code,
        code,
        message,
        detail=message,
        details=details or [],
    )


def _field_error(field: str, message: str, code: str) -> JSONResponse:
    return _error(
        _UNPROCESSABLE,
        code,
        message,
        details=[{"field": field, "message": message, "code": code}],
    )


def _require_self_lecturer(current_user: User) -> JSONResponse | None:
    if (
        current_user.role == "lecturer"
        and current_user.lecturer_profile is not None
    ):
        return None
    return _error(
        status.HTTP_403_FORBIDDEN,
        "forbidden",
        "Hanya dosen yang dapat mengelola preferensinya sendiri.",
    )


def _scheduler_scope(current_user: User) -> UUID | None | JSONResponse:
    if current_user.role == "admin":
        return None
    profile = current_user.lecturer_profile
    if (
        current_user.role == "lecturer"
        and profile is not None
        and profile.is_program_coordinator
        and profile.study_program_id is not None
    ):
        return profile.study_program_id
    return _error(
        status.HTTP_403_FORBIDDEN,
        "forbidden",
        "Assignment pengajar hanya tersedia untuk admin dan PJ Prodi.",
    )



def _preference_admin_scope(
    current_user: User, requested_program_id: UUID | None
) -> UUID | None | JSONResponse:
    if current_user.role == "admin":
        return requested_program_id
    profile = current_user.lecturer_profile
    if (
        current_user.role == "lecturer"
        and profile is not None
        and profile.is_program_coordinator
        and profile.study_program_id is not None
    ):
        if (
            requested_program_id is not None
            and requested_program_id != profile.study_program_id
        ):
            return _error(
                status.HTTP_403_FORBIDDEN,
                "forbidden",
                "PJ Prodi hanya dapat mengelola preferensi pada prodinya sendiri.",
            )
        return profile.study_program_id
    return _error(
        status.HTTP_403_FORBIDDEN,
        "forbidden",
        "Pengaturan preferensi hanya tersedia untuk admin dan PJ Prodi.",
    )


async def _resolve_study_program(
    db: AsyncSession, study_program_id: UUID
) -> StudyProgram | JSONResponse:
    program = await db.get(StudyProgram, study_program_id)
    if program is None:
        return _error(
            status.HTTP_404_NOT_FOUND,
            "study_program_not_found",
            "Program studi tidak ditemukan.",
        )
    return program


def _period_settings_response(
    period_id: UUID,
    study_program_id: UUID | None,
    study_program: StudyProgram | None,
    settings: SchedulePeriodSettings | None,
) -> PeriodSettingsResponse:
    return PeriodSettingsResponse(
        academic_period_id=str(period_id),
        study_program_id=str(study_program_id) if study_program_id else None,
        study_program_code=study_program.program_code if study_program else None,
        study_program_name=study_program.program_name if study_program else None,
        preference_deadline=settings.preference_deadline if settings else None,
        input_revision=settings.input_revision if settings else 0,
        finalized_at=settings.finalized_at if settings else None,
        updated_at=settings.updated_at if settings else None,
    )


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
        ).scalars().all()
    )
    global_deadline = None
    program_deadlines: dict[UUID, datetime] = {}
    for row in rows:
        if row.study_program_id is None:
            global_deadline = row.preference_deadline
        elif row.preference_deadline is not None:
            program_deadlines[row.study_program_id] = row.preference_deadline
    return global_deadline, program_deadlines


async def _effective_preference_deadline(
    db: AsyncSession, period_id: UUID, study_program_id: UUID | None
) -> datetime | None:
    global_deadline, program_deadlines = await _period_deadlines(db, period_id)
    if study_program_id is None:
        return global_deadline
    return program_deadlines.get(study_program_id, global_deadline)


async def _resolve_period(
    db: AsyncSession, requested_period_id: UUID | None
) -> AcademicPeriod | JSONResponse:
    period_id = requested_period_id or await current_period_id(db)
    if period_id is None:
        return _error(
            status.HTTP_404_NOT_FOUND,
            "period_not_found",
            "Periode akademik aktif tidak ditemukan.",
        )
    period = await db.get(AcademicPeriod, period_id)
    if period is None:
        return _error(
            status.HTTP_404_NOT_FOUND,
            "period_not_found",
            "Periode akademik tidak ditemukan.",
        )
    return period


def _preference_response(
    period_id: UUID,
    user_id: UUID,
    slots: list[PreferenceSlotRequest],
    *,
    warnings: list[PreferenceWarning] | None = None,
    deadline: datetime | None = None,
) -> PreferenceListResponse:
    ordered = sorted(slots, key=lambda slot: (slot.day_of_week, slot.start_time, slot.kind))
    preferred_count = sum(slot.kind == "preferred" for slot in ordered)
    unavailable_count = sum(slot.kind == "unavailable" for slot in ordered)
    filled = bool(ordered)
    return PreferenceListResponse(
        academic_period_id=str(period_id),
        user_id=str(user_id),
        data=[
            PreferenceItemResponse(
                day_of_week=slot.day_of_week,
                day_name=DAY_NAMES[slot.day_of_week],
                start_time=slot.start_time,
                end_time=slot.end_time,
                kind=slot.kind,
            )
            for slot in ordered
        ],
        meta=PreferenceMeta(
            count=len(ordered),
            status="filled" if filled else "empty",
            preferred_count=preferred_count,
            unavailable_count=unavailable_count,
            completeness=PreferenceCompleteness(
                filled=filled,
                preferred_count=preferred_count,
                unavailable_count=unavailable_count,
            ),
            deadline=deadline,
            warnings=warnings or [],
        ),
    )


def _preference_slots_from_rows(
    rows: list[LecturerSchedulePreference],
) -> list[PreferenceSlotRequest]:
    return [
        PreferenceSlotRequest(
            day_of_week=row.day_of_week,
            start_time=row.start_time,
            end_time=row.end_time,
            kind=row.kind,
        )
        for row in rows
    ]


def _overlapping_slots(
    slots: list[PreferenceSlotRequest],
) -> list[dict[str, Any]]:
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


async def _assignment_overlap_warnings(
    db: AsyncSession,
    user_id: UUID,
    period_id: UUID,
    slots: list[PreferenceSlotRequest],
) -> list[PreferenceWarning]:
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
    warnings: list[PreferenceWarning] = []
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
                PreferenceWarning(
                    code="assigned_class_overlap",
                    message=(
                        f"Blok tidak tersedia bertabrakan dengan {course_code} "
                        f"kelas {section_code}."
                    ),
                    class_section_id=str(schedule.class_section_id),
                    course_code=course_code,
                    course_name=course_name,
                    section_code=section_code,
                    day_of_week=slot.day_of_week,
                    day_name=DAY_NAMES[slot.day_of_week],
                    unavailable_start_time=slot.start_time,
                    unavailable_end_time=slot.end_time,
                    class_start_time=schedule.start_time,
                    class_end_time=schedule.end_time,
                    overlap_start_time=max(slot.start_time, schedule.start_time),
                    overlap_end_time=min(slot.end_time, schedule.end_time),
                )
            )
    return warnings


@router.get(
    "/scheduling/preferences/periods",
    response_model=PreferencePeriodListResponse,
)
async def list_preference_periods(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    current_id = await current_period_id(db)
    periods = list((await db.execute(select(AcademicPeriod))).scalars().all())
    periods.sort(
        key=lambda period: (
            period.academic_period_id != current_id,
            not period.is_active,
            -period.academic_year_start,
            -(period.semester_number or 0),
            period.term,
            str(period.academic_period_id),
        )
    )
    today = date.today()
    return PreferencePeriodListResponse(
        data=[
            PreferencePeriodResponse(
                academic_period_id=str(period.academic_period_id),
                academic_year_start=period.academic_year_start,
                semester_number=period.semester_number,
                term=period.term,
                label=period_payload(
                    period.academic_year_start,
                    period.term,
                    period.start_date,
                    period.end_date,
                    today,
                    semester_number=period.semester_number,
                )["label"],
                start_date=period.start_date,
                end_date=period.end_date,
                is_active=period.is_active,
                is_current=period.academic_period_id == current_id,
            )
            for period in periods
        ],
        meta={
            "total": len(periods),
            "current_academic_period_id": (
                str(current_id) if current_id is not None else None
            ),
        },
    )


@router.get("/scheduling/period-settings", response_model=PeriodSettingsResponse)
async def get_period_settings(
    academic_period_id: UUID | None = Query(None),
    study_program_id: UUID | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope = _preference_admin_scope(current_user, study_program_id)
    if isinstance(scope, JSONResponse):
        return scope
    period = await _resolve_period(db, academic_period_id)
    if isinstance(period, JSONResponse):
        return period
    program = None
    if scope is not None:
        program = await _resolve_study_program(db, scope)
        if isinstance(program, JSONResponse):
            return program
    settings = (
        await db.execute(
            select(SchedulePeriodSettings).where(
                SchedulePeriodSettings.academic_period_id
                == period.academic_period_id,
                (
                    SchedulePeriodSettings.study_program_id.is_(None)
                    if scope is None
                    else SchedulePeriodSettings.study_program_id == scope
                ),
            )
        )
    ).scalar_one_or_none()
    return _period_settings_response(
        period.academic_period_id, scope, program, settings
    )


@router.put("/scheduling/period-settings", response_model=PeriodSettingsResponse)
async def put_period_settings(
    payload: PeriodSettingsRequest = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = current_user.lecturer_profile
    if (
        current_user.role == "lecturer"
        and profile is not None
        and profile.is_program_coordinator
        and "study_program_id" in payload.model_fields_set
        and payload.study_program_id != profile.study_program_id
    ):
        return _error(
            status.HTTP_403_FORBIDDEN,
            "forbidden",
            "PJ Prodi hanya dapat mengatur deadline preferensi prodinya sendiri.",
        )
    scope = _preference_admin_scope(current_user, payload.study_program_id)
    if isinstance(scope, JSONResponse):
        return scope
    period = await _resolve_period(db, payload.academic_period_id)
    if isinstance(period, JSONResponse):
        return period
    program = None
    if scope is not None:
        program = await _resolve_study_program(db, scope)
        if isinstance(program, JSONResponse):
            return program
    locked = await scheduling_input_lock(
        db,
        period.academic_period_id,
        {scope} if scope is not None else None,
    )
    if locked is not None:
        code, message = locked
        return _error(status.HTTP_409_CONFLICT, code, message)


    await db.execute(
        select(AcademicPeriod.academic_period_id)
        .where(AcademicPeriod.academic_period_id == period.academic_period_id)
        .with_for_update()
    )
    settings = (
        await db.execute(
            select(SchedulePeriodSettings)
            .where(
                SchedulePeriodSettings.academic_period_id
                == period.academic_period_id,
                (
                    SchedulePeriodSettings.study_program_id.is_(None)
                    if scope is None
                    else SchedulePeriodSettings.study_program_id == scope
                ),
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if settings is None:
        settings = SchedulePeriodSettings(
            academic_period_id=period.academic_period_id,
            study_program_id=scope,
            preference_deadline=payload.preference_deadline,
        )
        db.add(settings)
    else:
        settings.preference_deadline = payload.preference_deadline
    await db.flush()
    await db.refresh(settings)
    response = _period_settings_response(
        period.academic_period_id, scope, program, settings
    )
    await db.commit()
    return response


@router.get(
    "/scheduling/preferences/summary",
    response_model=PreferenceSummaryResponse,
)
async def list_preference_summary(
    academic_period_id: UUID | None = Query(None),
    study_program_id: UUID | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope = _preference_admin_scope(current_user, study_program_id)
    if isinstance(scope, JSONResponse):
        return scope
    period = await _resolve_period(db, academic_period_id)
    if isinstance(period, JSONResponse):
        return period
    if scope is not None:
        program = await _resolve_study_program(db, scope)
        if isinstance(program, JSONResponse):
            return program

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
        lecturer_query = lecturer_query.where(
            LecturerProfile.study_program_id == scope
        )
    lecturers = (await db.execute(lecturer_query)).all()
    counts: dict[UUID, list[int]] = {
        row.user_id: [0, 0] for row in lecturers
    }
    if counts:
        preference_rows = (
            await db.execute(
                select(
                    LecturerSchedulePreference.user_id,
                    LecturerSchedulePreference.kind,
                ).where(
                    LecturerSchedulePreference.academic_period_id
                    == period.academic_period_id,
                    LecturerSchedulePreference.user_id.in_(counts),
                )
            )
        ).all()
        for user_id, kind in preference_rows:
            counts[user_id][0 if kind == "preferred" else 1] += 1

    global_deadline, program_deadlines = await _period_deadlines(
        db, period.academic_period_id
    )
    items = []
    filled_count = 0
    for row in lecturers:
        preferred_count, unavailable_count = counts[row.user_id]
        filled = bool(preferred_count or unavailable_count)
        filled_count += int(filled)
        items.append(
            PreferenceSummaryItem(
                user_id=str(row.user_id),
                full_name=row.full_name,
                study_program_id=str(row.study_program_id),
                study_program_code=row.program_code,
                study_program_name=row.program_name,
                status="filled" if filled else "empty",
                preferred_count=preferred_count,
                unavailable_count=unavailable_count,
                deadline=program_deadlines.get(
                    row.study_program_id, global_deadline
                ),
            )
        )
    return PreferenceSummaryResponse(
        data=items,
        meta={
            "total": len(items),
            "filled": filled_count,
            "empty": len(items) - filled_count,
        },
    )


@router.get("/scheduling/preferences/me", response_model=PreferenceListResponse)
async def get_my_preferences(
    academic_period_id: UUID | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    denied = _require_self_lecturer(current_user)
    if denied is not None:
        return denied
    period = await _resolve_period(db, academic_period_id)
    if isinstance(period, JSONResponse):
        return period
    rows = list(
        (
            await db.execute(
                select(LecturerSchedulePreference)
                .where(
                    LecturerSchedulePreference.user_id == current_user.user_id,
                    LecturerSchedulePreference.academic_period_id
                    == period.academic_period_id,
                )
                .order_by(
                    LecturerSchedulePreference.day_of_week,
                    LecturerSchedulePreference.start_time,
                    LecturerSchedulePreference.kind,
                )
            )
        ).scalars().all()
    )
    slots = _preference_slots_from_rows(rows)
    return _preference_response(
        period.academic_period_id,
        current_user.user_id,
        slots,
        warnings=await _assignment_overlap_warnings(
            db, current_user.user_id, period.academic_period_id, slots
        ),
        deadline=await _effective_preference_deadline(
            db,
            period.academic_period_id,
            current_user.lecturer_profile.study_program_id,
        ),
    )


@router.put("/scheduling/preferences/me", response_model=PreferenceListResponse)
async def replace_my_preferences(
    payload: list[PreferenceSlotRequest] | PreferenceReplaceRequest = Body(...),
    academic_period_id: UUID | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    denied = _require_self_lecturer(current_user)
    if denied is not None:
        return denied
    requested_period_id = (
        payload.academic_period_id if isinstance(payload, PreferenceReplaceRequest) else None
    )
    if (
        academic_period_id is not None
        and requested_period_id is not None
        and academic_period_id != requested_period_id
    ):
        return _field_error(
            "academic_period_id",
            "Periode akademik pada query dan body harus sama.",
            "period_mismatch",
        )
    period = await _resolve_period(db, academic_period_id or requested_period_id)
    if isinstance(period, JSONResponse):
        return period
    locked = await scheduling_input_lock(
        db,
        period.academic_period_id,
        {current_user.lecturer_profile.study_program_id},
    )
    if locked is not None:
        code, message = locked
        return _error(status.HTTP_409_CONFLICT, code, message)

    slots = payload if isinstance(payload, list) else payload.slots
    overlap = _overlapping_slots(slots)
    if overlap:
        return _error(
            _UNPROCESSABLE,
            "overlapping_preference",
            "Preferensi dan blok tidak tersedia tidak boleh bertabrakan.",
            details=overlap,
        )

    previous_rows = (
        await db.execute(
            select(LecturerSchedulePreference).where(
                LecturerSchedulePreference.user_id == current_user.user_id,
                LecturerSchedulePreference.academic_period_id
                == period.academic_period_id,
            )
        )
    ).scalars().all()
    previous_slots = _preference_slots_from_rows(previous_rows)

    def slot_key(slot: PreferenceSlotRequest) -> tuple[int, time, time, str]:
        return (
            slot.day_of_week,
            slot.start_time,
            slot.end_time,
            slot.kind,
        )

    changed = sorted(previous_slots, key=slot_key) != sorted(slots, key=slot_key)
    await db.execute(
        select(User.user_id)
        .where(User.user_id == current_user.user_id)
        .with_for_update()
    )
    await db.execute(
        delete(LecturerSchedulePreference).where(
            LecturerSchedulePreference.user_id == current_user.user_id,
            LecturerSchedulePreference.academic_period_id == period.academic_period_id,
        )
    )
    db.add_all(
        [
            LecturerSchedulePreference(
                user_id=current_user.user_id,
                academic_period_id=period.academic_period_id,
                day_of_week=slot.day_of_week,
                start_time=slot.start_time,
                end_time=slot.end_time,
                kind=slot.kind,
            )
            for slot in slots
        ]
    )
    if changed:
        await bump_input_revisions(
            db,
            period.academic_period_id,
            {current_user.lecturer_profile.study_program_id},
        )
    try:
        warnings = await _assignment_overlap_warnings(
            db, current_user.user_id, period.academic_period_id, slots
        )
        deadline = await _effective_preference_deadline(
            db,
            period.academic_period_id,
            current_user.lecturer_profile.study_program_id,
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return _error(
            _UNPROCESSABLE,
            "overlapping_preference",
            "Preferensi dan blok tidak tersedia tidak boleh bertabrakan.",
        )
    return _preference_response(
        period.academic_period_id,
        current_user.user_id,
        slots,
        warnings=warnings,
        deadline=deadline,
    )


@router.post("/scheduling/preferences/me/copy", response_model=PreferenceListResponse)
async def copy_my_preferences(
    payload: PreferenceCopyRequest = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    denied = _require_self_lecturer(current_user)
    if denied is not None:
        return denied
    if payload.from_academic_period_id == payload.academic_period_id:
        return _field_error(
            "academic_period_id",
            "Periode sumber dan tujuan harus berbeda.",
            "same_period",
        )
    source_period = await _resolve_period(db, payload.from_academic_period_id)
    if isinstance(source_period, JSONResponse):
        return source_period
    target_period = await _resolve_period(db, payload.academic_period_id)
    if isinstance(target_period, JSONResponse):
        return target_period
    locked = await scheduling_input_lock(
        db,
        target_period.academic_period_id,
        {current_user.lecturer_profile.study_program_id},
    )
    if locked is not None:
        code, message = locked
        return _error(status.HTTP_409_CONFLICT, code, message)

    await db.execute(
        select(User.user_id)
        .where(User.user_id == current_user.user_id)
        .with_for_update()
    )

    async def load_slots(period_id: UUID) -> list[PreferenceSlotRequest]:
        rows = list(
            (
                await db.execute(
                    select(LecturerSchedulePreference)
                    .where(
                        LecturerSchedulePreference.user_id == current_user.user_id,
                        LecturerSchedulePreference.academic_period_id == period_id,
                    )
                    .order_by(
                        LecturerSchedulePreference.day_of_week,
                        LecturerSchedulePreference.start_time,
                        LecturerSchedulePreference.kind,
                    )
                )
            ).scalars().all()
        )
        return _preference_slots_from_rows(rows)

    source_slots = await load_slots(source_period.academic_period_id)
    target_slots = await load_slots(target_period.academic_period_id)
    source_overlap = _overlapping_slots(source_slots)
    if source_overlap:
        return _error(
            _UNPROCESSABLE,
            "overlapping_preference",
            "Preferensi dan blok tidak tersedia pada periode sumber bertabrakan.",
            details=source_overlap,
        )

    def slot_key(slot: PreferenceSlotRequest) -> tuple[int, time, time, str]:
        return (
            slot.day_of_week,
            slot.start_time,
            slot.end_time,
            slot.kind,
        )
    if sorted(source_slots, key=slot_key) == sorted(target_slots, key=slot_key):
        return _preference_response(
            target_period.academic_period_id,
            current_user.user_id,
            target_slots,
            warnings=await _assignment_overlap_warnings(
                db,
                current_user.user_id,
                target_period.academic_period_id,
                target_slots,
            ),
            deadline=await _effective_preference_deadline(
                db,
                target_period.academic_period_id,
                current_user.lecturer_profile.study_program_id,
            ),
        )
    if target_slots and not payload.overwrite:
        return _error(
            status.HTTP_409_CONFLICT,
            "preferences_exist",
            "Preferensi periode tujuan sudah terisi. Gunakan overwrite untuk menimpanya.",
            details=[
                {
                    "field": "academic_period_id",
                    "academic_period_id": str(target_period.academic_period_id),
                    "existing_count": len(target_slots),
                }
            ],
        )

    await db.execute(
        delete(LecturerSchedulePreference).where(
            LecturerSchedulePreference.user_id == current_user.user_id,
            LecturerSchedulePreference.academic_period_id
            == target_period.academic_period_id,
        )
    )
    db.add_all(
        [
            LecturerSchedulePreference(
                user_id=current_user.user_id,
                academic_period_id=target_period.academic_period_id,
                day_of_week=slot.day_of_week,
                start_time=slot.start_time,
                end_time=slot.end_time,
                kind=slot.kind,
            )
            for slot in source_slots
        ]
    )
    await bump_input_revisions(
        db,
        target_period.academic_period_id,
        {current_user.lecturer_profile.study_program_id},
    )
    try:
        warnings = await _assignment_overlap_warnings(
            db,
            current_user.user_id,
            target_period.academic_period_id,
            source_slots,
        )
        deadline = await _effective_preference_deadline(
            db,
            target_period.academic_period_id,
            current_user.lecturer_profile.study_program_id,
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return _error(
            _UNPROCESSABLE,
            "overlapping_preference",
            "Preferensi dan blok tidak tersedia pada periode sumber bertabrakan.",
        )
    return _preference_response(
        target_period.academic_period_id,
        current_user.user_id,
        source_slots,
        warnings=warnings,
        deadline=deadline,
    )


async def _class_context(
    db: AsyncSession,
    class_section_id: UUID,
    scope: UUID | None,
) -> tuple[UUID, UUID | None] | JSONResponse:
    rows = (
        await db.execute(
            select(
                CourseOffering.academic_period_id,
                Curriculum.study_program_id,
                CurriculumCourse.curriculum_course_id,
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
            .where(ClassSection.class_section_id == class_section_id)
        )
    ).all()
    if not rows:
        return _error(
            status.HTTP_404_NOT_FOUND,
            "class_not_found",
            "Kelas MK tidak ditemukan.",
        )
    program_ids = {row.study_program_id for row in rows}
    curriculum_ids = {row.curriculum_course_id for row in rows}
    if len(program_ids) > 1 or len(curriculum_ids) > 1:
        return _error(
            status.HTTP_409_CONFLICT,
            "curriculum_context_required",
            "Kelas MK memiliki beberapa konteks kurikulum atau prodi.",
        )
    program_id = rows[0].study_program_id
    if scope is not None and program_id != scope:
        return _error(
            status.HTTP_403_FORBIDDEN,
            "forbidden",
            "Kelas MK berada di luar program studi Anda.",
        )
    return rows[0].academic_period_id, program_id


def _assignment_response(
    assignment: ClassInstructorAssignment,
    lecturer_name: str,
) -> AssignmentResponse:
    return AssignmentResponse(
        assignment_id=str(assignment.assignment_id),
        class_section_id=str(assignment.class_section_id),
        academic_period_id=str(assignment.academic_period_id),
        user_id=str(assignment.user_id),
        lecturer_name=lecturer_name,
        source=assignment.source,
        is_pinned=assignment.is_pinned,
        is_active=assignment.is_active,
        assigned_by=str(assignment.assigned_by),
        assigned_at=assignment.assigned_at.isoformat(),
    )


@router.get(
    "/scheduling/classes/{class_section_id}/assignment",
    response_model=AssignmentEnvelope,
)
async def get_class_assignment(
    class_section_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope = _scheduler_scope(current_user)
    if isinstance(scope, JSONResponse):
        return scope
    context = await _class_context(db, class_section_id, scope)
    if isinstance(context, JSONResponse):
        return context
    row = (
        await db.execute(
            select(ClassInstructorAssignment, User.full_name)
            .join(User, User.user_id == ClassInstructorAssignment.user_id)
            .where(
                ClassInstructorAssignment.class_section_id == class_section_id,
                ClassInstructorAssignment.is_active.is_(True),
            )
            .limit(1)
        )
    ).first()
    if row is None:
        return AssignmentEnvelope(data=None)
    return AssignmentEnvelope(data=_assignment_response(row[0], row[1]))


@router.put(
    "/scheduling/classes/{class_section_id}/assignment",
    response_model=AssignmentEnvelope,
)
async def upsert_class_assignment(
    class_section_id: UUID,
    payload: AssignmentUpsertRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope = _scheduler_scope(current_user)
    if isinstance(scope, JSONResponse):
        return scope
    context = await _class_context(db, class_section_id, scope)
    if isinstance(context, JSONResponse):
        return context
    class_period_id, program_id = context
    if payload.academic_period_id != class_period_id:
        return _field_error(
            "academic_period_id",
            "Periode akademik tidak sesuai dengan periode kelas MK.",
            "period_mismatch",
        )
    locked = await scheduling_input_lock(
        db,
        class_period_id,
        {program_id} if program_id is not None else None,
    )
    if locked is not None:
        code, message = locked
        return _error(status.HTTP_409_CONFLICT, code, message)


    lecturer = (
        await db.execute(
            select(User)
            .join(LecturerProfile, LecturerProfile.user_id == User.user_id)
            .where(
                User.user_id == payload.user_id,
                User.role == "lecturer",
                User.is_active.is_(True),
            )
        )
    ).scalars().first()
    if lecturer is None:
        return _field_error(
            "user_id",
            "Dosen harus memiliki akun dosen aktif.",
            "invalid_lecturer",
        )

    contexts = await load_curriculum_contexts(
        db, class_period_id, {class_section_id}
    )
    class_pool = await class_assignment_pools(db, class_period_id, contexts)
    if str(payload.user_id) not in {
        item.user_id for item in class_pool.get(class_section_id, [])
    }:
        message = "Dosen harus aktif, berakun, dan menjadi anggota Tim Pengajar kelas MK."
        return _error(
            _UNPROCESSABLE,
            "lecturer_not_in_pool",
            message,
            details=[
                {"field": "user_id", "message": message, "code": "lecturer_not_in_pool"}
            ],
        )

    assignment = (
        await db.execute(
            select(ClassInstructorAssignment)
            .where(
                ClassInstructorAssignment.class_section_id == class_section_id,
                ClassInstructorAssignment.is_active.is_(True),
            )
            .with_for_update()
        )
    ).scalars().first()
    changed = False
    if assignment is None:
        assignment = ClassInstructorAssignment(
            class_section_id=class_section_id,
            academic_period_id=class_period_id,
            user_id=payload.user_id,
            source=payload.source,
            is_pinned=payload.is_pinned,
            is_active=True,
            assigned_by=current_user.user_id,
        )
        db.add(assignment)
        changed = True
    elif (
        assignment.user_id != payload.user_id
        or assignment.source != payload.source
        or assignment.is_pinned != payload.is_pinned
        or assignment.assigned_by != current_user.user_id
    ):
        assignment.user_id = payload.user_id
        assignment.source = payload.source
        assignment.is_pinned = payload.is_pinned
        assignment.assigned_by = current_user.user_id
        assignment.assigned_at = datetime.now(timezone.utc)
        changed = True

    if changed:
        await bump_input_revisions(
            db,
            class_period_id,
            {program_id} if program_id is not None else None,
        )

    try:
        await db.flush()
        await db.refresh(assignment)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return _error(
            status.HTTP_409_CONFLICT,
            "assignment_conflict",
            "Kelas MK sudah memiliki assignment pengajar aktif.",
        )
    return AssignmentEnvelope(data=_assignment_response(assignment, lecturer.full_name))
