"""Pemetaan referensi nama dosen di katalog ke akun dosen nyata.

Nama free-text PJ MK dan Tim Pengajar tetap tampil walau belum terpetakan.
Akun yang dipetakan harus memiliki LecturerProfile agar penjadwal dapat
menegakkan aturan ketersediaan dan beban dosen tanpa tabrakan identitas.
"""

import uuid

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.errors import error_response
from auth import get_current_user
from database import get_db
from models import (
    Course,
    CourseInstructorReference,
    CurriculumCourse,
    User,
)
from schemas import (
    InstructorMappingRequest,
    InstructorReferenceListResponse,
    InstructorReferenceResponse,
)

router = APIRouter()

_UNPROCESSABLE = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)

_REFERENCE_SELECT = (
    select(
        CourseInstructorReference,
        Course.course_code.label("course_code"),
        Course.course_name.label("course_name"),
        User.full_name.label("lecturer_name"),
    )
    .outerjoin(
        CurriculumCourse,
        CurriculumCourse.curriculum_course_id
        == CourseInstructorReference.curriculum_course_id,
    )
    .outerjoin(Course, Course.course_id == CurriculumCourse.course_id)
    .outerjoin(User, User.user_id == CourseInstructorReference.user_id)
)


def _deny(status_code: int, code: str, message: str) -> JSONResponse:
    return error_response(status_code, code, message, detail=message)


def _field_error(field: str, message: str, code: str) -> JSONResponse:
    return error_response(
        _UNPROCESSABLE,
        code,
        message,
        detail=message,
        details=[{"field": field, "message": message, "code": code}],
    )


def _require_admin(current_user: User) -> JSONResponse | None:
    if current_user.role != "admin":
        return _deny(
            status.HTTP_403_FORBIDDEN,
            "forbidden",
            "Pemetaan referensi dosen hanya tersedia untuk admin.",
        )
    return None


def _reference_response(row) -> InstructorReferenceResponse:
    reference = row[0]
    return InstructorReferenceResponse(
        reference_id=str(reference.instructor_reference_id),
        instructor_name=reference.instructor_name,
        instructor_role=reference.instructor_role,
        course_code=row.course_code,
        course_name=row.course_name,
        user_id=str(reference.user_id) if reference.user_id is not None else None,
        is_mapped=reference.user_id is not None,
        lecturer_name=row.lecturer_name if reference.user_id is not None else None,
    )


@router.get(
    "/scheduling/instructor-references",
    response_model=InstructorReferenceListResponse,
)
async def list_instructor_references(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    denied = _require_admin(current_user)
    if denied is not None:
        return denied

    rows = (
        await db.execute(
            _REFERENCE_SELECT.order_by(
                Course.course_code,
                CourseInstructorReference.instructor_name,
                CourseInstructorReference.instructor_reference_id,
            )
        )
    ).all()
    items = [_reference_response(row) for row in rows]
    return InstructorReferenceListResponse(
        data=items,
        meta={
            "total": len(items),
            "mapped": sum(1 for item in items if item.is_mapped),
            "unmapped": sum(1 for item in items if not item.is_mapped),
        },
    )


@router.patch(
    "/scheduling/instructor-references/{reference_id}",
    response_model=InstructorReferenceResponse,
)
async def map_instructor_reference(
    reference_id: uuid.UUID,
    payload: InstructorMappingRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    denied = _require_admin(current_user)
    if denied is not None:
        return denied

    row = (
        await db.execute(
            _REFERENCE_SELECT.where(
                CourseInstructorReference.instructor_reference_id == reference_id
            )
        )
    ).first()
    if row is None:
        return _deny(
            status.HTTP_404_NOT_FOUND,
            "reference_not_found",
            "Referensi dosen tidak ditemukan.",
        )

    reference = row[0]
    if payload.user_id is None:
        reference.user_id = None
    else:
        try:
            user_id = uuid.UUID(str(payload.user_id))
        except (ValueError, TypeError, AttributeError):
            return _field_error("user_id", "ID akun dosen tidak valid.", "invalid_uuid")

        target = (
            await db.execute(
                select(User)
                .options(selectinload(User.lecturer_profile))
                .where(User.user_id == user_id)
            )
        ).scalars().first()
        if target is None or target.lecturer_profile is None:
            return _field_error(
                "user_id",
                "Akun yang dipilih bukan dosen.",
                "not_lecturer",
            )
        reference.user_id = target.user_id

    await db.commit()
    updated = (
        await db.execute(
            _REFERENCE_SELECT.where(
                CourseInstructorReference.instructor_reference_id == reference_id
            )
        )
    ).first()
    return _reference_response(updated)
