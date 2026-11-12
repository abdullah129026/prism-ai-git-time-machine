"""API tests for semantic ownership: GET /repos/{repo_id}/ownership."""

import os
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
    repo = tmp_path / "ownable"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "alice@example.com")
    _git(repo, "config", "user.name", "Alice")
    (repo / "auth.py").write_text(
        "def authenticate_user(password):\n"
        "    return verify_hash(password)\n"
    )
    (repo / "charts.py").write_text(
        "def render_chart(canvas):\n    draw_axes(canvas)\n"
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add auth and charts")

    resp = client.post("/repos", json={"repo_url": str(repo)})
    assert resp.status_code == 202
    status = client.get(f"/repos/{resp.json()['job_id']}").json()
    assert status["status"] == "ready"
    return status["repo_id"]


def test_ownership_ranks_authors(repo_id: str):
    body = client.get(f"/repos/{repo_id}/ownership").json()
    assert body["repo_id"] == repo_id
    assert body["path"] is None
    assert body["commit_count"] == 1
    assert len(body["owners"]) == 1
    owner = body["owners"][0]
    assert owner["login"] == "Alice"
    assert owner["score"] == 1.0
    assert owner["lines"] > 0
    assert owner["evidence"]


def test_ownership_path_scope_and_related(repo_id: str):
    body = client.get(f"/repos/{repo_id}/ownership",
                      params={"path": "auth.py"}).json()
    assert body["path"] == "auth.py"
    assert len(body["owners"]) == 1
    # charts.py is the only other indexed file, so it shows as related.
    assert body["related_paths"] == ["charts.py"]


def test_ownership_unknown_path_404(repo_id: str):
    resp = client.get(f"/repos/{repo_id}/ownership",
                      params={"path": "missing.py"})
    assert resp.status_code == 404


def test_ownership_traversal_400(repo_id: str):
    resp = client.get(f"/repos/{repo_id}/ownership",
                      params={"path": "../secret"})
    assert resp.status_code == 400


def test_ownership_unknown_repo_404():
    resp = client.get("/repos/no-such-repo/ownership")
    assert resp.status_code == 404


def test_ownership_unparseable_dates_404(tmp_path: Path):
    """A repo whose commits have no parseable dates fails inside
    semantic_owners; the endpoint maps that ValueError to 404, not 500."""
    from app.services.git_parser import FileChange, ParsedCommit
    from app.services.jobs import store

    commit = ParsedCommit(
        sha="c" * 40, message="change auth", author="Alice",
        author_email="alice@example.com", committed_at="garbage-date",
        files=[FileChange(path="auth.py", additions=5)])
    store.store_repo("own-api-nodates", str(tmp_path), [commit])
    resp = client.get("/repos/own-api-nodates/ownership")
    assert resp.status_code == 404
    assert "no parseable commit dates" in resp.json()["detail"]


def test_ownership_symlink_does_not_read_outside_repo(
        tmp_path: Path, monkeypatch):
    """A symlink inside a cloned repo must not let ?path= read a file
    outside the repo and feed it to the similarity search."""
    from app.routers import analyze as analyze_router

    secret = tmp_path / "outside-secret.txt"
    secret.write_text("TOP-SECRET-TOKEN-DO-NOT-READ")
    repo = tmp_path / "linkable"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "alice@example.com")
    _git(repo, "config", "user.name", "Alice")
    (repo / "real.py").write_text("def real():\n    return 1\n")
    os.symlink(secret, repo / "link.py")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add real file and symlink")

    resp = client.post("/repos", json={"repo_url": str(repo)})
    assert resp.status_code == 202
    status = client.get(f"/repos/{resp.json()['job_id']}").json()
    assert status["status"] == "ready"
    repo_id = status["repo_id"]

    seen: list[str] = []
    monkeypatch.setattr(
        analyze_router.embeddings_service, "similar_chunks",
        lambda repo_id_, text, **kw: seen.append(text) or [])
    body = client.get(f"/repos/{repo_id}/ownership",
                      params={"path": "link.py"}).json()
    assert body["owners"], "symlinked path is still a touched path"
    assert seen == [], "outside-repo content must never reach similarity search"


def test_ownership_path_outside_top_churn_is_appended_to_index_scope(
        monkeypatch):
    """With more than 20 touched files, a low-churn ?path= is appended to
    the 20-file index scope instead of being dropped from it.

    Fabricated in the store (no ingest) so the suite stays under the
    ingest rate limit."""
    from app.routers import analyze as analyze_router
    from app.services.git_parser import FileChange, ParsedCommit
    from app.services.jobs import store

    files = [FileChange(path=f"f{i:02d}.py", additions=2) for i in range(21)]
    commit = ParsedCommit(
        sha="a" * 40, message="add twenty-one files", author="Alice",
        author_email="alice@example.com", committed_at="2026-10-22T00:00:00",
        files=files)
    store.store_repo("own-api-manyfiles", "local://manyfiles", [commit])

    seen_scopes: list[list[str]] = []
    monkeypatch.setattr(
        analyze_router.embeddings_service, "index_scope",
        lambda _dir, _repo_id, scope: seen_scopes.append(list(scope)))
    monkeypatch.setattr(
        analyze_router.embeddings_service, "similar_chunks",
        lambda *args, **kw: [])
    body = client.get("/repos/own-api-manyfiles/ownership",
                      params={"path": "f20.py"}).json()
    assert body["owners"]
    assert len(seen_scopes) == 1
    assert len(seen_scopes[0]) == 21
    assert "f20.py" in seen_scopes[0]
