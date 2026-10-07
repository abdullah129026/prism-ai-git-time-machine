"""Repo ingestion routes: submit a URL, track parsing jobs."""

import json

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.services import git_parser
from app.services.jobs import run_ingest, store

router = APIRouter()
settings = get_settings()


class IngestRequest(BaseModel):
    repo_url: str
    max_commits: int = Field(default=500, ge=1, le=5000)


class IngestResponse(BaseModel):
    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    job_id: str
    repo_id: str
    status: str
    stage_detail: str
    commits_parsed: int
    error: str | None = None


@router.post("", response_model=IngestResponse, status_code=202)
def ingest_repo(body: IngestRequest, background: BackgroundTasks) -> IngestResponse:
    try:
        repo_url = git_parser.validate_repo_url(body.repo_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    job = store.create(repo_url, min(body.max_commits, settings.max_commits))
    background.add_task(run_ingest, job.job_id)
    return IngestResponse(job_id=job.job_id, status=job.status)


class DemoResponse(BaseModel):
    enabled: bool
    repo_id: str | None = None
    status: str  # disabled | seeding | ready


def _demo_repo_id(cfg: Settings) -> str | None:
    marker = cfg.data_dir / "demo.json"
    if not marker.exists():
        return None
    try:
        return json.loads(marker.read_text()).get("repo_id")
    except (OSError, ValueError):
        return None


# Registered before /{job_id} so "demo" isn't captured as a job id.
@router.get("/demo", response_model=DemoResponse)
def demo_status() -> DemoResponse:
    cfg = get_settings()
    if not cfg.demo_repo.strip():
        return DemoResponse(enabled=False, status="disabled")
    repo_id = _demo_repo_id(cfg)
    if repo_id is not None and store.get_repo(repo_id) is not None:
        return DemoResponse(enabled=True, repo_id=repo_id, status="ready")
    return DemoResponse(enabled=True, status="seeding")


@router.get("/{job_id}", response_model=JobStatusResponse)
def job_status(job_id: str) -> JobStatusResponse:
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="unknown job_id")
    return JobStatusResponse(
        job_id=job.job_id,
        repo_id=job.repo_id,
        status=job.status,
        stage_detail=job.stage_detail,
        commits_parsed=job.commits_parsed,
        error=job.error,
    )
