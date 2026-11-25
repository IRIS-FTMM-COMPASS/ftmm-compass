"""Orkestrasi domain pembangkitan jadwal, override jumlah kelas, dan diagnosis."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

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
)
from schemas import GenerateRequest, GenerateResponse
from scheduling_common import all_study_program_ids, current_period_id

from ..scheduler import (
    bump_input_revisions,
    enrich_unassigned_items,
    generate_schedule,
    scheduling_input_lock,
)
from . import UNPROCESSABLE
from .errors import ServiceError


@dataclass(frozen=True)
class UnassignedResult:
    data: list[dict[str, Any]]
    academic_period_id: UUID
    study_program_id: str | None
    run_id: UUID | None
    mode: str | None = None
    stats: Any = None


def _failure(status_code: int, code: str, message: str) -> ServiceError:
    return ServiceError(status_code, code, message)


def field_failure(
    field: str, message: str, code: str = "validation_error"
) -> ServiceError:
    envelope = "Data yang dikirim tidak valid."
    return ServiceError(
        UNPROCESSABLE,
        code,
        envelope,
        [{"field": field, "message": message, "code": code}],
    )


def parse_id(value: str, field: str) -> UUID | ServiceError:
    try:
        return UUID(value)
    except (ValueError, AttributeError, TypeError):
        return field_failure(field, f"{field} bukan UUID yang valid.")


async def resolve_period(
    db: AsyncSession, requested: str | None
) -> AcademicPeriod | ServiceError:
    if requested:
        period_id = parse_id(requested, "academic_period_id")
        if isinstance(period_id, ServiceError):
            return period_id
        period = await db.get(AcademicPeriod, period_id)
    else:
        active_id = await current_period_id(db)
        period = await db.get(AcademicPeriod, active_id) if active_id else None
    if period is None:
        return _failure(
            status.HTTP_404_NOT_FOUND,
            "period_not_found",
            "Periode akademik tidak ditemukan.",
        )
    return period


async def krs_lock_error(
    db: AsyncSession, period: AcademicPeriod, message: str
) -> ServiceError | None:
    """409 bersama saat KRS sudah dibuka untuk generate maupun override."""
    lock = await db.get(SchedulePeriodLock, period.academic_period_id)
    if lock is not None and lock.krs_open:
        return _failure(status.HTTP_409_CONFLICT, "scheduling_locked", message)
    return None


async def _generate_scope(
    db: AsyncSession,
    payload: GenerateRequest,
    is_admin: bool,
    actor_scope: UUID | None,
) -> UUID | None | ServiceError:
    if payload.mode == "full_reset":
        if payload.study_program_id is not None:
            return field_failure(
                "study_program_id",
                "Mode full_reset selalu mencakup seluruh prodi.",
                "invalid_full_reset_scope",
            )
        return None
    if not is_admin:
        if payload.study_program_id is not None:
            requested = parse_id(payload.study_program_id, "study_program_id")
            if isinstance(requested, ServiceError):
                return requested
            if requested != actor_scope:
                return _failure(
                    status.HTTP_403_FORBIDDEN,
                    "akses_prodi_ditolak",
                    "PJ hanya dapat membangkitkan jadwal prodinya sendiri.",
                )
        return actor_scope
    if payload.study_program_id is None:
        return None
    scope = parse_id(payload.study_program_id, "study_program_id")
    if isinstance(scope, ServiceError):
        return scope
    if await db.get(StudyProgram, scope) is None:
        return _failure(
            status.HTTP_404_NOT_FOUND,
            "study_program_not_found",
            "Program studi tidak ditemukan.",
        )
    return scope


async def generate(
    db: AsyncSession,
    payload: GenerateRequest,
    actor_id: UUID,
    is_admin: bool,
    actor_scope: UUID | None,
) -> GenerateResponse | ServiceError:
    period = await resolve_period(db, payload.academic_period_id)
    if isinstance(period, ServiceError):
        return period
    locked = await krs_lock_error(
        db, period, "KRS sudah dibuka; jadwal periode ini tidak dapat diubah."
    )
    if locked is not None:
        return locked
    scope = await _generate_scope(db, payload, is_admin, actor_scope)
    if isinstance(scope, ServiceError):
        return scope
    if scope is not None or payload.mode == "full_reset":
        locked = await scheduling_input_lock(
            db,
            period.academic_period_id,
            {scope} if scope is not None else None,
        )
        if locked is not None:
            code, message = locked
            return _failure(409, code, message)
    return await generate_schedule(
        db,
        period,
        mode=payload.mode,
        triggered_by=actor_id,
        study_program_id=scope,
    )


async def put_class_count_override(
    db: AsyncSession,
    payload: Any,
    is_admin: bool,
    actor_program_id: UUID | None,
) -> tuple[ClassCountOverride, bool] | ServiceError:
    period_id = (
        parse_id(payload.academic_period_id, "academic_period_id")
        if payload.academic_period_id
        else await current_period_id(db)
    )
    if period_id is None:
        return _failure(
            status.HTTP_404_NOT_FOUND,
            "period_not_found",
            "Tidak ada periode akademik aktif.",
        )
    if isinstance(period_id, ServiceError):
        return period_id
    course_id = parse_id(payload.course_id, "course_id")
    program_id = parse_id(payload.study_program_id, "study_program_id")
    for candidate in (course_id, program_id):
        if isinstance(candidate, ServiceError):
            return candidate
    if not is_admin and actor_program_id != program_id:
        return _failure(
            status.HTTP_403_FORBIDDEN,
            "akses_prodi_ditolak",
            "PJ hanya dapat mengatur jumlah kelas prodinya sendiri.",
        )

    period = await db.get(AcademicPeriod, period_id)
    course = await db.get(Course, course_id)
    program = await db.get(StudyProgram, program_id)
    if period is None:
        return _failure(
            status.HTTP_404_NOT_FOUND,
            "period_not_found",
            "Periode akademik tidak ditemukan.",
        )
    if course is None:
        return _failure(
            status.HTTP_404_NOT_FOUND,
            "course_not_found",
            "Mata kuliah tidak ditemukan.",
        )
    if program is None:
        return _failure(
            status.HTTP_404_NOT_FOUND,
            "study_program_not_found",
            "Program studi tidak ditemukan.",
        )

    locked = await krs_lock_error(
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

    actor_final = False
    if actor_program_id is not None:
        actor_status = await db.get(
            ScheduleProgramStatus, (period.academic_period_id, actor_program_id)
        )
        actor_final = actor_status is not None and actor_status.state == "final"
    if all_final or actor_final:
        return _failure(
            status.HTTP_409_CONFLICT,
            "schedule_final",
            "Jadwal sudah final; jumlah kelas tidak dapat diubah.",
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
        return _failure(
            status.HTTP_404_NOT_FOUND,
            "course_not_in_prodi",
            "Mata kuliah tidak termasuk kurikulum program studi ini.",
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
    return existing, created


async def list_unassigned(
    db: AsyncSession,
    period: AcademicPeriod,
    scope: UUID | None,
) -> UnassignedResult:
    scope_value = str(scope) if scope is not None else None

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
        return UnassignedResult([], period.academic_period_id, scope_value, None)

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
    return UnassignedResult(
        data,
        period.academic_period_id,
        scope_value,
        latest_run.run_id,
        mode=latest_run.mode,
        stats=latest_run.stats,
    )
