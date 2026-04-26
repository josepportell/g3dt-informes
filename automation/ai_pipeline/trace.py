"""Read-only diagnostic trace over the AI pipeline manifests (Stages 1-5).

This module joins ai_inventory.json, ai_typology.json, ai_conversion.json,
ai_analysis.json and ai_ranking.json into a unified `PipelineTrace` that
exposes per-concept journeys, per-source journeys, decision audits and
cross-stage analyses.

It does NOT execute any pipeline stage and DOES NOT make LLM calls. It only
reads existing manifests and derives signals from them.

Design notes:
- Eva ground truth is loaded from `validation/eva_reference_values.json` when
  present. Concepts and Eva-variable ids are matched directly when names match;
  otherwise stripped variants (e.g., `_upper`, `_lower`, `_text`, `_fmt`) are
  attempted as a fallback.
- Top issues are scored 0..1; see `_signal_strength_for` for the rubric.
"""

from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

from .analysis import (
    Candidate,
    ProjectAnalysis,
    SourceFailure,
    SourceInsight,
    load_analysis,
)
from .conversion import ConvertedArtifact, ProjectConversion, load_conversion
from .inventory import Inventory, InventoryFile, load_inventory
from .ranking import (
    ConceptRanking,
    GroupAuditResult,
    ProjectRanking,
    RankedCandidate,
    load_ranking,
)
from .typology import FileClass, FolderClass, ProjectTypology, load_typology

logger = logging.getLogger(__name__)


# ─── Configuration ─────────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_REPORT_VARIABLES_PATH = _PROJECT_ROOT / "schemas" / "concepts" / "report_variables.yaml"
_GLOSSARY_PATH = _PROJECT_ROOT / "schemas" / "ai_pipeline" / "concept_glossary.yaml"
_TEMPLATE_ALIASES_PATH = (
    _PROJECT_ROOT / "schemas" / "concepts" / "concept_template_aliases.yaml"
)

_TRACE_FILENAME = "ai_pipeline_trace.json"

# Heuristic thresholds. Documented in the docstring of the function that uses them.
_LOW_CONFIDENCE_THRESHOLD = 0.6
_HIGH_DISAGREEMENT_DISTINCT = 3
_HIGH_DISAGREEMENT_RATIO = 0.5
_AUTO_ACCEPT_CONFIDENCE = 0.9
_EVA_DECIDES_TOP2_CONFIDENCE = 0.8
_AGREEMENT_MAJORITY_THRESHOLD = 0.5
_AGREEMENT_SPLIT_THRESHOLD = 0.3
_AGREEMENT_OUTLIER_THRESHOLD = 0.3
_AMBIGUITY_LENGTH_RATIO = 3.0
_AMBIGUITY_MAGNITUDE_RATIO = 10.0
_TOP_ISSUES_CAP = 30


# Words/phrases appearing in candidate quotes/reasoning that hint at Eva's "professional cap".
# Use a precompiled regex with word-boundaries so the Catalan stopword "cap"
# (e.g. "no hi ha cap planta soterrani") doesn't trigger the flag — only
# domain bigrams like "cap màxim", "cap professional", "topall", "supera".
_DOMAIN_CAP_PATTERNS = (
    r"\bcap\s+(màxim|professional|d['e]\s|de\s)",
    r"\btopall\b",
    r"\bsupera\b",
    r"\bprofessional\s+judgement\b",
    r"\bjudgement\b",
    r"\bjudici\b",
)
_DOMAIN_CAP_RE = re.compile("|".join(_DOMAIN_CAP_PATTERNS), re.IGNORECASE)


# ─── Models ────────────────────────────────────────────────────────────


class CandidateView(BaseModel):
    """A flattened view of a Stage 4 Candidate plus its producing SourceInsight."""

    candidate_id: str
    concept_id: str
    value: Any
    confidence: float
    quote: str
    reasoning: str
    source_path: str
    source_chain: list[str] = Field(default_factory=list)
    insight: SourceInsight


class ConceptJourney(BaseModel):
    """All information about a single concept across stages 4 and 5."""

    concept_id: str
    concept_def: dict
    glossary_entry: str = ""

    # Stage 4
    candidates: list[CandidateView] = Field(default_factory=list)

    # Stage 5 Pass A
    final_status: str = ""
    final_ranked: list[RankedCandidate] = Field(default_factory=list)
    final_has_conflict: bool = False
    final_conflict_note: str = ""
    pass_a_attempts: int = 0

    # Stage 5 Pass B
    group: str | None = None
    group_factors_mentioning: list[dict] = Field(default_factory=list)
    group_revision_flag: dict | None = None

    # Stage 5 Pass C
    revised_by_group_pass: bool = False
    group_factor_considered: str = ""
    no_change_guardrail_fired: bool = False

    # Eva ground truth
    eva_value: Any | None = None
    eva_top1_match: Literal["exact", "substring", "mismatch", "no_ground_truth"] = "no_ground_truth"
    eva_rank_in_ranked: int | None = None  # 1-indexed; None if Eva value not in ranked list
    eva_rank_match_kind: Literal["exact", "substring", "none"] = "none"

    # Heuristic picker preview
    picker_action: Literal["auto_accept", "soft_review", "eva_decides", "no_value"] = "no_value"
    picker_rationale: str = ""
    source_agreement: Literal["unanimous", "majority", "split", "outlier", "n/a"] = "n/a"
    domain_flags: list[str] = Field(default_factory=list)


class SourceJourney(BaseModel):
    """All information about a single source path across stages 1-5."""

    source_path: str
    inventory: dict | None = None
    typology: dict | None = None
    artifacts: list[dict] = Field(default_factory=list)
    insight: SourceInsight | None = None
    candidates_emitted: list[dict] = Field(default_factory=list)
    pass4_attempts: int = 0
    pass4_failure: dict | None = None
    pass4_tokens_in: int = 0
    pass4_tokens_out: int = 0
    rankings_contributed_to: list[dict] = Field(default_factory=list)


class DecisionAudit(BaseModel):
    """Flat list of every non-trivial decision the pipeline made."""

    stage2_dev_only_skips: list[dict] = Field(default_factory=list)
    stage2_logo_skips: list[dict] = Field(default_factory=list)
    stage3_conversion_failures: list[dict] = Field(default_factory=list)
    stage4_retried_sources: list[dict] = Field(default_factory=list)
    stage4_failed_sources: list[dict] = Field(default_factory=list)
    stage5_pass_a_retries: list[dict] = Field(default_factory=list)
    stage5_pass_b_revisions_flagged: dict[str, int] = Field(default_factory=dict)
    stage5_pass_c_no_change_guardrails: list[str] = Field(default_factory=list)
    stage5_pass_c_reorderings: list[str] = Field(default_factory=list)
    instrumentation_gaps: list[str] = Field(default_factory=list)


class CrossStageAnalysis(BaseModel):
    """Cross-stage signals derived from the joined manifests."""

    stage2_to_stage4_dropoff: list[dict] = Field(default_factory=list)
    stage4_zero_candidate_sources: list[dict] = Field(default_factory=list)
    low_confidence_concepts: list[dict] = Field(default_factory=list)
    high_disagreement_concepts: list[dict] = Field(default_factory=list)
    pass_c_reorder_summary: list[dict] = Field(default_factory=list)
    eva_recoverable_mismatches: list[dict] = Field(default_factory=list)
    eva_unrecoverable_mismatches: list[dict] = Field(default_factory=list)
    eva_shape_mismatches: list[dict] = Field(default_factory=list)
    eva_reference_suspect: list[dict] = Field(default_factory=list)
    concept_definition_ambiguity_hints: list[dict] = Field(default_factory=list)


class PipelineTrace(BaseModel):
    project_path: str
    project_name: str
    generated_at: str
    concepts: dict[str, ConceptJourney] = Field(default_factory=dict)
    sources: dict[str, SourceJourney] = Field(default_factory=dict)
    decisions: DecisionAudit = Field(default_factory=DecisionAudit)
    cross_stage: CrossStageAnalysis = Field(default_factory=CrossStageAnalysis)
    stage1_summary: dict = Field(default_factory=dict)
    stage2_summary: dict = Field(default_factory=dict)
    stage3_summary: dict = Field(default_factory=dict)
    stage4_summary: dict = Field(default_factory=dict)
    stage5_summary: dict = Field(default_factory=dict)
    eva_summary: dict = Field(default_factory=dict)
    top_issues: list[dict] = Field(default_factory=list)


# ─── Loaders ───────────────────────────────────────────────────────────


def _load_concept_definitions() -> dict[str, dict]:
    if not _REPORT_VARIABLES_PATH.is_file():
        return {}
    try:
        data = yaml.safe_load(_REPORT_VARIABLES_PATH.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError) as exc:
        logger.warning(
            "Failed to load concept definitions at %s: %s",
            _REPORT_VARIABLES_PATH,
            exc,
        )
        return {}
    raw = data.get("concepts", {}) if isinstance(data, dict) else {}
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


def _load_glossary_entries() -> dict[str, str]:
    """Map concept_id -> YAML-formatted glossary entry text. Empty if missing.

    Also resolves the top-level `aliases:` section: each alias key is added to
    the returned mapping with a synthesised entry that points the LLM at the
    target's note (e.g. ``promotor`` → "(synonym of `client_name`) ...").
    """
    if not _GLOSSARY_PATH.is_file():
        return {}
    try:
        data = yaml.safe_load(_GLOSSARY_PATH.read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, OSError) as exc:
        logger.warning(
            "Failed to load glossary entries at %s: %s",
            _GLOSSARY_PATH,
            exc,
        )
        return {}
    if not isinstance(data, dict):
        return {}
    entries = data.get("entries", {}) if isinstance(data, dict) else {}
    out: dict[str, str] = {}
    for cid, entry in entries.items():
        if not entry:
            continue
        try:
            out[cid] = yaml.safe_dump(
                {cid: entry}, allow_unicode=True, sort_keys=False
            ).strip()
        except Exception:
            out[cid] = ""

    # Wire aliases — each alias gets a synonym note pointing at the target's
    # entry so the ranker actually sees the alias when looking up a concept.
    aliases_raw = data.get("aliases", {}) if isinstance(data, dict) else {}
    if isinstance(aliases_raw, dict):
        for alias, target in aliases_raw.items():
            if not isinstance(target, str):
                continue
            target_note = out.get(target, "")
            out[alias] = f"(synonym of `{target}`) {target_note}".strip()
    return out


def _load_eva_reference(project_path: Path) -> dict[str, Any]:
    """Return Eva variable values keyed by variable name. Empty if file absent."""
    p = project_path / "validation" / "eva_reference_values.json"
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load Eva reference values at %s: %s", p, exc)
        return {}
    variables = data.get("variables", {}) if isinstance(data, dict) else {}
    out: dict[str, Any] = {}
    for var_name, payload in variables.items():
        if isinstance(payload, dict) and "value" in payload:
            out[var_name] = payload["value"]
    return out


def _load_template_aliases() -> dict[str, list[str]]:
    """Map canonical concept_id → list of template-placeholder aliases.

    The reference extractor stores Eva's values keyed by template-placeholder
    name (e.g. ``architect_name_upper``, ``client``, ``data_camp_text``),
    which often differ from the canonical concept_id. Returns an empty map
    if the YAML is missing or malformed.
    """
    if not _TEMPLATE_ALIASES_PATH.is_file():
        return {}
    try:
        data = yaml.safe_load(_TEMPLATE_ALIASES_PATH.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError) as exc:
        logger.warning(
            "Failed to load template aliases at %s: %s",
            _TEMPLATE_ALIASES_PATH,
            exc,
        )
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, list[str]] = {}
    for cid, aliases in data.items():
        if not isinstance(cid, str):
            continue
        if aliases is None:
            out[cid] = []
            continue
        if isinstance(aliases, list):
            out[cid] = [a for a in aliases if isinstance(a, str)]
    return out


# ─── Utility helpers ───────────────────────────────────────────────────


_NUMERIC_TOLERANCE = 1e-6


def _normalize_value(value: Any) -> Any:
    """Normalize a value for equality comparison.

    - Strings: lowercase + collapse whitespace.
    - Numbers: pass through (compared with tolerance separately).
    - Bools: pass through.
    - Lists/dicts: stringified canonical JSON.
    - None: stays None.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        return re.sub(r"\s+", " ", value).strip().lower()
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        return str(value)


def _try_float(v: Any) -> float | None:
    """Best-effort numeric coercion that accepts numbers and number-like strings."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None
    if isinstance(v, str):
        s = v.strip().replace(",", ".")
        try:
            return float(s)
        except ValueError:
            return None
    return None


def _values_equal(a: Any, b: Any) -> bool:
    """Equality check: numbers within tolerance (incl. number-like strings),
    strings case-insensitive otherwise, deep equality for collections."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    fa = _try_float(a)
    fb = _try_float(b)
    if fa is not None and fb is not None:
        try:
            return math.isclose(fa, fb, abs_tol=_NUMERIC_TOLERANCE, rel_tol=1e-9)
        except (TypeError, ValueError):
            return False
    return _normalize_value(a) == _normalize_value(b)


def _value_as_string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return str(value)


_EVA_NAME_SUFFIXES = ("_upper", "_lower", "_text", "_fmt", "_long", "_short")


def _eva_lookup(
    eva_values: dict[str, Any],
    concept_id: str,
    aliases_map: dict[str, list[str]] | None = None,
) -> tuple[str | None, Any]:
    """Find Eva's value for a concept_id.

    Resolution order:
    1. Canonical concept_id match.
    2. Template-placeholder aliases from `concept_template_aliases.yaml`
       (when an alias map is provided).
    3. Simple suffix tolerance (`_upper`, `_lower`, `_text`, `_fmt`, …) as a
       safety net for projects whose extractor predates the alias map.

    Returns (eva_var_name_used, value). If no match, returns (None, None).
    """
    if concept_id in eva_values:
        return concept_id, eva_values[concept_id]
    # Template-placeholder aliases (canonical mapping, no guessing).
    if aliases_map:
        for alias in aliases_map.get(concept_id, []):
            if alias and alias != concept_id and alias in eva_values:
                return alias, eva_values[alias]
    # Try the same name with one of the known suffixes.
    for suffix in _EVA_NAME_SUFFIXES:
        candidate = concept_id + suffix
        if candidate in eva_values:
            return candidate, eva_values[candidate]
    # Also try stripping a known suffix from concept_id and matching base.
    for suffix in _EVA_NAME_SUFFIXES:
        if concept_id.endswith(suffix):
            base = concept_id[: -len(suffix)]
            if base in eva_values:
                return base, eva_values[base]
    return None, None


def _eva_value_for_concept(
    eva_values: dict[str, Any],
    concept_id: str,
    aliases_map: dict[str, list[str]] | None = None,
) -> Any:
    """Look up Eva's reference value for a concept, trying canonical concept_id
    first then any template-placeholder aliases (and finally suffix tolerance).

    Thin wrapper over `_eva_lookup` that returns just the value (no name).
    """
    _name, value = _eva_lookup(eva_values, concept_id, aliases_map)
    return value


def _eva_match_kind(eva_value: Any, top1_value: Any) -> Literal["exact", "substring", "mismatch"]:
    if _values_equal(eva_value, top1_value):
        return "exact"
    # Try substring containment (case-insensitive) for string-ish values.
    a = _value_as_string(eva_value).lower().strip()
    b = _value_as_string(top1_value).lower().strip()
    if a and b and (a in b or b in a):
        return "substring"
    return "mismatch"


# ─── Per-concept journey ───────────────────────────────────────────────


def _candidate_id(source_path: str, concept_id: str, idx: int) -> str:
    """Mirrors ranking._candidate_id without importing the private symbol."""
    return f"{source_path}::{concept_id}::{idx}"


def _build_candidate_views(
    analysis: ProjectAnalysis | None,
) -> dict[str, list[CandidateView]]:
    """Group Stage 4 candidates by concept_id, paired with their source insight."""
    out: dict[str, list[CandidateView]] = defaultdict(list)
    if analysis is None:
        return out
    for source in analysis.sources:
        for idx, candidate in enumerate(source.candidates):
            cid = _candidate_id(source.source_path, candidate.concept_id, idx)
            out[candidate.concept_id].append(
                CandidateView(
                    candidate_id=cid,
                    concept_id=candidate.concept_id,
                    value=candidate.value,
                    confidence=candidate.confidence,
                    quote=candidate.quote,
                    reasoning=candidate.reasoning,
                    source_path=candidate.source_path,
                    source_chain=list(candidate.source_chain),
                    insight=source.insight,
                )
            )
    return out


def _compute_source_agreement(
    candidates: list[CandidateView],
    ranking: ConceptRanking | None,
) -> Literal["unanimous", "majority", "split", "outlier", "n/a"]:
    if not candidates or len(candidates) <= 1:
        return "n/a"

    norm_values = [_normalize_value(c.value) for c in candidates]
    counts = Counter(norm_values)
    most_common_value, most_common_count = counts.most_common(1)[0]
    total = len(candidates)

    if most_common_count == total:
        return "unanimous"

    # Determine top-1 value used by ranking (or first candidate as fallback).
    if ranking and ranking.ranked:
        top1_norm = _normalize_value(ranking.ranked[0].value)
    else:
        top1_norm = norm_values[0]

    top1_count = counts.get(top1_norm, 0)
    top1_share = top1_count / total

    # Split: any two distinct values each with >= 30% share.
    distinct_with_min_share = [
        v for v, c in counts.items() if (c / total) >= _AGREEMENT_SPLIT_THRESHOLD
    ]
    if len(distinct_with_min_share) >= 2 and top1_share < (1 - _AGREEMENT_SPLIT_THRESHOLD):
        return "split"

    if top1_share < _AGREEMENT_OUTLIER_THRESHOLD:
        return "outlier"

    if most_common_count / total > _AGREEMENT_MAJORITY_THRESHOLD and top1_norm == most_common_value:
        return "majority"

    return "outlier" if top1_share < _AGREEMENT_MAJORITY_THRESHOLD else "majority"


def _compute_picker(
    candidates: list[CandidateView],
    ranking: ConceptRanking | None,
    agreement: str,
) -> tuple[str, str]:
    """Return (picker_action, picker_rationale_in_catalan)."""
    if ranking is None:
        if not candidates:
            return ("no_value", "Cap candidat per aquest concepte.")
        # Treat as unranked single — fall back to the only candidate.
        if len(candidates) == 1:
            c = candidates[0]
            if c.confidence >= _AUTO_ACCEPT_CONFIDENCE:
                return ("auto_accept", "Una sola font amb confiança alta.")
            return ("soft_review", "Una sola font; verifica abans d'acceptar.")
        return ("soft_review", "Múltiples candidats sense rànquing disponible.")

    status = ranking.status
    if status == "no_candidates":
        return ("no_value", "Cap candidat per aquest concepte.")

    has_conflict = bool(ranking.has_conflict)
    top1_conf = ranking.ranked[0].confidence if ranking.ranked else 0.0

    if status == "single":
        if top1_conf >= _AUTO_ACCEPT_CONFIDENCE:
            return ("auto_accept", "Una sola font amb confiança alta.")
        return ("soft_review", "Una sola font; verifica abans d'acceptar.")

    if (
        agreement == "unanimous"
        and top1_conf >= _AUTO_ACCEPT_CONFIDENCE
        and not has_conflict
    ):
        return ("auto_accept", "Acord unànime entre fonts amb confiança alta.")

    if has_conflict or agreement == "split":
        return (
            "eva_decides",
            "Conflicte detectat o desacord clar entre fonts; cal decisió d'Eva.",
        )

    if agreement == "outlier":
        return (
            "eva_decides",
            "El candidat top-1 és minoritari respecte de la resta de fonts.",
        )

    return ("soft_review", "Revisió suau abans d'acceptar el candidat top-1.")


def _compute_domain_flags(
    candidates: list[CandidateView],
    ranking: ConceptRanking | None,
    eva_value: Any,
) -> list[str]:
    """Return small textual flags useful to surface in the report."""
    flags: list[str] = []
    if not candidates:
        return flags

    # Domain cap mentions in any quote/reasoning.
    for c in candidates:
        text = f"{c.quote} {c.reasoning}"
        if _DOMAIN_CAP_RE.search(text):
            flags.append("Mencions de cap professional / topall en cites o raonaments.")
            break

    # Top-1 source from a prior report?
    if ranking and ranking.ranked:
        top1_path = ranking.ranked[0].source_path
        lower = top1_path.lower()
        if "_informe" in lower or "informe.doc" in lower or "_generated" in lower:
            flags.append(
                "Top-1 prové d'un informe previ — verifica que una font primària hi coincideixi."
            )

    # Eva-vs-pipeline numeric divergence > 50%.
    if (
        ranking
        and ranking.ranked
        and eva_value is not None
        and isinstance(eva_value, (int, float))
        and isinstance(ranking.ranked[0].value, (int, float))
    ):
        try:
            pipe = float(ranking.ranked[0].value)
            eva = float(eva_value)
            denom = abs(eva) if abs(eva) > _NUMERIC_TOLERANCE else 1.0
            if abs(pipe - eva) / denom > 0.5:
                flags.append("Divergència Eva-vs-pipeline > 50% (numèric).")
        except (TypeError, ValueError):
            pass

    return flags


def _eva_rank_in_ranked(
    eva_value: Any,
    ranked: list[RankedCandidate],
) -> tuple[int | None, Literal["exact", "substring", "none"]]:
    """Return (1-indexed position, match_kind) — exact preferred, substring as fallback."""
    for i, rc in enumerate(ranked, start=1):
        if _values_equal(rc.value, eva_value):
            return i, "exact"
    for i, rc in enumerate(ranked, start=1):
        if _eva_match_kind(eva_value, rc.value) == "substring":
            return i, "substring"
    return None, "none"


# ─── Ambiguity hint detection ──────────────────────────────────────────


_NUMERIC_CONCEPT_TYPES = {"number", "integer", "float", "decimal"}


def _has_magnitude_or_type_divergence(
    top1_value: Any, top2_value: Any, concept_type: str = ""
) -> str | None:
    """Detect concept-definition ambiguity between top-1 and top-2 values.

    Returns a short reason string if divergence is detected, else None.

    The numeric magnitude branch only fires when `concept_type` is one of the
    known numeric types — otherwise number-like text identifiers (e.g. an
    expedient like "26.0049") would spuriously trip the divergence flag.
    """
    if top1_value is None or top2_value is None:
        return None

    # Type mismatch (string vs number) — only when one IS a Python number and
    # the other can't be coerced to a number.
    is_num1 = isinstance(top1_value, (int, float)) and not isinstance(top1_value, bool)
    is_num2 = isinstance(top2_value, (int, float)) and not isinstance(top2_value, bool)
    coerced1 = _try_float(top1_value)
    coerced2 = _try_float(top2_value)
    if is_num1 != is_num2 and (coerced1 is None or coerced2 is None):
        return "tipus de valor diferent (string vs numèric)"

    # Numeric magnitude — only applies when the concept itself is numeric.
    is_numeric_concept = concept_type.strip().lower() in _NUMERIC_CONCEPT_TYPES
    if is_numeric_concept and coerced1 is not None and coerced2 is not None:
        a = abs(coerced1)
        b = abs(coerced2)
        if a > _NUMERIC_TOLERANCE and b > _NUMERIC_TOLERANCE:
            if max(a, b) / min(a, b) >= _AMBIGUITY_MAGNITUDE_RATIO:
                return "ordre de magnitud diferent"
        return None
    if coerced1 is not None and coerced2 is not None and not is_numeric_concept:
        # Both look numeric but the concept type is non-numeric (e.g. text id).
        # Skip magnitude check; fall through to string-length check below.
        pass

    # String length ratio.
    s1 = _value_as_string(top1_value)
    s2 = _value_as_string(top2_value)
    if s1 and s2:
        l1 = len(s1)
        l2 = len(s2)
        if min(l1, l2) > 0 and max(l1, l2) / min(l1, l2) >= _AMBIGUITY_LENGTH_RATIO:
            return "longitud molt diferent (>3×)"
    return None


# ─── Build helpers ─────────────────────────────────────────────────────


def _conv_artifact_to_dict(a: ConvertedArtifact) -> dict:
    return a.model_dump()


def _build_concept_journeys(
    concept_defs: dict[str, dict],
    glossary: dict[str, str],
    candidate_views: dict[str, list[CandidateView]],
    ranking: ProjectRanking | None,
    eva_values: dict[str, Any],
    aliases_map: dict[str, list[str]] | None = None,
) -> dict[str, ConceptJourney]:
    out: dict[str, ConceptJourney] = {}
    rankings_by_concept = ranking.concepts if ranking else {}
    groups_by_name = ranking.groups if ranking else {}

    # Pre-compute group → concept_ids mapping for Pass B lookups.
    concepts_in_group: dict[str, list[str]] = defaultdict(list)
    for cid, cdef in concept_defs.items():
        g = cdef.get("group", "")
        if g:
            concepts_in_group[g].append(cid)

    # Universe of concept IDs we want to journey: schema ∪ ranking ∪ candidates.
    # Synthetic / unrecognized concepts still get a journey so callers can see
    # their candidates and Stage 5 outcome — they just have an empty concept_def.
    all_concept_ids: set[str] = set(concept_defs.keys())
    all_concept_ids.update(rankings_by_concept.keys())
    all_concept_ids.update(candidate_views.keys())

    for cid in sorted(all_concept_ids):
        cdef = concept_defs.get(cid, {
            "id": cid, "type": "", "group": "",
            "description_ca": "", "required": False,
        })
        candidates = sorted(
            candidate_views.get(cid, []), key=lambda c: c.candidate_id
        )
        ranking_entry = rankings_by_concept.get(cid)
        group = cdef.get("group", "") or None

        # Pass B: factors mentioning this concept + revision flag.
        group_audit: GroupAuditResult | None = (
            groups_by_name.get(group) if group else None
        )
        factors_mentioning: list[dict] = []
        revision_flag: dict | None = None
        if group_audit:
            for f in group_audit.factors:
                affects = f.get("affects", []) if isinstance(f, dict) else []
                if cid in affects:
                    factors_mentioning.append(dict(f))
            for r in group_audit.revisions:
                if isinstance(r, dict) and r.get("concept_id") == cid:
                    revision_flag = dict(r)
                    break

        # Pass C / no-change guardrail derivation.
        revised = bool(ranking_entry.revised_by_group_pass) if ranking_entry else False
        gfac = ranking_entry.group_factor_considered if ranking_entry else ""
        no_change_fired = (not revised) and bool(gfac)

        # Eva ground truth.
        eva_var, eva_value = _eva_lookup(eva_values, cid, aliases_map)
        if eva_var is None:
            eva_match: Literal["exact", "substring", "mismatch", "no_ground_truth"] = "no_ground_truth"
            eva_rank = None
            eva_rank_kind: Literal["exact", "substring", "none"] = "none"
        else:
            top1_value: Any = None
            if ranking_entry and ranking_entry.ranked:
                top1_value = ranking_entry.ranked[0].value
            elif candidates:
                top1_value = candidates[0].value
            if top1_value is None and not ranking_entry:
                eva_match = "mismatch"
            else:
                eva_match = _eva_match_kind(eva_value, top1_value)
            if ranking_entry and ranking_entry.ranked:
                eva_rank, eva_rank_kind = _eva_rank_in_ranked(
                    eva_value, ranking_entry.ranked
                )
            else:
                eva_rank, eva_rank_kind = None, "none"

        agreement = _compute_source_agreement(candidates, ranking_entry)
        picker_action, picker_rationale = _compute_picker(
            candidates, ranking_entry, agreement
        )
        domain_flags = _compute_domain_flags(candidates, ranking_entry, eva_value)

        journey = ConceptJourney(
            concept_id=cid,
            concept_def=cdef,
            glossary_entry=glossary.get(cid, ""),
            candidates=candidates,
            final_status=ranking_entry.status if ranking_entry else "",
            final_ranked=list(ranking_entry.ranked) if ranking_entry else [],
            final_has_conflict=bool(ranking_entry.has_conflict) if ranking_entry else False,
            final_conflict_note=ranking_entry.conflict_note if ranking_entry else "",
            pass_a_attempts=ranking_entry.attempts if ranking_entry else 0,
            group=group,
            group_factors_mentioning=factors_mentioning,
            group_revision_flag=revision_flag,
            revised_by_group_pass=revised,
            group_factor_considered=gfac,
            no_change_guardrail_fired=no_change_fired,
            eva_value=eva_value,
            eva_top1_match=eva_match,
            eva_rank_in_ranked=eva_rank,
            eva_rank_match_kind=eva_rank_kind,
            picker_action=picker_action,  # type: ignore[arg-type]
            picker_rationale=picker_rationale,
            source_agreement=agreement,
            domain_flags=domain_flags,
        )
        out[cid] = journey
    return out


# ─── Source journeys ───────────────────────────────────────────────────


def _build_source_journeys(
    inventory: Inventory | None,
    typology: ProjectTypology | None,
    conversion: ProjectConversion | None,
    analysis: ProjectAnalysis | None,
    ranking: ProjectRanking | None,
) -> dict[str, SourceJourney]:
    """Return one SourceJourney per source path that appears in any stage."""
    inv_by_path: dict[str, InventoryFile] = {}
    if inventory:
        for f in inventory.files:
            inv_by_path[f.path] = f

    typ_by_path: dict[str, FileClass] = {}
    if typology:
        for f in typology.files:
            typ_by_path[f.path] = f

    arts_by_source: dict[str, list[ConvertedArtifact]] = defaultdict(list)
    if conversion:
        for a in conversion.artifacts:
            if a.source_path:
                arts_by_source[a.source_path].append(a)

    analysis_by_source: dict[str, Any] = {}
    if analysis:
        for s in analysis.sources:
            analysis_by_source[s.source_path] = s

    failure_by_source: dict[str, SourceFailure] = {}
    if analysis:
        for fl in analysis.failures:
            failure_by_source[fl.source_path] = fl

    # Build set of all relevant source paths — anywhere a "source" identity exists.
    all_paths: set[str] = set(typ_by_path.keys()) | set(arts_by_source.keys()) | set(analysis_by_source.keys()) | set(failure_by_source.keys())

    # Map ranking contributions: source_path -> [(concept_id, rank, total, was_revised, rank_change)]
    contrib_by_source: dict[str, list[dict]] = defaultdict(list)
    if ranking:
        for cid, cr in ranking.concepts.items():
            total = len(cr.ranked)
            for i, rc in enumerate(cr.ranked, start=1):
                contrib_by_source[rc.source_path].append(
                    {
                        "concept_id": cid,
                        "rank": i,
                        "rank_total": total,
                        "value": rc.value,
                        "was_revised": bool(cr.revised_by_group_pass),
                        "group_factor_considered": cr.group_factor_considered,
                    }
                )

    out: dict[str, SourceJourney] = {}
    for sp in sorted(all_paths):
        inv_entry = inv_by_path.get(sp)
        typ_entry = typ_by_path.get(sp)
        arts = arts_by_source.get(sp, [])
        sa = analysis_by_source.get(sp)
        fl = failure_by_source.get(sp)
        contrib = sorted(
            contrib_by_source.get(sp, []),
            key=lambda x: (x["concept_id"], x["rank"]),
        )

        candidates_emitted: list[dict] = []
        if sa is not None:
            for c in sa.candidates:
                candidates_emitted.append({
                    "concept_id": c.concept_id,
                    "value": c.value,
                    "confidence": c.confidence,
                    "quote": c.quote,
                })

        out[sp] = SourceJourney(
            source_path=sp,
            inventory=inv_entry.model_dump() if inv_entry else None,
            typology=typ_entry.model_dump() if typ_entry else None,
            artifacts=[_conv_artifact_to_dict(a) for a in arts],
            insight=sa.insight if sa else None,
            candidates_emitted=candidates_emitted,
            pass4_attempts=sa.attempts if sa else 0,
            pass4_failure=fl.model_dump() if fl else None,
            pass4_tokens_in=getattr(sa, "input_tokens", 0) if sa else 0,
            pass4_tokens_out=getattr(sa, "output_tokens", 0) if sa else 0,
            rankings_contributed_to=contrib,
        )
    return out


# ─── Decision audit ────────────────────────────────────────────────────


def _build_decision_audit(
    typology: ProjectTypology | None,
    conversion: ProjectConversion | None,
    analysis: ProjectAnalysis | None,
    ranking: ProjectRanking | None,
) -> DecisionAudit:
    audit = DecisionAudit()

    if typology:
        for f in typology.files:
            if f.category == "reference_output":
                audit.stage2_dev_only_skips.append({
                    "path": f.path,
                    "reason": f.reason,
                })
            elif f.category == "logo_image":
                audit.stage2_logo_skips.append({
                    "path": f.path,
                    "reason": f.reason,
                })

    if conversion:
        for a in conversion.artifacts:
            if a.skipped:
                audit.stage3_conversion_failures.append({
                    "source_path": a.source_path,
                    "strategy_used": a.strategy_used,
                    "skip_reason": a.skip_reason,
                })

    if analysis:
        for s in analysis.sources:
            if s.attempts and s.attempts > 1:
                audit.stage4_retried_sources.append({
                    "source_path": s.source_path,
                    "attempts": s.attempts,
                })
        for fl in analysis.failures:
            audit.stage4_failed_sources.append({
                "source_path": fl.source_path,
                "error_type": fl.error_type,
                "attempts": fl.attempts,
                "last_error": fl.last_error,
            })

    if ranking:
        for cid, cr in ranking.concepts.items():
            if cr.attempts and cr.attempts > 1:
                audit.stage5_pass_a_retries.append({
                    "concept_id": cid,
                    "attempts": cr.attempts,
                })
            if cr.revised_by_group_pass:
                audit.stage5_pass_c_reorderings.append(cid)
            elif cr.group_factor_considered:
                audit.stage5_pass_c_no_change_guardrails.append(cid)

        for group_name, gar in ranking.groups.items():
            count = sum(
                1
                for r in gar.revisions
                if isinstance(r, dict) and bool(r.get("revise"))
            )
            audit.stage5_pass_b_revisions_flagged[group_name] = count

    audit.instrumentation_gaps = [
        "Stage 2 logo filter: pHash distance not stored in ai_typology.json (only the reference name + Hamming integer in `reason`).",
        "Stage 4 cache hits per source: not flagged per-source in ai_analysis.json — only project-level total `cache_hits` is available.",
        "Stage 4 trimmed-prompt retries: the schema-validation retry path isn't recorded distinctly from regular retries; both contribute to `attempts > 1`.",
    ]
    return audit


# ─── Cross-stage analyses ──────────────────────────────────────────────


def _build_cross_stage(
    typology: ProjectTypology | None,
    conversion: ProjectConversion | None,
    analysis: ProjectAnalysis | None,
    ranking: ProjectRanking | None,
    concept_journeys: dict[str, ConceptJourney],
) -> CrossStageAnalysis:
    cs = CrossStageAnalysis()

    # Stage 2 → Stage 4 dropoff.
    useful_sources: set[str] = set()
    if typology:
        for f in typology.files:
            # parent of an extracted image is grouped under the parent (D1#2),
            # so the parent_path is what counts as a "source" downstream.
            if not f.useful or f.conversion_strategy == "skip":
                continue
            if f.parent_path:
                # Extracted images: their effective source is the parent.
                useful_sources.add(f.parent_path)
            else:
                useful_sources.add(f.path)

    analyzed_paths: set[str] = set()
    failed_paths: set[str] = set()
    if analysis:
        analyzed_paths = {s.source_path for s in analysis.sources}
        failed_paths = {f.source_path for f in analysis.failures}

    artifacts_by_source: dict[str, list[ConvertedArtifact]] = defaultdict(list)
    if conversion:
        for a in conversion.artifacts:
            if a.source_path:
                artifacts_by_source[a.source_path].append(a)

    for sp in sorted(useful_sources):
        if sp in analyzed_paths or sp in failed_paths:
            continue
        # Find why it wasn't analyzed.
        arts = artifacts_by_source.get(sp, [])
        if not arts:
            reason = "no Stage 3 artifacts for this source path"
        elif all(a.skipped for a in arts):
            reasons = sorted({a.skip_reason for a in arts if a.skip_reason})
            reason = "all Stage 3 artifacts skipped: " + "; ".join(reasons[:3])
        else:
            reason = "marked useful in Stage 2 but absent from Stage 4 sources"
        cs.stage2_to_stage4_dropoff.append({
            "source_path": sp,
            "stage2_status": "useful",
            "reason_inferred": reason,
        })

    # Stage 4 sources with 0 candidates.
    if analysis:
        for s in analysis.sources:
            if not s.candidates:
                cs.stage4_zero_candidate_sources.append({
                    "source_path": s.source_path,
                    "document_type": s.insight.document_type,
                    "purpose": s.insight.purpose,
                })

    # Concept-level signals.
    for cid, j in concept_journeys.items():
        if j.final_status == "ranked" and j.final_ranked:
            top1_conf = j.final_ranked[0].confidence
            if top1_conf < _LOW_CONFIDENCE_THRESHOLD:
                cs.low_confidence_concepts.append({
                    "concept_id": cid,
                    "top1_confidence": top1_conf,
                })
            distinct_values = {_normalize_value(rc.value) for rc in j.final_ranked}
            n_total = len(j.final_ranked)
            n_distinct = len(distinct_values)
            if n_distinct >= _HIGH_DISAGREEMENT_DISTINCT or (
                n_total > 0 and (n_distinct / n_total) > _HIGH_DISAGREEMENT_RATIO
            ):
                cs.high_disagreement_concepts.append({
                    "concept_id": cid,
                    "distinct_values_count": n_distinct,
                    "distinct_values_ratio": round(n_distinct / n_total, 3) if n_total else 0.0,
                })
            if j.revised_by_group_pass and len(j.final_ranked) >= 1:
                cs.pass_c_reorder_summary.append({
                    "concept_id": cid,
                    "after_top1": j.final_ranked[0].value,
                    "after_top1_source": j.final_ranked[0].source_path,
                    "factor": j.group_factor_considered,
                })
            if j.final_has_conflict and len(j.final_ranked) >= 2:
                # Find the first ranked entry whose value differs from top-1.
                top1 = j.final_ranked[0]
                first_distinct = next(
                    (rc for rc in j.final_ranked[1:] if not _values_equal(rc.value, top1.value)),
                    None,
                )
                if first_distinct is not None:
                    divergence = _has_magnitude_or_type_divergence(
                        top1.value,
                        first_distinct.value,
                        concept_journeys[cid].concept_def.get("type", ""),
                    )
                    if (
                        divergence
                        and top1.confidence >= _AUTO_ACCEPT_CONFIDENCE
                        and first_distinct.confidence >= _AUTO_ACCEPT_CONFIDENCE
                    ):
                        cs.concept_definition_ambiguity_hints.append({
                            "concept_id": cid,
                            "reason": divergence,
                            "top1_value": top1.value,
                            "top2_value": first_distinct.value,
                        })

        # Eva mismatches — routing depends on rank_match_kind:
        #   - exact match at rank ≥ 2  → recoverable (ranker reorder will fix it)
        #   - substring match          → shape mismatch (Eva ref shape differs)
        #   - none + suspect-Eva guard → eva_reference_suspect
        #   - none                     → unrecoverable
        if j.eva_top1_match == "mismatch":
            entry = {
                "concept_id": cid,
                "eva_value": j.eva_value,
                "top1_value": (
                    j.final_ranked[0].value if j.final_ranked else None
                ),
                "eva_rank_in_ranked": j.eva_rank_in_ranked,
                "eva_rank_match_kind": j.eva_rank_match_kind,
            }
            kind = j.eva_rank_match_kind
            if kind == "exact" and (j.eva_rank_in_ranked or 0) >= 2:
                cs.eva_recoverable_mismatches.append(entry)
            elif kind == "substring":
                cs.eva_shape_mismatches.append(entry)
            else:
                # kind == "none" — check suspect-Eva-reference guard.
                top1_conf = (
                    j.final_ranked[0].confidence if j.final_ranked else 0.0
                )
                suspect = (
                    j.source_agreement in ("unanimous", "majority")
                    and top1_conf >= _AUTO_ACCEPT_CONFIDENCE
                )
                if suspect:
                    cs.eva_reference_suspect.append(entry)
                else:
                    cs.eva_unrecoverable_mismatches.append(entry)

    return cs


# ─── Top issues ────────────────────────────────────────────────────────


def _signal_strength_for(kind: str, payload: dict) -> float:
    """Map an issue kind to a 0..1 signal strength."""
    if kind == "eva_unrecoverable_mismatch":
        return 0.95
    if kind == "eva_recoverable_mismatch":
        rank = payload.get("eva_rank_in_ranked") or 1
        # Deeper rank → higher signal (capped at 0.85). Rank 2 = 0.70.
        if rank >= 2:
            return min(0.85, 0.70 + 0.05 * (rank - 2))
        return 0.55
    if kind == "eva_shape_mismatch":
        return 0.30
    if kind == "eva_reference_suspect":
        return 0.50
    if kind == "definition_ambiguity":
        return 0.80
    if kind == "low_confidence":
        return 0.70
    if kind == "pass_c_reorder":
        return 0.65
    if kind == "zero_candidate_source":
        return 0.50
    if kind == "stage4_retry":
        return 0.50
    if kind == "stage2_to_stage4_dropoff":
        return 0.40
    if kind == "high_disagreement":
        return 0.55
    if kind == "stage3_conversion_failure":
        return 0.45
    if kind == "stage4_failure":
        return 0.55
    return 0.30


def _build_top_issues(
    cs: CrossStageAnalysis,
    audit: DecisionAudit,
) -> list[dict]:
    """Rank cross-stage signals by signal strength and cap at 30."""
    issues: list[dict] = []

    for entry in cs.eva_unrecoverable_mismatches:
        issues.append({
            "kind": "eva_unrecoverable_mismatch",
            "concept_id": entry["concept_id"],
            "signal_strength": _signal_strength_for("eva_unrecoverable_mismatch", entry),
            "description": (
                f"Eva's value for {entry['concept_id']} is not present in the ranked candidate list."
            ),
            "suggested_action": (
                "Inspect Stage 4 extraction — the value may have been missed, or Eva's"
                " ground truth shape differs from what the pipeline emits."
            ),
        })

    for entry in cs.eva_recoverable_mismatches:
        issues.append({
            "kind": "eva_recoverable_mismatch",
            "concept_id": entry["concept_id"],
            "signal_strength": _signal_strength_for("eva_recoverable_mismatch", entry),
            "description": (
                f"Eva's value for {entry['concept_id']} sits at rank "
                f"{entry['eva_rank_in_ranked']} of the ranked list."
            ),
            "suggested_action": "Tune authority_principles.md so the ranker prefers Eva's source.",
        })

    for entry in cs.eva_shape_mismatches:
        issues.append({
            "kind": "eva_shape_mismatch",
            "concept_id": entry["concept_id"],
            "signal_strength": _signal_strength_for("eva_shape_mismatch", entry),
            "description": (
                f"Eva's value for {entry['concept_id']} only matches a ranked candidate "
                f"as substring (rank {entry['eva_rank_in_ranked']}). The ground-truth "
                f"shape differs from what the pipeline emits — not a ranker failure."
            ),
            "suggested_action": (
                "Review the Eva reference extraction shape (whole sentence vs token); "
                "consider normalising the reference value."
            ),
        })

    for entry in cs.eva_reference_suspect:
        issues.append({
            "kind": "eva_reference_suspect",
            "concept_id": entry["concept_id"],
            "signal_strength": _signal_strength_for("eva_reference_suspect", entry),
            "description": (
                f"Eva's value for {entry['concept_id']} is absent from the ranked list, "
                f"but the ranker's top-1 has high agreement and high confidence. "
                f"Eva reference may be wrong field — verify against signed informe before tuning ranker."
            ),
            "suggested_action": (
                "Open the signed informe for this concept and confirm the reference "
                "extractor picked the right field before treating this as a ranker miss."
            ),
        })

    for entry in cs.concept_definition_ambiguity_hints:
        issues.append({
            "kind": "definition_ambiguity",
            "concept_id": entry["concept_id"],
            "signal_strength": _signal_strength_for("definition_ambiguity", entry),
            "description": (
                f"Top-2 candidates for {entry['concept_id']} differ by {entry['reason']}; "
                f"both have high confidence — the concept definition may be ambiguous."
            ),
            "suggested_action": (
                "Refine the concept description in report_variables.yaml or split into two concepts."
            ),
        })

    for entry in cs.low_confidence_concepts:
        issues.append({
            "kind": "low_confidence",
            "concept_id": entry["concept_id"],
            "signal_strength": _signal_strength_for("low_confidence", entry),
            "description": (
                f"Top-1 confidence for {entry['concept_id']} is "
                f"{entry['top1_confidence']:.2f} — below {_LOW_CONFIDENCE_THRESHOLD}."
            ),
            "suggested_action": "Inspect the source's quote/reasoning; consider a stronger primary source.",
        })

    for entry in cs.pass_c_reorder_summary:
        issues.append({
            "kind": "pass_c_reorder",
            "concept_id": entry["concept_id"],
            "signal_strength": _signal_strength_for("pass_c_reorder", entry),
            "description": (
                f"Pass C reordered {entry['concept_id']}; new top-1 = "
                f"{entry['after_top1']!r} (factor: {entry['factor'][:120]}…)."
            ),
            "suggested_action": "Check whether the new top-1 is closer to ground truth than the original.",
        })

    for entry in cs.high_disagreement_concepts:
        issues.append({
            "kind": "high_disagreement",
            "concept_id": entry["concept_id"],
            "signal_strength": _signal_strength_for("high_disagreement", entry),
            "description": (
                f"{entry['concept_id']} has {entry['distinct_values_count']} distinct values "
                f"(ratio {entry['distinct_values_ratio']})."
            ),
            "suggested_action": "Inspect candidates — may be transcription/format noise or genuine conflict.",
        })

    for entry in cs.stage4_zero_candidate_sources:
        issues.append({
            "kind": "zero_candidate_source",
            "source_path": entry["source_path"],
            "signal_strength": _signal_strength_for("zero_candidate_source", entry),
            "description": (
                f"Source {entry['source_path']} produced 0 candidates "
                f"(document_type={entry['document_type']!r})."
            ),
            "suggested_action": (
                "Verify the source is relevant; if not, mark as not-useful in Stage 2."
            ),
        })

    for entry in audit.stage4_retried_sources:
        issues.append({
            "kind": "stage4_retry",
            "source_path": entry["source_path"],
            "signal_strength": _signal_strength_for("stage4_retry", entry),
            "description": (
                f"Stage 4 retried {entry['source_path']} {entry['attempts']} times."
            ),
            "suggested_action": "Inspect the cached raw_response if available.",
        })

    for entry in audit.stage4_failed_sources:
        issues.append({
            "kind": "stage4_failure",
            "source_path": entry["source_path"],
            "signal_strength": _signal_strength_for("stage4_failure", entry),
            "description": (
                f"Stage 4 failed on {entry['source_path']} ({entry['error_type']})."
            ),
            "suggested_action": "Refresh Stage 4 or trim Stage 3 output for this source.",
        })

    for entry in cs.stage2_to_stage4_dropoff:
        issues.append({
            "kind": "stage2_to_stage4_dropoff",
            "source_path": entry["source_path"],
            "signal_strength": _signal_strength_for("stage2_to_stage4_dropoff", entry),
            "description": (
                f"Source {entry['source_path']} marked useful in Stage 2 but absent from Stage 4: "
                f"{entry['reason_inferred']}."
            ),
            "suggested_action": "Inspect Stage 3 conversion outputs.",
        })

    for entry in audit.stage3_conversion_failures:
        issues.append({
            "kind": "stage3_conversion_failure",
            "source_path": entry["source_path"],
            "signal_strength": _signal_strength_for("stage3_conversion_failure", entry),
            "description": (
                f"Stage 3 conversion failed for {entry['source_path']} "
                f"(strategy={entry['strategy_used']}): {entry['skip_reason']}"
            ),
            "suggested_action": "Verify converter dependencies (LibreOffice, pandoc, openpyxl, xlrd).",
        })

    issues.sort(key=lambda x: -x["signal_strength"])
    # Dedup by (concept_id or source_path). Highest-signal entry per target wins;
    # the kinds of any subsequent matches are appended to `also_flagged`.
    seen: dict[str, dict] = {}
    order: list[str] = []
    for it in issues:
        key = it.get("concept_id") or it.get("source_path") or f"__id_{id(it)}"
        if key not in seen:
            it_copy = dict(it)
            it_copy["also_flagged"] = []
            seen[key] = it_copy
            order.append(key)
        else:
            kind = it["kind"]
            if kind not in seen[key]["also_flagged"] and kind != seen[key]["kind"]:
                seen[key]["also_flagged"].append(kind)
    deduped = [seen[k] for k in order]
    return deduped[:_TOP_ISSUES_CAP]


# ─── Stage summaries ───────────────────────────────────────────────────


def _summarize_stage1(inv: Inventory | None) -> dict:
    if inv is None:
        return {"available": False}
    types = Counter(f.type for f in inv.files)
    return {
        "available": True,
        "total_files": inv.total_files,
        "root_file_count": inv.root_file_count,
        "msg_count": inv.msg_count,
        "extracted_attachments": inv.extracted_attachments,
        "types": dict(types),
        "scanned_at": inv.scanned_at,
    }


def _summarize_stage2(typ: ProjectTypology | None) -> dict:
    if typ is None:
        return {"available": False}
    return {
        "available": True,
        "total_files": len(typ.files),
        "useful": typ.useful_count,
        "skipped": typ.skipped_count,
        "counts_by_category": dict(typ.counts_by_category),
        "warnings": list(typ.warnings),
        "classified_at": typ.classified_at,
    }


def _summarize_stage3(conv: ProjectConversion | None) -> dict:
    if conv is None:
        return {"available": False}
    by_format: Counter = Counter()
    skipped = 0
    for a in conv.artifacts:
        if a.skipped:
            skipped += 1
            continue
        by_format[a.format] += 1
    return {
        "available": True,
        "total_artifacts": len(conv.artifacts),
        "skipped": skipped,
        "by_format": dict(by_format),
        "total_bytes": conv.total_bytes,
        "warnings": list(conv.warnings),
        "converted_at": conv.converted_at,
        "source_count": len(conv.per_source),
    }


def _summarize_stage4(analysis: ProjectAnalysis | None) -> dict:
    if analysis is None:
        return {"available": False}
    n_candidates = sum(len(s.candidates) for s in analysis.sources)
    doc_types: Counter = Counter()
    for s in analysis.sources:
        doc_types[s.insight.document_type] += 1
    return {
        "available": True,
        "sources": len(analysis.sources),
        "failures": len(analysis.failures),
        "candidates": n_candidates,
        "concepts_covered": len(analysis.candidates_by_concept),
        "estimated_cost_usd": analysis.estimated_cost_usd,
        "input_tokens": analysis.total_input_tokens,
        "output_tokens": analysis.total_output_tokens,
        "cache_hits": analysis.cache_hits,
        "doc_types": dict(doc_types),
        "analyzed_at": analysis.analyzed_at,
        "systemic_failure": (
            analysis.systemic_failure.model_dump() if analysis.systemic_failure else None
        ),
    }


def _summarize_stage5(ranking: ProjectRanking | None) -> dict:
    if ranking is None:
        return {"available": False}
    status_counts: Counter = Counter(c.status for c in ranking.concepts.values())
    n_conflicts = sum(1 for c in ranking.concepts.values() if c.has_conflict)
    n_revised = sum(1 for c in ranking.concepts.values() if c.revised_by_group_pass)
    n_no_change = sum(
        1
        for c in ranking.concepts.values()
        if (not c.revised_by_group_pass) and c.group_factor_considered
    )
    return {
        "available": True,
        "concepts": len(ranking.concepts),
        "status_counts": dict(status_counts),
        "conflicts": n_conflicts,
        "groups_audited": len(ranking.groups),
        "pass_c_reorderings": n_revised,
        "pass_c_no_change_guardrails": n_no_change,
        "estimated_cost_usd": ranking.estimated_cost_usd,
        "input_tokens": ranking.total_input_tokens,
        "output_tokens": ranking.total_output_tokens,
        "cache_hits": ranking.cache_hits,
        "ranked_at": ranking.ranked_at,
    }


def _summarize_eva(
    concept_journeys: dict[str, ConceptJourney],
) -> dict:
    compared = sum(
        1 for j in concept_journeys.values() if j.eva_top1_match != "no_ground_truth"
    )
    exact = sum(1 for j in concept_journeys.values() if j.eva_top1_match == "exact")
    substring = sum(
        1 for j in concept_journeys.values() if j.eva_top1_match == "substring"
    )
    mismatch = sum(
        1 for j in concept_journeys.values() if j.eva_top1_match == "mismatch"
    )
    accuracy = (exact / compared) if compared else 0.0
    return {
        "compared": compared,
        "exact": exact,
        "substring": substring,
        "mismatch": mismatch,
        "top1_accuracy": round(accuracy, 4),
    }


# ─── Public API ────────────────────────────────────────────────────────


def build_trace(project_path: Path | str) -> PipelineTrace:
    """Build a PipelineTrace by joining all five Stage manifests + Eva ground truth."""
    pp = Path(project_path).resolve()
    if not pp.is_dir():
        raise ValueError(f"Not a directory: {pp}")

    inv = load_inventory(pp)
    typ = load_typology(pp)
    conv = load_conversion(pp)
    analysis = load_analysis(pp)
    ranking = load_ranking(pp)
    eva_values = _load_eva_reference(pp)

    concept_defs = _load_concept_definitions()
    glossary = _load_glossary_entries()
    template_aliases = _load_template_aliases()

    candidate_views = _build_candidate_views(analysis)
    concept_journeys = _build_concept_journeys(
        concept_defs, glossary, candidate_views, ranking, eva_values,
        aliases_map=template_aliases,
    )
    source_journeys = _build_source_journeys(inv, typ, conv, analysis, ranking)
    decisions = _build_decision_audit(typ, conv, analysis, ranking)
    cross_stage = _build_cross_stage(typ, conv, analysis, ranking, concept_journeys)
    top_issues = _build_top_issues(cross_stage, decisions)

    return PipelineTrace(
        project_path=str(pp),
        project_name=pp.name,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        concepts=concept_journeys,
        sources=source_journeys,
        decisions=decisions,
        cross_stage=cross_stage,
        stage1_summary=_summarize_stage1(inv),
        stage2_summary=_summarize_stage2(typ),
        stage3_summary=_summarize_stage3(conv),
        stage4_summary=_summarize_stage4(analysis),
        stage5_summary=_summarize_stage5(ranking),
        eva_summary=_summarize_eva(concept_journeys),
        top_issues=top_issues,
    )


def save_trace(trace: PipelineTrace, project_path: Path | str) -> Path:
    pp = Path(project_path).resolve()
    out_dir = pp / "validation"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / _TRACE_FILENAME
    out_path.write_text(trace.model_dump_json(indent=2), encoding="utf-8")
    return out_path


def load_trace(project_path: Path | str) -> PipelineTrace | None:
    pp = Path(project_path).resolve()
    p = pp / "validation" / _TRACE_FILENAME
    if not p.is_file():
        return None
    try:
        return PipelineTrace.model_validate_json(p.read_text(encoding="utf-8"))
    except Exception:
        return None


# ─── Diff (used by --diff CLI flag) ────────────────────────────────────


def diff_traces(prior: PipelineTrace, current: PipelineTrace) -> dict:
    """Return a small diff dict between two traces.

    Reports concepts whose top-1 changed, conflicts gained/lost, and Pass C
    direction changes.
    """
    out: dict[str, list[dict]] = {
        "top1_changed": [],
        "conflicts_gained": [],
        "conflicts_lost": [],
        "pass_c_changed": [],
    }
    common_ids = set(prior.concepts.keys()) & set(current.concepts.keys())
    for cid in sorted(common_ids):
        a = prior.concepts[cid]
        b = current.concepts[cid]
        a_top1 = a.final_ranked[0].value if a.final_ranked else None
        b_top1 = b.final_ranked[0].value if b.final_ranked else None
        if not _values_equal(a_top1, b_top1):
            out["top1_changed"].append({
                "concept_id": cid,
                "before": a_top1,
                "after": b_top1,
            })
        if (not a.final_has_conflict) and b.final_has_conflict:
            out["conflicts_gained"].append({"concept_id": cid})
        elif a.final_has_conflict and (not b.final_has_conflict):
            out["conflicts_lost"].append({"concept_id": cid})
        if a.revised_by_group_pass != b.revised_by_group_pass:
            out["pass_c_changed"].append({
                "concept_id": cid,
                "before": a.revised_by_group_pass,
                "after": b.revised_by_group_pass,
            })
    return out
