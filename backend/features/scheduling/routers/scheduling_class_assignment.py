"""Single-class lecturer-assignment lookup and upsert."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.errors import error_response
from auth import get_current_user
from database import get_db
from models import User
from schemas import AssignmentUpsertRequest
from ..services.errors import ServiceError
from ..services.lecturer_assignments import (
    get_class_assignment as get_class_assignment_service,
    upsert_class_assignment as upsert_class_assignment_service,
)

router = APIRouter()


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


def _failure(error: ServiceError) -> JSONResponse:
    return error_response(
        error.status_code,
        error.code,
        error.message,
        detail=error.message,
        details=error.details,
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
    return _failure(
        ServiceError(
            status.HTTP_403_FORBIDDEN,
            "forbidden",
            "Assignment pengajar hanya tersedia untuk admin dan PJ Prodi.",
        )
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
    result = await get_class_assignment_service(db, class_section_id, scope)
    if isinstance(result, ServiceError):
        return _failure(result)
    return AssignmentEnvelope.model_validate({"data": result})


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
    result = await upsert_class_assignment_service(
        db,
        class_section_id,
        payload.academic_period_id,
        payload.user_id,
        payload.source,
        payload.is_pinned,
        scope,
        current_user,
    )
    if isinstance(result, ServiceError):
        return _failure(result)
    return AssignmentEnvelope.model_validate({"data": result})
