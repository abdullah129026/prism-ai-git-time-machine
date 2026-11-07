"""Tests for the pre-loaded demo repo: config binding, /repos/demo, seed logic."""

import json
import threading
import time

import pytest
from fastapi.testclient import TestClient

from app import main
from app.config import get_settings
from app.services.jobs import store

client = TestClient(main.app)


@pytest.fixture()
def fresh_settings(monkeypatch, tmp_path):
    """Isolate settings to a temp data dir with the given PRISM_ env vars."""
    monkeypatch.setenv("PRISM_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


def test_demo_repo_binds_prism_env_prefix(monkeypatch, tmp_path):
    monkeypatch.setenv("PRISM_DATA_DIR", str(tmp_path))
    monkeypatch.setenv(
        "PRISM_DEMO_REPO", "https://github.com/example/demo.git"
    )
    get_settings.cache_clear()
    try:
        assert get_settings().demo_repo == "https://github.com/example/demo.git"
    finally:
        get_settings.cache_clear()


def test_demo_disabled_by_default(fresh_settings):
    resp = client.get("/repos/demo")
    assert resp.status_code == 200
    assert resp.json() == {"enabled": False, "repo_id": None, "status": "disabled"}


def test_demo_seeding_when_no_marker(monkeypatch, tmp_path):
    monkeypatch.setenv("PRISM_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PRISM_DEMO_REPO", "https://github.com/example/demo.git")
    get_settings.cache_clear()
    try:
        resp = client.get("/repos/demo")
        assert resp.status_code == 200
        assert resp.json() == {"enabled": True, "repo_id": None, "status": "seeding"}
    finally:
        get_settings.cache_clear()


def test_demo_ready_when_marker_matches_store(monkeypatch, tmp_path):
    monkeypatch.setenv("PRISM_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PRISM_DEMO_REPO", "https://github.com/example/demo.git")
    get_settings.cache_clear()
    try:
        store.store_repo("demorepo1", "https://github.com/example/demo.git", [])
        (tmp_path / "demo.json").write_text(
            json.dumps({"repo_id": "demorepo1"})
        )
        resp = client.get("/repos/demo")
        assert resp.status_code == 200
        assert resp.json() == {
            "enabled": True,
            "repo_id": "demorepo1",
            "status": "ready",
        }
    finally:
        get_settings.cache_clear()


def test_demo_seeding_when_marker_points_nowhere(monkeypatch, tmp_path):
    """A marker without a matching in-memory repo must not report ready."""
    monkeypatch.setenv("PRISM_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PRISM_DEMO_REPO", "https://github.com/example/demo.git")
    get_settings.cache_clear()
    try:
        (tmp_path / "demo.json").write_text(json.dumps({"repo_id": "gone"}))
        resp = client.get("/repos/demo")
        assert resp.json()["status"] == "seeding"
        assert resp.json()["repo_id"] is None
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize("marker", ["[1, 2]", "{not valid json"])
def test_demo_seeding_when_marker_is_not_an_object(monkeypatch, tmp_path, marker):
    """A corrupt or non-object marker must degrade to seeding, never 500."""
    monkeypatch.setenv("PRISM_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PRISM_DEMO_REPO", "https://github.com/example/demo.git")
    get_settings.cache_clear()
    try:
        (tmp_path / "demo.json").write_text(marker)
        resp = client.get("/repos/demo")
        assert resp.status_code == 200
        assert resp.json() == {"enabled": True, "repo_id": None, "status": "seeding"}
    finally:
        get_settings.cache_clear()


def test_seed_demo_skips_invalid_url(monkeypatch, tmp_path):
    monkeypatch.setenv("PRISM_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        cfg = get_settings()
        cfg.demo_repo = "not a repo url"
        main._seed_demo(cfg)
        assert not (tmp_path / "demo.json").exists()
    finally:
        get_settings.cache_clear()


def _wait_for(path, timeout=5.0):
    """Poll until path exists with content; False when the seed thread
    never writes it (write_text creates the file before filling it)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists() and path.stat().st_size > 0:
            return True
        time.sleep(0.05)
    return False


def test_seed_demo_writes_marker_when_ingest_succeeds(
        monkeypatch, fresh_settings):
    """Happy path: a finished ingest leaves demo.json with repo id + url."""
    cfg = fresh_settings
    cfg.demo_repo = "https://github.com/example/demo.git"
    done = threading.Event()

    def fake_ingest(job_id):
        job = store.get(job_id)
        job.status = "ready"
        done.set()

    monkeypatch.setattr(main.git_parser, "validate_repo_url",
                        lambda url: url)
    monkeypatch.setattr(main, "run_ingest", fake_ingest)
    main._seed_demo(cfg)
    assert done.wait(5.0)
    marker = cfg.data_dir / "demo.json"
    assert _wait_for(marker)
    body = json.loads(marker.read_text())
    assert body["repo_url"] == "https://github.com/example/demo.git"
    assert body["repo_id"]


def test_seed_demo_writes_no_marker_when_ingest_fails(
        monkeypatch, fresh_settings):
    """A job that never reaches ready must not leave a stale marker."""
    cfg = fresh_settings
    cfg.demo_repo = "https://github.com/example/demo.git"
    done = threading.Event()

    def fake_ingest(job_id):
        job = store.get(job_id)
        job.status = "error"
        done.set()

    monkeypatch.setattr(main.git_parser, "validate_repo_url",
                        lambda url: url)
    monkeypatch.setattr(main, "run_ingest", fake_ingest)
    main._seed_demo(cfg)
    assert done.wait(5.0)
    time.sleep(0.2)  # let the seed thread notice the failed job
    assert not (cfg.data_dir / "demo.json").exists()


def test_lifespan_runs_with_demo_disabled(fresh_settings):
    """Startup with no demo repo configured must not fail the boot."""
    with TestClient(main.app) as client:
        assert client.get("/health").status_code == 200
