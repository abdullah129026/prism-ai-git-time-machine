"""Tests for the pre-loaded demo repo: config binding, /repos/demo, seed logic."""

import json

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
