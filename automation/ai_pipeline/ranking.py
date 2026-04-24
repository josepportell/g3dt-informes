"""Stage 5: ranking — authority-based ordering of per-concept candidates.

Consumes `ProjectAnalysis` (Stage 4) and emits a `ProjectRanking` with, for
each `concept_id`, an ordered list of candidates from most to least trusted,
applying Eva's authority principles.

This module exposes the shared data models, the passthrough orchestrator for
the 0/1-candidate paths (no LLM involved), and the save/load helpers. The
LLM-backed passes A/B/C land in later chunks.

Design doc: docs/PLA-FASE-5-AUTHORITY-RANKING.md (§§4, 6, 15)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

from .analysis import Candidate, ProjectAnalysis, SourceInsight, load_analysis

# ─── Configuration ─────────────────────────────────────────────────────

_RANKING_ROOT = Path("validation") / "ai_pipeline" / "ranking"
_RANKING_MANIFEST = Path("validation") / "ai_ranking.json"

_DEFAULT_MODEL = "claude-sonnet-4-6"
_SCHEMA_VERSION = "1.0"

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_AUTHORITY_PRINCIPLES_PATH = (
    _PROJECT_ROOT / "schemas" / "ai_pipeline" / "authority_principles.md"
)


# ─── Models ────────────────────────────────────────────────────────────


class RankedCandidate(BaseModel):
    """One ranked candidate inside a `ConceptRanking`."""

    candidate_id: str
    source_path: str
    value: Any
    confidence: float
    rationale: str


class ConceptRanking(BaseModel):
    """Stage 5's output for a single concept."""

    concept_id: str
    status: Literal["ranked", "single", "no_candidates", "pending_fase5"]
    ranked: list[RankedCandidate] = Field(default_factory=list)
    has_conflict: bool = False
    conflict_note: str = ""
    group_factor_considered: str = ""
    revised_by_group_pass: bool = False
    attempts: int = 0
    elapsed_ms: int = 0
    model: str = ""


class GroupAuditResult(BaseModel):
    """Stage 5 Pass B output per group (cross-concept auditor)."""

    group: str
    factors: list[dict] = Field(default_factory=list)
    revisions: list[dict] = Field(default_factory=list)
    attempts: int = 0
    elapsed_ms: int = 0
    model: str = ""
    skipped_reason: str = ""


class ProjectRanking(BaseModel):
    project_path: str
    ranked_at: str
    concepts: dict[str, ConceptRanking] = Field(default_factory=dict)
    groups: dict[str, GroupAuditResult] = Field(default_factory=dict)
    eva_summary: list[str] = Field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_creation_tokens: int = 0
    total_cache_read_tokens: int = 0
    estimated_cost_usd: float = 0.0
    cache_hits: int = 0
    failures: list[dict] = Field(default_factory=list)
    schema_version: str = _SCHEMA_VERSION

    def ranking_of(self, concept_id: str) -> ConceptRanking | None:
        return self.concepts.get(concept_id)


# ─── Candidate helpers ─────────────────────────────────────────────────


def _candidate_id(source_path: str, concept_id: str, idx: int) -> str:
    """Stable, reconstructible id for a Fase-4 candidate.

    Resolves design doc §16 open question 1.
    """
    return f"{source_path}::{concept_id}::{idx}"


def _extract_candidates_by_concept(
    analysis: ProjectAnalysis,
) -> dict[str, list[tuple[str, SourceInsight, Candidate]]]:
    """Group Fase-4 candidates by concept_id, paired with their source insight.

    Returns: `{concept_id: [(candidate_id, insight, candidate), ...]}`.
    The `idx` used in the candidate id is the candidate's position within its
    source's candidate list — stable as long as Fase-4's output is stable.
    """
    out: dict[str, list[tuple[str, SourceInsight, Candidate]]] = {}
    for source in analysis.sources:
        for idx, candidate in enumerate(source.candidates):
            cid = _candidate_id(source.source_path, candidate.concept_id, idx)
            out.setdefault(candidate.concept_id, []).append(
                (cid, source.insight, candidate)
            )
    return out


# ─── Schema loaders ────────────────────────────────────────────────────


def load_concept_definitions() -> dict[str, dict]:
    """Load `schemas/concepts/report_variables.yaml` as `{concept_id: info}`.

    Info dict contains: `id`, `type`, `group`, `description_ca`, `required`.
    Exposed publicly because Pass B (chunk 3) needs the `group` field too.
    """
    path = _PROJECT_ROOT / "schemas" / "concepts" / "report_variables.yaml"
    if not path.is_file():
        raise FileNotFoundError(
            f"Concept definitions YAML not found at {path}"
        )
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(
            f"Malformed concept YAML at {path}: {exc}"
        ) from exc
    if not isinstance(data, dict) or "concepts" not in data:
        raise ValueError(
            f"Concept YAML at {path} missing 'concepts' key"
        )
    raw = data.get("concepts") or {}
    out: dict[str, dict] = {}
    for cid, meta in raw.items():
        if not isinstance(meta, dict):
            continue
        out[cid] = {
            "id": cid,
            "type": meta.get("type", ""),
            "group": meta.get("group", ""),
            "description_ca": meta.get("description_ca", ""),
            "required": bool(meta.get("required", False)),
        }
    return out


def load_authority_principles() -> str:
    """Read Eva's authority-principles Markdown verbatim.

    Returns an empty string if the file is absent (lets tests run on fresh
    checkouts; the LLM passes in later chunks will enforce presence).
    """
    if not _AUTHORITY_PRINCIPLES_PATH.is_file():
        return ""
    return _AUTHORITY_PRINCIPLES_PATH.read_text(encoding="utf-8")


# ─── Passthrough orchestrator (chunk 1) ────────────────────────────────


def rank_project_passthrough_only(
    project_path: Path | str,
    *,
    analysis: ProjectAnalysis | None = None,
) -> ProjectRanking:
    """Run only the no-LLM passthrough paths of Stage 5.

    Handles concepts with 0 candidates (`status="no_candidates"`) and concepts
    with exactly 1 candidate (`status="single"`). Concepts with ≥2 candidates
    are deliberately omitted from the returned `concepts` dict — later chunks
    (Pass A/B/C) fill them in.

    The goal of this function is to (a) prove the data shape end-to-end, (b)
    handle the cheap paths without any API cost, and (c) serve as the scaffold
    that the LLM orchestrators in chunks 2–3 build on top of.
    """
    pp = Path(project_path).resolve()

    if analysis is None:
        analysis = load_analysis(pp)
        if analysis is None:
            raise FileNotFoundError(
                f"ai_analysis.json not found under {pp / 'validation'}; "
                "run Stage 4 first or pass `analysis=...` explicitly."
            )

    concept_defs = load_concept_definitions()
    by_concept = _extract_candidates_by_concept(analysis)

    concepts: dict[str, ConceptRanking] = {}
    n_zero = 0
    n_single = 0
    n_pending = 0

    for cid in concept_defs:
        entries = by_concept.get(cid, [])
        if len(entries) == 0:
            concepts[cid] = ConceptRanking(
                concept_id=cid, status="no_candidates"
            )
            n_zero += 1
        elif len(entries) == 1:
            candidate_id, _insight, candidate = entries[0]
            concepts[cid] = ConceptRanking(
                concept_id=cid,
                status="single",
                ranked=[
                    RankedCandidate(
                        candidate_id=candidate_id,
                        source_path=candidate.source_path,
                        value=candidate.value,
                        confidence=candidate.confidence,
                        rationale="única font disponible",
                    )
                ],
            )
            n_single += 1
        else:
            # ≥2 candidates — left for chunks 2–3 (LLM passes).
            n_pending += 1

    eva_summary = [
        f"Passthrough de Fase 5: {n_zero} sense candidats, "
        f"{n_single} amb font única, {n_pending} pendents de rànquing LLM."
    ]

    return ProjectRanking(
        project_path=str(pp),
        ranked_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        concepts=concepts,
        eva_summary=eva_summary,
        schema_version=_SCHEMA_VERSION,
    )


# ─── Save / load ───────────────────────────────────────────────────────


def save_ranking(ranking: ProjectRanking, project_path: Path | str) -> Path:
    pp = Path(project_path).resolve()
    out_dir = pp / "validation"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "ai_ranking.json"
    out_path.write_text(ranking.model_dump_json(indent=2), encoding="utf-8")
    return out_path


def load_ranking(project_path: Path | str) -> ProjectRanking | None:
    pp = Path(project_path).resolve()
    p = pp / "validation" / "ai_ranking.json"
    if not p.is_file():
        return None
    return ProjectRanking.model_validate_json(p.read_text(encoding="utf-8"))
