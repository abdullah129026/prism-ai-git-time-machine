"""Parse git history with GitPython: clone, walk commits, extract diffs.

History is read with two `git log` calls (numstat + name-status) so even
large repos are parsed without one subprocess per commit.
"""

from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError, NoSuchPathError

from app.config import get_settings

#: Hard cap on diff text returned per commit — keeps intent prompts bounded.
MAX_DIFF_CHARS = 200_000

_ALLOWED_SCHEMES = {"http", "https", "git", "ssh", "file"}
_SCP_LIKE = re.compile(r"^[\w.~-]+@[\w.~-]+:[\w./~%-]+$")
_FIELD_SEP = "\x1f"
_LOG_FORMAT = (
    f"COMMIT:%H{_FIELD_SEP}%an{_FIELD_SEP}%ae{_FIELD_SEP}"
    f"%aI{_FIELD_SEP}%P{_FIELD_SEP}%s"
)


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

    @property
    def additions(self) -> int:
        return sum(f.additions for f in self.files)

    @property
    def deletions(self) -> int:
        return sum(f.deletions for f in self.files)


def validate_repo_url(url: str, *, allow_local: bool | None = None) -> str:
    """Return a normalized repo URL/path, or raise ValueError.

    By default only public http(s) URLs are accepted: file://, ssh/scp-like
    and bare local paths are rejected, and the host must resolve to public
    IPs (SSRF guard). Pass allow_local=True — or set PRISM_ALLOW_LOCAL_REPOS
    — for self-hosting and tests.
    """
    if allow_local is None:
        allow_local = get_settings().allow_local_repos
    url = (url or "").strip()
    if not url:
        raise ValueError("repo_url must not be empty")
    scheme = urlparse(url).scheme
    if scheme:
        if scheme not in _ALLOWED_SCHEMES:
            raise ValueError(f"unsupported URL scheme: {scheme}")
        if scheme in ("http", "https"):
            _require_public_host(url)
            return url
        if not allow_local:
            raise ValueError(f"{scheme} URLs are disabled on this server")
        return url
    if _SCP_LIKE.match(url):
        if not allow_local:
            raise ValueError("ssh-style repo URLs are disabled on this server")
        return url
    if not allow_local:
        raise ValueError("local repo paths are disabled on this server")
    path = Path(url).expanduser()
    if path.exists():
        return str(path)
    raise ValueError(f"not a valid repo URL or local path: {url}")


def _require_public_host(url: str) -> None:
    """Reject URLs whose host resolves to a non-public IP.

    Blocks SSRF probes at cloud metadata endpoints (169.254.169.254),
    loopback, and other private ranges before git ever dials out.
    """
    host = urlparse(url).hostname or ""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise ValueError(f"could not resolve repo host: {host}") from exc
    ips = {info[4][0] for info in infos}
    if not ips:
        raise ValueError(f"could not resolve repo host: {host}")
    for ip in ips:
        # ponytail: literal parse, no DNS needed when the host is already an IP
        if not ipaddress.ip_address(ip).is_global:
            raise ValueError(
                f"repo host resolves to a non-public IP: {host}")


def clone_repo(url: str, dest: Path, timeout: int = 300,
               depth: int | None = None) -> Path:
    """Clone a repo URL to dest. Raises on invalid URL or clone failure.

    depth caps the clone to the newest N commits — PRISM only ever parses
    the newest max_commits, so a full clone just wastes disk and bandwidth
    (and lets a huge repo exhaust the disk).
    """
    url = validate_repo_url(url)
    dest = Path(dest)
    if dest.exists():
        raise FileExistsError(f"destination already exists: {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    clone_kwargs: dict = {"kill_after_timeout": timeout}
    if depth is not None:
        clone_kwargs["depth"] = max(1, depth)
    try:
        Repo.clone_from(url, str(dest), **clone_kwargs)
    except GitCommandError as exc:
        raise RuntimeError(f"clone failed for {url}: {exc.stderr or exc}") from exc
    return dest


def walk_history(repo_path: Path, max_commits: int = 500) -> list[ParsedCommit]:
    """Walk commit history newest-first, with per-file stats.

    Returns an empty list for repos without any commits yet.
    """
    try:
        repo = Repo(str(repo_path))
    except (InvalidGitRepositoryError, NoSuchPathError) as exc:
        raise ValueError(f"not a git repository: {repo_path}") from exc

    count = max(1, max_commits)
    try:
        numstat_raw = repo.git.log(
            "HEAD", f"--max-count={count}", f"--format={_LOG_FORMAT}",
            "--numstat", "--no-renames", "-z",
        )
    except GitCommandError:
        return []  # empty repo — HEAD does not exist yet

    commits = _parse_numstat_log(numstat_raw)
    if not commits:
        return []

    try:
        status_raw = repo.git.log(
            "HEAD", f"--max-count={count}", "--format=COMMIT:%H",
            "--name-status", "--no-renames", "-z",
        )
        status_map = _parse_status_log(status_raw)
    except GitCommandError:
        status_map = {}

    for commit in commits:
        per_file = status_map.get(commit.sha, {})
        for change in commit.files:
            change.change_type = per_file.get(change.path, "M")
    return commits


def diff_for_commit(repo_path: Path, sha: str) -> str:
    """Unified diff for a single commit, truncated to MAX_DIFF_CHARS."""
    try:
        repo = Repo(str(repo_path))
    except (InvalidGitRepositoryError, NoSuchPathError) as exc:
        raise ValueError(f"not a git repository: {repo_path}") from exc
    try:
        diff = repo.git.show(
            sha, "--format=", "--patch", "--no-ext-diff",
            "--unified=3", "--no-renames",
        )
    except GitCommandError as exc:
        raise ValueError(f"unknown commit: {sha}") from exc
    if len(diff) > MAX_DIFF_CHARS:
        return diff[:MAX_DIFF_CHARS] + f"\n... [truncated at {MAX_DIFF_CHARS} chars]"
    return diff


def _parse_numstat_log(raw: str) -> list[ParsedCommit]:
    """Parse `git log --format=... --numstat -z` into ParsedCommits."""
    commits: list[ParsedCommit] = []
    current: ParsedCommit | None = None
    for token in raw.split("\0"):
        if token.startswith("COMMIT:"):
            fields = token[len("COMMIT:"):].split(_FIELD_SEP)
            fields += [""] * (6 - len(fields))
            sha, author, email, committed_at, parents, subject = fields[:6]
            current = ParsedCommit(
                sha=sha,
                message=subject,
                author=author,
                author_email=email,
                committed_at=committed_at,
                parents=[p for p in parents.split() if p],
            )
            commits.append(current)
        elif current is not None:
            # One token holds the whole numstat block: lines of add\tdel\tpath.
            for line in token.strip().splitlines():
                parts = line.split("\t")
                if len(parts) != 3:
                    continue
                add_s, del_s, path = parts
                current.files.append(FileChange(
                    path=path,
                    additions=int(add_s) if add_s.isdigit() else 0,
                    deletions=int(del_s) if del_s.isdigit() else 0,
                ))
    return commits


def _parse_status_log(raw: str) -> dict[str, dict[str, str]]:
    """Parse `git log --format=COMMIT:%H --name-status -z` into sha -> path -> type.

    With -z, status and path arrive as separate NUL-delimited tokens.
    """
    result: dict[str, dict[str, str]] = {}
    current_sha: str | None = None
    pending_status: str | None = None
    for token in raw.split("\0"):
        if token.startswith("COMMIT:"):
            current_sha = token[len("COMMIT:"):]
            result[current_sha] = {}
            pending_status = None
        elif current_sha is None:
            continue
        else:
            token = token.lstrip("\n")
            if not token:
                continue
            if pending_status is None:
                pending_status = token
            else:
                result[current_sha][token] = pending_status[0]
                pending_status = None
    return result
