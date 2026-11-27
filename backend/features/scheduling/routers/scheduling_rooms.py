"""Master ruang untuk penjadwalan lintas program studi.

Admin mengelola semua ruang, termasuk kode, kapasitas, kepemilikan prodi, dan
status aktif. PJ Prodi hanya membaca ruang milik prodinya dan ruang bersama;
kapasitas selalu berasal dari data ruang, bukan tebakan solver.
"""

import uuid

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.errors import error_response
from auth import get_current_user
from database import get_db
from models import Room, User
from schemas import RoomCreateRequest, RoomListResponse, RoomResponse, RoomUpdateRequest

from ..services import rooms as room_service
from ..services.errors import ServiceError

router = APIRouter()


def _reject(error: ServiceError) -> JSONResponse:
    return error_response(
        error.status_code, error.code, error.message,
        detail=error.message, details=error.details,
    )


def _deny(code: str, message: str) -> JSONResponse:
    return _reject(ServiceError(status.HTTP_403_FORBIDDEN, code, message))


def _require_admin(current_user: User) -> JSONResponse | None:
    if current_user.role != "admin":
        return _deny("forbidden", "Manajemen master ruang hanya tersedia untuk admin.")
    return None


def _read_scope(current_user: User) -> uuid.UUID | None | JSONResponse:
    """None berartikan admin (tanpa filter), UUID membatasi PJ pada prodinya."""
    if current_user.role == "admin":
        return None

    profile = current_user.lecturer_profile
    if (
        current_user.role != "lecturer"
        or profile is None
        or not profile.is_program_coordinator
        or profile.study_program_id is None
    ):
        return _deny("forbidden", "Ruangan hanya dapat dilihat oleh admin dan PJ Prodi.")
    return profile.study_program_id


def _room_response(room: Room) -> RoomResponse:
    return RoomResponse(
        room_id=str(room.room_id),
        room_code=room.room_code,
        building=room.building,
        floor=room.floor,
        capacity=room.capacity,
        owner_study_program_id=(
            str(room.owner_study_program_id) if room.owner_study_program_id else None
        ),
        is_active=bool(room.is_active),
    )


async def _owner_key_present(request: Request) -> bool:
    try:
        raw = await request.json()
    except Exception:
        return False
    return isinstance(raw, dict) and "owner_study_program_id" in raw


@router.get("/scheduling/rooms", response_model=RoomListResponse)
async def list_rooms(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scope = _read_scope(current_user)
    if isinstance(scope, JSONResponse):
        return scope
    rooms = await room_service.list_records(db, scope)
    items = [_room_response(room) for room in rooms]
    return RoomListResponse(data=items, meta={"total": len(items)})


@router.post(
    "/scheduling/rooms",
    response_model=RoomResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_room(
    payload: RoomCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    denied = _require_admin(current_user)
    if denied is not None:
        return denied

    result = await room_service.create(
        db,
        room_code=payload.room_code,
        building=payload.building,
        floor=payload.floor,
        capacity=payload.capacity,
        is_active=payload.is_active,
        owner_study_program_id=payload.owner_study_program_id,
    )
    if isinstance(result, ServiceError):
        return _reject(result)
    return _room_response(result)


@router.patch("/scheduling/rooms/{room_id}", response_model=RoomResponse)
async def update_room(
    room_id: uuid.UUID,
    payload: RoomUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    denied = _require_admin(current_user)
    if denied is not None:
        return denied

    result = await room_service.update(
        db,
        room_id,
        room_code=payload.room_code,
        building=payload.building,
        floor=payload.floor,
        capacity=payload.capacity,
        is_active=payload.is_active,
        owner_study_program_id=payload.owner_study_program_id,
        owner_present=await _owner_key_present(request),
    )
    if isinstance(result, ServiceError):
        return _reject(result)
    return _room_response(result)
