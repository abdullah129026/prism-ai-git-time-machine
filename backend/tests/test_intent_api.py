"""API tests for the intent endpoints.

Covers GET /repos/{repo_id}/intent/{sha} lookup semantics and the
POST /repos/{repo_id}/intent/analyze warming paths.
"""

import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.routers.analyze import _warm_intent_cache
from app.services.git_parser import ParsedCommit
from app.services.intent import CommitIntent, IntentUnavailableError
from app.services.jobs import store
from test_timeline_api import repo_id  # noqa: F401 — shared ingest fixture

client = TestClient(app)


def _seed(rid: str, shas: list[str]) -> None:
    commits = [
        ParsedCommit(
            sha=sha, message=f"commit {i}", author="t",
            author_email="t@example.com", committed_at="2026-10-22T00:00:00",
        )
        for i, sha in enumerate(shas)
    ]
    store.store_repo(rid, "https://example.com/r.git", commits)


def test_ambiguous_short_sha_returns_404():
    rid = "ambig-repo"
    _seed(rid, ["a" * 40, "a" * 39 + "b"])
    resp = client.get(f"/repos/{rid}/intent/aaaa")
    assert resp.status_code == 404
    assert "ambiguous" in resp.json()["detail"]


def test_unknown_short_sha_returns_404():
    rid = "ambig-repo-2"
    _seed(rid, ["a" * 40, "b" * 40])
    resp = client.get(f"/repos/{rid}/intent/zzzz")
    assert resp.status_code == 404
    assert "unknown commit" in resp.json()["detail"]


def test_analyze_intent_unknown_repo_404():
    resp = client.post("/repos/no-such-repo/intent/analyze", json={"limit": 5})
    assert resp.status_code == 404
    assert "unknown repo_id" in resp.json()["detail"]


def test_analyze_intent_unconfigured_503(repo_id: str):  # noqa: F811 — param requests the shared fixture by name
    with patch("app.services.intent.is_configured", return_value=False):
        resp = client.post(f"/repos/{repo_id}/intent/analyze",
                           json={"limit": 5})
    assert resp.status_code == 503
    assert "intent engine unavailable" in resp.json()["detail"]


def test_analyze_intent_starts_warming(repo_id: str):  # noqa: F811 — param requests the shared fixture by name
    with patch("app.services.intent.is_configured", return_value=True), \
            patch("app.routers.analyze._warm_intent_cache") as warm:
        resp = client.post(f"/repos/{repo_id}/intent/analyze",
                           json={"limit": 5})
    assert resp.status_code == 200
    assert resp.json() == {"started": True, "repo_id": repo_id, "limit": 5}
    # TestClient runs background tasks synchronously before returning.
    warm.assert_called_once_with(repo_id, 5)


def _unique_rid(prefix: str) -> str:
    # Intent cache spills to disk (/tmp/prism_data), so a fixed repo id
    # would read a previous run's cache and flip cached True/False.
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def test_intent_cached_hit_returns_cached():
    rid = _unique_rid("intent-cached-repo")
    sha = "c" * 40
    _seed(rid, [sha])
    store.set_intent(
        rid, sha,
        CommitIntent(sha=sha, why="fix crash", bug_fixed="crash",
                     risk="none", confidence=0.9))
    resp = client.get(f"/repos/{rid}/intent/{sha}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["cached"] is True
    assert body["intent"]["why"] == "fix crash"
    assert body["intent_available"] is True


def test_intent_generates_and_caches_when_missing():
    rid = _unique_rid("intent-gen-repo")
    sha = "d" * 40
    _seed(rid, [sha])
    intent = CommitIntent(sha=sha, why="add retry", bug_fixed=None,
                          risk="extra latency", confidence=0.8)
    with patch("app.routers.analyze.git_parser.diff_for_commit",
               return_value="diff") as diff, \
            patch("app.routers.analyze.intent_service.generate_intent",
                  return_value=intent) as gen:
        resp = client.get(f"/repos/{rid}/intent/{sha}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["cached"] is False
        assert body["intent"]["why"] == "add retry"
        # Second call is served from the cache the first call populated.
        resp2 = client.get(f"/repos/{rid}/intent/{sha}")
    assert resp2.json()["cached"] is True
    diff.assert_called_once()
    gen.assert_called_once()


def test_intent_unavailable_degrades_to_200():
    rid = _unique_rid("intent-down-repo")
    sha = "e" * 40
    _seed(rid, [sha])
    with patch("app.routers.analyze.git_parser.diff_for_commit",
               return_value="diff"), \
            patch("app.routers.analyze.intent_service.generate_intent",
                  side_effect=IntentUnavailableError("no key")):
        resp = client.get(f"/repos/{rid}/intent/{sha}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["cached"] is False
    assert body["intent"] is None
    assert body["intent_available"] is False


def test_intent_unknown_repo_404():
    resp = client.get("/repos/no-such-repo/intent/" + "f" * 40)
    assert resp.status_code == 404
    assert "unknown repo_id" in resp.json()["detail"]


def test_warm_intent_cache_unknown_repo_returns():
    assert _warm_intent_cache("no-such-repo", 5) is None


def test_warm_intent_cache_skips_cached_commits(repo_id: str):  # noqa: F811 — param requests the shared fixture by name
    commits = store.get_repo(repo_id)["commits"]
    store.set_intent(
        repo_id, commits[0].sha,
        CommitIntent(sha=commits[0].sha, why="w", bug_fixed=None,
                     risk="r", confidence=0.9))
    with patch("app.routers.analyze._generate_and_cache") as gen:
        _warm_intent_cache(repo_id, 20)
    gen.assert_called_once()
    assert gen.call_args[0][1] == commits[1].sha


def test_warm_intent_cache_stops_when_engine_unavailable(repo_id: str):  # noqa: F811 — param requests the shared fixture by name
    with patch("app.routers.analyze._generate_and_cache",
               side_effect=IntentUnavailableError("no key")) as gen:
        _warm_intent_cache(repo_id, 20)
    # the failure is swallowed — the warm-up just stops, never raises
    assert gen.call_count == 1
