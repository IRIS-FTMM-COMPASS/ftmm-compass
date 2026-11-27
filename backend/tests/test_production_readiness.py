import shlex
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, patch

import app as app_module
import settings
from fastapi import Request
from fastapi.testclient import TestClient
from rate_limit import limiter

REPO_ROOT = Path(__file__).resolve().parents[2]


@contextmanager
def _temporary_route(path: str, endpoint, methods=("GET",)):
    original_routes = list(app_module.app.router.routes)
    app_module.app.add_api_route(
        path, endpoint, methods=list(methods), include_in_schema=False
    )
    try:
        yield
    finally:
        app_module.app.router.routes[:] = original_routes


def _service_config(compose: str, name: str) -> dict[str, list[str] | str]:
    lines = compose.splitlines()
    start = lines.index(f"  {name}:")
    config: dict[str, list[str] | str] = {}
    current: str | None = None
    for line in lines[start + 1 :]:
        if line and not line.startswith("    "):
            break
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not line.startswith("      "):
            key, _, value = stripped.partition(":")
            current = key.strip()
            config[current] = value.strip() if value.strip() else []
        elif current is not None and stripped.startswith("- "):
            values = config[current]
            assert isinstance(values, list)
            values.append(shlex.split(stripped[2:].strip())[0])
    return config


def _dockerfile_steps(text: str) -> list[tuple[str, list[str]]]:
    steps: list[tuple[str, list[str]]] = []
    logical_lines: list[str] = []
    pending = ""
    for raw in text.splitlines():
        line = raw.strip()
        pending = line if not pending else f"{pending} {line}"
        if pending.endswith("\\"):
            pending = pending[:-1].rstrip()
            continue
        logical_lines.append(pending)
        pending = ""
    if pending:
        logical_lines.append(pending)
    for line in logical_lines:
        code = line.split("#", 1)[0].strip()
        if not code:
            continue
        instruction, _, arguments = code.partition(" ")
        steps.append((instruction.upper(), shlex.split(arguments)))
    return steps

def test_unhandled_exception_returns_standard_envelope_without_details(client):
    path = "/__probe/unhandled"

    def explode():
        raise RuntimeError("secret internal detail: password=hunter2")

    with TestClient(app_module.app, raise_server_exceptions=False) as probe_client:
        with _temporary_route(path, explode):
            response = probe_client.get(path)

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_server_error"
    assert body["error"]["message"]
    assert body["error"]["details"] == []
    assert "hunter2" not in response.text
    assert "Traceback" not in response.text
    assert Exception in app_module.app.exception_handlers
    assert not any(
        getattr(middleware.kwargs.get("dispatch"), "__name__", "")
        == "internal_error_middleware"
        for middleware in app_module.app.user_middleware
    )


def test_rate_limit_response_carries_retry_hint(client):
    path = "/__probe/rate_limited"

    @limiter.limit("1/minute")
    def probe(request: Request):
        return {"ok": True}

    with _temporary_route(path, probe):
        first = client.get(path)
        second = client.get(path)

    assert first.status_code == 200
    assert second.status_code == 429
    assert int(second.headers["Retry-After"]) > 0
    body = second.json()
    assert body["error"]["code"] == "rate_limit_exceeded"
    assert body["error"]["retry_after"] == int(second.headers["Retry-After"])


def test_stream_generator_stops_on_client_disconnect(client, student_headers):
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
            patch("features.chat.router.log_chat_metadata", new_callable=AsyncMock) as log_metadata,
        ):
            response = client.post(
                "/api/v1/chat/stream",
                headers=student_headers,
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
        config = _service_config(compose, service)
        assert config["cap_drop"] == ["ALL"]
        assert config["read_only"] == "true"
        assert config["tmpfs"]
        assert "no-new-privileges:true" in config["security_opt"]

    for dockerfile in ("Dockerfile.backend", "Dockerfile.frontend"):
        steps = _dockerfile_steps((REPO_ROOT / dockerfile).read_text(encoding="utf-8"))
        users = [args for instruction, args in steps if instruction == "USER"]
        assert users == [["appuser"]]
        numeric_ids = {
            args[index + 1]
            for _, args in steps
            for index, flag in enumerate(args[:-1])
            if flag in ("-u", "-g") and args[index + 1] == "1001"
        }
        assert numeric_ids == {"1001"}


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
