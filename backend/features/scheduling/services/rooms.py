"""Operasi domain master ruang: duplikat, kepemilikan, kunci input, dan revisi."""

import uuid

from fastapi import status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Room, StudyProgram
from scheduling_common import current_period_id

from ..scheduler import bump_input_revisions, scheduling_input_lock
from . import UNPROCESSABLE
from .errors import ServiceError


def _deny(status_code: int, code: str, message: str) -> ServiceError:
    return ServiceError(status_code, code, message)


def _field_failure(field: str, message: str, code: str) -> ServiceError:
    return ServiceError(
        UNPROCESSABLE,
        "validation_error",
        message,
        [{"field": field, "message": message, "code": code}],
    )


async def _resolve_program(
    db: AsyncSession, raw: str | None, field: str
) -> uuid.UUID | None | ServiceError:
    """Terjemahkan ID prodi pemilik; kosong berarti ruang bersama."""
    value = raw.strip() if isinstance(raw, str) else ""
    if not value:
        return None
    try:
        program_id = uuid.UUID(value)
    except (ValueError, TypeError, AttributeError):
        return _field_failure(field, "Program studi tidak valid.", "invalid_uuid")
    exists = await db.execute(
        select(StudyProgram.study_program_id).where(
            StudyProgram.study_program_id == program_id
        )
    )
    if exists.scalar_one_or_none() is None:
        return _field_failure(
            field, "Program studi tidak ditemukan.", "study_program_not_found"
        )
    return program_id


async def _active_period_guard(
    db: AsyncSession, study_program_ids: set[uuid.UUID] | None
) -> tuple[uuid.UUID | None, ServiceError | None]:
    period_id = await current_period_id(db)
    if period_id is None:
        return None, None
    locked = await scheduling_input_lock(db, period_id, study_program_ids)
    if locked is not None:
        code, message = locked
        return None, _deny(409, code, message)
    return period_id, None


async def list_records(
    db: AsyncSession, scope: uuid.UUID | None
) -> list[Room]:
    stmt = select(Room).order_by(Room.room_code, Room.room_id)
    if scope is not None:
        stmt = stmt.where(
            or_(
                Room.owner_study_program_id == scope,
                Room.owner_study_program_id.is_(None),
            )
        )
    return list((await db.execute(stmt)).scalars().all())


async def create(
    db: AsyncSession,
    *,
    room_code: str,
    building: str,
    floor: str | None,
    capacity: int,
    is_active: bool,
    owner_study_program_id: str | None,
) -> Room | ServiceError:
    code = room_code.strip()
    duplicate = await db.execute(select(Room.room_id).where(Room.room_code == code))
    if duplicate.scalar_one_or_none() is not None:
        return _deny(
            status.HTTP_409_CONFLICT,
            "room_code_exists",
            "Kode ruang sudah digunakan.",
        )

    owner_id = await _resolve_program(
        db, owner_study_program_id, "owner_study_program_id"
    )
    if isinstance(owner_id, ServiceError):
        return owner_id
    period_id, denied = await _active_period_guard(
        db, {owner_id} if owner_id is not None else None
    )
    if denied is not None:
        return denied

    room = Room(
        room_code=code,
        capacity=capacity,
        building=building,
        floor=floor,
        owner_study_program_id=owner_id,
        is_active=is_active,
    )
    db.add(room)
    await db.flush()
    if period_id is not None:
        await bump_input_revisions(
            db, period_id, {owner_id} if owner_id is not None else None
        )
    await db.commit()
    await db.refresh(room)
    return room


async def update(
    db: AsyncSession,
    room_id: uuid.UUID,
    *,
    room_code: str | None,
    building: str | None,
    floor: str | None,
    capacity: int | None,
    is_active: bool | None,
    owner_study_program_id: str | None,
    owner_present: bool,
) -> Room | ServiceError:
    room = (
        await db.execute(select(Room).where(Room.room_id == room_id))
    ).scalars().first()
    if room is None:
        return _deny(
            status.HTTP_404_NOT_FOUND, "room_not_found", "Ruang tidak ditemukan."
        )

    owner_id = room.owner_study_program_id
    if owner_present:
        owner_id = await _resolve_program(
            db, owner_study_program_id, "owner_study_program_id"
        )
        if isinstance(owner_id, ServiceError):
            return owner_id

    room_program_ids = {
        program_id
        for program_id in (room.owner_study_program_id, owner_id)
        if program_id is not None
    }
    period_id, denied = await _active_period_guard(db, room_program_ids or None)
    if denied is not None:
        return denied
    before = (
        room.room_code,
        room.capacity,
        room.building,
        room.floor,
        room.is_active,
        room.owner_study_program_id,
    )

    if room_code is not None:
        code = room_code.strip()
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

    if capacity is not None:
        room.capacity = capacity
    if building is not None:
        room.building = building
    if floor is not None:
        room.floor = floor
    if is_active is not None:
        room.is_active = is_active
    if owner_present:
        room.owner_study_program_id = owner_id
    changed = before != (
        room.room_code,
        room.capacity,
        room.building,
        room.floor,
        room.is_active,
        room.owner_study_program_id,
    )
    await db.flush()
    if period_id is not None and changed:
        await bump_input_revisions(db, period_id, room_program_ids or None)

    await db.commit()
    await db.refresh(room)
    return room
