"""Stage 4: analysis — per-source LLM call producing SourceInsight + Candidates.

Groups Stage 3 artifacts by source_path, issues one multimodal call per source
via Anthropic's `tools` API with a strict JSON schema, and writes a manifest
at validation/ai_analysis.json.

Design doc: docs/ARQUITECTURA-AI-PIPELINE.md §7
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationError

from .conversion import ConvertedArtifact, ProjectConversion, convert_project
from .typology import FileClass, ProjectTypology

logger = logging.getLogger(__name__)

# ─── Configuration ─────────────────────────────────────────────────────

_ANALYSIS_ROOT = Path("validation") / "ai_pipeline" / "analysis"
_ANALYSIS_MANIFEST = Path("validation") / "ai_analysis.json"

_DEFAULT_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 8_000
_SCHEMA_VERSION = "1.0"

# Per-source caps so a pathological source doesn't blow the context window
_MAX_ARTIFACTS_PER_SOURCE = 30
_MAX_TEXT_BYTES_PER_SOURCE = 250_000
_MAX_IMAGES_PER_SOURCE = 16  # Sonnet accepts up to 100 but cost stays reasonable

# Per-source retry caps
_MAX_RETRIES_PER_SOURCE = 3
_BACKOFF_INITIAL_S = 2.0

# Circuit breaker: abort project if N consecutive non-systemic failures
_CIRCUIT_BREAKER_THRESHOLD = 3

# Approximate pricing (USD per 1M tokens). Used only for display, not billing.
_PRICING = {
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    "claude-opus-4-7": {"input": 15.0, "output": 75.0},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
}

# System prompt — short, task-focused, returns a tool call.
_SYSTEM_PROMPT = """You are an expert analyst for geotechnical engineering projects in Catalonia/Spain.
You read project documents (architect plans, field sheets, emails, budgets, lab reports) and extract
structured information for a report-writing assistant.

Your job on each call:
1. Identify what the source document IS (its type, author, purpose, version, date).
2. Extract every value you can find that matches one of the listed concepts.
3. Never invent. Every value must have a verbatim `quote` from the source.
4. Confidence in [0, 1]: 1.0 for crisp explicit values ("Plot area: 518 m²"),
   0.6-0.8 for inferred/derived, below 0.5 when the source is ambiguous.
5. Return exactly one `emit_analysis` tool call.

You never produce prose, only the tool call."""


# ─── Models ────────────────────────────────────────────────────────────


class SourceInsight(BaseModel):
    """LLM's structured understanding of what a source document IS."""

    source_path: str
    document_type: str
    purpose: str
    author: str = ""
    date_info: str = ""
    version_info: str = ""
    related_sources: list[str] = Field(default_factory=list)
    authority_hints: list[str] = Field(default_factory=list)
    confidence: float = 0.5
    notes: str = ""


class Candidate(BaseModel):
    """One candidate value for one concept, extracted from one source."""

    concept_id: str
    value: Any
    confidence: float = 0.5
    quote: str = ""
    artifact_path: str = ""
    source_path: str = ""
    source_chain: list[str] = Field(default_factory=list)
    extractor: str = ""
    reasoning: str = ""


class SourceAnalysis(BaseModel):
    """Everything Stage 4 emits for one source."""

    source_path: str
    insight: SourceInsight
    candidates: list[Candidate] = Field(default_factory=list)
    attempts: int = 1
    elapsed_ms: int = 0
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


class SourceFailure(BaseModel):
    """A source Stage 4 could not analyze (per-source failure)."""

    source_path: str
    error_type: str
    attempts: int
    last_error: str
    raw_response: str = ""


class SystemicFailure(BaseModel):
    """Project-wide fail-fast: API key missing, insufficient credits, model not found."""

    error_type: str
    message: str
    sources_skipped: int = 0


class ProjectAnalysis(BaseModel):
    project_path: str
    analyzed_at: str
    sources: list[SourceAnalysis] = Field(default_factory=list)
    failures: list[SourceFailure] = Field(default_factory=list)
    systemic_failure: SystemicFailure | None = None
    candidates_by_concept: dict[str, list[str]] = Field(default_factory=dict)
    eva_summary: list[str] = Field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    cache_hits: int = 0
    schema_version: str = _SCHEMA_VERSION

    def candidates_of(self, concept_id: str) -> list[Candidate]:
        out: list[Candidate] = []
        for s in self.sources:
            for c in s.candidates:
                if c.concept_id == concept_id:
                    out.append(c)
        return out


# ─── Concept schema loading ────────────────────────────────────────────


_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _load_concept_yaml() -> str:
    path = _PROJECT_ROOT / "schemas" / "concepts" / "report_variables.yaml"
    return path.read_text(encoding="utf-8")


def _load_concept_ids() -> list[str]:
    """Return the list of concept IDs known to the report."""
    path = _PROJECT_ROOT / "schemas" / "concepts" / "report_variables.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    concepts = data.get("concepts", {}) if isinstance(data, dict) else {}
    return sorted(concepts.keys())


def _load_glossary() -> str:
    path = _PROJECT_ROOT / "schemas" / "ai_pipeline" / "concept_glossary.yaml"
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


# ─── Source grouping ───────────────────────────────────────────────────


def _group_artifacts_by_source(conv: ProjectConversion) -> dict[str, list[ConvertedArtifact]]:
    groups: dict[str, list[ConvertedArtifact]] = defaultdict(list)
    for a in conv.artifacts:
        if a.skipped or not a.path:
            continue
        groups[a.source_path].append(a)
    # Deterministic order per source
    for arts in groups.values():
        arts.sort(key=lambda a: (a.page or 0, a.sheet or "", a.path))
    return groups


# ─── Prompt building ───────────────────────────────────────────────────


def _read_text_artifact(pp: Path, art: ConvertedArtifact, remaining_bytes: int) -> str:
    """Read a markdown/CSV artifact, return as a labeled text block. Truncated if needed."""
    p = pp / art.path
    try:
        data = p.read_bytes()[:remaining_bytes]
    except OSError:
        return f"[unreadable: {art.path}]\n"
    text = data.decode("utf-8", errors="replace")
    truncated_suffix = "\n[...truncated]\n" if len(data) >= remaining_bytes else ""
    label = art.path
    if art.page:
        label += f" (page {art.page})"
    if art.sheet:
        label += f" (sheet: {art.sheet})"
    return f"\n--- {label} ---\n{text}{truncated_suffix}\n"


def _read_image_artifact(pp: Path, art: ConvertedArtifact) -> dict | None:
    """Return an Anthropic image content block, or None if unreadable."""
    p = pp / art.path
    try:
        data = p.read_bytes()
    except OSError:
        return None
    suffix = p.suffix.lower()
    media_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(suffix, "image/png")
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": media_type,
            "data": base64.b64encode(data).decode("ascii"),
        },
    }


def _is_text_artifact(art: ConvertedArtifact) -> bool:
    return art.format in ("md", "csv")


def _is_image_artifact(art: ConvertedArtifact, pp: Path) -> bool:
    if art.format == "png":
        return True
    if art.format == "passthrough":
        suffix = Path(art.path).suffix.lower()
        return suffix in (".png", ".jpg", ".jpeg", ".gif", ".webp")
    return False


def _build_user_content(
    pp: Path,
    source_path: str,
    artifacts: list[ConvertedArtifact],
) -> list[dict]:
    """Build the Anthropic `content` blocks for one per-source call."""
    concept_yaml = _load_concept_yaml()
    glossary = _load_glossary()

    header = (
        f"# Source under analysis\n\n"
        f"**source_path**: `{source_path}`\n\n"
        f"Below are the artifacts belonging to this source (page-by-page, sheet-by-sheet).\n"
        f"After them, return a single `emit_analysis` tool call with:\n"
        f"1. `insight`: a SourceInsight describing what this document IS.\n"
        f"2. `candidates`: a Candidate for every value you can map to one of the listed concepts.\n"
    )

    concept_block = (
        f"\n# Concept schema (all target variables)\n\n"
        f"```yaml\n{concept_yaml}\n```\n"
    )
    glossary_block = ""
    if glossary:
        glossary_block = (
            f"\n# Glossary — Eva's rules for ambiguous concepts\n\n"
            f"```yaml\n{glossary}\n```\n"
        )

    blocks: list[dict] = [{"type": "text", "text": header + concept_block + glossary_block}]

    # Interleave artifacts in deterministic order, capped
    remaining_text_bytes = _MAX_TEXT_BYTES_PER_SOURCE
    images_added = 0
    text_artifacts = 0
    for art in artifacts[:_MAX_ARTIFACTS_PER_SOURCE]:
        if _is_text_artifact(art):
            if remaining_text_bytes <= 0:
                continue
            text = _read_text_artifact(pp, art, remaining_text_bytes)
            blocks.append({"type": "text", "text": text})
            remaining_text_bytes -= len(text.encode("utf-8"))
            text_artifacts += 1
        elif _is_image_artifact(art, pp):
            if images_added >= _MAX_IMAGES_PER_SOURCE:
                continue
            img_block = _read_image_artifact(pp, art)
            if img_block is None:
                continue
            label = art.path + (f" (page {art.page})" if art.page else "")
            blocks.append({"type": "text", "text": f"\n--- image: {label} ---\n"})
            blocks.append(img_block)
            images_added += 1

    if text_artifacts == 0 and images_added == 0:
        blocks.append({"type": "text", "text": "\n[No readable artifacts for this source.]\n"})

    blocks.append({"type": "text", "text": "\nNow return exactly one `emit_analysis` tool call."})
    return blocks


# ─── Tool schema ───────────────────────────────────────────────────────


def _build_tool_schema() -> dict:
    """JSON schema Anthropic enforces on the tool_use input."""
    return {
        "name": "emit_analysis",
        "description": (
            "Emit the SourceInsight (what this document is) and the list of Candidate "
            "values extracted from it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "insight": {
                    "type": "object",
                    "properties": {
                        "document_type": {"type": "string"},
                        "purpose": {"type": "string"},
                        "author": {"type": "string"},
                        "date_info": {"type": "string"},
                        "version_info": {"type": "string"},
                        "related_sources": {"type": "array", "items": {"type": "string"}},
                        "authority_hints": {"type": "array", "items": {"type": "string"}},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "notes": {"type": "string"},
                    },
                    "required": ["document_type", "purpose", "confidence"],
                },
                "candidates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "concept_id": {"type": "string"},
                            "value": {
                                "description": "string, number, boolean, list, or object",
                            },
                            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                            "quote": {"type": "string"},
                            "artifact_path": {"type": "string"},
                            "reasoning": {"type": "string"},
                        },
                        "required": ["concept_id", "value", "confidence", "quote"],
                    },
                },
            },
            "required": ["insight", "candidates"],
        },
    }


# ─── Error classification ──────────────────────────────────────────────


_SYSTEMIC_ERROR_HINTS = (
    "authentication_error", "permission_error", "invalid_api_key",
    "insufficient_credits", "credit_balance", "overloaded_error",
    "invalid_request_error.*model", "model_not_found",
)


def _classify_error(exc: Exception) -> tuple[str, bool]:
    """Classify an exception. Returns (error_type, is_systemic)."""
    msg = str(exc).lower()
    err_type = type(exc).__name__

    # Anthropic SDK types
    if "authenticationerror" in err_type.lower() or "401" in msg:
        return ("authentication_error", True)
    if "permissiondenied" in err_type.lower() or "403" in msg:
        return ("permission_error", True)
    if "notfound" in err_type.lower() or ("404" in msg and "model" in msg):
        return ("model_not_found", True)
    if any(hint in msg for hint in ("insufficient_credits", "insufficient credit", "credit_balance", "credits are too low")):
        return ("insufficient_credits", True)
    if "402" in msg:
        return ("insufficient_credits", True)

    # Transient
    if "ratelimit" in err_type.lower() or "429" in msg:
        return ("rate_limit", False)
    if "timeout" in err_type.lower() or "timeout" in msg:
        return ("timeout", False)
    if "apistatuserror" in err_type.lower() and "5" in msg[:10]:  # 5xx
        return ("server_error", False)

    return ("unknown_error", False)


# ─── Cache ─────────────────────────────────────────────────────────────


def _cache_key(user_content: list[dict], model: str) -> str:
    """SHA256 over the meaningful inputs — deterministic across runs."""
    h = hashlib.sha256()
    h.update(f"schema:{_SCHEMA_VERSION}|model:{model}".encode())
    for block in user_content:
        if block.get("type") == "text":
            h.update(b"TEXT:")
            h.update(block["text"].encode("utf-8"))
        elif block.get("type") == "image":
            h.update(b"IMAGE:")
            src = block.get("source", {})
            h.update(src.get("data", "").encode("ascii"))
        h.update(b"|")
    return h.hexdigest()


def _cache_path(pp: Path, source_path: str) -> Path:
    from .conversion import _slugify  # same slug convention
    stem = _slugify(Path(source_path).stem) or "unnamed"
    return pp / _ANALYSIS_ROOT / stem / "_cache.json"


def _cache_read(pp: Path, source_path: str, key: str) -> SourceAnalysis | None:
    cache_file = _cache_path(pp, source_path)
    if not cache_file.is_file():
        return None
    try:
        payload = json.loads(cache_file.read_text(encoding="utf-8"))
        if payload.get("key") != key:
            return None
        return SourceAnalysis.model_validate(payload["analysis"])
    except Exception:
        return None


def _cache_write(pp: Path, source_path: str, key: str, analysis: SourceAnalysis) -> None:
    cache_file = _cache_path(pp, source_path)
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {"key": key, "analysis": analysis.model_dump()}
    cache_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


# ─── Per-source analysis ───────────────────────────────────────────────


def _extract_tool_use(response) -> dict | None:
    """Pull the emit_analysis tool input out of an Anthropic message response."""
    for block in getattr(response, "content", []):
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", "") == "emit_analysis":
            return getattr(block, "input", None)
    return None


def _analyze_one_source(
    client,
    pp: Path,
    source_path: str,
    artifacts: list[ConvertedArtifact],
    model: str,
) -> tuple[SourceAnalysis | None, SourceFailure | None, bool, bool]:
    """Analyze one source. Returns (analysis, failure, is_systemic, from_cache).

    At most one of (analysis, failure) is non-None. `is_systemic=True` signals
    the caller to abort the whole project.
    """
    content = _build_user_content(pp, source_path, artifacts)
    tool_schema = _build_tool_schema()
    key = _cache_key(content, model)

    cached = _cache_read(pp, source_path, key)
    if cached is not None:
        return (cached, None, False, True)

    last_error: Exception | None = None
    raw_response: str = ""
    attempts = 0

    for attempt in range(1, _MAX_RETRIES_PER_SOURCE + 1):
        attempts = attempt
        started = time.monotonic()
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=_MAX_TOKENS,
                system=_SYSTEM_PROMPT,
                tools=[tool_schema],
                tool_choice={"type": "tool", "name": "emit_analysis"},
                messages=[{"role": "user", "content": content}],
            )
        except Exception as e:
            err_type, systemic = _classify_error(e)
            last_error = e
            if systemic:
                return (None, SourceFailure(
                    source_path=source_path,
                    error_type=err_type,
                    attempts=attempt,
                    last_error=str(e),
                ), True, False)
            # Transient → backoff and retry
            if attempt < _MAX_RETRIES_PER_SOURCE:
                time.sleep(_BACKOFF_INITIAL_S * (2 ** (attempt - 1)))
                continue
            return (None, SourceFailure(
                source_path=source_path,
                error_type=err_type,
                attempts=attempt,
                last_error=str(e),
            ), False, False)

        tool_input = _extract_tool_use(resp)
        raw_response = json.dumps(tool_input, default=str)[:8000] if tool_input else ""
        if tool_input is None:
            # Model didn't emit a tool call. Rare with tool_choice forced; bail this attempt.
            last_error = RuntimeError("model returned no emit_analysis tool call")
            if attempt < _MAX_RETRIES_PER_SOURCE:
                continue
            return (None, SourceFailure(
                source_path=source_path,
                error_type="empty_response",
                attempts=attempt,
                last_error=str(last_error),
                raw_response=raw_response,
            ), False, False)

        # Validate against our pydantic shapes
        try:
            insight_data = tool_input.get("insight", {})
            insight_data["source_path"] = source_path
            insight = SourceInsight.model_validate(insight_data)

            candidates_raw = tool_input.get("candidates", []) or []
            candidates: list[Candidate] = []
            for c_raw in candidates_raw:
                c_raw["source_path"] = source_path
                c_raw["extractor"] = model
                # source_chain inherited later by caller
                candidates.append(Candidate.model_validate(c_raw))

            usage = getattr(resp, "usage", None)
            input_tokens = getattr(usage, "input_tokens", 0) if usage else 0
            output_tokens = getattr(usage, "output_tokens", 0) if usage else 0

            analysis = SourceAnalysis(
                source_path=source_path,
                insight=insight,
                candidates=candidates,
                attempts=attempt,
                elapsed_ms=int((time.monotonic() - started) * 1000),
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
            _cache_write(pp, source_path, key, analysis)
            return (analysis, None, False, False)
        except ValidationError as ve:
            last_error = ve
            if attempt < _MAX_RETRIES_PER_SOURCE:
                continue
            return (None, SourceFailure(
                source_path=source_path,
                error_type="schema_validation",
                attempts=attempt,
                last_error=str(ve)[:500],
                raw_response=raw_response,
            ), False, False)

    # Should be unreachable
    return (None, SourceFailure(
        source_path=source_path,
        error_type="unknown_error",
        attempts=attempts,
        last_error=str(last_error),
    ), False, False)


# ─── Orchestrator ──────────────────────────────────────────────────────


def _get_client(model: str):
    """Return an Anthropic SDK client. Raises if anthropic is unusable."""
    try:
        import anthropic
    except ImportError as e:
        raise RuntimeError("anthropic SDK not installed") from e
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    return anthropic.Anthropic()


def _build_eva_summary(analysis: ProjectAnalysis, typology_source_count: int) -> list[str]:
    if analysis.systemic_failure:
        return [
            f"⚠ {analysis.systemic_failure.error_type}: {analysis.systemic_failure.message}",
        ]

    n_sources = len(analysis.sources)
    n_candidates = sum(len(s.candidates) for s in analysis.sources)
    n_failures = len(analysis.failures)

    doc_types: dict[str, int] = defaultdict(int)
    for s in analysis.sources:
        doc_types[s.insight.document_type] += 1

    covered_concepts = set(analysis.candidates_by_concept.keys())
    all_concepts = set(_load_concept_ids())
    uncovered = sorted(all_concepts - covered_concepts)

    lines = [
        f"Hem analitzat {n_sources} fonts i n'hem extret {n_candidates} candidats de valor.",
    ]
    top_types = sorted(doc_types.items(), key=lambda kv: -kv[1])[:4]
    if top_types:
        lines.append(
            "• Tipus de document: " +
            ", ".join(f"{n} {t}" for t, n in top_types) + "."
        )
    lines.append(
        f"• {len(covered_concepts)} conceptes tenen almenys un candidat; "
        f"{len(uncovered)} encara no."
    )
    if n_failures:
        lines.append(
            f"⚠ {n_failures} fonts no s'han pogut analitzar — premeu 'Refresh' per tornar-ho a intentar."
        )
    if analysis.cache_hits:
        lines.append(f"• {analysis.cache_hits} fonts servides des de cache (0 $).")
    if analysis.estimated_cost_usd > 0:
        lines.append(f"• Cost estimat d'aquesta anàlisi: ${analysis.estimated_cost_usd:.4f}")
    return lines


# ─── Public API ────────────────────────────────────────────────────────


def analyze_project(
    project_path: Path | str,
    *,
    conversion: ProjectConversion | None = None,
    typology: ProjectTypology | None = None,
    model: str | None = None,
    source_filter: str | None = None,
    client=None,  # for tests: inject a mock
) -> ProjectAnalysis:
    """Analyze every useful source in a project via per-source LLM calls.

    Args:
        project_path: Project folder.
        conversion: Optionally reuse an existing Stage 3 conversion. If None, built fresh.
        typology: Optionally reuse the Stage 2 typology (passed through to conversion).
        model: Override the default model.
        source_filter: Only analyze sources whose path contains this substring (dev).
        client: Optionally inject an Anthropic client (used by tests with mocks).

    Returns:
        ProjectAnalysis with one SourceAnalysis per successful source, plus any failures.
    """
    pp = Path(project_path).resolve()
    if not pp.is_dir():
        raise ValueError(f"Not a directory: {pp}")

    model = model or os.environ.get("G3DT_AI_MODEL", _DEFAULT_MODEL)

    conv = conversion if conversion is not None else convert_project(pp, typology=typology)
    groups = _group_artifacts_by_source(conv)

    # Attach source_chain lookup from conversion
    chain_by_source: dict[str, list[str]] = {}
    for a in conv.artifacts:
        if a.source_path and a.source_path not in chain_by_source:
            chain_by_source[a.source_path] = list(a.source_chain)

    items = sorted(groups.items())
    if source_filter:
        items = [(sp, arts) for sp, arts in items if source_filter.lower() in sp.lower()]

    # Resolve client — fail fast if anthropic itself is unusable
    if client is None:
        try:
            client = _get_client(model)
        except RuntimeError as e:
            msg = str(e)
            err_type = "missing_api_key" if "ANTHROPIC_API_KEY" in msg else "sdk_missing"
            analysis = ProjectAnalysis(
                project_path=str(pp),
                analyzed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                sources=[], failures=[],
                systemic_failure=SystemicFailure(
                    error_type=err_type, message=msg, sources_skipped=len(items),
                ),
                candidates_by_concept={}, eva_summary=[], schema_version=_SCHEMA_VERSION,
            )
            analysis.eva_summary = _build_eva_summary(analysis, len(items))
            return analysis

    sources: list[SourceAnalysis] = []
    fresh_source_paths: set[str] = set()  # paths that paid real LLM cost this run
    failures: list[SourceFailure] = []
    systemic: SystemicFailure | None = None
    cache_hits = 0
    consecutive_non_systemic_failures = 0

    for source_path, arts in items:
        analysis, failure, is_systemic, from_cache = _analyze_one_source(
            client, pp, source_path, arts, model,
        )

        if is_systemic and failure is not None:
            remaining = len(items) - (len(sources) + len(failures))
            msg = (
                f"{failure.error_type} from {failure.source_path}: {failure.last_error}. "
                f"Aborted remaining {remaining} sources."
            )
            action_hint = ""
            if failure.error_type == "insufficient_credits":
                action_hint = " Action: add Anthropic credits, or set G3DT_AI_MODEL_VISION=gpt-4.1-mini for image-only sources."
            elif failure.error_type == "authentication_error":
                action_hint = " Action: check ANTHROPIC_API_KEY."
            elif failure.error_type == "model_not_found":
                action_hint = f" Action: unset G3DT_AI_MODEL or use a valid model id (tried '{model}')."
            systemic = SystemicFailure(
                error_type=failure.error_type,
                message=msg + action_hint,
                sources_skipped=remaining + 1,  # +1 for the current source
            )
            break

        if analysis is not None:
            # Propagate source_chain from conversion metadata
            chain = chain_by_source.get(source_path, [])
            if chain:
                for c in analysis.candidates:
                    if not c.source_chain:
                        c.source_chain = list(chain)
            # Attach artifact_path when missing
            for c in analysis.candidates:
                if not c.artifact_path and arts:
                    c.artifact_path = arts[0].path
            sources.append(analysis)
            if from_cache:
                cache_hits += 1
            else:
                fresh_source_paths.add(source_path)
            consecutive_non_systemic_failures = 0
        elif failure is not None:
            failures.append(failure)
            consecutive_non_systemic_failures += 1
            if consecutive_non_systemic_failures >= _CIRCUIT_BREAKER_THRESHOLD:
                remaining = len(items) - (len(sources) + len(failures))
                systemic = SystemicFailure(
                    error_type="circuit_breaker",
                    message=(
                        f"{_CIRCUIT_BREAKER_THRESHOLD} consecutive non-systemic failures; "
                        f"aborted remaining {remaining} sources. Last error: {failure.last_error}"
                    ),
                    sources_skipped=remaining,
                )
                break

    # Aggregate. Only count tokens from freshly-called sources — cache hits cost 0.
    candidates_by_concept: dict[str, list[str]] = defaultdict(list)
    total_input = 0
    total_output = 0
    for s in sources:
        if s.source_path in fresh_source_paths:
            total_input += s.input_tokens
            total_output += s.output_tokens
        for c in s.candidates:
            if c.source_path not in candidates_by_concept[c.concept_id]:
                candidates_by_concept[c.concept_id].append(c.source_path)

    price = _PRICING.get(model, {"input": 0.0, "output": 0.0})
    estimated_cost = (total_input * price["input"] + total_output * price["output"]) / 1_000_000.0

    analysis = ProjectAnalysis(
        project_path=str(pp),
        analyzed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        sources=sources,
        failures=failures,
        systemic_failure=systemic,
        candidates_by_concept=dict(candidates_by_concept),
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        estimated_cost_usd=round(estimated_cost, 6),
        cache_hits=cache_hits,
        schema_version=_SCHEMA_VERSION,
    )
    analysis.eva_summary = _build_eva_summary(analysis, len(items))
    return analysis


def save_analysis(analysis: ProjectAnalysis, project_path: Path | str) -> Path:
    pp = Path(project_path).resolve()
    out_dir = pp / "validation"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "ai_analysis.json"
    out_path.write_text(analysis.model_dump_json(indent=2), encoding="utf-8")
    return out_path


def load_analysis(project_path: Path | str) -> ProjectAnalysis | None:
    pp = Path(project_path).resolve()
    p = pp / "validation" / "ai_analysis.json"
    if not p.is_file():
        return None
    return ProjectAnalysis.model_validate_json(p.read_text(encoding="utf-8"))
