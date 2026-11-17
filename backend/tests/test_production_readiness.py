import settings
import app as app_module
from fastapi import Request
from rate_limit import limiter
from unittest.mock import AsyncMock, patch

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _remove_probe(path: str) -> None:
    app_module.app.router.routes[:] = [
        route
        for route in app_module.app.router.routes
        if getattr(route, "path", None) != path
    ]


def _service_block(compose: str, name: str) -> str:
    lines = compose.splitlines()
    start = lines.index(f"  {name}:")
    end = next(
        (
            index
            for index in range(start + 1, len(lines))
            if lines[index].startswith("  ") and not lines[index].startswith("    ")
        ),
        len(lines),
    )
    return "\n".join(lines[start:end])


def test_unhandled_exception_returns_standard_envelope_without_details(client):
    path = "/__probe/unhandled"

    def explode():
        raise RuntimeError("secret internal detail: password=hunter2")

    app_module.app.add_api_route(path, explode, methods=["GET"], include_in_schema=False)
    try:
        response = client.get(path)
    finally:
        _remove_probe(path)

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_server_error"
    assert body["error"]["message"]
    assert body["error"]["details"] == []
    assert "hunter2" not in response.text
    assert "Traceback" not in response.text


def test_rate_limit_response_carries_retry_hint(client):
    path = "/__probe/rate_limited"

    @limiter.limit("1/minute")
    def probe(request: Request):
        return {"ok": True}

    app_module.app.add_api_route(path, probe, methods=["GET"], include_in_schema=False)
    try:
        first = client.get(path)
        second = client.get(path)
    finally:
        _remove_probe(path)

    assert first.status_code == 200
    assert second.status_code == 429
    assert int(second.headers["Retry-After"]) > 0
    body = second.json()
    assert body["error"]["code"] == "rate_limit_exceeded"
    assert body["error"]["retry_after"] == int(second.headers["Retry-After"])


def test_stream_generator_stops_on_client_disconnect(client):
    original = settings.CHATBOT_SERVICE_URL
    settings.CHATBOT_SERVICE_URL = "http://chatbot.test"
    consumed: list[int] = []
    checks = 0

    async def fake_lines(*args, **kwargs):
        for index in range(3):
            consumed.append(index)
            yield f'data: {{"token": "token{index}"}}'

    class FakeStream:
        status_code = 200

        def __init__(self):
            self.aiter_lines = fake_lines

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    async def disconnected(*args):
        nonlocal checks
        checks += 1
        return checks > 1

    try:
        with (
            patch("httpx.AsyncClient.stream", return_value=FakeStream()),
            patch("starlette.requests.Request.is_disconnected", new=disconnected),
            patch("api.chat.log_chat_metadata", new_callable=AsyncMock) as log_metadata,
        ):
            response = client.post(
                "/api/v1/chat/stream",
                json={"message": "halo", "history": [], "student_profile": {}},
            )
    finally:
        settings.CHATBOT_SERVICE_URL = original

    assert response.status_code == 200
    assert "token" not in response.text
    assert consumed == []
    assert checks >= 1
    log_metadata.assert_not_awaited()


def test_application_containers_are_hardened():
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    for service in ("gateway", "frontend"):
        block = _service_block(compose, service)
        assert "cap_drop:" in block
        assert "- ALL" in block
        assert "read_only: true" in block
        assert "tmpfs:" in block
        assert "no-new-privileges:true" in block

    for dockerfile in ("Dockerfile.backend", "Dockerfile.frontend"):
        text = (REPO_ROOT / dockerfile).read_text(encoding="utf-8")
        assert "USER appuser" in text
        assert "-u 1001" in text or "-g 1001" in text
        assert "USER root" not in text


def test_root_and_version_info_match_across_route_tiers(client):
    paths = (
        "/",
        "/api",
        "/api/v1",
        "/api/",
        "/api/v1/",
        "/api/version",
        "/api/v1/version",
    )
    responses = [client.get(path) for path in paths]

    assert [response.status_code for response in responses] == [200] * len(paths)
    payloads = [response.json() for response in responses]
    assert all(payload == payloads[0] for payload in payloads)
    assert payloads[0]["service"] == app_module.app.title
    assert payloads[0]["version"]
    assert payloads[0]["api_version"] == "v1"


def test_course_search_matches_across_route_tiers(client):
    original = settings.CHATBOT_SERVICE_URL
    settings.CHATBOT_SERVICE_URL = "http://127.0.0.1:59999"
    try:
        canonical = client.get("/api/v1/courses/search", params={"q": "AGI101"})
        legacy = client.get("/api/courses/search", params={"q": "AGI101"})
    finally:
        settings.CHATBOT_SERVICE_URL = original

    assert canonical.status_code == 200
    assert legacy.status_code == 200
    assert canonical.json() == legacy.json()
