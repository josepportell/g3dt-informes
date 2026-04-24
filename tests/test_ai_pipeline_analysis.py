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
    _SCHEMA_VERSION,
    _build_user_content,
    _cache_path,
    _classify_error,
    _group_artifacts_by_source,
    analyze_project,
    load_analysis,
    save_analysis,
)
from automation.ai_pipeline.conversion import ConvertedArtifact, ProjectConversion


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
        self.kwargs_history: list[dict] = []

    def create(self, **kwargs):
        self.calls += 1
        self.kwargs_history.append(kwargs)
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
# D14 tests — cache folder slug collision (inserted above this anchor)
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


# SENTINEL_D14_END


# ---------------------------------------------------------------------------
# D16 tests — Anthropic prompt caching on static content (inserted above this anchor)
# ---------------------------------------------------------------------------


def test_build_user_content_marks_static_block_cacheable(tmp_path):
    project = _make_project(tmp_path)
    blocks = _build_user_content(project, "PENETROS.pdf", [])

    cached_blocks = [
        b for b in blocks
        if isinstance(b, dict) and b.get("cache_control", {}).get("type") == "ephemeral"
    ]
    assert len(cached_blocks) >= 1, "At least one block must be marked cache_control ephemeral"

    # The cached block should contain the concept schema. 'architect_name' is a
    # concept_id we know lives in report_variables.yaml.
    cached_text = "\n".join(b.get("text", "") for b in cached_blocks)
    assert "architect_name" in cached_text


def test_build_user_content_header_not_cached(tmp_path):
    project = _make_project(tmp_path)
    source_path = "PENETROS.pdf"
    blocks = _build_user_content(project, source_path, [])

    # The per-source header block contains the source_path. It must NOT be cached.
    header_blocks = [
        b for b in blocks
        if isinstance(b, dict) and b.get("type") == "text" and source_path in b.get("text", "")
    ]
    assert len(header_blocks) >= 1
    for b in header_blocks:
        # Make sure the header block itself has no cache_control
        # (cached block contains concept YAML, not the source_path header text).
        if "cache_control" in b:
            # Header sharing the same block as cached content would be wrong.
            # Header text and concept YAML must be in different blocks.
            assert "architect_name" not in b.get("text", ""), (
                "Header block should not contain the cached static content"
            )


def test_analysis_aggregates_cache_token_stats(tmp_path):
    project = _make_project(tmp_path)

    class _CacheUsage:
        def __init__(self):
            self.input_tokens = 100
            self.output_tokens = 200
            self.cache_creation_input_tokens = 3_500
            self.cache_read_input_tokens = 0

    class _CacheResponse:
        def __init__(self, tool_input: dict):
            self.content = [SimpleNamespace(
                type="tool_use",
                name="emit_analysis",
                input=tool_input,
            )]
            self.usage = _CacheUsage()

    def _cache_behavior(call_num, kwargs):
        return _CacheResponse({
            "insight": {
                "document_type": "architect_plan",
                "purpose": "Project plan",
                "author": "X",
                "date_info": "",
                "version_info": "",
                "related_sources": [],
                "authority_hints": [],
                "confidence": 0.9,
                "notes": "",
            },
            "candidates": [],
        })

    client = _MockClient(_cache_behavior)
    analysis = analyze_project(project, client=client, model="claude-sonnet-4-6")

    assert analysis.systemic_failure is None
    assert len(analysis.sources) == 2
    # Two fresh sources × 3500 creation tokens = 7000
    assert analysis.total_cache_creation_tokens == 7_000
    assert analysis.total_cache_read_tokens == 0
    # Per-source fields populated
    for s in analysis.sources:
        assert s.cache_creation_input_tokens == 3_500
        assert s.cache_read_input_tokens == 0


def test_schema_version_bumped_invalidates_local_cache(tmp_path):
    # Schema bumped to 1.2 — D16 (block layout) then D1#2 (grouping).
    assert _SCHEMA_VERSION == "1.2"

    project = _make_project(tmp_path)
    client = _MockClient(_happy_behavior)
    analyze_project(project, client=client, model="claude-sonnet-4-6")
    first_calls = client.messages.calls
    assert first_calls == 2

    # Second run at the same version should hit local cache — zero calls.
    client2 = _MockClient(_happy_behavior)
    second = analyze_project(project, client=client2, model="claude-sonnet-4-6")
    assert client2.messages.calls == 0
    assert second.cache_hits == 2


# SENTINEL_D16_END


# ---------------------------------------------------------------------------
# D1#2 tests — extracted images group with their parent source
# ---------------------------------------------------------------------------


def _fake_conversion(artifacts: list[ConvertedArtifact]) -> ProjectConversion:
    return ProjectConversion(
        project_path="/tmp/fake",
        converted_at="2026-04-25T00:00:00+00:00",
        artifacts=artifacts,
    )


def test_group_puts_text_before_passthrough_images():
    """Sort within a source: text pages/sheets come before passthrough images."""
    conv = _fake_conversion([
        ConvertedArtifact(
            path="validation/ai_pipeline/extracted/A.01/img_000.png",
            format="passthrough", source_path="A.01.pdf",
            strategy_used="image_passthrough",
        ),
        ConvertedArtifact(
            path="validation/ai_pipeline/converted/A.01/page_002.md",
            format="md", source_path="A.01.pdf", page=2,
            strategy_used="pdf_to_markdown_plus_images",
        ),
        ConvertedArtifact(
            path="validation/ai_pipeline/converted/A.01/page_001.md",
            format="md", source_path="A.01.pdf", page=1,
            strategy_used="pdf_to_markdown_plus_images",
        ),
    ])
    groups = _group_artifacts_by_source(conv)
    arts = groups["A.01.pdf"]
    assert [a.page for a in arts[:2]] == [1, 2]  # text in page order first
    assert arts[-1].format == "passthrough"      # image last


def test_group_merges_extracted_images_with_parent():
    """An extracted-image artifact carrying the parent's source_path lands in one group."""
    conv = _fake_conversion([
        ConvertedArtifact(
            path="validation/ai_pipeline/converted/A.01/page_001.md",
            format="md", source_path="A.01.pdf", page=1,
            strategy_used="pdf_to_markdown_plus_images",
        ),
        ConvertedArtifact(
            path="validation/ai_pipeline/extracted/A.01/img_000.png",
            format="passthrough", source_path="A.01.pdf",
            strategy_used="image_passthrough",
        ),
        ConvertedArtifact(
            path="validation/ai_pipeline/extracted/A.01/img_001.png",
            format="passthrough", source_path="A.01.pdf",
            strategy_used="image_passthrough",
        ),
    ])
    groups = _group_artifacts_by_source(conv)
    assert list(groups.keys()) == ["A.01.pdf"]
    assert len(groups["A.01.pdf"]) == 3


def test_extracted_image_does_not_trigger_extra_llm_call(tmp_path):
    """A PDF with an embedded image should produce ONE Stage 4 call, not two."""
    project = tmp_path / "demo_grouping"
    project.mkdir()
    # PDF with text + embedded image — Stage 2 will extract the image as its own FileClass.
    # We need a small PDF that both has text AND an image.
    import fitz
    from PIL import Image
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Plan with an embedded image. " * 8)
    # Insert an image rectangle; use a random-noise PNG big enough to pass the 5 KB filter.
    img_buf = BytesIO()
    random_img = Image.new("RGB", (256, 256))
    import random
    random.seed(7)
    random_img.putdata([(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
                        for _ in range(256 * 256)])
    random_img.save(img_buf, format="PNG")
    page.insert_image(fitz.Rect(100, 200, 300, 400), stream=img_buf.getvalue())
    (project / "PLAN.pdf").write_bytes(doc.tobytes())
    doc.close()

    client = _MockClient(_happy_behavior)
    analysis = analyze_project(project, client=client, model="claude-sonnet-4-6")
    # Exactly one source group (the PDF), not one-per-embedded-image.
    assert len(analysis.sources) == 1
    assert analysis.sources[0].source_path == "PLAN.pdf"
    assert client.messages.calls == 1


# ---------------------------------------------------------------------------
# D5 tests — schema-validation retry uses a trimmed prompt (arch §7.6)
# ---------------------------------------------------------------------------

# Distinctive substring that appears only in the glossary block header. Used to
# detect glossary presence/absence in a user_content list of blocks.
_GLOSSARY_MARKER = "Glossary — Eva's rules"


def _user_text(kwargs: dict) -> str:
    """Join every text block of the user message for substring assertions."""
    messages = kwargs.get("messages") or []
    parts: list[str] = []
    for msg in messages:
        for block in msg.get("content", []) or []:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
    return "\n".join(parts)


def test_build_user_content_respects_include_glossary_flag(tmp_path):
    project = _make_project(tmp_path)

    with_gloss = _build_user_content(project, "PENETROS.pdf", [])
    without_gloss = _build_user_content(
        project, "PENETROS.pdf", [], include_glossary=False,
    )

    with_text = "\n".join(b.get("text", "") for b in with_gloss if isinstance(b, dict))
    without_text = "\n".join(b.get("text", "") for b in without_gloss if isinstance(b, dict))

    assert _GLOSSARY_MARKER in with_text
    assert _GLOSSARY_MARKER not in without_text
    # The trimmed version must be meaningfully shorter.
    assert len(without_text) < len(with_text)
    # Concept schema (authoritative target) stays in both shapes.
    assert "architect_name" in with_text
    assert "architect_name" in without_text


def _bad_then_good_behavior(call_num, kwargs):
    """Call 1: schema violation (empty insight). Call 2+: valid."""
    if call_num == 1:
        return _MockResponse({"insight": {}, "candidates": []})
    return _happy_behavior(call_num, kwargs)


def test_schema_validation_retry_uses_trimmed_prompt(tmp_path):
    project = _make_project(tmp_path)
    import automation.ai_pipeline.analysis as ai
    original_backoff = ai._BACKOFF_INITIAL_S
    ai._BACKOFF_INITIAL_S = 0.0
    try:
        client = _MockClient(_bad_then_good_behavior)
        analysis = analyze_project(project, client=client, model="claude-sonnet-4-6")
    finally:
        ai._BACKOFF_INITIAL_S = original_backoff

    assert analysis.systemic_failure is None
    # We need at least one source that went through a schema-retry cycle.
    assert client.messages.calls >= 2
    # Call 1 (schema-violating response) was sent with the full prompt INCLUDING
    # the glossary. Call 2 (trimmed retry) must NOT contain the glossary block.
    first_text = _user_text(client.messages.kwargs_history[0])
    second_text = _user_text(client.messages.kwargs_history[1])
    assert _GLOSSARY_MARKER in first_text
    assert _GLOSSARY_MARKER not in second_text
    # Concept schema stays on the retry — that's the authoritative target.
    assert "architect_name" in second_text


def _rate_limit_then_good_behavior(call_num, kwargs):
    """Call 1: transient 429. Call 2+: valid."""
    if call_num == 1:
        raise RuntimeError("RateLimitError: 429 too many requests")
    return _happy_behavior(call_num, kwargs)


def test_transient_retry_keeps_full_prompt(tmp_path):
    project = _make_project(tmp_path)
    import automation.ai_pipeline.analysis as ai
    original_backoff = ai._BACKOFF_INITIAL_S
    ai._BACKOFF_INITIAL_S = 0.0
    try:
        client = _MockClient(_rate_limit_then_good_behavior)
        analysis = analyze_project(project, client=client, model="claude-sonnet-4-6")
    finally:
        ai._BACKOFF_INITIAL_S = original_backoff

    assert analysis.systemic_failure is None
    assert client.messages.calls >= 2
    # Both attempts (the transient failure AND the successful retry) must keep
    # the full prompt — transient errors have nothing to do with schema noise.
    first_text = _user_text(client.messages.kwargs_history[0])
    second_text = _user_text(client.messages.kwargs_history[1])
    assert _GLOSSARY_MARKER in first_text
    assert _GLOSSARY_MARKER in second_text
