"""Unit tests for conflict prediction (AST overlap between branches)."""

import importlib
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


def test_unrelated_histories_raise_value_error(tmp_path: Path):
    # Orphan branches share no merge-base: git merge-base exits nonzero,
    # which must surface as a ValueError (404 upstream), not a 500.
    repo = tmp_path / "orphans"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / "a.py").write_text("x = 1\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "main root")
    _git(repo, "checkout", "--orphan", "orphan")
    _git(repo, "rm", "-rf", ".")
    (repo / "b.py").write_text("y = 2\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "orphan root")
    with pytest.raises(ValueError, match="no common history"):
        conflict.predict_conflict(repo, "main", "orphan")


def test_option_like_ref_rejected(branched_repo: Path):
    """Refs starting with '-' would be parsed as git options, not refs."""
    with pytest.raises(ValueError, match="invalid ref"):
        conflict.predict_conflict(branched_repo, "--verify", "main")
    with pytest.raises(ValueError, match="invalid ref"):
        conflict.predict_conflict(branched_repo, "main", "-h")


def test_ref_with_forbidden_chars_rejected(branched_repo: Path):
    with pytest.raises(ValueError, match="invalid ref"):
        conflict.predict_conflict(branched_repo, "main", "feat/my branch")


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


def test_extract_symbols_anonymous_default_export_skipped():
    """`export default function() {}` has no name child: the parser must
    silently skip it, not crash or mis-attribute the symbol."""
    assert conflict.extract_symbols(b"export default function() {}", "a.js") == []


def test_extract_symbols_computed_method_name_skipped():
    """A computed method name (`["x"]() {}`) has no name child either:
    the method is skipped while the enclosing class is still recorded."""
    symbols = {s.name: s.kind
               for s in conflict.extract_symbols(
                   b"class A {\n    [\"x\"]() {}\n}\n", "a.js")}
    assert symbols == {"A": "class"}


def test_parser_for_missing_grammar_returns_none(monkeypatch):
    """A grammar package that isn't installed degrades to None (and the
    caller falls back to shared changed lines) instead of raising."""
    monkeypatch.setattr(conflict, "_parsers", {})

    def _boom(name, *args, **kwargs):
        raise ImportError("no grammar installed")

    monkeypatch.setattr(importlib, "import_module", _boom)
    assert conflict._parser_for("a.py") is None


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


def test_deleted_on_one_side_is_not_a_conflict(tmp_path: Path):
    """File deleted on one side and edited on the other: git merges that
    fine, so the predictor must return a prediction, not raise."""
    repo = tmp_path / "del"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / "app.py").write_text("def foo():\n    return 1\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _git(repo, "checkout", "-b", "del")
    (repo / "app.py").unlink()
    _git(repo, "commit", "-am", "delete app.py")
    _git(repo, "checkout", "-b", "edit", "main")
    (repo / "app.py").write_text("def foo():\n    return 2\n")
    _git(repo, "commit", "-am", "edit app.py")
    result = conflict.predict_conflict(repo, "del", "edit")
    assert result.probability == 0.0
    assert result.overlapping_symbols == []


def test_changed_lines_respects_cap(tmp_path: Path):
    """The 50,000-line safety cap: a diff wider than the cap returns at
    most `cap` lines instead of the whole file."""
    repo = tmp_path / "cap"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / "f.py").write_text("".join(f"line{i}\n" for i in range(10)))
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _git(repo, "checkout", "-b", "wide")
    (repo / "f.py").write_text("".join(f"changed{i}\n" for i in range(10)))
    _git(repo, "commit", "-am", "rewrite all lines")
    from git import Repo

    lines = conflict.changed_lines(Repo(str(repo)), "main", "wide", "f.py",
                                   cap=5)
    assert len(lines) == 5
    assert lines == {1, 2, 3, 4, 5}
