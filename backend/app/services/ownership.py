"""Semantic code ownership: who understands this code.

Not git blame. Blame tells you who last touched a line; this scores who
*changed* the code substantively, weighted by recency and by how well the
change was understood (cached intent confidence — a commit whose "why" the
intent engine grasped with high confidence counts more than a drive-by).

score(author) = sum over their commits of
    changed_lines * recency_decay * intent_weight
normalized so the top scorer is 1.0.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

#: Recency half-life: a commit from this many days ago counts half as much.
RECENCY_HALF_LIFE_DAYS = 180.0

#: Intent weight when a commit has no cached intent analysis yet.
DEFAULT_INTENT_WEIGHT = 0.5

#: Reject absurdly long paths before they touch the filesystem.
MAX_PATH_LEN = 500


@dataclass
class Owner:
    login: str
    score: float  # 0.0 - 1.0, normalized to the top scorer
    lines: int  # lines changed in scope
    commits: int  # commits touching the scope
    evidence: list[str] = field(default_factory=list)


def _validate_path(path: str) -> str:
    path = (path or "").strip()
    if path.startswith("./"):
        path = path[2:]
    if not path or len(path) > MAX_PATH_LEN:
        raise ValueError(f"invalid path: {path!r}")
    if Path(path).is_absolute() or ".." in Path(path).parts:
        raise ValueError(f"invalid path: {path!r}")
    return path


def _in_scope(file_path: str, scope: str | None) -> bool:
    if scope is None:
        return True
    return file_path == scope or file_path.startswith(scope.rstrip("/") + "/")


def _recency_weight(committed_at: str, newest: datetime) -> float:
    try:
        when = datetime.fromisoformat(committed_at)
    except ValueError:
        return 1.0
    age_days = max(0.0, (newest - when).total_seconds() / 86400.0)
    return 0.5 ** (age_days / RECENCY_HALF_LIFE_DAYS)


def semantic_owners(repo_id: str, path: str | None = None) -> list[Owner]:
    """Rank authors by substantive, recent, understood changes.

    `path` scopes to one file or directory; None covers the whole repo.
    Raises ValueError for unknown repos or paths no commit touches.
    """
    from app.services.jobs import store

    scope = _validate_path(path) if path else None

    snapshot = store.get_repo(repo_id)
    if snapshot is None:
        raise ValueError(f"unknown repo_id: {repo_id}")
    commits = snapshot["commits"]
    if not commits:
        raise ValueError(f"no commits in repo: {repo_id}")

    newest = max(
        (datetime.fromisoformat(c.committed_at) for c in commits
         if _parseable(c.committed_at)),
        default=None,
    )
    if newest is None:
        raise ValueError(f"no parseable commit dates in repo: {repo_id}")

    totals: dict[str, dict] = {}
    matched = 0
    for commit in commits:
        scoped = [f for f in commit.files if _in_scope(f.path, scope)]
        if not scoped:
            continue
        matched += 1
        lines = sum(f.additions + f.deletions for f in scoped)
        cached = store.get_intent(repo_id, commit.sha)
        intent_w = cached.confidence if cached is not None else DEFAULT_INTENT_WEIGHT
        contribution = lines * _recency_weight(commit.committed_at, newest) * intent_w

        entry = totals.setdefault(commit.author, {
            "score": 0.0, "lines": 0, "commits": 0, "evidence": []})
        entry["score"] += contribution
        entry["lines"] += lines
        entry["commits"] += 1
        headline = (commit.message.splitlines() or [""])[0][:72]
        entry["evidence"].append(
            (contribution,
             f"{commit.sha[:7]} +{sum(f.additions for f in scoped)}/"
             f"-{sum(f.deletions for f in scoped)}, {headline}"))

    if matched == 0:
        raise ValueError(f"no commits touch path: {scope!r}")

    peak = max(e["score"] for e in totals.values()) or 1.0
    owners = [
        Owner(
            login=login,
            score=round(entry["score"] / peak, 3),
            lines=entry["lines"],
            commits=entry["commits"],
            evidence=[text for _, text in sorted(
                entry["evidence"], reverse=True)[:3]],
        )
        for login, entry in totals.items()
    ]
    owners.sort(key=lambda o: o.score, reverse=True)
    return owners


def _parseable(value: str) -> bool:
    try:
        datetime.fromisoformat(value)
        return True
    except ValueError:
        return False
