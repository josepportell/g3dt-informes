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

import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, ValidationError

from .analysis import Candidate, ProjectAnalysis, SourceInsight, _classify_error, load_analysis

logger = logging.getLogger(__name__)

# ─── Configuration ─────────────────────────────────────────────────────

_RANKING_ROOT = Path("validation") / "ai_pipeline" / "ranking"
_RANKING_MANIFEST = Path("validation") / "ai_ranking.json"

_DEFAULT_MODEL = "claude-sonnet-4-6"
_SCHEMA_VERSION = "1.0"

_MAX_TOKENS = 4_000
_PER_CALL_TIMEOUT_S = 60.0
_MAX_RETRIES_PER_CONCEPT = 3
_BACKOFF_INITIAL_S = 2.0
_CIRCUIT_BREAKER_THRESHOLD = 3

_PRICING = {
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    "claude-opus-4-7": {"input": 15.0, "output": 75.0},
}

# Anthropic prompt-caching multipliers relative to the base input price.
_CACHE_CREATION_MULTIPLIER = 1.25
_CACHE_READ_MULTIPLIER = 0.1

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_AUTHORITY_PRINCIPLES_PATH = (
    _PROJECT_ROOT / "schemas" / "ai_pipeline" / "authority_principles.md"
)
_GLOSSARY_PATH = _PROJECT_ROOT / "schemas" / "ai_pipeline" / "concept_glossary.yaml"

_SYSTEM_PROMPT = """Ets un assistent de redacció d'informes geotècnics treballant per a Eva (G3 Geotècnia).
Per un concept_id concret, reps diversos candidats de valor extrets de fonts diferents (plànols, emails, fitxes de camp, pressupostos, laboratori…) i els ordenes del més fiable al menys, segons els principis d'autoritat d'Eva.

Regles invariants:
- No inventes candidats nous. No alteres valors.
- Tots els candidate_id originals han d'aparèixer exactament una vegada a l'ordenació (cap duplicat, cap omissió).
- Si dos candidats tenen valors significativament diferents amb confiança raonable, marca `has_conflict=true` i descriu-ho a `conflict_note` en una frase.
- Retorna sempre una única tool call `emit_ranking`. Cap prosa."""


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


# ─── Glossary loading ──────────────────────────────────────────────────


_GLOSSARY_CACHE: dict | None = None


def _get_glossary() -> dict:
    global _GLOSSARY_CACHE
    if _GLOSSARY_CACHE is not None:
        return _GLOSSARY_CACHE
    if not _GLOSSARY_PATH.is_file():
        _GLOSSARY_CACHE = {}
        return _GLOSSARY_CACHE
    try:
        data = yaml.safe_load(_GLOSSARY_PATH.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    _GLOSSARY_CACHE = data
    return _GLOSSARY_CACHE


def load_glossary_entry(concept_id: str) -> str:
    """Return the glossary entry for a concept_id as YAML-formatted text, or ''.

    Looks under the top-level `entries:` key. Callers embed the result in the
    Pass A user content.
    """
    data = _get_glossary()
    entries = data.get("entries", {}) if isinstance(data, dict) else {}
    entry = entries.get(concept_id)
    if not entry:
        return ""
    return yaml.safe_dump(
        {concept_id: entry}, allow_unicode=True, sort_keys=False
    ).strip()


# ─── Tool schema ───────────────────────────────────────────────────────


def _build_ranking_tool_schema() -> dict:
    return {
        "name": "emit_ranking",
        "description": (
            "Emit the ordered candidate list for this concept, from most to "
            "least trusted, and flag whether the top candidates conflict."
        ),
        "input_schema": {
            "type": "object",
            "required": ["ranked", "has_conflict"],
            "properties": {
                "ranked": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["candidate_id", "rationale"],
                        "properties": {
                            "candidate_id": {"type": "string"},
                            "rationale": {"type": "string"},
                        },
                    },
                },
                "has_conflict": {"type": "boolean"},
                "conflict_note": {"type": "string"},
            },
        },
    }


# ─── Prompt building ───────────────────────────────────────────────────


def _build_concept_user_content(
    concept_def: dict,
    glossary_entry: str,
    principles: str,
    candidates_with_insights: list[tuple[str, SourceInsight, Candidate]],
    *,
    include_principles: bool = True,
) -> list[dict]:
    """Build Anthropic `content` blocks for one Pass A call.

    When `include_principles=False`, both the glossary entry and the cached
    principles block are dropped on the retry path (mirrors analysis.py D5:
    trimmed prompt on schema-violation retry — drop everything non-essential).
    """
    cid = concept_def.get("id", "")
    ctype = concept_def.get("type", "")
    cgroup = concept_def.get("group", "")
    cdesc = concept_def.get("description_ca", "")

    header = (
        f"# Concept to rank\n\n"
        f"**concept_id**: `{cid}` (type={ctype}, group={cgroup})\n\n"
        f"{cdesc}\n"
    )
    if include_principles and glossary_entry:
        header += f"\n## Glossary entry\n\n```yaml\n{glossary_entry}\n```\n"

    blocks: list[dict] = [{"type": "text", "text": header}]

    if include_principles and principles:
        blocks.append(
            {
                "type": "text",
                "text": (
                    f"\n# Authority principles (Eva)\n\n{principles}\n"
                ),
                "cache_control": {"type": "ephemeral"},
            }
        )

    # Deterministic candidate order by candidate_id.
    sorted_candidates = sorted(candidates_with_insights, key=lambda t: t[0])
    for i, (candidate_id, insight, candidate) in enumerate(sorted_candidates, 1):
        payload = {
            "candidate_id": candidate_id,
            "value": candidate.value,
            "confidence": candidate.confidence,
            "quote": candidate.quote,
            "reasoning": candidate.reasoning,
            "source": {
                "path": candidate.source_path,
                "document_type": insight.document_type,
                "purpose": insight.purpose,
                "author": insight.author,
                "date_info": insight.date_info,
                "version_info": insight.version_info,
                "authority_hints": list(insight.authority_hints),
                "source_chain": list(candidate.source_chain),
            },
        }
        blocks.append(
            {
                "type": "text",
                "text": (
                    f"\n--- candidate {i} ---\n"
                    f"```json\n{json.dumps(payload, ensure_ascii=False, default=str, indent=2)}\n```\n"
                ),
            }
        )

    blocks.append(
        {
            "type": "text",
            "text": (
                "\nRetorna exactament una tool call `emit_ranking`. "
                "Cap duplicat ni omissió de candidate_id."
            ),
        }
    )
    return blocks


# ─── Cache ─────────────────────────────────────────────────────────────


_SLUG_RE = re.compile(r"[^A-Za-z0-9]+")


def _slugify(s: str) -> str:
    slug = _SLUG_RE.sub("_", s).strip("_")
    return slug or "unnamed"


def _concept_cache_path(pp: Path, concept_id: str) -> Path:
    return pp / _RANKING_ROOT / f"{_slugify(concept_id)}_cache.json"


def _concept_cache_key(
    concept_id: str,
    candidates_with_insights: list[tuple[str, SourceInsight, Candidate]],
    principles: str,
    model: str,
    concept_def: dict,
    glossary_entry: str,
) -> str:
    h = hashlib.sha256()
    h.update(
        f"schema:{_SCHEMA_VERSION}|model:{model}|concept:{concept_id}".encode()
    )
    h.update(b"|principles:")
    h.update(principles.encode("utf-8"))
    h.update(b"|concept_def:")
    h.update(
        json.dumps(
            concept_def, ensure_ascii=False, sort_keys=True, default=str
        ).encode("utf-8")
    )
    h.update(b"|glossary:")
    h.update(glossary_entry.encode("utf-8"))
    canon = []
    for candidate_id, insight, candidate in sorted(
        candidates_with_insights, key=lambda t: t[0]
    ):
        canon.append(
            {
                "candidate_id": candidate_id,
                "value": candidate.value,
                "confidence": candidate.confidence,
                "quote": candidate.quote,
                "source_path": candidate.source_path,
                "document_type": insight.document_type,
                "version_info": insight.version_info,
            }
        )
    h.update(b"|candidates:")
    h.update(
        json.dumps(canon, ensure_ascii=False, sort_keys=True, default=str).encode(
            "utf-8"
        )
    )
    return h.hexdigest()


def _concept_cache_read(
    pp: Path, concept_id: str, key: str
) -> ConceptRanking | None:
    cache_file = _concept_cache_path(pp, concept_id)
    if not cache_file.is_file():
        return None
    try:
        payload = json.loads(cache_file.read_text(encoding="utf-8"))
        if payload.get("key") != key:
            return None
        return ConceptRanking.model_validate(payload["ranking"])
    except Exception:
        return None


def _concept_cache_write(
    pp: Path, concept_id: str, key: str, ranking: ConceptRanking
) -> None:
    cache_file = _concept_cache_path(pp, concept_id)
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {"key": key, "ranking": ranking.model_dump()}
    cache_file.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# ─── Client resolution ────────────────────────────────────────────────


def _get_client(model: str):
    try:
        import anthropic  # noqa: F401
    except ImportError as e:
        raise RuntimeError("anthropic SDK not installed") from e
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    import anthropic as _anthropic
    return _anthropic.Anthropic()


# ─── Per-concept ranker ───────────────────────────────────────────────


def _extract_ranking_tool_use(response) -> dict | None:
    for block in getattr(response, "content", []):
        if (
            getattr(block, "type", None) == "tool_use"
            and getattr(block, "name", "") == "emit_ranking"
        ):
            return getattr(block, "input", None)
    return None


def _rank_one_concept(
    client,
    pp: Path,
    concept_def: dict,
    candidates_with_insights: list[tuple[str, SourceInsight, Candidate]],
    model: str,
    principles: str,
    *,
    force: bool = False,
) -> tuple[ConceptRanking | None, dict | None, bool, bool, dict]:
    """Rank one concept via a single Pass A LLM call.

    Returns (ranking, failure, is_systemic, from_cache, token_counts).
    `token_counts` has keys {"input", "output", "cache_creation", "cache_read"};
    zeroed for cache-hit and failure paths (aligns with analysis.py accounting).
    """
    concept_id = concept_def["id"]
    tool_schema = _build_ranking_tool_schema()
    glossary_entry = load_glossary_entry(concept_id)

    key = _concept_cache_key(
        concept_id,
        candidates_with_insights,
        principles,
        model,
        concept_def,
        glossary_entry,
    )

    zero_tokens = {
        "input": 0,
        "output": 0,
        "cache_creation": 0,
        "cache_read": 0,
    }

    if not force:
        cached = _concept_cache_read(pp, concept_id, key)
        if cached is not None:
            return (cached, None, False, True, dict(zero_tokens))

    input_candidate_ids = {cid for cid, _, _ in candidates_with_insights}
    candidate_by_id = {
        cid: (insight, candidate)
        for cid, insight, candidate in candidates_with_insights
    }

    last_error: Exception | None = None
    raw_response: str = ""
    attempts = 0
    trimmed_retry = False
    total_input_tokens = 0
    total_output_tokens = 0
    total_cache_creation = 0
    total_cache_read = 0

    started = time.monotonic()
    for attempt in range(1, _MAX_RETRIES_PER_CONCEPT + 1):
        attempts = attempt
        content = _build_concept_user_content(
            concept_def,
            glossary_entry,
            principles,
            candidates_with_insights,
            include_principles=not trimmed_retry,
        )
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=_MAX_TOKENS,
                system=_SYSTEM_PROMPT,
                tools=[tool_schema],
                tool_choice={"type": "tool", "name": "emit_ranking"},
                messages=[{"role": "user", "content": content}],
                timeout=_PER_CALL_TIMEOUT_S,
            )
        except Exception as e:
            err_type, systemic = _classify_error(e)
            last_error = e
            if systemic:
                return (
                    None,
                    {
                        "concept_id": concept_id,
                        "error_type": err_type,
                        "attempts": attempt,
                        "last_error": str(e),
                        "raw_response": "",
                    },
                    True,
                    False,
                    dict(zero_tokens),
                )
            if attempt < _MAX_RETRIES_PER_CONCEPT:
                time.sleep(_BACKOFF_INITIAL_S * (2 ** (attempt - 1)))
                continue
            return (
                None,
                {
                    "concept_id": concept_id,
                    "error_type": err_type,
                    "attempts": attempt,
                    "last_error": str(e),
                    "raw_response": "",
                },
                False,
                False,
                dict(zero_tokens),
            )

        usage = getattr(resp, "usage", None)
        if usage is not None:
            total_input_tokens += getattr(usage, "input_tokens", 0) or 0
            total_output_tokens += getattr(usage, "output_tokens", 0) or 0
            total_cache_creation += (
                getattr(usage, "cache_creation_input_tokens", 0) or 0
            )
            total_cache_read += (
                getattr(usage, "cache_read_input_tokens", 0) or 0
            )

        tool_input = _extract_ranking_tool_use(resp)
        raw_response = (
            json.dumps(tool_input, default=str)[:8000] if tool_input else ""
        )
        if tool_input is None:
            last_error = RuntimeError("model returned no emit_ranking tool call")
            # Align with analysis.py: empty tool_use is treated as transient —
            # retry with the SAME full prompt (don't drop the principles block).
            if attempt < _MAX_RETRIES_PER_CONCEPT:
                continue
            return (
                None,
                {
                    "concept_id": concept_id,
                    "error_type": "empty_response",
                    "attempts": attempt,
                    "last_error": str(last_error),
                    "raw_response": raw_response,
                },
                False,
                False,
                dict(zero_tokens),
            )

        try:
            ranked_raw = tool_input.get("ranked")
            has_conflict = bool(tool_input.get("has_conflict", False))
            conflict_note = str(tool_input.get("conflict_note", "") or "")
            if not isinstance(ranked_raw, list) or not ranked_raw:
                raise ValueError("`ranked` must be a non-empty list")

            seen_ids: set[str] = set()
            ranked_entries: list[RankedCandidate] = []
            for item in ranked_raw:
                if not isinstance(item, dict):
                    raise ValueError("each ranked entry must be an object")
                cid_out = item.get("candidate_id")
                rationale = item.get("rationale", "")
                if not isinstance(cid_out, str):
                    raise ValueError("candidate_id must be a string")
                if cid_out in seen_ids:
                    raise ValueError(
                        f"duplicate candidate_id in ranking: {cid_out!r}"
                    )
                if cid_out not in input_candidate_ids:
                    raise ValueError(
                        f"invented candidate_id not in inputs: {cid_out!r}"
                    )
                seen_ids.add(cid_out)
                insight, candidate = candidate_by_id[cid_out]
                ranked_entries.append(
                    RankedCandidate(
                        candidate_id=cid_out,
                        source_path=candidate.source_path,
                        value=candidate.value,
                        confidence=candidate.confidence,
                        rationale=str(rationale or ""),
                    )
                )
            missing = input_candidate_ids - seen_ids
            if missing:
                raise ValueError(
                    f"ranking omits candidate_ids: {sorted(missing)!r}"
                )

            ranking = ConceptRanking(
                concept_id=concept_id,
                status="ranked",
                ranked=ranked_entries,
                has_conflict=has_conflict,
                conflict_note=conflict_note,
                attempts=attempt,
                elapsed_ms=int((time.monotonic() - started) * 1000),
                model=model,
            )
            _concept_cache_write(pp, concept_id, key, ranking)
            token_counts = {
                "input": total_input_tokens,
                "output": total_output_tokens,
                "cache_creation": total_cache_creation,
                "cache_read": total_cache_read,
            }
            return (ranking, None, False, False, token_counts)
        except (ValidationError, ValueError) as ve:
            last_error = ve
            if attempt < _MAX_RETRIES_PER_CONCEPT:
                trimmed_retry = True
                continue
            return (
                None,
                {
                    "concept_id": concept_id,
                    "error_type": "schema_validation",
                    "attempts": attempt,
                    "last_error": str(ve)[:500],
                    "raw_response": raw_response,
                },
                False,
                False,
                dict(zero_tokens),
            )

    # Unreachable
    return (
        None,
        {
            "concept_id": concept_id,
            "error_type": "unknown_error",
            "attempts": attempts,
            "last_error": str(last_error) if last_error else "",
            "raw_response": raw_response,
        },
        False,
        False,
        dict(zero_tokens),
    )


# ─── Summary ──────────────────────────────────────────────────────────


def _build_ranking_summary(
    ranking: ProjectRanking,
    *,
    principles_missing: bool,
) -> list[str]:
    n_ranked = sum(1 for c in ranking.concepts.values() if c.status == "ranked")
    n_single = sum(1 for c in ranking.concepts.values() if c.status == "single")
    n_none = sum(
        1 for c in ranking.concepts.values() if c.status == "no_candidates"
    )
    n_pending = sum(
        1 for c in ranking.concepts.values() if c.status == "pending_fase5"
    )
    n_conflicts = sum(
        1 for c in ranking.concepts.values() if c.has_conflict
    )
    lines = [
        f"Rànquing de Fase 5: {n_ranked} conceptes rankejats, "
        f"{n_single} amb font única, {n_none} sense candidats, "
        f"{n_pending} pendents de revisió manual."
    ]
    if n_conflicts:
        lines.append(f"• {n_conflicts} conceptes amb conflicte detectat entre fonts.")
    if ranking.cache_hits:
        lines.append(
            f"• {ranking.cache_hits} conceptes servits des de cache (0 $)."
        )
    if ranking.estimated_cost_usd > 0:
        lines.append(
            f"• Cost estimat d'aquesta passada: ${ranking.estimated_cost_usd:.4f}"
        )
    if principles_missing:
        lines.append(
            "⚠ authority_principles.md buit o absent — el rànquing s'ha fet "
            "sense principis d'autoritat."
        )
    if ranking.failures:
        lines.append(
            f"⚠ {len(ranking.failures)} conceptes no s'han pogut rankejar."
        )
    return lines


# ─── Orchestrator ─────────────────────────────────────────────────────


def rank_project(
    project_path: Path | str,
    *,
    analysis: ProjectAnalysis | None = None,
    model: str | None = None,
    concept_filter: str | set[str] | None = None,
    force: bool = False,
    client=None,
) -> ProjectRanking:
    """Run Pass A of Stage 5: per-concept authority ranking via LLM.

    Concepts with 0 candidates → `no_candidates`. With 1 candidate → `single`.
    With ≥2 candidates → LLM call through Pass A. Missing inputs (no analysis)
    raise ValueError.
    """
    pp = Path(project_path).resolve()

    if analysis is None:
        analysis = load_analysis(pp)
        if analysis is None:
            raise ValueError(
                f"No ai_analysis.json at {pp}; run Stage 4 first"
            )

    model = model or os.environ.get("G3DT_AI_MODEL_RANKER", _DEFAULT_MODEL)

    concept_defs = load_concept_definitions()
    by_concept = _extract_candidates_by_concept(analysis)
    principles = load_authority_principles()
    principles_missing = not principles.strip()
    if principles_missing:
        logger.warning(
            "authority_principles.md is empty or missing; ranking runs without principles"
        )

    # Normalize concept_filter to a set or None.
    filter_set: set[str] | None
    if concept_filter is None:
        filter_set = None
    elif isinstance(concept_filter, str):
        filter_set = {concept_filter}
    else:
        filter_set = set(concept_filter)

    concepts: dict[str, ConceptRanking] = {}
    failures: list[dict] = []
    systemic_aborted = False
    systemic_reason = ""
    total_input = 0
    total_output = 0
    total_cache_creation = 0
    total_cache_read = 0
    cache_hits = 0
    consecutive_failures = 0

    # Sort concepts deterministically.
    ordered_cids = sorted(concept_defs.keys())

    # Partition work: passthrough first (0/1 candidates), LLM second (≥2).
    llm_cids: list[str] = []
    for cid in ordered_cids:
        if filter_set is not None and cid not in filter_set:
            continue
        entries = by_concept.get(cid, [])
        if len(entries) == 0:
            concepts[cid] = ConceptRanking(concept_id=cid, status="no_candidates")
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
        else:
            llm_cids.append(cid)

    # Resolve client lazily — only if LLM work is needed.
    if llm_cids and client is None:
        try:
            client = _get_client(model)
        except RuntimeError as e:
            msg = str(e)
            err_type = (
                "missing_api_key" if "ANTHROPIC_API_KEY" in msg else "sdk_missing"
            )
            for cid in llm_cids:
                concepts[cid] = ConceptRanking(
                    concept_id=cid, status="pending_fase5"
                )
            failures.append(
                {
                    "concept_id": "*",
                    "error_type": err_type,
                    "attempts": 0,
                    "last_error": msg,
                    "raw_response": "",
                }
            )
            ranking = ProjectRanking(
                project_path=str(pp),
                ranked_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                concepts=concepts,
                failures=failures,
                schema_version=_SCHEMA_VERSION,
            )
            ranking.eva_summary = _build_ranking_summary(
                ranking, principles_missing=principles_missing
            )
            return ranking

    for i, cid in enumerate(llm_cids):
        if systemic_aborted:
            concepts[cid] = ConceptRanking(concept_id=cid, status="pending_fase5")
            continue

        entries = by_concept[cid]
        concept_def = concept_defs[cid]
        ranking_obj, failure, is_systemic, from_cache, token_counts = (
            _rank_one_concept(
                client, pp, concept_def, entries, model, principles, force=force,
            )
        )

        if ranking_obj is not None:
            concepts[cid] = ranking_obj
            if from_cache:
                cache_hits += 1
            else:
                total_input += token_counts["input"]
                total_output += token_counts["output"]
                total_cache_creation += token_counts["cache_creation"]
                total_cache_read += token_counts["cache_read"]
            consecutive_failures = 0
            continue

        # Failure path
        if failure is not None:
            failures.append(failure)
        concepts[cid] = ConceptRanking(concept_id=cid, status="pending_fase5")

        if is_systemic:
            systemic_aborted = True
            systemic_reason = (
                failure.get("error_type", "systemic") if failure else "systemic"
            )
            # Mark remaining as pending
            for remaining in llm_cids[i + 1 :]:
                concepts[remaining] = ConceptRanking(
                    concept_id=remaining, status="pending_fase5"
                )
            break

        consecutive_failures += 1
        if consecutive_failures >= _CIRCUIT_BREAKER_THRESHOLD:
            systemic_aborted = True
            systemic_reason = "circuit_breaker"
            failures.append(
                {
                    "concept_id": "*",
                    "error_type": "circuit_breaker",
                    "attempts": 0,
                    "last_error": (
                        f"{_CIRCUIT_BREAKER_THRESHOLD} consecutive non-systemic "
                        f"failures; aborted remaining concepts."
                    ),
                    "raw_response": "",
                }
            )
            for remaining in llm_cids[i + 1 :]:
                concepts[remaining] = ConceptRanking(
                    concept_id=remaining, status="pending_fase5"
                )
            break

    price = _PRICING.get(model, {"input": 0.0, "output": 0.0})
    estimated_cost = (
        total_input * price["input"]
        + total_cache_creation * price["input"] * _CACHE_CREATION_MULTIPLIER
        + total_cache_read * price["input"] * _CACHE_READ_MULTIPLIER
        + total_output * price["output"]
    ) / 1_000_000.0

    ranking = ProjectRanking(
        project_path=str(pp),
        ranked_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        concepts=concepts,
        failures=failures,
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        total_cache_creation_tokens=total_cache_creation,
        total_cache_read_tokens=total_cache_read,
        estimated_cost_usd=round(estimated_cost, 6),
        cache_hits=cache_hits,
        schema_version=_SCHEMA_VERSION,
    )
    ranking.eva_summary = _build_ranking_summary(
        ranking, principles_missing=principles_missing
    )
    return ranking
