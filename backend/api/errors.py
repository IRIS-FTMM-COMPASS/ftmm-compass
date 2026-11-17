"""Konstruksi envelope error kanonik untuk semua handler gateway."""

from collections.abc import Mapping, Sequence
from typing import Any

from fastapi.responses import JSONResponse

_NO_DETAIL = object()


def error_response(
    status_code: int,
    code: str,
    message: str,
    *,
    details: Sequence[Mapping[str, Any]] = (),
    detail: Any = _NO_DETAIL,
    headers: Mapping[str, str] | None = None,
    **extra: Any,
) -> JSONResponse:
    error = {"code": code, "message": message, **extra, "details": list(details)}
    content: dict[str, Any] = {"error": error}
    if detail is not _NO_DETAIL:
        content = {"detail": detail, **content}
    return JSONResponse(
        status_code=status_code,
        headers=dict(headers) if headers is not None else None,
        content=content,
    )
