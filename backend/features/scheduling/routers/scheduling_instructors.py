"""Pemetaan PJ MK dan Tim Pengajar per periode akademik."""

import math
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.errors import error_response
from auth import get_current_user
from database import get_db
from models import User
from schemas import (
    CurriculumCourseListResponse,
    InstructorCandidateItem,
    InstructorCandidateListResponse,
)
from ..schemas import (
    InstructorReferenceCopyRequest,
    InstructorReferenceCopyResponse,
    InstructorReferenceCreateRequest,
    InstructorReferenceListResponse,
    InstructorReferenceOrderRequest,
    InstructorReferenceResponse,
    InstructorReferenceUpdateRequest,
)
from ..services import instructor_catalog, instructor_references
from ..services.errors import ServiceError

router = APIRouter()


def _failure(error: ServiceError) -> JSONResponse:
    return error_response(
        error.status_code, error.code, error.message,
        detail=error.message, details=error.details
    )


async def _present_keys(request: Request) -> set[str]:
    try:
        raw = await request.json()
    except Exception:
        return set()
    return set(raw) if isinstance(raw, dict) else set()


def _read_scope(current_user: User) -> UUID | None | JSONResponse:
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
    return _failure(
        ServiceError(403, "forbidden", "Referensi pengajar hanya tersedia untuk admin dan PJ Prodi.")
    )


@router.get("/scheduling/instructor-references/periods")
async def list_mapping_periods(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope = _read_scope(current_user)
    if isinstance(scope, JSONResponse): return scope
    periods = await instructor_references.list_periods(db)
    return {"data": periods, "meta": {"total": len(periods)}}


@router.get(
    "/scheduling/instructor-references", response_model=InstructorReferenceListResponse
)
async def list_instructor_references(
    role: str | None = Query(None),
    academic_period_id: UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope = _read_scope(current_user)
    if isinstance(scope, JSONResponse): return scope
    items = await instructor_references.list_references(db, scope, academic_period_id, role)
    if isinstance(items, ServiceError): return _failure(items)
    mapped = sum(item["is_mapped"] for item in items)
    return InstructorReferenceListResponse(
        data=[InstructorReferenceResponse(**item) for item in items],
        meta={"total": len(items), "mapped": mapped, "unmapped": len(items) - mapped},
    )


@router.get(
    "/scheduling/instructor-candidates", response_model=InstructorCandidateListResponse
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
    if isinstance(scope, JSONResponse): return scope
    result = await instructor_catalog.list_candidates(
        db, scope, academic_period_id, curriculum_course_id, search, page, page_size
    )
    if isinstance(result, ServiceError): return _failure(result)
    items, total = result
    return InstructorCandidateListResponse(
        data=[InstructorCandidateItem(**item) for item in items],
        meta={
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": math.ceil(total / page_size),
        },
    )


@router.post(
    "/scheduling/instructor-references", response_model=InstructorReferenceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_instructor_reference(
    payload: InstructorReferenceCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope = _read_scope(current_user)
    if isinstance(scope, JSONResponse): return scope
    result = await instructor_references.create_reference(db, scope, current_user, payload)
    if isinstance(result, ServiceError): return _failure(result)
    return InstructorReferenceResponse(**result)


@router.patch(
    "/scheduling/instructor-references/{reference_id}", response_model=InstructorReferenceResponse
)
async def map_instructor_reference(
    reference_id: UUID,
    payload: InstructorReferenceUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope = _read_scope(current_user)
    if isinstance(scope, JSONResponse): return scope
    keys = await _present_keys(request)
    result = await instructor_references.map_reference(
        db, scope, current_user, reference_id, payload, keys
    )
    if isinstance(result, ServiceError): return _failure(result)
    return InstructorReferenceResponse(**result)


@router.delete(
    "/scheduling/instructor-references/{reference_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_instructor_reference(
    reference_id: UUID,
    academic_period_id: UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope = _read_scope(current_user)
    if isinstance(scope, JSONResponse): return scope
    result = await instructor_references.delete_reference(
        db, scope, current_user, reference_id, academic_period_id
    )
    if isinstance(result, ServiceError): return _failure(result)
    return None


@router.post(
    "/scheduling/instructor-references/copy", response_model=InstructorReferenceCopyResponse
)
async def copy_instructor_references(
    payload: InstructorReferenceCopyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope = _read_scope(current_user)
    if isinstance(scope, JSONResponse): return scope
    result = await instructor_references.copy_references(db, scope, current_user, payload)
    if isinstance(result, ServiceError): return _failure(result)
    items, meta = result
    return InstructorReferenceCopyResponse(
        data=[InstructorReferenceResponse(**item) for item in items], meta=meta
    )


@router.put(
    "/scheduling/instructor-references/order", response_model=InstructorReferenceListResponse
)
async def order_instructor_references(
    payload: InstructorReferenceOrderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope = _read_scope(current_user)
    if isinstance(scope, JSONResponse): return scope
    items = await instructor_references.order_references(db, scope, current_user, payload)
    if isinstance(items, ServiceError): return _failure(items)
    return InstructorReferenceListResponse(
        data=[InstructorReferenceResponse(**item) for item in items],
        meta={"total": len(items)},
    )


@router.get(
    "/scheduling/curriculum-courses", response_model=CurriculumCourseListResponse
)
async def list_curriculum_courses(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope = _read_scope(current_user)
    if isinstance(scope, JSONResponse): return scope
    items = await instructor_catalog.list_curriculum_courses(db, scope)
    return CurriculumCourseListResponse(data=items, meta={"total": len(items)})
