"""API tests for the intent endpoints.

Covers GET /repos/{repo_id}/intent/{sha} lookup semantics and the
POST /repos/{repo_id}/intent/analyze warming paths.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.routers.analyze import _warm_intent_cache
from app.services.git_parser import ParsedCommit
from app.services.intent import CommitIntent, IntentUnavailableError
from app.services.jobs import store
from test_timeline_api import repo_id  # noqa: F401 — shared ingest fixture

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


def test_analyze_intent_unknown_repo_404():
    resp = client.post("/repos/no-such-repo/intent/analyze", json={"limit": 5})
    assert resp.status_code == 404
    assert "unknown repo_id" in resp.json()["detail"]


def test_analyze_intent_unconfigured_503(repo_id: str):
    with patch("app.services.intent.is_configured", return_value=False):
        resp = client.post(f"/repos/{repo_id}/intent/analyze",
                           json={"limit": 5})
    assert resp.status_code == 503
    assert "intent engine unavailable" in resp.json()["detail"]


def test_analyze_intent_starts_warming(repo_id: str):
    with patch("app.services.intent.is_configured", return_value=True), \
            patch("app.routers.analyze._warm_intent_cache") as warm:
        resp = client.post(f"/repos/{repo_id}/intent/analyze",
                           json={"limit": 5})
    assert resp.status_code == 200
    assert resp.json() == {"started": True, "repo_id": repo_id, "limit": 5}
    # TestClient runs background tasks synchronously before returning.
    warm.assert_called_once_with(repo_id, 5)


def test_warm_intent_cache_unknown_repo_returns():
    assert _warm_intent_cache("no-such-repo", 5) is None


def test_warm_intent_cache_skips_cached_commits(repo_id: str):
    commits = store.get_repo(repo_id)["commits"]
    store.set_intent(
        repo_id, commits[0].sha,
        CommitIntent(sha=commits[0].sha, why="w", bug_fixed=None,
                     risk="r", confidence=0.9))
    with patch("app.routers.analyze._generate_and_cache") as gen:
        _warm_intent_cache(repo_id, 20)
    gen.assert_called_once()
    assert gen.call_args[0][1] == commits[1].sha


def test_warm_intent_cache_stops_when_engine_unavailable(repo_id: str):
    with patch("app.routers.analyze._generate_and_cache",
               side_effect=IntentUnavailableError("no key")) as gen:
        _warm_intent_cache(repo_id, 20)
    # the failure is swallowed — the warm-up just stops, never raises
    assert gen.call_count == 1
