"""Tests for AI pipeline Stage 4 — analysis.

The Anthropic client is always mocked in these tests. We never burn real credits.
"""

from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from automation.ai_pipeline.analysis import (
    Candidate,
    ProjectAnalysis,
    SourceAnalysis,
    SourceFailure,
    SourceInsight,
    SystemicFailure,
    _cache_path,
    _classify_error,
    analyze_project,
    load_analysis,
    save_analysis,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _noisy_png(size: int = 256) -> bytes:
    import random
    from PIL import Image
    random.seed(42)
    img = Image.new("RGB", (size, size))
    pixels = [(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
              for _ in range(size * size)]
    img.putdata(pixels)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _tiny_pdf_with_text(text: str) -> bytes:
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def _tiny_xlsx(sheet_name: str, rows: list[list]) -> bytes:
    import openpyxl
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet(sheet_name)
    for row in rows:
        ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _make_project(tmp_path: Path) -> Path:
    """Project with 2 sources that Stage 3 will convert to text artifacts."""
    p = tmp_path / "demo"
    p.mkdir()
    (p / "PENETROS.pdf").write_bytes(_tiny_pdf_with_text("Field sheet PENETROS. " * 10))
    (p / "DATA.xlsx").write_bytes(_tiny_xlsx("Main", [["a", "b"], [1, 2], [3, 4]]))
    return p


def _make_three_source_project(tmp_path: Path) -> Path:
    """Circuit-breaker tests need ≥3 sources (threshold is 3 consecutive failures)."""
    p = tmp_path / "demo3"
    p.mkdir()
    (p / "A.pdf").write_bytes(_tiny_pdf_with_text("Source A text. " * 10))
    (p / "B.pdf").write_bytes(_tiny_pdf_with_text("Source B text. " * 10))
    (p / "C.pdf").write_bytes(_tiny_pdf_with_text("Source C text. " * 10))
    return p


# ---------------------------------------------------------------------------
# Mock Anthropic client
# ---------------------------------------------------------------------------


class _MockUsage:
    def __init__(self, input_tokens=100, output_tokens=200):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _MockResponse:
    def __init__(self, tool_input: dict):
        self.content = [SimpleNamespace(
            type="tool_use",
            name="emit_analysis",
            input=tool_input,
        )]
        self.usage = _MockUsage()


class _MockMessages:
    def __init__(self, behavior):
        """behavior: callable that returns a response OR raises."""
        self.behavior = behavior
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        return self.behavior(self.calls, kwargs)


class _MockClient:
    def __init__(self, behavior):
        self.messages = _MockMessages(behavior)


def _happy_behavior(call_num, kwargs) -> _MockResponse:
    """Every call returns a valid minimal SourceAnalysis."""
    return _MockResponse({
        "insight": {
            "document_type": "architect_plan",
            "purpose": "Project plan for the site",
            "author": "Architect X",
            "date_info": "2026-04-01",
            "version_info": "v1",
            "related_sources": [],
            "authority_hints": [],
            "confidence": 0.9,
            "notes": "",
        },
        "candidates": [
            {
                "concept_id": "architect_name",
                "value": "Architect X",
                "confidence": 0.9,
                "quote": "Architect: Architect X",
                "artifact_path": "irrelevant",
                "reasoning": "caixetí",
            },
        ],
    })


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_happy_path_produces_analysis_per_source(tmp_path):
    project = _make_project(tmp_path)
    client = _MockClient(_happy_behavior)
    analysis = analyze_project(project, client=client, model="claude-sonnet-4-6")

    assert isinstance(analysis, ProjectAnalysis)
    assert analysis.systemic_failure is None
    assert len(analysis.sources) == 2  # PENETROS.pdf + DATA.xlsx
    assert len(analysis.failures) == 0
    assert client.messages.calls == 2


def test_candidates_carry_source_path_and_extractor(tmp_path):
    project = _make_project(tmp_path)
    client = _MockClient(_happy_behavior)
    analysis = analyze_project(project, client=client, model="claude-sonnet-4-6")

    for s in analysis.sources:
        for c in s.candidates:
            assert c.source_path == s.source_path
            assert c.extractor == "claude-sonnet-4-6"


def test_insight_source_path_matches_source(tmp_path):
    project = _make_project(tmp_path)
    client = _MockClient(_happy_behavior)
    analysis = analyze_project(project, client=client, model="claude-sonnet-4-6")
    for s in analysis.sources:
        assert s.insight.source_path == s.source_path


def test_candidates_by_concept_index(tmp_path):
    project = _make_project(tmp_path)
    client = _MockClient(_happy_behavior)
    analysis = analyze_project(project, client=client, model="claude-sonnet-4-6")
    assert "architect_name" in analysis.candidates_by_concept


def test_total_tokens_aggregate(tmp_path):
    project = _make_project(tmp_path)
    client = _MockClient(_happy_behavior)
    analysis = analyze_project(project, client=client, model="claude-sonnet-4-6")
    assert analysis.total_input_tokens > 0
    assert analysis.total_output_tokens > 0
    assert analysis.estimated_cost_usd > 0


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


def test_second_run_hits_cache(tmp_path):
    project = _make_project(tmp_path)
    client = _MockClient(_happy_behavior)
    analyze_project(project, client=client, model="claude-sonnet-4-6")
    first_calls = client.messages.calls

    # Second run — same inputs, cache should short-circuit every source
    client2 = _MockClient(_happy_behavior)
    second = analyze_project(project, client=client2, model="claude-sonnet-4-6")
    assert client2.messages.calls == 0
    assert second.cache_hits == 2
    # No token cost when served from cache
    assert second.total_input_tokens == 0


def test_cache_invalidated_by_content_change(tmp_path):
    project = _make_project(tmp_path)
    client = _MockClient(_happy_behavior)
    analyze_project(project, client=client, model="claude-sonnet-4-6")

    # Change one source file so its conversion + cache key changes
    (project / "PENETROS.pdf").write_bytes(_tiny_pdf_with_text("Totally new content. " * 20))
    # Invalidate Stage 2/3 caches so classify_project + convert_project re-run
    import shutil
    shutil.rmtree(project / "validation" / "ai_pipeline", ignore_errors=True)
    (project / "validation" / "ai_typology.json").unlink(missing_ok=True)
    (project / "validation" / "ai_conversion.json").unlink(missing_ok=True)

    client2 = _MockClient(_happy_behavior)
    analyze_project(project, client=client2, model="claude-sonnet-4-6")
    # The changed source must re-call; unchanged source keeps cache
    assert client2.messages.calls >= 1


# ---------------------------------------------------------------------------
# Systemic errors (project-wide abort)
# ---------------------------------------------------------------------------


def _insufficient_credits_behavior(call_num, kwargs):
    raise RuntimeError("Error code: 402 - insufficient_credits: credit_balance is too low")


def test_insufficient_credits_aborts_project_wide(tmp_path):
    project = _make_project(tmp_path)
    client = _MockClient(_insufficient_credits_behavior)
    analysis = analyze_project(project, client=client, model="claude-sonnet-4-6")

    assert analysis.systemic_failure is not None
    assert analysis.systemic_failure.error_type == "insufficient_credits"
    # Only ONE API call was attempted despite multiple sources — fail-fast
    assert client.messages.calls == 1
    # All remaining sources skipped, none enumerated as per-source failures
    assert len(analysis.failures) == 0
    assert analysis.systemic_failure.sources_skipped >= 1


def _auth_error_behavior(call_num, kwargs):
    raise RuntimeError("AuthenticationError: invalid API key (401)")


def test_auth_error_aborts_project_wide(tmp_path):
    project = _make_project(tmp_path)
    client = _MockClient(_auth_error_behavior)
    analysis = analyze_project(project, client=client, model="claude-sonnet-4-6")
    assert analysis.systemic_failure is not None
    assert analysis.systemic_failure.error_type == "authentication_error"
    assert client.messages.calls == 1


def test_systemic_failure_has_action_hint(tmp_path):
    project = _make_project(tmp_path)
    client = _MockClient(_insufficient_credits_behavior)
    analysis = analyze_project(project, client=client, model="claude-sonnet-4-6")
    assert "Action:" in analysis.systemic_failure.message


# ---------------------------------------------------------------------------
# Per-source failures (isolated, retries, circuit breaker)
# ---------------------------------------------------------------------------


def _make_per_source_retry_behavior(fail_first_n: int):
    """Fail with rate_limit for the first N calls, then succeed."""
    def behavior(call_num, kwargs):
        if call_num <= fail_first_n:
            raise RuntimeError("RateLimitError: 429 too many requests")
        return _happy_behavior(call_num, kwargs)
    return behavior


def test_transient_error_retries_then_succeeds(tmp_path):
    project = _make_project(tmp_path)
    # First source will fail once with rate_limit, then succeed on retry
    # Second source happy path (succeeds on first try)
    # Override default backoff so test stays fast
    import automation.ai_pipeline.analysis as ai
    original_backoff = ai._BACKOFF_INITIAL_S
    ai._BACKOFF_INITIAL_S = 0.0
    try:
        client = _MockClient(_make_per_source_retry_behavior(fail_first_n=1))
        analysis = analyze_project(project, client=client, model="claude-sonnet-4-6")
    finally:
        ai._BACKOFF_INITIAL_S = original_backoff

    # All sources eventually succeed
    assert analysis.systemic_failure is None
    assert len(analysis.sources) == 2
    # At least one source reports attempts>1
    assert any(s.attempts >= 2 for s in analysis.sources)


def _always_transient_behavior(call_num, kwargs):
    raise RuntimeError("RateLimitError: 429 too many requests")


def test_transient_exhausts_retries_then_fails_that_source(tmp_path):
    project = _make_three_source_project(tmp_path)
    import automation.ai_pipeline.analysis as ai
    original_backoff = ai._BACKOFF_INITIAL_S
    ai._BACKOFF_INITIAL_S = 0.0
    try:
        client = _MockClient(_always_transient_behavior)
        analysis = analyze_project(project, client=client, model="claude-sonnet-4-6")
    finally:
        ai._BACKOFF_INITIAL_S = original_backoff

    # Circuit breaker should kick in after 3 consecutive per-source failures
    assert analysis.systemic_failure is not None
    assert analysis.systemic_failure.error_type == "circuit_breaker"
    assert len(analysis.failures) == 3
    for f in analysis.failures:
        assert f.error_type == "rate_limit"


# ---------------------------------------------------------------------------
# Schema validation fallback
# ---------------------------------------------------------------------------


def _bad_schema_then_good_behavior(call_num, kwargs):
    """First call returns invalid tool input; retry returns valid."""
    if call_num == 1:
        # Missing required 'insight' fields
        return _MockResponse({"insight": {}, "candidates": []})
    return _happy_behavior(call_num, kwargs)


def test_schema_validation_retries_once(tmp_path):
    project = _make_project(tmp_path)
    client = _MockClient(_bad_schema_then_good_behavior)
    analysis = analyze_project(project, client=client, model="claude-sonnet-4-6")
    # First source had to retry, second went straight through
    assert analysis.systemic_failure is None
    assert len(analysis.sources) >= 1


def _always_bad_schema_behavior(call_num, kwargs):
    return _MockResponse({"insight": {}, "candidates": []})


def test_schema_validation_repeatedly_fails_records_per_source_failure(tmp_path):
    project = _make_three_source_project(tmp_path)
    import automation.ai_pipeline.analysis as ai
    original_backoff = ai._BACKOFF_INITIAL_S
    ai._BACKOFF_INITIAL_S = 0.0
    try:
        client = _MockClient(_always_bad_schema_behavior)
        analysis = analyze_project(project, client=client, model="claude-sonnet-4-6")
    finally:
        ai._BACKOFF_INITIAL_S = original_backoff

    # Circuit-breaker aborts after 3 consecutive failures
    assert analysis.systemic_failure is not None
    assert analysis.systemic_failure.error_type == "circuit_breaker"
    assert len(analysis.failures) == 3
    for f in analysis.failures:
        assert f.error_type == "schema_validation"


# ---------------------------------------------------------------------------
# Error classification unit
# ---------------------------------------------------------------------------


def test_classify_error_identifies_systemic():
    err = RuntimeError("402 insufficient_credits")
    et, sys_ = _classify_error(err)
    assert sys_ is True
    assert et == "insufficient_credits"


def test_classify_error_identifies_transient():
    err = RuntimeError("429 rate limit exceeded")
    et, sys_ = _classify_error(err)
    assert sys_ is False
    assert et == "rate_limit"


def test_classify_error_identifies_usage_limit():
    # Exact shape Anthropic returns when a per-key usage cap is hit (see D15).
    err = RuntimeError(
        "Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', "
        "'message': 'You have reached your specified API usage limits. You will regain "
        "access on 2026-05-01 at 00:00 UTC.'}, 'request_id': 'req_abc123'}"
    )
    et, sys_ = _classify_error(err)
    assert sys_ is True
    assert et == "usage_limit"


def _usage_limit_behavior(call_num, kwargs):
    raise RuntimeError(
        "Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', "
        "'message': 'You have reached your specified API usage limits. You will regain "
        "access on 2026-05-01 at 00:00 UTC.'}, 'request_id': 'req_abc123'}"
    )


def test_usage_limit_aborts_project_wide(tmp_path):
    project = _make_project(tmp_path)
    client = _MockClient(_usage_limit_behavior)
    analysis = analyze_project(project, client=client, model="claude-sonnet-4-6")

    assert analysis.systemic_failure is not None
    assert analysis.systemic_failure.error_type == "usage_limit"
    # Fail-fast on first call — no circuit-breaker waste.
    assert client.messages.calls == 1
    assert len(analysis.failures) == 0
    assert analysis.systemic_failure.sources_skipped >= 1


def test_usage_limit_message_has_action_hint(tmp_path):
    project = _make_project(tmp_path)
    client = _MockClient(_usage_limit_behavior)
    analysis = analyze_project(project, client=client, model="claude-sonnet-4-6")
    msg = analysis.systemic_failure.message
    assert "Action:" in msg
    # Preserve Anthropic's regain-access timestamp in the surfaced message
    assert "regain access" in msg.lower() or "regain-access" in msg.lower()


# ---------------------------------------------------------------------------
# Source filter
# ---------------------------------------------------------------------------


def test_source_filter_limits_analysis(tmp_path):
    project = _make_project(tmp_path)
    client = _MockClient(_happy_behavior)
    analysis = analyze_project(project, client=client, model="claude-sonnet-4-6", source_filter="PENETROS")
    assert len(analysis.sources) == 1
    assert "PENETROS" in analysis.sources[0].source_path


# ---------------------------------------------------------------------------
# Save/load
# ---------------------------------------------------------------------------


def test_save_load_roundtrip(tmp_path):
    project = _make_project(tmp_path)
    client = _MockClient(_happy_behavior)
    analysis = analyze_project(project, client=client, model="claude-sonnet-4-6")
    out = save_analysis(analysis, project)
    assert out == project / "validation" / "ai_analysis.json"
    loaded = load_analysis(project)
    assert loaded is not None
    assert len(loaded.sources) == len(analysis.sources)


def test_load_returns_none_when_absent(tmp_path):
    project = _make_project(tmp_path)
    assert load_analysis(project) is None


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


def test_rejects_nonexistent_project(tmp_path):
    with pytest.raises(ValueError):
        analyze_project(tmp_path / "no-such-dir")


def test_missing_api_key_without_client_returns_systemic_failure(tmp_path, monkeypatch):
    project = _make_project(tmp_path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # No client injected → module must resolve real one, which should fail-fast
    analysis = analyze_project(project)
    assert analysis.systemic_failure is not None
    assert analysis.systemic_failure.error_type == "missing_api_key"


# ---------------------------------------------------------------------------
# Eva summary
# ---------------------------------------------------------------------------


def test_eva_summary_is_catalan(tmp_path):
    project = _make_project(tmp_path)
    client = _MockClient(_happy_behavior)
    analysis = analyze_project(project, client=client, model="claude-sonnet-4-6")
    joined = "\n".join(analysis.eva_summary).lower()
    assert "analitzat" in joined
    assert "candidats" in joined


def test_eva_summary_mentions_systemic_failure(tmp_path):
    project = _make_project(tmp_path)
    client = _MockClient(_insufficient_credits_behavior)
    analysis = analyze_project(project, client=client, model="claude-sonnet-4-6")
    joined = "\n".join(analysis.eva_summary).lower()
    assert "insufficient_credits" in joined or "systemic" in joined or "⚠" in "".join(analysis.eva_summary)


# ---------------------------------------------------------------------------
# D14 tests — cache folder slug collision
# ---------------------------------------------------------------------------
def test_cache_path_includes_parent_for_extracted_images(tmp_path):
    path_a = _cache_path(
        tmp_path,
        "validation/ai_pipeline/extracted/PLAN_COST_ALCOLETGE/img_000.png",
    )
    path_b = _cache_path(
        tmp_path,
        "validation/ai_pipeline/extracted/A.01/img_000.png",
    )
    assert path_a != path_b
    assert path_a.parent.name != path_b.parent.name


def test_cache_path_for_root_source_unchanged(tmp_path):
    cache_path = _cache_path(tmp_path, "PENETROS.pdf")
    assert cache_path.parent.name == "PENETROS"


def test_cache_path_slugifies_parent_with_dots(tmp_path):
    cache_path = _cache_path(tmp_path, "26.0049/A.01.pdf")
    assert cache_path.parent.name == "26.0049_A.01"
