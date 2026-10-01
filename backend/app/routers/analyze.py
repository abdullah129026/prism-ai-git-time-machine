"""Analysis routes: timeline, conflict prediction, ownership."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.jobs import store

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


@router.post("/{repo_id}/predict-conflict")
def predict_conflict(repo_id: str, body: ConflictRequest) -> dict:
    # Week 2 (days 11-12)
    raise NotImplementedError


@router.get("/{repo_id}/ownership")
def ownership(repo_id: str, path: str | None = None) -> dict:
    # Week 2 (days 13-14)
    raise NotImplementedError
