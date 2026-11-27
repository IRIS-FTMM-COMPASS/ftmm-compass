"""Penamaan kode section kelas."""

from collections.abc import Iterable

SHARED_SCOPES = frozenset({"fakultas", "universitas"})
PROGRAM_PREFIXES = {"TSD": "SD", "TRKB": "RK"}


def section_prefix(
    program_codes: Iterable[str | None], course_scopes: Iterable[str]
) -> str:
    codes = {code for code in program_codes if code}
    scopes = set(course_scopes)
    if not codes or len(codes) > 1 or scopes & SHARED_SCOPES:
        return "UM"
    code = next(iter(codes))
    return PROGRAM_PREFIXES.get(code, code)


def format_section_code(prefix: str, ordinal: int) -> str:
    return f"{prefix}-A{ordinal}"
