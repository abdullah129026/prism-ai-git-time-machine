"""LLM intent engine: why was this changed? what bug? what risk? (Groq)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CommitIntent:
    sha: str
    why: str
    bug_fixed: str | None
    risk: str
    confidence: float


INTENT_SYSTEM_PROMPT = """\
You are a senior staff engineer reading a git commit.
Given the commit message and diff, explain:

1. WHY was this changed? (1-2 sentences, plain language)
2. WHAT BUG did it fix, if any? (or "none" — do not invent bugs)
3. WHAT RISK does it introduce? (regressions, perf, security — be specific)

Rules:
- Ground everything in the diff. Never invent context.
- If the intent is unclear, say so and give your best hypothesis labeled as such.
- Keep each field under 60 words.
"""


def generate_intent(sha: str, message: str, diff: str) -> CommitIntent:
    """Call Groq to generate intent for one commit. Week 1 (days 6-7)."""
    raise NotImplementedError
