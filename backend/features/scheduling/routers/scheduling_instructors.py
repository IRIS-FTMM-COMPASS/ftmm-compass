"""Pemetaan PJ MK dan Tim Pengajar per periode akademik."""

import json
import math
import re
import uuid
from datetime import date
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.errors import error_response
from audit import record_admin_action
from auth import get_current_user
from database import get_db
from models import (
    AcademicPeriod,
    Course,
    CourseInstructorReference,
    Curriculum,
    CurriculumCourse,
    LecturerProfile,
    StudyProgram,
    User,
)
from schemas import (
    CurriculumCourseListResponse,
    InstructorCandidateItem,
    InstructorCandidateListResponse,
)
from ..scheduler import bump_input_revisions, scheduling_input_lock

router = APIRouter()

_UNPROCESSABLE = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)
_ROLE_VALUES = ("pjmk", "teaching_team", "lecturer", "other")
_PJMK_ROLE = "pjmk"
_TEAM_ROLE = "teaching_team"
_POOL_ROLES = (_PJMK_ROLE, _TEAM_ROLE)

_NAME_TITLES = {
    "dr",
    "ir",
    "prof",
    "drs",
    "dra",
    "eng",
    "hj",
    "h",
    "cand",
    "sp",
    "btkv",
    "k",
}


class InstructorReferenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference_id: str
    instructor_name: str
    instructor_role: str = "other"
    course_code: str | None = None
    course_name: str | None = None
    curriculum_course_id: str | None = None
    study_program_id: str | None = None
    study_program_code: str | None = None
    study_program_name: str | None = None
    user_id: str | None = None
    is_mapped: bool = False
    lecturer_name: str | None = None
    academic_period_id: str
    position: int | None = None
    can_auto_assign: bool
    eligibility_reason: str
    source_reference_id: str | None = None


class InstructorReferenceCreateRequest(BaseModel):
    curriculum_course_id: str
    instructor_name: str = Field(..., min_length=1, max_length=200)
    instructor_role: Literal["pjmk", "teaching_team", "lecturer", "other"] = "pjmk"
    user_id: str | None = None
    academic_period_id: UUID
    position: int | None = Field(None, ge=1, le=32767)


class InstructorReferenceUpdateRequest(BaseModel):
    instructor_name: str | None = Field(None, min_length=1, max_length=200)
    instructor_role: Literal["pjmk", "teaching_team", "lecturer", "other"] | None = None
    curriculum_course_id: str | None = None
    user_id: str | None = None
    academic_period_id: UUID
    position: int | None = Field(None, ge=1, le=32767)


class InstructorReferenceListResponse(BaseModel):
    data: list[InstructorReferenceResponse] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class InstructorReferenceCopyRequest(BaseModel):
    from_academic_period_id: UUID
    academic_period_id: UUID


class InstructorReferenceCopyResponse(BaseModel):
    data: list[InstructorReferenceResponse] = Field(default_factory=list)
    meta: dict[str, int]


class InstructorReferenceOrderRequest(BaseModel):
    curriculum_course_id: str
    academic_period_id: UUID
    ordered_reference_ids: list[UUID] = Field(..., min_length=1)


_REFERENCE_SELECT = (
    select(
        CourseInstructorReference,
        Course.course_code.label("course_code"),
        Course.course_name.label("course_name"),
        CurriculumCourse.curriculum_course_id.label("curriculum_course_id"),
        User.full_name.label("lecturer_name"),
        User.role.label("lecturer_role"),
        User.is_active.label("lecturer_is_active"),
        LecturerProfile.user_id.label("lecturer_profile_id"),
        Curriculum.study_program_id.label("program_id"),
        StudyProgram.study_program_id.label("study_program_id"),
        StudyProgram.program_code.label("study_program_code"),
        StudyProgram.program_name.label("study_program_name"),
    )
    .outerjoin(
        CurriculumCourse,
        CurriculumCourse.curriculum_course_id
        == CourseInstructorReference.curriculum_course_id,
    )
    .outerjoin(Curriculum, Curriculum.curriculum_id == CurriculumCourse.curriculum_id)
    .outerjoin(Course, Course.course_id == CurriculumCourse.course_id)
    .outerjoin(User, User.user_id == CourseInstructorReference.user_id)
    .outerjoin(LecturerProfile, LecturerProfile.user_id == User.user_id)
    .outerjoin(
        StudyProgram, StudyProgram.study_program_id == Curriculum.study_program_id
    )
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
    if current_user.role == "admin" and current_user.is_active:
        return None

    profile = current_user.lecturer_profile
    if (
        current_user.role == "lecturer"
        and current_user.is_active
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


def _eligibility(row) -> tuple[bool, str]:
    reference = row[0]
    if reference.user_id is None:
        return False, "external"
    if row.lecturer_profile_id is None or row.lecturer_role != "lecturer":
        return False, "not_lecturer"
    if not row.lecturer_is_active:
        return False, "inactive_account"
    return True, "eligible"


def _reference_response(
    row,
    *,
    position: int | None = None,
) -> InstructorReferenceResponse:
    reference = row[0]
    can_auto_assign, eligibility_reason = _eligibility(row)
    return InstructorReferenceResponse(
        reference_id=str(reference.instructor_reference_id),
        instructor_name=reference.instructor_name,
        instructor_role=reference.instructor_role,
        course_code=row.course_code,
        course_name=row.course_name,
        curriculum_course_id=(
            str(row.curriculum_course_id)
            if row.curriculum_course_id is not None
            else None
        ),
        study_program_id=(
            str(row.study_program_id) if row.study_program_id is not None else None
        ),
        study_program_code=row.study_program_code,
        study_program_name=row.study_program_name,
        user_id=str(reference.user_id) if reference.user_id is not None else None,
        is_mapped=reference.user_id is not None,
        lecturer_name=row.lecturer_name if reference.user_id is not None else None,
        academic_period_id=str(reference.academic_period_id),
        position=position if position is not None else reference.position,
        can_auto_assign=can_auto_assign,
        eligibility_reason=eligibility_reason,
        source_reference_id=(
            str(reference.source_reference_id)
            if reference.source_reference_id is not None
            else None
        ),
    )


def _reference_snapshot(reference: CourseInstructorReference) -> dict[str, Any]:
    return {
        "reference_id": str(reference.instructor_reference_id),
        "curriculum_course_id": str(reference.curriculum_course_id),
        "academic_period_id": (
            str(reference.academic_period_id)
            if reference.academic_period_id is not None
            else None
        ),
        "instructor_name": reference.instructor_name,
        "instructor_role": reference.instructor_role,
        "user_id": str(reference.user_id) if reference.user_id is not None else None,
        "position": reference.position,
        "source_reference_id": (
            str(reference.source_reference_id)
            if reference.source_reference_id is not None
            else None
        ),
    }


def _json_value(value: dict[str, Any] | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


async def _record_mapping_change(
    db: AsyncSession,
    actor: User,
    action: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> None:
    context = after or before or {}
    await record_admin_action(
        db,
        actor=actor,
        target=actor,
        action=f"instructor_reference_{action}",
        reason=(
            f"curriculum_course_id={context.get('curriculum_course_id')} "
            f"academic_period_id={context.get('academic_period_id')}"
        ),
        field_name=context.get("reference_id"),
        old_value=_json_value(before),
        new_value=_json_value(after),
    )


async def _bump_period_revision(
    db: AsyncSession,
    period_id: UUID,
    program_id: UUID | None,
) -> None:
    if program_id is None:
        return
    await bump_input_revisions(db, period_id, {program_id})


async def _curriculum_program_id(
    db: AsyncSession, curriculum_course_id: UUID
) -> UUID:
    return (
        await db.execute(
            select(Curriculum.study_program_id).where(
                CurriculumCourse.curriculum_course_id == curriculum_course_id,
                Curriculum.curriculum_id == CurriculumCourse.curriculum_id,
            )
        )
    ).scalar_one()


def _pjmk_conflict() -> JSONResponse:
    message = "Mata kuliah ini sudah memiliki PJ MK."
    return error_response(
        status.HTTP_409_CONFLICT, "pjmk_exists", message, detail=message
    )


def _pjmk_is_team_conflict() -> JSONResponse:
    message = (
        "PJMK sudah menjadi anggota Tim Pengajar mata kuliah ini dan tidak dapat diduplikasi."
    )
    return error_response(
        status.HTTP_409_CONFLICT, "pjmk_is_team", message, detail=message
    )


def _team_member_conflict() -> JSONResponse:
    message = "Anggota tim pengajar tersebut sudah terdaftar pada mata kuliah ini."
    return error_response(
        status.HTTP_409_CONFLICT, "team_member_exists", message, detail=message
    )


def _position_conflict() -> JSONResponse:
    message = "Posisi tersebut sudah dipakai anggota Tim Pengajar lain."
    return error_response(
        status.HTTP_409_CONFLICT, "position_exists", message, detail=message
    )


def _external_name_key(raw: str | None) -> str:
    if not raw:
        return ""
    head = raw.split(",", 1)[0].lower()
    cleaned = re.sub(r"[^a-z0-9]+", " ", head)
    return " ".join(token for token in cleaned.split() if token not in _NAME_TITLES)


def _same_reference_identity(
    reference: CourseInstructorReference,
    *,
    user_id: UUID | None,
    instructor_name: str,
) -> bool:
    if user_id is not None and reference.user_id is not None:
        return user_id == reference.user_id
    if user_id is not None or reference.user_id is not None:
        return False
    return bool(_external_name_key(instructor_name)) and _external_name_key(
        instructor_name
    ) == _external_name_key(reference.instructor_name)


def _pool_order(references: list[CourseInstructorReference]):
    pjmk = sorted(
        (row for row in references if row.instructor_role == _PJMK_ROLE),
        key=lambda row: (row.position is None, row.position or 0, row.instructor_name),
    )
    members = sorted(
        (row for row in references if row.instructor_role == _TEAM_ROLE),
        key=lambda row: (
            row.position is None,
            row.position or 0,
            row.instructor_name,
            str(row.instructor_reference_id),
        ),
    )
    return [*pjmk, *members]


def _position_map(references: list[CourseInstructorReference]) -> dict[UUID, int]:
    grouped: dict[UUID, list[CourseInstructorReference]] = {}
    for reference in references:
        grouped.setdefault(reference.curriculum_course_id, []).append(reference)
    positions: dict[UUID, int] = {}
    for course_references in grouped.values():
        used = {
            row.position for row in course_references if row.position is not None
        }
        next_position = 1
        for row in _pool_order(course_references):
            if row.position is not None:
                positions[row.instructor_reference_id] = row.position
                continue
            while next_position in used:
                next_position += 1
            positions[row.instructor_reference_id] = next_position
            used.add(next_position)
            next_position += 1
    return positions


async def _period_filter(
    db: AsyncSession,
    period_id: UUID,
) -> UUID | JSONResponse:
    period = await db.get(AcademicPeriod, period_id)
    if period is None:
        return _deny(
            status.HTTP_404_NOT_FOUND,
            "period_not_found",
            "Periode akademik tidak ditemukan.",
        )
    return period_id


async def _team_member_guard(
    db: AsyncSession,
    curriculum_course_id: UUID,
    academic_period_id: UUID,
    *,
    user_id: UUID | None,
    instructor_name: str,
    exclude_reference_id: UUID | None = None,
) -> JSONResponse | None:
    stmt = select(CourseInstructorReference).where(
        CourseInstructorReference.curriculum_course_id == curriculum_course_id,
        CourseInstructorReference.instructor_role.in_(_POOL_ROLES),
    )
    stmt = stmt.where(
        CourseInstructorReference.academic_period_id == academic_period_id
    )
    if exclude_reference_id is not None:
        stmt = stmt.where(
            CourseInstructorReference.instructor_reference_id != exclude_reference_id
        )
    rows = list((await db.execute(stmt.with_for_update())).scalars().all())
    for row in rows:
        if not _same_reference_identity(
            row, user_id=user_id, instructor_name=instructor_name
        ):
            continue
        if row.instructor_role == _PJMK_ROLE:
            return _pjmk_is_team_conflict()
        return _team_member_conflict()
    return None


async def _pjmk_exists(
    db: AsyncSession,
    curriculum_course_id: UUID,
    academic_period_id: UUID,
    *,
    exclude_reference_id: UUID | None = None,
) -> bool:
    stmt = select(CourseInstructorReference.instructor_reference_id).where(
        CourseInstructorReference.curriculum_course_id == curriculum_course_id,
        CourseInstructorReference.instructor_role == _PJMK_ROLE,
    )
    stmt = stmt.where(
        CourseInstructorReference.academic_period_id == academic_period_id
    )
    if exclude_reference_id is not None:
        stmt = stmt.where(
            CourseInstructorReference.instructor_reference_id != exclude_reference_id
        )
    return (await db.execute(stmt.limit(1))).first() is not None


async def _pool_rows(
    db: AsyncSession,
    curriculum_course_id: UUID,
    academic_period_id: UUID,
) -> list[CourseInstructorReference]:
    return list(
        (
            await db.execute(
                select(CourseInstructorReference)
                .where(
                    CourseInstructorReference.curriculum_course_id
                    == curriculum_course_id,
                    CourseInstructorReference.academic_period_id == academic_period_id,
                    CourseInstructorReference.instructor_role.in_(_POOL_ROLES),
                )
                .with_for_update()
            )
        ).scalars().all()
    )


async def _resolve_lecturer(
    db: AsyncSession, raw: str | None, scope: UUID | None
) -> UUID | None | JSONResponse:
    if raw is None:
        return None
    try:
        user_id = UUID(str(raw))
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
    if scope is not None and target.lecturer_profile.study_program_id != scope:
        return _deny(
            status.HTTP_403_FORBIDDEN,
            "akses_prodi_ditolak",
            "Dosen berada di luar program studi Anda.",
        )
    return target.user_id


async def _require_active_pjmk(
    db: AsyncSession, user_id: UUID | None, scope: UUID | None
) -> JSONResponse | None:
    if user_id is None:
        return _field_error(
            "user_id",
            "PJ MK harus memiliki akun dosen aktif.",
            "pjmk_requires_account",
        )
    stmt = (
        select(User)
        .join(LecturerProfile, LecturerProfile.user_id == User.user_id)
        .where(
            User.user_id == user_id,
            User.role == "lecturer",
            User.is_active.is_(True),
        )
    )
    if scope is not None:
        stmt = stmt.where(LecturerProfile.study_program_id == scope)
    if (await db.execute(stmt)).first() is None:
        return _field_error(
            "user_id",
            "PJ MK harus memiliki akun dosen aktif.",
            "pjmk_requires_account",
        )
    return None


async def _resolve_curriculum_course(
    db: AsyncSession, raw: str, scope: UUID | None
) -> UUID | JSONResponse:
    try:
        curriculum_course_id = UUID(str(raw))
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
            .with_for_update()
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


async def _resolve_candidate_course(
    db: AsyncSession, raw: str, scope: UUID | None
) -> UUID | JSONResponse:
    try:
        curriculum_course_id = UUID(str(raw))
    except (ValueError, TypeError, AttributeError):
        return _deny(
            status.HTTP_404_NOT_FOUND,
            "course_not_found",
            "Mata kuliah tidak ditemukan.",
        )

    row = (
        await db.execute(
            select(Curriculum.study_program_id)
            .join(
                CurriculumCourse,
                Curriculum.curriculum_id == CurriculumCourse.curriculum_id,
            )
            .where(
                CurriculumCourse.curriculum_course_id == curriculum_course_id,
                CurriculumCourse.is_active.is_(True),
            )
        )
    ).first()
    if row is None:
        return _deny(
            status.HTTP_404_NOT_FOUND,
            "course_not_found",
            "Mata kuliah tidak ditemukan.",
        )
    if scope is not None and row.study_program_id != scope:
        return _deny(
            status.HTTP_403_FORBIDDEN,
            "forbidden",
            "Mata kuliah di luar program studi Anda.",
        )
    return curriculum_course_id


async def _find_reference(
    db: AsyncSession,
    reference_id: UUID,
    scope: UUID | None,
    academic_period_id: UUID,
):
    row = (
        await db.execute(
            _REFERENCE_SELECT.where(
                CourseInstructorReference.instructor_reference_id == reference_id,
                CourseInstructorReference.academic_period_id == academic_period_id,
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


async def _set_pjmk_first(
    db: AsyncSession,
    references: list[CourseInstructorReference],
    pjmk_reference: CourseInstructorReference | None,
) -> list[tuple[CourseInstructorReference, dict[str, Any], dict[str, Any]]]:
    changes = []
    for reference in references:
        before = _reference_snapshot(reference)
        reference.position = None
        changes.append((reference, before, None))
    await db.flush()
    if pjmk_reference is not None:
        pjmk_reference.position = 1
    members = _pool_order(
        [row for row in references if row is not pjmk_reference]
    )
    for position, reference in enumerate(members, start=2):
        reference.position = position
    return [
        (reference, before, _reference_snapshot(reference))
        for reference, before, _ in changes
        if before != _reference_snapshot(reference)
    ]


def _period_order(period: AcademicPeriod) -> tuple[int, int, date]:
    semester = period.semester_number
    if semester is None:
        semester = 1 if "ganjil" in period.term.lower() else 2
    return (
        period.academic_year_start,
        semester,
        period.start_date or date(period.academic_year_start, 1, 1),
    )


@router.get("/scheduling/instructor-references/periods")
async def list_mapping_periods(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope = _read_scope(current_user)
    if isinstance(scope, JSONResponse):
        return scope
    periods = (
        await db.execute(
            select(AcademicPeriod).order_by(
                AcademicPeriod.academic_year_start.desc(),
                AcademicPeriod.semester_number.desc(),
                AcademicPeriod.created_at.desc(),
            )
        )
    ).scalars().all()
    return {
        "data": [
            {
                "academic_period_id": str(period.academic_period_id),
                "academic_year_start": period.academic_year_start,
                "semester_number": period.semester_number,
                "term": period.term,
                "is_active": period.is_active,
            }
            for period in periods
        ],
        "meta": {"total": len(periods)},
    }


@router.get(
    "/scheduling/instructor-references",
    response_model=InstructorReferenceListResponse,
)
async def list_instructor_references(
    role: str | None = Query(None),
    academic_period_id: UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope = _read_scope(current_user)
    if isinstance(scope, JSONResponse):
        return scope
    period_id = await _period_filter(db, academic_period_id)
    if isinstance(period_id, JSONResponse):
        return period_id

    stmt = _REFERENCE_SELECT
    if scope is not None:
        stmt = stmt.where(Curriculum.study_program_id == scope)
    stmt = stmt.where(CourseInstructorReference.academic_period_id == period_id)
    if role is not None:
        normalized_role = role.strip()
        if normalized_role not in _ROLE_VALUES:
            return _field_error(
                "role", "Peran pengajar tidak valid.", "invalid_role"
            )
        stmt = stmt.where(
            CourseInstructorReference.instructor_role == normalized_role
        )
    rows = (
        await db.execute(
            stmt.order_by(
                Course.course_code,
                CourseInstructorReference.position,
                CourseInstructorReference.instructor_name,
                CourseInstructorReference.instructor_reference_id,
            )
        )
    ).all()
    positions = _position_map([row[0] for row in rows])
    items = [
        _reference_response(
            row,
            position=positions.get(row[0].instructor_reference_id),
        )
        for row in rows
    ]
    items.sort(
        key=lambda item: (
            item.course_code or "",
            item.position if item.position is not None else 2**31 - 1,
            item.instructor_name,
            item.reference_id,
        )
    )
    return InstructorReferenceListResponse(
        data=items,
        meta={
            "total": len(items),
            "mapped": sum(1 for item in items if item.is_mapped),
            "unmapped": sum(1 for item in items if not item.is_mapped),
        },
    )


@router.get(
    "/scheduling/instructor-candidates",
    response_model=InstructorCandidateListResponse,
)
async def list_instructor_candidates(
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    curriculum_course_id: str | None = Query(None),
    academic_period_id: UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope = _read_scope(current_user)
    if isinstance(scope, JSONResponse):
        return scope
    period_id = await _period_filter(db, academic_period_id)
    if isinstance(period_id, JSONResponse):
        return period_id

    pjmk_user_ids: list[UUID] = []
    if curriculum_course_id is not None:
        resolved_course_id = await _resolve_candidate_course(
            db, curriculum_course_id, scope
        )
        if isinstance(resolved_course_id, JSONResponse):
            return resolved_course_id
        stmt = select(CourseInstructorReference.user_id).where(
            CourseInstructorReference.curriculum_course_id == resolved_course_id,
            CourseInstructorReference.instructor_role == _PJMK_ROLE,
            CourseInstructorReference.user_id.is_not(None),
        )
        stmt = stmt.where(
            CourseInstructorReference.academic_period_id == period_id
        )
        pjmk_user_ids = list((await db.execute(stmt)).scalars().all())

    base = (
        select(User, LecturerProfile, StudyProgram)
        .join(LecturerProfile, LecturerProfile.user_id == User.user_id)
        .outerjoin(
            StudyProgram,
            StudyProgram.study_program_id == LecturerProfile.study_program_id,
        )
        .where(User.role == "lecturer", User.is_active.is_(True))
    )
    count_stmt = (
        select(func.count())
        .select_from(User)
        .join(LecturerProfile, LecturerProfile.user_id == User.user_id)
        .outerjoin(
            StudyProgram,
            StudyProgram.study_program_id == LecturerProfile.study_program_id,
        )
        .where(User.role == "lecturer", User.is_active.is_(True))
    )
    if scope is not None:
        base = base.where(LecturerProfile.study_program_id == scope)
        count_stmt = count_stmt.where(LecturerProfile.study_program_id == scope)
    if pjmk_user_ids:
        base = base.where(User.user_id.not_in(pjmk_user_ids))
        count_stmt = count_stmt.where(User.user_id.not_in(pjmk_user_ids))
    if search and search.strip():
        term = f"%{search.strip()}%"
        condition = or_(
            User.full_name.ilike(term),
            User.email.ilike(term),
            LecturerProfile.employee_number.ilike(term),
        )
        base = base.where(condition)
        count_stmt = count_stmt.where(condition)

    total = int((await db.execute(count_stmt)).scalar_one())
    rows = (
        await db.execute(
            base.order_by(User.full_name)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    items = [
        InstructorCandidateItem(
            user_id=str(user.user_id),
            full_name=user.full_name,
            email=user.email,
            employee_number=profile.employee_number,
            study_program_id=(
                str(profile.study_program_id)
                if profile.study_program_id is not None
                else None
            ),
            study_program_code=program.program_code if program is not None else None,
            is_active=user.is_active,
        )
        for user, profile, program in rows
    ]
    return InstructorCandidateListResponse(
        data=items,
        meta={
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": math.ceil(total / page_size),
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
    period_id = await _period_filter(db, payload.academic_period_id)
    if isinstance(period_id, JSONResponse):
        return period_id
    program_id = await _curriculum_program_id(db, curriculum_course_id)
    locked = await scheduling_input_lock(db, period_id, {program_id})
    if locked is not None:
        code, message = locked
        return _deny(409, code, message)

    user_id = await _resolve_lecturer(db, payload.user_id, scope)
    if isinstance(user_id, JSONResponse):
        return user_id

    instructor_name = payload.instructor_name.strip()
    if not instructor_name:
        return _field_error(
            "instructor_name", "Nama pengajar tidak boleh kosong.", "invalid_name"
        )
    if user_id is not None:
        account = await db.get(User, user_id)
        if account is not None and account.full_name.strip():
            instructor_name = account.full_name.strip()
    if payload.instructor_role == _PJMK_ROLE:
        denied = await _require_active_pjmk(db, user_id, scope)
        if denied is not None:
            return denied
        if payload.position is not None and payload.position != 1:
            return _field_error(
                "position", "PJ MK harus berada pada posisi pertama.", "invalid_position"
            )

    pool = await _pool_rows(db, curriculum_course_id, period_id)
    if payload.instructor_role == _TEAM_ROLE:
        conflict = await _team_member_guard(
            db,
            curriculum_course_id,
            period_id,
            user_id=user_id,
            instructor_name=instructor_name,
        )
        if conflict is not None:
            return conflict
    if payload.instructor_role == _PJMK_ROLE and await _pjmk_exists(
        db, curriculum_course_id, period_id
    ):
        return _pjmk_conflict()

    position = payload.position
    shifted: list[tuple[CourseInstructorReference, dict[str, Any], dict[str, Any]]] = []
    if payload.instructor_role == _PJMK_ROLE:
        shifted = await _set_pjmk_first(db, pool, None)
        position = 1
    elif position is None:
        position = max(
            max((row.position or 0 for row in pool), default=0), len(pool)
        ) + 1
    elif any(
        row.instructor_role == _PJMK_ROLE and row.position == 1
        for row in pool
    ) and position == 1:
        return _field_error(
            "position",
            "Posisi pertama dicadangkan untuk PJ MK.",
            "invalid_position",
        )

    reference = CourseInstructorReference(
        curriculum_course_id=curriculum_course_id,
        academic_period_id=period_id,
        instructor_name=instructor_name,
        instructor_role=payload.instructor_role,
        user_id=user_id,
        position=position,
    )
    db.add(reference)
    try:
        await db.flush()
        row = await _find_reference(db, reference.instructor_reference_id, scope, period_id)
        for shifted_reference, before, after in shifted:
            await _record_mapping_change(
                db, current_user, "position", before, after
            )
        await _record_mapping_change(
            db, current_user, "create", None, _reference_snapshot(reference)
        )
        await _bump_period_revision(db, period_id, row.study_program_id)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        if payload.instructor_role == _PJMK_ROLE:
            return _pjmk_conflict()
        return _position_conflict()
    row = await _find_reference(db, reference.instructor_reference_id, scope, period_id)
    return _reference_response(row)


@router.patch(
    "/scheduling/instructor-references/{reference_id}",
    response_model=InstructorReferenceResponse,
)
async def map_instructor_reference(
    reference_id: UUID,
    payload: InstructorReferenceUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope = _read_scope(current_user)
    if isinstance(scope, JSONResponse):
        return scope
    period_id = await _period_filter(db, payload.academic_period_id)
    if isinstance(period_id, JSONResponse):
        return period_id
    row = await _find_reference(db, reference_id, scope, period_id)
    if isinstance(row, JSONResponse):
        return row
    if row is None:
        return _deny(
            status.HTTP_404_NOT_FOUND,
            "reference_not_found",
            "Referensi dosen tidak ditemukan.",
        )

    keys = await _present_keys(request)
    reference = row[0]
    before = _reference_snapshot(reference)
    old_program_id = row.study_program_id
    instructor_name = (
        payload.instructor_name.strip()
        if "instructor_name" in keys and payload.instructor_name is not None
        else None
    )
    instructor_role = (
        payload.instructor_role
        if "instructor_role" in keys and payload.instructor_role is not None
        else None
    )
    curriculum_course_id = reference.curriculum_course_id
    if "curriculum_course_id" in keys and payload.curriculum_course_id is not None:
        curriculum_course_id = await _resolve_curriculum_course(
            db, payload.curriculum_course_id, scope
        )
        if isinstance(curriculum_course_id, JSONResponse):
            return curriculum_course_id
    user_id = reference.user_id
    if "user_id" in keys:
        user_id = await _resolve_lecturer(db, payload.user_id, scope)
        if isinstance(user_id, JSONResponse):
            return user_id
    target_program_id = await _curriculum_program_id(db, curriculum_course_id)
    for locked_program_id in {old_program_id, target_program_id}:
        locked = await scheduling_input_lock(db, period_id, {locked_program_id})
        if locked is not None:
            code, message = locked
            return _deny(409, code, message)

    target_role = instructor_role or reference.instructor_role
    target_name = instructor_name or reference.instructor_name
    if instructor_name is None and user_id is not None:
        account = await db.get(User, user_id)
        if account is not None and account.full_name.strip():
            target_name = account.full_name.strip()
    if target_role == _PJMK_ROLE:
        denied = await _require_active_pjmk(db, user_id, scope)
        if denied is not None:
            return denied
    if target_role == _TEAM_ROLE:
        conflict = await _team_member_guard(
            db,
            curriculum_course_id,
            period_id,
            user_id=user_id,
            instructor_name=target_name,
            exclude_reference_id=reference_id,
        )
        if conflict is not None:
            return conflict
    if target_role == _PJMK_ROLE and await _pjmk_exists(
        db, curriculum_course_id, period_id, exclude_reference_id=reference_id
    ):
        return _pjmk_conflict()

    pool = [
        item
        for item in await _pool_rows(db, curriculum_course_id, period_id)
        if item.instructor_reference_id != reference_id
    ]
    position = reference.position
    shifted: list[tuple[CourseInstructorReference, dict[str, Any], dict[str, Any]]] = []
    position_changed = "position" in keys
    if target_role == _PJMK_ROLE:
        if position_changed and payload.position not in (None, 1):
            return _field_error(
                "position",
                "PJ MK harus berada pada posisi pertama.",
                "invalid_position",
            )
        shifted = await _set_pjmk_first(db, pool, reference)
        position = 1
    elif position_changed:
        if payload.position is None:
            position = max(
                max((item.position or 0 for item in pool), default=0), len(pool)
            ) + 1
        else:
            position = payload.position
            if any(item.position == position for item in pool):
                return _position_conflict()
            if position == 1 and any(
                item.instructor_role == _PJMK_ROLE for item in pool
            ):
                return _field_error(
                    "position",
                    "Posisi pertama dicadangkan untuk PJ MK.",
                    "invalid_position",
                )
    elif (
        curriculum_course_id != reference.curriculum_course_id
        or target_role != reference.instructor_role
    ):
        position = max(
            max((item.position or 0 for item in pool), default=0), len(pool)
        ) + 1

    reference.instructor_name = target_name
    reference.instructor_role = target_role
    reference.curriculum_course_id = curriculum_course_id
    reference.user_id = user_id
    reference.position = position
    after = _reference_snapshot(reference)
    if before == after and not shifted:
        await db.commit()
        updated = await _find_reference(db, reference_id, scope, period_id)
        return _reference_response(updated)

    try:
        await db.flush()
        updated = await _find_reference(db, reference_id, scope, period_id)
        if target_role == _PJMK_ROLE:
            for shifted_reference, shifted_before, shifted_after in shifted:
                await _record_mapping_change(
                    db, current_user, "position", shifted_before, shifted_after
                )
        if before != after:
            await _record_mapping_change(db, current_user, "update", before, after)
        await _bump_period_revision(db, period_id, updated.study_program_id)
        if old_program_id != updated.study_program_id:
            await _bump_period_revision(db, period_id, old_program_id)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        if target_role == _PJMK_ROLE:
            return _pjmk_conflict()
        return _position_conflict()
    updated = await _find_reference(db, reference_id, scope, period_id)
    return _reference_response(updated)


@router.delete(
    "/scheduling/instructor-references/{reference_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_instructor_reference(
    reference_id: UUID,
    academic_period_id: UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope = _read_scope(current_user)
    if isinstance(scope, JSONResponse):
        return scope
    period_id = await _period_filter(db, academic_period_id)
    if isinstance(period_id, JSONResponse):
        return period_id
    row = await _find_reference(db, reference_id, scope, period_id)
    if isinstance(row, JSONResponse):
        return row
    if row is None:
        return _deny(
            status.HTTP_404_NOT_FOUND,
            "reference_not_found",
            "Referensi dosen tidak ditemukan.",
        )

    reference = row[0]
    before = _reference_snapshot(reference)
    program_id = row.study_program_id
    locked = await scheduling_input_lock(db, period_id, {program_id})
    if locked is not None:
        code, message = locked
        return _deny(409, code, message)

    await db.delete(reference)
    await _record_mapping_change(db, current_user, "delete", before, None)
    await _bump_period_revision(db, period_id, program_id)
    await db.commit()
    return None


@router.post(
    "/scheduling/instructor-references/copy",
    response_model=InstructorReferenceCopyResponse,
)
async def copy_instructor_references(
    payload: InstructorReferenceCopyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope = _read_scope(current_user)
    if isinstance(scope, JSONResponse):
        return scope
    source_period = await db.get(AcademicPeriod, payload.from_academic_period_id)
    target_period = await db.get(AcademicPeriod, payload.academic_period_id)
    if source_period is None or target_period is None:
        return _deny(
            status.HTTP_404_NOT_FOUND,
            "period_not_found",
            "Periode akademik tidak ditemukan.",
        )
    if _period_order(source_period) >= _period_order(target_period):
        return _field_error(
            "from_academic_period_id",
            "Periode sumber harus mendahului periode tujuan.",
            "invalid_source_period",
        )
    locked = await scheduling_input_lock(
        db,
        payload.academic_period_id,
        {scope} if scope is not None else None,
    )
    if locked is not None:
        code, message = locked
        return _deny(409, code, message)


    stmt = _REFERENCE_SELECT.where(
        CourseInstructorReference.academic_period_id
        == payload.from_academic_period_id
    )
    if scope is not None:
        stmt = stmt.where(Curriculum.study_program_id == scope)
    source_rows = (await db.execute(stmt)).all()
    source_rows_by_id = {row[0].instructor_reference_id: row for row in source_rows}
    grouped: dict[UUID, list] = {}
    for source_row in source_rows:
        grouped.setdefault(source_row[0].curriculum_course_id, []).append(source_row)

    copied_items: list[InstructorReferenceResponse] = []
    copied_count = 0
    skipped_count = 0
    affected_programs: set[UUID | None] = set()
    for curriculum_course_id, course_rows in grouped.items():
        resolved_course_id = await _resolve_curriculum_course(
            db, str(curriculum_course_id), scope
        )
        if isinstance(resolved_course_id, JSONResponse):
            return resolved_course_id
        source_references = [item[0] for item in course_rows]
        source_positions = _position_map(source_references)
        for source_row in course_rows:
            source = source_row[0]
            if source.instructor_role == _PJMK_ROLE:
                denied = await _require_active_pjmk(db, source.user_id, scope)
                if denied is not None:
                    return denied

        pool = await _pool_rows(db, curriculum_course_id, payload.academic_period_id)
        target_rows = list(
            (
                await db.execute(
                    _REFERENCE_SELECT.where(
                        CourseInstructorReference.curriculum_course_id
                        == curriculum_course_id,
                        CourseInstructorReference.academic_period_id
                        == payload.academic_period_id,
                    )
                )
            ).all()
        )
        target_references = [row[0] for row in target_rows]
        target_was_empty = not target_references
        shifted: list[
            tuple[CourseInstructorReference, dict[str, Any], dict[str, Any]]
        ] = []
        ordered_source_ids = [
            row.instructor_reference_id for row in _pool_order(source_references)
        ]
        ordered_source_ids.extend(
            row.instructor_reference_id
            for row in sorted(
                (
                    item
                    for item in source_references
                    if item.instructor_role not in _POOL_ROLES
                ),
                key=lambda item: (
                    item.instructor_role,
                    item.instructor_name,
                    str(item.instructor_reference_id),
                ),
            )
        )
        for source_id in ordered_source_ids:
            source_row = source_rows_by_id[source_id]
            source = source_row[0]
            equivalent = next(
                (
                    target
                    for target in target_references
                    if target.source_reference_id == source.instructor_reference_id
                ),
                None,
            )
            if equivalent is None:
                equivalent = next(
                    (
                        target
                        for target in target_references
                        if target.source_reference_id is None
                        and target.instructor_role == source.instructor_role
                        and _same_reference_identity(
                            target,
                            user_id=source.user_id,
                            instructor_name=source.instructor_name,
                        )
                    ),
                    None,
                )
            if equivalent is not None:
                skipped_count += 1
                continue
            if source.instructor_role == _TEAM_ROLE and any(
                target.instructor_role == _PJMK_ROLE
                and _same_reference_identity(
                    target,
                    user_id=source.user_id,
                    instructor_name=source.instructor_name,
                )
                for target in target_references
            ):
                skipped_count += 1
                continue
            if source.instructor_role == _PJMK_ROLE:
                if any(
                    target.instructor_role == _PJMK_ROLE
                    for target in target_references
                ):
                    skipped_count += 1
                    continue
                if not shifted:
                    shifted = await _set_pjmk_first(db, pool, None)
                position = 1
            else:
                if target_was_empty and source.instructor_role in _POOL_ROLES:
                    position = source_positions[source.instructor_reference_id]
                else:
                    position = max(
                        max((item.position or 0 for item in pool), default=0),
                        len(pool),
                    ) + 1
            reference = CourseInstructorReference(
                curriculum_course_id=curriculum_course_id,
                academic_period_id=payload.academic_period_id,
                source_document_id=source.source_document_id,
                instructor_name=source.instructor_name,
                instructor_role=source.instructor_role,
                user_id=source.user_id,
                position=position,
                source_reference_id=source.instructor_reference_id,
            )
            db.add(reference)
            await db.flush()
            target_references.append(reference)
            if reference.instructor_role in _POOL_ROLES:
                pool.append(reference)
            copied_row = await _find_reference(
                db,
                reference.instructor_reference_id,
                scope,
                payload.academic_period_id,
            )
            copied_items.append(_reference_response(copied_row))
            affected_programs.add(copied_row.study_program_id)
            copied_count += 1
        for shifted_reference, before, after in shifted:
            await _record_mapping_change(
                db, current_user, "position", before, after
            )
        for item in copied_items:
            if item.curriculum_course_id != str(curriculum_course_id):
                continue
            reference = await db.get(
                CourseInstructorReference, UUID(item.reference_id)
            )
            await _record_mapping_change(
                db, current_user, "copy", None, _reference_snapshot(reference)
            )

    for program_id in affected_programs:
        await _bump_period_revision(db, payload.academic_period_id, program_id)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        if any(item.instructor_role == _PJMK_ROLE for item in copied_items):
            return _pjmk_conflict()
        return _position_conflict()
    return InstructorReferenceCopyResponse(
        data=copied_items,
        meta={
            "copied": copied_count,
            "skipped": skipped_count,
            "total": len(source_rows),
        },
    )


@router.put(
    "/scheduling/instructor-references/order",
    response_model=InstructorReferenceListResponse,
)
async def order_instructor_references(
    payload: InstructorReferenceOrderRequest,
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
    period_id = await _period_filter(db, payload.academic_period_id)
    if isinstance(period_id, JSONResponse):
        return period_id
    program_id = await _curriculum_program_id(db, curriculum_course_id)
    locked = await scheduling_input_lock(db, period_id, {program_id})
    if locked is not None:
        code, message = locked
        return _deny(409, code, message)
    pool = await _pool_rows(db, curriculum_course_id, payload.academic_period_id)
    pool_ids = {row.instructor_reference_id for row in pool}
    ordered_ids = payload.ordered_reference_ids
    if len(set(ordered_ids)) != len(ordered_ids) or set(ordered_ids) != pool_ids:
        return _field_error(
            "ordered_reference_ids",
            "Urutan harus memuat seluruh anggota pool tepat satu kali.",
            "invalid_pool_order",
        )
    by_id = {row.instructor_reference_id: row for row in pool}
    pjmk = [
        by_id[item]
        for item in ordered_ids
        if by_id[item].instructor_role == _PJMK_ROLE
    ]
    if pjmk and ordered_ids[0] != pjmk[0].instructor_reference_id:
        return _field_error(
            "ordered_reference_ids",
            "PJ MK harus berada pada posisi pertama.",
            "invalid_pool_order",
        )
    if pjmk:
        denied = await _require_active_pjmk(db, pjmk[0].user_id, scope)
        if denied is not None:
            return denied

    before = {
        row.instructor_reference_id: _reference_snapshot(row) for row in pool
    }
    for row in pool:
        row.position = None
    await db.flush()
    for position, reference_id in enumerate(ordered_ids, start=1):
        by_id[reference_id].position = position
    changed = [
        row
        for row in pool
        if before[row.instructor_reference_id] != _reference_snapshot(row)
    ]
    if changed:
        rows = (
            await db.execute(
                _REFERENCE_SELECT.where(
                    CourseInstructorReference.curriculum_course_id
                    == curriculum_course_id,
                    CourseInstructorReference.academic_period_id
                    == payload.academic_period_id,
                    CourseInstructorReference.instructor_role.in_(_POOL_ROLES),
                ).order_by(CourseInstructorReference.position)
            )
        ).all()
        program_id = rows[0].study_program_id if rows else None
        for row in changed:
            await _record_mapping_change(
                db,
                current_user,
                "order",
                before[row.instructor_reference_id],
                _reference_snapshot(row),
            )
        await _bump_period_revision(db, payload.academic_period_id, program_id)
    await db.commit()
    rows = (
        await db.execute(
            _REFERENCE_SELECT.where(
                CourseInstructorReference.curriculum_course_id
                == curriculum_course_id,
                CourseInstructorReference.academic_period_id
                == payload.academic_period_id,
                CourseInstructorReference.instructor_role.in_(_POOL_ROLES),
            ).order_by(CourseInstructorReference.position)
        )
    ).all()
    items = [_reference_response(row) for row in rows]
    return InstructorReferenceListResponse(data=items, meta={"total": len(items)})


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
            Course.course_id.label("course_id"),
            Curriculum.study_program_id.label("study_program_id"),
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
        {
            "curriculum_course_id": str(row.curriculum_course_id),
            "course_id": str(row.course_id),
            "study_program_id": str(row.study_program_id),
            "course_code": row.course_code,
            "course_name": row.course_name,
        }
        for row in rows
    ]
    return CurriculumCourseListResponse(data=items, meta={"total": len(items)})
