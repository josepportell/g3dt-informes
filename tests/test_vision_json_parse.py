"""
F2 (2026-08) — Anthropic vision: JSON-only prompt + robust reply parser.

AUDIT-PROD-2026-08 §T1.1: 29/29 Anthropic DPSH failures were
``Expecting value: line 1 column 1 (char 0)`` after a 200 OK — Claude answered
"Here is the extracted data:\n{...}" and ``json.loads(text)`` choked on the
prose. ``_parse_json_response`` is pure (no network) and shared by the three
providers; ``_call_anthropic_vision`` is tested with a mocked client.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from web.vision_groq import _parse_json_response, _call_anthropic_vision  # noqa: E402
from automation.validation.prompts import EXTRACTION_SYSTEM_PROMPT  # noqa: E402


# ---------------------------------------------------------------------------
# _parse_json_response
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    '{"a":1}',
    '  \n{"a": 1}\n  ',
    'Here is the data:\n{"a":1}',
    '```json\n{"a":1}\n```',
    '```\n{"a":1}\n```',
    'Sure!\n```json\n{"a": 1}\n```\nDone.',
    'Here is the extracted data:\n\n{"a": 1}\n\nLet me know if you need anything else.',
    'JSON:\n{"a": 1}',
])
def test_parse_json_response_ok(text):
    assert _parse_json_response(text) == {"a": 1}


def test_parse_json_response_truncated_raises_with_preview():
    truncated = 'Here you go:\n{"dpsh_tests": [{"test_id": "P-1", "readings": [{"depth_m": 0.2'
    with pytest.raises(json.JSONDecodeError) as ei:
        _parse_json_response(truncated)
    # the message must carry what the model actually said (first 200 chars)
    assert "Here you go" in str(ei.value)
    assert "dpsh_tests" in str(ei.value)


@pytest.mark.parametrize("text", ["", "   ", "No JSON here.", "[1, 2, 3]", "null"])
def test_parse_json_response_no_object_raises(text):
    with pytest.raises(json.JSONDecodeError):
        _parse_json_response(text)


def test_parse_json_response_preview_capped_at_200():
    text = "x" * 5000
    with pytest.raises(json.JSONDecodeError) as ei:
        _parse_json_response(text)
    assert len(str(ei.value)) < 400


# ---------------------------------------------------------------------------
# EXTRACTION_SYSTEM_PROMPT demands JSON only (affects all 3 providers)
# ---------------------------------------------------------------------------

def test_system_prompt_demands_json_only():
    tail = EXTRACTION_SYSTEM_PROMPT.strip().splitlines()[-2:]
    tail_text = " ".join(tail).lower()
    assert "json object" in tail_text
    assert "no markdown fences" in tail_text or "no preamble" in tail_text


# ---------------------------------------------------------------------------
# _call_anthropic_vision with a mocked client
# ---------------------------------------------------------------------------

def _fake_client(reply_text: str, stop_reason: str = "end_turn", calls: list | None = None):
    def create(**kwargs):
        if calls is not None:
            calls.append(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=reply_text)],
            stop_reason=stop_reason,
            usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        )
    return SimpleNamespace(messages=SimpleNamespace(create=create))


def test_anthropic_vision_prose_before_json(monkeypatch):
    import automation.llm_client as llm_client

    calls: list = []
    monkeypatch.setattr(llm_client, "get_anthropic_client",
                        lambda: _fake_client('Here you go:\n{"tests": []}', calls=calls))
    monkeypatch.setattr(llm_client, "get_cc_model", lambda: "claude-test")

    out = _call_anthropic_vision("extract", ["aGVsbG8="], "sys", max_tokens=1234)
    assert out == {"tests": []}
    assert len(calls) == 1
    kw = calls[0]
    assert kw["max_tokens"] == 1234
    # No assistant prefill: rejected (HTTP 400) on the claude-*-4-6 family.
    assert [m["role"] for m in kw["messages"]] == ["user"]


def test_anthropic_vision_unparseable_logs_reply_and_returns_none(monkeypatch, caplog):
    import automation.llm_client as llm_client

    monkeypatch.setattr(llm_client, "get_anthropic_client",
                        lambda: _fake_client("I cannot read this image.", stop_reason="end_turn"))
    monkeypatch.setattr(llm_client, "get_cc_model", lambda: "claude-test")

    with caplog.at_level("WARNING", logger="web.vision_groq"):
        out = _call_anthropic_vision("extract", ["aGVsbG8="], "sys")
    assert out is None
    msgs = " ".join(r.getMessage() for r in caplog.records)
    assert "stop_reason=end_turn" in msgs
    assert "I cannot read this image." in msgs
