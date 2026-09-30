"""Merge-conflict prediction via AST overlap analysis (Tree-sitter)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ConflictPrediction:
    base: str
    head: str
    probability: float  # 0.0 - 1.0
    overlapping_symbols: list[str]
    explanation: str


def predict_conflict(repo_path: str, base: str, head: str) -> ConflictPrediction:
    """Analyze overlapping AST changes between branches. Week 2 (days 11-12)."""
    raise NotImplementedError
