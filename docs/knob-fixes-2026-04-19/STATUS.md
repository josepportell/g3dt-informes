# Knob Fixes 2026-04-19 — STATUS

**Source:** manual walkthrough findings — `docs/inspect-examples/2026-04-19-email-attachments/README.md`
**Goal:** implement the top 5 knob fixes in 3 parallel streams, re-sweep, then revisit methodology.
**Baseline sweep:** 64.3% (post trust-fix, commit `e381f5e`)
**Target delta:** +1.5-4pp (predicted)

---

## Phase 1 — Three parallel streams

### Stream A — Expedient

**Scope:** #1 deterministic expedient from project folder name + #3 tighter expedient regex (defense-in-depth).
**Touches:** `automation/fileminer/miners/_detection.py`, `automation/fileminer/` (new deterministic source).
**Branch:** `fix/knob-expedient-deterministic` → merged as `c29af87`
**Acceptance:**
- Linyola `expedient` flips from `13/52/04` (MISMATCH) to `4001607` (MATCH) without regressions on the other 6 projects. *(Pending re-sweep verification.)*
- New test: folder-name-derived signal wins over regex when both present. ✓
- New test: tightened regex rejects uncontextualized numeric tokens (e.g. bare `13/52/04`). ✓
**Status:** merged. Implementer commits `c3d4a50` → `41589a0` (fix-up for shape-guard preamble warning).

### Stream B — Vision probe

**Scope:** #2 widen probe gate for layout-heavy text-extractable PDFs + #4 abstention clause + map-subject scoping in probe prompt.
**Touches:** `automation/concept_scout/vision_probe.py` (gate + prompt).
**Branch:** `fix/knob-vision-probe-gate-and-prompt` → merged as `c8dd829`
**Acceptance:**
- Vilanova `1.0.pdf` triggers vision probe (was skipped as text-extractable). *(Pending re-sweep verification.)*
- F1 SIT.png probe abstains on municipality instead of returning `Alpicat` (when re-run). *(Pending re-sweep verification.)*
- Cost delta per sweep: budgeted ≤ $0.50. Estimated ~$0.11 (~11 extra probes).
- New test: probe gate fires on layout-heavy PDF fixture. ✓ (truth-table test)
- New test: probe prompt round-trip preserves abstention field. ✓
**Status:** merged. Implementer commits `ebd90df` → `2edb845` (fix-up removed dead `_is_layout_heavy_text` heuristic, aligned legacy-dir handling, grounded 2000-char threshold).

### Stream C — Independent

**Scope:** #5 MsgMiner content-hash dedup + vision extractor `source_file` backlink (the one analysis-blocking data gap).
**Touches:** `automation/fileminer/miners/msg_miner.py`, vision extractor output writers (`automation/vision_extractor.py` + friends).
**Branch:** `fix/knob-msg-dedup-and-source-backlink` → merged as `ad0454b`
**Acceptance:**
- Duplicate .msg attachments (same content hash) mined once, not N times — measured on Rubí + Vilanova. *(Pending re-sweep verification.)*
- `validation/{planol,sondeig,dpsh,projecte,sondeig_annex,docs}_extracted.json` each carry `_metadata.source_file` = relative path to origin artifact. ✓ (all writers updated: `attach_source_metadata` helper; UTC timestamps normalized)
- New test: dedup skips second call for identical attachment. ✓
- New test: vision extractor output contains `source_file` key. ✓
- New test (fix-up): seed-path dedup preserves existing on-disk duplicate. ✓
**Status:** merged. Implementer commits `ad5df21` → `b3f924e` (fix-up: UTC everywhere, `threading.Lock`, streaming sha256 via `hashlib.file_digest`, removed `_SEEDED_PROJECTS` cache for long-running-server correctness).

---

## Workflow per stream

Per `~/.claude/CLAUDE.md` subagent loop:
1. Worktree (isolation: `worktree`) — isolates file edits, prevents collisions between streams.
2. `code-implementer` drafts changes.
3. `code-reviewer` with explicit findings list (no "looks good").
4. Loop until zero CRITICAL/WARNING.
5. `code-tester` runs `pytest` with 10-min timeout.
6. Loop until green.
7. Merge to `experiment/cc-only-extraction`.

Three streams kicked off in one message (parallel Agent calls).

---

## Merge + re-sweep

All 3 merges landed on `experiment/cc-only-extraction` without conflicts (file-touch boundaries were disjoint).

**Merge commits**: `c29af87` (A) → `c8dd829` (B) → `ad0454b` (C). HEAD: `ad0454b`.

**Full-suite test delta on merged state** (compared to parent `e381f5e`):
- Parent: 450 passed, 1 failed, 2 skipped, 13 errors.
- Merged: **475 passed**, 1 failed, 2 skipped, 13 errors.
- Net: **+25 passing tests**, 0 new failures, 0 new errors. Pre-existing `test_bell_lloc_bearing_idx_and_n20` regression and `automation/test_data_schema.py` + `templates/test_template.py` collection errors are unrelated to this work and remain.

Next:
1. Run full diagnostic sweep on 7 reference projects.
2. Record delta vs 64.3% baseline in this file under a new "Results" section.
3. Per-component scorecard: which streams contributed what.

---

## Phase 2 — Methodology revisions (post re-sweep)

**Biggest revision:** split Downstream Impact table's `status` column into `value_correct?` + `signal_won?`. The current column conflates two questions that the walkthrough showed are independent.

**Other 6 revisions:** see `docs/inspect-examples/2026-04-19-email-attachments/README.md` methodology-gaps section.

**Validation plan:** pick 1-2 artifacts from the re-sweep (ideally new MISMATCHes or new MATCHes vs baseline) and re-run the 9-field walkthrough with the revised template. If the new columns surface insights the old template hid, adopt. If not, revisit.

---

## Phase 3 — Tooling follow-up (new plan, later)

Only after Phase 2 template stabilizes. Scope TBD based on what methodology revisions change. The `automation/inspect/` library + slash commands sketched in `/home/josep/.claude/plans/we-need-to-dig-jaunty-ocean.md` "Tooling sketch" section is the starting point, not the commitment.

---

## 2026-04-19 post-merge re-sweep (Phase 1 results)

**Headline: 64.3% → 65.2% match+close (+0.9pp)** — below predicted +1.5-4pp range but with one clear Stream A win. Log: `docs/diagnostics/2026-04-19_post-knob-fixes-sweep.log`.

| Project | Baseline | Post-knob-fixes | Δ |
|---|---|---|---|
| Bell-Lloc | 76.7% | 76.7% | 0.0 |
| Castellar | 77.4% | 77.4% | 0.0 |
| Rubí | 67.6% | 67.6% | 0.0 |
| **Linyola** | 65.8% | **71.1%** | **+5.3** ✓ Stream A win |
| Alcoletge | 50.0% | 50.0% | 0.0 |
| Vilanova | 57.1% | 57.1% | 0.0 |
| Anciles | 33.3% | 33.3% | 0.0 |

**Confirmed**: Linyola `expedient` flipped MISMATCH → MATCH (`13/52/04` → `4001607`). Stream A's deterministic folder-name signal worked as designed.

**Unmeasured gains**: Stream B (probe gate widening) is working structurally — `1.0.pdf` now gets probed and classified as `architect_plan` → vision extractor runs → extracts architect/client/dimensions. But the metric didn't move because the architect on the plan ("jordi carner") doesn't match Eva's reference ("JUAN JOSÉ TORRES POVEDANO") — likely a different role/naming convention. Stream C (dedup) invisible to MATCH/MISMATCH metric by design.

---

## 2026-04-21 follow-ups (Steps 2b, 3, 3b, 5, 6)

After the re-sweep we pivoted into a focused sub-investigation on adjacents (four N/S/W/E description fields, underperforming at ~43% match+close). This produced five additional merged streams (some flagged separately below):

### Step 2b — Role-aware filter in vision_probe (merged `2d892cc`)
**Branch:** `fix/role-aware-probe-filter` → **Commit:** `67bb32c` + merge.

`automation/concept_scout/vision_probe.py`: allow files with roles in `{photo_site_overview, photo_test_point, photo_spt_sample, field_photo}` through the `_SKIP_PHOTO_DIRS` filter. Previously all `FOTOGRAFIES/` files were skipped unconditionally — that was fine before the 6 visual-observation concepts were added, then became a regression. Linyola + Bell-Lloc went from 0/6 to 5/6 visual concepts populated (confirmed by targeted diagnostic re-run).

### Step 3 — LLM adjacent synthesis with end-to-end wiring (merged `8dab93b`)
**Branch:** `feature/llm-synth-adjacents` → **Commits:** `8ac5e5b` (synth logic), `3faed25` (wiring fix-up).

Extended `web/wizard_service.py:_synthesize_with_llm` to produce `adjacent_{north,south,east,west}_fmt` from cadastre facts + visual observations. Gated to projects with ≥2 visual observations. Wired end-to-end:
- `automation/report_generator.py` now delegates adjacent resolution to new `automation/adjacent_formatter.py:resolve_adjacent_fmt` helper with per-direction precedence `user > llm_synthesis_with_observations > cadastre template`.
- `automation/wizard.py:WIZARD_FIELDS` gains the 4 `*_fmt` names for persistence.
- `templates/validation/review.html` renders a new "Adjacents - frases redactades" group with 4 textareas + source badges.
- Schema priorities (`user: 10`, `llm_synthesis: 20`, `formatted_cadastre: 30`) are documentation-only; runtime resolution is via write-last-wins in `_synthesize_with_llm`. YAML has a NOTE documenting this.

**Targeted sweep result (6 projects with visuals):** adjacent MATCH+CLOSE unchanged at 11/24 = 45.8%. Wiring works (all 24 directions now sourced `llm_synthesis_with_observations`), but the LLM rephrasing doesn't move the needle meaningfully — either matches cadastre template verbatim (Vilanova, when visuals add nothing) or drifts slightly (Bell-Lloc west: CLOSE → MISMATCH).

### Step 3b — Judge prompt: cross-language + preposition tolerance (merged `f1b3c61`)
**Branch:** `fix/judge-cross-language-tolerance` → **Commit:** `174a9c9` + merge.

`scripts/compare_benchmarks.py`: additive edits to `compare_text_llm`'s system prompt — explicit Catalan↔Spanish cross-language MATCH rule, preposition-variant MATCH (Vilanova `de Segrià` vs `del Segrià`), 2 worked examples, a new "## Strict on measurements" section locking strictness on numeric fields. Refactored the prompt string into module-level `_JUDGE_SYSTEM_PROMPT` constant (exposed via `get_judge_system_prompt()`) for hermetic tests.

Judge cache was cleared and re-run on all 7 projects. Cache now contains multiple explicit MATCH verdicts citing `"Language difference (Catalan vs Spanish) irrelevant"` — prompt change IS being applied. However, Vilanova's 4 adjacent MISMATCHes did NOT flip because the underlying mismatch is factual, not language (Eva's "parcelas de similares características" vs pipeline's "Carrer Santa Anna" — different content entirely).

### Step 5 — Geocoding robustness (merged `81bebee`)
**Branch:** `fix/geocoding-robustness` → **Commit:** `de36566` + merge.

Two linked fixes motivated by Vilanova cadastre wrong-parcel regression (uncovered during Step 3b audit):

- **Fix 1** — `_consulta_via` now strips full-word street-type prefixes (`Carrer`, `Calle`, `Plaça`, etc., + connectors `de`/`del`/`d'`) before hitting Cadastre. Before: `"Carrer Santa Gemma"` wrongly matched to `CARRERADA PD 83` (a different *partida*). After: resolves correctly to `SANTA GEMMA CL 109`. Live-test confirmed.
- **Fix 2** — Run Cadastre + Nominatim in parallel; if Cadastre's resolved parcel's adjacents don't contain the project street, switch to Nominatim's UTM and re-query Cadastre by RCCOOR. Helper `_project_street_matches_cadastre` introduced.

**Vilanova impact**: targeted re-run still produces wrong UTM `(298740.96, 4620349.32)`. Fix #1 didn't apply because the pipeline's wrong-UTM derivation goes through a different code path (probably `cadastre_search_address` / Callejero, not `_consulta_via`). Fix #2 didn't trigger because Nominatim doesn't geocode Vilanova at all (empty result for the address). Step 5 merged for completeness but didn't fix Vilanova.

### Step 6 — CartoCiudad (IGN) integration (MERGED)
**Branch:** `feature/cartociudad-geocoder` → merged into `experiment/cc-only-extraction`. **Commits:** `da77cf2` (initial impl) + `486d876` (bug fix-up). **Status:** live-verified; next session should run Vilanova diagnostic to confirm west-adjacent flips to MATCH.

**Bug fix-up (`486d876`):** live integration test caught two bugs in `da77cf2`:
1. Vilanova returned `None` because appending province as a third comma-segment (`"Santa Gemma 4, Vilanova de Segrià, Lleida"`) makes CartoCiudad return zero candidates. Fix: retry without province after a zero-result first attempt.
2. Multi-portal streets picked wrong candidate (Linyola returned #17 not #16; Anciles returned #10 not #20). Fix: parse trailing digits from input address, prefer candidates with matching `portalNumber` field, optional broader-query retry.

Post-fix live verification (all 4 cases correct):
```
Vilanova:  (41.70978, 0.57897)  ✓
Linyola:   (41.70860, 0.89561)  ✓ house #16
Anciles:   (42.59199, 0.51050)  ✓ house #20
Bell-Lloc: None                 ✓ expected miss
```

Implementation summary (per handoff):
- `cartociudad_geocode(address, muni, province)` at `automation/geocode_coordinates.py:1861-1950`, supporting helpers `_cartociudad_cache_key`, `_cartociudad_cache_load/save`, `_parse_cartociudad_body`, `_cartociudad_muni_matches` at lines 1710-1859.
- Municipality match: accent-insensitive + case-insensitive substring both directions, parenthetical suffixes stripped.
- Cache: `~/.g3dt/cache/cartociudad/{sha256-12}.json`, 365-day TTL, negative caching for `__MISS__`, honors `G3DT_NO_CACHE=1`, atomic writes.
- Reconciliation: preserved the old `_run_cadastre_and_nominatim_parallel` name so Step 5 tests keep passing; new `_run_cadastre_and_alternates_parallel` wraps it + adds CartoCiudad branch. CartoCiudad > Nominatim > cadastre-as-is.
- HTTPError → no retry (won't heal), URLError → exponential backoff 3 tries, transient failures not cached.
- Nominatim path preserved as tertiary safety net.
- 27 new tests including `test_vilanova_cartociudad_wins_over_nominatim` (end-to-end reconciled flow).
- Full suite: +27 passing, 0 regressions, identical pre-existing-failure set.

Motivation from live empirical testing:
- Nominatim (OSM) has sparse coverage of Catalan small towns — geocoded 2 of 7 projects, both as street centerlines (not usable for parcel lookup).
- CartoCiudad (IGN Spain-wide) geocoded 5 of 7 as `type=portal` entrance-level. Specifically resolves `"Santa Gemma 4, Vilanova de Segrià"` → lat/lng `(41.70978, 0.57897)` → UTM `(298580.9, 4620387.1)` → Cadastre RCCOOR valid RC `8606709CG9280N` → adjacents include `"Carrer Santa Gemma"` west. End-to-end.

Expected impact on Vilanova: +1 MATCH (west adjacent flips to match Eva's `"calle STA. GEMMA"`). Other 3 directions stay MISMATCH — those are an Eva-vs-cadastre narrative-vs-taxonomy philosophy gap, unrelated to geocoding.

Scope dispatched:
- New `cartociudad_geocode(address, muni, province)` in `automation/geocode_coordinates.py`.
- Candidates endpoint + portal-preference + muni-match filter + `callback(...)` stripping + 24h disk cache.
- Extends Step 5's parallel branch to Cadastre + Nominatim + CartoCiudad. Reconciliation order: CartoCiudad > Nominatim > stick with Cadastre.
- 11 hermetic tests + end-to-end Vilanova flow.

### Deprioritized

- **Step 4 (PNOA/IGN all-Spain ortho coverage)** — task #21, still pending. Anciles is the test case (no visual observations because it's in Aragón, outside ICGC ortho coverage). Discussed in passing; no concrete plan file yet. Revisit once CartoCiudad merges and we have a clean baseline.

---

## Session end state — 2026-04-21 (for fresh session continuation)

**Current HEAD of `experiment/cc-only-extraction`**: Step 6 merged (commits `da77cf2` + `486d876`). Nothing awaiting merge.

**Active tasks (carry forward into new session):**
- #21 Step 4 — PNOA/IGN all-Spain ortho coverage roadmap (pending, not started).
- #26 Step 7 — Simplify geocoding pipeline per official-manuals findings (new, details below).

**First thing to do in next session:** targeted Vilanova diagnostic. Clear cache (`rm ~/.g3dt/cache/cadastre_adjacents/fe4d8e63cbea.json`, `rm "reference-material/4001671 VILANOVA DE SEGRIA/validation/concept_map.json"`) and run `.venv/bin/python scripts/diagnostic_trace.py --save --project 4001671 --components`. Expected: west-adjacent flips `Carrer Santa Marta` → `Carrer Santa Gemma` → MATCH.

---

## Step 7 — Simplify geocoding pipeline per official-manuals findings (pending)

**Task:** review G3DT's current 3-hop geocoding flow (CartoCiudad → Cadastre RCCOOR → Cadastre geometry probing) and adopt simplifications authorized by the three official manuals archived under `docs/cadastre/manuals/`. Live-validated 2026-04-21; cross-references INDEX.md in that folder.

**Motivation:** during Step 6's investigation we discovered our current flow makes avoidable HTTP hops and ignores response fields that carry authoritative data directly. Official docs + empirical validation show a much cleaner pipeline is available.

### Six concrete opportunities (ranked by impact × effort)

1. **Use CartoCiudad's native `refCatastral`** — `candidates`/`find`/`reverseGeocode` all return the 14-char Spanish RC on portal matches. For Vilanova's portal: `refCatastral='8606709CG9280N'` comes back in the same response as lat/lng. **Eliminates the RCCOOR hop entirely** for the happy path. Verified live.

2. **Use CartoCiudad filters we currently ignore** — `municipio_filter=<muni-name>` (by name, not muniCode) + `no_process=toponimo,municipio,comunidad autonoma,poblacion` + `limit=5`. Live test: reduced a 13-candidate noisy query for `"Santa Gemma"` down to **1 exact portal**. Would have prevented the multi-portal disambiguation bug we hit in Step 6 (Linyola #17 instead of #16).

3. **Wire ICGC API Territorial for Catalan projects** — `GET https://api.icgc.cat/territorial/elements/cadastre,municipis,sigpac,qualificacions-muc/{lng},{lat}` returns 4 GeoJSON features in one call: parcel polygon (`refcadp` field = same 14-char RC), municipality + comarca + província, SIGPAC agricultural codes, urban zoning. Replaces multiple WMS GetFeatureInfo queries. Catalonia-only; Anciles still via Catastro. **Caveat: coord order is `{lng},{lat}` (or UTM `{x},{y}`), NOT `{lat},{lng}` — wrong order silently returns 0 features.** Verified live.

4. **Upgrade Cadastre calls from ASMX to REST/JSON** — `COVCCoordenadas.svc/json/Consulta_RCCOOR?SRS=EPSG:25831&...` instead of the legacy `OVCCoordenadas.asmx`. Takes `EPSG:25831` natively (no reprojection). Better ergonomics for the non-Catalan fallback path.

5. **Distinguish error code 16 from transport failures** — Cadastre returns code 16 = "PARA ESAS COORDENADAS NO HAY REFERENCIA DISPONIBLE" when the coord is on a road/unbuilt area. Our current code conflates this with network errors and returns `None` indiscriminately. Handling code 16 explicitly + calling `Consulta_RCCOOR_Distancia` for nearest RCs would recover the Linyola/Anciles street-centerline cases we currently give up on.

6. **Replace ASMX adjacents geometry probing with INSPIRE WFS-CP** (optional) — `wfsCP.aspx` `GetFeature` by RC returns the parcel polygon in a standards-compliant format. Current code uses bespoke ASMX geometry logic; WFS-CP would be cleaner and more stable. Lower priority than #1-#5.

### Bonus — cross-verification for high-stakes cases

CartoCiudad's `refCatastral` and ICGC's `refcadp` are byte-identical for the same address (verified for Vilanova: both returned `8606709CG9280N`). Comparing them gives a free sanity check — if they disagree for a Catalan project, one of the data sources is wrong and we should flag the case rather than proceed silently.

### Target pipeline after adoption

```
project address + municipality
    │
    ▼
CartoCiudad candidates  [q + municipio_filter=<name> + no_process + limit=5]
    │
    ├─ hit? portal with refCatastral  ← RC acquired, skip RCCOOR
    │      ├─ Catalonia?  → ICGC API Territorial /elements/cadastre,municipis,qualificacions-muc/{lng},{lat}
    │      └─ elsewhere?  → Cadastre WFS-CP GetFeature by RC → buffer + RCCOOR probe ring
    │
    └─ miss? → Cadastre RCCOOR REST/JSON (coord → RC as authoritative tiebreaker)
```

**Happy-path cost**: current 3 hops → **1 HTTP call to CartoCiudad + 1 to ICGC** for Catalan portal-matched addresses. Authoritative RC direct from response. No fuzzy matching. Nominatim + current ASMX fallback stays as a tertiary safety net for when CartoCiudad misses.

### References

- `docs/cadastre/manuals/INDEX.md` — full research + live validation log.
- `docs/cadastre/manuals/CartoCiudad_ServiciosWeb.pdf` — REST geocoder spec + `refCatastral`, filter semantics.
- `docs/cadastre/manuals/Catastro_Webservices_Libres.pdf` — WCF REST/JSON endpoints + error code table.
- `docs/cadastre/manuals/ICGC_API_Territorial_docs.html` — API Territorial overview (canonical URL `https://api.icgc.cat/territorial/documentacio/`).
- `docs/cadastre/manuals/Catastro_INSPIRE_CP_WFS.pdf` — INSPIRE WFS-CP parcel geometry service.

**Completed since Phase 1 merges:**
- #18 Step 1, #19 Step 2, #20 Step 3, #22 Step 2b, #23 Step 3b, #24 Step 5.

**Open questions when resuming:**
1. After Step 6 lands: does Vilanova's west-adjacent actually flip to MATCH in a full diagnostic? Measure.
2. The Vilanova wrong-UTM originally came from some non-`_consulta_via` path. If Step 6 works via reconciliation, root cause doesn't matter. If not, trace `cadastre_search_address` / Callejero.
3. Eva's adjacent-narrative philosophy (field observations vs cadastre taxonomy) is a design decision, not a pipeline bug. Raise with user before attempting to close the 9 cadastre-vs-Eva MISMATCHes across projects.
4. The 2 non-adjacent Alcoletge flips (`location_sentence`, `site_condition`) came from pipeline-output drift after Step 2b added visual observations. Acceptable collateral or worth revisiting.
