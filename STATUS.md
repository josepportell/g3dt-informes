# G3DT — Automatització d'Informes Geotècnics — Status
Last updated: 2026-04-26 (end of session)

## Current State

**AI Pipeline Phase 5 hardened over 5 offline iterations — zero API spend.** Branch `experiment/ai-pipeline` now carries the full LLM-based authority ranker (Stages 1–5) plus diagnostic infrastructure, calculator delegation MVP (Phase 1), strengthened authority principles, and ground-truth corrections across 7 reference projects. **Full suite: 984 passing** (+100 vs the 884 baseline pre-session).

The legacy deterministic pipeline (FileMiner + ConceptScout + auto_extractor on `feature/action-2-deterministic`) is unchanged from 2026-04-22.

## Today's frontier movement

| Metric (Alcoletge, no API spend) | 2026-04-24 (last live run) | Today |
|---|---:|---:|
| Eva refs visible to trace tool | 34 | **47** |
| Exact matches | 5 | **13** |
| `top1_accuracy` | 14.7% | **27.66%** |
| Pass C verdicts (better/worse/neutral/no-ref) | 3/1/1/9 | **5/3/1/5** |

The accuracy jump comes from honest measurement (alias map + UTM ground truth + bearing-stratum fix surface concepts that previously read as "no_eva_ref") on top of real ranker improvements. The Pass C "5 better" are all tracked on Eva-referenced concepts; the "3 worse" includes the now-visible utm_x/utm_y corruption (utm_x: 308782 → 0.70348) that motivated the new `G3DT_AI_SKIP_GROUPS` env var.

## This session's commits (8 on `experiment/ai-pipeline`)

| Commit | What it does |
|---|---|
| `dce5912` | Session summary + handoff doc for 2026-04-27 |
| `82b45c8` | C1 polish + `G3DT_AI_SKIP_GROUPS` env var (skip Pass B per group) |
| `f32eadc` | Phase 1 calculator delegation (Stage 4.5) + A3 silent-source rules |
| `15505ac` | B3 investigation doc (engineering-judgment delegation GO recommendation) |
| `6d706f2` | B1 audit + UTM/full-name principles |
| `93e6fe6` | A3 silent sources + B2 architect_name investigations |
| `e0579be` | Bearing-stratum extraction bug fix (geotech_rows[0] → geotech_rows[-1]) |
| `a3bbfc7` | reference_extractor merge logic — preserves intelligent_analysis entries |

## Per-project ground-truth state

| Project | UTM truth | Architect verified | Geomech (bearing) |
|---|:-:|:-:|:-:|
| Castellar | ✓ | (single-layer; auto OK) | ✓ unchanged |
| Rubí | ✓ | (single-layer; auto OK) | ✓ unchanged |
| Linyola | ✓ | manual (firm-led) | ✓ E now >800 |
| Bell-Lloc | ✓ | (single-layer; auto OK) | ✓ unchanged |
| Alcoletge | ✓ | manual (truncated body) | ✓ E now >400 |
| Vilanova | — (no COORDENADES.txt) | (auto pending verify) | ✓ E now 550 |
| Anciles | — (no COORDENADES.txt) | (auto pending verify) | ✓ unchanged |

## Suggested sequencing (next session)

1. **D1 — live re-run on Alcoletge**, ~$2.50–2.55 of the $5 ceiling. Procedure in `docs/_FOR-NEW-YOU-20260427.md` §4. Decide between option A (skip-coordinates only), B (also enable calculator), or C (separate-measurement) — all three cost the same.
2. After re-run: re-trace, re-Pass-C-diff, compare verdicts.
3. If accuracy ≥80% gate (per design doc §11): Phase 5 reaches adoption-ready threshold.
4. If not: iterate principles or extend reference_extractor (table-flatten more concepts) — both offline.

## Active Blockers

- $5 budget ceiling. Live re-run estimated $2.50–2.55. ~$2.45 buffer.
- Eva-clarification questions pending:
  1. `QA_CAP_ROCK = 3.0` (legacy code) vs Eva's 4.0–4.5 (per MEMORY) — affects calculator output for rock projects.
  2. Refusal-Nb canonical rule — `R` vs numeric-prefix-R like `47-R`.
  3. Why PyMuPDF re-encoded the PLAN_COST_ALCOLETGE logo such that pHash didn't match.
- Installation on Eva's machine pending.
- 1 pre-existing test failure: `test_bell_lloc_bearing_idx_and_n20` (vision non-determinism, deselected in CI).

## Deferred / open tasks

- **Phase 2 calculator delegation** — extend `_TERZAGHI_EXTRACTORS` to `geomech_E/phi/cohesion/gamma`, `Es_settlement`, `k30_value`. Plumbing is identical; gated by validating Phase 1 first.
- **B1 audit recommendations not yet implemented**: confidence-based no-change guardrail; per-group prompt tuning.
- **Reference extractor table-nested concepts**: utm_x/y currently come from manually-added `intelligent_analysis` entries; extending the flatten to extract them automatically from `dpsh_tests` rows is the next coverage win.
- **Step 7 #6** (INSPIRE WFS-CP for adjacents) — medium effort, modest gain. Pre-existing.

## Live re-run readiness

| Item | Status |
|---|:-:|
| D17 dev-only filter shipped (filters `_informe*`, `_generated*`, `_portada*`) | ✓ |
| D18 cache fix (concept YAML in cached block, ≥1024 tokens) | ✓ |
| Alias map for trace-tool measurement | ✓ |
| Authority principles strengthened (10 numbered sections, TOC) | ✓ |
| Manual ground truth for UTM (5/7) and architect (Alcoletge, Linyola) | ✓ |
| Phase 1 calculator delegation (qa_value + settlement_cm) | ✓ behind feature flag |
| `G3DT_AI_SKIP_GROUPS=coordinates` to eliminate UTM corruption | ✓ |
| Cache invalidation procedure documented | ✓ in `_FOR-NEW-YOU-20260427.md` §4 |

## Pla de Delivery

Detalls complets: `docs/PLA-DELIVERY-ACCIONS.md`.

## Metodologia d'Eva (source-of-truth)

`docs/METODOLOGIA-EVA.md` — síntesi dels 7 informes signats amb cites textuals (Crespo / Rodríguez Ortiz / Schmertmann / Terzaghi-Peck). PDF d'Ortiz Cap. 2 arxivat a `docs/research/books/`. Referència primària per qualsevol canvi en càlculs geotècnics.

## Documents clau d'aquesta sessió

- `docs/_RESUM-SESSIO-20260426.md` — recap exhaustiu.
- `docs/_FOR-NEW-YOU-20260427.md` — handoff per la propera sessió.
- `docs/INVESTIGACIO-GEOMECH-STRATUM.md` — A1.
- `docs/INVESTIGACIO-SILENT-SOURCES.md` — A3.
- `docs/INVESTIGACIO-ARCHITECT-NAME.md` — B2.
- `docs/INVESTIGACIO-PASS-BC-EFFECTIVENESS.md` — B1.
- `docs/INVESTIGACIO-ENGINEERING-DELEGATION.md` — B3.
