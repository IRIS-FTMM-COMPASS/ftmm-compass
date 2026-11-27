"""Ketersediaan MK Pilihan yang dikelola PJ prodi."""

from collections import defaultdict
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.errors import error_response
from audit import record_admin_action
from auth import get_current_user
from catalog import authoritative_curriculum_id, normalize_course_type, normalize_prodi
from database import get_db
from models import (
    AcademicPeriod,
    ClassCountOverride,
    ClassSection,
    Course,
    CourseOffering,
    Curriculum,
    CurriculumCourse,
    ElectiveCourseVote,
    ElectivePollingPeriod,
    OfferingComponent,
    SchedulePeriodLock,
    StudyProgram,
    User,
)
from prodi_access import require_pj_scope
from schemas import CourseQuotaResponse, CourseQuotaUpdateRequest
from scheduling_common import current_period_id

router = APIRouter()

SHARED_SCOPES = ("fakultas", "universitas")


class CourseAvailabilityUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_active: bool = Field(strict=True)
    reason: Optional[str] = None


def _deny(status_code: int, code: str, message: str) -> JSONResponse:
    return error_response(status_code, code, message, detail=message)


def _require_pj(current_user: User, db: AsyncSession):
    """Kembalikan prodi PJ canonical atau envelope penolakan."""
    if current_user.role != "lecturer":
        return None, _deny(
            status.HTTP_403_FORBIDDEN,
            "forbidden",
            "Kelola ketersediaan MK hanya tersedia untuk PJ prodi.",
        )
    scope = require_pj_scope(current_user, db, None)
    if isinstance(scope, JSONResponse):
        return None, scope
    return scope, None


def _availability_select():
    return (
        select(
            CurriculumCourse.curriculum_course_id.label("curriculum_course_id"),
            CurriculumCourse.course_id.label("course_id"),
            Course.course_code.label("course_code"),
            Course.course_name.label("course_name"),
            CurriculumCourse.credits_total.label("credits"),
            CurriculumCourse.recommended_semester.label("recommended_semester"),
            CurriculumCourse.course_type.label("course_type"),
            CurriculumCourse.course_scope.label("course_scope"),
            CurriculumCourse.is_active.label("is_active"),
            Curriculum.curriculum_id.label("curriculum_id"),
            StudyProgram.program_name.label("program_name"),
            Curriculum.study_program_id.label("study_program_id"),
        )
        .join(Course, Course.course_id == CurriculumCourse.course_id)
        .join(Curriculum, Curriculum.curriculum_id == CurriculumCourse.curriculum_id)
        .join(
            StudyProgram,
            StudyProgram.study_program_id == Curriculum.study_program_id,
        )
    )


async def _quota_map(
    db: AsyncSession, academic_period_id: UUID, course_ids: list[UUID]
) -> dict[UUID, dict[str, Any]]:
    """Kuota kelas dan jumlah peminat per MK untuk satu periode akademik."""
    if not course_ids:
        return {}

    code_rows = (
        await db.execute(
            select(Course.course_id, Course.course_code).where(
                Course.course_id.in_(course_ids)
            )
        )
    ).all()
    codes = {course_id: course_code for course_id, course_code in code_rows}
    if not codes:
        return {}

    curriculum_rows = (
        await db.execute(
            select(CurriculumCourse.course_id, Curriculum.study_program_id)
            .join(
                Curriculum,
                Curriculum.curriculum_id == CurriculumCourse.curriculum_id,
            )
            .where(CurriculumCourse.course_id.in_(course_ids))
        )
    ).all()
    programs_by_course: dict[Any, set[Any]] = defaultdict(set)
    for course_id, program_id in curriculum_rows:
        programs_by_course[course_id].add(program_id)

    overrides = (
        await db.execute(
            select(ClassCountOverride).where(
                ClassCountOverride.academic_period_id == academic_period_id,
                ClassCountOverride.course_id.in_(course_ids),
            )
        )
    ).scalars().all()
    override_counts: dict[Any, int] = {}
    for override in overrides:
        allowed_programs = programs_by_course.get(override.course_id)
        if allowed_programs and override.study_program_id not in allowed_programs:
            continue
        override_counts[override.course_id] = max(
            override_counts.get(override.course_id, 0),
            max(int(override.class_count), 1),
        )

    section_rows = (
        await db.execute(
            select(CourseOffering.course_id, ClassSection.capacity)
            .join(
                OfferingComponent,
                OfferingComponent.course_offering_id
                == CourseOffering.course_offering_id,
            )
            .join(
                ClassSection,
                ClassSection.offering_component_id
                == OfferingComponent.offering_component_id,
            )
            .where(
                CourseOffering.academic_period_id == academic_period_id,
                CourseOffering.course_id.in_(course_ids),
            )
        )
    ).all()
    sections_by_course: dict[Any, list[Any]] = defaultdict(list)
    for course_id, capacity in section_rows:
        sections_by_course[course_id].append(capacity)

    vote_rows = (
        await db.execute(
            select(
                ElectiveCourseVote.course_id,
                ElectiveCourseVote.course_code,
                func.count(ElectiveCourseVote.vote_id),
            )
            .join(
                ElectivePollingPeriod,
                ElectivePollingPeriod.polling_period_id
                == ElectiveCourseVote.polling_period_id,
            )
            .where(
                ElectivePollingPeriod.status == "open",
                or_(
                    ElectiveCourseVote.course_id.in_(
                        [str(course_id) for course_id in codes]
                    ),
                    ElectiveCourseVote.course_code.in_(list(codes.values())),
                ),
            )
            .group_by(
                ElectiveCourseVote.course_id, ElectiveCourseVote.course_code
            )
        )
    ).all()
    enrolled: dict[Any, int] = defaultdict(int)
    for vote_course_id, vote_code, total in vote_rows:
        for course_id, code in codes.items():
            if vote_course_id == str(course_id) or vote_code == code:
                enrolled[course_id] += int(total)

    result: dict[Any, dict[str, Any]] = {}
    for course_id in course_ids:
        capacities = [
            capacity
            for capacity in sections_by_course[course_id]
            if capacity is not None
        ]
        result[course_id] = {
            "class_count": override_counts.get(course_id)
            or max(len(sections_by_course[course_id]), 1),
            "capacity_per_class": max(capacities) if capacities else 40,
            "enrolled_count": enrolled[course_id],
        }
    return result


async def _resolve_academic_period(db: AsyncSession, period_id: Optional[str]):
    stmt = select(AcademicPeriod)
    if period_id:
        try:
            wanted = UUID(period_id)
        except (ValueError, AttributeError, TypeError):
            return None
        stmt = stmt.where(AcademicPeriod.academic_period_id == wanted)
    else:
        stmt = (
            stmt.where(AcademicPeriod.is_active.is_(True))
            .order_by(
                AcademicPeriod.academic_year_start.desc(),
                AcademicPeriod.created_at.desc(),
            )
        )
    return (await db.execute(stmt)).scalars().first()


async def _krs_lock_error(
    db: AsyncSession, academic_period_id: Optional[UUID]
) -> Optional[JSONResponse]:
    if academic_period_id is None:
        return None
    lock = await db.get(SchedulePeriodLock, academic_period_id)
    if lock is not None and lock.krs_open:
        return _deny(
            status.HTTP_409_CONFLICT,
            "scheduling_locked",
            "Jadwal periode ini sudah difinalisasi.",
        )
    return None


def _item(
    row: Any,
    target_semester: int,
    scope: Optional[str] = None,
    quota: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    course_type = normalize_course_type(row["course_type"])
    semester = row["recommended_semester"]
    is_active = bool(row["is_active"])
    own_program = scope is None or _is_own_program(row, scope)
    can_toggle = (
        own_program
        and course_type == "Pilihan"
        and (semester is None or semester >= target_semester)
    )
    quota = quota or {}
    class_count = int(quota.get("class_count", 1))
    capacity_per_class = int(quota.get("capacity_per_class", 40))

    if not own_program:
        lock_reason: Optional[str] = "prodi_lain"
    elif semester is not None and semester < target_semester:
        lock_reason = "semester_berjalan"
    elif course_type != "Pilihan":
        lock_reason = "bukan_pilihan"
    elif not is_active:
        lock_reason = "dinonaktifkan"
    else:
        lock_reason = None

    return {
        "curriculum_course_id": str(row["curriculum_course_id"]),
        "course_id": str(row["course_id"]),
        "course_code": row["course_code"],
        "course_name": row["course_name"],
        "credits": row["credits"] or 0,
        "semester": semester,
        "type": course_type,
        "course_scope": row["course_scope"],
        "is_active": is_active,
        "can_toggle": can_toggle,
        "lock_reason": lock_reason,
        "class_count": class_count,
        "capacity_per_class": capacity_per_class,
        "total_quota": class_count * capacity_per_class,
        "enrolled_count": int(quota.get("enrolled_count", 0)),
    }


async def _resolve_period(db: AsyncSession, period_id: Optional[str] = None):
    stmt = select(ElectivePollingPeriod)
    if period_id:
        try:
            wanted = UUID(period_id)
        except (ValueError, AttributeError, TypeError):
            return None
        stmt = stmt.where(ElectivePollingPeriod.polling_period_id == wanted)
    else:
        stmt = stmt.where(ElectivePollingPeriod.status == "open").order_by(
            ElectivePollingPeriod.created_at.desc()
        )
    return (await db.execute(stmt)).scalars().first()


def _is_own_program(row: Any, scope: Optional[str]) -> bool:
    row_program = normalize_prodi(row["program_name"]) or row["program_name"]
    own_program = normalize_prodi(scope) or scope
    return row_program == own_program


@router.get("/pj/course-availability")
async def get_course_availability(
    period_id: Optional[str] = None,
    semester: Optional[int] = Query(None, ge=1, le=8),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope, denial = _require_pj(current_user, db)
    if denial is not None:
        return denial

    period = await _resolve_period(db, period_id)
    if period is None:
        return _deny(
            status.HTTP_404_NOT_FOUND,
            "polling_period_not_found",
            "Periode polling pra-KRS tidak ditemukan.",
        )

    target_semester = semester if semester is not None else int(period.target_semester)
    curriculum_id = await authoritative_curriculum_id(db, scope or "")
    stmt = _availability_select().where(
        or_(
            CurriculumCourse.curriculum_id == curriculum_id,
            CurriculumCourse.course_scope.in_(SHARED_SCOPES),
        )
    )
    order = []
    if curriculum_id is not None:
        order.append(
            case((CurriculumCourse.curriculum_id == curriculum_id, 0), else_=1)
        )
    order.extend(
        (
            CurriculumCourse.recommended_semester.asc().nullslast(),
            Course.course_code.asc(),
        )
    )
    rows = (await db.execute(stmt.order_by(*order))).mappings().all()
    unique_course_ids = list(dict.fromkeys(row["course_id"] for row in rows))
    academic_period_id = await current_period_id(db)
    quota_by_course = (
        await _quota_map(db, academic_period_id, unique_course_ids)
        if academic_period_id is not None
        else {}
    )

    items: list[dict[str, Any]] = []
    seen: set[Any] = set()
    for row in rows:
        course_id = row["course_id"]
        if course_id in seen:
            continue
        seen.add(course_id)
        items.append(
            _item(row, target_semester, scope, quota_by_course.get(course_id))
        )

    return {
        "data": items,
        "meta": {
            "period_id": str(period.polling_period_id),
            "target_semester": target_semester,
            "study_program": scope,
            "total": len(items),
        },
    }


@router.patch("/pj/course-availability/{curriculum_course_id}")
async def update_course_availability(
    curriculum_course_id: str,
    payload: CourseAvailabilityUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope, denial = _require_pj(current_user, db)
    if denial is not None:
        return denial

    period = await _resolve_period(db)
    if period is None:
        return _deny(
            status.HTTP_404_NOT_FOUND,
            "polling_period_not_found",
            "Periode polling pra-KRS tidak ditemukan.",
        )

    try:
        wanted = UUID(curriculum_course_id)
    except (ValueError, AttributeError, TypeError):
        return _deny(
            status.HTTP_404_NOT_FOUND, "not_found", "MK kurikulum tidak ditemukan."
        )

    row = (
        await db.execute(
            _availability_select().where(
                CurriculumCourse.curriculum_course_id == wanted
            )
        )
    ).mappings().first()
    if row is None:
        return _deny(status.HTTP_404_NOT_FOUND, "not_found", "MK kurikulum tidak ditemukan.")

    if not _is_own_program(row, scope):
        return _deny(
            status.HTTP_403_FORBIDDEN,
            "prodi_mismatch",
            "PJ hanya dapat mengubah MK prodinya sendiri.",
        )

    semester = row["recommended_semester"]
    if semester is not None and semester < int(period.target_semester):
        return _deny(
            status.HTTP_409_CONFLICT,
            "semester_not_eligible",
            "MK semester berjalan tidak dapat diubah.",
        )

    if normalize_course_type(row["course_type"]) != "Pilihan":
        return _deny(
            422,
            "not_elective",
            "Hanya MK Pilihan yang dapat diatur ketersediaannya.",
        )
    active_period_id = await current_period_id(db)
    locked = await _krs_lock_error(db, active_period_id)
    if locked is not None:
        return locked

    course = (
        await db.execute(
            select(CurriculumCourse).where(
                CurriculumCourse.curriculum_course_id == wanted
            )
        )
    ).scalars().one()
    old_value = bool(course.is_active)
    course.is_active = payload.is_active
    if row["course_scope"] == "program_studi":
        catalog_course = (
            await db.execute(
                select(Course).where(Course.course_id == row["course_id"])
            )
        ).scalars().one()
        catalog_course.is_active = payload.is_active
    await record_admin_action(
        db,
        actor=current_user,
        target=current_user,
        action="course_availability_change",
        reason=payload.reason or "",
        field_name=f"curriculum_course:{curriculum_course_id}",
        old_value=str(old_value).lower(),
        new_value=str(payload.is_active).lower(),
    )
    await db.commit()
    await db.refresh(course)

    refreshed = dict(row)
    refreshed["is_active"] = course.is_active
    quota_by_course = (
        await _quota_map(db, active_period_id, [row["course_id"]])
        if active_period_id is not None
        else {}
    )
    return _item(
        refreshed,
        int(period.target_semester),
        quota=quota_by_course.get(row["course_id"]),
    )


@router.put(
    "/pj/course-availability/{curriculum_course_id}/quota",
    response_model=CourseQuotaResponse,
)
async def update_course_quota(
    curriculum_course_id: str,
    payload: CourseQuotaUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope, denial = _require_pj(current_user, db)
    if denial is not None:
        return denial

    try:
        wanted = UUID(curriculum_course_id)
    except (ValueError, AttributeError, TypeError):
        return _deny(
            status.HTTP_404_NOT_FOUND, "not_found", "MK kurikulum tidak ditemukan."
        )

    row = (
        await db.execute(
            _availability_select().where(
                CurriculumCourse.curriculum_course_id == wanted
            )
        )
    ).mappings().first()
    if row is None:
        return _deny(
            status.HTTP_404_NOT_FOUND, "not_found", "MK kurikulum tidak ditemukan."
        )
    if not _is_own_program(row, scope):
        return _deny(
            status.HTTP_403_FORBIDDEN,
            "prodi_mismatch",
            "PJ hanya dapat mengatur kuota MK prodinya sendiri.",
        )

    period = await _resolve_academic_period(db, payload.academic_period_id)
    if period is None:
        return _deny(
            status.HTTP_404_NOT_FOUND,
            "period_not_found",
            "Periode akademik tidak ditemukan.",
        )

    locked = await _krs_lock_error(db, period.academic_period_id)
    if locked is not None:
        return locked

    quota_by_course = await _quota_map(
        db, period.academic_period_id, [row["course_id"]]
    )
    enrolled_count = quota_by_course.get(row["course_id"], {}).get(
        "enrolled_count", 0
    )
    total_quota = payload.class_count * payload.capacity_per_class
    if enrolled_count > total_quota:
        message = (
            "Jumlah kelas dan kapasitas tidak boleh lebih rendah dari jumlah "
            "mahasiswa yang terdaftar."
        )
        return error_response(
            422,
            "quota_below_enrollment",
            message,
            detail=message,
            details=[
                {
                    "field": "class_count",
                    "message": message,
                    "code": "quota_below_enrollment",
                }
            ],
        )

    override = (
        await db.execute(
            select(ClassCountOverride).where(
                ClassCountOverride.academic_period_id == period.academic_period_id,
                ClassCountOverride.course_id == row["course_id"],
                ClassCountOverride.study_program_id == row["study_program_id"],
            )
        )
    ).scalars().first()
    created = override is None
    old_count: Optional[int] = None
    if created:
        override = ClassCountOverride(
            academic_period_id=period.academic_period_id,
            course_id=row["course_id"],
            study_program_id=row["study_program_id"],
            class_count=payload.class_count,
        )
        db.add(override)
    else:
        old_count = int(override.class_count)
        override.class_count = payload.class_count

    sections = (
        await db.execute(
            select(ClassSection)
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
            .where(
                CourseOffering.academic_period_id == period.academic_period_id,
                CourseOffering.course_id == row["course_id"],
            )
        )
    ).scalars().all()
    for section in sections:
        section.capacity = payload.capacity_per_class

    await record_admin_action(
        db,
        actor=current_user,
        target=current_user,
        action="course_quota_change",
        reason=payload.reason or "",
        field_name=f"curriculum_course:{curriculum_course_id}",
        old_value=str(old_count) if old_count is not None else None,
        new_value=str(payload.class_count),
    )
    await db.commit()

    return CourseQuotaResponse(
        curriculum_course_id=str(wanted),
        study_program_id=str(row["study_program_id"]),
        academic_period_id=str(period.academic_period_id),
        class_count=payload.class_count,
        capacity_per_class=payload.capacity_per_class,
        total_quota=total_quota,
        enrolled_count=enrolled_count,
        created=created,
    )
