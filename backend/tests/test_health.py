"""Smoke tests for the PRISM API skeleton: root, health, readiness."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_reports_service_metadata():
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "PRISM API"
    assert body["version"]
    assert body["health"] == "/health"


def test_health_is_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_ready_reports_dependency_checks():
    resp = client.get("/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["checks"]["git_available"] is True
    assert body["ready"] is True
