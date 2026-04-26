"""Tests for AI pipeline Stage 4.5 — engineering calculator pass.

The legacy terzaghi_calculator is mocked in unit tests so that we exercise
the integration shape (input resolution, candidate emission, save/load,
feature flag) without depending on numerical behaviour.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from automation.ai_pipeline.analysis import (
    Candidate,
    ProjectAnalysis,
    SourceAnalysis,
    SourceInsight,
)
from automation.ai_pipeline import calculator_pass as cp
from automation.ai_pipeline.calculator_pass import (
    _CALCULATOR_SOURCE_PATH,
    load_calculations,
    run_calculator_pass,
    save_calculations,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_insight(path: str = "doc1.pdf") -> SourceInsight:
    return SourceInsight(
        source_path=path,
        document_type="report",
        purpose="test fixture",
        confidence=0.9,
    )


def _make_analysis(tmp_path: Path, candidates: list[Candidate]) -> ProjectAnalysis:
    """Build a minimal ProjectAnalysis containing a single source with the
    given candidates."""
    src = SourceAnalysis(
        source_path="doc1.pdf",
        insight=_make_insight("doc1.pdf"),
        candidates=candidates,
    )
    return ProjectAnalysis(
        project_path=str(tmp_path),
        analyzed_at="2026-04-26T12:00:00+00:00",
        sources=[src],
    )


def _bearing_inputs_candidates(
    *, phi: float = 30.0, cohesion: float = 0.0, gamma: float = 2.0,
    n20: float = 25.0,
) -> list[Candidate]:
    """Stage 4 candidates that the calculator pass needs to find."""
    return [
        Candidate(concept_id="geomech_phi", value=phi, confidence=0.9, source_path="doc1.pdf"),
        Candidate(concept_id="geomech_cohesion", value=cohesion, confidence=0.9, source_path="doc1.pdf"),
        Candidate(concept_id="geomech_gamma", value=gamma, confidence=0.9, source_path="doc1.pdf"),
        Candidate(concept_id="spt_n30", value=n20, confidence=0.8, source_path="doc1.pdf"),
    ]


def _write_user_data(project: Path, data: dict) -> None:
    project.mkdir(parents=True, exist_ok=True)
    (project / "user_data.json").write_text(
        json.dumps(data), encoding="utf-8"
    )


class _FakeResult:
    """Stand-in for BearingCapacityResult."""

    def __init__(self, Qa: float = 2.5, settlement_cm: float | None = 1.3):
        self.Qa = Qa
        self.settlement_cm = settlement_cm


class _FakeCalc:
    last_init: dict | None = None
    last_call: dict | None = None
    qa: float = 2.5
    settlement_cm: float | None = 1.3
    raises: bool = False

    def __init__(self, phi, cohesion=0.0, gamma=2.0, **kwargs):
        type(self).last_init = {
            "phi": phi, "cohesion": cohesion, "gamma": gamma, **kwargs,
        }

    def calculate_qa(self, **kwargs):
        type(self).last_call = kwargs
        if type(self).raises:
            raise RuntimeError("simulated calculator failure")
        return _FakeResult(
            Qa=type(self).qa, settlement_cm=type(self).settlement_cm,
        )


@pytest.fixture
def fake_terzaghi(monkeypatch):
    """Patch TerzaghiCalculator + FootingShape so tests are deterministic."""
    # Reset class-level state between tests.
    _FakeCalc.last_init = None
    _FakeCalc.last_call = None
    _FakeCalc.qa = 2.5
    _FakeCalc.settlement_cm = 1.3
    _FakeCalc.raises = False

    fake_module = SimpleNamespace(
        TerzaghiCalculator=_FakeCalc,
        FootingShape=SimpleNamespace(SQUARE="square", STRIP="strip"),
    )

    import automation.terzaghi_calculator as real_mod

    monkeypatch.setattr(real_mod, "TerzaghiCalculator", _FakeCalc)
    # FootingShape is enum-typed in the real module; only used as kwarg, so
    # passing an arbitrary sentinel is fine because _FakeCalc.calculate_qa
    # accepts **kwargs.
    return _FakeCalc


# ---------------------------------------------------------------------------
# Tests — public API
# ---------------------------------------------------------------------------


def test_run_calculator_pass_emits_qa_value_candidate(tmp_path, fake_terzaghi):
    project = tmp_path / "demo"
    project.mkdir()
    fake_terzaghi.qa = 3.0
    fake_terzaghi.settlement_cm = 1.1
    analysis = _make_analysis(project, _bearing_inputs_candidates())
    _write_user_data(project, {
        "footing_width_m": 1.5, "foundation_depth_m": 0.8,
    })

    result = run_calculator_pass(project, analysis=analysis, force=True)

    assert len(result.sources) == 1
    src = result.sources[0]
    assert src.source_path == _CALCULATOR_SOURCE_PATH
    qa_cands = [c for c in src.candidates if c.concept_id == "qa_value"]
    assert len(qa_cands) == 1
    qa = qa_cands[0]
    assert qa.value == 3.0
    assert qa.confidence == 1.0
    assert qa.source_path == _CALCULATOR_SOURCE_PATH
    assert qa.extractor == "legacy_calculator"
    assert "terzaghi_calculator.calculate_qa" in qa.reasoning


def test_run_calculator_pass_emits_settlement_candidate(tmp_path, fake_terzaghi):
    project = tmp_path / "demo"
    project.mkdir()
    fake_terzaghi.qa = 2.5
    fake_terzaghi.settlement_cm = 1.42
    analysis = _make_analysis(project, _bearing_inputs_candidates())
    _write_user_data(project, {
        "footing_width_m": 1.0, "foundation_depth_m": 0.5,
    })

    result = run_calculator_pass(project, analysis=analysis, force=True)
    src = result.sources[0]
    s_cands = [c for c in src.candidates if c.concept_id == "settlement_cm"]
    assert len(s_cands) == 1
    s = s_cands[0]
    assert s.value == 1.42
    assert s.confidence == 1.0
    assert "schmertmann_settlement" in s.reasoning


def test_run_calculator_pass_skips_concept_when_calculator_raises(
    tmp_path, fake_terzaghi
):
    project = tmp_path / "demo"
    project.mkdir()
    fake_terzaghi.raises = True
    analysis = _make_analysis(project, _bearing_inputs_candidates())
    _write_user_data(project, {})

    result = run_calculator_pass(project, analysis=analysis, force=True)
    src = result.sources[0]
    # Calculator raised → no candidates emitted.
    assert src.candidates == []
    # The synthetic source itself is still present.
    assert src.source_path == _CALCULATOR_SOURCE_PATH


def test_run_calculator_pass_skips_when_user_data_missing(tmp_path, fake_terzaghi):
    """No user_data.json on disk: calculator pass falls back to defaults
    and still runs (warning logged). Candidates ARE emitted because the
    calculator inputs (geomech_*, spt_n30) are sufficient."""
    project = tmp_path / "demo"
    project.mkdir()
    analysis = _make_analysis(project, _bearing_inputs_candidates())
    # Deliberately do NOT write user_data.json.

    result = run_calculator_pass(project, analysis=analysis, force=True)
    src = result.sources[0]
    # Defaults were used (B=1.0, Df=0.8); candidates emitted.
    assert any(c.concept_id == "qa_value" for c in src.candidates)
    # Verify default geometry reached the calculator.
    last_call = _FakeCalc.last_call
    assert last_call is not None
    assert last_call["B"] == cp._DEFAULT_B_M
    assert last_call["Df"] == cp._DEFAULT_DF_M


def test_run_calculator_pass_skips_when_phi_missing(tmp_path, fake_terzaghi):
    """No phi candidate at all: calculator can't run, no candidates emitted."""
    project = tmp_path / "demo"
    project.mkdir()
    # Provide cohesion + gamma but not phi.
    cands = [
        Candidate(concept_id="geomech_cohesion", value=0.0, confidence=0.9, source_path="doc1.pdf"),
        Candidate(concept_id="geomech_gamma", value=2.0, confidence=0.9, source_path="doc1.pdf"),
    ]
    analysis = _make_analysis(project, cands)
    _write_user_data(project, {})

    result = run_calculator_pass(project, analysis=analysis, force=True)
    src = result.sources[0]
    assert src.candidates == []


def test_save_load_roundtrip(tmp_path, fake_terzaghi):
    project = tmp_path / "demo"
    project.mkdir()
    analysis = _make_analysis(project, _bearing_inputs_candidates())
    _write_user_data(project, {"footing_width_m": 1.0, "foundation_depth_m": 0.5})

    result = run_calculator_pass(project, analysis=analysis, force=True)
    out = save_calculations(result, project)
    assert out.is_file()
    assert out.name == "ai_calculations.json"

    loaded = load_calculations(project)
    assert loaded is not None
    assert len(loaded.sources) == 1
    assert loaded.sources[0].source_path == _CALCULATOR_SOURCE_PATH
    # Candidate count matches.
    assert len(loaded.sources[0].candidates) == len(result.sources[0].candidates)


def test_load_calculations_returns_none_when_missing(tmp_path):
    project = tmp_path / "empty"
    project.mkdir()
    assert load_calculations(project) is None


# ---------------------------------------------------------------------------
# Tests — feature flag gating in ranking._load_combined_candidates
# ---------------------------------------------------------------------------


def test_feature_flag_off_excludes_calculator_candidates(tmp_path, monkeypatch, fake_terzaghi):
    """Without the env var, calculator candidates must NOT be merged."""
    from automation.ai_pipeline.analysis import save_analysis
    from automation.ai_pipeline.ranking import _load_combined_candidates

    project = tmp_path / "demo"
    project.mkdir()
    # Stage 4 manifest: one Stage 4 candidate for qa_value.
    s4_candidates = [
        Candidate(concept_id="qa_value", value=2.0, confidence=0.7, source_path="doc1.pdf"),
    ]
    s4 = _make_analysis(project, s4_candidates)
    save_analysis(s4, project)

    # Stage 4.5 manifest: synthetic calculator candidate for qa_value.
    calc = _make_analysis(project, [])
    calc.sources = [
        SourceAnalysis(
            source_path=_CALCULATOR_SOURCE_PATH,
            insight=SourceInsight(
                source_path=_CALCULATOR_SOURCE_PATH,
                document_type="deterministic_calculator",
                purpose="test",
            ),
            candidates=[
                Candidate(
                    concept_id="qa_value",
                    value=3.0,
                    confidence=1.0,
                    source_path=_CALCULATOR_SOURCE_PATH,
                    extractor="legacy_calculator",
                ),
            ],
        )
    ]
    save_calculations(calc, project)

    # Flag OFF (default).
    monkeypatch.delenv("G3DT_ENABLE_CALCULATOR_DELEGATION", raising=False)
    merged = _load_combined_candidates(project)
    qa_sources = {
        c.source_path
        for s in merged.sources for c in s.candidates
        if c.concept_id == "qa_value"
    }
    assert _CALCULATOR_SOURCE_PATH not in qa_sources

    # Flag ON.
    monkeypatch.setenv("G3DT_ENABLE_CALCULATOR_DELEGATION", "true")
    merged = _load_combined_candidates(project)
    qa_sources = {
        c.source_path
        for s in merged.sources for c in s.candidates
        if c.concept_id == "qa_value"
    }
    assert _CALCULATOR_SOURCE_PATH in qa_sources


# ---------------------------------------------------------------------------
# Tests — real Alcoletge data smoke test (uses real terzaghi_calculator)
# ---------------------------------------------------------------------------


def test_calculator_pass_works_on_real_alcoletge_data(tmp_path):
    """Smoke test: load real Alcoletge ai_analysis.json into a tmp project,
    write minimal user_data.json with default foundation geometry, run the
    pass with the REAL legacy calculator, assert ≥1 candidate emitted.
    Does NOT assert specific numeric values (manual validation step)."""
    repo_root = Path(__file__).resolve().parent.parent
    real_analysis = (
        repo_root / "reference-material" / "4001670 ALCOLETGE"
        / "validation" / "ai_analysis.json"
    )
    if not real_analysis.is_file():
        pytest.skip(f"Alcoletge fixture not present: {real_analysis}")

    # Copy the analysis into a tmp project.
    project = tmp_path / "alcoletge"
    (project / "validation").mkdir(parents=True)
    (project / "validation" / "ai_analysis.json").write_bytes(
        real_analysis.read_bytes()
    )
    _write_user_data(project, {
        "footing_width_m": 2.0,
        "foundation_depth_m": 1.0,
    })

    result = run_calculator_pass(project, force=True)
    assert len(result.sources) == 1
    src = result.sources[0]
    cids = {c.concept_id for c in src.candidates}
    # At least one of the two delegated concepts must be computable.
    assert cids & {"qa_value", "settlement_cm"}


# ---------------------------------------------------------------------------
# Tests — input resolution edge cases
# ---------------------------------------------------------------------------


def test_user_data_zero_b_not_overridden_by_default(tmp_path, fake_terzaghi):
    """An explicit footing_width_m=0.0 in user_data must reach the calculator
    instead of being silently replaced by the default. The calculator itself
    is responsible for validating/rejecting absurd geometries."""
    project = tmp_path / "demo"
    project.mkdir()
    analysis = _make_analysis(project, _bearing_inputs_candidates())
    _write_user_data(project, {
        "footing_width_m": 0.0, "foundation_depth_m": 0.0,
    })

    run_calculator_pass(project, analysis=analysis, force=True)
    last_call = _FakeCalc.last_call
    assert last_call is not None
    # Defaults must NOT have leaked in: explicit 0.0 reaches the calculator.
    assert last_call["B"] == 0.0
    assert last_call["Df"] == 0.0


# ---------------------------------------------------------------------------
# Tests — save_calculations guard
# ---------------------------------------------------------------------------


def test_save_calculations_rejects_non_calculator_analysis(tmp_path):
    """save_calculations must refuse to overwrite ai_calculations.json with
    an analysis that wasn't produced by run_calculator_pass (i.e. has no
    synthetic calculator source)."""
    project = tmp_path / "demo"
    project.mkdir()
    # Build a regular ProjectAnalysis with a real source path (not the calculator one).
    plain = ProjectAnalysis(
        project_path=str(project),
        analyzed_at="2026-04-26T12:00:00+00:00",
        sources=[
            SourceAnalysis(
                source_path="some_doc.pdf",
                insight=_make_insight("some_doc.pdf"),
                candidates=[],
            )
        ],
    )
    with pytest.raises(ValueError, match="run_calculator_pass"):
        save_calculations(plain, project)


# ---------------------------------------------------------------------------
# Tests — YAML ↔ dispatch coverage
# ---------------------------------------------------------------------------


def test_yaml_delegated_concepts_match_dispatch_table():
    """Every concept marked delegate_to_calculator: true in the schema must
    have an entry in the dispatch (_TERZAGHI_EXTRACTORS), and vice versa.
    Prevents silent drift between YAML and code."""
    yaml_set = set(cp._load_delegated_concepts())
    dispatch_set = set(cp._TERZAGHI_EXTRACTORS.keys())
    missing_in_dispatch = yaml_set - dispatch_set
    missing_in_yaml = dispatch_set - yaml_set
    assert not missing_in_dispatch, (
        f"Concepts marked delegate_to_calculator in YAML but missing "
        f"from dispatch: {missing_in_dispatch}"
    )
    assert not missing_in_yaml, (
        f"Concepts in dispatch but not marked delegate_to_calculator "
        f"in YAML: {missing_in_yaml}"
    )
