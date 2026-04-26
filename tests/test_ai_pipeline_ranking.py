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


# ═══════════════════════════════════════════════════════════════════════
# Chunk 3 — Pass B (group auditor) + Pass C (targeted revision) tests
# ═══════════════════════════════════════════════════════════════════════


def _build_group_audit_tool_input(
    factors: list[dict],
    revisions: list[dict],
) -> dict:
    return {"factors": factors, "revisions": revisions}


class _FakeGroupResponse:
    """Simulates an Anthropic response containing an `emit_group_audit` call."""

    def __init__(self, tool_input: dict):
        self.content = [
            SimpleNamespace(
                type="tool_use", name="emit_group_audit", input=tool_input
            )
        ]
        self.usage = _FakeUsage()


def _pick_group_with_two_concepts() -> tuple[str, list[str]]:
    """Return (group_name, [concept_id, concept_id]) for a group with ≥2
    simple (text) concepts in the real schema.
    """
    defs = load_concept_definitions()
    from collections import defaultdict
    by_group: dict[str, list[str]] = defaultdict(list)
    for cid, meta in defs.items():
        by_group[meta["group"]].append(cid)
    # Prefer `location` (has street_address + municipality + province).
    for preferred in ("location", "client", "building", "architect"):
        if len(by_group.get(preferred, [])) >= 2:
            return preferred, sorted(by_group[preferred])[:3]
    # Fallback: any group with ≥2 concepts.
    for g, items in sorted(by_group.items()):
        if len(items) >= 2:
            return g, sorted(items)[:3]
    raise RuntimeError("no group with ≥2 concepts in schema")


def _multi_analysis_for_concepts(
    concept_values: dict[str, list[tuple[str, str, float]]],
) -> ProjectAnalysis:
    """Build an analysis given `{concept_id: [(source_path, value, conf), ...]}`."""
    sources_map: dict[str, list[tuple[str, object, float]]] = {}
    for cid, vals in concept_values.items():
        for sp, v, c in vals:
            sources_map.setdefault(sp, []).append((cid, v, c))
    sources_list = list(sources_map.items())
    return _make_analysis(sources_list)


# ─── Pass B — auditor tests ────────────────────────────────────────────


def test_audit_group_happy_path(tmp_path):
    group_name, cids = _pick_group_with_two_concepts()
    cids = cids[:3]
    analysis = _multi_analysis_for_concepts(
        {cid: [("a.pdf", f"val_a_{cid}", 0.9), ("b.pdf", f"val_b_{cid}", 0.7)]
         for cid in cids}
    )
    project = _make_project_with_analysis(tmp_path, analysis)

    pass_a_expected = {
        cid: _expected_candidate_ids(analysis, cid) for cid in cids
    }

    call_log = []

    def behavior(call_num, kwargs):
        call_log.append(("tool" if kwargs.get("tools", [{}])[0].get("name") == "emit_group_audit" else "rank", kwargs))
        system = kwargs.get("system", "")
        if "emit_group_audit" in str(kwargs.get("tools", "")) or "grup" in system.lower():
            # Group audit call
            return _FakeGroupResponse(
                _build_group_audit_tool_input(
                    factors=[{"description": "v2 supersedes v1 across group",
                              "affects": [cids[0]]}],
                    revisions=[
                        {"concept_id": cid,
                         "revise": (cid == cids[0]),
                         "reason": "sample"}
                        for cid in cids
                    ],
                )
            )
        # Per-concept Pass A (or Pass C) call — return plain Pass-A ranking.
        cid = _extract_cid_from_kwargs(kwargs)
        ordered = pass_a_expected[cid]
        # Pass C: if Group-level signal block is present, reorder (swap).
        if _has_group_signal_block(kwargs) and cid == cids[0]:
            ordered = list(reversed(ordered))
        return _FakeResponse(_build_ranked_tool_input(ordered))

    client = _FakeAnthropicClient(behavior)
    ranking = rank_project(
        project,
        analysis=analysis,
        client=client,
        concept_filter=set(cids),
    )

    assert group_name in ranking.groups
    result = ranking.groups[group_name]
    assert result.skipped_reason == ""
    assert len(result.factors) == 1
    assert len(result.revisions) == len(cids)
    # Pass C applied: cids[0] was revised.
    revised = ranking.concepts[cids[0]]
    assert revised.revised_by_group_pass is True
    assert revised.group_factor_considered
    # cids[1] not revised.
    assert ranking.concepts[cids[1]].revised_by_group_pass is False


def _extract_cid_from_kwargs(kwargs: dict) -> str:
    # Extract concept_id from the user content's `**concept_id**:` marker.
    import re as _re
    for msg in kwargs.get("messages", []) or []:
        for block in msg.get("content", []) or []:
            if not isinstance(block, dict):
                continue
            m = _re.search(r"\*\*concept_id\*\*:\s*`([^`]+)`", block.get("text", ""))
            if m:
                return m.group(1)
    return ""


def _has_group_signal_block(kwargs: dict) -> bool:
    for msg in kwargs.get("messages", []) or []:
        for block in msg.get("content", []) or []:
            if not isinstance(block, dict):
                continue
            if "# Group-level signal" in block.get("text", ""):
                return True
    return False


def test_audit_group_skipped_when_too_few_ranked_concepts(tmp_path):
    """Only 1 ranked concept in a group → Pass B skipped with reason."""
    group_name, cids = _pick_group_with_two_concepts()
    cid_ranked = cids[0]
    # Single concept with multiple candidates; rest of group not in analysis.
    analysis = _multi_analysis_for_concepts(
        {cid_ranked: [("a.pdf", "X", 0.9), ("b.pdf", "Y", 0.7)]}
    )
    project = _make_project_with_analysis(tmp_path, analysis)
    ordered = _expected_candidate_ids(analysis, cid_ranked)

    group_audit_calls = 0

    def behavior(call_num, kwargs):
        nonlocal group_audit_calls
        if "emit_group_audit" in str(kwargs.get("tools", "")):
            group_audit_calls += 1
            return _FakeGroupResponse(
                _build_group_audit_tool_input([], [])
            )
        return _FakeResponse(_build_ranked_tool_input(ordered))

    client = _FakeAnthropicClient(behavior)
    ranking = rank_project(
        project,
        analysis=analysis,
        client=client,
        concept_filter=cid_ranked,
    )

    # No group audit happened for this group.
    assert group_audit_calls == 0
    # Either the group is absent from `ranking.groups`, or present with
    # skipped_reason set. Our orchestrator only processes groups that have
    # at least one ranked concept — which this one does — so we expect it
    # to appear marked-skipped.
    g = ranking.groups.get(group_name)
    assert g is not None
    assert g.skipped_reason
    assert "need" in g.skipped_reason or "ranked" in g.skipped_reason


def test_audit_group_skips_non_ranked_concepts_in_group_size_count(tmp_path):
    """2 single + 1 ranked in group → still only 1 rankable → skip."""
    group_name, cids = _pick_group_with_two_concepts()
    if len(cids) < 3:
        pytest.skip("need a group with 3+ concepts for this test")
    ranked_cid = cids[0]
    single_a = cids[1]
    single_b = cids[2]

    # ranked_cid: 2 candidates (ranked); single_a/b: 1 candidate each (single).
    sources_map: dict[str, list] = {
        "a.pdf": [(ranked_cid, "X", 0.9), (single_a, "Va", 0.9)],
        "b.pdf": [(ranked_cid, "Y", 0.7), (single_b, "Vb", 0.9)],
    }
    analysis = _make_analysis(list(sources_map.items()))
    project = _make_project_with_analysis(tmp_path, analysis)
    ordered = _expected_candidate_ids(analysis, ranked_cid)

    group_audit_calls = 0

    def behavior(call_num, kwargs):
        nonlocal group_audit_calls
        if "emit_group_audit" in str(kwargs.get("tools", "")):
            group_audit_calls += 1
            return _FakeGroupResponse(_build_group_audit_tool_input([], []))
        return _FakeResponse(_build_ranked_tool_input(ordered))

    client = _FakeAnthropicClient(behavior)
    ranking = rank_project(
        project,
        analysis=analysis,
        client=client,
        concept_filter={ranked_cid, single_a, single_b},
    )

    assert group_audit_calls == 0
    # The group in question should be recorded as skipped.
    g = ranking.groups.get(group_name)
    assert g is not None
    assert g.skipped_reason


def test_audit_group_filters_out_alien_concept_ids_from_affects(tmp_path):
    group_name, cids = _pick_group_with_two_concepts()
    cids = cids[:2]
    analysis = _multi_analysis_for_concepts(
        {cid: [("a.pdf", "X", 0.9), ("b.pdf", "Y", 0.7)] for cid in cids}
    )
    project = _make_project_with_analysis(tmp_path, analysis)
    pass_a = {cid: _expected_candidate_ids(analysis, cid) for cid in cids}

    def behavior(call_num, kwargs):
        if "emit_group_audit" in str(kwargs.get("tools", "")):
            # Two factors: one with a real + alien, one with only aliens.
            return _FakeGroupResponse(
                _build_group_audit_tool_input(
                    factors=[
                        {"description": "mixed factor",
                         "affects": [cids[0], "nonexistent_id"]},
                        {"description": "all-alien factor",
                         "affects": ["foo", "bar"]},
                    ],
                    revisions=[
                        {"concept_id": cid, "revise": False, "reason": ""}
                        for cid in cids
                    ],
                )
            )
        cid = _extract_cid_from_kwargs(kwargs)
        return _FakeResponse(_build_ranked_tool_input(pass_a[cid]))

    client = _FakeAnthropicClient(behavior)
    ranking = rank_project(
        project, analysis=analysis, client=client, concept_filter=set(cids),
    )

    g = ranking.groups[group_name]
    # All-alien factor dropped; mixed factor kept with only real id.
    assert len(g.factors) == 1
    assert g.factors[0]["affects"] == [cids[0]]


def test_audit_group_rejects_revisions_referring_unknown_concept(tmp_path, monkeypatch):
    group_name, cids = _pick_group_with_two_concepts()
    cids = cids[:2]
    analysis = _multi_analysis_for_concepts(
        {cid: [("a.pdf", "X", 0.9), ("b.pdf", "Y", 0.7)] for cid in cids}
    )
    project = _make_project_with_analysis(tmp_path, analysis)
    pass_a = {cid: _expected_candidate_ids(analysis, cid) for cid in cids}

    import automation.ai_pipeline.ranking as ranking_mod
    monkeypatch.setattr(ranking_mod, "_BACKOFF_INITIAL_S", 0.0)

    call_num_holder = {"n": 0}

    def behavior(call_num, kwargs):
        if "emit_group_audit" in str(kwargs.get("tools", "")):
            call_num_holder["n"] += 1
            if call_num_holder["n"] == 1:
                # Bad: alien revision concept_id.
                return _FakeGroupResponse(
                    _build_group_audit_tool_input(
                        factors=[],
                        revisions=[
                            {"concept_id": "not_a_real_concept",
                             "revise": False, "reason": ""},
                        ],
                    )
                )
            # Good: proper revisions.
            return _FakeGroupResponse(
                _build_group_audit_tool_input(
                    factors=[],
                    revisions=[
                        {"concept_id": cid, "revise": False, "reason": ""}
                        for cid in cids
                    ],
                )
            )
        cid = _extract_cid_from_kwargs(kwargs)
        return _FakeResponse(_build_ranked_tool_input(pass_a[cid]))

    client = _FakeAnthropicClient(behavior)
    ranking = rank_project(
        project, analysis=analysis, client=client, concept_filter=set(cids),
    )
    # Group passed on retry.
    g = ranking.groups[group_name]
    assert g.skipped_reason == ""
    assert call_num_holder["n"] == 2


def test_audit_group_cache_miss_then_hit(tmp_path):
    group_name, cids = _pick_group_with_two_concepts()
    cids = cids[:2]
    analysis = _multi_analysis_for_concepts(
        {cid: [("a.pdf", "X", 0.9), ("b.pdf", "Y", 0.7)] for cid in cids}
    )
    project = _make_project_with_analysis(tmp_path, analysis)
    pass_a = {cid: _expected_candidate_ids(analysis, cid) for cid in cids}

    def behavior(call_num, kwargs):
        if "emit_group_audit" in str(kwargs.get("tools", "")):
            return _FakeGroupResponse(
                _build_group_audit_tool_input(
                    factors=[],
                    revisions=[
                        {"concept_id": cid, "revise": False, "reason": ""}
                        for cid in cids
                    ],
                )
            )
        cid = _extract_cid_from_kwargs(kwargs)
        return _FakeResponse(_build_ranked_tool_input(pass_a[cid]))

    client = _FakeAnthropicClient(behavior)
    rank_project(project, analysis=analysis, client=client, concept_filter=set(cids))
    first_calls = client.messages.calls
    group_calls_first = sum(
        1 for kw in client.messages.kwargs_history
        if "emit_group_audit" in str(kw.get("tools", ""))
    )
    assert group_calls_first == 1

    # Second run: Pass A concept calls are also cached — so no calls at all.
    client2 = _FakeAnthropicClient(behavior)
    rank_project(project, analysis=analysis, client=client2, concept_filter=set(cids))
    group_calls_second = sum(
        1 for kw in client2.messages.kwargs_history
        if "emit_group_audit" in str(kw.get("tools", ""))
    )
    assert group_calls_second == 0


def test_audit_group_cache_invalidated_by_principles_change(tmp_path, monkeypatch):
    group_name, cids = _pick_group_with_two_concepts()
    cids = cids[:2]
    analysis = _multi_analysis_for_concepts(
        {cid: [("a.pdf", "X", 0.9), ("b.pdf", "Y", 0.7)] for cid in cids}
    )
    project = _make_project_with_analysis(tmp_path, analysis)
    pass_a = {cid: _expected_candidate_ids(analysis, cid) for cid in cids}

    def behavior(call_num, kwargs):
        if "emit_group_audit" in str(kwargs.get("tools", "")):
            return _FakeGroupResponse(
                _build_group_audit_tool_input(
                    factors=[],
                    revisions=[
                        {"concept_id": cid, "revise": False, "reason": ""}
                        for cid in cids
                    ],
                )
            )
        cid = _extract_cid_from_kwargs(kwargs)
        return _FakeResponse(_build_ranked_tool_input(pass_a[cid]))

    import automation.ai_pipeline.ranking as ranking_mod
    monkeypatch.setattr(ranking_mod, "load_authority_principles", lambda: "P1")
    client = _FakeAnthropicClient(behavior)
    rank_project(project, analysis=analysis, client=client, concept_filter=set(cids))
    assert any(
        "emit_group_audit" in str(kw.get("tools", ""))
        for kw in client.messages.kwargs_history
    )

    monkeypatch.setattr(
        ranking_mod, "load_authority_principles", lambda: "P2 — DIFFERENT"
    )
    client2 = _FakeAnthropicClient(behavior)
    rank_project(project, analysis=analysis, client=client2, concept_filter=set(cids))
    # Principles changed → group cache must re-run.
    assert any(
        "emit_group_audit" in str(kw.get("tools", ""))
        for kw in client2.messages.kwargs_history
    )


def test_audit_group_systemic_error_skips_remaining_groups(tmp_path):
    """First Pass B call raises 401 → remaining groups marked skipped."""
    # Two groups each with ≥2 ranked concepts.
    defs = load_concept_definitions()
    from collections import defaultdict
    by_group = defaultdict(list)
    for cid, m in defs.items():
        by_group[m["group"]].append(cid)

    groups_with_two = sorted(
        g for g, items in by_group.items() if len(items) >= 2
    )
    if len(groups_with_two) < 2:
        pytest.skip("need at least 2 groups with ≥2 concepts")
    g1 = groups_with_two[0]
    g2 = groups_with_two[1]
    cids_g1 = sorted(by_group[g1])[:2]
    cids_g2 = sorted(by_group[g2])[:2]
    all_cids = cids_g1 + cids_g2

    analysis = _multi_analysis_for_concepts(
        {cid: [("a.pdf", "X", 0.9), ("b.pdf", "Y", 0.7)] for cid in all_cids}
    )
    project = _make_project_with_analysis(tmp_path, analysis)
    pass_a = {cid: _expected_candidate_ids(analysis, cid) for cid in all_cids}

    def behavior(call_num, kwargs):
        if "emit_group_audit" in str(kwargs.get("tools", "")):
            raise RuntimeError("AuthenticationError: invalid API key (401)")
        cid = _extract_cid_from_kwargs(kwargs)
        return _FakeResponse(_build_ranked_tool_input(pass_a[cid]))

    client = _FakeAnthropicClient(behavior)
    ranking = rank_project(
        project, analysis=analysis, client=client, concept_filter=set(all_cids),
    )

    # First failure logged in `failures`.
    assert any(f.get("error_type") == "authentication_error" for f in ranking.failures)
    # Other group marked skipped.
    g2_result = ranking.groups.get(g2)
    assert g2_result is not None
    assert "systemic" in g2_result.skipped_reason


# ─── Pass C — revision tests ───────────────────────────────────────────


def test_revise_concept_applies_group_factor_to_prompt(tmp_path):
    group_name, cids = _pick_group_with_two_concepts()
    cids = cids[:2]
    analysis = _multi_analysis_for_concepts(
        {cid: [("a.pdf", "X", 0.9), ("b.pdf", "Y", 0.7)] for cid in cids}
    )
    project = _make_project_with_analysis(tmp_path, analysis)
    pass_a = {cid: _expected_candidate_ids(analysis, cid) for cid in cids}

    factor_text = "THE ONE SPECIFIC FACTOR for cids[0]"

    def behavior(call_num, kwargs):
        if "emit_group_audit" in str(kwargs.get("tools", "")):
            return _FakeGroupResponse(
                _build_group_audit_tool_input(
                    factors=[{"description": factor_text,
                              "affects": [cids[0]]}],
                    revisions=[
                        {"concept_id": cids[0], "revise": True, "reason": "go"},
                        {"concept_id": cids[1], "revise": False, "reason": ""},
                    ],
                )
            )
        cid = _extract_cid_from_kwargs(kwargs)
        ordered = pass_a[cid]
        if _has_group_signal_block(kwargs):
            ordered = list(reversed(ordered))
        return _FakeResponse(_build_ranked_tool_input(ordered))

    client = _FakeAnthropicClient(behavior)
    rank_project(project, analysis=analysis, client=client, concept_filter=set(cids))

    # Find the Pass C call for cids[0] — must include the factor text.
    found = False
    for kw in client.messages.kwargs_history:
        if _has_group_signal_block(kw) and _extract_cid_from_kwargs(kw) == cids[0]:
            text_joined = _user_text(kw)
            assert factor_text in text_joined
            found = True
    assert found


def test_revise_concept_happy_path_reorders(tmp_path):
    group_name, cids = _pick_group_with_two_concepts()
    cids = cids[:2]
    analysis = _multi_analysis_for_concepts(
        {cid: [("a.pdf", "X", 0.9), ("b.pdf", "Y", 0.7)] for cid in cids}
    )
    project = _make_project_with_analysis(tmp_path, analysis)
    pass_a = {cid: _expected_candidate_ids(analysis, cid) for cid in cids}

    def behavior(call_num, kwargs):
        if "emit_group_audit" in str(kwargs.get("tools", "")):
            return _FakeGroupResponse(
                _build_group_audit_tool_input(
                    factors=[{"description": "v2 supersedes v1",
                              "affects": [cids[0]]}],
                    revisions=[
                        {"concept_id": cids[0], "revise": True, "reason": "go"},
                        {"concept_id": cids[1], "revise": False, "reason": ""},
                    ],
                )
            )
        cid = _extract_cid_from_kwargs(kwargs)
        if _has_group_signal_block(kwargs) and cid == cids[0]:
            return _FakeResponse(
                _build_ranked_tool_input(list(reversed(pass_a[cid])))
            )
        return _FakeResponse(_build_ranked_tool_input(pass_a[cid]))

    client = _FakeAnthropicClient(behavior)
    ranking = rank_project(
        project, analysis=analysis, client=client, concept_filter=set(cids),
    )

    revised = ranking.concepts[cids[0]]
    # First in the new order is the last of the original (reversed).
    assert revised.ranked[0].candidate_id == pass_a[cids[0]][-1]
    assert revised.revised_by_group_pass is True
    assert "v2 supersedes v1" in revised.group_factor_considered


def test_revise_concept_no_change_guardrail_keeps_original(tmp_path):
    group_name, cids = _pick_group_with_two_concepts()
    cids = cids[:2]
    analysis = _multi_analysis_for_concepts(
        {cid: [("a.pdf", "X", 0.9), ("b.pdf", "Y", 0.7)] for cid in cids}
    )
    project = _make_project_with_analysis(tmp_path, analysis)
    pass_a = {cid: _expected_candidate_ids(analysis, cid) for cid in cids}

    def behavior(call_num, kwargs):
        if "emit_group_audit" in str(kwargs.get("tools", "")):
            return _FakeGroupResponse(
                _build_group_audit_tool_input(
                    factors=[{"description": "nothing-changing factor",
                              "affects": [cids[0]]}],
                    revisions=[
                        {"concept_id": cids[0], "revise": True, "reason": "go"},
                        {"concept_id": cids[1], "revise": False, "reason": ""},
                    ],
                )
            )
        cid = _extract_cid_from_kwargs(kwargs)
        # Both Pass A and Pass C return same order.
        return _FakeResponse(_build_ranked_tool_input(pass_a[cid]))

    client = _FakeAnthropicClient(behavior)
    ranking = rank_project(
        project, analysis=analysis, client=client, concept_filter=set(cids),
    )

    revised = ranking.concepts[cids[0]]
    assert revised.revised_by_group_pass is False
    assert revised.group_factor_considered
    # Order unchanged.
    assert [r.candidate_id for r in revised.ranked] == pass_a[cids[0]]


def test_revise_concept_cache_separate_from_pass_a(tmp_path):
    group_name, cids = _pick_group_with_two_concepts()
    cids = cids[:2]
    analysis = _multi_analysis_for_concepts(
        {cid: [("a.pdf", "X", 0.9), ("b.pdf", "Y", 0.7)] for cid in cids}
    )
    project = _make_project_with_analysis(tmp_path, analysis)
    pass_a = {cid: _expected_candidate_ids(analysis, cid) for cid in cids}

    def behavior(call_num, kwargs):
        if "emit_group_audit" in str(kwargs.get("tools", "")):
            return _FakeGroupResponse(
                _build_group_audit_tool_input(
                    factors=[{"description": "factor",
                              "affects": [cids[0]]}],
                    revisions=[
                        {"concept_id": cids[0], "revise": True, "reason": ""},
                        {"concept_id": cids[1], "revise": False, "reason": ""},
                    ],
                )
            )
        cid = _extract_cid_from_kwargs(kwargs)
        ordered = pass_a[cid]
        if _has_group_signal_block(kwargs) and cid == cids[0]:
            ordered = list(reversed(ordered))
        return _FakeResponse(_build_ranked_tool_input(ordered))

    client = _FakeAnthropicClient(behavior)
    rank_project(project, analysis=analysis, client=client, concept_filter=set(cids))

    import automation.ai_pipeline.ranking as ranking_mod

    pp = project.resolve()
    pass_a_cache = ranking_mod._concept_cache_path(pp, cids[0])
    pass_c_cache = ranking_mod._revised_cache_path(pp, cids[0])
    assert pass_a_cache.is_file()
    assert pass_c_cache.is_file()
    assert pass_a_cache != pass_c_cache


def test_revise_concept_cache_invalidated_by_group_factor_change(tmp_path):
    """Pass C cache key mixes in `group_factor`: changing the factor text
    between runs (with identical concept_def / candidates / principles) must
    cause a cache MISS and a fresh LLM call. Guard for ranking.py:1426-1428.
    """
    cid = _pick_multi_candidate_concept()
    analysis = _make_multi_analysis(
        cid, [("a.pdf", "X", 0.9), ("b.pdf", "Y", 0.7)]
    )
    project = _make_project_with_analysis(tmp_path, analysis)
    pp = project.resolve()
    (pp / "validation" / "ai_pipeline" / "ranking").mkdir(parents=True, exist_ok=True)
    cids_list = _expected_candidate_ids(analysis, cid)

    import automation.ai_pipeline.ranking as ranking_mod

    concept_def = ranking_mod.load_concept_definitions()[cid]
    by_concept = ranking_mod._extract_candidates_by_concept(analysis)
    entries = by_concept[cid]
    principles = "P-test"
    model = ranking_mod._DEFAULT_MODEL

    original = ConceptRanking(
        concept_id=cid,
        status="ranked",
        ranked=[
            RankedCandidate(
                candidate_id=c_id,
                source_path=c_id.split("::")[0],
                value="X",
                confidence=0.9,
                rationale="pass-A",
            )
            for c_id in cids_list
        ],
    )

    def behavior(call_num, kwargs):
        # Pass C always returns a reversed order so the no-change guardrail
        # does not fire — we want a genuine write to the revise cache.
        return _FakeResponse(_build_ranked_tool_input(list(reversed(cids_list))))

    # ─── Run 1: factor "A" ──
    client1 = _FakeAnthropicClient(behavior)
    revised1, failure1, systemic1, _ = ranking_mod._revise_one_concept(
        client1,
        pp,
        concept_def,
        entries,
        model,
        principles,
        "factor-A",
        original,
    )
    assert failure1 is None and not systemic1
    assert revised1 is not None
    assert client1.messages.calls == 1
    assert ranking_mod._revised_cache_path(pp, cid).is_file()

    # ─── Run 2: same factor "A" → must HIT cache, no new call ──
    client2 = _FakeAnthropicClient(behavior)
    revised2, failure2, systemic2, _ = ranking_mod._revise_one_concept(
        client2,
        pp,
        concept_def,
        entries,
        model,
        principles,
        "factor-A",
        original,
    )
    assert failure2 is None and not systemic2
    assert revised2 is not None
    assert client2.messages.calls == 0  # cache hit

    # ─── Run 3: factor "B" (different text) → must MISS cache ──
    client3 = _FakeAnthropicClient(behavior)
    revised3, failure3, systemic3, _ = ranking_mod._revise_one_concept(
        client3,
        pp,
        concept_def,
        entries,
        model,
        principles,
        "factor-B",
        original,
    )
    assert failure3 is None and not systemic3
    assert revised3 is not None
    assert client3.messages.calls == 1  # cache miss → fresh call


def test_revise_concept_cap_max_revisions_per_group(tmp_path, monkeypatch):
    """7 revisions flagged → only _MAX_REVISIONS_PER_GROUP=5 actually revised."""
    # Need a group with ≥7 concepts. Use `parcel` if available; else skip.
    defs = load_concept_definitions()
    from collections import defaultdict
    by_group = defaultdict(list)
    for cid, m in defs.items():
        by_group[m["group"]].append(cid)

    big_groups = [g for g, items in by_group.items() if len(items) >= 7]
    if not big_groups:
        pytest.skip("no group with ≥7 concepts in schema")
    group_name = sorted(big_groups)[0]
    cids = sorted(by_group[group_name])[:7]

    analysis = _multi_analysis_for_concepts(
        {cid: [("a.pdf", "X", 0.9), ("b.pdf", "Y", 0.7)] for cid in cids}
    )
    project = _make_project_with_analysis(tmp_path, analysis)
    pass_a = {cid: _expected_candidate_ids(analysis, cid) for cid in cids}

    def behavior(call_num, kwargs):
        if "emit_group_audit" in str(kwargs.get("tools", "")):
            return _FakeGroupResponse(
                _build_group_audit_tool_input(
                    factors=[{"description": "all", "affects": cids}],
                    revisions=[
                        {"concept_id": cid, "revise": True, "reason": ""}
                        for cid in cids
                    ],
                )
            )
        cid = _extract_cid_from_kwargs(kwargs)
        ordered = pass_a[cid]
        if _has_group_signal_block(kwargs):
            ordered = list(reversed(ordered))
        return _FakeResponse(_build_ranked_tool_input(ordered))

    client = _FakeAnthropicClient(behavior)
    ranking = rank_project(
        project, analysis=analysis, client=client, concept_filter=set(cids),
    )

    n_revised = sum(1 for c in cids if ranking.concepts[c].revised_by_group_pass)
    import automation.ai_pipeline.ranking as ranking_mod
    assert n_revised == ranking_mod._MAX_REVISIONS_PER_GROUP


def test_revise_trimmed_retry_drops_group_factor_block(tmp_path, monkeypatch):
    group_name, cids = _pick_group_with_two_concepts()
    cids = cids[:2]
    analysis = _multi_analysis_for_concepts(
        {cid: [("a.pdf", "X", 0.9), ("b.pdf", "Y", 0.7)] for cid in cids}
    )
    project = _make_project_with_analysis(tmp_path, analysis)
    pass_a = {cid: _expected_candidate_ids(analysis, cid) for cid in cids}

    import automation.ai_pipeline.ranking as ranking_mod
    monkeypatch.setattr(ranking_mod, "_BACKOFF_INITIAL_S", 0.0)

    # Track per-concept call counts so the FIRST Pass C call for cids[0] fails
    # validation, and the retry succeeds without the group-signal block.
    pass_c_calls_for_target: dict[str, int] = {cids[0]: 0}

    def behavior(call_num, kwargs):
        if "emit_group_audit" in str(kwargs.get("tools", "")):
            return _FakeGroupResponse(
                _build_group_audit_tool_input(
                    factors=[{"description": "x", "affects": [cids[0]]}],
                    revisions=[
                        {"concept_id": cids[0], "revise": True, "reason": ""},
                        {"concept_id": cids[1], "revise": False, "reason": ""},
                    ],
                )
            )
        cid = _extract_cid_from_kwargs(kwargs)
        # Only the Pass C call for cids[0] is driven here; Pass A calls return
        # valid rankings normally.
        if _has_group_signal_block(kwargs) and cid == cids[0]:
            pass_c_calls_for_target[cid] += 1
            if pass_c_calls_for_target[cid] == 1:
                return _FakeResponse(
                    _build_ranked_tool_input(["invented_id"])
                )
            return _FakeResponse(_build_ranked_tool_input(list(reversed(pass_a[cid]))))
        # Pass C trimmed retry: no group-signal block — return valid ranking.
        if cid == cids[0] and pass_c_calls_for_target[cid] >= 1:
            return _FakeResponse(_build_ranked_tool_input(list(reversed(pass_a[cid]))))
        return _FakeResponse(_build_ranked_tool_input(pass_a[cid]))

    client = _FakeAnthropicClient(behavior)
    ranking = rank_project(
        project, analysis=analysis, client=client, concept_filter=set(cids),
    )

    # Look at the Pass C calls for cids[0].
    pass_c_kwargs = [
        kw for kw in client.messages.kwargs_history
        if _extract_cid_from_kwargs(kw) == cids[0]
        and "emit_group_audit" not in str(kw.get("tools", ""))
    ]
    # Split those into the ones with vs without the group-signal block. The
    # retry must be the call WITHOUT the signal block.
    without_signal = [kw for kw in pass_c_kwargs if not _has_group_signal_block(kw)]
    # There should be at least one Pass C call without the signal block (retry).
    assert without_signal
    # The final result is the revised (reversed) ranking.
    assert ranking.concepts[cids[0]].revised_by_group_pass is True


# ─── Orchestrator integration tests ────────────────────────────────────


def test_no_group_pass_flag_skips_b_and_c(tmp_path):
    group_name, cids = _pick_group_with_two_concepts()
    cids = cids[:2]
    analysis = _multi_analysis_for_concepts(
        {cid: [("a.pdf", "X", 0.9), ("b.pdf", "Y", 0.7)] for cid in cids}
    )
    project = _make_project_with_analysis(tmp_path, analysis)
    pass_a = {cid: _expected_candidate_ids(analysis, cid) for cid in cids}

    def behavior(call_num, kwargs):
        if "emit_group_audit" in str(kwargs.get("tools", "")):
            pytest.fail("Pass B must not be called when no_group_pass=True")
        cid = _extract_cid_from_kwargs(kwargs)
        return _FakeResponse(_build_ranked_tool_input(pass_a[cid]))

    client = _FakeAnthropicClient(behavior)
    ranking = rank_project(
        project,
        analysis=analysis,
        client=client,
        concept_filter=set(cids),
        no_group_pass=True,
    )

    assert ranking.groups == {}


def test_group_filter_restricts_audits(tmp_path):
    # Same construction as systemic test: two groups with ≥2 ranked concepts.
    defs = load_concept_definitions()
    from collections import defaultdict
    by_group = defaultdict(list)
    for cid, m in defs.items():
        by_group[m["group"]].append(cid)

    groups_with_two = sorted(g for g, items in by_group.items() if len(items) >= 2)
    if len(groups_with_two) < 2:
        pytest.skip("need at least 2 groups with ≥2 concepts")
    g1, g2 = groups_with_two[:2]
    cids_g1 = sorted(by_group[g1])[:2]
    cids_g2 = sorted(by_group[g2])[:2]
    all_cids = cids_g1 + cids_g2

    analysis = _multi_analysis_for_concepts(
        {cid: [("a.pdf", "X", 0.9), ("b.pdf", "Y", 0.7)] for cid in all_cids}
    )
    project = _make_project_with_analysis(tmp_path, analysis)
    pass_a = {cid: _expected_candidate_ids(analysis, cid) for cid in all_cids}

    def behavior(call_num, kwargs):
        if "emit_group_audit" in str(kwargs.get("tools", "")):
            # Determine which group this is for by reading the `group:` marker.
            text = _user_text(kwargs)
            assert f"`{g1}`" in text, "group_filter should restrict to g1 only"
            return _FakeGroupResponse(
                _build_group_audit_tool_input(
                    factors=[],
                    revisions=[
                        {"concept_id": cid, "revise": False, "reason": ""}
                        for cid in cids_g1
                    ],
                )
            )
        cid = _extract_cid_from_kwargs(kwargs)
        return _FakeResponse(_build_ranked_tool_input(pass_a[cid]))

    client = _FakeAnthropicClient(behavior)
    ranking = rank_project(
        project,
        analysis=analysis,
        client=client,
        concept_filter=set(all_cids),
        group_filter=g1,
    )

    assert g1 in ranking.groups
    assert g2 not in ranking.groups


def test_tokens_and_cost_aggregate_pass_b_and_c(tmp_path):
    group_name, cids = _pick_group_with_two_concepts()
    cids = cids[:2]
    analysis = _multi_analysis_for_concepts(
        {cid: [("a.pdf", "X", 0.9), ("b.pdf", "Y", 0.7)] for cid in cids}
    )
    project = _make_project_with_analysis(tmp_path, analysis)
    pass_a = {cid: _expected_candidate_ids(analysis, cid) for cid in cids}

    class _FixedUsage:
        def __init__(self):
            self.input_tokens = 100
            self.output_tokens = 50
            self.cache_creation_input_tokens = 0
            self.cache_read_input_tokens = 0

    class _RankResp:
        def __init__(self, tool_input):
            self.content = [SimpleNamespace(
                type="tool_use", name="emit_ranking", input=tool_input
            )]
            self.usage = _FixedUsage()

    class _GroupResp:
        def __init__(self, tool_input):
            self.content = [SimpleNamespace(
                type="tool_use", name="emit_group_audit", input=tool_input
            )]
            self.usage = _FixedUsage()

    def behavior(call_num, kwargs):
        if "emit_group_audit" in str(kwargs.get("tools", "")):
            return _GroupResp(
                _build_group_audit_tool_input(
                    factors=[{"description": "x", "affects": [cids[0]]}],
                    revisions=[
                        {"concept_id": cids[0], "revise": True, "reason": ""},
                        {"concept_id": cids[1], "revise": False, "reason": ""},
                    ],
                )
            )
        cid = _extract_cid_from_kwargs(kwargs)
        ordered = pass_a[cid]
        if _has_group_signal_block(kwargs) and cid == cids[0]:
            ordered = list(reversed(ordered))
        return _RankResp(_build_ranked_tool_input(ordered))

    client = _FakeAnthropicClient(behavior)
    ranking = rank_project(
        project,
        analysis=analysis,
        client=client,
        concept_filter=set(cids),
        model="claude-sonnet-4-6",
    )

    # Count calls: 2 Pass A + 1 Pass B + 1 Pass C = 4 calls × 100 input tokens.
    n_calls = client.messages.calls
    assert n_calls == 4
    assert ranking.total_input_tokens == 100 * n_calls
    assert ranking.total_output_tokens == 50 * n_calls
    # Cost formula: (input * 3 + output * 15) / 1e6.
    expected_cost = (
        (100 * n_calls * 3.0) + (50 * n_calls * 15.0)
    ) / 1_000_000.0
    assert abs(ranking.estimated_cost_usd - expected_cost) < 1e-6


def test_eva_summary_includes_group_audit_line(tmp_path):
    group_name, cids = _pick_group_with_two_concepts()
    cids = cids[:2]
    analysis = _multi_analysis_for_concepts(
        {cid: [("a.pdf", "X", 0.9), ("b.pdf", "Y", 0.7)] for cid in cids}
    )
    project = _make_project_with_analysis(tmp_path, analysis)
    pass_a = {cid: _expected_candidate_ids(analysis, cid) for cid in cids}

    def behavior(call_num, kwargs):
        if "emit_group_audit" in str(kwargs.get("tools", "")):
            return _FakeGroupResponse(
                _build_group_audit_tool_input(
                    factors=[{"description": "x", "affects": [cids[0]]}],
                    revisions=[
                        {"concept_id": cids[0], "revise": True, "reason": ""},
                        {"concept_id": cids[1], "revise": False, "reason": ""},
                    ],
                )
            )
        cid = _extract_cid_from_kwargs(kwargs)
        ordered = pass_a[cid]
        if _has_group_signal_block(kwargs) and cid == cids[0]:
            ordered = list(reversed(ordered))
        return _FakeResponse(_build_ranked_tool_input(ordered))

    client = _FakeAnthropicClient(behavior)
    ranking = rank_project(
        project, analysis=analysis, client=client, concept_filter=set(cids),
    )

    summary_joined = "\n".join(ranking.eva_summary)
    assert "Auditors de grup" in summary_joined
    assert "factors cross-concept" in summary_joined
    assert "rànquings revisats" in summary_joined


# ─── D18: cached block bundles concept YAML ───────────────────────────


def test_cached_block_includes_concept_yaml():
    """D18 fix: the ephemeral-cached block must contain BOTH the concept
    schema and the authority principles, so the combined block clears
    Anthropic's 1024-token cache minimum.
    """
    from automation.ai_pipeline.ranking import (
        _build_concept_user_content,
        _build_group_user_content,
        load_authority_principles,
        load_concept_definitions,
    )

    defs = load_concept_definitions()
    cid = _pick_multi_candidate_concept()
    concept_def = defs[cid]
    principles = load_authority_principles() or "non-empty principles"

    analysis = _make_multi_analysis(
        cid, [("a.pdf", "X", 0.9), ("b.pdf", "Y", 0.7)]
    )
    candidates_with_insights: list = []
    for s in analysis.sources:
        for idx, c in enumerate(s.candidates):
            if c.concept_id == cid:
                candidates_with_insights.append(
                    (f"{s.source_path}::{cid}::{idx}", s.insight, c)
                )

    blocks = _build_concept_user_content(
        concept_def,
        glossary_entry="",
        principles=principles,
        candidates_with_insights=candidates_with_insights,
        include_principles=True,
    )

    cached_blocks = [
        b for b in blocks
        if isinstance(b, dict) and b.get("cache_control", {}).get("type") == "ephemeral"
    ]
    assert len(cached_blocks) == 1, "expected exactly one ephemeral-cached block"
    cached_text = cached_blocks[0].get("text", "")
    assert "# Concept schema" in cached_text
    assert "# Authority principles" in cached_text
    # Sanity check: bundling should push the block well above the 1024-token
    # threshold. ~4 chars/token → ≥4500 chars is comfortably over.
    assert len(cached_text) > 4500, (
        f"cached block too small ({len(cached_text)} chars); "
        "would silently miss Anthropic's 1024-token cache minimum"
    )

    # Same expectation for the Pass B (group) prompt builder.
    pass_a = ConceptRanking(
        concept_id=cid,
        status="ranked",
        ranked=[
            RankedCandidate(
                candidate_id=candidates_with_insights[0][0],
                source_path="a.pdf",
                value="X",
                confidence=0.9,
                rationale="r",
            )
        ],
    )
    group_blocks = _build_group_user_content(
        group_name=concept_def.get("group", "test"),
        concepts_in_group=[concept_def],
        pass_a_rankings={cid: pass_a},
        analysis=analysis,
        principles=principles,
        include_principles=True,
    )
    cached_group = [
        b for b in group_blocks
        if isinstance(b, dict) and b.get("cache_control", {}).get("type") == "ephemeral"
    ]
    assert len(cached_group) == 1
    cached_group_text = cached_group[0].get("text", "")
    assert "# Concept schema" in cached_group_text
    assert "# Authority principles" in cached_group_text
    assert len(cached_group_text) > 4500


def test_cached_block_present_even_when_principles_empty(monkeypatch):
    """D18 follow-up: empty principles must not disable cache; the YAML alone
    clears Anthropic's 1024-token ephemeral-cache minimum."""
    import automation.ai_pipeline.ranking as rk
    from automation.ai_pipeline.ranking import (
        _build_concept_user_content,
        _build_group_user_content,
        load_concept_definitions,
    )

    defs = load_concept_definitions()
    cid = _pick_multi_candidate_concept()
    concept_def = defs[cid]

    analysis = _make_multi_analysis(
        cid, [("a.pdf", "X", 0.9), ("b.pdf", "Y", 0.7)]
    )
    candidates_with_insights: list = []
    for s in analysis.sources:
        for idx, c in enumerate(s.candidates):
            if c.concept_id == cid:
                candidates_with_insights.append(
                    (f"{s.source_path}::{cid}::{idx}", s.insight, c)
                )

    # Pass A with empty principles.
    blocks = _build_concept_user_content(
        concept_def,
        glossary_entry="",
        principles="",
        candidates_with_insights=candidates_with_insights,
        include_principles=True,
    )
    cached = [
        b for b in blocks
        if isinstance(b, dict)
        and b.get("cache_control", {}).get("type") == "ephemeral"
    ]
    assert len(cached) == 1, "expected exactly one cached block"
    cached_text = cached[0].get("text", "")
    assert "# Concept schema" in cached_text
    assert "# Authority principles" not in cached_text, (
        "no principles section when principles empty"
    )
    assert len(cached_text) > 4500, (
        f"cached block should clear 1024-token min ({len(cached_text)} chars)"
    )

    # Pass B (group): same expectation when principles is empty.
    pass_a = ConceptRanking(
        concept_id=cid,
        status="ranked",
        ranked=[
            RankedCandidate(
                candidate_id=candidates_with_insights[0][0],
                source_path="a.pdf",
                value="X",
                confidence=0.9,
                rationale="r",
            )
        ],
    )
    group_blocks = _build_group_user_content(
        group_name=concept_def.get("group", "test"),
        concepts_in_group=[concept_def],
        pass_a_rankings={cid: pass_a},
        analysis=analysis,
        principles="",
        include_principles=True,
    )
    cached_group = [
        b for b in group_blocks
        if isinstance(b, dict)
        and b.get("cache_control", {}).get("type") == "ephemeral"
    ]
    assert len(cached_group) == 1
    cached_group_text = cached_group[0].get("text", "")
    assert "# Concept schema" in cached_group_text
    assert "# Authority principles" not in cached_group_text
    assert len(cached_group_text) > 4500


def test_glossary_aliases_resolve_to_target_notes(tmp_path, monkeypatch):
    """W3: alias keys in concept_glossary.yaml must resolve to the target's
    note via load_glossary_entry — ranker must see synonyms, not blanks."""
    import automation.ai_pipeline.ranking as rk

    fake = tmp_path / "concept_glossary.yaml"
    fake.write_text(
        "version: '1.1'\n"
        "entries:\n"
        "  client_name:\n"
        "    note: |\n"
        "      The promoter / project owner.\n"
        "aliases:\n"
        "  promotor: client_name\n"
        "  sol·licitant: client_name\n"
        "  Nb:\n"
        "    hint: |\n"
        "      Nb = N20 / 0.83.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(rk, "_GLOSSARY_PATH", fake)
    monkeypatch.setattr(rk, "_GLOSSARY_CACHE", None)

    # Direct entry still works.
    direct = rk.load_glossary_entry("client_name")
    assert "promoter / project owner" in direct.lower()

    # String alias points at the target's note.
    aliased = rk.load_glossary_entry("promotor")
    assert "synonym of `client_name`" in aliased
    assert "promoter / project owner" in aliased.lower()

    # Dict-form alias is rendered as its own entry.
    nb = rk.load_glossary_entry("Nb")
    assert "Nb" in nb
    assert "0.83" in nb

    # Unknown id returns empty string (no crash).
    assert rk.load_glossary_entry("does_not_exist") == ""

    # Reset cache so other tests pick up the real file.
    monkeypatch.setattr(rk, "_GLOSSARY_CACHE", None)
