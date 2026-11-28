from importlib import import_module

health_module = import_module("features.health.router")


class _FailingSession:
    async def __aenter__(self):
        raise RuntimeError("database down")

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_health_reports_database_and_chatbot(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["database_online"] is True
    assert "chatbot_service_online" in body


def test_health_is_degraded_when_database_is_down(client, monkeypatch):
    monkeypatch.setattr(health_module, "AsyncSessionLocal", _FailingSession)
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["database_online"] is False
    assert body["status"] == "degraded"
