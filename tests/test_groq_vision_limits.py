"""
F4 (2026-08) — Groq vision: ≤5 images per call, real backoff on 429, and a
per-opening rate-limit budget in concept_scout.vision_probe.

AUDIT-PROD-2026-08 §T1/T3: 27 × "Too many images provided" (model accepts 5),
320 × HTTP 429 answered with a fixed 5 s sleep (14 min of waiting in 14 days).
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from automation import config  # noqa: E402
from web import vision_groq as vg  # noqa: E402


class _Resp:
    def __init__(self, status=200, payload=None, text="", headers=None):
        self.status_code = status
        self._payload = payload
        self.text = text
        self.headers = headers or {}

    def json(self):
        return self._payload


def _chat(content: str) -> dict:
    return {"choices": [{"message": {"content": content}, "finish_reason": "stop"}],
            "usage": {}}


@pytest.fixture
def http(monkeypatch):
    rec = SimpleNamespace(calls=[], sleeps=[], queue=[])

    def post(self, url, json=None, headers=None, **kw):
        rec.calls.append(json)
        return rec.queue.pop(0)

    monkeypatch.setattr(httpx.Client, "post", post)
    monkeypatch.setattr(vg.time, "sleep", lambda s: rec.sleeps.append(s))
    monkeypatch.setattr(config, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-key")
    return rec


# ---------------------------------------------------------------------------
# image cap
# ---------------------------------------------------------------------------

def test_groq_more_than_5_images_sends_nothing(http):
    assert vg.GROQ_MAX_IMAGES == 5
    out = vg._call_groq_vision("p", ["img"] * 6, "sys")
    assert out is None
    assert http.calls == []


def test_groq_exactly_5_images_is_sent(http):
    http.queue[:] = [_Resp(200, _chat('{"ok": 1}'))]
    assert vg._call_groq_vision("p", ["img"] * 5, "sys") == {"ok": 1}
    assert len(http.calls) == 1


# ---------------------------------------------------------------------------
# 429 backoff
# ---------------------------------------------------------------------------

def test_groq_429_honours_retry_after(http):
    http.queue[:] = [
        _Resp(429, text="rate", headers={"retry-after": "1"}),
        _Resp(200, _chat('{"ok": 1}')),
    ]
    before = vg.rate_limit_count()
    assert vg._call_groq_vision("p", ["img"], "sys") == {"ok": 1}
    assert len(http.sleeps) == 1 and 1.0 <= http.sleeps[0] <= 2.0
    assert vg.rate_limit_count() == before + 1


def test_groq_429_exponential_backoff_without_header(http):
    http.queue[:] = [_Resp(429), _Resp(429), _Resp(200, _chat('{"ok": 1}'))]
    assert vg._call_groq_vision("p", ["img"], "sys", max_retries=3) == {"ok": 1}
    assert len(http.sleeps) == 2
    assert 2.0 <= http.sleeps[0] <= 3.0   # 2^1 + jitter
    assert 4.0 <= http.sleeps[1] <= 5.0   # 2^2 + jitter


def test_groq_429_gives_up_after_max_retries(http):
    http.queue[:] = [_Resp(429)] * 3
    assert vg._call_groq_vision("p", ["img"], "sys", max_retries=3) is None
    assert len(http.calls) == 3 and len(http.sleeps) == 2


def test_openai_429_honours_retry_after(http):
    http.queue[:] = [
        _Resp(429, headers={"retry-after": "1"}),
        _Resp(200, _chat('{"ok": 1}')),
    ]
    assert vg._call_openai_vision("p", ["img"], "sys") == {"ok": 1}
    assert len(http.sleeps) == 1 and 1.0 <= http.sleeps[0] <= 2.0


def test_retry_after_is_capped():
    assert vg._retry_delay(_Resp(429, headers={"retry-after": "3600"}), 1) == vg.RETRY_AFTER_MAX_S
    assert vg._retry_delay(_Resp(429, headers={"retry-after": "garbage"}), 1) >= 2.0


# ---------------------------------------------------------------------------
# per-opening 429 budget in vision_probe
# ---------------------------------------------------------------------------

def _entries(tmp_path: Path, n: int):
    from automation.concept_scout.models import FileEntry

    out = []
    for i in range(n):
        f = tmp_path / "ANEXOS" / f"foto_{i}.png"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"\x89PNG\r\n\x1a\n" + bytes([i]))
        out.append(FileEntry(path=f"ANEXOS/foto_{i}.png", type="image",
                             size_kb=1, text_extractable=False))
    return out


def test_probe_stops_after_rate_limit_budget(tmp_path, monkeypatch):
    from automation.concept_scout import vision_probe

    monkeypatch.setattr(vision_probe, "GROQ_PROBE_429_BUDGET", 3)
    entries = _entries(tmp_path, 8)
    calls: list[str] = []

    def fake_run(file_path: Path):
        calls.append(file_path.name)
        vg._note_rate_limit()   # every probe hits a 429 and fails
        return None

    monkeypatch.setattr(vision_probe, "_run_probe", fake_run)
    vision_probe.probe_unreadable_files(entries, tmp_path)

    assert len(calls) == 3, f"probing must stop at the budget; calls={calls}"
    notes = [fe.notes for fe in entries]
    assert all(n == vision_probe._UNPROBED_NOTE for n in notes[2:]), notes
    assert notes[:2] == ["", ""]


def test_probe_budget_not_triggered_without_429(tmp_path, monkeypatch):
    from automation.concept_scout import vision_probe

    monkeypatch.setattr(vision_probe, "GROQ_PROBE_429_BUDGET", 1)
    entries = _entries(tmp_path, 4)
    calls: list[str] = []

    def fake_run(file_path: Path):
        calls.append(file_path.name)
        return {"document_type": "site_photo", "document_description": "x", "concepts_found": []}

    monkeypatch.setattr(vision_probe, "_run_probe", fake_run)
    vision_probe.probe_unreadable_files(entries, tmp_path)
    assert len(calls) == 4
    assert all(fe.notes != vision_probe._UNPROBED_NOTE for fe in entries)


def test_probe_budget_disabled_with_zero(tmp_path, monkeypatch):
    from automation.concept_scout import vision_probe

    monkeypatch.setattr(vision_probe, "GROQ_PROBE_429_BUDGET", 0)
    entries = _entries(tmp_path, 4)
    calls: list[str] = []

    def fake_run(file_path: Path):
        calls.append(file_path.name)
        vg._note_rate_limit()
        return None

    monkeypatch.setattr(vision_probe, "_run_probe", fake_run)
    vision_probe.probe_unreadable_files(entries, tmp_path)
    assert len(calls) == 4
