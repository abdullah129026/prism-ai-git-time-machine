"""Repo ingestion routes: submit a URL, track parsing jobs."""

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from app.config import get_settings
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
