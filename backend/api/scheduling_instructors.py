"""Pemetaan referensi nama dosen di katalog ke akun dosen nyata.

Nama free-text PJ MK dan Tim Pengajar tetap tampil walau belum terpetakan.
Akun yang dipetakan harus memiliki LecturerProfile agar penjadwal dapat
menegakkan aturan ketersediaan dan beban dosen tanpa tabrakan identitas.
"""

import uuid

from fastapi import APIRouter, Depends, Request, status
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
    Curriculum,
    CurriculumCourse,
    User,
)
from schemas import (
    CurriculumCourseListResponse,
    InstructorReferenceCreateRequest,
    InstructorReferenceListResponse,
    InstructorReferenceResponse,
    InstructorReferenceUpdateRequest,
)

router = APIRouter()

_UNPROCESSABLE = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)

_REFERENCE_SELECT = (
    select(
        CourseInstructorReference,
        Course.course_code.label("course_code"),
        Course.course_name.label("course_name"),
        User.full_name.label("lecturer_name"),
        Curriculum.study_program_id.label("program_id"),
    )
    .outerjoin(
        CurriculumCourse,
        CurriculumCourse.curriculum_course_id
        == CourseInstructorReference.curriculum_course_id,
    )
    .outerjoin(Curriculum, Curriculum.curriculum_id == CurriculumCourse.curriculum_id)
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


async def _present_keys(request: Request) -> set[str]:
    try:
        raw = await request.json()
    except Exception:
        return set()
    return set(raw) if isinstance(raw, dict) else set()


def _read_scope(current_user: User) -> uuid.UUID | None | JSONResponse:
    """None berarti admin; UUID membatasi PJ pada prodinya."""
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
    return _deny(
        status.HTTP_403_FORBIDDEN,
        "forbidden",
        "Referensi pengajar hanya tersedia untuk admin dan PJ Prodi.",
    )


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


async def _resolve_lecturer(
    db: AsyncSession, raw: str | None
) -> uuid.UUID | None | JSONResponse:
    if raw is None:
        return None
    try:
        user_id = uuid.UUID(str(raw))
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
        return _field_error("user_id", "Akun yang dipilih bukan dosen.", "not_lecturer")
    return target.user_id


async def _resolve_curriculum_course(
    db: AsyncSession, raw: str, scope: uuid.UUID | None
) -> uuid.UUID | JSONResponse:
    try:
        curriculum_course_id = uuid.UUID(str(raw))
    except (ValueError, TypeError, AttributeError):
        return _field_error(
            "curriculum_course_id", "Mata kuliah tidak valid.", "invalid_uuid"
        )

    curriculum_course = (
        await db.execute(
            select(CurriculumCourse, Curriculum.study_program_id.label("program_id"))
            .join(
                Curriculum, Curriculum.curriculum_id == CurriculumCourse.curriculum_id
            )
            .where(
                CurriculumCourse.curriculum_course_id == curriculum_course_id,
                CurriculumCourse.is_active.is_(True),
            )
        )
    ).first()
    if curriculum_course is None:
        return _deny(
            status.HTTP_404_NOT_FOUND,
            "curriculum_course_not_found",
            "Mata kuliah tidak ditemukan.",
        )
    if scope is not None and curriculum_course.program_id != scope:
        return _deny(
            status.HTTP_403_FORBIDDEN,
            "forbidden",
            "Mata kuliah di luar program studi Anda.",
        )
    return curriculum_course_id


async def _find_reference(
    db: AsyncSession, reference_id: uuid.UUID, scope: uuid.UUID | None
):
    row = (
        await db.execute(
            _REFERENCE_SELECT.where(
                CourseInstructorReference.instructor_reference_id == reference_id
            )
        )
    ).first()
    if row is not None and scope is not None and row.program_id != scope:
        return _deny(
            status.HTTP_403_FORBIDDEN,
            "forbidden",
            "Referensi dosen di luar program studi Anda.",
        )
    return row


@router.get(
    "/scheduling/instructor-references",
    response_model=InstructorReferenceListResponse,
)
async def list_instructor_references(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope = _read_scope(current_user)
    if isinstance(scope, JSONResponse):
        return scope

    stmt = _REFERENCE_SELECT
    if scope is not None:
        stmt = stmt.where(Curriculum.study_program_id == scope)
    rows = (
        await db.execute(
            stmt.order_by(
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


@router.post(
    "/scheduling/instructor-references",
    response_model=InstructorReferenceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_instructor_reference(
    payload: InstructorReferenceCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope = _read_scope(current_user)
    if isinstance(scope, JSONResponse):
        return scope

    curriculum_course_id = await _resolve_curriculum_course(
        db, payload.curriculum_course_id, scope
    )
    if isinstance(curriculum_course_id, JSONResponse):
        return curriculum_course_id

    user_id = await _resolve_lecturer(db, payload.user_id)
    if isinstance(user_id, JSONResponse):
        return user_id

    reference = CourseInstructorReference(
        curriculum_course_id=curriculum_course_id,
        instructor_name=payload.instructor_name.strip(),
        instructor_role=payload.instructor_role,
        user_id=user_id,
    )
    db.add(reference)
    await db.commit()
    row = await _find_reference(db, reference.instructor_reference_id, None)
    return _reference_response(row)


@router.patch(
    "/scheduling/instructor-references/{reference_id}",
    response_model=InstructorReferenceResponse,
)
async def map_instructor_reference(
    reference_id: uuid.UUID,
    payload: InstructorReferenceUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope = _read_scope(current_user)
    if isinstance(scope, JSONResponse):
        return scope

    row = await _find_reference(db, reference_id, scope)
    if isinstance(row, JSONResponse):
        return row
    if row is None:
        return _deny(
            status.HTTP_404_NOT_FOUND,
            "reference_not_found",
            "Referensi dosen tidak ditemukan.",
        )

    keys = await _present_keys(request)
    instructor_name = None
    instructor_role = None
    curriculum_course_id = None
    user_id = None
    if "instructor_name" in keys and payload.instructor_name is not None:
        instructor_name = payload.instructor_name.strip()
    if "instructor_role" in keys and payload.instructor_role is not None:
        instructor_role = payload.instructor_role
    if "curriculum_course_id" in keys and payload.curriculum_course_id is not None:
        curriculum_course_id = await _resolve_curriculum_course(
            db, payload.curriculum_course_id, scope
        )
        if isinstance(curriculum_course_id, JSONResponse):
            return curriculum_course_id
    if "user_id" in keys:
        user_id = await _resolve_lecturer(db, payload.user_id)
        if isinstance(user_id, JSONResponse):
            return user_id

    reference = row[0]
    if instructor_name is not None:
        reference.instructor_name = instructor_name
    if instructor_role is not None:
        reference.instructor_role = instructor_role
    if curriculum_course_id is not None:
        reference.curriculum_course_id = curriculum_course_id
    if "user_id" in keys:
        reference.user_id = user_id

    await db.commit()
    updated = await _find_reference(db, reference_id, scope)
    return _reference_response(updated)


@router.delete(
    "/scheduling/instructor-references/{reference_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_instructor_reference(
    reference_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope = _read_scope(current_user)
    if isinstance(scope, JSONResponse):
        return scope

    row = await _find_reference(db, reference_id, scope)
    if isinstance(row, JSONResponse):
        return row
    if row is None:
        return _deny(
            status.HTTP_404_NOT_FOUND,
            "reference_not_found",
            "Referensi dosen tidak ditemukan.",
        )

    await db.delete(row[0])
    await db.commit()
    return None


@router.get(
    "/scheduling/curriculum-courses",
    response_model=CurriculumCourseListResponse,
)
async def list_curriculum_courses(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope = _read_scope(current_user)
    if isinstance(scope, JSONResponse):
        return scope

    stmt = (
        select(
            CurriculumCourse.curriculum_course_id.label("curriculum_course_id"),
            Course.course_code.label("course_code"),
            Course.course_name.label("course_name"),
        )
        .join(Curriculum, Curriculum.curriculum_id == CurriculumCourse.curriculum_id)
        .join(Course, Course.course_id == CurriculumCourse.course_id)
        .where(CurriculumCourse.is_active.is_(True))
    )
    if scope is not None:
        stmt = stmt.where(Curriculum.study_program_id == scope)
    rows = (await db.execute(stmt.order_by(Course.course_code))).all()
    items = [
        {"curriculum_course_id": str(row.curriculum_course_id),
         "course_code": row.course_code,
         "course_name": row.course_name}
        for row in rows
    ]
    return CurriculumCourseListResponse(data=items, meta={"total": len(items)})
