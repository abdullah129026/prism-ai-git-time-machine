"""Repo ingestion routes: submit a URL, track parsing jobs."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class IngestRequest(BaseModel):
    repo_url: str
    max_commits: int = 500


class IngestResponse(BaseModel):
    job_id: str
    status: str


@router.post("", response_model=IngestResponse, status_code=202)
def ingest_repo(body: IngestRequest) -> IngestResponse:
    # Week 1 (days 3-5): enqueue background clone + parse job
    raise NotImplementedError


@router.get("/{job_id}")
def job_status(job_id: str) -> dict:
    # Week 1 (days 3-5): return parse progress
    raise NotImplementedError
