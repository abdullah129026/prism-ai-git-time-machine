"""Code-chunk embeddings in Qdrant.

Chunks are Tree-sitter symbols (reuses conflict.extract_symbols), so one
chunk is one function/class/method. Vectors are deterministic hashed
token embeddings: no API key, no model download, works offline and in CI.

Qdrant runs in local mode (no server): the index lives under
`data_dir/qdrant` and survives restarts.
"""

from __future__ import annotations

import hashlib
import math
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.services import conflict as conflict_service

#: Vector width. Hashed, so wider only buys fewer collisions.
EMBED_DIM = 256

COLLECTION = "prism_chunks"

#: A file this big is skipped — chunking it would be noise anyway.
MAX_FILE_BYTES = 200_000

#: Lines of a symbol's body kept in its chunk text.
CHUNK_BODY_LINES = 40

_TOKEN_RE = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*")

_clients: dict[str, QdrantClient] = {}


@dataclass
class CodeChunk:
    path: str
    symbol: str  # qualified name, or "file" for whole-file chunks
    kind: str  # function | method | class | interface | file
    text: str


@dataclass
class ChunkHit:
    path: str
    symbol: str
    kind: str
    score: float


def embed_text(text: str, dim: int = EMBED_DIM) -> list[float]:
    """Deterministic hashed token embedding, L2-normalized.

    Sublinear term frequency over hashed token buckets, so repeated
    identifiers don't dominate. Cosine-ready.
    """
    # ponytail: hashed TF beats a learned encoder here — no dependency,
    # no key, offline. Swap in fastembed/sentence-transformers when
    # retrieval quality (not plumbing) becomes the bottleneck.
    buckets = [0.0] * dim
    for token in _TOKEN_RE.findall(text.lower()):
        digest = hashlib.md5(token.encode(), usedforsecurity=False).digest()
        buckets[int.from_bytes(digest[:4], "little") % dim] += 1.0
    tf = [(1.0 + math.log(c)) if c else 0.0 for c in buckets]
    norm = math.sqrt(sum(v * v for v in tf)) or 1.0
    return [v / norm for v in tf]


def chunks_for_file(source: bytes, rel_path: str) -> list[CodeChunk]:
    """One chunk per Tree-sitter symbol; whole-file chunk when the
    language has no grammar."""
    try:
        text = source.decode("utf-8")
    except UnicodeDecodeError:
        return []  # binary — nothing to embed
    lines = text.splitlines()

    symbols = conflict_service.extract_symbols(source, rel_path)
    chunks = []
    for sym in symbols:
        body = lines[sym.start_line - 1:sym.start_line - 1 + CHUNK_BODY_LINES]
        chunks.append(CodeChunk(
            path=rel_path,
            symbol=sym.name,
            kind=sym.kind,
            text=f"{sym.kind} {sym.name}\n" + "\n".join(body),
        ))
    if not chunks:
        chunks.append(CodeChunk(
            path=rel_path, symbol="file", kind="file",
            text="\n".join(lines[:CHUNK_BODY_LINES * 5]),
        ))
    return chunks


def client_for(storage_dir: Path | None = None) -> QdrantClient:
    """Qdrant client in local mode; one per storage dir (cached)."""
    from app.config import get_settings

    path = str(storage_dir or get_settings().data_dir / "qdrant")
    client = _clients.get(path)
    if client is None:
        client = QdrantClient(path=path)
        if not client.collection_exists(COLLECTION):
            client.create_collection(
                COLLECTION,
                vectors_config=VectorParams(
                    size=EMBED_DIM, distance=Distance.COSINE),
            )
        _clients[path] = client
    return client


def _point_id(repo_id: str, chunk: CodeChunk) -> str:
    # Qdrant string ids must be UUIDs — uuid5 keeps them deterministic.
    return str(uuid.uuid5(
        uuid.NAMESPACE_URL, f"{repo_id}\x00{chunk.path}\x00{chunk.symbol}"))


def index_file(repo_path: str | Path, repo_id: str, rel_path: str,
               storage_dir: Path | None = None) -> int:
    """Chunk + embed one file at its working-tree state, upsert into
    Qdrant. Idempotent (stable point ids). Returns chunk count; 0 when
    the file is missing, binary, or oversized."""
    full = Path(repo_path) / rel_path
    try:
        if not full.is_file() or full.stat().st_size > MAX_FILE_BYTES:
            return 0
        source = full.read_bytes()
    except OSError:
        return 0
    chunks = chunks_for_file(source, rel_path)
    if not chunks:
        return 0
    client = client_for(storage_dir)
    client.upsert(
        collection_name=COLLECTION,
        points=[
            PointStruct(
                id=_point_id(repo_id, chunk),
                vector=embed_text(chunk.text),
                payload={
                    "repo_id": repo_id,
                    "path": chunk.path,
                    "symbol": chunk.symbol,
                    "kind": chunk.kind,
                },
            )
            for chunk in chunks
        ],
    )
    return len(chunks)


def index_scope(repo_path: str | Path, repo_id: str, rel_paths: list[str],
                max_files: int = 50,
                storage_dir: Path | None = None) -> int:
    """Index up to `max_files` paths. Returns total chunks indexed."""
    return sum(
        index_file(repo_path, repo_id, p, storage_dir)
        for p in rel_paths[:max_files]
    )


def similar_chunks(repo_id: str, text: str, top_k: int = 5,
                   exclude_path: str | None = None,
                   storage_dir: Path | None = None) -> list[ChunkHit]:
    """Chunks in this repo most similar to `text` (cosine)."""
    client = client_for(storage_dir)
    result = client.query_points(
        collection_name=COLLECTION,
        query=embed_text(text),
        query_filter=Filter(must=[
            FieldCondition(key="repo_id", match=MatchValue(value=repo_id))
        ]),
        limit=top_k * 2 + 5,
    )
    hits = []
    for point in result.points:
        payload = point.payload or {}
        if exclude_path is not None and payload.get("path") == exclude_path:
            continue
        hits.append(ChunkHit(
            path=payload.get("path", ""),
            symbol=payload.get("symbol", ""),
            kind=payload.get("kind", ""),
            score=round(point.score, 3),
        ))
        if len(hits) >= top_k:
            break
    return hits
