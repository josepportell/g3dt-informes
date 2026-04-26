"""Stage 4.5 — Engineering Calculator Pass.

Runs Eva's deterministic calculators (terzaghi_calculator, etc.) against
Stage 4 outputs (`ai_analysis.json`) plus foundation geometry from
`user_data.json`, and emits one synthetic `SourceAnalysis` containing
`Candidate` entries for each delegated concept.

The output is written to `validation/ai_calculations.json` (a sibling of
`ai_analysis.json`, NOT a replacement). Stage 5 reads both manifests when
the feature flag `G3DT_ENABLE_CALCULATOR_DELEGATION=true`.

Design doc: docs/INVESTIGACIO-ENGINEERING-DELEGATION.md (§2 integration shape).

Phase 1 scope: `qa_value` + `settlement_cm` only. Phase 2 will add geomech_*.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import yaml

from .analysis import (
    Candidate,
    ProjectAnalysis,
    SourceAnalysis,
    SourceInsight,
    load_analysis,
)

logger = logging.getLogger(__name__)


# ─── Configuration ─────────────────────────────────────────────────────

_CALCULATIONS_MANIFEST = Path("validation") / "ai_calculations.json"

_CALCULATOR_SOURCE_PATH = "calculator:legacy_geotech"

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_REPORT_VARIABLES_PATH = _PROJECT_ROOT / "schemas" / "concepts" / "report_variables.yaml"

# Defaults if user_data is missing foundation geometry.
# Mirror report_generator defaults (B=1.0 m, Df=0.8 m).
_DEFAULT_B_M = 1.0
_DEFAULT_DF_M = 0.8

# DPSH energy-correction factor (Eva confirmed): Nb = N20 / 0.83.
# Ref: Dapena, Lacasa & García (2000).
_NB_FACTOR = 0.83


# ─── Schema introspection ──────────────────────────────────────────────


def _load_delegated_concepts() -> list[str]:
    """Return the list of concept_ids with `delegate_to_calculator: true`.

    Reads `schemas/concepts/report_variables.yaml`. Phase 1 expects exactly
    `qa_value` and `settlement_cm`.
    """
    if not _REPORT_VARIABLES_PATH.is_file():
        raise FileNotFoundError(
            f"Concept definitions YAML not found at {_REPORT_VARIABLES_PATH}"
        )
    data = yaml.safe_load(_REPORT_VARIABLES_PATH.read_text(encoding="utf-8"))
    concepts = (data or {}).get("concepts") or {}
    out: list[str] = []
    for cid, meta in concepts.items():
        if isinstance(meta, dict) and meta.get("delegate_to_calculator") is True:
            out.append(cid)
    return out


# ─── Input resolution ──────────────────────────────────────────────────


def _pick_top_candidate_value(
    analysis: ProjectAnalysis, concept_id: str
) -> Any | None:
    """Return the highest-confidence candidate value for a concept (deterministic).

    Sort key: (confidence DESC, source_path ASC, candidate-index ASC). The
    secondary keys ensure a stable, replayable winner when two sources tie on
    confidence — useful both for reproducibility and for tests.
    """
    matches: list[tuple[float, str, int, Any]] = []
    for source in analysis.sources:
        for idx, cand in enumerate(source.candidates):
            if cand.concept_id == concept_id:
                matches.append(
                    (cand.confidence, source.source_path, idx, cand.value)
                )
    if not matches:
        return None
    # Negate confidence so we sort descending on it while keeping ascending on
    # the tie-break keys.
    matches.sort(key=lambda t: (-t[0], t[1], t[2]))
    return matches[0][3]


# DPSH "stroke string" — Eva's transcribed blow counts per 20 cm,
# e.g. "5/9/11/33". The LAST 20-cm value is the canonical N20 used downstream.
_DPSH_STROKE_RE = re.compile(r"\s*\d+(?:\s*/\s*\d+)+\s*")
# General numeric extractor — accepts signed values, decimals (comma or dot)
# and scientific notation. Used for "30°", "2.0 g/cm³", "1.5e2", "-3,2", …
_NUMERIC_TOKEN_RE = re.compile(r"[+-]?\d+(?:[.,]\d+)?(?:[eE][+-]?\d+)?")


def _coerce_float(value: Any) -> float | None:
    """Best-effort numeric coercion. Returns None on failure."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        # DPSH stroke string ("5/9/11/33"): take the LAST 20cm count as N20.
        if "/" in value and _DPSH_STROKE_RE.fullmatch(value):
            try:
                parsed = float(value.rsplit("/", 1)[-1].strip())
                logger.debug(
                    "_coerce_float: DPSH stroke string %r → N20=%s", value, parsed
                )
                return parsed
            except ValueError:
                return None
        m = _NUMERIC_TOKEN_RE.search(value)
        if m:
            try:
                return float(m.group(0).replace(",", "."))
            except ValueError:
                return None
    return None


def _resolve_bearing_inputs(
    analysis: ProjectAnalysis, user_data: dict
) -> dict:
    """Gather calculator inputs from Stage 4 candidates + user_data.

    Returns a dict with keys: phi, cohesion, gamma, nspt_n20, B, Df, soil_type.
    Any unresolved value is None.

    Phase 2 limitation
    ------------------
    This Phase 1 resolver is intentionally NAIVE about the bearing stratum:
    it picks the highest-confidence candidate for ``geomech_phi`` /
    ``geomech_cohesion`` / ``geomech_gamma`` / ``spt_n30`` regardless of which
    geological level the candidate describes. The legacy code path in
    ``automation/report_data.py`` and ``automation/bicapa.py`` (specifically
    ``_select_bearing_layer_idx`` + ``bicapa.select_bearing_layer``) does the
    real per-layer pick, weighing depth, foundation embedment ``Df``, and
    bicapa rules. Phase 2 will move that logic here so the calculator pass
    consumes the same bearing layer Eva would.
    """
    # Phase 2: per-layer bearing pick via _select_bearing_layer_idx +
    # bicapa.select_bearing_layer
    phi = _coerce_float(_pick_top_candidate_value(analysis, "geomech_phi"))
    cohesion = _coerce_float(_pick_top_candidate_value(analysis, "geomech_cohesion"))
    gamma = _coerce_float(_pick_top_candidate_value(analysis, "geomech_gamma"))
    # spt_n30 is the closest concept to bearing-stratum N20 in current schema.
    # Stage 4 candidates may be a single number or a string like "30" or "5/9/11/33".
    nspt_n20 = _coerce_float(_pick_top_candidate_value(analysis, "spt_n30"))

    # Foundation geometry from user_data. Match report_generator's keys.
    # Use explicit None-check (not `or`) so an explicit 0.0 is preserved and
    # only validated/rejected by the calculator itself.
    _B = _coerce_float(user_data.get("footing_width_m"))
    B = _B if _B is not None else _DEFAULT_B_M
    _Df = _coerce_float(user_data.get("foundation_depth_m"))
    Df = _Df if _Df is not None else _DEFAULT_DF_M

    # Es override from wizard (if Eva manually set it)
    Es_override = _coerce_float(user_data.get("Es_settlement"))

    # soil_type: prefer user_data soil_types[-1] (bearing stratum).
    soil_type: str | None = None
    soil_types = user_data.get("soil_types") or []
    if isinstance(soil_types, list) and soil_types:
        soil_type = str(soil_types[-1])

    return {
        "phi": phi,
        "cohesion": cohesion,
        "gamma": gamma,
        "nspt_n20": nspt_n20,
        "B": B,
        "Df": Df,
        "Es_override": Es_override,
        "soil_type": soil_type,
    }


# ─── Calculator dispatch ───────────────────────────────────────────────


def _run_terzaghi(inputs: dict) -> Any:
    """Build a TerzaghiCalculator and call calculate_qa, returning the result.

    Caller decides which fields to consume (Qa, settlement_cm, …).
    """
    from automation.terzaghi_calculator import (  # local import — keep module import-light
        FootingShape,
        TerzaghiCalculator,
    )

    phi = inputs.get("phi")
    cohesion = inputs.get("cohesion") or 0.0
    gamma = inputs.get("gamma") or 2.0
    if phi is None:
        raise ValueError("phi missing — cannot run Terzaghi calculator")

    nspt_n20 = inputs.get("nspt_n20")
    nb_for_tp = nspt_n20 / _NB_FACTOR if nspt_n20 is not None else None

    is_granular = cohesion < 0.5
    soil_type = inputs.get("soil_type") or (
        "granular" if is_granular else "cohesive"
    )

    calc = TerzaghiCalculator(phi=phi, cohesion=cohesion, gamma=gamma)
    result = calc.calculate_qa(
        B=inputs["B"],
        Df=inputs["Df"],
        shape=FootingShape.SQUARE,
        nspt=nb_for_tp,
        is_granular=is_granular,
        soil_type=soil_type,
        Es_override=inputs.get("Es_override"),
    )
    return result


def _format_input_summary(inputs: dict, fields: list[str]) -> str:
    parts = []
    for k in fields:
        v = inputs.get(k)
        if v is None:
            continue
        if isinstance(v, float):
            parts.append(f"{k}={v:.3g}")
        else:
            parts.append(f"{k}={v}")
    return ", ".join(parts)


@dataclass(frozen=True)
class _CalcOutputs:
    """One Terzaghi calculator run shared across all delegated concepts.

    Holds the calculator result plus a pre-formatted input summary so each
    extractor can produce a per-concept reasoning string without re-running
    the calculator. See ``_terzaghi_outputs`` for the producer side.
    """

    result: Any
    summary: str


def _terzaghi_outputs(inputs: dict) -> _CalcOutputs:
    """Run the Terzaghi calculator ONCE and return shared outputs.

    Raises whatever ``_run_terzaghi`` raises (e.g. ``ValueError`` when phi is
    missing). Callers in ``run_calculator_pass`` are expected to skip the
    entire Terzaghi-backed concept group on failure.
    """
    return _CalcOutputs(
        result=_run_terzaghi(inputs),
        summary=_format_input_summary(
            inputs, ["phi", "cohesion", "gamma", "nspt_n20", "B", "Df", "soil_type"]
        ),
    )


def _extract_qa(out: _CalcOutputs) -> tuple[Any, str]:
    """Pull qa_value (in kg/cm²) out of a shared Terzaghi run."""
    return out.result.Qa, (
        f"Computed via terzaghi_calculator.calculate_qa({out.summary}) "
        f"per Eva's methodology (Terzaghi-Peck + cap)"
    )


def _extract_settlement(out: _CalcOutputs) -> tuple[Any, str]:
    """Pull settlement_cm out of a shared Terzaghi run; raises when missing."""
    if out.result.settlement_cm is None:
        raise ValueError("settlement_cm not computed (calculator returned None)")
    return out.result.settlement_cm, (
        f"Computed via terzaghi_calculator.schmertmann_settlement({out.summary}) "
        f"per Eva's methodology (Es=2.5×Nb square / 3.5×Nb strip)"
    )


# Concept → extractor dispatch for the Terzaghi calculator group. All entries
# share a single ``_terzaghi_outputs`` invocation; see ``run_calculator_pass``.
# When adding a new Terzaghi-backed concept, register it here AND mark
# ``delegate_to_calculator: true`` in ``schemas/concepts/report_variables.yaml``.
# The YAML↔dispatch coverage test guards against drift.
_TERZAGHI_EXTRACTORS: dict[str, Callable[[_CalcOutputs], tuple[Any, str]]] = {
    "qa_value": _extract_qa,
    "settlement_cm": _extract_settlement,
}


# ─── Public API ────────────────────────────────────────────────────────


def run_calculator_pass(
    project_path: Path | str,
    *,
    analysis: ProjectAnalysis | None = None,
    user_data: dict | None = None,
    force: bool = False,
) -> ProjectAnalysis:
    """Run delegated-concept calculators using Stage 4 outputs as inputs.

    Args:
        project_path: project directory.
        analysis: optionally pre-loaded ProjectAnalysis (else load from
            validation/ai_analysis.json). If absent on disk, raise.
        user_data: optionally pre-loaded user_data (else load from
            user_data.json at project root). If absent, defaults are used.
        force: bypass cache (rebuild even if ai_calculations.json exists).

    Returns:
        ProjectAnalysis containing one synthetic "calculator" source with
        Candidate entries for each successfully-computed delegated concept.
    """
    pp = Path(project_path).resolve()
    if not pp.is_dir():
        raise ValueError(f"Not a directory: {pp}")

    # Cache short-circuit.
    if not force:
        cached = load_calculations(pp)
        if cached is not None:
            return cached

    # 1. Load Stage 4 analysis (mandatory).
    if analysis is None:
        analysis = load_analysis(pp)
        if analysis is None:
            raise ValueError(
                f"No ai_analysis.json at {pp}; run Stage 4 first"
            )

    # 2. Load user_data (optional — defaults when missing).
    if user_data is None:
        ud_path = pp / "user_data.json"
        if ud_path.is_file():
            try:
                user_data = json.loads(ud_path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning(
                    "Failed to parse user_data.json at %s: %s — using defaults",
                    ud_path, exc,
                )
                user_data = {}
        else:
            logger.warning(
                "No user_data.json at %s — calculator pass will use default "
                "foundation geometry (B=%s m, Df=%s m).",
                pp, _DEFAULT_B_M, _DEFAULT_DF_M,
            )
            user_data = {}

    # 3. Resolve inputs (single bundle reused across all delegated concepts).
    inputs = _resolve_bearing_inputs(analysis, user_data)

    # 4. Determine which concepts to delegate (from YAML schema).
    delegated = _load_delegated_concepts()

    candidates: list[Candidate] = []
    t0 = time.perf_counter()

    # 5a. Run the Terzaghi calculator ONCE for the whole concept group.
    # On failure (e.g. phi missing), every Terzaghi-backed concept is skipped.
    tz_out: _CalcOutputs | None
    try:
        tz_out = _terzaghi_outputs(inputs)
    except Exception as exc:
        logger.warning(
            "Terzaghi calculator failed (%s) — skipping all Terzaghi-backed "
            "concepts: %s", exc, sorted(_TERZAGHI_EXTRACTORS.keys()),
        )
        tz_out = None

    # 5b. Iterate delegated concepts and dispatch to the right extractor group.
    for cid in delegated:
        if cid in _TERZAGHI_EXTRACTORS:
            if tz_out is None:
                continue
            extractor = _TERZAGHI_EXTRACTORS[cid]
            try:
                value, reasoning = extractor(tz_out)
            except Exception as exc:
                logger.warning(
                    "Calculator extractor failed for concept %r: %s — emitting no candidate",
                    cid, exc,
                )
                continue
        else:
            logger.warning(
                "Concept %r marked delegate_to_calculator but has no dispatch "
                "entry in calculator_pass — skipping.", cid
            )
            continue
        candidates.append(
            Candidate(
                concept_id=cid,
                value=value,
                confidence=1.0,
                quote="",
                source_path=_CALCULATOR_SOURCE_PATH,
                source_chain=[],
                extractor="legacy_calculator",
                reasoning=reasoning,
            )
        )
    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    insight = SourceInsight(
        source_path=_CALCULATOR_SOURCE_PATH,
        document_type="deterministic_calculator",
        purpose=(
            "Eva's methodology codified in automation/terzaghi_calculator.py "
            "(plus cte_geomech.py, bicapa.py for Phase 2+). Outputs are "
            "deterministic given Stage 4 inputs."
        ),
        author="Eva (via legacy code)",
        date_info="",
        version_info="",
        related_sources=[],
        authority_hints=[
            "computed via legacy deterministic calculators per Eva's methodology",
        ],
        confidence=1.0,
        notes="",
    )
    src = SourceAnalysis(
        source_path=_CALCULATOR_SOURCE_PATH,
        insight=insight,
        candidates=candidates,
        attempts=1,
        elapsed_ms=elapsed_ms,
        model="legacy_calculator",
        input_tokens=0,
        output_tokens=0,
    )

    return ProjectAnalysis(
        project_path=str(pp),
        analyzed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        sources=[src],
        failures=[],
        systemic_failure=None,
        candidates_by_concept={
            c.concept_id: [_CALCULATOR_SOURCE_PATH] for c in candidates
        },
        eva_summary=[
            f"Pas calculadora ha emès {len(candidates)} candidats sintètics "
            f"(de {len(delegated)} conceptes delegats)."
        ],
        total_input_tokens=0,
        total_output_tokens=0,
        estimated_cost_usd=0.0,
        cache_hits=0,
    )


# ─── Save / load ───────────────────────────────────────────────────────


def save_calculations(
    analysis: ProjectAnalysis, project_path: Path | str
) -> Path:
    if not any(s.source_path == _CALCULATOR_SOURCE_PATH for s in analysis.sources):
        raise ValueError(
            "save_calculations expects an analysis produced by run_calculator_pass "
            f"(must contain a synthetic {_CALCULATOR_SOURCE_PATH!r} source). "
            "Refusing to write ai_calculations.json — would overwrite Stage 4.5 manifest."
        )
    pp = Path(project_path).resolve()
    out = pp / _CALCULATIONS_MANIFEST
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(analysis.model_dump_json(indent=2), encoding="utf-8")
    return out


def load_calculations(project_path: Path | str) -> ProjectAnalysis | None:
    pp = Path(project_path).resolve()
    p = pp / _CALCULATIONS_MANIFEST
    if not p.is_file():
        return None
    try:
        return ProjectAnalysis.model_validate_json(p.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to parse %s: %s — ignoring", p, exc)
        return None
