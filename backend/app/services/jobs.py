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

import json

from app.config import get_settings
from app.services import git_parser
from app.services.git_parser import ParsedCommit
from app.services.intent import CommitIntent


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
        self._intents: dict[str, CommitIntent] = {}

    def _intent_key(self, repo_id: str, sha: str) -> str:
        return f"{repo_id}:{sha}"

    def get_intent(self, repo_id: str, sha: str) -> CommitIntent | None:
        """Return a cached intent, checking memory then disk."""
        key = self._intent_key(repo_id, sha)
        with self._lock:
            cached = self._intents.get(key)
        if cached is not None:
            return cached
        disk_path = intent_file(repo_id, sha)
        if disk_path.exists():
            try:
                data = json.loads(disk_path.read_text())
                intent = CommitIntent.from_dict(data)
                with self._lock:
                    self._intents[key] = intent
                return intent
            except (OSError, ValueError, KeyError):
                return None
        return None

    def set_intent(self, repo_id: str, sha: str, intent: CommitIntent) -> None:
        """Cache an intent in memory and on disk (survives restarts)."""
        with self._lock:
            self._intents[self._intent_key(repo_id, sha)] = intent
        try:
            path = intent_file(repo_id, sha)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(intent.to_dict()))
        except OSError:
            pass  # disk cache is best-effort; memory still holds it

    def list_intents(self, repo_id: str) -> list[CommitIntent]:
        with self._lock:
            return [i for k, i in self._intents.items()
                    if k.startswith(f"{repo_id}:")]

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


def intent_file(repo_id: str, sha: str) -> Path:
    """Disk location of one cached intent JSON."""
    return get_settings().data_dir / "intents" / repo_id / f"{sha}.json"


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
