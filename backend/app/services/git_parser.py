"""Parse git history with GitPython: clone, walk commits, extract diffs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FileChange:
    path: str
    additions: int = 0
    deletions: int = 0
    change_type: str = "M"  # A/M/D/R


@dataclass
class ParsedCommit:
    sha: str
    message: str
    author: str
    author_email: str
    committed_at: str  # ISO 8601
    parents: list[str] = field(default_factory=list)
    files: list[FileChange] = field(default_factory=list)


def clone_repo(url: str, dest: Path) -> Path:
    """Clone a repo URL to dest. Implemented in week 1 (days 3-5)."""
    raise NotImplementedError


def walk_history(repo_path: Path, max_commits: int = 500) -> list[ParsedCommit]:
    """Walk commit history newest-first. Implemented in week 1 (days 3-5)."""
    raise NotImplementedError


def diff_for_commit(repo_path: Path, sha: str) -> str:
    """Unified diff for a single commit. Implemented in week 1 (days 3-5)."""
    raise NotImplementedError
