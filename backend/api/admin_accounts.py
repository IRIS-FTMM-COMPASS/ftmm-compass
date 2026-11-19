"""Koreksi profil mahasiswa dan anonimisasi akun oleh admin."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.errors import error_response
from audit import record_admin_action
from auth import bump_token_version, get_current_user
from curriculum_admin import (
    active_plan_target_semester,
    current_curriculum_id,
    resolve_cohort_curriculum_id,
)
from database import get_db
from models import StudentProfile, StudyProgram, User
from schemas import AccountResponse, AdminProfileUpdateRequest, AnonymizeRequest

router = APIRouter()

_UNPROCESSABLE = getattr(
    status, "HTTP_422_UNPROCESSABLE_CONTENT", 422
)


def _field_error(field: str, message: str, code: str):
    return error_response(
        _UNPROCESSABLE,
        "validation_error",
        "Data yang dikirim tidak valid.",
        detail="Data yang dikirim tidak valid.",
        details=[{"field": field, "message": message, "code": code}],
    )


def _require_admin(current_user: User):
    if current_user.role != "admin":
        return error_response(
            status.HTTP_403_FORBIDDEN,
            "forbidden",
            "Akses manajemen akun hanya tersedia untuk admin.",
        )
    return None


async def _load_user(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    return (
        await db.execute(
            select(User)
            .options(
                selectinload(User.student_profile).selectinload(
                    StudentProfile.study_program
                )
            )
            .where(User.user_id == user_id)
        )
    ).scalars().first()


async def _user_flag(db: AsyncSession, user_id: uuid.UUID, column: str):
    if column not in ("needs_revalidation", "anonymized_at"):
        raise ValueError("Kolom flag pengguna tidak dikenal")
    return (
        await db.execute(
            text(f"SELECT {column} FROM users WHERE user_id = CAST(:uid AS uuid)"),
            {"uid": str(user_id)},
        )
    ).scalar_one_or_none()


async def _account_payload(
    db: AsyncSession,
    user: User,
    profile: StudentProfile | None,
    program: StudyProgram | None,
) -> dict:
    needs_revalidation = await _user_flag(db, user.user_id, "needs_revalidation")
    anonymized_at = await _user_flag(db, user.user_id, "anonymized_at")
    data = AccountResponse(
        user_id=str(user.user_id),
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        status="active" if user.is_active else "inactive",
        student_number=profile.student_number if profile is not None else None,
        created_at=user.created_at.isoformat() if user.created_at else None,
        needs_revalidation=bool(needs_revalidation),
        study_program=program.program_name if program is not None else None,
        admission_year=profile.admission_year if profile is not None else None,
        current_semester=profile.current_semester if profile is not None else None,
    ).model_dump()
    data.update(
        {
            "study_program_id": (
                str(profile.study_program_id) if profile is not None else None
            ),
            "program_code": program.program_code if program is not None else None,
            "anonymized_at": str(anonymized_at) if anonymized_at is not None else None,
            "student_profile": (
                {
                    "student_number": profile.student_number,
                    "study_program": program.program_name if program is not None else None,
                    "study_program_id": str(profile.study_program_id),
                    "program_code": program.program_code if program is not None else None,
                    "admission_year": profile.admission_year,
                    "current_semester": profile.current_semester,
                }
                if profile is not None
                else None
            ),
        }
    )
    return {"data": data}


@router.get("/admin/accounts/{user_id}/profile")
async def get_student_profile(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    denied = _require_admin(current_user)
    if denied is not None:
        return denied

    user = await _load_user(db, user_id)
    if user is None:
        return error_response(status.HTTP_404_NOT_FOUND, "not_found", "Akun tidak ditemukan.")
    profile = user.student_profile
    if user.role != "student" or profile is None:
        return _field_error(
            "user_id",
            "Data akademik hanya tersedia pada akun mahasiswa.",
            "non_student_target",
        )
    return await _account_payload(db, user, profile, profile.study_program)


@router.patch("/admin/accounts/{user_id}/profile")
async def update_student_profile(
    user_id: uuid.UUID,
    payload: AdminProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    denied = _require_admin(current_user)
    if denied is not None:
        return denied

    user = await _load_user(db, user_id)
    if user is None:
        return error_response(status.HTTP_404_NOT_FOUND, "not_found", "Akun tidak ditemukan.")
    profile = user.student_profile
    if user.role != "student" or profile is None:
        return _field_error(
            "user_id",
            "Koreksi data akademik hanya tersedia untuk akun mahasiswa.",
            "non_student_target",
        )

    study_program = (
        await db.execute(
            select(StudyProgram).where(
                StudyProgram.study_program_id == payload.study_program_id
            )
        )
    ).scalars().first()
    if study_program is None:
        return _field_error(
            "study_program_id", "Program studi tidak ditemukan.", "study_program_not_found"
        )

    this_year = datetime.now(timezone.utc).year
    if payload.admission_year < 2000 or payload.admission_year > this_year:
        return _field_error(
            "admission_year",
            f"Tahun angkatan harus antara 2000 dan {this_year}.",
            "invalid_admission_year",
        )
    if payload.current_semester < 1 or payload.current_semester > 14:
        return _field_error(
            "current_semester",
            "Semester berjalan harus antara 1 dan 14.",
            "invalid_current_semester",
        )

    student_number = payload.student_number.strip()
    if not student_number:
        return _field_error(
            "student_number", "NIM tidak boleh kosong.", "invalid_student_number"
        )
    duplicate = (
        await db.execute(
            select(StudentProfile.user_id).where(
                StudentProfile.student_number == student_number,
                StudentProfile.user_id != user_id,
            )
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        return _field_error(
            "student_number",
            "NIM sudah digunakan oleh akun mahasiswa lain.",
            "duplicate_student_number",
        )

    target_semester = await active_plan_target_semester(db, user_id)
    if target_semester is not None and payload.current_semester > target_semester:
        return _field_error(
            "current_semester",
            "Semester berjalan ("
            f"{payload.current_semester}) tidak boleh melebihi target semester "
            f"kelulusan ({target_semester}) pada rencana studi aktif.",
            "semester_exceeds_target",
        )

    changes: list[tuple[str, str | None, str | None]] = []
    if profile.study_program_id != payload.study_program_id:
        changes.append(
            ("study_program_id", str(profile.study_program_id), str(payload.study_program_id))
        )
    if profile.admission_year != payload.admission_year:
        changes.append(
            ("admission_year", str(profile.admission_year), str(payload.admission_year))
        )
    if profile.student_number != student_number:
        changes.append(("student_number", profile.student_number, student_number))
    if profile.current_semester != payload.current_semester:
        changes.append(
            ("current_semester", str(profile.current_semester), str(payload.current_semester))
        )
    cohort_changed = any(
        field in ("study_program_id", "admission_year") for field, _, _ in changes
    )

    if changes and not payload.reason.strip():
        return _field_error(
            "reason",
            "Alasan wajib diisi saat mengubah data akademik mahasiswa.",
            "reason_required",
        )

    new_curriculum_id = None
    if cohort_changed:
        new_curriculum_id = await resolve_cohort_curriculum_id(
            db,
            study_program_id=payload.study_program_id,
            admission_year=payload.admission_year,
        )
        if new_curriculum_id is None:
            return _field_error(
                "admission_year",
                "Kurikulum untuk program studi dan tahun angkatan tersebut tidak ditemukan.",
                "curriculum_not_found",
            )
        old_curriculum_id = await current_curriculum_id(db, user_id)
        if old_curriculum_id is None:
            return _field_error(
                "study_program_id",
                "Penugasan kurikulum aktif mahasiswa tidak ditemukan.",
                "curriculum_assignment_missing",
            )

    # Snapshot jejak wewenang diambil sebelum mutasi apa pun.
    for field_name, old_value, new_value in changes:
        await record_admin_action(
            db,
            actor=current_user,
            target=user,
            action="profile_correction",
            reason=payload.reason,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
        )

    if changes:
        profile.study_program_id = payload.study_program_id
        profile.study_program = study_program
        profile.admission_year = payload.admission_year
        profile.student_number = student_number
        profile.current_semester = payload.current_semester

    # SQL function switch_student_curriculum() memeriksa program studi pada
    # student_profiles, sehingga perubahan ORM harus terlihat di session dulu.
    await db.flush()

    if cohort_changed:
        await db.execute(
            text(
                "UPDATE users SET needs_revalidation = true "
                "WHERE user_id = CAST(:uid AS uuid)"
            ),
            {"uid": str(user_id)},
        )
        if new_curriculum_id != old_curriculum_id:
            await db.execute(
                text(
                    "SELECT switch_student_curriculum("
                    "CAST(:uid AS uuid), CAST(:cid AS uuid), "
                    "CAST(:actor AS uuid), :reason)"
                ),
                {
                    "uid": str(user_id),
                    "cid": str(new_curriculum_id),
                    "actor": str(current_user.user_id),
                    "reason": payload.reason,
                },
            )

    await db.commit()
    return await _account_payload(db, user, profile, study_program)


@router.post("/admin/accounts/{user_id}/anonymize")
async def anonymize_account(
    user_id: uuid.UUID,
    payload: AnonymizeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    denied = _require_admin(current_user)
    if denied is not None:
        return denied

    user = await _load_user(db, user_id)
    if user is None:
        return error_response(status.HTTP_404_NOT_FOUND, "not_found", "Akun tidak ditemukan.")
    profile = user.student_profile
    expected = user.email
    if user.role == "student" and profile and profile.student_number:
        expected = profile.student_number
    if not expected or payload.confirmation != expected:
        return _field_error(
            "confirmation",
            "Konfirmasi tidak cocok dengan identitas akun yang akan dianonimisasi.",
            "confirmation_mismatch",
        )

    if user.role == "admin" and user.is_active:
        active_admins = (
            await db.execute(
                select(func.count())
                .select_from(User)
                .where(User.role == "admin", User.is_active.is_(True))
            )
        ).scalar_one()
        if int(active_admins) <= 1:
            return error_response(
                status.HTTP_409_CONFLICT,
                "admin_guard",
                "Akun admin aktif terakhir tidak dapat dianonimisasi.",
            )

    # Snapshot identitas diambil sebelum penimpaan data identitas.
    await record_admin_action(
        db,
        actor=current_user,
        target=user,
        action="anonymize",
        reason=payload.reason,
    )

    user.email = f"anon+{uuid.uuid4()}@invalid.local"
    user.full_name = "Akun Anonim"
    user.phone_number = None
    user.bio = None
    user.career_interests = []
    user.is_active = False
    if profile is not None:
        profile.student_number = None
    await db.execute(
        text(
            "UPDATE users SET anonymized_at = now(), needs_revalidation = false "
            "WHERE user_id = CAST(:uid AS uuid)"
        ),
        {"uid": str(user_id)},
    )
    await bump_token_version(db, user.user_id)
    await db.commit()

    response = await _account_payload(db, user, profile, profile.study_program if profile else None)
    response["message"] = "Akun berhasil dianonimisasi."
    return response
