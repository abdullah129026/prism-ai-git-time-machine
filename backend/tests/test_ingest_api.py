"""API tests for repo ingestion: POST /repos and GET /repos/{job_id}."""

import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture()
def sample_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "sample"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / "app.py").write_text("print('v1')\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial commit")
    (repo / "app.py").write_text("print('v1')\nprint('v2')\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "second commit")
    return repo


def test_ingest_accepts_repo_and_reports_progress(sample_repo: Path):
    resp = client.post("/repos", json={"repo_url": str(sample_repo), "max_commits": 10})
    assert resp.status_code == 202
    body = resp.json()
    assert body["job_id"]
    assert body["status"] == "queued"

    status = client.get(f"/repos/{body['job_id']}").json()
    assert status["status"] == "ready"
    assert status["commits_parsed"] == 2
    assert status["repo_id"]
    assert status["error"] is None


def test_ingest_rejects_bad_url():
    resp = client.post("/repos", json={"repo_url": "ftp://example.com/x.git"})
    assert resp.status_code == 400
    assert "scheme" in resp.json()["detail"]


def test_ingest_rejects_empty_url():
    resp = client.post("/repos", json={"repo_url": "   "})
    assert resp.status_code == 400


def test_job_status_unknown_job_404():
    resp = client.get("/repos/does-not-exist")
    assert resp.status_code == 404


def test_ingest_caps_max_commits(sample_repo: Path, monkeypatch):
    from app.routers import repos as repos_router

    monkeypatch.setattr(repos_router.settings, "max_commits", 1)
    resp = client.post("/repos", json={"repo_url": str(sample_repo), "max_commits": 5000})
    assert resp.status_code == 202
    status = client.get(f"/repos/{resp.json()['job_id']}").json()
    assert status["status"] == "ready"
    assert status["commits_parsed"] == 1
