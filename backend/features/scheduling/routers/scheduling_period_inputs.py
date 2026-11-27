"""Period-scoped lecturer preferences."""

from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.errors import error_response
from auth import get_current_user
from database import get_db
from models import User
from schemas import (
    PreferenceCopyRequest,
    PreferenceListResponse,
    PreferencePeriodListResponse,
    PreferenceReplaceRequest,
    PreferenceSlotRequest,
)
from ..services.errors import ServiceError
from ..services.preferences import (
    PreferenceSlot,
    copy_preferences,
    get_preferences,
    list_periods,
    replace_preferences,
)
from ._common import resolve_period

router = APIRouter()

_UNPROCESSABLE = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)


def _failure(error: ServiceError) -> JSONResponse:
    return error_response(
        error.status_code,
        error.code,
        error.message,
        detail=error.message,
        details=error.details,
    )


def _field_error(field: str, message: str, code: str) -> JSONResponse:
    return _failure(
        ServiceError(
            _UNPROCESSABLE,
            code,
            message,
            details=[{"field": field, "message": message, "code": code}],
        )
    )


def _require_self_lecturer(current_user: User) -> JSONResponse | None:
    if (
        current_user.role == "lecturer"
        and current_user.lecturer_profile is not None
    ):
        return None
    return _failure(
        ServiceError(
            status.HTTP_403_FORBIDDEN,
            "forbidden",
            "Hanya dosen yang dapat mengelola preferensinya sendiri.",
        )
    )


@router.get(
    "/scheduling/preferences/periods",
    response_model=PreferencePeriodListResponse,
)
async def list_preference_periods(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return PreferencePeriodListResponse.model_validate(await list_periods(db))


@router.get("/scheduling/preferences/me", response_model=PreferenceListResponse)
async def get_my_preferences(
    academic_period_id: UUID | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    denied = _require_self_lecturer(current_user)
    if denied is not None:
        return denied
    period = await resolve_period(db, academic_period_id, _failure)
    if isinstance(period, JSONResponse):
        return period
    return PreferenceListResponse.model_validate(
        await get_preferences(
            db,
            period.academic_period_id,
            current_user.user_id,
            current_user.lecturer_profile.study_program_id,
        )
    )


@router.put("/scheduling/preferences/me", response_model=PreferenceListResponse)
async def replace_my_preferences(
    payload: list[PreferenceSlotRequest] | PreferenceReplaceRequest = Body(...),
    academic_period_id: UUID | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    denied = _require_self_lecturer(current_user)
    if denied is not None:
        return denied
    requested_period_id = (
        payload.academic_period_id if isinstance(payload, PreferenceReplaceRequest) else None
    )
    if (
        academic_period_id is not None
        and requested_period_id is not None
        and academic_period_id != requested_period_id
    ):
        return _field_error(
            "academic_period_id",
            "Periode akademik pada query dan body harus sama.",
            "period_mismatch",
        )
    period = await resolve_period(db, academic_period_id or requested_period_id, _failure)
    if isinstance(period, JSONResponse):
        return period
    slots = [
        PreferenceSlot(**slot.model_dump())
        for slot in (payload if isinstance(payload, list) else payload.slots)
    ]
    result = await replace_preferences(
        db,
        period.academic_period_id,
        current_user.user_id,
        current_user.lecturer_profile.study_program_id,
        slots,
    )
    if isinstance(result, ServiceError):
        return _failure(result)
    return PreferenceListResponse.model_validate(result)


@router.post("/scheduling/preferences/me/copy", response_model=PreferenceListResponse)
async def copy_my_preferences(
    payload: PreferenceCopyRequest = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    denied = _require_self_lecturer(current_user)
    if denied is not None:
        return denied
    if payload.from_academic_period_id == payload.academic_period_id:
        return _field_error(
            "academic_period_id",
            "Periode sumber dan tujuan harus berbeda.",
            "same_period",
        )
    source_period = await resolve_period(db, payload.from_academic_period_id, _failure)
    if isinstance(source_period, JSONResponse):
        return source_period
    target_period = await resolve_period(db, payload.academic_period_id, _failure)
    if isinstance(target_period, JSONResponse):
        return target_period
    result = await copy_preferences(
        db,
        source_period.academic_period_id,
        target_period.academic_period_id,
        current_user.user_id,
        current_user.lecturer_profile.study_program_id,
        payload.overwrite,
    )
    if isinstance(result, ServiceError):
        return _failure(result)
    return PreferenceListResponse.model_validate(result)
