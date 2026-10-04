"""Merge-conflict prediction via AST overlap analysis (Tree-sitter).

Two branches are compared against their merge-base: for every file
changed on *both* sides, Tree-sitter extracts the named symbols
(functions, classes, methods) and each side's changed lines are mapped
to the symbols they touch. Symbols touched on both sides are the ones
a merge will fight over.
"""

from __future__ import annotations

import importlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError, NoSuchPathError

#: extension -> (grammar package, language factory attr)
_LANGS = {
    ".py": ("tree_sitter_python", "language"),
    ".js": ("tree_sitter_javascript", "language"),
    ".jsx": ("tree_sitter_javascript", "language"),
    ".mjs": ("tree_sitter_javascript", "language"),
    ".cjs": ("tree_sitter_javascript", "language"),
    ".ts": ("tree_sitter_typescript", "language_typescript"),
    ".mts": ("tree_sitter_typescript", "language_typescript"),
    ".cts": ("tree_sitter_typescript", "language_typescript"),
    ".tsx": ("tree_sitter_typescript", "language_tsx"),
}

#: AST node types that introduce a named symbol.
_SYMBOL_NODES = {
    "function_definition",  # python
    "class_definition",  # python
    "function_declaration",  # js/ts
    "class_declaration",  # js/ts
    "method_definition",  # js/ts
    "interface_declaration",  # ts
}

_NAME_NODES = {
    "identifier",
    "property_identifier",
    "private_property_identifier",
    "type_identifier",
}

_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")

_parsers: dict[str, object] = {}


@dataclass
class Symbol:
    name: str  # qualified, e.g. "Handler.handle"
    kind: str  # function | method | class | interface
    start_line: int  # 1-based, inclusive
    end_line: int


@dataclass
class FileOverlap:
    path: str
    symbols: list[str]
    shared_lines: int


@dataclass
class ConflictPrediction:
    base: str
    head: str
    probability: float  # 0.0 - 1.0
    overlapping_symbols: list[str]  # "path:Symbol"
    explanation: str
    overlapping_files: list[FileOverlap] = field(default_factory=list)


def _parser_for(path: str):
    """Tree-sitter parser for a file, or None when the language is
    unsupported or its grammar package isn't installed."""
    ext = Path(path).suffix.lower()
    if ext not in _LANGS:
        return None
    if ext not in _parsers:
        package, attr = _LANGS[ext]
        try:
            module = importlib.import_module(package)
        except ImportError:
            return None
        from tree_sitter import Language, Parser

        _parsers[ext] = Parser(Language(getattr(module, attr)()))
    return _parsers.get(ext)


def extract_symbols(source: bytes, path: str) -> list[Symbol]:
    """Named symbols in a source file. Returns [] for unsupported
    languages — overlap then falls back to shared changed lines."""
    parser = _parser_for(path)
    if parser is None:
        return []
    symbols: list[Symbol] = []

    def name_of(node) -> str | None:
        for child in node.children:
            if child.type in _NAME_NODES:
                return source[child.start_byte:child.end_byte].decode(
                    "utf-8", errors="replace")
        return None

    def walk(node, prefix: str = "") -> None:
        if node.type in _SYMBOL_NODES:
            name = name_of(node)
            if name is None:
                return
            kind = (
                "class" if "class" in node.type
                else "method" if node.type == "method_definition"
                else "interface" if node.type == "interface_declaration"
                else "function"
            )
            qualified = f"{prefix}.{name}" if prefix else name
            symbols.append(Symbol(
                name=qualified, kind=kind,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
            ))
            prefix = qualified  # nest methods under their class
        elif node.type == "variable_declarator":
            # const handler = () => {} — name the arrow/function binding,
            # don't descend into its body.
            value = next(
                (c for c in node.children
                 if c.type in ("arrow_function", "function_expression")),
                None,
            )
            ident = next(
                (c for c in node.children if c.type == "identifier"), None)
            if value is not None and ident is not None:
                name = source[ident.start_byte:ident.end_byte].decode(
                    "utf-8", errors="replace")
                symbols.append(Symbol(
                    name=f"{prefix}.{name}" if prefix else name,
                    kind="function",
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                ))
                return
        for child in node.children:
            walk(child, prefix)

    walk(parser.parse(source).root_node)
    return symbols


def changed_lines(repo: Repo, rev_a: str, rev_b: str, path: str,
                  cap: int = 50_000) -> set[int]:
    """1-based line numbers changed in `path` between two revisions
    (the + side of the diff)."""
    raw = repo.git.diff("-U0", rev_a, rev_b, "--", path)
    lines: set[int] = set()
    for line in raw.splitlines():
        match = _HUNK_RE.match(line)
        if not match:
            continue
        start, count = int(match.group(1)), int(match.group(2) or 1)
        for n in range(start, start + count):
            lines.add(n)
            if len(lines) >= cap:
                return lines
    return lines


def touched_symbols(symbols: list[Symbol], lines: set[int]) -> set[str]:
    """Names of symbols whose line range contains any changed line."""
    return {
        s.name for s in symbols
        if any(s.start_line <= n <= s.end_line for n in lines)
    }


def _blob(repo: Repo, rev: str, path: str) -> bytes | None:
    try:
        return repo.git.show(f"{rev}:{path}").encode("utf-8", "replace")
    except GitCommandError:
        return None  # file added/deleted on this side — nothing to parse


def _changed_files(repo: Repo, rev_a: str, rev_b: str) -> set[str]:
    raw = repo.git.diff("--name-only", "-z", rev_a, rev_b, "--")
    return {p for p in raw.split("\0") if p}


def predict_conflict(repo_path: str | Path, base: str, head: str) -> ConflictPrediction:
    """Probability that merging `head` into `base` hits a conflict.

    Compares each side against the merge-base: files touched by both,
    symbols touched by both, and exact shared changed lines feed a
    saturating score p = w / (1 + w).
    """
    try:
        repo = Repo(str(repo_path))
    except (InvalidGitRepositoryError, NoSuchPathError) as exc:
        raise ValueError(f"not a git repository: {repo_path}") from exc

    try:
        base_sha = repo.git.rev_parse("--verify", base).strip()
        head_sha = repo.git.rev_parse("--verify", head).strip()
    except GitCommandError as exc:
        detail = (exc.stderr or "").strip().splitlines()
        raise ValueError(
            f"unknown branch or ref: {detail[0] if detail else base!r}/{head!r}"
        ) from exc

    merge_base = repo.git.merge_base(base_sha, head_sha).strip().split()[0]

    base_files = _changed_files(repo, merge_base, base_sha)
    head_files = _changed_files(repo, merge_base, head_sha)
    common = sorted(base_files & head_files)

    overlaps: list[FileOverlap] = []
    weight = 0.0
    for path in common:
        base_blob, head_blob = _blob(repo, base_sha, path), _blob(repo, head_sha, path)
        if base_blob is None or head_blob is None:
            continue  # added on one side, deleted on the other — git merges that fine
        base_syms = touched_symbols(
            extract_symbols(base_blob, path),
            changed_lines(repo, merge_base, base_sha, path))
        head_syms = touched_symbols(
            extract_symbols(head_blob, path),
            changed_lines(repo, merge_base, head_sha, path))
        sym_overlap = sorted(base_syms & head_syms)
        shared = changed_lines(repo, merge_base, base_sha, path) & changed_lines(
            repo, merge_base, head_sha, path)
        # Symbol overlap carries the signal; raw shared lines catch
        # languages without a grammar and edits outside any symbol.
        sym_union = base_syms | head_syms
        weight += len(sym_overlap) / max(1, len(sym_union))
        weight += min(1.0, len(shared) / 10)
        if sym_overlap or shared:
            overlaps.append(FileOverlap(
                path=path, symbols=sym_overlap, shared_lines=len(shared)))

    probability = round(weight / (1 + weight), 3) if weight else 0.0
    flat = sorted(f"{f.path}:{s}" for f in overlaps for s in f.symbols)

    if not common:
        explanation = (
            f"{base} and {head} touch no common files — the merge should be clean.")
    elif not overlaps:
        explanation = (
            f"{len(common)} file(s) touched by both branches, but different "
            f"symbols — conflict risk is low.")
    else:
        names = ", ".join(f"`{s}`" for s in flat[:5])
        more = f" (+{len(flat) - 5} more)" if len(flat) > 5 else ""
        explanation = (
            f"Both branches edit {names}{more} — expect a merge conflict there.")

    return ConflictPrediction(
        base=base, head=head, probability=probability,
        overlapping_symbols=flat, explanation=explanation,
        overlapping_files=overlaps,
    )
