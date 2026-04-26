# Investigation — Engineering-judgment delegation to legacy calculators

**Data:** 2026-04-26
**Branca:** `experiment/ai-pipeline`
**Trigger:** Several "stuck" concepts where the AI pipeline cannot match Eva's value because the value is the result of professional methodology, not a direct extraction. The legacy deterministic pipeline already encodes that methodology.

---

## Executive summary

The AI pipeline's Stage 4 LLM is being asked to rediscover values that are *computed* outputs of Eva's methodology — `qa_value` (Terzaghi-Peck + caps), `geomech_E` (Schmertmann correlation), `geomech_phi` (Crespo lookup), `settlement_cm` (Schmertmann integration), `k30_value` (E/75 or E/60). The documents only carry raw signals (Nb, soil type, geometry). The methodology that converts raw signals into final values lives in `automation/terzaghi_calculator.py`, `automation/cte_geomech.py`, and `automation/bicapa.py` — production-grade code hardened over 7 reference projects.

The recommendation is to add a **"Stage 4.5 — Engineering Calculator Pass"** between Stage 4 (LLM extraction) and Stage 5 (authority ranking). For each concept marked `delegate_to_calculator: true` in `report_variables.yaml`, the calculator pass reads Stage 4's raw outputs (Nb, geotech_rows, foundation geometry from user_data), invokes the legacy function, and emits a synthetic `Candidate` with `source_path="calculator:<name>"` and `confidence=1.0`. Stage 5 then ranks this synthetic candidate alongside the LLM-extracted ones; the existing principles file already mandates Eva's methodology over raw extractions, so it naturally rises to top-1.

Phase 1 MVP scope: **`qa_value` + `settlement_cm` only**, behind an env-var feature flag (`G3DT_ENABLE_CALCULATOR_DELEGATION`), default OFF for safe opt-in on the next live run.

---

## 1. Concept-by-concept catalog

| Concept | Legacy function | Inputs needed | Available from Stage 4? | Recommended option |
|---|---|---|---|---|
| `qa_value` | `terzaghi_calculator.calculate_qa(B, Df, Nb, cohesion, phi, gamma, soil_type)` | bearing-layer Nb (from DPSH), foundation geometry B/Df (user_data), bearing-layer phi/c/gamma (geotech_rows[-1]) | YES — Stage 4 emits dpsh_tests + geotech_rows | **A — delegate** |
| `settlement_cm` | `terzaghi_calculator.schmertmann_settlement(B, qa, Es, ...)` | foundation B + applied pressure + Es | YES — same as qa_value | **A — delegate** |
| `geomech_E` (bearing) | `cte_geomech.nspt_to_E_kg_cm2(Nb)` or D.23 lookup | Nb, soil_type | YES — flatten now reads bearing row | **A — delegate** (alongside qa flow) |
| `geomech_phi` | `cte_geomech.nspt_to_phi(Nb, soil_type)` (Schmertmann factor n) | Nb, soil_type, grain_size hint | YES | **A — delegate** |
| `geomech_cohesion` | `cte_geomech.nspt_to_cohesion(qu)` (Hunt's table) | Nb or qu | YES | **A — delegate** |
| `geomech_gamma` | `cte_geomech.gamma_for_soil_type(soil_type)` (CTE D.27) | soil_type only | YES — table lookup | **A — delegate** (trivial) |
| `Es_settlement` | `terzaghi_calculator._es_for_geometry(Nb, geometry)` (2.5×Nb square / 3.5×Nb strip) | Nb, geometry | YES | **A — delegate** |
| `k30_value` | `cte_geomech.k30_from_E(E, soil_type)` (E/75 granular, E/60 rock) | computed E, soil_type | YES — derived from above | **A — delegate** |

All 8 concepts are good delegation candidates. The MVP picks the two that move the most ground (qa_value + settlement_cm); the rest follow once Phase 1 is validated.

---

## 2. Integration shape (Option A — Stage 4.5 calculator pass)

```
Stage 4: LLM extraction
  └─ ai_analysis.json  (sources × candidates)
       │
       ▼
Stage 4.5: Engineering Calculator Pass (NEW)
  ├─ Read ai_analysis.json + user_data.json (foundation geometry)
  ├─ For each concept with delegate_to_calculator=true:
  │     • Resolve calculator inputs (Nb from dpsh_tests, soil_type
  │       from geotech_rows[-1], B/Df from user_data)
  │     • Call legacy function (terzaghi_calculator.calculate_qa, etc.)
  │     • Emit synthetic Candidate with source_path="calculator:<name>",
  │       confidence=1.0, extractor="legacy_calculator",
  │       reasoning="Computed via <fn>(<inputs>) per Eva's methodology"
  └─ Append candidates to ai_analysis.json under a synthetic
     "calculator" SourceAnalysis (or write a sibling
     ai_calculations.json — design choice)
       │
       ▼
Stage 5: Authority ranking
  └─ Pass A sees the calculator candidate as one source among
     many. Authority principles already say
     "calculator output per Eva's methodology > LLM extraction" so
     it ranks top-1 naturally.
```

**Variant**: instead of writing into `ai_analysis.json`, emit a separate `ai_calculations.json` and have Stage 5 read both manifests. Cleaner separation; minor plumbing cost. Recommend the separate manifest — keeps Stage 4 immutable so re-runs of Stage 4 don't compete with calculator outputs.

---

## 3. Risk + rollback strategy

**Feature flag**: `G3DT_ENABLE_CALCULATOR_DELEGATION` env var.
- Default `false` for the first MVP run — opt-in only.
- After Alcoletge validates the calculator output matches Eva's value, flip default to `true`.
- Rollback = unset the env var; pipeline behaves as today.

**Failure modes**:
- **Missing inputs** (calculator can't run because user_data lacks foundation geometry): emit no synthetic candidate, log a warning. Stage 5 falls back to LLM-only candidates.
- **Calculator crash** (numeric overflow, divide-by-zero on edge data): catch the exception, log, emit no candidate. Don't abort Stage 4.5 for other concepts.
- **Calculator output disagrees with all LLM candidates**: this is exactly the case the system was built for; Stage 5 ranks the calculator top-1 per principles, Eva sees it in the wizard with the rationale "computed via <fn>".

**Determinism**: legacy calculators are deterministic; same inputs → same output. Calculator candidates have `confidence=1.0` and stable provenance. Reduces overall pipeline variance compared to the all-LLM path.

**Cost savings**: modest. Stage 4 prompt size could shrink slightly if we skip extracting these concepts from documents (~300 tokens/source × 72 sources × $3/1M = ~$0.06/project). Not the main motivation; correctness is.

---

## 4. Predicted Alcoletge regression run

Tracing through the legacy code with Alcoletge's actual data:

**Bearing layer selection** (`bicapa.py:select_bearing_layer`):
- Layer 1: "Sorres argiloses de rebliment" — Nb=5-0 (very weak, top 0–1.4m). Identified as soft top, SKIPPED per Eva's "skip-soft-top" rule.
- Layer 2: "Lutites i sorrenques alterades" — Nb=R (refusal, depth ≥1.4m). Selected as bearing.

**Inputs to `calculate_qa`**:
- Nb = R (refusal) → treated as the configured "refusal Nb" constant (typically 50+).
- soil_type = "rock" (lutites with cohesion ≥ 0.5) → triggers rock branch.
- cohesion = 1.0 kg/cm² (from geotech_rows[-1] now that bearing-stratum flatten lands).
- phi = 30°, gamma = 2.0.
- B (foundation width) and Df (foundation depth) from user_data.

**Expected calculation** (per `terzaghi_calculator.py` lines 408–425):
- `qa_terzaghi = Nb / 12` with width + depth corrections → likely ~3.5 on Alcoletge geometry.
- `qa_cap` for rock = 3.0 (per current code) OR 4.0–4.5 (per MEMORY: "Roca (bretxes/lutites): Qa cap 4.0–4.5") — **DISCREPANCY**.
- `qa_governs = "terzaghi"` if terzaghi < cap, else `"cap"`.
- Eva's actual value: 3.50.

**The discrepancy**: the current `terzaghi_calculator.py` may have `QA_CAP_ROCK=3.0`, but Eva's documented values show rock caps of 4.0–4.5. Either:
- (a) The calculator's cap is too conservative — fix the constant, both legacy and AI pipeline benefit.
- (b) Eva applies a different cap rule (e.g., `cohesion >= 0.5 AND Nb_refusal → cap 4.5`) we haven't fully captured.
- (c) For Alcoletge specifically, `qa_terzaghi ≈ 3.50` and the cap doesn't fire — the calculator output IS 3.50. We need to actually run it to confirm.

**Gate**: Phase 1 MVP must run the calculator on Alcoletge as part of validation. If it produces 3.50, ship. If it produces 3.0 and Eva says 3.50, file an Eva-clarification question (the gap is in the legacy code, not in delegation strategy).

---

## 5. Recommended implementation order

**Phase 1 — qa_value MVP** (1 commit, ~150 lines):
- Add `automation/ai_pipeline/calculator_pass.py` with `run_calculator_pass(project_path, *, force=False)`.
- Add `delegate_to_calculator: true` to `qa_value` and `settlement_cm` in `report_variables.yaml`.
- New `ai_calculations.json` manifest format (one synthetic SourceAnalysis with concept candidates).
- Update Stage 5 trace + ranking to also load `ai_calculations.json` if present.
- Env var feature flag: `G3DT_ENABLE_CALCULATOR_DELEGATION` (default `false`).
- Tests: synthetic project with mock DPSH data, assert calculator pass emits expected qa_value candidate; assert Stage 5 ranks it top-1.

**Phase 2 — geomech_* delegation** (1 commit, ~80 lines):
- Add `geomech_E`, `geomech_phi`, `geomech_cohesion`, `geomech_gamma` to delegated set.
- These reuse `calculate_qa`'s same input pipeline, so plumbing is trivial.

**Phase 3 — Es_settlement, k30_value** (1 commit, ~50 lines):
- Add the two derived concepts. Their inputs are calculator outputs of Phase 2, so no new inputs needed.

**Phase 4 — flip the flag default** (1 commit, ~5 lines):
- After Alcoletge run shows calculator path matches Eva's values across all 7 reference projects, flip default to `true`.

---

## 6. Open questions for the user / Eva

1. **`qa_cap_rock` mismatch**: legacy code has `QA_CAP_ROCK=3.0`, MEMORY says 4.0–4.5. Which is correct? (Affects Alcoletge prediction.) Likely an Eva-clarify question — *"For lutites alterades + Nb=R, what's the qa cap you apply: 3.0 or 4.0?"*

2. **Refusal handling**: when DPSH hits refusal at depth N, what `Nb` value does Eva use in calc? Some projects show `R` (treat as ≥50?), others show `47-R` (use 47). Need a canonical rule.

3. **MVP scope**: should Phase 1 include only `qa_value` (1 concept, simplest), or `qa_value` + `settlement_cm` (2 concepts, both share the same input pipeline)? Marginal complexity for second concept is small; recommend including both.

4. **Manifest design**: synthesize calculator candidates into `ai_analysis.json` (under a virtual SourceAnalysis), or write `ai_calculations.json` as a sibling manifest? Recommend sibling — cleaner separation, doesn't compete with Stage 4 caching.

---

## 7. Conclusions

1. **Legacy calculators are production-grade, deterministic, and battle-tested across 7 projects.** They encode Eva's methodology precisely. The AI pipeline's LLM-only approach can't match this without rebuilding the same methodology in prompts (and rediscovering the same edge cases).

2. **All inputs the calculators need are already produced by Stage 4.** Delegation is a plumbing exercise, not a data-discovery one. No new extractions required.

3. **Stage 4.5 calculator pass is the lowest-risk integration shape.** Thin optional layer, feature flag default OFF, sibling manifest, doesn't touch existing pipeline behavior unless opted in.

4. **One known gap to resolve**: the `qa_cap_rock` constant value (3.0 in code vs 4.0–4.5 in Eva's notes). MVP validation surfaces this; we either fix the constant or document the more nuanced rule before flipping the feature flag default.

5. **GO with Phase 1 MVP** — `qa_value` + `settlement_cm`, env-var feature flag default OFF, first run on Alcoletge to validate calculator outputs match Eva's signed values.

---

*Investigation report — 2026-04-26.*
