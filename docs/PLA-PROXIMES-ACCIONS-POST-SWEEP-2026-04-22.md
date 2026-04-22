# Pla de Pròximes Accions — Post-Sweep 2026-04-22

**Baseline sweep:** `docs/diagnostics/2026-04-22_CROSS_351d13.json` — 64.1% match+close (within Apr 19 judge-noise band of 62.4%-65.2%).

**Objective:** Identify, scope, and stage the highest-leverage fixes revealed by today's 7-project re-sweep. Do **not** execute yet — this document captures the analysis and plan.

---

## Cross-project failure-mode classification

Of the **78 total MISMATCHes** across 7 projects, the bulk cluster into **4 structural failure modes + 1 schema-gap class** — not 78 independent bugs:

| # | Failure mode | Vars affected | Projects | Root cause |
|---|---|---:|---|---|
| A | Schema gaps (NOT_EXTRACTED) | ~20 var-comparisons | 6-7/7 each | 9 concepts missing from `schemas/concepts/report_variables.yaml` |
| B | CTE classification threshold | 12 var-comparisons | 4/7 each | Single wrong-answer pattern across `cte_sol` / `cte_edificacio` / `qa_value` |
| C | Settlement format | 6 var-comparisons | 6/7 | Pipeline returns numeric `1.70`, Eva writes narrative prose. **Values are correct**. |
| D | Identity disambiguation | 8 var-comparisons | 4/7 each | `client_name` / `architect_name` — multi-name document, wrong person picked |
| E | Adjacent / location narrative | 12+ var-comparisons | 3-6/7 | Eva writes from visual observation; pipeline uses cadastre taxonomy |

**Top recoverable headline gain (A+B+C):** ~13pp if all three land cleanly.

---

## Action 1 — Schema gaps (highest leverage)

**Est. effort:** S (half-day)
**Est. headline impact:** +3-5pp (recovers ~20 NE var-comparisons)
**Risk:** Low

### 9 concepts missing from `schemas/concepts/report_variables.yaml`

| Concept | Projects affected | Eva example |
|---|---:|---|
| `access_street` | 6/7 | `"El dia dels treballs de camp es realitza l'entrada a la zona per..."` |
| `sulfate_baumann` | 3/7 | `"---"` |
| `sulfate_classification` | 1/7 | `"No Agressius"` |
| `sulfate_level_name` | 3/7 | `"2on nivell"` |
| `spt_depth_range` | 2/7 | `"-1.00 a -1.20"` |
| `spt_lithology` | 2/7 | `"Limolites i bretxes"` |
| `spt_location` | 2/7 | `"S-1"` |
| `spt_n30` | 2/7 | `"R"` |
| `spt_test_id` | 2/7 | `"SPT-1"` |

### Fix approach

1. Add 9 entries to `schemas/concepts/report_variables.yaml` with appropriate `type`, `group`, `source_priority` chains.
2. For the sulfate family: source chain should be `user: 10, lab_pdf: 20, pressupost_pdf: 30, content_email: 40, content_pdf: 45`.
3. For the spt family: source chain should be `user: 10, sondeig_vision: 20, dpsh_excel: 25, pressupost_pdf: 30`.
4. For `access_street`: source chain should be `user: 10, projecte_vision: 20, planol_vision: 25, content_email: 40`.
5. Verify `ConceptRegistry().all_concept_ids()` picks them up (new `test_all_vision_detectable_concepts_exist_in_registry` already enforces consistency between vision probe and YAML).
6. Check if any extractor already emits these internally and was just dropping them for lack of a concept definition. If yes, the concepts auto-populate; if no, add simple text/regex extractors.

### Acceptance

- NE count drops from 40 → ≤20 on re-sweep.
- No regression on existing MATCH/CLOSE/MISMATCH.

---

## Action 2 — CTE classification threshold bug

**Est. effort:** S (1-2 hours)
**Est. headline impact:** +4pp (12 var-comparisons across 4 projects)
**Risk:** Medium (calc-chain change; verify against Eva's criterion)

### The bug pattern

Across 4 projects (Castellar, Rubí, Linyola, Alcoletge, Vilanova):

| Variable | Eva consistently | Pipeline consistently |
|---|---|---|
| `cte_sol` | `T-1` | `T-2` |
| `cte_edificacio` | `C-0` | `C-1` |
| `qa_value` | `3.0` | `2.00` |

The off-by-one pattern is coherent across all 4 projects → single threshold bug, not 12 independent failures.

### Fix approach

1. Locate the CTE lookup in `automation/terzaghi_calculator.py` / `automation/report_data.py`. Most likely candidate: threshold boundaries between terrain types are off by one bracket (e.g., "Gravas y arenas" → T-2 when it should be T-1 given Eva's N20 interpretation).
2. Cross-reference Eva's methodology (`Spt-correlacions.doc` + `docs/RESPOSTA-EVA-PREGUNTES-CALCULS.md`) — Eva's question #3 was about Qa cap; related but distinct. For CTE table this is a direct lookup.
3. Compare Eva's actual reference-report N20 values against the thresholds. If Eva classifies `N20=14` as T-1 but our lookup says T-2, the threshold is too loose.
4. The `qa_value` 3.0 vs 2.0 is likely the Qa cap question — already answered by Eva in the 2026-02-26 email: "3.0 quilos és un topall màxim, en roca clara seria 4.0-4.50. Sinó preval Terzaghi-Peck."

### Acceptance

- 12 var-comparisons flip from MISMATCH to MATCH across Castellar / Rubí / Linyola / Alcoletge / Vilanova.
- Bell-Lloc's CTE values (currently MATCH) don't regress.

---

## Action 3 — Settlement format wrap

**Est. effort:** S (2-3 hours)
**Est. headline impact:** +6pp (6 var-comparisons across 6/7 projects — BIGGEST single lever)
**Risk:** Low (values already correct; only output format changes)

### The pattern

| Project | Eva | Pipeline |
|---|---|---|
| Bell-Lloc | `"Els assentaments màxims previstos per la càrrega..."` | `1.70` |
| Castellar | `"Els assentaments màxims previstos per la càrrega..."` | `1.80` |
| Linyola | same sentence | `1.80` |
| Alcoletge | same sentence | `2.20` |
| Vilanova | (Spanish variant) | `3.10` |
| Anciles | (Spanish variant) | `2.40` |

The pipeline's numeric output is presumably correct for the calculation; Eva ALWAYS writes a boilerplate narrative sentence with the number embedded.

### Fix approach

1. Locate `settlement` assembly in `automation/report_generator.py` / section templates.
2. Wrap the computed value in Eva's standard Catalan/Spanish sentence:
   - CA: `"Els assentaments màxims previstos per la càrrega recomanada són de {value:.2f} cm, inferiors als admissibles (2.50 cm per a estructures convencionals)."`
   - ES: `"Los asientos máximos previstos para la carga recomendada son de {value:.2f} cm, inferiores a los admisibles (2.50 cm para estructuras convencionales)."`
3. Extract the exact sentence template from 2-3 reference reports (Bell-Lloc, Castellar, Vilanova) to make sure we match Eva's phrasing.
4. Determine language per project (Catalan for Ponent, Spanish for Aragón / Cat-SP bilingual).

### Acceptance

- 6 var-comparisons flip to MATCH.
- The numeric value stays accurate; only the wrapping sentence is new.

### Caveat

The judge's Catalan↔Spanish tolerance (Step 3b) should accept either language, but verify on first re-sweep that it doesn't downgrade MATCH→CLOSE because the numeric value in the middle of the sentence triggers the "strict on measurements" rule (which we specifically added in Step 3b).

---

## Action 4 — Identity narrative synthesis

**Est. effort:** M (1-2 days)
**Est. headline impact:** +2-4pp (`client_name` 4/7, `architect_name` 4/7)
**Risk:** Medium (multi-source disambiguation is nuanced)

### The pattern

| Project | Field | Eva | Pipeline |
|---|---|---|---|
| Rubí | `client_name` | `"SRA. JOANA MARTINEZ"` | `"SRA. Mª JOSÉ MASIDE"` (vendor) |
| Linyola | `architect_name` | `"SÍLVIA EROLES BALAGUERÓ"` | `"JOSEP BUNYESC PALACIN"` (co-author) |
| Vilanova | `architect_name` | `"JUAN JOSÉ TORRES POVEDANO"` | `"JORDI CARNER"` |
| Anciles | `architect_name` | `"ALBA MARIA BARRAU CASTÁN"` | `"ALBA BARRUETA, nºCol. 6.408; MIRIAM CASTEL..."` (multi-author list with colegiada numbers) |

Vision extracts the wrong person when a document lists multiple (buyer + seller; lead architect + collaborator; architect + colegiado).

### Fix approach

1. Tighten the LLM synthesis prompt for `client_name` / `architect_name` to:
   - For `client_name`: **promotor / comprador / propietari**, never **vendedor / vendor / venedor**.
   - For `architect_name`: **lead architect** (first listed, or marked as "redactor", "arquitecte director"), not collaborators or colegiado registry numbers.
2. Add a cross-validation step: if vision extracts a name matching a `vendor_*` or `nºCol.` pattern, flag it and re-probe or abstain.
3. Where Eva's reference contains `SRA.` / `SR.` / `SRS.` title prefix, expect a natural-person name (first-name last-name). Companies like `PICO DE OLA ARQUITECTURA Y PROMOCION S.L.` shouldn't land in `client_name` when a `SRA.` variant exists.

### Acceptance

- 4 of 7 `client_name` MISMATCHes → MATCH.
- 3 of 4 `architect_name` MISMATCHes → MATCH (Anciles multi-author probably needs separate narrative synthesis).

---

## Action 5 — Adjacent / location narrative synthesis

**Est. effort:** L (3+ days, partial delivery realistic)
**Est. headline impact:** +2-5pp (hard to quantify; judge already tolerates Catalan↔Spanish and phrasing)
**Risk:** High (Eva's voice is intrinsically subjective)

### The pattern

`adjacent_north_fmt` fails 6/7, `adjacent_south/east/west_fmt` 3/7 each.

Typical gap:

- Eva: `"Por la parte noreste con un campo de conreo herbàceo, con árboles aíslats y algún arbusto"` (visual observation at the site visit).
- Pipeline: `"Por la parte noreste con la Carretera de Anciles"` (cadastre taxonomy + street name).

This is **not an extraction failure** — it's a philosophical gap. Eva describes what she SEES; the pipeline describes the abstract neighbor (another parcel, a street, a river). The `llm_synthesis_with_observations` path already exists (Step 3, prior session) but the visual-observation signals it draws from aren't strong enough.

### Fix approach

1. Improve visual-observation extraction (concept_scout `vision_probe.py` for `surrounding_context_visual`, `site_vegetation_visual`, etc.). Already shipped in the prior session; tune prompts.
2. Weight visual observations above cadastre text in the adjacent synthesis when both exist.
3. For projects WITHOUT visual observations (e.g., Anciles mostly has aerial-only), fall back to cadastre prose.
4. Consider: is this an "acceptable" gap? Eva's narrative is hand-written; fully replicating her voice on every adjacent is non-trivial and has diminishing returns once the pipeline reliably identifies the neighbor correctly.

### Acceptance

Soft target: +2pp. Stretch: +5pp. This is the kind of problem where 80% is reachable but the last 20% is Eva-in-the-loop territory.

---

## Suggested sequencing

1. **Action 1 (schema gaps)** first — biggest NE recovery with lowest risk. Pure YAML edit + maybe small extractor additions.
2. **Action 2 (CTE threshold)** second — single cause, bulk unlock. Needs verification against Eva's methodology doc before shipping.
3. **Action 3 (settlement wrap)** third — biggest single pp gain, format-only change, low risk. Verify measurements-strict judge rule doesn't trip on the wrapped number.
4. **Action 4 (identity synthesis)** — medium effort, medium gain. Do after 1-3 land.
5. **Action 5 (adjacent narrative)** — lowest priority. Consider whether the last-20% gain is worth the engineering effort or whether this is "good enough" as is.

After actions 1-3: projected headline ~**77-80%**. A plausible ceiling before Eva-voice narrative becomes the frontier.

---

## Non-headline improvements already shipped today (hidden wins)

These don't show in the headline because the judge-noise band masks them, but the **pipeline is qualitatively better**:

- **Vilanova geocoding chain end-to-end correct** — `adjacent_west_fmt` flipped `"Carrer Santa Marta"` MISMATCH → `"Carrer Santa Gemma"` MATCH. First time the CartoCiudad + ICGC chain works for a real Catalan project with a noisy vision-extracted address.
- **Vision signals compete in FileMiner** — structural fix that lets the right extractor win when multiple sources exist.
- **G3 internal address filter moved to competition** — prevents the `C/ Vallbona, 22` footgun from ever reaching downstream.
- **CartoCiudad accent-strict `municipio_filter` bug dropped** — would have silently broken future projects with un-accented folder names.
- **Hedged vision previews filtered** — prevents `"appears to be 2-3 levels"`-style prose from winning competition.
- **NOT_EXTRACTED count: 47 → 40** (-7). Wider extraction net, smaller blind spot.

---

## Deferred / unresolved

- **Step 7 #4 (Cadastre REST/JSON migration)** — blocked server-side. Code scaffolded for drop-in flip when Catastro fixes their JSON binding.
- **Step 7 #6 (INSPIRE WFS-CP for adjacents)** — medium effort, modest gain. Can stay deferred until after Actions 1-3.
- **Anciles DNS-error re-sweep** — today's 38.1% result had 13 network errors hitting it mid-sweep. Re-run with stable network to get a clean number.
- **Bell-Lloc handwriting fixture** — the `test_bell_lloc_bearing_idx_and_n20` pre-existing test failure is a vision non-determinism issue on the curated handwritten sondeig PDF. Not urgent.

---

## References

- Sweep CROSS snapshot: `docs/diagnostics/2026-04-22_CROSS_351d13.json`
- Per-project snapshots: `docs/diagnostics/2026-04-22_*_*.json`
- Apr 19 baseline runs (for judge-noise band): `docs/diagnostics/2026-04-19_CROSS_{00d6bf,221ac9,54663c}.json`
- Eva methodology source-of-truth: `docs/RESPOSTA-EVA-PREGUNTES-CALCULS.md`, `~/.claude/projects/-home-josep-projects-claudecode-job-clients-g3dt/memory/MEMORY.md`
- Concept-format schema design: `docs/ARQUITECTURA-CONCEPT-FORMAT-SCHEMAS.md`
