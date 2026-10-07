"""Analysis routes: timeline, commit intent, conflict prediction, ownership."""

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field

from app.services import git_parser
from app.services import conflict as conflict_service
from app.services import embeddings as embeddings_service
from app.services import intent as intent_service
from app.services.intent import CommitIntent, IntentUnavailableError
from app.services.jobs import repo_dir, store
from app.services import ownership as ownership_service

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
    files: list[str] = []  # paths touched — lets views map files back to commits


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
            files=[f.path for f in c.files],
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


class ConflictFileOverlap(BaseModel):
    path: str
    symbols: list[str]
    shared_lines: int


class ConflictPredictionResponse(BaseModel):
    base: str
    head: str
    probability: float
    overlapping_symbols: list[str]
    overlapping_files: list[ConflictFileOverlap]
    explanation: str


@router.post("/{repo_id}/predict-conflict",
            response_model=ConflictPredictionResponse)
def predict_conflict(repo_id: str, body: ConflictRequest) -> ConflictPredictionResponse:
    """Merge-conflict probability for `head` into `base`.

    Compares both branches against their merge-base: files changed on
    both sides feed Tree-sitter AST overlap analysis. 404 when the
    repo or either ref is unknown.
    """
    snapshot = store.get_repo(repo_id)
    if snapshot is None:
        raise HTTPException(
            status_code=404, detail="unknown repo_id — ingest a repo first")
    try:
        result = conflict_service.predict_conflict(
            repo_dir(repo_id), body.base, body.head)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ConflictPredictionResponse(
        base=result.base,
        head=result.head,
        probability=result.probability,
        overlapping_symbols=result.overlapping_symbols,
        overlapping_files=[
            ConflictFileOverlap(
                path=f.path, symbols=f.symbols, shared_lines=f.shared_lines)
            for f in result.overlapping_files
        ],
        explanation=result.explanation,
    )


class OwnershipOwner(BaseModel):
    login: str
    score: float
    lines: int
    commits: int
    evidence: list[str]


class OwnershipResponse(BaseModel):
    repo_id: str
    path: str | None
    commit_count: int
    owners: list[OwnershipOwner]
    related_paths: list[str]


@router.get("/{repo_id}/ownership", response_model=OwnershipResponse)
def ownership(repo_id: str, path: str | None = None) -> OwnershipResponse:
    """Semantic code ownership: who understands this code, not git blame.

    Scores authors by substantive, recent, intent-understood changes
    (cached intent confidence weights each commit). `path` scopes to one
    file or directory; without it the whole repo is ranked. `related_paths`
    lists files with semantically similar code, from the Qdrant chunk index.
    """
    snapshot = store.get_repo(repo_id)
    if snapshot is None:
        raise HTTPException(
            status_code=404, detail="unknown repo_id — ingest a repo first")
    try:
        owners = ownership_service.semantic_owners(repo_id, path)
    except ValueError as exc:
        detail = str(exc)
        status_code = 400 if detail.startswith("invalid path") else 404
        raise HTTPException(status_code=status_code, detail=detail) from exc

    # Keep the chunk index warm: top-churn files, bounded, idempotent.
    churn: dict[str, int] = {}
    for commit in snapshot["commits"]:
        for f in commit.files:
            churn[f.path] = churn.get(f.path, 0) + f.additions + f.deletions
    top_files = sorted(churn, key=churn.get, reverse=True)[:20]
    if path and path not in top_files:
        top_files.append(path)
    embeddings_service.index_scope(repo_dir(repo_id), repo_id, top_files)

    related_paths: list[str] = []
    if path:
        target = repo_dir(repo_id) / path
        try:
            text = target.read_text(encoding="utf-8") if target.is_file() else ""
        except OSError:
            text = ""
        if text:
            hits = embeddings_service.similar_chunks(
                repo_id, text, top_k=5, exclude_path=path)
            for hit in hits:
                if hit.path not in related_paths:
                    related_paths.append(hit.path)

    return OwnershipResponse(
        repo_id=repo_id,
        path=path,
        commit_count=sum(o.commits for o in owners),
        owners=[
            OwnershipOwner(
                login=o.login, score=o.score, lines=o.lines,
                commits=o.commits, evidence=o.evidence)
            for o in owners
        ],
        related_paths=related_paths,
    )
