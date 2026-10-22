"""API tests for GET /repos/{repo_id}/intent/{sha} lookup semantics."""

from fastapi.testclient import TestClient

from app.main import app
from app.services.git_parser import ParsedCommit
from app.services.jobs import store

client = TestClient(app)


def _seed(repo_id: str, shas: list[str]) -> None:
    commits = [
        ParsedCommit(
            sha=sha, message=f"commit {i}", author="t",
            author_email="t@example.com", committed_at="2026-10-22T00:00:00",
        )
        for i, sha in enumerate(shas)
    ]
    store.store_repo(repo_id, "https://example.com/r.git", commits)


def test_ambiguous_short_sha_returns_404():
    repo_id = "ambig-repo"
    _seed(repo_id, ["a" * 40, "a" * 39 + "b"])
    resp = client.get(f"/repos/{repo_id}/intent/aaaa")
    assert resp.status_code == 404
    assert "ambiguous" in resp.json()["detail"]


def test_unknown_short_sha_returns_404():
    repo_id = "ambig-repo-2"
    _seed(repo_id, ["a" * 40, "b" * 40])
    resp = client.get(f"/repos/{repo_id}/intent/zzzz")
    assert resp.status_code == 404
    assert "unknown commit" in resp.json()["detail"]
