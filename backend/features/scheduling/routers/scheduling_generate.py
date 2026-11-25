"""Endpoint pembangkit jadwal dan diagnosis kelas yang belum terjadwal."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.errors import error_response
from auth import get_current_user
from database import get_db
from models import User
from schemas import GenerateRequest, GenerateResponse

from ..scheduler import reason_code, reason_label
from ..services import generation as generation_service
from ..services.errors import ServiceError

router = APIRouter()


class ClassCountOverrideRequest(BaseModel):
    academic_period_id: str | None = None
    course_id: str
    study_program_id: str
    class_count: int = Field(..., ge=1, le=3)


class ClassCountOverrideResponse(BaseModel):
    override_id: str
    academic_period_id: str
    course_id: str
    study_program_id: str
    class_count: int
    created: bool


def _reject(error: ServiceError) -> JSONResponse:
    return error_response(
        error.status_code,
        error.code,
        error.message,
        detail=error.message,
        details=error.details,
    )


def _forbidden(code: str, message: str) -> JSONResponse:
    return error_response(status.HTTP_403_FORBIDDEN, code, message, detail=message)


def _field_error(
    field: str, message: str, code: str = "validation_error"
) -> JSONResponse:
    return _reject(generation_service.field_failure(field, message, code))


def _require_scheduler(current_user: User) -> JSONResponse | None:
    """Admin dan PJ Prodi boleh membangkitkan jadwal."""
    if current_user.role == "admin":
        return None
    profile = current_user.lecturer_profile
    if (
        current_user.role == "lecturer"
        and profile is not None
        and profile.is_program_coordinator
        and profile.study_program is not None
    ):
        return None
    return _forbidden(
        "forbidden", "Pembangkitan jadwal hanya tersedia untuk admin dan PJ Prodi."
    )


def _actor_scope(current_user: User) -> UUID | None:
    profile = current_user.lecturer_profile
    return profile.study_program_id if profile is not None else None


def _generate_payload(result: GenerateResponse) -> dict[str, Any]:
    payload = result.model_dump(mode="json")
    for item in payload["unassigned"]:
        code = reason_code(item["reason"])
        item["reason_code"] = code
        item["reason"] = reason_label(code)
    return payload


@router.post("/scheduling/generate", response_model=GenerateResponse)
async def generate(
    payload: GenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    denied = _require_scheduler(current_user)
    if denied is not None:
        return denied

    if payload.mode == "full_reset":
        if current_user.role != "admin":
            return _forbidden("forbidden", "Mode full_reset hanya tersedia untuk admin.")
        if not payload.confirm_full_reset:
            return _field_error(
                "confirm_full_reset",
                "Mode full_reset memerlukan konfirmasi confirm_full_reset=true.",
                "confirmation_required",
            )

    result = await generation_service.generate(
        db,
        payload,
        current_user.user_id,
        current_user.role == "admin",
        _actor_scope(current_user),
    )
    if isinstance(result, ServiceError):
        return _reject(result)
    return JSONResponse(content=_generate_payload(result))


@router.post(
    "/scheduling/class-count-overrides", response_model=ClassCountOverrideResponse
)
async def put_class_count_override(
    payload: ClassCountOverrideRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    denied = _require_scheduler(current_user)
    if denied is not None:
        return denied

    result = await generation_service.put_class_count_override(
        db,
        payload,
        current_user.role == "admin",
        _actor_scope(current_user),
    )
    if isinstance(result, ServiceError):
        return _reject(result)
    record, created = result
    return ClassCountOverrideResponse(
        override_id=str(record.id),
        academic_period_id=str(record.academic_period_id),
        course_id=str(record.course_id),
        study_program_id=str(record.study_program_id),
        class_count=record.class_count,
        created=created,
    )


@router.get("/scheduling/unassigned")
async def list_unassigned(
    academic_period_id: str | None = None,
    study_program_id: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    denied = _require_scheduler(current_user)
    if denied is not None:
        return denied

    requested = None
    if study_program_id is not None:
        requested = generation_service.parse_id(study_program_id, "study_program_id")
        if isinstance(requested, ServiceError):
            return _reject(requested)

    if current_user.role == "admin":
        scope = requested
    else:
        scope = _actor_scope(current_user)
        if scope is None:
            return _forbidden("forbidden", "PJ Prodi belum memiliki program studi.")
        if requested is not None and requested != scope:
            return _forbidden(
                "akses_prodi_ditolak",
                "PJ hanya dapat melihat diagnosis prodinya sendiri.",
            )

    period = await generation_service.resolve_period(db, academic_period_id)
    if isinstance(period, ServiceError):
        return _reject(period)
    result = await generation_service.list_unassigned(db, period, scope)
    meta = {
        "total": len(result.data),
        "academic_period_id": str(result.academic_period_id),
        "study_program_id": result.study_program_id,
        "run_id": str(result.run_id) if result.run_id is not None else None,
    }
    if result.run_id is not None:
        meta.update(mode=result.mode, stats=result.stats)
    return {"data": result.data, "meta": meta}
