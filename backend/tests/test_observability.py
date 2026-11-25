"""Sentry wiring: the temporary test endpoint is gone, and the SDK init
branch runs cleanly when a DSN is configured."""

import os
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

BACKEND_DIR = Path(__file__).resolve().parent.parent


def test_sentry_test_endpoint_is_gone():
    """The temporary /__sentry_test route was removed: Sentry wiring is
    parked (no DSN is set), so the unauthenticated route that deliberately
    raised a 500 must not stay live in production. It can be re-added
    temporarily if verification ever resumes."""
    resp = client.get("/__sentry_test")
    assert resp.status_code == 404


def test_sentry_init_runs_with_dsn_set():
    """With SENTRY_DSN set, importing the app initialises the Sentry
    client (init sends nothing over the network). Runs in a subprocess
    so the global Sentry client does not leak into the rest of the
    suite."""
    script = (
        "import sentry_sdk\n"
        "from app.main import app\n"
        "client = sentry_sdk.get_client()\n"
        "assert client.dsn is not None, 'Sentry client has no DSN'\n"
        "print('sentry dsn:', client.dsn)\n"
    )
    env = dict(os.environ)
    env["SENTRY_DSN"] = "https://publickey@o0.ingest.sentry.io/0"
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
        cwd=BACKEND_DIR,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert "sentry dsn: https://publickey@o0.ingest.sentry.io/0" in result.stdout
