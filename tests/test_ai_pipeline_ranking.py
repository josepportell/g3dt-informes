"""Tests for AI pipeline Stage 5 — ranking.

Chunk 1: models + passthrough (no LLM).
Chunk 2: Pass A (per-concept LLM ranker) — all calls mocked via an injected
client; zero real API calls.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pydantic
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from automation.ai_pipeline.analysis import (
    Candidate,
    ProjectAnalysis,
    SourceAnalysis,
    SourceInsight,
)
from automation.ai_pipeline.ranking import (
    ConceptRanking,
    GroupAuditResult,
    ProjectRanking,
    RankedCandidate,
    _candidate_id,
    load_authority_principles,
    load_concept_definitions,
    load_ranking,
    rank_project,
    rank_project_passthrough_only,
    save_ranking,
)


# ─── Fixtures ──────────────────────────────────────────────────────────


def _make_analysis(
    sources: list[tuple[str, list[tuple[str, object, float]]]],
) -> ProjectAnalysis:
    """Build a minimal ProjectAnalysis.

    `sources` is a list of (source_path, [(concept_id, value, confidence), ...]).
    """
    src_analyses: list[SourceAnalysis] = []
    for source_path, cand_specs in sources:
        candidates = [
            Candidate(
                concept_id=cid,
                value=val,
                confidence=conf,
                source_path=source_path,
            )
            for cid, val, conf in cand_specs
        ]
        src_analyses.append(
            SourceAnalysis(
                source_path=source_path,
                insight=SourceInsight(
                    source_path=source_path,
                    document_type="test",
                    purpose="test",
                ),
                candidates=candidates,
            )
        )
    return ProjectAnalysis(
        project_path="/tmp/fake",
        analyzed_at="2026-04-24T00:00:00+00:00",
        sources=src_analyses,
    )


def _make_project_with_analysis(tmp_path: Path, analysis: ProjectAnalysis) -> Path:
    p = tmp_path / "demo"
    (p / "validation").mkdir(parents=True)
    (p / "validation" / "ai_analysis.json").write_text(
        analysis.model_dump_json(indent=2), encoding="utf-8"
    )
    return p


# ─── Candidate-id helper ───────────────────────────────────────────────


def test_candidate_id_format():
    assert (
        _candidate_id("plans/A.01.pdf", "architect_name", 0)
        == "plans/A.01.pdf::architect_name::0"
    )
    assert (
        _candidate_id("", "x", 7) == "::x::7"
    )  # degenerate but well-defined


# ─── Pydantic models ───────────────────────────────────────────────────


def test_ranked_candidate_model():
    rc = RankedCandidate(
        candidate_id="plans/A.01.pdf::architect_name::0",
        source_path="plans/A.01.pdf",
        value="Joan Planes",
        confidence=0.9,
        rationale="caixetí del plànol",
    )
    assert rc.confidence == 0.9
    assert rc.value == "Joan Planes"


def test_concept_ranking_statuses():
    for status in ("ranked", "single", "no_candidates", "pending_fase5"):
        cr = ConceptRanking(concept_id="cid", status=status)
        assert cr.status == status


def test_concept_ranking_rejects_unknown_status():
    with pytest.raises(pydantic.ValidationError):
        ConceptRanking(concept_id="cid", status="weird_status")  # type: ignore[arg-type]


def test_project_ranking_ranking_of():
    cr = ConceptRanking(concept_id="client_name", status="single")
    pr = ProjectRanking(
        project_path="/tmp",
        ranked_at="2026-04-24T00:00:00+00:00",
        concepts={"client_name": cr},
    )
    assert pr.ranking_of("client_name") is cr
    assert pr.ranking_of("missing_concept") is None


def test_group_audit_result_defaults():
    g = GroupAuditResult(group="parcel")
    assert g.factors == []
    assert g.revisions == []
    assert g.skipped_reason == ""


# ─── Schema / principles loaders ───────────────────────────────────────


def test_load_concept_definitions_returns_many_concepts():
    defs = load_concept_definitions()
    # Sanity check — robust against small schema edits.
    assert len(defs) >= 80
    # Every entry should carry the keys Pass B (chunk 3) relies on.
    sample = next(iter(defs.values()))
    for k in ("id", "type", "group", "description_ca", "required"):
        assert k in sample


def test_load_authority_principles_exists():
    text = load_authority_principles()
    assert text  # non-empty
    assert ("Eva" in text) or ("autoritat" in text.lower())


# ─── Passthrough orchestrator ──────────────────────────────────────────


def test_passthrough_zero_candidates(tmp_path):
    # No sources at all → every concept ends up in no_candidates.
    analysis = _make_analysis(sources=[])
    project = _make_project_with_analysis(tmp_path, analysis)
    ranking = rank_project_passthrough_only(project, analysis=analysis)

    defs = load_concept_definitions()
    # Pick a concept we know exists in the real YAML.
    some_cid = next(iter(defs))
    cr = ranking.ranking_of(some_cid)
    assert cr is not None
    assert cr.status == "no_candidates"
    assert cr.ranked == []


def test_passthrough_single_candidate(tmp_path):
    # Use a concept that exists in the real YAML.
    defs = load_concept_definitions()
    cid = next(iter(defs))
    analysis = _make_analysis(
        sources=[("plans/A.01.pdf", [(cid, "Joan Planes", 0.9)])]
    )
    project = _make_project_with_analysis(tmp_path, analysis)

    ranking = rank_project_passthrough_only(project, analysis=analysis)
    cr = ranking.ranking_of(cid)
    assert cr is not None
    assert cr.status == "single"
    assert len(cr.ranked) == 1
    rc = cr.ranked[0]
    assert rc.value == "Joan Planes"
    assert rc.source_path == "plans/A.01.pdf"
    assert rc.rationale == "única font disponible"
    # Candidate id follows the documented shape.
    assert rc.candidate_id == f"plans/A.01.pdf::{cid}::0"
    # Chunks 2–3 will populate groups; for now passthrough must leave it empty.
    assert ranking.groups == {}


def test_passthrough_skips_multi_candidate_concepts(tmp_path):
    defs = load_concept_definitions()
    cid = next(iter(defs))
    analysis = _make_analysis(
        sources=[
            ("plans/A.01.pdf", [(cid, "Joan Planes", 0.9)]),
            ("emails/hello.msg", [(cid, "Marta Soler", 0.7)]),
        ]
    )
    project = _make_project_with_analysis(tmp_path, analysis)
    ranking = rank_project_passthrough_only(project, analysis=analysis)

    # Multi-candidate concept is intentionally omitted (later chunks fill it in).
    assert cid not in ranking.concepts
    # Exactly one concept has ≥2 candidates → summary must report "1 pendents".
    assert len(ranking.eva_summary) == 1
    assert "1 pendents de rànquing LLM" in ranking.eva_summary[0]


def test_passthrough_loads_from_disk_when_analysis_not_passed(tmp_path):
    defs = load_concept_definitions()
    cid = next(iter(defs))
    analysis = _make_analysis(
        sources=[("plans/A.01.pdf", [(cid, "Joan Planes", 0.9)])]
    )
    project = _make_project_with_analysis(tmp_path, analysis)

    # Do NOT pass analysis — function must load it from disk.
    ranking = rank_project_passthrough_only(project)
    cr = ranking.ranking_of(cid)
    assert cr is not None
    assert cr.status == "single"


def test_passthrough_raises_when_analysis_missing(tmp_path):
    project = tmp_path / "empty_project"
    project.mkdir()
    with pytest.raises(FileNotFoundError):
        rank_project_passthrough_only(project)


def test_save_and_load_ranking_roundtrip(tmp_path):
    project = tmp_path / "demo"
    project.mkdir()
    pr = ProjectRanking(
        project_path=str(project),
        ranked_at="2026-04-24T00:00:00+00:00",
        concepts={
            "client_name": ConceptRanking(
                concept_id="client_name",
                status="single",
                ranked=[
                    RankedCandidate(
                        candidate_id="plans/A.01.pdf::client_name::0",
                        source_path="plans/A.01.pdf",
                        value="Joan Planes",
                        confidence=0.9,
                        rationale="única font disponible",
                    )
                ],
            )
        },
        eva_summary=["test"],
    )

    out = save_ranking(pr, project)
    assert out == project / "validation" / "ai_ranking.json"

    loaded = load_ranking(project)
    assert loaded is not None
    assert loaded.model_dump() == pr.model_dump()


def test_load_ranking_returns_none_when_absent(tmp_path):
    project = tmp_path / "demo"
    project.mkdir()
    assert load_ranking(project) is None


def test_eva_summary_populated(tmp_path):
    analysis = _make_analysis(sources=[])
    project = _make_project_with_analysis(tmp_path, analysis)
    ranking = rank_project_passthrough_only(project, analysis=analysis)
    assert ranking.eva_summary
    assert any("Passthrough" in line for line in ranking.eva_summary)


# ═══════════════════════════════════════════════════════════════════════
# Chunk 2 — Pass A (per-concept LLM ranker) tests
# ═══════════════════════════════════════════════════════════════════════


# ─── Mock Anthropic client (Pass A shape) ──────────────────────────────


class _FakeUsage:
    def __init__(self, input_tokens=120, output_tokens=80):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cache_creation_input_tokens = 0
        self.cache_read_input_tokens = 0


class _FakeResponse:
    def __init__(self, tool_input: dict):
        self.content = [
            SimpleNamespace(type="tool_use", name="emit_ranking", input=tool_input)
        ]
        self.usage = _FakeUsage()


class _FakeMessages:
    def __init__(self, behavior):
        self.behavior = behavior
        self.calls = 0
        self.kwargs_history: list[dict] = []

    def create(self, **kwargs):
        self.calls += 1
        self.kwargs_history.append(kwargs)
        return self.behavior(self.calls, kwargs)


class _FakeAnthropicClient:
    def __init__(self, behavior):
        self.messages = _FakeMessages(behavior)


def _pick_multi_candidate_concept() -> str:
    """Return a concept_id known to exist in the real YAML for test inputs."""
    defs = load_concept_definitions()
    # Prefer a simple string concept — avoid complex lists.
    preferred = ("architect_name", "client_name", "municipality", "num_floors")
    for cid in preferred:
        if cid in defs:
            return cid
    return next(iter(defs))


def _make_multi_analysis(
    cid: str,
    values: list[tuple[str, str, float]],
) -> ProjectAnalysis:
    """values = [(source_path, value, confidence), ...]."""
    return _make_analysis(
        sources=[(sp, [(cid, val, conf)]) for sp, val, conf in values]
    )


def _build_ranked_tool_input(
    candidate_ids: list[str],
    has_conflict: bool = False,
    conflict_note: str = "",
) -> dict:
    return {
        "ranked": [
            {"candidate_id": cid, "rationale": f"reason for {cid}"}
            for cid in candidate_ids
        ],
        "has_conflict": has_conflict,
        "conflict_note": conflict_note,
    }


def _expected_candidate_ids(analysis: ProjectAnalysis, cid: str) -> list[str]:
    out = []
    for s in analysis.sources:
        for idx, c in enumerate(s.candidates):
            if c.concept_id == cid:
                out.append(f"{s.source_path}::{cid}::{idx}")
    return sorted(out)


# ─── Happy path ────────────────────────────────────────────────────────


def test_rank_project_single_concept_happy_path(tmp_path):
    cid = _pick_multi_candidate_concept()
    analysis = _make_multi_analysis(
        cid,
        [
            ("plans/A.01.pdf", "Joan Planes", 0.9),
            ("emails/a.msg", "Marta Soler", 0.7),
            ("memo.pdf", "Other Name", 0.5),
        ],
    )
    project = _make_project_with_analysis(tmp_path, analysis)
    cids = _expected_candidate_ids(analysis, cid)
    # Ranker returns a specific order: the middle candidate wins.
    chosen_order = [cids[1], cids[0], cids[2]]

    def behavior(call_num, kwargs):
        return _FakeResponse(_build_ranked_tool_input(chosen_order))

    client = _FakeAnthropicClient(behavior)
    ranking = rank_project(
        project, analysis=analysis, client=client, concept_filter=cid,
    )

    cr = ranking.ranking_of(cid)
    assert cr is not None
    assert cr.status == "ranked"
    assert [r.candidate_id for r in cr.ranked] == chosen_order
    assert all(r.rationale for r in cr.ranked)
    assert cr.has_conflict is False
    assert cr.attempts == 1
    assert cr.model


def test_rank_project_populates_catalan_summary(tmp_path):
    cid = _pick_multi_candidate_concept()
    analysis = _make_multi_analysis(
        cid,
        [("plans/A.01.pdf", "X", 0.9), ("emails/a.msg", "Y", 0.7)],
    )
    project = _make_project_with_analysis(tmp_path, analysis)
    cids = _expected_candidate_ids(analysis, cid)

    def behavior(call_num, kwargs):
        return _FakeResponse(_build_ranked_tool_input(cids))

    client = _FakeAnthropicClient(behavior)
    ranking = rank_project(
        project, analysis=analysis, client=client, concept_filter=cid,
    )
    joined = "\n".join(ranking.eva_summary).lower()
    assert ranking.eva_summary
    assert "rànquing" in joined or "fase 5" in joined


# ─── Cache ─────────────────────────────────────────────────────────────


def test_concept_cache_miss_then_hit(tmp_path):
    cid = _pick_multi_candidate_concept()
    analysis = _make_multi_analysis(
        cid, [("a.pdf", "X", 0.9), ("b.pdf", "Y", 0.7)]
    )
    project = _make_project_with_analysis(tmp_path, analysis)
    cids = _expected_candidate_ids(analysis, cid)

    def behavior(call_num, kwargs):
        return _FakeResponse(_build_ranked_tool_input(cids))

    client = _FakeAnthropicClient(behavior)
    first = rank_project(
        project, analysis=analysis, client=client, concept_filter=cid,
    )
    assert client.messages.calls == 1
    assert first.cache_hits == 0

    client2 = _FakeAnthropicClient(behavior)
    second = rank_project(
        project, analysis=analysis, client=client2, concept_filter=cid,
    )
    assert client2.messages.calls == 0
    assert second.cache_hits == 1
    assert second.total_input_tokens == 0


def test_concept_cache_invalidated_by_principles_change(tmp_path, monkeypatch):
    cid = _pick_multi_candidate_concept()
    analysis = _make_multi_analysis(
        cid, [("a.pdf", "X", 0.9), ("b.pdf", "Y", 0.7)]
    )
    project = _make_project_with_analysis(tmp_path, analysis)
    cids = _expected_candidate_ids(analysis, cid)

    def behavior(call_num, kwargs):
        return _FakeResponse(_build_ranked_tool_input(cids))

    import automation.ai_pipeline.ranking as ranking_mod

    monkeypatch.setattr(ranking_mod, "load_authority_principles", lambda: "P1")
    client = _FakeAnthropicClient(behavior)
    rank_project(project, analysis=analysis, client=client, concept_filter=cid)
    assert client.messages.calls == 1

    monkeypatch.setattr(ranking_mod, "load_authority_principles", lambda: "P2 DIFFERENT")
    client2 = _FakeAnthropicClient(behavior)
    second = rank_project(
        project, analysis=analysis, client=client2, concept_filter=cid,
    )
    assert client2.messages.calls == 1
    assert second.cache_hits == 0


def test_concept_cache_invalidated_by_schema_version(tmp_path, monkeypatch):
    cid = _pick_multi_candidate_concept()
    analysis = _make_multi_analysis(
        cid, [("a.pdf", "X", 0.9), ("b.pdf", "Y", 0.7)]
    )
    project = _make_project_with_analysis(tmp_path, analysis)
    cids = _expected_candidate_ids(analysis, cid)

    def behavior(call_num, kwargs):
        return _FakeResponse(_build_ranked_tool_input(cids))

    import automation.ai_pipeline.ranking as ranking_mod

    client = _FakeAnthropicClient(behavior)
    rank_project(project, analysis=analysis, client=client, concept_filter=cid)
    assert client.messages.calls == 1

    monkeypatch.setattr(ranking_mod, "_SCHEMA_VERSION", "99.99")
    client2 = _FakeAnthropicClient(behavior)
    rank_project(project, analysis=analysis, client=client2, concept_filter=cid)
    assert client2.messages.calls == 1


def test_force_flag_bypasses_cache(tmp_path):
    cid = _pick_multi_candidate_concept()
    analysis = _make_multi_analysis(
        cid, [("a.pdf", "X", 0.9), ("b.pdf", "Y", 0.7)]
    )
    project = _make_project_with_analysis(tmp_path, analysis)
    cids = _expected_candidate_ids(analysis, cid)

    def behavior(call_num, kwargs):
        return _FakeResponse(_build_ranked_tool_input(cids))

    client = _FakeAnthropicClient(behavior)
    rank_project(project, analysis=analysis, client=client, concept_filter=cid)
    assert client.messages.calls == 1

    client2 = _FakeAnthropicClient(behavior)
    rank_project(
        project, analysis=analysis, client=client2, concept_filter=cid, force=True,
    )
    assert client2.messages.calls == 1  # not a cache hit


# ─── Retry / error ─────────────────────────────────────────────────────


def _user_text(kwargs: dict) -> str:
    parts = []
    for msg in kwargs.get("messages", []) or []:
        for block in msg.get("content", []) or []:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
    return "\n".join(parts)


def _has_principles_block(kwargs: dict) -> bool:
    for msg in kwargs.get("messages", []) or []:
        for block in msg.get("content", []) or []:
            if not isinstance(block, dict):
                continue
            if (
                block.get("cache_control", {}).get("type") == "ephemeral"
                and "Authority principles" in block.get("text", "")
            ):
                return True
    return False


def _has_glossary_section(kwargs: dict) -> bool:
    for msg in kwargs.get("messages", []) or []:
        for block in msg.get("content", []) or []:
            if not isinstance(block, dict):
                continue
            if "## Glossary entry" in block.get("text", ""):
                return True
    return False


def test_schema_validation_retry_drops_principles_block(tmp_path, monkeypatch):
    # Pick a concept known to have a glossary entry so we can also assert the
    # glossary section is dropped on the trimmed retry.
    cid = "num_floors"
    defs = load_concept_definitions()
    assert cid in defs
    analysis = _make_multi_analysis(
        cid, [("a.pdf", "2", 0.9), ("b.pdf", "3", 0.7)]
    )
    project = _make_project_with_analysis(tmp_path, analysis)
    cids = _expected_candidate_ids(analysis, cid)

    def behavior(call_num, kwargs):
        if call_num == 1:
            # invent a candidate_id that doesn't exist → schema validation fails
            return _FakeResponse(
                _build_ranked_tool_input(["invented_candidate_id"])
            )
        return _FakeResponse(_build_ranked_tool_input(cids))

    import automation.ai_pipeline.ranking as ranking_mod

    monkeypatch.setattr(ranking_mod, "_BACKOFF_INITIAL_S", 0.0)
    client = _FakeAnthropicClient(behavior)
    ranking = rank_project(
        project, analysis=analysis, client=client, concept_filter=cid,
    )

    assert client.messages.calls == 2
    # First call: full prompt with principles AND glossary.
    assert _has_principles_block(client.messages.kwargs_history[0])
    assert _has_glossary_section(client.messages.kwargs_history[0])
    # Retry: both principles and glossary must be dropped.
    assert not _has_principles_block(client.messages.kwargs_history[1])
    assert not _has_glossary_section(client.messages.kwargs_history[1])
    cr = ranking.ranking_of(cid)
    assert cr is not None
    assert cr.status == "ranked"


def test_transient_error_retries_and_succeeds(tmp_path, monkeypatch):
    cid = _pick_multi_candidate_concept()
    analysis = _make_multi_analysis(
        cid, [("a.pdf", "X", 0.9), ("b.pdf", "Y", 0.7)]
    )
    project = _make_project_with_analysis(tmp_path, analysis)
    cids = _expected_candidate_ids(analysis, cid)

    def behavior(call_num, kwargs):
        if call_num == 1:
            raise RuntimeError("RateLimitError: 429 too many requests")
        return _FakeResponse(_build_ranked_tool_input(cids))

    import automation.ai_pipeline.ranking as ranking_mod

    monkeypatch.setattr(ranking_mod, "_BACKOFF_INITIAL_S", 0.0)
    client = _FakeAnthropicClient(behavior)
    ranking = rank_project(
        project, analysis=analysis, client=client, concept_filter=cid,
    )

    assert client.messages.calls == 2
    cr = ranking.ranking_of(cid)
    assert cr is not None
    assert cr.status == "ranked"
    assert cr.attempts == 2


def test_systemic_error_sets_remaining_pending_fase5(tmp_path):
    cid_a = "architect_name"
    cid_b = "client_name"
    defs = load_concept_definitions()
    for c in (cid_a, cid_b):
        assert c in defs, f"required concept {c} missing from schema"

    analysis = _make_analysis(
        sources=[
            ("s1.pdf", [(cid_a, "X", 0.9), (cid_b, "P", 0.9)]),
            ("s2.pdf", [(cid_a, "Y", 0.7), (cid_b, "Q", 0.7)]),
        ]
    )
    project = _make_project_with_analysis(tmp_path, analysis)

    def behavior(call_num, kwargs):
        raise RuntimeError("AuthenticationError: invalid API key (401)")

    client = _FakeAnthropicClient(behavior)
    ranking = rank_project(
        project,
        analysis=analysis,
        client=client,
        concept_filter={cid_a, cid_b},
    )

    # Fail-fast on first call, second concept never attempted.
    assert client.messages.calls == 1
    statuses = {
        ranking.concepts[cid_a].status,
        ranking.concepts[cid_b].status,
    }
    assert statuses == {"pending_fase5"}
    assert ranking.failures
    assert ranking.failures[0]["error_type"] == "authentication_error"


def test_circuit_breaker_after_3_consecutive_per_concept_failures(tmp_path, monkeypatch):
    defs = load_concept_definitions()
    cids_pool = [c for c in ("architect_name", "client_name", "municipality", "num_floors")
                 if c in defs][:4]
    assert len(cids_pool) >= 4, "need 4 concepts for circuit-breaker test"

    analysis = _make_analysis(
        sources=[
            ("s1.pdf", [(c, "A", 0.9) for c in cids_pool]),
            ("s2.pdf", [(c, "B", 0.7) for c in cids_pool]),
        ]
    )
    project = _make_project_with_analysis(tmp_path, analysis)

    def behavior(call_num, kwargs):
        # Always invent → schema validation failure
        return _FakeResponse(
            _build_ranked_tool_input(["invented_only"])
        )

    import automation.ai_pipeline.ranking as ranking_mod

    monkeypatch.setattr(ranking_mod, "_BACKOFF_INITIAL_S", 0.0)
    client = _FakeAnthropicClient(behavior)
    ranking = rank_project(
        project,
        analysis=analysis,
        client=client,
        concept_filter=set(cids_pool),
    )

    # 3 concepts × 3 retries each = 9 calls max; after 3 failures the 4th
    # concept must not be attempted.
    for c in cids_pool:
        assert ranking.concepts[c].status == "pending_fase5"
    assert any(f["error_type"] == "circuit_breaker" for f in ranking.failures)
    # Calls to the 4th concept: none.
    # After 3 failed concepts (9 calls total max), no more.
    assert client.messages.calls <= 9


# ─── Concept filter ────────────────────────────────────────────────────


def test_concept_filter_restricts_ranking_work(tmp_path):
    cid_a = "architect_name"
    cid_b = "client_name"
    defs = load_concept_definitions()
    for c in (cid_a, cid_b):
        assert c in defs

    analysis = _make_analysis(
        sources=[
            ("s1.pdf", [(cid_a, "X", 0.9), (cid_b, "P", 0.9)]),
            ("s2.pdf", [(cid_a, "Y", 0.7), (cid_b, "Q", 0.7)]),
        ]
    )
    project = _make_project_with_analysis(tmp_path, analysis)

    cids_a = _expected_candidate_ids(analysis, cid_a)

    def behavior(call_num, kwargs):
        return _FakeResponse(_build_ranked_tool_input(cids_a))

    client = _FakeAnthropicClient(behavior)
    ranking = rank_project(
        project, analysis=analysis, client=client, concept_filter=cid_a,
    )

    # Only cid_a was ranked; cid_b is absent from the ranking.
    assert ranking.concepts[cid_a].status == "ranked"
    assert cid_b not in ranking.concepts
    assert client.messages.calls == 1


# ─── Invented / omitted candidate guard ────────────────────────────────


def test_rejects_ranking_with_invented_candidate_id(tmp_path, monkeypatch):
    cid = _pick_multi_candidate_concept()
    analysis = _make_multi_analysis(
        cid, [("a.pdf", "X", 0.9), ("b.pdf", "Y", 0.7)]
    )
    project = _make_project_with_analysis(tmp_path, analysis)

    def behavior(call_num, kwargs):
        return _FakeResponse(
            _build_ranked_tool_input(["nonexistent_candidate"])
        )

    import automation.ai_pipeline.ranking as ranking_mod

    monkeypatch.setattr(ranking_mod, "_BACKOFF_INITIAL_S", 0.0)
    client = _FakeAnthropicClient(behavior)
    ranking = rank_project(
        project, analysis=analysis, client=client, concept_filter=cid,
    )

    assert ranking.concepts[cid].status == "pending_fase5"
    assert ranking.failures
    assert ranking.failures[0]["error_type"] == "schema_validation"


def test_rejects_ranking_with_missing_candidate_id(tmp_path, monkeypatch):
    cid = _pick_multi_candidate_concept()
    analysis = _make_multi_analysis(
        cid,
        [
            ("a.pdf", "X", 0.9),
            ("b.pdf", "Y", 0.7),
            ("c.pdf", "Z", 0.5),
        ],
    )
    project = _make_project_with_analysis(tmp_path, analysis)
    cids = _expected_candidate_ids(analysis, cid)

    def behavior(call_num, kwargs):
        # Only return 2 of the 3 required ids.
        return _FakeResponse(_build_ranked_tool_input(cids[:2]))

    import automation.ai_pipeline.ranking as ranking_mod

    monkeypatch.setattr(ranking_mod, "_BACKOFF_INITIAL_S", 0.0)
    client = _FakeAnthropicClient(behavior)
    ranking = rank_project(
        project, analysis=analysis, client=client, concept_filter=cid,
    )
    assert ranking.concepts[cid].status == "pending_fase5"
    assert ranking.failures[0]["error_type"] == "schema_validation"


# ─── Missing inputs ────────────────────────────────────────────────────


def test_rank_project_raises_when_no_analysis(tmp_path):
    project = tmp_path / "empty"
    project.mkdir()
    with pytest.raises(ValueError):
        rank_project(project)


def test_empty_principles_logs_warning_but_proceeds(tmp_path, monkeypatch, caplog):
    cid = _pick_multi_candidate_concept()
    analysis = _make_multi_analysis(
        cid, [("a.pdf", "X", 0.9), ("b.pdf", "Y", 0.7)]
    )
    project = _make_project_with_analysis(tmp_path, analysis)
    cids = _expected_candidate_ids(analysis, cid)

    import automation.ai_pipeline.ranking as ranking_mod

    monkeypatch.setattr(ranking_mod, "load_authority_principles", lambda: "")

    def behavior(call_num, kwargs):
        return _FakeResponse(_build_ranked_tool_input(cids))

    client = _FakeAnthropicClient(behavior)
    with caplog.at_level("WARNING", logger="automation.ai_pipeline.ranking"):
        ranking = rank_project(
            project, analysis=analysis, client=client, concept_filter=cid,
        )

    assert ranking.concepts[cid].status == "ranked"
    # Summary should mention the missing principles.
    joined = "\n".join(ranking.eva_summary)
    assert "authority_principles" in joined or "principis" in joined.lower()


# ─── Determinism / token counting ──────────────────────────────────────


def test_token_counts_only_from_fresh_calls_not_cache(tmp_path):
    cid = _pick_multi_candidate_concept()
    analysis = _make_multi_analysis(
        cid, [("a.pdf", "X", 0.9), ("b.pdf", "Y", 0.7)]
    )
    project = _make_project_with_analysis(tmp_path, analysis)
    cids = _expected_candidate_ids(analysis, cid)

    def behavior(call_num, kwargs):
        return _FakeResponse(_build_ranked_tool_input(cids))

    client = _FakeAnthropicClient(behavior)
    first = rank_project(
        project, analysis=analysis, client=client, concept_filter=cid,
    )
    assert first.total_input_tokens > 0
    first_input = first.total_input_tokens

    client2 = _FakeAnthropicClient(behavior)
    second = rank_project(
        project, analysis=analysis, client=client2, concept_filter=cid,
    )
    # Cache hit — tokens from this run are zero; not doubled.
    assert second.total_input_tokens == 0
    assert second.cache_hits == 1
    # First run's tokens don't carry over to second run's total.
    assert second.total_input_tokens != first_input


# ─── Model selection ───────────────────────────────────────────────────


def test_env_var_model_override(tmp_path, monkeypatch):
    cid = _pick_multi_candidate_concept()
    analysis = _make_multi_analysis(
        cid, [("a.pdf", "X", 0.9), ("b.pdf", "Y", 0.7)]
    )
    project = _make_project_with_analysis(tmp_path, analysis)
    cids = _expected_candidate_ids(analysis, cid)

    monkeypatch.setenv("G3DT_AI_MODEL_RANKER", "claude-opus-4-7")

    def behavior(call_num, kwargs):
        return _FakeResponse(_build_ranked_tool_input(cids))

    client = _FakeAnthropicClient(behavior)
    rank_project(project, analysis=analysis, client=client, concept_filter=cid)

    assert client.messages.kwargs_history
    assert client.messages.kwargs_history[0].get("model") == "claude-opus-4-7"


# ─── Cost estimate: cache tokens priced ────────────────────────────────


def test_cost_estimate_prices_cache_tokens(tmp_path):
    cid = _pick_multi_candidate_concept()
    analysis = _make_multi_analysis(
        cid, [("a.pdf", "X", 0.9), ("b.pdf", "Y", 0.7)]
    )
    project = _make_project_with_analysis(tmp_path, analysis)
    cids = _expected_candidate_ids(analysis, cid)

    class _UsageWithCache:
        def __init__(self):
            self.input_tokens = 0
            self.output_tokens = 0
            self.cache_creation_input_tokens = 1000
            self.cache_read_input_tokens = 2000

    class _RespWithCache:
        def __init__(self, tool_input):
            self.content = [
                SimpleNamespace(
                    type="tool_use", name="emit_ranking", input=tool_input
                )
            ]
            self.usage = _UsageWithCache()

    def behavior(call_num, kwargs):
        return _RespWithCache(_build_ranked_tool_input(cids))

    client = _FakeAnthropicClient(behavior)
    ranking = rank_project(
        project,
        analysis=analysis,
        client=client,
        concept_filter=cid,
        model="claude-sonnet-4-6",
    )

    # Expected: (0*3 + 1000*3*1.25 + 2000*3*0.1 + 0*15) / 1e6
    # = (3750 + 600) / 1e6 = 0.00435
    assert ranking.total_cache_creation_tokens == 1000
    assert ranking.total_cache_read_tokens == 2000
    assert abs(ranking.estimated_cost_usd - 0.00435) < 1e-6


# ─── Cache invalidation: glossary / concept_def changes ────────────────


def test_concept_cache_invalidated_by_glossary_change(tmp_path, monkeypatch):
    cid = _pick_multi_candidate_concept()
    analysis = _make_multi_analysis(
        cid, [("a.pdf", "X", 0.9), ("b.pdf", "Y", 0.7)]
    )
    project = _make_project_with_analysis(tmp_path, analysis)
    cids = _expected_candidate_ids(analysis, cid)

    def behavior(call_num, kwargs):
        return _FakeResponse(_build_ranked_tool_input(cids))

    import automation.ai_pipeline.ranking as ranking_mod

    # Prime cache with glossary entry v1.
    monkeypatch.setattr(
        ranking_mod, "load_glossary_entry", lambda c: "hint: version-1 text"
    )
    client = _FakeAnthropicClient(behavior)
    rank_project(project, analysis=analysis, client=client, concept_filter=cid)
    assert client.messages.calls == 1

    # Change glossary entry → cache must miss.
    monkeypatch.setattr(
        ranking_mod, "load_glossary_entry", lambda c: "hint: COMPLETELY DIFFERENT"
    )
    client2 = _FakeAnthropicClient(behavior)
    second = rank_project(
        project, analysis=analysis, client=client2, concept_filter=cid,
    )
    assert client2.messages.calls == 1
    assert second.cache_hits == 0


def test_concept_cache_invalidated_by_concept_def_change(tmp_path, monkeypatch):
    cid = _pick_multi_candidate_concept()
    analysis = _make_multi_analysis(
        cid, [("a.pdf", "X", 0.9), ("b.pdf", "Y", 0.7)]
    )
    project = _make_project_with_analysis(tmp_path, analysis)
    cids = _expected_candidate_ids(analysis, cid)

    def behavior(call_num, kwargs):
        return _FakeResponse(_build_ranked_tool_input(cids))

    import automation.ai_pipeline.ranking as ranking_mod

    # Prime cache with the real concept definitions.
    real_defs = ranking_mod.load_concept_definitions()
    client = _FakeAnthropicClient(behavior)
    rank_project(project, analysis=analysis, client=client, concept_filter=cid)
    assert client.messages.calls == 1

    # Mutate the concept's description_ca → cache must miss.
    mutated = {k: dict(v) for k, v in real_defs.items()}
    mutated[cid]["description_ca"] = "MUTATED description for cache invalidation"
    monkeypatch.setattr(
        ranking_mod, "load_concept_definitions", lambda: mutated
    )
    client2 = _FakeAnthropicClient(behavior)
    second = rank_project(
        project, analysis=analysis, client=client2, concept_filter=cid,
    )
    assert client2.messages.calls == 1
    assert second.cache_hits == 0


# ─── Empty-response retry keeps full prompt ────────────────────────────


def test_empty_response_retry_keeps_full_prompt(tmp_path, monkeypatch):
    cid = _pick_multi_candidate_concept()
    analysis = _make_multi_analysis(
        cid, [("a.pdf", "X", 0.9), ("b.pdf", "Y", 0.7)]
    )
    project = _make_project_with_analysis(tmp_path, analysis)
    cids = _expected_candidate_ids(analysis, cid)

    class _EmptyResponse:
        def __init__(self):
            # No tool_use block at all.
            self.content = []
            self.usage = _FakeUsage()

    def behavior(call_num, kwargs):
        if call_num == 1:
            return _EmptyResponse()
        return _FakeResponse(_build_ranked_tool_input(cids))

    import automation.ai_pipeline.ranking as ranking_mod

    monkeypatch.setattr(ranking_mod, "_BACKOFF_INITIAL_S", 0.0)
    client = _FakeAnthropicClient(behavior)
    ranking = rank_project(
        project, analysis=analysis, client=client, concept_filter=cid,
    )

    assert client.messages.calls == 2
    # Both calls must retain the principles block — empty-response is transient,
    # not a schema violation, so we do NOT trim the prompt.
    assert _has_principles_block(client.messages.kwargs_history[0])
    assert _has_principles_block(client.messages.kwargs_history[1])
    cr = ranking.ranking_of(cid)
    assert cr is not None
    assert cr.status == "ranked"
