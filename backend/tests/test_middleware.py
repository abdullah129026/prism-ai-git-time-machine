"""Tests for the security middlewares (rate limit, headers, host guard)."""

from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from app.middleware import (
    HostGuardMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)


async def _ok_app(scope, receive, send):
    assert scope["type"] == "http"
    await JSONResponse({"ok": True})(scope, receive, send)


def test_rate_limit_blocks_third_ingest_per_hour():
    app = RateLimitMiddleware(_ok_app, ingest_per_hour=2, intent_per_hour=100)
    client = TestClient(app)
    assert client.post("/repos").status_code == 200
    assert client.post("/repos").status_code == 200
    resp = client.post("/repos")
    assert resp.status_code == 429
    assert "retry-after" in resp.headers


def test_rate_limit_ignores_unrelated_paths():
    app = RateLimitMiddleware(_ok_app, ingest_per_hour=1, intent_per_hour=100)
    client = TestClient(app)
    for _ in range(3):
        assert client.get("/health").status_code == 200


def test_rate_limit_buckets_are_per_ip():
    app = RateLimitMiddleware(_ok_app, ingest_per_hour=1, intent_per_hour=100)
    client = TestClient(app)
    assert client.post("/repos").status_code == 200
    assert client.post("/repos").status_code == 429
    other = {"X-Forwarded-For": "203.0.113.9"}
    assert client.post("/repos", headers=other).status_code == 200


def test_rate_limit_covers_intent_endpoints():
    app = RateLimitMiddleware(_ok_app, ingest_per_hour=100, intent_per_hour=1)
    client = TestClient(app)
    assert client.get("/repos/abc/intent/def").status_code == 200
    assert client.get("/repos/abc/intent/def").status_code == 429
    assert client.post("/repos/abc/intent/analyze").status_code == 429


def test_security_headers_present():
    client = TestClient(SecurityHeadersMiddleware(_ok_app))
    resp = client.get("/repos/abc")
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"
    assert resp.headers["referrer-policy"] == "no-referrer"


def test_host_guard_rejects_unknown_host():
    app = HostGuardMiddleware(_ok_app, allowed_hosts=["example.com"])
    client = TestClient(app)
    assert client.get("/repos", headers={"host": "evil.com"}).status_code == 400
    assert client.get("/repos", headers={"host": "example.com"}).status_code == 200


def test_host_guard_exempts_health_probes():
    app = HostGuardMiddleware(_ok_app, allowed_hosts=["example.com"])
    client = TestClient(app)
    assert client.get("/health", headers={"host": "evil.com"}).status_code == 200
    assert client.get("/ready", headers={"host": "evil.com"}).status_code == 200
