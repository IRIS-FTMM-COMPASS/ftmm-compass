"""Deterministic lecturer-assignment preview and scoped persistence."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.errors import error_response
from auth import get_current_user
from database import get_db
from models import AcademicPeriod, User
from schemas import (
    AssignmentBulkRequest,
    AssignmentBulkResponse,
    AssignmentEnvelope,
    AssignmentPreviewResponse,
)
from scheduling_common import current_period_id
from ..services.errors import ServiceError
from ..services.lecturer_assignments import (
    AssignmentDecision,
    build_preview,
    delete_assignment,
    save_assignments,
)

router = APIRouter()



def _failure(error: ServiceError) -> JSONResponse:
    return error_response(
        error.status_code,
        error.code,
        error.message,
        detail=error.message,
        details=error.details,
    )


def _scope(current_user: User) -> UUID | None | JSONResponse:
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
        ServiceError(
            status.HTTP_403_FORBIDDEN,
            "forbidden",
            "Assignment pengajar hanya tersedia untuk admin dan PJ Prodi.",
        )
    )


async def _period(db: AsyncSession, period_id: UUID | None) -> AcademicPeriod | JSONResponse:
    resolved_id = period_id or await current_period_id(db)
    if resolved_id is None:
        return _failure(
            ServiceError(
                404, "period_not_found", "Periode akademik aktif tidak ditemukan."
            )
        )
    period = await db.get(AcademicPeriod, resolved_id)
    if period is None:
        return _failure(
            ServiceError(404, "period_not_found", "Periode akademik tidak ditemukan.")
        )
    return period


@router.get(
    "/scheduling/assignments/preview", response_model=AssignmentPreviewResponse
)
async def preview_assignments(
    academic_period_id: UUID | None = Query(None),
    curriculum_course_id: UUID | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope = _scope(current_user)
    if isinstance(scope, JSONResponse):
        return scope
    period = await _period(db, academic_period_id)
    if isinstance(period, JSONResponse):
        return period
    return AssignmentPreviewResponse.model_validate(
        await build_preview(
            db, period.academic_period_id, scope, curriculum_course_id
        )
    )


@router.put("/scheduling/assignments", response_model=AssignmentBulkResponse)
async def save_class_assignments(
    payload: AssignmentBulkRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope = _scope(current_user)
    if isinstance(scope, JSONResponse):
        return scope
    decisions = [AssignmentDecision(**item.model_dump()) for item in payload.decisions]
    result = await save_assignments(db, decisions, scope, current_user)
    if isinstance(result, ServiceError):
        return _failure(result)
    return AssignmentBulkResponse.model_validate(result)


@router.delete(
    "/scheduling/assignments/{class_section_id}", response_model=AssignmentEnvelope
)
async def delete_class_assignment(
    class_section_id: UUID,
    curriculum_course_id: UUID | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope = _scope(current_user)
    if isinstance(scope, JSONResponse):
        return scope
    result = await delete_assignment(
        db, class_section_id, curriculum_course_id, scope, current_user
    )
    if isinstance(result, ServiceError):
        return _failure(result)
    return AssignmentEnvelope(data=None)
