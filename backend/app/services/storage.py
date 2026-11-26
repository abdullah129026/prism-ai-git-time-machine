"""Persistent storage behind the job store (PRISM v2 item 1).

The JobStore keeps jobs and parsed repos in memory; this module is the
one storage layer they move behind, so a backend restart no longer
loses ingested repos. The local disk implementation ships first, for
self-hosting; which persistent store the live deployment uses is
Abdullah's call (v2 scope, open question 1), and it plugs in here
behind the same protocol. Intents already persist on disk through
intent_file and move behind this interface in a later slice.

Disk layout, under the given root:
    repos/<repo_id>.json   {"repo_url", "commits": [...], "parsed_at"}
    jobs/<job_id>.json     the Job dataclass as JSON

Writes are best-effort, like the intent disk cache: a failed write
never breaks the request in flight, memory still holds the entry.
Loads skip corrupt or unknown-shaped files instead of failing startup.
"""

from __future__ import annotations

import json
from contextlib import suppress
from dataclasses import asdict
from pathlib import Path
from typing import Protocol

from app.services.git_parser import FileChange, ParsedCommit
from app.services.jobs import Job


class RepoStorage(Protocol):
    """What a JobStore needs from durable storage."""

    def save_repo(self, repo_id: str, payload: dict) -> None: ...
    def load_repo(self, repo_id: str) -> dict | None: ...
    def load_all_repos(self) -> dict[str, dict]: ...
    def save_job(self, job: Job) -> None: ...
    def load_job(self, job_id: str) -> Job | None: ...
    def load_all_jobs(self) -> dict[str, Job]: ...


class DiskRepoStorage:
    """RepoStorage on local disk, for self-hosting.

    The live deployment's persistent option plugs in behind the same
    protocol; this implementation stays as the self-hosting default.
    """

    def __init__(self, root: Path) -> None:
        self._root = Path(root)
        self._repos_dir = self._root / "repos"
        self._jobs_dir = self._root / "jobs"

    # -- repos ------------------------------------------------------

    def save_repo(self, repo_id: str, payload: dict) -> None:
        data = {
            "repo_url": payload.get("repo_url"),
            "commits": [asdict(c) for c in payload.get("commits", [])],
            "parsed_at": payload.get("parsed_at"),
        }
        self._write(self._repos_dir / f"{repo_id}.json", data)

    def load_repo(self, repo_id: str) -> dict | None:
        return self._read_repo(self._repos_dir / f"{repo_id}.json")

    def load_all_repos(self) -> dict[str, dict]:
        out = {}
        for path in sorted(self._repos_dir.glob("*.json")):
            repo = self._read_repo(path)
            if repo is not None:
                out[path.stem] = repo
        return out

    @staticmethod
    def _read_repo(path: Path) -> dict | None:
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            return None
        if not isinstance(data, dict):
            return None
        try:
            commits = [ParsedCommit(
                sha=c["sha"], message=c["message"], author=c["author"],
                author_email=c["author_email"],
                committed_at=c["committed_at"],
                parents=list(c.get("parents", [])),
                files=[FileChange(**f) for f in c.get("files", [])],
            ) for c in data.get("commits", [])]
        except (KeyError, TypeError):
            return None
        return {"repo_url": data.get("repo_url"), "commits": commits,
                "parsed_at": data.get("parsed_at")}

    # -- jobs -------------------------------------------------------

    def save_job(self, job: Job) -> None:
        self._write(self._jobs_dir / f"{job.job_id}.json", asdict(job))

    def load_job(self, job_id: str) -> Job | None:
        return self._read_job(self._jobs_dir / f"{job_id}.json")

    def load_all_jobs(self) -> dict[str, Job]:
        out = {}
        for path in sorted(self._jobs_dir.glob("*.json")):
            job = self._read_job(path)
            if job is not None:
                out[job.job_id] = job
        return out

    @staticmethod
    def _read_job(path: Path) -> Job | None:
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            return None
        if not isinstance(data, dict):
            return None
        try:
            return Job(**data)
        except TypeError:
            return None

    # -- helpers ----------------------------------------------------

    def _write(self, path: Path, data: dict) -> None:
        """Best-effort write: temp file then rename, so a crash mid-write
        never leaves a half-written JSON behind."""
        tmp = path.with_suffix(".tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(data))
            tmp.replace(path)
        except OSError:
            with suppress(OSError):
                tmp.unlink(missing_ok=True)
