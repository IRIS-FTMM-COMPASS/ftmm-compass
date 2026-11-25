"""Endpoint pembangkit jadwal dan diagnosis kelas yang belum terjadwal."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.errors import error_response
from auth import get_current_user
from database import get_db
from models import (
    AcademicPeriod,
    ClassCountOverride,
    ClassSection,
    Course,
    CourseOffering,
    Curriculum,
    CurriculumCourse,
    OfferingComponent,
    SchedulePeriodLock,
    ScheduleProgramStatus,
    ScheduleRun,
    StudyProgram,
    UnassignedClass,
    User,
)
from ..scheduler import (
    bump_input_revisions,
    enrich_unassigned_items,
    generate_schedule,
    reason_code,
    reason_label,
    scheduling_input_lock,
)
from schemas import GenerateRequest, GenerateResponse
from scheduling_common import all_study_program_ids, current_period_id

router = APIRouter()

_UNPROCESSABLE = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)


class ClassCountOverrideRequest(BaseModel):
    academic_period_id: str | None = None
    course_id: str
    study_program_id: str
    class_count: int = Field(..., ge=1, le=3)


class ClassCountOverrideResponse(BaseModel):
    override_id: str
    academic_period_id: str
    course_id: str
    study_program_id: str
    class_count: int
    created: bool


def _field_error(field: str, message: str, code: str = "validation_error"):
    return error_response(
        _UNPROCESSABLE,
        code,
        "Data yang dikirim tidak valid.",
        detail="Data yang dikirim tidak valid.",
        details=[{"field": field, "message": message, "code": code}],
    )


def _require_scheduler(current_user: User):
    """Admin dan PJ Prodi boleh membangkitkan jadwal."""
    if current_user.role == "admin":
        return None
    profile = current_user.lecturer_profile
    if (
        current_user.role == "lecturer"
        and profile is not None
        and profile.is_program_coordinator
        and profile.study_program is not None
    ):
        return None
    return error_response(
        status.HTTP_403_FORBIDDEN,
        "forbidden",
        "Pembangkitan jadwal hanya tersedia untuk admin dan PJ Prodi.",
        detail="Pembangkitan jadwal hanya tersedia untuk admin dan PJ Prodi.",
    )


def _parse_id(value: str, field: str) -> UUID | object:
    try:
        return UUID(value)
    except (ValueError, AttributeError, TypeError):
        return _field_error(field, f"{field} bukan UUID yang valid.")


async def _resolve_period(
    db: AsyncSession, requested: str | None
) -> AcademicPeriod | object | None:
    if requested:
        period_id = _parse_id(requested, "academic_period_id")
        if not isinstance(period_id, UUID):
            return period_id
        period = await db.get(AcademicPeriod, period_id)
    else:
        active_id = await current_period_id(db)
        period = await db.get(AcademicPeriod, active_id) if active_id else None
    if period is None:
        return error_response(
            status.HTTP_404_NOT_FOUND,
            "period_not_found",
            "Periode akademik tidak ditemukan.",
            detail="Periode akademik tidak ditemukan.",
        )
    return period


async def _krs_lock_error(db: AsyncSession, period: AcademicPeriod, message: str):
    """409 bersama saat KRS sudah dibuka untuk generate maupun override."""
    lock = await db.get(SchedulePeriodLock, period.academic_period_id)
    if lock is not None and lock.krs_open:
        return error_response(
            status.HTTP_409_CONFLICT,
            "scheduling_locked",
            message,
            detail=message,
        )
    return None


async def _generate_scope(
    db: AsyncSession,
    payload: GenerateRequest,
    current_user: User,
) -> UUID | None | JSONResponse:
    if payload.mode == "full_reset":
        if payload.study_program_id is not None:
            return _field_error(
                "study_program_id",
                "Mode full_reset selalu mencakup seluruh prodi.",
                "invalid_full_reset_scope",
            )
        return None
    if current_user.role == "lecturer":
        profile = current_user.lecturer_profile
        scope = profile.study_program_id if profile is not None else None
        if payload.study_program_id is not None:
            requested = _parse_id(payload.study_program_id, "study_program_id")
            if not isinstance(requested, UUID):
                return requested
            if requested != scope:
                return error_response(
                    status.HTTP_403_FORBIDDEN,
                    "akses_prodi_ditolak",
                    "PJ hanya dapat membangkitkan jadwal prodinya sendiri.",
                    detail="PJ hanya dapat membangkitkan jadwal prodinya sendiri.",
                )
        return scope
    if payload.study_program_id is None:
        return None
    scope = _parse_id(payload.study_program_id, "study_program_id")
    if not isinstance(scope, UUID):
        return scope
    if await db.get(StudyProgram, scope) is None:
        return error_response(
            status.HTTP_404_NOT_FOUND,
            "study_program_not_found",
            "Program studi tidak ditemukan.",
            detail="Program studi tidak ditemukan.",
        )
    return scope


def _generate_payload(result: GenerateResponse) -> dict[str, Any]:
    payload = result.model_dump(mode="json")
    for item in payload["unassigned"]:
        code = reason_code(item["reason"])
        item["reason_code"] = code
        item["reason"] = reason_label(code)
    return payload


@router.post("/scheduling/generate", response_model=GenerateResponse)
async def generate(
    payload: GenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    denied = _require_scheduler(current_user)
    if denied is not None:
        return denied

    if payload.mode == "full_reset":
        if current_user.role != "admin":
            return error_response(
                status.HTTP_403_FORBIDDEN,
                "forbidden",
                "Mode full_reset hanya tersedia untuk admin.",
                detail="Mode full_reset hanya tersedia untuk admin.",
            )
        if not payload.confirm_full_reset:
            return _field_error(
                "confirm_full_reset",
                "Mode full_reset memerlukan konfirmasi confirm_full_reset=true.",
                "confirmation_required",
            )

    period = await _resolve_period(db, payload.academic_period_id)
    if not isinstance(period, AcademicPeriod):
        return period

    locked = await _krs_lock_error(
        db, period, "KRS sudah dibuka; jadwal periode ini tidak dapat diubah."
    )
    if locked is not None:
        return locked
    scope = await _generate_scope(db, payload, current_user)
    if isinstance(scope, JSONResponse):
        return scope
    if scope is not None or payload.mode == "full_reset":
        locked = await scheduling_input_lock(
            db,
            period.academic_period_id,
            {scope} if scope is not None else None,
        )
        if locked is not None:
            code, message = locked
            return error_response(409, code, message, detail=message)
    result = await generate_schedule(
        db,
        period,
        mode=payload.mode,
        triggered_by=current_user.user_id,
        study_program_id=scope,
    )
    return JSONResponse(content=_generate_payload(result))


@router.post("/scheduling/class-count-overrides", response_model=ClassCountOverrideResponse)
async def put_class_count_override(
    payload: ClassCountOverrideRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    denied = _require_scheduler(current_user)
    if denied is not None:
        return denied

    period_id = _parse_id(payload.academic_period_id or "", "academic_period_id") if (
        payload.academic_period_id
    ) else await current_period_id(db)
    if period_id is None:
        return error_response(
            status.HTTP_404_NOT_FOUND,
            "period_not_found",
            "Tidak ada periode akademik aktif.",
            detail="Tidak ada periode akademik aktif.",
        )
    if not isinstance(period_id, UUID):
        return period_id
    course_id = _parse_id(payload.course_id, "course_id")
    program_id = _parse_id(payload.study_program_id, "study_program_id")
    for candidate in (course_id, program_id):
        if not isinstance(candidate, UUID):
            return candidate

    if current_user.role != "admin":
        profile = current_user.lecturer_profile
        if profile.study_program_id != program_id:
            return error_response(
                status.HTTP_403_FORBIDDEN,
                "akses_prodi_ditolak",
                "PJ hanya dapat mengatur jumlah kelas prodinya sendiri.",
                detail="PJ hanya dapat mengatur jumlah kelas prodinya sendiri.",
            )

    period = await db.get(AcademicPeriod, period_id)
    course = await db.get(Course, course_id)
    program = await db.get(StudyProgram, program_id)
    if period is None:
        return error_response(
            status.HTTP_404_NOT_FOUND,
            "period_not_found",
            "Periode akademik tidak ditemukan.",
            detail="Periode akademik tidak ditemukan.",
        )
    if course is None:
        return error_response(
            status.HTTP_404_NOT_FOUND,
            "course_not_found",
            "Mata kuliah tidak ditemukan.",
            detail="Mata kuliah tidak ditemukan.",
        )
    if program is None:
        return error_response(
            status.HTTP_404_NOT_FOUND,
            "study_program_not_found",
            "Program studi tidak ditemukan.",
            detail="Program studi tidak ditemukan.",
        )

    locked = await _krs_lock_error(
        db, period, "KRS sudah dibuka; jumlah kelas tidak dapat diubah."
    )
    if locked is not None:
        return locked

    program_ids = await all_study_program_ids(db)
    final_program_ids: set[UUID] = set()
    if program_ids:
        final_program_ids = set(
            (
                await db.execute(
                    select(ScheduleProgramStatus.study_program_id).where(
                        ScheduleProgramStatus.academic_period_id
                        == period.academic_period_id,
                        ScheduleProgramStatus.study_program_id.in_(program_ids),
                        ScheduleProgramStatus.state == "final",
                    )
                )
            ).scalars().all()
        )
    all_final = bool(program_ids) and final_program_ids.issuperset(program_ids)

    profile = current_user.lecturer_profile
    actor_program_id = profile.study_program_id if profile is not None else None
    actor_final = False
    if actor_program_id is not None:
        actor_status = await db.get(
            ScheduleProgramStatus, (period.academic_period_id, actor_program_id)
        )
        actor_final = actor_status is not None and actor_status.state == "final"
    if all_final or actor_final:
        message = "Jadwal sudah final; jumlah kelas tidak dapat diubah."
        return error_response(
            status.HTTP_409_CONFLICT,
            "schedule_final",
            message,
            detail=message,
        )
    belongs = (
        await db.execute(
            select(CurriculumCourse.curriculum_course_id)
            .join(
                Curriculum,
                Curriculum.curriculum_id == CurriculumCourse.curriculum_id,
            )
            .where(
                CurriculumCourse.course_id == course_id,
                Curriculum.study_program_id == program_id,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if belongs is None:
        return error_response(
            status.HTTP_404_NOT_FOUND,
            "course_not_in_prodi",
            "Mata kuliah tidak termasuk kurikulum program studi ini.",
            detail="Mata kuliah tidak termasuk kurikulum program studi ini.",
        )

    existing = (
        await db.execute(
            select(ClassCountOverride).where(
                ClassCountOverride.academic_period_id == period_id,
                ClassCountOverride.course_id == course_id,
                ClassCountOverride.study_program_id == program_id,
            )
        )
    ).scalars().first()
    changed = existing is None or existing.class_count != payload.class_count
    if existing is None:
        existing = ClassCountOverride(
            academic_period_id=period_id,
            course_id=course_id,
            study_program_id=program_id,
            class_count=payload.class_count,
        )
        db.add(existing)
        created = True
    else:
        existing.class_count = payload.class_count
        created = False
    await db.flush()
    if changed:
        await bump_input_revisions(db, period_id, {program_id})

    return ClassCountOverrideResponse(
        override_id=str(existing.id),
        academic_period_id=str(period_id),
        course_id=str(course_id),
        study_program_id=str(program_id),
        class_count=payload.class_count,
        created=created,
    )


@router.get("/scheduling/unassigned")
async def list_unassigned(
    academic_period_id: str | None = None,
    study_program_id: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    denied = _require_scheduler(current_user)
    if denied is not None:
        return denied

    requested = None
    if study_program_id is not None:
        requested = _parse_id(study_program_id, "study_program_id")
        if not isinstance(requested, UUID):
            return requested

    if current_user.role == "admin":
        scope = requested
    else:
        profile = current_user.lecturer_profile
        scope = profile.study_program_id if profile is not None else None
        if scope is None:
            return error_response(
                status.HTTP_403_FORBIDDEN,
                "forbidden",
                "PJ Prodi belum memiliki program studi.",
                detail="PJ Prodi belum memiliki program studi.",
            )
        if requested is not None and requested != scope:
            return error_response(
                status.HTTP_403_FORBIDDEN,
                "akses_prodi_ditolak",
                "PJ hanya dapat melihat diagnosis prodinya sendiri.",
                detail="PJ hanya dapat melihat diagnosis prodinya sendiri.",
            )
    scope_value = str(scope) if scope is not None else None

    period = await _resolve_period(db, academic_period_id)
    if not isinstance(period, AcademicPeriod):
        return period

    latest_run = (
        await db.execute(
            select(ScheduleRun)
            .where(ScheduleRun.academic_period_id == period.academic_period_id)
            .order_by(
                func.coalesce(ScheduleRun.ended_at, ScheduleRun.started_at).desc(),
                ScheduleRun.run_id.desc(),
            )
            .limit(1)
        )
    ).scalars().first()
    if latest_run is None:
        return {
            "data": [],
            "meta": {
                "total": 0,
                "academic_period_id": str(period.academic_period_id),
                "study_program_id": scope_value,
                "run_id": None,
            },
        }

    rows = (
        await db.execute(
            select(UnassignedClass, ClassSection, Course)
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
            .where(UnassignedClass.run_id == latest_run.run_id)
            .order_by(Course.course_code, ClassSection.section_code)
        )
    ).all()

    entries = [
        (section.class_section_id, course.course_code, unassigned.reason)
        for unassigned, section, course in rows
    ]
    data = [
        item.model_dump(mode="json")
        for item in await enrich_unassigned_items(
            db, period.academic_period_id, entries
        )
    ]
    if scope_value is not None:
        data = [
            item
            for item in data
            if any(
                context["study_program_id"] == scope_value
                for context in item["eligible_curriculum_contexts"]
            )
        ]

    return {
        "data": data,
        "meta": {
            "total": len(data),
            "academic_period_id": str(period.academic_period_id),
            "study_program_id": scope_value,
            "run_id": str(latest_run.run_id),
            "mode": latest_run.mode,
            "stats": latest_run.stats,
        },
    }
