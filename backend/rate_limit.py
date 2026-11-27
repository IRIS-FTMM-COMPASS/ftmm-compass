"""Rate limiter bersama untuk seluruh router."""

import jwt
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

import settings

default_limits = (
    [settings.DEFAULT_RATE_LIMIT]
    if settings.DEFAULT_RATE_LIMIT
    and settings.DEFAULT_RATE_LIMIT.lower() not in ("none", "false", "0")
    else []
)


def rate_limit_key(request: Request) -> str:
    """Kunci per pengguna agar proxy loopback tidak menyatukan semua klien."""
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )
            subject = payload.get("sub")
            if subject:
                return f"user:{subject}"
        except Exception:
            pass
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=rate_limit_key, default_limits=default_limits)
