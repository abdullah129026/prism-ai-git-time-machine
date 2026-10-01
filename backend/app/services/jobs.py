"""Background ingest jobs: clone a repo, parse its history, track progress.

Week 1 uses a thread-safe in-memory store — enough for a single API
process. A durable queue (Redis/RQ) replaces this before multi-worker
deploys.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings
from app.services import git_parser
from app.services.git_parser import ParsedCommit


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Job:
    job_id: str
    repo_url: str
    repo_id: str
    max_commits: int
    status: str = "queued"  # queued | cloning | parsing | ready | error
    stage_detail: str = ""
    commits_parsed: int = 0
    error: str | None = None
    created_at: str = field(default_factory=_now)
    finished_at: str | None = None


class JobStore:
    """Thread-safe registry of ingest jobs and parsed repo snapshots."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, Job] = {}
        self._repos: dict[str, dict] = {}

    def create(self, repo_url: str, max_commits: int) -> Job:
        job = Job(
            job_id=uuid.uuid4().hex,
            repo_url=repo_url,
            repo_id=uuid.uuid4().hex[:12],
            max_commits=max_commits,
        )
        with self._lock:
            self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **fields) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            for key, value in fields.items():
                setattr(job, key, value)

    def store_repo(self, repo_id: str, repo_url: str, commits: list[ParsedCommit]) -> None:
        with self._lock:
            self._repos[repo_id] = {
                "repo_url": repo_url,
                "commits": commits,
                "parsed_at": _now(),
            }

    def get_repo(self, repo_id: str) -> dict | None:
        with self._lock:
            return self._repos.get(repo_id)


store = JobStore()


def repo_dir(repo_id: str) -> Path:
    return get_settings().data_dir / "repos" / repo_id


def run_ingest(job_id: str) -> None:
    """Background task: clone the repo and walk its history.

    Never raises — failures are recorded on the job so that
    GET /repos/{job_id} can report them.
    """
    settings = get_settings()
    job = store.get(job_id)
    if job is None:
        return
    dest = repo_dir(job.repo_id)
    try:
        store.update(job_id, status="cloning",
                     stage_detail=f"cloning {job.repo_url}")
        git_parser.clone_repo(job.repo_url, dest,
                              timeout=settings.clone_timeout_seconds)
        store.update(job_id, status="parsing",
                     stage_detail="walking commit history")
        commits = git_parser.walk_history(dest, max_commits=job.max_commits)
        store.store_repo(job.repo_id, job.repo_url, commits)
        store.update(job_id, status="ready",
                     stage_detail=f"parsed {len(commits)} commits",
                     commits_parsed=len(commits), finished_at=_now())
    except Exception as exc:  # noqa: BLE001 — surfaced via job status
        store.update(job_id, status="error", stage_detail="ingest failed",
                     error=str(exc)[:500], finished_at=_now())
