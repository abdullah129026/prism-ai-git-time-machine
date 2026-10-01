"""API tests for the timeline endpoint: GET /repos/{repo_id}/timeline."""

import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture()
def repo_id(tmp_path: Path) -> str:
    repo = tmp_path / "sample"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / "app.py").write_text("print('v1')\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial commit")
    (repo / "app.py").write_text("print('v1')\nprint('v2')\n")
    (repo / "hot.py").write_text("x = 1\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "second commit")

    resp = client.post("/repos", json={"repo_url": str(repo)})
    assert resp.status_code == 202
    status = client.get(f"/repos/{resp.json()['job_id']}").json()
    assert status["status"] == "ready"
    return status["repo_id"]


def test_timeline_returns_nodes_edges_and_churn(repo_id: str):
    tl = client.get(f"/repos/{repo_id}/timeline").json()
    assert tl["repo_id"] == repo_id
    assert tl["commit_count"] == 2
    assert len(tl["nodes"]) == 2

    newest = tl["nodes"][0]
    assert newest["message"] == "second commit"
    assert newest["additions"] == 2  # one line in app.py + hot.py
    assert newest["files_changed"] == 2
    assert len(newest["sha"]) == 40

    # Every non-root commit links to its parent.
    assert len(tl["edges"]) == 1
    assert tl["edges"][0]["target"] == newest["sha"]
    assert tl["edges"][0]["source"] == tl["nodes"][1]["sha"]

    # Churn aggregates per file, hottest first.
    churn = {f["path"]: f for f in tl["file_churn"]}
    assert churn["app.py"]["commits"] == 2
    assert churn["hot.py"]["commits"] == 1
    assert tl["file_churn"][0]["path"] == "app.py"


def test_timeline_respects_limit(repo_id: str):
    tl = client.get(f"/repos/{repo_id}/timeline", params={"limit": 1}).json()
    assert len(tl["nodes"]) == 1
    assert tl["commit_count"] == 2  # total is still reported


def test_timeline_unknown_repo_404():
    resp = client.get("/repos/no-such-repo/timeline")
    assert resp.status_code == 404
