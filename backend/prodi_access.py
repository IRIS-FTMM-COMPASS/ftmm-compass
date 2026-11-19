"""Pemeriksaan scope server-side untuk endpoint PJ prodi."""

from fastapi import status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.errors import error_response
from catalog import normalize_prodi


def _deny(status_code: int, code: str, message: str) -> JSONResponse:
    return error_response(status_code, code, message, detail=message)


def _requested(value: str | None) -> str | None:
    if not value:
        return None
    normalized = normalize_prodi(value)
    if normalized and normalized.lower() == "all":
        return None
    return normalized


def require_pj_scope(
    current_user,
    db: AsyncSession,
    requested_prodi: str | None,
) -> str | None | JSONResponse:
    """Kembalikan prodi canonical (None untuk admin/all) atau envelope penolakan."""
    target = _requested(requested_prodi)

    if current_user.role == "admin":
        return target

    if current_user.role != "lecturer":
        return _deny(
            status.HTTP_403_FORBIDDEN,
            "forbidden",
            "Akses rekap peminatan hanya tersedia untuk admin dan PJ prodi.",
        )

    profile = current_user.lecturer_profile
    if profile is None or profile.study_program is None:
        return _deny(
            status.HTTP_403_FORBIDDEN,
            "prodi_belum_ditetapkan",
            "Prodi PJ belum ditetapkan.",
        )
    if not profile.is_program_coordinator:
        return _deny(
            status.HTTP_403_FORBIDDEN,
            "not_program_coordinator",
            "Hanya koordinator program studi yang dapat melihat rekap peminatan.",
        )

    own_prodi = normalize_prodi(profile.study_program.program_name) or profile.study_program.program_code
    if target and normalize_prodi(target) != normalize_prodi(own_prodi):
        return _deny(
            status.HTTP_403_FORBIDDEN,
            "akses_prodi_ditolak",
            "PJ hanya dapat mengakses rekap prodinya sendiri.",
        )
    return own_prodi
