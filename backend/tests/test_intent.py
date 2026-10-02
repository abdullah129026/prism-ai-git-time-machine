"""Unit tests for the intent engine (prompt, parsing, cache).

The Groq client is mocked — no network, no API key needed.
"""

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services import intent as intent_module
from app.services.intent import (
    CommitIntent,
    IntentUnavailableError,
    build_prompt,
    generate_intent,
)
from app.services.jobs import store


def _groq_response(content: str):
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


def _fake_client(payload: dict):
    completion = _groq_response(json.dumps(payload))
    completions = SimpleNamespace(create=lambda **kw: completion)
    chat = SimpleNamespace(completions=completions)
    return SimpleNamespace(chat=chat)


INTENT_PAYLOAD = {
    "why": "Bump the request timeout so slow upstream calls stop 500ing.",
    "bug_fixed": "Timeout errors on the /reports endpoint.",
    "risk": "Slow endpoints now hold connections 3x longer under load.",
    "confidence": 0.85,
}


def test_generate_intent_parses_json_response():
    with patch.object(intent_module, "_client",
                      return_value=_fake_client(INTENT_PAYLOAD)):
        result = generate_intent("abc123", "bump timeout", "+timeout=90")
    assert isinstance(result, CommitIntent)
    assert result.sha == "abc123"
    assert result.why == INTENT_PAYLOAD["why"]
    assert result.bug_fixed == INTENT_PAYLOAD["bug_fixed"]
    assert result.risk == INTENT_PAYLOAD["risk"]
    assert result.confidence == pytest.approx(0.85)


def test_generate_intent_normalizes_none_bug():
    payload = dict(INTENT_PAYLOAD, bug_fixed="none")
    with patch.object(intent_module, "_client",
                      return_value=_fake_client(payload)):
        result = generate_intent("abc123", "msg", "diff")
    assert result.bug_fixed is None


def test_generate_intent_rejects_empty_why():
    payload = dict(INTENT_PAYLOAD, why="  ")
    with patch.object(intent_module, "_client",
                      return_value=_fake_client(payload)):
        with pytest.raises(IntentUnavailableError):
            generate_intent("abc123", "msg", "diff")


def test_generate_intent_rejects_non_json():
    with patch.object(intent_module, "_client",
                      return_value=_groq_response("not json")):
        with pytest.raises(IntentUnavailableError):
            generate_intent("abc123", "msg", "diff")


def test_generate_intent_without_api_key_raises():
    with patch("app.config.get_settings",
               return_value=SimpleNamespace(groq_api_key="")):
        with pytest.raises(IntentUnavailableError, match="API key"):
            generate_intent("abc123", "msg", "diff")


def test_build_prompt_truncates_huge_diffs():
    big_diff = "x" * (intent_module.MAX_PROMPT_DIFF_CHARS + 100)
    messages = build_prompt("msg", big_diff)
    user_content = messages[1]["content"]
    assert len(user_content) < len(big_diff)
    assert "truncated" in user_content


def test_intent_cache_round_trip(tmp_path, monkeypatch):
    import app.services.jobs as jobs_module

    settings = SimpleNamespace(data_dir=tmp_path)
    monkeypatch.setattr(jobs_module, "get_settings", lambda: settings)
    intent = CommitIntent(sha="deadbeef", why="w", bug_fixed=None,
                          risk="r", confidence=0.7)
    assert store.get_intent("repo1", "deadbeef") is None
    store.set_intent("repo1", "deadbeef", intent)
    cached = store.get_intent("repo1", "deadbeef")
    assert cached is not None
    assert cached.why == "w"
    assert (tmp_path / "intents" / "repo1" / "deadbeef.json").exists()


def test_intent_from_dict_round_trip():
    intent = CommitIntent(sha="s", why="w", bug_fixed="b", risk="r",
                          confidence=0.5, generated_at="2026-10-02T00:00:00Z")
    restored = CommitIntent.from_dict(intent.to_dict())
    assert restored == intent
