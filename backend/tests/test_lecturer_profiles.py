"""Kontrak data profil dosen dan PJ Prodi."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from models import LecturerProfile, StudyProgram, User


def _label() -> str:
    return uuid.uuid4().hex[:10]


def _program_id(client, db_session) -> uuid.UUID:
    async def run():
        label = _label()
        program = StudyProgram(
            program_code=f"UJI-{label}",
            program_name=f"Program Uji {label}",
        )
        db_session.add(program)
        await db_session.flush()
        await db_session.commit()
        return program.study_program_id

    return client.portal.call(run)


def _add_lecturer(
    client, db_session, program_id: uuid.UUID, *, coordinator: bool, employee_number=None
) -> uuid.UUID:
    async def run():
        label = _label()
        user = User(
            email=f"dosen.uji.{label}@ftmm.unair.ac.id",
            full_name=f"Dosen Uji {label}",
            role="lecturer",
        )
        db_session.add(user)
        await db_session.flush()
        profile = LecturerProfile(
            user_id=user.user_id,
            study_program_id=program_id,
            is_program_coordinator=coordinator,
            employee_number=employee_number,
        )
        db_session.add(profile)
        await db_session.commit()
        return user.user_id

    return client.portal.call(run)


def test_profil_pj_persis_dengan_program_studi(client, db_session):
    program_id = _program_id(client, db_session)
    user_id = _add_lecturer(
        client,
        db_session,
        program_id,
        coordinator=True,
        employee_number=f"PJ-{_label()}",
    )

    async def read():
        profile = (
            await db_session.execute(
                select(LecturerProfile)
                .join(LecturerProfile.study_program)
                .options(selectinload(LecturerProfile.study_program))
                .where(LecturerProfile.user_id == user_id)
            )
        ).scalar_one()
        user = (
            await db_session.execute(
                select(User)
                .options(selectinload(User.lecturer_profile))
                .where(User.user_id == user_id)
            )
        ).scalar_one()
        return profile, user

    profile, user = client.portal.call(read)
    assert profile.is_program_coordinator is True
    assert profile.employee_number is not None
    assert profile.study_program.study_program_id == program_id
    assert user.lecturer_profile is not None
    assert user.lecturer_profile.user_id == user_id


def test_pj_kedua_di_program_sama_ditolak_database(client, db_session):
    program_id = _program_id(client, db_session)
    _add_lecturer(client, db_session, program_id, coordinator=True)

    with pytest.raises(IntegrityError):
        _add_lecturer(client, db_session, program_id, coordinator=True)


def test_dosen_non_pj_kedua_di_program_sama_diizinkan(client, db_session):
    program_id = _program_id(client, db_session)
    first_id = _add_lecturer(client, db_session, program_id, coordinator=True)
    second_id = _add_lecturer(client, db_session, program_id, coordinator=False)

    async def read():
        rows = (
            await db_session.execute(
                select(LecturerProfile).where(
                    LecturerProfile.user_id.in_([first_id, second_id])
                )
            )
        ).scalars().all()
        return {row.user_id: row for row in rows}

    profiles = client.portal.call(read)
    assert profiles[first_id].is_program_coordinator is True
    assert profiles[second_id].is_program_coordinator is False
    assert profiles[second_id].study_program_id == program_id


def test_pengguna_tanpa_profil_dosen_membaca_none(client, db_session):
    async def run():
        label = _label()
        user = User(
            email=f"non.dosen.{label}@ftmm.unair.ac.id",
            full_name=f"Pengguna Uji {label}",
            role="admin",
        )
        db_session.add(user)
        await db_session.commit()
        fresh = (
            await db_session.execute(
                select(User)
                .options(selectinload(User.lecturer_profile))
                .where(User.user_id == user.user_id)
            )
        ).scalar_one()
        return fresh.lecturer_profile

    assert client.portal.call(run) is None
