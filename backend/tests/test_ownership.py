"""Unit tests for intent-weighted semantic ownership scoring."""

import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from app.services import git_parser
from app.services.git_parser import FileChange, ParsedCommit
from app.services.intent import CommitIntent
from app.services.jobs import store
from app.services.ownership import (
    _recency_weight,
    _validate_path,
    semantic_owners,
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _commit(repo: Path, name: str, email: str, message: str) -> None:
    _git(repo, "add", ".")
    _git(repo, "-c", f"user.name={name}", "-c", f"user.email={email}",
         "commit", "-m", message)


@pytest.fixture()
def two_author_repo(tmp_path: Path) -> Path:
    """Alice writes a 30-line feature; Bob later fixes one line."""
    repo = tmp_path / "owned"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    body = "".join(f"def step_{i}():\n    return {i}\n\n" for i in range(10))
    (repo / "auth.py").write_text(body)
    _commit(repo, "Alice", "alice@example.com", "add auth flow")
    (repo / "auth.py").write_text(body.replace("return 0", "return 42"))
    _commit(repo, "Bob", "bob@example.com", "fix off-by-one in step_0")
    return repo


def _ingest(repo: Path, repo_id: str) -> None:
    commits = git_parser.walk_history(repo, max_commits=500)
    store.store_repo(repo_id, str(repo), commits)


def test_substantive_author_outranks_drive_by(two_author_repo: Path):
    _ingest(two_author_repo, "own-basic")
    owners = semantic_owners("own-basic")
    assert [o.login for o in owners] == ["Alice", "Bob"]
    assert owners[0].score == 1.0
    assert 0.0 < owners[1].score < 1.0
    assert owners[0].lines > owners[1].lines
    assert owners[0].commits == 1
    assert owners[0].evidence and "add auth flow" in owners[0].evidence[0]


def test_path_scoping(two_author_repo: Path):
    _ingest(two_author_repo, "own-scope")
    owners = semantic_owners("own-scope", path="auth.py")
    assert {o.login for o in owners} == {"Alice", "Bob"}
    with pytest.raises(ValueError, match="no commits touch path"):
        semantic_owners("own-scope", path="missing.py")


def test_intent_weight_moves_the_needle(two_author_repo: Path):
    """Same history, different cached intents: the well-understood small
    change can outrank the poorly-understood big one."""
    _ingest(two_author_repo, "own-intent")
    commits = store.get_repo("own-intent")["commits"]
    alice_sha = next(c.sha for c in commits if c.author == "Alice")
    bob_sha = next(c.sha for c in commits if c.author == "Bob")

    plain = {o.login: o.score for o in semantic_owners("own-intent")}
    assert plain["Alice"] > plain["Bob"]

    store.set_intent("own-intent", alice_sha, CommitIntent(
        sha=alice_sha, why="unclear", bug_fixed=None, risk="unknown",
        confidence=0.0))
    store.set_intent("own-intent", bob_sha, CommitIntent(
        sha=bob_sha, why="fixes step_0", bug_fixed="off-by-one",
        risk="low", confidence=1.0))
    weighted = {o.login: o.score for o in semantic_owners("own-intent")}
    assert weighted["Bob"] == 1.0
    assert weighted["Alice"] == 0.0


def test_unknown_repo_raises():
    with pytest.raises(ValueError, match="unknown repo_id"):
        semantic_owners("no-such-repo")


def test_path_validation_rejects_traversal():
    for bad in ["../secret", "/etc/passwd", "..", "x" * 501, ""]:
        with pytest.raises(ValueError, match="invalid path"):
            _validate_path(bad)
    assert _validate_path("src/auth.py") == "src/auth.py"
    assert _validate_path("./src/auth.py") == "src/auth.py"


def test_recency_weight_unparseable_date_counts_full():
    """A commit whose date cannot be parsed must not vanish from the
    ranking: it counts at full weight instead of raising."""
    assert _recency_weight("not-a-date", datetime(2026, 11, 9)) == 1.0


def test_recency_weight_halves_after_one_half_life():
    newest = datetime(2026, 11, 9)
    assert _recency_weight("2026-11-09T00:00:00", newest) == pytest.approx(1.0)
    assert _recency_weight("2026-05-13T00:00:00", newest) == pytest.approx(0.5)


def test_empty_repo_raises(tmp_path: Path):
    store.store_repo("own-empty", str(tmp_path), [])
    with pytest.raises(ValueError, match="no commits in repo"):
        semantic_owners("own-empty")


def _commit_with_date(sha: str, committed_at: str) -> ParsedCommit:
    return ParsedCommit(
        sha=sha, message="change auth", author="Alice",
        author_email="alice@example.com", committed_at=committed_at,
        files=[FileChange(path="auth.py", additions=5)])


def test_no_parseable_dates_raises(tmp_path: Path):
    """Every commit date unparseable: the ranking cannot pick a newest
    commit, so it raises instead of dividing by a bogus recency."""
    store.store_repo("own-nodates", str(tmp_path),
                     [_commit_with_date("a" * 40, "garbage-date")])
    with pytest.raises(ValueError, match="no parseable commit dates"):
        semantic_owners("own-nodates")


def test_mixed_parseable_and_unparseable_dates_rank(tmp_path: Path):
    """One bad date among good ones: the bad commit still counts (full
    recency weight) and the good one anchors the newest date."""
    store.store_repo("own-mixeddates", str(tmp_path), [
        _commit_with_date("a" * 40, "garbage-date"),
        _commit_with_date("b" * 40, "2026-11-09T00:00:00"),
    ])
    owners = semantic_owners("own-mixeddates")
    assert [o.login for o in owners] == ["Alice"]
    assert owners[0].commits == 2
    assert owners[0].lines == 10
