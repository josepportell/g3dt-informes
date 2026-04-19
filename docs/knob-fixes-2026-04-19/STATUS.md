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
