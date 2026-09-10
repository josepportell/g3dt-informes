"""
F3 (2026-08) — max_tokens per vision type + truncation detection, no retries.

AUDIT-PROD-2026-08 §T1.2-3: flat max_tokens=4096 truncated every big DPSH
(4 penetros × 40 readings ≈ 4.8k tokens); the truncated JSON was then retried
2-3 × (~150 s each) and handed to the next provider with the same limit.
Rule: "never 3 × 150 s for the same error".
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from automation import config  # noqa: E402
from web import vision_groq as vg  # noqa: E402


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

class _Resp:
    def __init__(self, status=200, payload=None, text="", headers=None):
        self.status_code = status
        self._payload = payload
        self.text = text
        self.headers = headers or {}

    def json(self):
        return self._payload


def _chat(content: str, finish_reason: str = "stop") -> dict:
    return {
        "choices": [{"message": {"content": content}, "finish_reason": finish_reason}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
    }


@pytest.fixture
def http(monkeypatch):
    """Patch httpx.Client.post; returns a recorder with .calls and .sleeps."""
    rec = SimpleNamespace(calls=[], sleeps=[], queue=[])

    def post(self, url, json=None, headers=None, **kw):
        rec.calls.append({"url": url, "json": json})
        item = rec.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(httpx.Client, "post", post)
    monkeypatch.setattr(vg.time, "sleep", lambda s: rec.sleeps.append(s))
    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(config, "GROQ_API_KEY", "test-key")
    return rec


# ---------------------------------------------------------------------------
# budgets
# ---------------------------------------------------------------------------

def test_max_tokens_by_type():
    assert vg._max_tokens_for("dpsh") == 16384
    assert vg._max_tokens_for("projecte_arquitecte") == 8192
    assert vg._max_tokens_for("planol") == 4096
    assert vg._max_tokens_for("sondeig") == 4096


def test_max_tokens_clamped_to_provider_cap():
    # Groq qwen/qwen3.6-27b: max_completion_tokens 16384 (verified 2026-08-22)
    assert vg._max_tokens_for("dpsh", provider="groq") == 16384
    assert vg.PROVIDER_MAX_OUTPUT_TOKENS["openai"] == 32768
    assert min(32768, vg.PROVIDER_MAX_OUTPUT_TOKENS["groq"]) == 16384


# ---------------------------------------------------------------------------
# OpenAI / Groq: finish_reason=length → one call, raise, no sleep
# ---------------------------------------------------------------------------

def test_openai_length_is_single_call_no_retry(http):
    http.queue[:] = [_Resp(200, _chat('{"tests": [{"a": 1', "length"))]
    with pytest.raises(vg.VisionTruncated) as ei:
        vg._call_openai_vision("p", ["img"], "sys", max_tokens=4096)
    assert len(http.calls) == 1
    assert http.sleeps == []
    assert "max_tokens=4096" in str(ei.value)
    assert http.calls[0]["json"]["max_tokens"] == 4096


def test_groq_length_is_single_call_no_retry(http):
    http.queue[:] = [_Resp(200, _chat('{"tests": [{"a": 1', "length"))]
    with pytest.raises(vg.VisionTruncated):
        vg._call_groq_vision("p", ["img"], "sys", max_tokens=2048)
    assert len(http.calls) == 1
    assert http.sleeps == []


def test_openai_unparseable_reply_not_retried(http):
    http.queue[:] = [_Resp(200, _chat("not json at all", "stop"))]
    assert vg._call_openai_vision("p", ["img"], "sys") is None
    assert len(http.calls) == 1
    assert http.sleeps == []


def test_groq_unparseable_reply_not_retried(http):
    http.queue[:] = [_Resp(200, _chat("not json at all", "stop"))]
    assert vg._call_groq_vision("p", ["img"], "sys") is None
    assert len(http.calls) == 1
    assert http.sleeps == []


def test_openai_network_error_still_retried(http):
    http.queue[:] = [httpx.ConnectError("boom"), _Resp(200, _chat('{"ok": 1}'))]
    assert vg._call_openai_vision("p", ["img"], "sys") == {"ok": 1}
    assert len(http.calls) == 2
    assert http.sleeps == [2]


def test_openai_ok_reply_parsed(http):
    http.queue[:] = [_Resp(200, _chat('{"tests": []}', "stop"))]
    assert vg._call_openai_vision("p", ["img"], "sys") == {"tests": []}


# ---------------------------------------------------------------------------
# Anthropic: stop_reason=max_tokens → raise (not swallowed by the broad except)
# ---------------------------------------------------------------------------

def test_anthropic_max_tokens_raises(monkeypatch):
    import automation.llm_client as llm_client

    def create(**kwargs):
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text='{"tests": [{"a": 1')],
            stop_reason="max_tokens",
            usage=SimpleNamespace(input_tokens=1, output_tokens=4096),
        )

    monkeypatch.setattr(llm_client, "get_anthropic_client",
                        lambda: SimpleNamespace(messages=SimpleNamespace(create=create)))
    monkeypatch.setattr(llm_client, "get_cc_model", lambda: "claude-test")
    with pytest.raises(vg.VisionTruncated):
        vg._call_anthropic_vision("p", ["img"], "sys", max_tokens=4096)


# ---------------------------------------------------------------------------
# Backend chain
# ---------------------------------------------------------------------------

@pytest.fixture
def all_providers(monkeypatch):
    monkeypatch.setattr(config, "has_provider", lambda name: True)
    monkeypatch.setattr(vg, "log_vision_call", lambda **kw: None)


def test_chain_stops_on_truncation(all_providers):
    calls = []

    def first(prompt, images, system_prompt, max_tokens):
        calls.append(("first", max_tokens))
        raise vg.VisionTruncated("first truncated")

    def second(prompt, images, system_prompt, max_tokens):
        calls.append(("second", max_tokens))
        return {"never": True}

    call_map = {"anthropic": (first, "m1"), "openai": (second, "m2")}
    result, used = vg._call_backend_chain(
        ["anthropic", "openai"], call_map, "p", ["img"], "sys", 16384, "PENETROS.pdf", "dpsh",
    )
    assert result is None and used is None
    assert [c[0] for c in calls] == ["first"], "next provider must NOT be tried after truncation"


def test_chain_falls_through_on_none(all_providers):
    def first(prompt, images, system_prompt, max_tokens):
        return None

    def second(prompt, images, system_prompt, max_tokens):
        return {"ok": 1}

    call_map = {"anthropic": (first, "m1"), "openai": (second, "m2")}
    result, used = vg._call_backend_chain(
        ["anthropic", "openai"], call_map, "p", ["img"], "sys", 4096, "f.pdf", "planol",
    )
    assert result == {"ok": 1} and used == "openai"


def test_chain_clamps_budget_to_provider_cap(all_providers):
    seen = {}

    def groq(prompt, images, system_prompt, max_tokens):
        seen["groq"] = max_tokens
        return None

    def openai(prompt, images, system_prompt, max_tokens):
        seen["openai"] = max_tokens
        return {"ok": 1}

    call_map = {"groq": (groq, "q"), "openai": (openai, "o")}
    vg._call_backend_chain(["groq", "openai"], call_map, "p", ["img"], "sys", 32768, "f.pdf", "dpsh")
    assert seen == {"groq": 16384, "openai": 32768}
