from datetime import datetime, timedelta, timezone

import jwt
from starlette.requests import Request

import app as app_module
import settings
from rate_limit import rate_limit_key
from slowapi.middleware import SlowAPIMiddleware


def _request(authorization: str | None = None) -> Request:
    headers = []
    if authorization:
        headers.append((b"authorization", authorization.encode()))
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": headers,
            "client": ("203.0.113.7", 1234),
            "server": ("testserver", 80),
            "scheme": "http",
            "query_string": b"",
        }
    )


def test_rate_limit_key_uses_authenticated_user():
    token = jwt.encode(
        {
            "sub": "user-123",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    assert rate_limit_key(_request(f"Bearer {token}")) == "user:user-123"


def test_rate_limit_key_falls_back_to_ip_for_invalid_token():
    assert rate_limit_key(_request("Bearer not-a-token")) == "ip:203.0.113.7"
    assert rate_limit_key(_request()) == "ip:203.0.113.7"


def test_cors_defaults_are_explicit_and_credential_safe():
    assert settings.parse_cors_origins(None) == (
        list(settings.DEFAULT_CORS_ORIGINS),
        True,
    )
    assert settings.parse_cors_origins("*") == (["*"], False)
    assert settings.parse_cors_origins("https://a.test, https://b.test") == (
        ["https://a.test", "https://b.test"],
        True,
    )


def test_slowapi_middleware_is_mounted():
    assert any(
        middleware.cls is SlowAPIMiddleware
        for middleware in app_module.app.user_middleware
    )
