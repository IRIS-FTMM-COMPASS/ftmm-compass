from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy import delete, select

import settings
from database import AsyncSessionLocal
from models import ChatLog, User


@pytest.fixture
def chatbot_url():
    original = settings.CHATBOT_SERVICE_URL
    yield
    settings.CHATBOT_SERVICE_URL = original


def _sse_response():
    async def fake_lines(*args, **kwargs):
        yield 'data: {"token": "Halo"}'
        yield 'data: {"done": true, "reply": "Halo"}'

    class FakeResponse:
        status_code = 200

        def __init__(self):
            self.aiter_lines = fake_lines

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    return FakeResponse()


def test_chat_requires_authentication(client):
    response = client.post(
        "/api/v1/chat",
        json={"message": "halo", "history": [], "student_profile": {}},
    )
    assert response.status_code == 401


def test_circular_forwarding_is_blocked(client, chatbot_url, student_headers):
    settings.CHATBOT_SERVICE_URL = "http://127.0.0.1:8001"
    response = client.post(
        "/api/chat",
        headers=student_headers,
        json={"message": "halo", "history": [], "student_profile": {}},
    )
    assert response.status_code == 500
    body = response.json()
    assert "Circular forwarding detected" in body["error"]["message"]


def test_offline_chatbot_returns_503(client, chatbot_url, student_headers):
    settings.CHATBOT_SERVICE_URL = "http://127.0.0.1:59999"
    response = client.post(
        "/api/chat",
        headers=student_headers,
        json={"message": "halo", "history": [], "student_profile": {}},
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "upstream_service_unavailable"
    assert "Retry-After" in response.headers


def test_chat_ignores_body_user_id(client, chatbot_url, student_headers):
    settings.CHATBOT_SERVICE_URL = "http://chatbot.test"
    claimed_id = "00000000-0000-0000-0000-000000000001"
    mocked = httpx.Response(
        status_code=200,
        json={
            "reply": "Halo.",
            "updated_profile": {"program_studi": "Teknologi Sains Data"},
            "action_type": "GENERAL",
        },
        request=httpx.Request("POST", "http://chatbot.test/api/chat"),
    )
    with (
        patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post,
        patch("features.chat.router.log_chat_metadata", new_callable=AsyncMock) as log_metadata,
    ):
        mock_post.return_value = mocked
        response = client.post(
            "/api/v1/chat",
            headers=student_headers,
            json={
                "message": "halo",
                "history": [],
                "student_profile": {},
                "user_id": claimed_id,
            },
        )
    assert response.status_code == 200
    assert str(log_metadata.call_args.kwargs["user_id"]) != claimed_id


def test_chat_forward_passes_reply_and_profile(client, chatbot_url, student_headers):
    settings.CHATBOT_SERVICE_URL = "http://chatbot.test"
    mocked = httpx.Response(
        status_code=200,
        json={
            "reply": "Halo, saya bantu.",
            "updated_profile": {
                "program_studi": "Teknologi Sains Data",
                "semester_saat_ini": 4,
            },
            "action_type": "GENERAL",
            "routing_mode": "HYBRID",
            "latency_ms": 12.5,
        },
        request=httpx.Request("POST", "http://chatbot.test/api/chat"),
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mocked
        response = client.post(
            "/api/chat",
            headers=student_headers,
            json={"message": "halo", "history": [], "student_profile": {}},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "Halo, saya bantu."
    assert body["updated_profile"]["semester_saat_ini"] == 4
    assert body["routing_mode"] == "HYBRID"


def test_stream_requires_authentication(client, chatbot_url):
    settings.CHATBOT_SERVICE_URL = "http://chatbot.test"
    response = client.post(
        "/api/v1/chat/stream",
        json={"message": "halo", "history": [], "student_profile": {}},
    )
    assert response.status_code == 401


def test_stream_identity_comes_from_token(client, chatbot_url, student_headers):
    settings.CHATBOT_SERVICE_URL = "http://chatbot.test"

    claimed_id = "00000000-0000-0000-0000-000000000001"
    with (
        patch("httpx.AsyncClient.stream", return_value=_sse_response()),
        patch("features.chat.router.log_chat_metadata", new_callable=AsyncMock) as log_metadata,
    ):
        response = client.post(
            "/api/v1/chat/stream",
            headers=student_headers,
            json={
                "message": "halo",
                "history": [],
                "student_profile": {},
                "user_id": claimed_id,
            },
        )
    assert response.status_code == 200
    assert str(log_metadata.call_args.kwargs["user_id"]) != claimed_id


def test_stream_connection_limit_returns_503(client, chatbot_url, student_headers):
    settings.CHATBOT_SERVICE_URL = "http://chatbot.test"
    from stream_control import stream_tracker

    original = stream_tracker.max_connections
    stream_tracker.max_connections = 0
    try:
        response = client.post(
            "/api/v1/chat/stream",
            headers=student_headers,
            json={"message": "halo", "history": [], "student_profile": {}},
        )
    finally:
        stream_tracker.max_connections = original
    assert response.status_code == 503


def test_health_reports_stream_metrics(client):
    from stream_control import stream_tracker

    stream_tracker.first_token_latency_ms = 12.5
    stream_tracker.last_stream_duration_ms = 480.0
    try:
        body = client.get("/api/v1/health").json()
    finally:
        stream_tracker.first_token_latency_ms = None
        stream_tracker.last_stream_duration_ms = None
    assert body["active_streams"] == 0
    assert body["first_token_latency_ms"] == 12.5
    assert body["last_stream_duration_ms"] == 480.0


def test_stream_endpoint_emits_sse(client, chatbot_url, student_headers):
    settings.CHATBOT_SERVICE_URL = "http://chatbot.test"
    with patch("httpx.AsyncClient.stream", return_value=_sse_response()):
        response = client.post(
            "/api/v1/chat/stream",
            headers=student_headers,
            json={"message": "halo", "history": [], "student_profile": {}},
        )
    assert response.status_code == 200
    assert "data:" in response.text


def _insert_chat_log(client, session_id: str, email: str) -> None:
    async def run() -> None:
        async with AsyncSessionLocal() as db:
            user = (
                await db.execute(select(User).where(User.email == email))
            ).scalar_one()
            db.add(
                ChatLog(
                    session_id=session_id,
                    user_id=user.user_id,
                    user_message="halo",
                )
            )
            await db.commit()

    client.portal.call(run)


def _delete_chat_logs(client, session_id: str) -> None:
    async def run() -> None:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(ChatLog).where(ChatLog.session_id == session_id))
            await db.commit()

    client.portal.call(run)


def test_delete_chat_session_requires_authentication(client):
    response = client.delete("/api/v1/chat/sessions/phase1-no-auth")
    assert response.status_code == 401


def test_delete_chat_session_hides_other_users_session(client, student_headers):
    session_id = "phase1-other-user"
    _insert_chat_log(client, session_id, "admin@ftmm.unair.ac.id")
    try:
        response = client.delete(
            f"/api/v1/chat/sessions/{session_id}",
            headers=student_headers,
        )
    finally:
        _delete_chat_logs(client, session_id)
    assert response.status_code == 404


def test_delete_chat_session_allows_owner(client, student_headers):
    session_id = "phase1-own-user-success"
    _insert_chat_log(client, session_id, "mahasiswa.testing@ftmm.unair.ac.id")
    deleted = httpx.Response(
        204,
        request=httpx.Request(
            "DELETE", "http://chatbot.test/api/v1/chat/sessions/x"
        ),
    )
    try:
        with patch("httpx.AsyncClient.delete", new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = deleted
            response = client.delete(
                f"/api/v1/chat/sessions/{session_id}",
                headers=student_headers,
            )
    finally:
        _delete_chat_logs(client, session_id)
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_delete_chat_session_propagates_upstream_failure(client, student_headers):
    session_id = "phase1-own-user-failure"
    _insert_chat_log(client, session_id, "mahasiswa.testing@ftmm.unair.ac.id")
    failed = httpx.Response(
        500,
        request=httpx.Request(
            "DELETE", "http://chatbot.test/api/v1/chat/sessions/x"
        ),
    )
    try:
        with patch("httpx.AsyncClient.delete", new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = failed
            response = client.delete(
                f"/api/v1/chat/sessions/{session_id}",
                headers=student_headers,
            )
    finally:
        _delete_chat_logs(client, session_id)
    assert response.status_code == 502


class _FailedStreamResponse:
    status_code = 503

    async def aread(self) -> bytes:
        return b'{"detail":"chatbot offline"}'

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def test_stream_upstream_error_returns_real_status(client, chatbot_url, student_headers):
    settings.CHATBOT_SERVICE_URL = "http://chatbot.test"
    with patch("httpx.AsyncClient.stream", return_value=_FailedStreamResponse()):
        response = client.post(
            "/api/v1/chat/stream",
            headers=student_headers,
            json={"message": "halo", "history": [], "student_profile": {}},
        )
    assert response.status_code == 502
    assert "chatbot offline" in response.text
