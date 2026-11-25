"""Edit jadwal kelas, finalisasi per prodi, dan pembukaan kunci KRS.

Perubahan manual tetap disimpan walaupun menghasilkan bentrok; bentrok
dilaporkan kembali supaya PJ Prodi dapat menindaklanjutinya. Aturan bentrok
di sini mengikuti Papan Jadwal Bersama: dosen yang sama atau ruang yang sama
dengan blok jam yang bertabrakan.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.errors import error_response
from auth import get_current_user
from database import get_db
from models import User
from schemas import (
    ClassMoveRequest,
    ClassMoveResponse,
    EditLogResponse,
    FinalizeResponse,
    UnlockRequest,
)

from ..services import schedule_management as management
from ..services.errors import ServiceError

router = APIRouter()

_NO_DETAIL_CODES = {"conflicts_exist", "schedule_stale", "unassigned_classes"}


def _reject(error: ServiceError) -> JSONResponse:
    extra = {"conflicts": error.details} if error.code == "conflicts_exist" else {}
    if error.code not in _NO_DETAIL_CODES:
        extra["detail"] = error.message
    return error_response(
        error.status_code,
        error.code,
        error.message,
        details=error.details,
        **extra,
    )


def _actor_program_id(current_user: User) -> UUID | None | ServiceError:
    """None berarti admin; UUID berarti PJ prodi; sisanya penolakan."""
    if current_user.role == "admin":
        return None
    profile = current_user.lecturer_profile
    if (
        current_user.role != "lecturer"
        or profile is None
        or not profile.is_program_coordinator
        or profile.study_program_id is None
    ):
        return ServiceError(
            status.HTTP_403_FORBIDDEN,
            "forbidden",
            "Perubahan jadwal hanya tersedia untuk admin dan PJ Prodi.",
        )
    return profile.study_program_id


@router.patch("/scheduling/classes/{section_id}", response_model=ClassMoveResponse)
async def move_class(
    section_id: UUID,
    payload: ClassMoveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    reason = payload.reason.strip()
    if not reason:
        return _reject(management.field_failure("reason", "Alasan perubahan jadwal wajib diisi.", "required"))
    actor_program = _actor_program_id(current_user)
    if isinstance(actor_program, ServiceError):
        return _reject(actor_program)
    result = await management.move_class(
        db, section_id, payload, reason, actor_program, current_user.user_id
    )
    if isinstance(result, ServiceError):
        return _reject(result)
    return result


@router.post(
    "/scheduling/periods/{period_id}/finalize", response_model=FinalizeResponse
)
async def finalize_period(
    period_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    actor_program = _actor_program_id(current_user)
    if isinstance(actor_program, ServiceError):
        return _reject(actor_program)
    if actor_program is None:
        return _reject(
            ServiceError(
                status.HTTP_403_FORBIDDEN,
                "forbidden",
                "Finalisasi jadwal dilakukan oleh PJ Prodi untuk prodinya sendiri.",
            )
        )
    result = await management.finalize_period(
        db, period_id, actor_program, current_user.user_id
    )
    if isinstance(result, ServiceError):
        return _reject(result)
    return result


@router.post("/scheduling/periods/{period_id}/unlock")
async def unlock_period(
    period_id: UUID,
    payload: UnlockRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "admin":
        return _reject(
            ServiceError(
                status.HTTP_403_FORBIDDEN,
                "forbidden",
                "Pembukaan kunci jadwal hanya tersedia untuk admin.",
            )
        )
    result = await management.unlock_period(db, period_id, payload, current_user.user_id)
    if isinstance(result, ServiceError):
        return _reject(result)
    return result


@router.get("/scheduling/edit-log", response_model=EditLogResponse)
async def get_edit_log(
    period_id: str | None = Query(default=None),
    class_section_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    actor_program = _actor_program_id(current_user)
    if isinstance(actor_program, ServiceError):
        return _reject(actor_program)
    entries = await management.get_edit_log(
        db, period_id, class_section_id, actor_program
    )
    if isinstance(entries, ServiceError):
        return _reject(entries)
    return EditLogResponse(data=entries, meta={"total": len(entries)})
