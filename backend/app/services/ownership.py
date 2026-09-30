"""Semantic code ownership via embeddings (Qdrant), intent-weighted."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Owner:
    login: str
    score: float
    evidence: list[str]


def semantic_owners(repo_id: str, path: str) -> list[Owner]:
    """Who truly understands this code — not git blame. Week 2 (days 13-14)."""
    raise NotImplementedError
