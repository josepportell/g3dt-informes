# G3DT — Automatització d'Informes Geotècnics — Status
Last updated: 2026-04-30

## Current State

**Live re-run #3 (Alcoletge, 2026-04-30) completed end-to-end.** All 3 Stage-5 passes ran; D18 prompt-cache fix validated in production: `cache_creation=536,381` / `cache_read=595,484` (vs 420k / 0 last run). Total reported $5.10; Anthropic platform Stage 4 alone $3.30 → telemetry undercount worsened from 1.58× to **3.1×**. Total run actual ~$7.60.

**Coverage**: 49 ranked / 12 single / 28 no-candidates / 0 pending_fase5. Pass B audited 10 groups (30 factors). Pass C: 15 reorderings + 10 no-change guardrails.

**Eva ground truth**: 7/47 hit (3 exact + 4 substring). 40 misses cluster in known buckets — calculator phi-input plumbing (6), lab data formatting (8), adjacents source pipeline (8), descriptive-prose mismatches (~10), hard misses (~8).

**Castellar attempted same day** — Stage 2/3 OK, Stage 4 hit circuit breaker on 3 consecutive vision-input timeouts after 7 sources. Cancelled before meeting; partial state preserved.

**G3DT meeting held 2026-04-30 afternoon.**

## D18 cache fix shipped (commit `79b44fa`)

Pass A only; Pass B/Pass C still carry the same prefix-divergence bug (deferred — neither was on the critical path). Schema 1.2. Test `test_pass_a_system_cached_prefix_is_byte_identical_across_concepts` pins the byte-identical-prefix invariant offline.

## Highest-leverage open items

1. **Cost telemetry retry aggregation + hard 90% budget guard.** Undercount is now 3.1× — budget reasoning unreliable. Highest priority before the next live run.
2. **Calculator pass input plumbing** — pass emits 0 candidates (phi missing). Blocks 6 geomech concepts on every project.
3. **Castellar Stage 4 timeout investigation** — identify which vision input triggered the 3 consecutive timeouts; either pre-resize images, split large PDFs, or extend per-call timeout.
4. **Cache TTL 5min → 1h** — Stage 5 runtime ~45 min; cached prefix expires repeatedly, costing ~5× more than necessary.
5. **Pass B + Pass C cache fix** — mirror of Pass A schema 1.2 migration. Worth doing before next live run if budget remains tight.

## Active Blockers

- Cost telemetry undercount (3.1×) — see #1 above.
- Castellar Stage 4 vision timeouts — see #3 above.
- Eva-clarification questions still pending: QA_CAP_ROCK constant, refusal-Nb canonical rule, PLAN_COST logo pHash mismatch.

## Per-project ground-truth state (unchanged)

| Project | UTM truth | Architect verified | Geomech (bearing) | Eva baseline acc% |
|---|:-:|:-:|:-:|:-:|
| Castellar | ✓ | auto OK | ✓ | 77.4 |
| Linyola | ✓ | manual (firm-led) | ✓ E >800 | 73.7 |
| Bell-Lloc | ✓ | auto OK | ✓ | 72.1 |
| Rubí | ✓ | auto OK | ✓ | 63.9 |
| Vilanova | — | (auto pending) | ✓ E 550 | 56.0 |
| Alcoletge | ✓ | manual (truncated body) | ✓ E >400 | 47.8 |
| Anciles | — | (auto pending) | ✓ | 38.1 |

(Eva-vs-pipeline tiered, source: `docs/diagnostics/2026-04-22_CROSS_351d13.json`.)

## Wizard

Running on http://localhost:8765 pointing at `/mnt/c/claude/g3dt/projectes/` (Windows). Background PID 93007. Stop with `pkill -f "python -m web"`.

## Reading order for next session

1. `.claude/sessions/2026-04-30-session.md` — what landed in this session.
2. `docs/diagnostics/ai_pipeline_4001670_20260430.md` — Alcoletge trace + top issues.
3. `docs/INVESTIGACIONS-CREDIT-BLACKOUT-2026-04-27.md` — strategy + matrices (still relevant).
4. `docs/_FOR-NEW-YOU-20260427.md` — pre-D18-fix handoff (mostly superseded).

## Authoritative investigation docs (load before changing calculations or pipeline)

- `docs/METODOLOGIA-EVA.md` — calculation source-of-truth (Crespo, Schmertmann, Terzaghi-Peck, CTE D.27, Rodríguez Ortiz Cap. 2). §8 indexes the five investigation docs below. Now also has YAML front matter for PDF generation.
- `docs/INVESTIGACIO-GEOMECH-STRATUM.md` — bearing stratum semantics (geomech_*).
- `docs/INVESTIGACIO-ENGINEERING-DELEGATION.md` — Phase 1 calculator delegation catalog.
- `docs/INVESTIGACIO-ARCHITECT-NAME.md` — Eva's 4 architect/client writing patterns.
- `docs/INVESTIGACIO-SILENT-SOURCES.md` — Stage 2 pre-skip rules.
- `docs/INVESTIGACIO-PASS-BC-EFFECTIVENESS.md` — Pass B/C cost-vs-benefit per group.

## Metodologia d'Eva (source-of-truth)

`docs/METODOLOGIA-EVA.md` (+ `.pdf` + `.yaml`). Reference primària per qualsevol canvi en càlculs geotècnics.
