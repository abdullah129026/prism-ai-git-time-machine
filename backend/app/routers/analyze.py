"""Analysis routes: timeline, commit intent, conflict prediction, ownership."""

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field

from app.services import git_parser
from app.services import intent as intent_service
from app.services.intent import CommitIntent, IntentUnavailableError
from app.services.jobs import repo_dir, store

router = APIRouter()


class TimelineNode(BaseModel):
    sha: str
    message: str
    author: str
    committed_at: str
    parents: list[str]
    additions: int
    deletions: int
    files_changed: int


class TimelineEdge(BaseModel):
    source: str
    target: str


class FileChurn(BaseModel):
    path: str
    additions: int
    deletions: int
    commits: int


class TimelineResponse(BaseModel):
    repo_id: str
    repo_url: str
    commit_count: int
    nodes: list[TimelineNode]
    edges: list[TimelineEdge]
    file_churn: list[FileChurn]


@router.get("/{repo_id}/timeline", response_model=TimelineResponse)
def timeline(
    repo_id: str,
    limit: int = Query(default=500, ge=1, le=2000),
) -> TimelineResponse:
    """3D-ready timeline JSON: commit nodes on a time axis, parent edges,
    and per-file churn for the file "buildings" view."""
    snapshot = store.get_repo(repo_id)
    if snapshot is None:
        raise HTTPException(
            status_code=404, detail="unknown repo_id — ingest a repo first")

    commits = snapshot["commits"][:limit]
    known = {c.sha for c in commits}

    nodes = [
        TimelineNode(
            sha=c.sha,
            message=c.message,
            author=c.author,
            committed_at=c.committed_at,
            parents=c.parents,
            additions=c.additions,
            deletions=c.deletions,
            files_changed=len(c.files),
        )
        for c in commits
    ]
    edges = [
        TimelineEdge(source=parent, target=c.sha)
        for c in commits
        for parent in c.parents
        if parent in known
    ]

    churn: dict[str, FileChurn] = {}
    for c in commits:
        for f in c.files:
            entry = churn.setdefault(
                f.path, FileChurn(path=f.path, additions=0, deletions=0, commits=0))
            entry.additions += f.additions
            entry.deletions += f.deletions
            entry.commits += 1
    top_files = sorted(
        churn.values(), key=lambda e: e.additions + e.deletions, reverse=True)[:50]

    return TimelineResponse(
        repo_id=repo_id,
        repo_url=snapshot["repo_url"],
        commit_count=len(snapshot["commits"]),
        nodes=nodes,
        edges=edges,
        file_churn=top_files,
    )


class ConflictRequest(BaseModel):
    base: str
    head: str


class IntentCommitSummary(BaseModel):
    sha: str
    message: str
    author: str
    committed_at: str
    additions: int
    deletions: int
    files_changed: int


class IntentResponse(BaseModel):
    repo_id: str
    cached: bool
    commit: IntentCommitSummary
    intent: CommitIntent | None
    intent_available: bool = True


def _find_commit(snapshot: dict, sha: str):
    """Find a commit by full or short SHA."""
    for commit in snapshot["commits"]:
        if commit.sha == sha or commit.sha.startswith(sha):
            return commit
    return None


def _commit_summary(commit) -> IntentCommitSummary:
    return IntentCommitSummary(
        sha=commit.sha,
        message=commit.message,
        author=commit.author,
        committed_at=commit.committed_at,
        additions=commit.additions,
        deletions=commit.deletions,
        files_changed=len(commit.files),
    )


def _generate_and_cache(repo_id: str, sha: str, message: str) -> CommitIntent:
    """Generate intent for one commit, cache it, and return it."""
    diff = git_parser.diff_for_commit(repo_dir(repo_id), sha)
    intent = intent_service.generate_intent(sha, message, diff)
    store.set_intent(repo_id, sha, intent)
    return intent


@router.get("/{repo_id}/intent/{sha}", response_model=IntentResponse)
def commit_intent(repo_id: str, sha: str) -> IntentResponse:
    """Why / what bug / what risk for one commit.

    Served from cache when available, otherwise generated on demand with
    Groq and cached. Returns 503 when the intent engine has no API key.
    """
    snapshot = store.get_repo(repo_id)
    if snapshot is None:
        raise HTTPException(
            status_code=404, detail="unknown repo_id — ingest a repo first")
    commit = _find_commit(snapshot, sha)
    if commit is None:
        raise HTTPException(
            status_code=404, detail=f"unknown commit: {sha}")

    cached = store.get_intent(repo_id, commit.sha)
    if cached is not None:
        return IntentResponse(
            repo_id=repo_id, cached=True,
            commit=_commit_summary(commit), intent=cached)

    try:
        intent = _generate_and_cache(repo_id, commit.sha, commit.message)
    except IntentUnavailableError as exc:
        return IntentResponse(
            repo_id=repo_id, cached=False,
            commit=_commit_summary(commit), intent=None,
            intent_available=False)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return IntentResponse(
        repo_id=repo_id, cached=False,
        commit=_commit_summary(commit), intent=intent)


class AnalyzeIntentRequest(BaseModel):
    limit: int = Field(default=20, ge=1, le=200)


def _warm_intent_cache(repo_id: str, limit: int) -> None:
    """Background task: analyze the N most recent uncached commits."""
    snapshot = store.get_repo(repo_id)
    if snapshot is None:
        return
    for commit in snapshot["commits"][:limit]:
        if store.get_intent(repo_id, commit.sha) is not None:
            continue
        try:
            _generate_and_cache(repo_id, commit.sha, commit.message)
        except (IntentUnavailableError, ValueError):
            break  # key missing or repo gone — no point continuing


@router.post("/{repo_id}/intent/analyze")
def analyze_intent(repo_id: str, body: AnalyzeIntentRequest,
                   background: BackgroundTasks) -> dict:
    """Warm the intent cache for the N most recent commits (background)."""
    snapshot = store.get_repo(repo_id)
    if snapshot is None:
        raise HTTPException(
            status_code=404, detail="unknown repo_id — ingest a repo first")
    if not intent_service.is_configured():
        raise HTTPException(
            status_code=503,
            detail="intent engine unavailable — set PRISM_GROQ_API_KEY")
    background.add_task(_warm_intent_cache, repo_id, body.limit)
    return {"started": True, "repo_id": repo_id, "limit": body.limit}


@router.post("/{repo_id}/predict-conflict")
def predict_conflict(repo_id: str, body: ConflictRequest) -> dict:
    # Week 2 (days 11-12)
    raise NotImplementedError


@router.get("/{repo_id}/ownership")
def ownership(repo_id: str, path: str | None = None) -> dict:
    # Week 2 (days 13-14)
    raise NotImplementedError
