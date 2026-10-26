"""API tests for the conflict-prediction endpoint.

The service-level tests in test_conflict.py cover the AST analysis; these
cover the HTTP layer, which previously had no tests at all: success shape,
unknown repo, unknown ref, and empty-ref validation.
"""

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
    repo = tmp_path / "branched"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    base = "def foo():\n    return 1\n\ndef bar():\n    return 2\n"
    (repo / "app.py").write_text(base)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    for branch, body in [
        ("side-a", base.replace("return 1", "return 10")),
        ("side-b", base.replace("return 1", "return 99")),
    ]:
        _git(repo, "checkout", "-b", branch, "main")
        (repo / "app.py").write_text(body)
        _git(repo, "commit", "-am", f"{branch} edits")
    _git(repo, "checkout", "main")

    resp = client.post("/repos", json={"repo_url": str(repo)})
    assert resp.status_code == 202
    status = client.get(f"/repos/{resp.json()['job_id']}").json()
    assert status["status"] == "ready"
    return status["repo_id"]


def test_predict_conflict_same_function_scores_high(repo_id: str):
    resp = client.post(f"/repos/{repo_id}/predict-conflict",
                       json={"base": "side-a", "head": "side-b"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["base"] == "side-a"
    assert body["head"] == "side-b"
    assert body["probability"] > 0.5
    assert body["overlapping_symbols"] == ["app.py:foo"]
    assert "foo" in body["explanation"]


def test_predict_conflict_unknown_repo_404():
    resp = client.post("/repos/no-such-repo/predict-conflict",
                       json={"base": "main", "head": "side-a"})
    assert resp.status_code == 404


def test_predict_conflict_unknown_ref_404(repo_id: str):
    resp = client.post(f"/repos/{repo_id}/predict-conflict",
                       json={"base": "side-a", "head": "no-such-branch"})
    assert resp.status_code == 404


def test_predict_conflict_empty_ref_422(repo_id: str):
    resp = client.post(f"/repos/{repo_id}/predict-conflict",
                       json={"base": "", "head": "side-a"})
    assert resp.status_code == 422
