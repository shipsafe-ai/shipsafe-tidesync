import pytest
import hmac
import hashlib
import json
from unittest.mock import AsyncMock, patch


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from api.main import app
    return TestClient(app)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_run_returns_awaiting_approval_when_stale(client):
    mock_result = {
        "needs_recovery": True,
        "connection_id": "conn_abc123",
        "contradiction": {"is_stale": True, "lag_display": "4h 41m"},
        "briefing": {"summary": "Stale"},
    }
    with patch("api.main.orchestrator.run", new_callable=AsyncMock, return_value=mock_result):
        resp = client.post("/run")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "awaiting_approval"
    assert "approval_token" in data


def test_run_returns_complete_when_healthy(client):
    mock_result = {
        "needs_recovery": False,
        "contradiction": {"is_stale": False},
        "briefing": {"summary": "All healthy"},
    }
    with patch("api.main.orchestrator.run", new_callable=AsyncMock, return_value=mock_result):
        resp = client.post("/run")
    assert resp.status_code == 200
    assert resp.json()["status"] == "complete"


def test_approve_invalid_token(client):
    resp = client.post("/approve/nonexistent_token")
    assert resp.status_code == 404


def test_connections_endpoint(client):
    with patch("api.main.sync_sentinel.run", new_callable=AsyncMock, return_value=[{"connection_id": "conn_abc123"}]):
        resp = client.get("/connections")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_freshness_endpoint(client):
    with patch("api.main.sync_sentinel.run", new_callable=AsyncMock, return_value=[{"connection_id": "conn_abc123"}]), \
         patch("api.main.data_doctor.run", new_callable=AsyncMock, return_value=[{"table": "arrivals", "lag_seconds": 16740}]):
        resp = client.get("/freshness")
    assert resp.status_code == 200


def test_webhook_rejects_invalid_signature(client):
    with patch("api.main._get_webhook_secret", return_value="test_webhook_secret"):
        resp = client.post(
            "/webhooks/fivetran",
            json={"event": "sync_end", "connector_id": "conn_abc123"},
            headers={"X-Fivetran-Signature": "invalid"},
        )
    assert resp.status_code == 401


def test_webhook_processes_sync_end(client):
    payload = json.dumps({"event": "sync_end", "connector_id": "conn_abc123"}).encode()
    secret = b"test_webhook_secret"
    sig = hmac.new(secret, payload, hashlib.sha256).hexdigest()

    with patch("api.main._get_webhook_secret", return_value="test_webhook_secret"), \
         patch("api.main.data_doctor.run", new_callable=AsyncMock, return_value=[{"table": "arrivals", "lag_seconds": 16740}]):
        resp = client.post(
            "/webhooks/fivetran",
            content=payload,
            headers={"X-Fivetran-Signature": sig, "Content-Type": "application/json"},
        )
    assert resp.status_code == 200
