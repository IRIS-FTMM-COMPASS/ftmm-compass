"""Ketersediaan MK Pilihan yang dikelola PJ prodi."""

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.errors import error_response
from audit import record_admin_action
from auth import get_current_user
from catalog import authoritative_curriculum_id, normalize_course_type, normalize_prodi
from database import get_db
from models import (
    Course,
    Curriculum,
    CurriculumCourse,
    ElectivePollingPeriod,
    StudyProgram,
    User,
)
from prodi_access import require_pj_scope

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
        )
        .join(Course, Course.course_id == CurriculumCourse.course_id)
        .join(Curriculum, Curriculum.curriculum_id == CurriculumCourse.curriculum_id)
        .join(
            StudyProgram,
            StudyProgram.study_program_id == Curriculum.study_program_id,
        )
    )


def _item(row: Any, target_semester: int) -> dict[str, Any]:
    course_type = normalize_course_type(row["course_type"])
    semester = row["recommended_semester"]
    is_active = bool(row["is_active"])
    can_toggle = course_type == "Pilihan" and (
        semester is None or semester >= target_semester
    )

    if semester is not None and semester < target_semester:
        lock_reason: Optional[str] = "semester_berjalan"
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

    items: list[dict[str, Any]] = []
    seen: set[Any] = set()
    for row in rows:
        course_id = row["course_id"]
        if course_id in seen:
            continue
        seen.add(course_id)
        items.append(_item(row, target_semester))

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

    if not _is_own_program(row, scope) and row["course_scope"] not in SHARED_SCOPES:
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

    course = (
        await db.execute(
            select(CurriculumCourse).where(
                CurriculumCourse.curriculum_course_id == wanted
            )
        )
    ).scalars().one()
    old_value = bool(course.is_active)
    course.is_active = payload.is_active
    await db.commit()

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
    return _item(refreshed, int(period.target_semester))
