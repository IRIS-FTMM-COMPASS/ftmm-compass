"""Master ruang untuk penjadwalan lintas program studi.

Admin mengelola kode, kapasitas, kepemilikan prodi, dan status aktif ruang.
PJ Prodi hanya melihat ruang yang dimiliki prodinya; kapasitas selalu berasal
dari data ruang, bukan tebakan solver.
"""

import uuid

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.errors import error_response
from auth import get_current_user
from database import get_db
from models import Room, StudyProgram, User
from schemas import RoomCreateRequest, RoomListResponse, RoomResponse, RoomUpdateRequest

router = APIRouter()

_UNPROCESSABLE = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)


def _deny(status_code: int, code: str, message: str) -> JSONResponse:
    return error_response(status_code, code, message, detail=message)


def _field_error(field: str, message: str, code: str) -> JSONResponse:
    return error_response(
        _UNPROCESSABLE,
        "validation_error",
        message,
        detail=message,
        details=[{"field": field, "message": message, "code": code}],
    )


def _require_admin(current_user: User) -> JSONResponse | None:
    if current_user.role != "admin":
        return _deny(
            status.HTTP_403_FORBIDDEN,
            "forbidden",
            "Manajemen master ruang hanya tersedia untuk admin.",
        )
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
        return _deny(
            status.HTTP_403_FORBIDDEN,
            "forbidden",
            "Ruangan hanya dapat dilihat oleh admin dan PJ Prodi.",
        )
    return profile.study_program_id


def _room_response(room: Room) -> RoomResponse:
    return RoomResponse(
        room_id=str(room.room_id),
        room_code=room.room_code,
        building=room.building,
        floor=room.floor,
        capacity=room.capacity,
        owner_study_program_id=(
            str(room.owner_study_program_id)
            if room.owner_study_program_id is not None
            else None
        ),
        is_active=bool(room.is_active),
    )


async def _resolve_program(
    db: AsyncSession, raw: str | None, field: str
) -> uuid.UUID | None | JSONResponse:
    """Terjemahkan ID prodi pemilik; kosong berarti ruang bersama."""
    value = raw.strip() if isinstance(raw, str) else ""
    if not value:
        return None
    try:
        program_id = uuid.UUID(value)
    except (ValueError, TypeError, AttributeError):
        return _field_error(field, "Program studi tidak valid.", "invalid_uuid")
    exists = await db.execute(
        select(StudyProgram.study_program_id).where(
            StudyProgram.study_program_id == program_id
        )
    )
    if exists.scalar_one_or_none() is None:
        return _field_error(field, "Program studi tidak ditemukan.", "study_program_not_found")
    return program_id


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

    stmt = select(Room).order_by(Room.room_code, Room.room_id)
    if scope is not None:
        stmt = stmt.where(
            or_(
                Room.owner_study_program_id == scope,
                Room.owner_study_program_id.is_(None),
            )
        )
    rooms = (await db.execute(stmt)).scalars().all()
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

    code = payload.room_code.strip()
    duplicate = await db.execute(
        select(Room.room_id).where(Room.room_code == code)
    )
    if duplicate.scalar_one_or_none() is not None:
        return _deny(
            status.HTTP_409_CONFLICT,
            "room_code_exists",
            "Kode ruang sudah digunakan.",
        )

    owner_id = await _resolve_program(
        db, payload.owner_study_program_id, "owner_study_program_id"
    )
    if isinstance(owner_id, JSONResponse):
        return owner_id

    room = Room(
        room_code=code,
        capacity=payload.capacity,
        building=payload.building,
        floor=payload.floor,
        owner_study_program_id=owner_id,
        is_active=payload.is_active,
    )
    db.add(room)
    await db.commit()
    await db.refresh(room)
    return _room_response(room)


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

    room = (
        await db.execute(select(Room).where(Room.room_id == room_id))
    ).scalars().first()
    if room is None:
        return _deny(
            status.HTTP_404_NOT_FOUND,
            "room_not_found",
            "Ruang tidak ditemukan.",
        )

    if payload.room_code is not None:
        code = payload.room_code.strip()
        duplicate = await db.execute(
            select(Room.room_id).where(
                Room.room_code == code,
                Room.room_id != room_id,
            )
        )
        if duplicate.scalar_one_or_none() is not None:
            return _deny(
                status.HTTP_409_CONFLICT,
                "room_code_exists",
                "Kode ruang sudah digunakan.",
            )
        room.room_code = code

    if payload.capacity is not None:
        room.capacity = payload.capacity
    if payload.building is not None:
        room.building = payload.building

    if payload.floor is not None:
        room.floor = payload.floor

    if payload.is_active is not None:
        room.is_active = payload.is_active

    if await _owner_key_present(request):
        owner_id = await _resolve_program(
            db, payload.owner_study_program_id, "owner_study_program_id"
        )
        if isinstance(owner_id, JSONResponse):
            return owner_id
        room.owner_study_program_id = owner_id

    await db.commit()
    await db.refresh(room)
    return _room_response(room)
