"""Papan Jadwal Bersama lima prodi: kelas MK, status, dan konflik."""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.errors import error_response
from auth import get_current_user
from database import get_db
from models import User
from schemas import BoardData, BoardResponse, ConflictListResponse

from ..services import schedule_reads as reads
from ..services.errors import ServiceError

router = APIRouter()


def _reject(error: ServiceError) -> JSONResponse:
    return error_response(
        error.status_code,
        error.code,
        error.message,
        detail=error.message,
        details=error.details,
    )


def _scope(user: User) -> tuple[bool, str | None, bool]:
    """Kembali: izin edit admin, prodi PJ, izin edit pada metadata."""
    profile = user.lecturer_profile
    actor = (
        str(profile.study_program_id)
        if (
            user.role == "lecturer"
            and profile is not None
            and profile.is_program_coordinator
            and profile.study_program_id
        )
        else None
    )
    return (
        user.role == "admin" and user.is_active,
        actor,
        user.role == "admin" or actor is not None,
    )


@router.get("/scheduling/board", response_model=BoardResponse)
async def get_board(
    period_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    admin_can_edit, actor, can_edit = _scope(current_user)
    context = await reads.build_board_context(
        db, period_id, admin_can_edit=admin_can_edit, actor_program_id=actor
    )
    if isinstance(context, ServiceError):
        return _reject(context)
    response = BoardResponse(
        data=BoardData(
            academic_period_id=str(context.period.academic_period_id),
            period_label=reads.period_label(context.period),
            classes=context.classes,
            conflicts=context.conflicts,
            programs=context.programs,
            unassigned=context.unassigned,
        ),
        meta=reads.board_meta(context, actor, can_edit),
    )
    return JSONResponse(content=response.model_dump(mode="json"))


@router.get("/scheduling/conflicts", response_model=ConflictListResponse)
async def get_conflicts(
    period_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    admin_can_edit, actor, can_edit = _scope(current_user)
    context = await reads.build_board_context(
        db, period_id, admin_can_edit=admin_can_edit, actor_program_id=actor
    )
    if isinstance(context, ServiceError):
        return _reject(context)
    return ConflictListResponse(
        data=context.conflicts, meta=reads.board_meta(context, actor, can_edit)
    )
