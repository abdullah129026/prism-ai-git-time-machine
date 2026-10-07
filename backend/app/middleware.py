"""Small ASGI middlewares: rate limiting, security headers, host guard.

Dependency-free on purpose — a couple of buckets and headers don't justify
another package. All state is in-memory, which is fine for a single-process
service; revisit if PRISM ever runs more than one worker.
"""

from __future__ import annotations

import threading
import time

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_RATE_WINDOW_SECONDS = 3600.0


def _client_ip(scope: Scope) -> str:
    headers = dict(scope.get("headers", []))
    xff = headers.get(b"x-forwarded-for", b"").decode("latin1")
    if xff:
        return xff.split(",")[0].strip()
    client = scope.get("client")
    return client[0] if client else "unknown"


def _request_bucket(scope: Scope) -> str | None:
    """Which rate-limit bucket a request belongs to, if any."""
    if scope["type"] != "http":
        return None
    method = scope["method"]
    path = scope["path"].rstrip("/") or "/"
    if method == "POST" and path == "/repos":
        return "ingest"  # clone = CPU + disk
    if "/intent/" in path or path.endswith("/intent/analyze"):
        return "intent"  # uncached call = paid Groq request
    return None


class RateLimitMiddleware:
    """Fixed-window per-IP rate limiter for the expensive endpoints."""

    def __init__(self, app: ASGIApp, *, ingest_per_hour: int = 20,
                 intent_per_hour: int = 120) -> None:
        self.app = app
        self._limits = {"ingest": ingest_per_hour, "intent": intent_per_hour}
        self._lock = threading.Lock()
        # (ip, bucket) -> timestamps of requests inside the current window
        self._hits: dict[tuple[str, str], list[float]] = {}

    def _check(self, key: tuple[str, str], bucket: str) -> int:
        """Record a hit; return retry-after seconds, or 0 when allowed."""
        now = time.monotonic()
        with self._lock:
            # ponytail: O(n) prune per request; n stays tiny on this service
            hits = [t for t in self._hits.get(key, [])
                    if now - t < _RATE_WINDOW_SECONDS]
            if len(hits) >= self._limits[bucket]:
                retry_after = int(_RATE_WINDOW_SECONDS - (now - hits[0])) + 1
            else:
                hits.append(now)
                self._hits[key] = hits
                retry_after = 0
            if len(self._hits) > 5000:  # drop fully-expired buckets
                self._hits = {k: v for k, v in self._hits.items()
                              if any(now - t < _RATE_WINDOW_SECONDS for t in v)}
            return retry_after

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        bucket = _request_bucket(scope)
        if bucket is None:
            await self.app(scope, receive, send)
            return
        retry_after = self._check((_client_ip(scope), bucket), bucket)
        if retry_after:
            response = JSONResponse(
                {"detail": "rate limit exceeded, try again later"},
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


class SecurityHeadersMiddleware:
    """Baseline security headers on every response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                req_headers = dict(scope.get("headers", []))
                req_host = (req_headers.get(b"host", b"").decode("latin1")
                            .split(":")[0])
                headers = dict(message.setdefault("headers", []))
                headers.setdefault(b"x-content-type-options", b"nosniff")
                headers.setdefault(b"x-frame-options", b"DENY")
                headers.setdefault(b"referrer-policy", b"no-referrer")
                if req_host not in ("localhost", "127.0.0.1", "testserver"):
                    headers.setdefault(
                        b"strict-transport-security",
                        b"max-age=31536000; includeSubDomains",
                    )
                message["headers"] = list(headers.items())
            await send(message)

        await self.app(scope, receive, send_with_headers)


class HostGuardMiddleware:
    """Reject unexpected Host headers — except on the health probes.

    Probes stay exempt so Render's health checks can never wedge the
    service, whatever Host header the platform sends.
    """

    _EXEMPT_PATHS = ("/health", "/ready")

    def __init__(self, app: ASGIApp, *, allowed_hosts: list[str]) -> None:
        self.app = app
        self._allowed = {h.lower() for h in allowed_hosts}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"] not in self._EXEMPT_PATHS:
            headers = dict(scope.get("headers", []))
            host = headers.get(b"host", b"").decode("latin1").split(":")[0].lower()
            if host not in self._allowed:
                response = JSONResponse(
                    {"detail": "invalid host header"}, status_code=400)
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)
