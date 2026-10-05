"""Unit tests for the code-chunk embedding index (Qdrant, local mode)."""

import math
from pathlib import Path

from app.services import embeddings


def test_embed_text_is_deterministic_and_normalized():
    a = embeddings.embed_text("def foo(): return bar")
    b = embeddings.embed_text("def foo(): return bar")
    assert a == b
    assert len(a) == embeddings.EMBED_DIM
    assert math.isclose(sum(v * v for v in a), 1.0, rel_tol=1e-6)


def test_embed_text_distinguishes_content():
    a = embeddings.embed_text("def authenticate_user(password): verify hash")
    b = embeddings.embed_text("def render_chart(canvas): draw axes labels")
    c = embeddings.embed_text("def authenticate_user(password): verify hash!")
    dot = lambda x, y: sum(i * j for i, j in zip(x, y))
    assert dot(a, c) > dot(a, b)


def test_chunks_for_file_extracts_symbols():
    src = b"class Repo:\n    def clone(self):\n        pass\n\ndef helper():\n    pass\n"
    chunks = embeddings.chunks_for_file(src, "git.py")
    names = {c.symbol: c.kind for c in chunks}
    assert names == {"Repo": "class", "Repo.clone": "method", "helper": "function"}
    assert all("Repo.clone" in c.text or c.symbol != "Repo.clone" for c in chunks)
    clone_chunk = next(c for c in chunks if c.symbol == "Repo.clone")
    assert "def clone" in clone_chunk.text


def test_chunks_for_file_falls_back_for_unknown_language():
    chunks = embeddings.chunks_for_file(b"line1\nline2\n", "notes.txt")
    assert len(chunks) == 1
    assert chunks[0].kind == "file"


def test_chunks_for_file_skips_binary():
    assert embeddings.chunks_for_file(b"\x00\x01\x02\xff", "blob.bin") == []


def _write_repo(root: Path) -> Path:
    repo = root / "code"
    repo.mkdir()
    (repo / "auth.py").write_text(
        "def authenticate_user(password):\n"
        "    return verify_hash(password)\n"
        "\ndef verify_hash(password):\n"
        "    return True\n"
    )
    (repo / "charts.py").write_text(
        "def render_chart(canvas):\n"
        "    draw_axes(canvas)\n"
    )
    return repo


def test_index_and_similar_chunks_roundtrip(tmp_path: Path):
    repo = _write_repo(tmp_path)
    store = tmp_path / "qdrant"
    n = embeddings.index_file(repo, "repo-1", "auth.py", storage_dir=store)
    assert n == 2  # two functions
    n = embeddings.index_file(repo, "repo-1", "charts.py", storage_dir=store)
    assert n == 1

    hits = embeddings.similar_chunks(
        "repo-1", "def login(password): check credentials",
        top_k=3, storage_dir=store)
    assert hits
    # auth.py's password-checking code outranks the chart renderer.
    assert hits[0].path == "auth.py"

    # Queries are scoped per repo.
    assert embeddings.similar_chunks(
        "repo-2", "def login(password)", storage_dir=store) == []


def test_similar_chunks_excludes_self(tmp_path: Path):
    repo = _write_repo(tmp_path)
    store = tmp_path / "qdrant"
    embeddings.index_file(repo, "repo-1", "auth.py", storage_dir=store)
    embeddings.index_file(repo, "repo-1", "charts.py", storage_dir=store)
    text = (repo / "auth.py").read_text()
    hits = embeddings.similar_chunks(
        "repo-1", text, top_k=5, exclude_path="auth.py", storage_dir=store)
    assert all(h.path != "auth.py" for h in hits)
    assert {h.path for h in hits} == {"charts.py"}


def test_index_file_idempotent_and_missing(tmp_path: Path):
    repo = _write_repo(tmp_path)
    store = tmp_path / "qdrant"
    first = embeddings.index_file(repo, "repo-1", "auth.py", storage_dir=store)
    second = embeddings.index_file(repo, "repo-1", "auth.py", storage_dir=store)
    assert first == second == 2  # upsert, no duplicates
    assert embeddings.index_file(repo, "repo-1", "nope.py",
                                 storage_dir=store) == 0


def test_index_scope_bounds_files(tmp_path: Path):
    repo = _write_repo(tmp_path)
    store = tmp_path / "qdrant"
    total = embeddings.index_scope(
        repo, "repo-1", ["auth.py", "charts.py", "missing.py"],
        max_files=1, storage_dir=store)
    assert total == 2  # only the first file indexed
