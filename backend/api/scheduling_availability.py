"""Ketersediaan waktu dosen untuk penjadwalan lintas lima program studi."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, status
from fastapi.responses import JSONResponse
from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.errors import error_response
from auth import get_current_user
from database import get_db
from models import LecturerAvailability, LecturerProfile, StudyProgram, User
from schemas import (
    AvailabilityListResponse,
    AvailabilityResponse,
    AvailabilitySlotRequest,
)
from scheduling_common import DAY_NAMES, blocks_overlap

router = APIRouter()

UNPROCESSABLE = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)


class AvailabilityReplaceRequest(BaseModel):
    """Menerima daftar slot apa adanya maupun dibungkus oleh frontend."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    slots: list[AvailabilitySlotRequest] = Field(
        default_factory=list,
        validation_alias=AliasChoices("slots", "data", "availability"),
    )


def _slots_from_payload(
    payload: list[AvailabilitySlotRequest] | AvailabilityReplaceRequest,
) -> list[AvailabilitySlotRequest]:
    if isinstance(payload, list):
        return payload
    return payload.slots


def _overlap_detail(slots: list[AvailabilitySlotRequest]) -> dict[str, Any] | None:
    """Cari satu pasangan slot bertabrakan pada hari yang sama."""
    ordered = sorted(slots, key=lambda slot: (slot.day_of_week, slot.start_hour))
    by_day: dict[int, list[AvailabilitySlotRequest]] = {}
    for slot in ordered:
        seen = by_day.setdefault(slot.day_of_week, [])
        for first in seen:
            if blocks_overlap(
                first.start_hour, first.end_hour, slot.start_hour, slot.end_hour
            ):
                return {
                    "day_of_week": slot.day_of_week,
                    "day_name": DAY_NAMES.get(slot.day_of_week),
                    "first_start_hour": first.start_hour,
                    "first_end_hour": first.end_hour,
                    "second_start_hour": slot.start_hour,
                    "second_end_hour": slot.end_hour,
                }
        seen.append(slot)
    return None


def _response(rows: list[LecturerAvailability]) -> AvailabilityListResponse:
    ordered = sorted(rows, key=lambda row: (row.day_of_week, row.start_hour))
    return AvailabilityListResponse(
        data=[
            AvailabilityResponse(
                availability_id=str(row.availability_id),
                day_of_week=row.day_of_week,
                start_hour=row.start_hour,
                end_hour=row.end_hour,
                day_name=DAY_NAMES.get(row.day_of_week),
                user_id=str(row.user_id),
            )
            for row in ordered
        ],
        meta={"count": len(ordered)},
    )


async def _slots_for(db: AsyncSession, user_id: UUID) -> list[LecturerAvailability]:
    result = await db.execute(
        select(LecturerAvailability)
        .where(LecturerAvailability.user_id == user_id)
        .order_by(LecturerAvailability.day_of_week, LecturerAvailability.start_hour)
    )
    return list(result.scalars().all())


def _deny(
    code: str,
    message: str,
    status_code: int,
    details: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    return error_response(
        status_code, code, message, detail=message, details=details or []
    )


async def _replace_availability(
    db: AsyncSession,
    user_id: UUID,
    payload: list[AvailabilitySlotRequest] | AvailabilityReplaceRequest,
) -> AvailabilityListResponse | JSONResponse:
    """Timpa seluruh slot untuk user_id yang diberikan, tanpa otorisasi."""
    slots = _slots_from_payload(payload)
    overlap = _overlap_detail(slots)
    if overlap is not None:
        return _deny(
            "overlapping_availability",
            "Slot ketersediaan bertabrakan pada hari yang sama.",
            UNPROCESSABLE,
            [overlap],
        )

    await db.execute(
        delete(LecturerAvailability).where(LecturerAvailability.user_id == user_id)
    )
    new_rows = [
        LecturerAvailability(
            user_id=user_id,
            day_of_week=slot.day_of_week,
            start_hour=slot.start_hour,
            end_hour=slot.end_hour,
        )
        for slot in slots
    ]
    db.add_all(new_rows)
    await db.commit()
    return _response(new_rows)


@router.put("/scheduling/availability/me", response_model=AvailabilityListResponse)
async def replace_my_availability(
    payload: list[AvailabilitySlotRequest] | AvailabilityReplaceRequest = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Timpa seluruh slot milik sendiri; user_id tidak pernah diambil dari request."""
    return await _replace_availability(db, current_user.user_id, payload)


@router.get("/scheduling/availability/me", response_model=AvailabilityListResponse)
async def get_my_availability(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return _response(await _slots_for(db, current_user.user_id))


@router.get("/scheduling/availability/lecturers")
async def list_availability_lecturers(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Daftar dosen untuk pemilih ketersediaan, dibatasi prodi bagi PJ."""
    is_admin = current_user.role == "admin"
    own_profile = current_user.lecturer_profile
    is_pj = bool(
        not is_admin
        and current_user.role == "lecturer"
        and own_profile is not None
        and own_profile.is_program_coordinator
    )
    if not is_admin and not is_pj:
        return _deny(
            "forbidden",
            "Hanya admin atau PJ prodi yang dapat melihat daftar dosen.",
            status.HTTP_403_FORBIDDEN,
        )

    query = (
        select(User.user_id, User.full_name, StudyProgram.program_code)
        .join(LecturerProfile, LecturerProfile.user_id == User.user_id)
        .join(
            StudyProgram,
            StudyProgram.study_program_id == LecturerProfile.study_program_id,
        )
        .where(User.role == "lecturer")
    )
    if is_pj:
        query = query.where(
            LecturerProfile.study_program_id == own_profile.study_program_id
        )
    rows = (
        await db.execute(query.order_by(User.full_name, User.user_id))
    ).all()
    return {
        "data": [
            {
                "user_id": str(row.user_id),
                "full_name": row.full_name,
                "study_program_code": row.program_code,
            }
            for row in rows
        ],
        "meta": {"total": len(rows)},
    }


@router.put(
    "/scheduling/availability/{user_id}", response_model=AvailabilityListResponse
)
async def replace_lecturer_availability(
    user_id: UUID,
    payload: list[AvailabilitySlotRequest] | AvailabilityReplaceRequest = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Path eksplisit tetap hanya menulis slot milik caller, termasuk untuk admin."""
    if user_id != current_user.user_id:
        return _deny(
            "forbidden",
            "Dosen hanya dapat memperbarui ketersediaannya sendiri.",
            status.HTTP_403_FORBIDDEN,
        )
    return await _replace_availability(db, user_id, payload)


@router.get(
    "/scheduling/availability/{user_id}", response_model=AvailabilityListResponse
)
async def get_lecturer_availability(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Admin atau PJ prodi pemilik dosen yang boleh membaca slot dosen lain."""
    is_admin = current_user.role == "admin"
    own_profile = current_user.lecturer_profile
    if not is_admin and not (
        current_user.role == "lecturer"
        and own_profile is not None
        and own_profile.is_program_coordinator
    ):
        return _deny(
            "forbidden",
            "Hanya admin atau PJ prodi pemilik dosen yang dapat melihat ketersediaan ini.",
            status.HTTP_403_FORBIDDEN,
        )

    target = (
        await db.execute(
            select(User)
            .options(selectinload(User.lecturer_profile))
            .where(User.user_id == user_id)
        )
    ).scalars().first()
    if target is None or target.lecturer_profile is None:
        return _deny(
            "not_found", "Dosen tidak ditemukan.", status.HTTP_404_NOT_FOUND
        )
    if not is_admin and (
        own_profile.study_program_id != target.lecturer_profile.study_program_id
    ):
        return _deny(
            "forbidden",
            "Hanya admin atau PJ prodi pemilik dosen yang dapat melihat ketersediaan ini.",
            status.HTTP_403_FORBIDDEN,
        )

    return _response(await _slots_for(db, user_id))
