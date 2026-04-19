# G3DT - Automatització d'Informes Geotècnics — Status
Last updated: 2026-04-18

## ✅ Diagnostic v1.2 sweep — 65.6% precision (+4.9pp vs Apr 11 baseline)

Full 7-project sweep with new judge (Sonnet 4.6 + geotechnical-engineer prompt) via Anthropic direct. **Headline jumped from 60.7% → 65.6%** despite the new judge being significantly stricter than Apr 11's lenient version. Every project gained:

| Project | Apr 11 | 2026-04-18 | Δ |
|---|---:|---:|---:|
| Bell-Lloc | 65.1% | **79.1%** | +14pp |
| Castellar | ~65% | **80.6%** | +15.6pp |
| Rubí | 51% | **67.6%** | +16.6pp |
| Linyola | 67% | 68.4% | +1.4pp |
| Alcoletge | 43% | 52.4% | +9.4pp |
| Vilanova | 41% | 52.0% | +11pp |
| Anciles | 33% | 42.3% | +9.3pp |

Component scorecard: `llm_synthesis` 0% → 75% (+75pp), `cadastre` 7% → 50% (+43pp), `constant` 45% → 95% (+50pp), `lab_extractor` 78% → 89%, `fileminer_regex` 50% → 75%, `vision_planol` 40% → 52%, `vision_sondeig` 47% → 67%, `vision_projecte` (new) 75%. Cost: $0.146 OpenAI vision (judge cost not tracked yet).

## Current State

**Accuracy 65.6% (+23.9pp accumulated). 396 tests passing.** Diagnostic v1.2 ships with: judge ON by default + Sonnet 4.6 substance-not-wording prompt, per-vision-type backend (Claude for sondeig/dpsh, OpenAI for planol/projecte), schema 1.2 with `cost_summary`/`concept_scout`/`missing_summary`/`global_ne_trace`/`judge_model` in metadata, plus `--easy-wins`/`--leverage`/`--ne-trace` diagnostic flags.

## Saved artifacts (2026-04-18)

| Artifact | Path |
|---|---|
| **CROSS snapshot v1.2** | `docs/diagnostics/2026-04-18_CROSS_d4f898.json` (incl. `global_ne_trace`) |
| **Pre-ne-trace CROSS** | `docs/diagnostics/2026-04-18_CROSS_f0bb14.json` |
| **Per-project snapshots** | `docs/diagnostics/2026-04-18_*_*.json` (1 per project, latest mtime is canonical) |
| **Apr 11 baseline** | `docs/diagnostics/2026-04-11_CROSS_dbf211.json` (judge era; for diff comparison) |
| **LLM judge cache** | `docs/benchmarks/_llm_judge_cache.json` (rebuilt today with new prompt; reused on future runs) |
| **Old judge cache backup** | `docs/benchmarks/_llm_judge_cache.json.bak-2026-04-18` (pre-rewrite, for forensics) |
| **Plan file** | `~/.claude/plans/plan-it-first-diagnostic-logical-breeze.md` |
| **Today's session log** | `.claude/sessions/2026-04-18-session.md` (TODO) |

## NOT_EXTRACTED trace (39 occurrences, 18 vars) — categorized by missing_reason

| Reason | Vars | Occurrences | Highest-leverage fix |
|---|---:|---:|---|
| **`schema_missing`** | 9 | 18 (46%) | Add 9 concepts to `schemas/concepts/report_variables.yaml` (sulfate_*, spt_*, access_street) |
| **`no_extractor`** | 1 | 4 | Add planol_vision/groq_llm source for `building_structure_desc` |
| **`no_source_file`** | 3 | 11 | `num_floors`/`superficie_*` lack architect_plan in 3-4 projects (likely buried in email attachments — see below) |
| **`file_had_no_match`** | 5 | 6 | Tighten extractors: Rubí architect, Vilanova/Anciles field_dates, Castellar lab_location/sample, Alcoletge sulfate |
| **`extracted_but_filtered`** | 0 | 0 | (clean — no filtered losses) |
| **`extracted_low_confidence`** | 0 | 0 | (clean) |

## Done (2026-04-18)

- [x] Diagnostic v1.1: schema bump, calc_trace (bicapa+Crespo+cap_reason), ConceptScout summary, missing_summary, cost_summary
- [x] v1.2: `--llm-judge` ON by default + geotech-engineer prompt, judge_model in metadata, OpenRouter→Anthropic-direct switch
- [x] Per-vision-type backend selection (Claude for sondeig/dpsh, OpenAI for planol/projecte)
- [x] Vilanova radon (accent), Linyola architect priority, Bell-Lloc expedient (pressupost exclusion), Bell-Lloc sondeig regen + gate fix
- [x] OpenAI vision cost tracking, `--easy-wins` + `--leverage` flags
- [x] **`--ne-trace`** flag with 6-reason classifier + suggested fixes per variable
- [x] Cache rename safety (judge cache backup `.bak-2026-04-18`)
- [x] 396 tests passing (was 379; +17 across new test files)

## Active Blockers

- Instal·lació a l'ordinador d'Eva pendent
- **Email a Eva pendent d'enviar** — v4 a `docs/CORREU-EVA-PREGUNTES-CALCULS-v4.md`. 4 questions: (1) Nb×0.83 criteri, (2) n-factor Schmertmann per graves carbonatades, (3) Qa topall vs càlcul, (4) confirmar clamp φ=28° per transicionals
- 1 pre-existing test failure: `test_bell_lloc_bearing_idx_and_n20` (vision non-determinism on handwritten sondeig — see "Sondeig vision non-determinism" below)

## Open work — prioritized for tomorrow

### Highest leverage
1. **Schema gap fix** — add the 9 missing concepts (`access_street`, `sulfate_baumann/level_name/classification`, `spt_*` family) to `schemas/concepts/report_variables.yaml` with proper `source_priority` chains. **Estimated cuts NE from 39 → 21 (-46%)**, likely accuracy +3-5pp.
2. **Email-attachment role tracking** — 117 attachments saved across 7 projects, **0 assigned to any role**. Likely contains hidden planols (Vilanova `1.0.pdf`, Linyola `PLAN_COST_*.xlsx`). See `docs/INVESTIGACIO-EMAIL-ATTACHMENTS.md` (TODO) for finding details.
3. **Adjacents leverage** — `adjacent_north_fmt` (6 projects), `adjacent_south/east_fmt` (3 each) all MISMATCH due to cadastre wrapper writing generic "amb una parcel·la amb construcció" vs Eva's specific descriptions.

### Medium leverage
4. **Identity narratives** — `client_name` (5 proj MISMATCH), `architect_name` (4 proj MISMATCH), `site_description` (7 proj MISMATCH). Synthesis prompt needs work — Rubí especially picks vendor-not-person.
5. **CTE table lookup** — `cte_sol`, `cte_edificacio` MISMATCH on 4 projects each (logic bug or wrong N20 input?).

### Lower priority / methodology
6. **Castellar `qa_value` 3.0 → 2.0** — G.5/G.7 calc-chain change, may need Eva's input on whether middle layer is "transitional" or "normal".
7. **Sondeig vision non-determinism** — even Claude returns different layer splits on same handwritten sondeig PDF across runs. Curated d70030c fixture is the regression-test ground truth; live re-runs unreliable.
8. **Cost telemetry gaps** — Anthropic judge calls (significant, since judge ran on 281 vars) not captured in `cost_summary`. Claude vision cost shows $0 even when sondeig should use it (transient fallback?).
9. **CROSS metadata `judge_enabled=None`** — per-project files have `True` correctly, just CROSS aggregation step doesn't propagate. Cosmetic.

## Pla de Delivery

Detalls complets: `docs/PLA-DELIVERY-ACCIONS.md`
