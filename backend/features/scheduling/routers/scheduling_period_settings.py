"""Period-scoped preference settings and lecturer completion summary."""

from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.errors import error_response
from auth import get_current_user
from database import get_db
from models import StudyProgram, User
from schemas import (
    PeriodSettingsRequest,
    PeriodSettingsResponse,
    PreferenceSummaryResponse,
)
from ..services.errors import ServiceError
from ..services.period_settings import get_settings, put_settings
from ..services.preferences import preference_summary
from ._common import resolve_period

router = APIRouter()


def _failure(error: ServiceError) -> JSONResponse:
    return error_response(
        error.status_code,
        error.code,
        error.message,
        detail=error.message,
        details=error.details,
    )


def _preference_admin_scope(
    current_user: User, requested_program_id: UUID | None
) -> UUID | None | JSONResponse:
    if current_user.role == "admin":
        return requested_program_id
    profile = current_user.lecturer_profile
    if (
        current_user.role == "lecturer"
        and profile is not None
        and profile.is_program_coordinator
        and profile.study_program_id is not None
    ):
        if (
            requested_program_id is not None
            and requested_program_id != profile.study_program_id
        ):
            return _failure(
                ServiceError(
                    status.HTTP_403_FORBIDDEN,
                    "forbidden",
                    "PJ Prodi hanya dapat mengelola preferensi pada prodinya sendiri.",
                )
            )
        return profile.study_program_id
    return _failure(
        ServiceError(
            status.HTTP_403_FORBIDDEN,
            "forbidden",
            "Pengaturan preferensi hanya tersedia untuk admin dan PJ Prodi.",
        )
    )


async def _resolve_study_program(
    db: AsyncSession, study_program_id: UUID
) -> StudyProgram | JSONResponse:
    program = await db.get(StudyProgram, study_program_id)
    if program is None:
        return _failure(
            ServiceError(
                status.HTTP_404_NOT_FOUND,
                "study_program_not_found",
                "Program studi tidak ditemukan.",
            )
        )
    return program


@router.get("/scheduling/period-settings", response_model=PeriodSettingsResponse)
async def get_period_settings(
    academic_period_id: UUID | None = Query(None),
    study_program_id: UUID | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope = _preference_admin_scope(current_user, study_program_id)
    if isinstance(scope, JSONResponse):
        return scope
    period = await resolve_period(db, academic_period_id, _failure)
    if isinstance(period, JSONResponse):
        return period
    program = None
    if scope is not None:
        program = await _resolve_study_program(db, scope)
        if isinstance(program, JSONResponse):
            return program
    return PeriodSettingsResponse.model_validate(
        await get_settings(db, period.academic_period_id, scope, program)
    )


@router.put("/scheduling/period-settings", response_model=PeriodSettingsResponse)
async def put_period_settings(
    payload: PeriodSettingsRequest = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = current_user.lecturer_profile
    if (
        current_user.role == "lecturer"
        and profile is not None
        and profile.is_program_coordinator
        and "study_program_id" in payload.model_fields_set
        and payload.study_program_id != profile.study_program_id
    ):
        return _failure(
            ServiceError(
                status.HTTP_403_FORBIDDEN,
                "forbidden",
                "PJ Prodi hanya dapat mengatur deadline preferensi prodinya sendiri.",
            )
        )
    scope = _preference_admin_scope(current_user, payload.study_program_id)
    if isinstance(scope, JSONResponse):
        return scope
    period = await resolve_period(db, payload.academic_period_id, _failure)
    if isinstance(period, JSONResponse):
        return period
    program = None
    if scope is not None:
        program = await _resolve_study_program(db, scope)
        if isinstance(program, JSONResponse):
            return program
    result = await put_settings(
        db,
        period.academic_period_id,
        scope,
        program,
        payload.preference_deadline,
    )
    if isinstance(result, ServiceError):
        return _failure(result)
    return PeriodSettingsResponse.model_validate(result)


@router.get(
    "/scheduling/preferences/summary",
    response_model=PreferenceSummaryResponse,
)
async def list_preference_summary(
    academic_period_id: UUID | None = Query(None),
    study_program_id: UUID | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope = _preference_admin_scope(current_user, study_program_id)
    if isinstance(scope, JSONResponse):
        return scope
    period = await resolve_period(db, academic_period_id, _failure)
    if isinstance(period, JSONResponse):
        return period
    if scope is not None:
        program = await _resolve_study_program(db, scope)
        if isinstance(program, JSONResponse):
            return program
    return PreferenceSummaryResponse.model_validate(
        await preference_summary(db, period.academic_period_id, scope)
    )
