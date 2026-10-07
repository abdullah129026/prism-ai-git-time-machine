"""Unit tests for git history parsing (clone, walk, diff)."""

import socket
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services import git_parser


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture()
def sample_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "sample"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / "app.py").write_text("print('v1')\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial commit")
    (repo / "app.py").write_text("print('v1')\nprint('v2')\n")
    (repo / "util.py").write_text("x = 1\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add feature")
    (repo / "util.py").unlink()
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "remove util")
    return repo


def test_walk_history_parses_commits_newest_first(sample_repo: Path):
    commits = git_parser.walk_history(sample_repo)
    assert len(commits) == 3
    assert commits[0].message == "remove util"
    assert commits[2].message == "initial commit"
    assert all(len(c.sha) == 40 for c in commits)
    assert commits[2].parents == []  # root commit
    assert commits[0].parents  # has a parent
    assert commits[0].committed_at  # ISO 8601 timestamp present


def test_walk_history_file_stats_and_types(sample_repo: Path):
    commits = git_parser.walk_history(sample_repo)

    newest = {f.path: f for f in commits[0].files}
    assert newest["util.py"].change_type == "D"
    assert newest["util.py"].deletions == 1

    middle = {f.path: f for f in commits[1].files}
    assert middle["util.py"].change_type == "A"
    assert middle["app.py"].change_type == "M"
    assert middle["app.py"].additions == 1
    assert middle["app.py"].deletions == 0

    root = {f.path: f for f in commits[2].files}
    assert root["app.py"].change_type == "A"


def test_walk_history_respects_max_commits(sample_repo: Path):
    assert len(git_parser.walk_history(sample_repo, max_commits=2)) == 2


def test_walk_history_empty_repo(tmp_path: Path):
    repo = tmp_path / "empty"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    assert git_parser.walk_history(repo) == []


def test_walk_history_not_a_repo(tmp_path: Path):
    with pytest.raises(ValueError, match="not a git repository"):
        git_parser.walk_history(tmp_path)


def test_diff_for_commit_returns_patch(sample_repo: Path):
    commits = git_parser.walk_history(sample_repo)
    diff = git_parser.diff_for_commit(sample_repo, commits[1].sha)
    assert "print('v2')" in diff
    assert diff.startswith("diff --git")


def test_diff_for_unknown_sha_raises(sample_repo: Path):
    with pytest.raises(ValueError, match="unknown commit"):
        git_parser.diff_for_commit(sample_repo, "0" * 40)


def test_validate_repo_url_accepts_local_path(sample_repo: Path):
    assert (git_parser.validate_repo_url(str(sample_repo), allow_local=True)
            == str(sample_repo))


def test_validate_repo_url_rejects_garbage():
    with pytest.raises(ValueError):
        git_parser.validate_repo_url("not a url ;;", allow_local=True)
    with pytest.raises(ValueError):
        git_parser.validate_repo_url("ftp://example.com/x.git",
                                       allow_local=True)
    with pytest.raises(ValueError):
        git_parser.validate_repo_url("", allow_local=True)


def test_validate_repo_url_rejects_file_scheme_by_default():
    with pytest.raises(ValueError, match="disabled"):
        git_parser.validate_repo_url("file:///etc/passwd", allow_local=False)


def test_validate_repo_url_rejects_ssh_by_default():
    with pytest.raises(ValueError, match="disabled"):
        git_parser.validate_repo_url("git@github.com:owner/repo.git",
                                       allow_local=False)
    with pytest.raises(ValueError, match="disabled"):
        git_parser.validate_repo_url("ssh://git@github.com/owner/repo.git",
                                       allow_local=False)


def test_validate_repo_url_rejects_local_path_by_default(sample_repo: Path):
    with pytest.raises(ValueError, match="disabled"):
        git_parser.validate_repo_url(str(sample_repo), allow_local=False)


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/x.git",
    "http://10.0.0.1/x.git",
    "http://169.254.169.254/latest/meta-data/",
    "https://[::1]/x.git",
])
def test_validate_repo_url_rejects_non_public_hosts(url: str):
    # literal IPs need no DNS, so this also runs offline
    with pytest.raises(ValueError, match="non-public"):
        git_parser.validate_repo_url(url, allow_local=False)


def test_validate_repo_url_accepts_public_https():
    fake_info = [(None, None, None, None, ("140.82.121.4", 0))]
    with patch("socket.getaddrinfo", return_value=fake_info):
        url = "https://github.com/owner/repo.git"
        assert git_parser.validate_repo_url(url, allow_local=False) == url


def test_validate_repo_url_rejects_unresolvable_host():
    with patch("socket.getaddrinfo",
               side_effect=socket.gaierror("nope")):
        with pytest.raises(ValueError, match="could not resolve"):
            git_parser.validate_repo_url("https://nonexistent.invalid/x.git",
                                           allow_local=False)


def test_clone_repo_copies_local_path(tmp_path: Path, sample_repo: Path):
    dest = tmp_path / "clone"
    git_parser.clone_repo(str(sample_repo), dest)
    assert (dest / ".git").exists()
    assert len(git_parser.walk_history(dest)) == 3


def test_clone_repo_refuses_existing_dest(tmp_path: Path, sample_repo: Path):
    with pytest.raises(FileExistsError):
        git_parser.clone_repo(str(sample_repo), sample_repo)


def test_clone_repo_passes_depth_to_git(tmp_path: Path, sample_repo: Path):
    dest = tmp_path / "shallow"
    with patch.object(git_parser.Repo, "clone_from") as mock_clone:
        git_parser.clone_repo(str(sample_repo), dest, depth=7)
    _, kwargs = mock_clone.call_args
    assert kwargs["depth"] == 7


def test_clone_repo_without_depth_omits_flag(tmp_path: Path, sample_repo: Path):
    dest = tmp_path / "full"
    with patch.object(git_parser.Repo, "clone_from") as mock_clone:
        git_parser.clone_repo(str(sample_repo), dest)
    _, kwargs = mock_clone.call_args
    assert "depth" not in kwargs
