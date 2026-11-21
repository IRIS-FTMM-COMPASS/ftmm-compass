from unittest.mock import AsyncMock, patch

import httpx
import pytest

import settings


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


def test_circular_forwarding_is_blocked(client, chatbot_url):
    settings.CHATBOT_SERVICE_URL = "http://127.0.0.1:8001"
    response = client.post(
        "/api/chat", json={"message": "halo", "history": [], "student_profile": {}}
    )
    assert response.status_code == 500
    body = response.json()
    assert "Circular forwarding detected" in body["error"]["message"]


def test_offline_chatbot_returns_503(client, chatbot_url):
    settings.CHATBOT_SERVICE_URL = "http://127.0.0.1:59999"
    response = client.post(
        "/api/chat", json={"message": "halo", "history": [], "student_profile": {}}
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "upstream_service_unavailable"
    assert "Retry-After" in response.headers


def test_chat_forward_passes_reply_and_profile(client, chatbot_url):
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
