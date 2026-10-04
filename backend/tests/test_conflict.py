"""Unit tests for conflict prediction (AST overlap between branches)."""

import subprocess
from pathlib import Path

import pytest

from app.services import conflict


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture()
def branched_repo(tmp_path: Path) -> Path:
    """main + three branches: a/b edit the same function, c edits another."""
    repo = tmp_path / "branched"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    base = "def foo():\n    return 1\n\ndef bar():\n    return 2\n"
    (repo / "app.py").write_text(base)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    for branch, body in [
        ("side-a", base.replace("return 1", "return 10")),
        ("side-b", base.replace("return 1", "return 99")),
        ("side-c", base.replace("return 2", "return 20")),
    ]:
        _git(repo, "checkout", "-b", branch, "main")
        (repo / "app.py").write_text(body)
        _git(repo, "commit", "-am", f"{branch} edits")
    _git(repo, "checkout", "main")
    return repo


def test_same_function_overlap_scores_high(branched_repo: Path):
    result = conflict.predict_conflict(branched_repo, "side-a", "side-b")
    assert result.probability > 0.5
    assert result.overlapping_symbols == ["app.py:foo"]
    assert "foo" in result.explanation


def test_different_functions_score_zero(branched_repo: Path):
    result = conflict.predict_conflict(branched_repo, "side-a", "side-c")
    assert result.probability == 0.0
    assert result.overlapping_symbols == []
    assert "low" in result.explanation


def test_same_branch_is_clean(branched_repo: Path):
    result = conflict.predict_conflict(branched_repo, "side-a", "side-a")
    assert result.probability == 0.0


def test_unknown_ref_raises_value_error(branched_repo: Path):
    with pytest.raises(ValueError, match="unknown branch or ref"):
        conflict.predict_conflict(branched_repo, "side-a", "no-such-branch")


def test_not_a_repo_raises_value_error(tmp_path: Path):
    with pytest.raises(ValueError, match="not a git repository"):
        conflict.predict_conflict(tmp_path, "a", "b")


def test_extract_symbols_python_nests_methods():
    src = b"class A:\n    def m(self):\n        pass\n\ndef f():\n    pass\n"
    symbols = {s.name: s.kind for s in conflict.extract_symbols(src, "x.py")}
    assert symbols == {"A": "class", "A.m": "method", "f": "function"}


def test_extract_symbols_javascript_arrow_binding():
    src = b"function f() {}\nconst g = () => {};\n"
    symbols = {s.name: s.kind for s in conflict.extract_symbols(src, "x.js")}
    assert symbols == {"f": "function", "g": "function"}


def test_extract_symbols_unsupported_language_returns_empty():
    assert conflict.extract_symbols(b"hello", "notes.txt") == []


def test_untracked_extension_falls_back_to_shared_lines(tmp_path: Path):
    """No grammar for .txt: identical-line edits still raise the score."""
    repo = tmp_path / "txt"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / "notes.txt").write_text("line1\nline2\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    for branch, text in [("t-a", "line1\nline2 edited by a\n"),
                         ("t-b", "line1\nline2 edited by b\n")]:
        _git(repo, "checkout", "-b", branch, "main")
        (repo / "notes.txt").write_text(text)
        _git(repo, "commit", "-am", branch)
    result = conflict.predict_conflict(repo, "t-a", "t-b")
    assert result.probability > 0
    assert result.overlapping_files[0].shared_lines > 0
