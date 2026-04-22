# G3DT — Automatització d'Informes Geotècnics — Status
Last updated: 2026-04-22

## Current State

**Step 7 (geocoding pipeline simplification) mostly shipped.** Three streams merged on `experiment/cc-only-extraction` today: CartoCiudad native `refCatastral` + query filters, Cadastre error-code-16 fallback via `RCCOOR_Distancia`, and ICGC API Territorial fast path for Catalan projects. Full suite: **557 pass** (+37 new tests across 3 streams), zero regressions on any cycle, identical pre-existing failure set (22 fail / 13 err / 1 skip — all unrelated baseline items).

Last full diagnostic sweep was Apr 19 post-knob-fixes (**65.2% match+close**, +0.9pp over Apr 11). Step 6 + Step 7 impact not yet measured — due a re-sweep once upstream #8 (Vilanova address extraction) is resolved.

## Recently Shipped

| Date | Merge | Notes |
|---|---|---|
| 2026-04-22 | Step 7 #3 — ICGC API Territorial | Catalan fast path; cross-verifies refcadp vs CartoCiudad RC. `icgc_territorial` module + 15 tests. |
| 2026-04-22 | Step 7 #5 — Err-code-16 fallback | `Consulta_RCCOOR_Distancia` for street-centerline coords (Linyola/Anciles case). 13 new tests. |
| 2026-04-22 | Step 7 #1+#2 — CartoCiudad `refCatastral` + filters | One-call RC for portal matches; `municipio_filter`+`no_process`+`limit`. 9 new tests. |
| 2026-04-21 | Step 6 — CartoCiudad integration + bug-fix | Province-segment retry, portal-number matching. |
| 2026-04-21 | Steps 2b/3/3b/5 | Role-aware probe, LLM adjacent synthesis, judge cross-language tolerance, geocoding robustness. |

Full Step 7 tracker: `docs/knob-fixes-2026-04-19/STATUS.md`.

## Active Blockers

- **Installation on Eva's machine pending.**
- **Email to Eva pending** — v4 at `docs/CORREU-EVA-PREGUNTES-CALCULS-v4.md` (4 questions: Nb×0.83, Schmertmann n-factor for carbonated gravels, Qa cap vs calc, φ=28° clamp confirmation).
- **Step 7 #4 (ASMX→REST/JSON) blocked server-side** — Catastro's JSON endpoint returns `cod=76 "LA COORDENADA X OBLIGATORIA"` regardless of casing; WSDL exposes only SOAP binding. Code structured for drop-in flip if/when Catastro fixes it.
- 1 pre-existing test failure (vision non-determinism on handwritten sondeig PDF): `test_bell_lloc_bearing_idx_and_n20`.

## Next Milestones

1. **#8 Vilanova address extraction** (in flight — diagnostic running) — real address "Santa Gemma 4" never surfaces as a `street_address` prefill; FileMiner finds only G3 internal "C/ Vallbona, 22". Adjacents still produce wrong UTM `(298740.96, 4620349.31)` via a non-`_consulta_via` code path (Step 5 flagged this). Unblocks Vilanova verification of Step 7 improvements.
2. **Re-sweep 7-project diagnostic** to measure Step 6 + Step 7 impact on match+close rate.
3. **Schema-gap fix** — 9 missing concepts (`access_street`, `sulfate_*`, `spt_*` family) to `schemas/concepts/report_variables.yaml`. Est. NE 39→21 (-46%), +3-5pp accuracy.
4. **Email-attachment role tracking** — 117 attachments across 7 projects, 0 role-assigned. Hidden planols likely (Vilanova `1.0.pdf`, Linyola `PLAN_COST_*.xlsx`).

## Deferred

- Step 7 #4 (REST/JSON) — server-side block (above).
- Step 7 #6 (INSPIRE WFS-CP for adjacents) — optional; low priority.
- Identity narratives (`client_name`, `architect_name`, `site_description`): synthesis prompt work.
- CTE table lookup MISMATCHes (4 projects each on `cte_sol`/`cte_edificacio`).
- Castellar `qa_value` 3.0→2.0 — needs Eva's input on transitional-layer classification.

## Pla de Delivery

Detalls complets: `docs/PLA-DELIVERY-ACCIONS.md`.
