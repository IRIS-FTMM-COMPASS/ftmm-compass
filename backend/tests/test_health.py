def test_health_reports_database_and_chatbot(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["database_online"] is True
    assert "chatbot_service_online" in body
