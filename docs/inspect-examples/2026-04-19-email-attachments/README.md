# Per-Artifact Deep Inspection — 2026-04-19 Email Attachments

This directory contains the **manual walkthrough** deliverable from the plan `/home/josep/.claude/plans/we-need-to-dig-jaunty-ocean.md`. Five problematic (or notably working) email-attached files from yesterday's Phase A+B work, each traced through every pipeline stage it touched, using **only data already persisted** on disk — no code changes, no new instrumentation, no slash commands.

**Purpose:** validate the 9-field-per-stage methodology on real artifacts, extract specific knob-level fixes that would move the accuracy numbers, and identify which data gaps (if any) actually block analysis.

## Artifacts inspected

| # | File | Project | Failure mode |
|---|---|---|---|
| 1 | [`1.0_pdf_vilanova.md`](1.0_pdf_vilanova.md) | Vilanova | Misclassified (architect_plan → situation_plan); Groq extracted wrong architect_name |
| 2 | [`img_wa0015_rubi.md`](img_wa0015_rubi.md) | Rubí | Classification correct but vision extraction didn't find architect_name (image likely doesn't contain it) |
| 3 | [`f1_sit_vilanova.md`](f1_sit_vilanova.md) | Vilanova | Classification correct; probe surfaced wrong-confident municipality ("Alpicat") that correctly lost competition |
| 4 | [`m1_castellar.md`](m1_castellar.md) | Castellar | Nothing failed — used as the "works as intended" baseline |
| 5 | [`dg_silvia_linyola.md`](dg_silvia_linyola.md) | Linyola | Classification correct (role already filled); FileMiner regex extracted wrong expedient "13/52/04" |

Each file follows the 9-field template: **goal / config / expected / actual / deviation / knobs / hypothesis / replay** per stage, plus a **downstream impact** table, a **one-stage-to-blame hypothesis**, and a **recommended knob (highest leverage)**.

---

## Cross-artifact patterns

Recurring deviations observed across the 5 artifacts. Not all appear in every case — column marks which artifact exhibited each.

| Pattern | Where it bit | Severity |
|---|---|---|
| **Vision probe gate is too conservative** — text-extractable PDFs skip the probe even when text is semantically useless (layout coordinates, CAD-exported dimension strings). | Artifacts 1, 5 | **High** — blocks architect_plan classification for layout-heavy PDFs |
| **Probe generates plausibly-wrong answers with high confidence, rarely abstains.** | Artifacts 3 (Alpicat at 0.8) vs. 4 (province abstained at 0.0) — same prompt, different image content, different behavior | Medium — harmless today thanks to priority math, but scales poorly if we widen the probe's concept list |
| **LLM extractors (Groq, vision) don't ground their answers.** A grounded extractor would return the text span that justifies each field, letting us audit post-hoc. | Artifacts 1 (Groq's `jordi carner`), 5 (vision's `JOSEP BUNYESC` vs Eva's `EROLES BALAGUERÓ`) | High |
| **MsgMiner duplicates content extensively.** Three physical copies of the same DG PDF; every downstream stage processes all three. | Artifact 5 (3× DG, 2× Punts de Sondeig, various mined_images duplicated) | Low-Medium — scales LLM cost ~20-30%, indirectly risks vision cap exhaustion |
| **FileMiner regex is too permissive for expedient.** `\d+/\d+/\d+` matches the architect's internal visa code, not G3DT's expedient. | Artifact 5 (all 6 competing expedient signals agreed on the wrong answer) | **High** — direct MISMATCH, applies to any project whose PDFs contain slash-separated numbers |
| **Vision extractor outputs don't backlink source_file** — `validation/*_extracted.json` has `source_file: null`, so winning vision signals don't appear in `variables[].signals[]` for artifact-centric analysis. | Artifacts 2, 5 | Medium for analysis tooling; zero effect on pipeline correctness |
| **"Role already filled" correctly blocks redundant promotion but also blocks legitimate secondary sources.** | Artifact 5 (msg-copy of DG PDF is identical content, so no loss — but a *different* newer revision in email would be missed) | Low today, but a trap for future email-revision workflows |
| **Domain-knowledge gaps in LLM prompts.** "Owner-architect wins over designer-architect" (Linyola), "client is the person, not the firm" (Rubí) are Eva conventions that the prompts don't encode. | Artifacts 2, 5 | Medium — causes MISMATCHes where substance is close but not matching Eva's specific rule |

---

## Ranked knob-level fixes (top 5 to implement first)

Ordered by estimated accuracy impact × implementation cost. Each ticket-ready.

### 1. Deterministic `expedient` from project folder name
**Evidence:** artifact 5 (Linyola `13/52/04` MISMATCH); pattern applies across all 7 projects (all use `reference-material/<7-digit-code> <name>/` convention).
**Fix:** in `automation/auto_extractor.py`, add a phase-0 step that parses the folder name's leading 7-digit code and emits a constant-source `expedient` signal with priority 1 (overrides all other candidates). ~15 LOC.
**Expected win:** Linyola `expedient` MISMATCH → MATCH. Guards any future project from the same regex trap. Global +0.5-1pp.
**Risk:** low. Deterministic; fails safely when folder name doesn't match the pattern.

### 2. Widen vision probe gate for text-extractable layout-heavy PDFs
**Evidence:** artifact 1 (`1.0.pdf` skipped by probe → misclassified by classifier → architect_plan role left empty → Vilanova `architect_name` MISMATCH + `num_floors` / `superficie_*` NE). Likely applies to other projects' architect plan sheets that use `A.01.pdf`-style names in subfolders.
**Fix:** in `automation/concept_scout/vision_probe.py:probe_unreadable_files`, change the gate from `not text_extractable` to `not text_extractable OR (text_extractable AND fe.concepts_detected == [])`. If the text aggregator found zero concepts, force vision.
**Expected win:** Vilanova recovers 1-3 MATCHes (architect_name + possibly num_floors/superficie). Modest cost (~$0.05 extra OpenAI vision per sweep). Global +1-2pp.
**Risk:** low-medium. Increases probe budget by ~10-15 more probes per project. Cap at `MAX_VISION_CALLS_PER_RUN` already protects from runaway.

### 3. Tighten `expedient` regex with context label
**Evidence:** artifact 5 (all 6 competing signals returned `13/52/04` — no context requirement means any slash-number matches).
**Fix:** in `automation/fileminer/miners/_detection.py`, change the expedient pattern to require `(?i)(?:expedient|expediente|exp\.?|ref\.?|n[úu]mero)` within 20 chars of the slash-number. Fallback to unlabeled pattern only if no labeled match exists and emit at lower confidence (0.5).
**Expected win:** redundant with knob #1 after that ships, BUT provides defense-in-depth and helps projects where the folder-name fix can't apply.
**Risk:** low. Regex change, no new dependencies.

### 4. Probe prompt: add abstention clause + map-subject scoping
**Evidence:** artifact 3 (municipality=Alpicat at 0.8 conf — wrong; neighbor town picked up from map frame). Artifact 4 shows the probe CAN abstain (province=empty at 0.0 conf) — just doesn't always.
**Fix:** in `automation/concept_scout/vision_probe._PROBE_PROMPT`, add:
> "For document_type='map': identify ONLY the municipality/province that is the SUBJECT of the map (marked with highlighted polygon, legend marker, or a label near the image center). Do NOT return neighboring towns visible at frame edges. If you cannot distinguish, return concepts_found=[] — prefer abstention over guessing."
**Expected win:** no direct MATCH→MISMATCH flips today (priority math saves us), but prevents regressions when we extend `_VISION_DETECTABLE_CONCEPTS` (planned for Phase B probe extensions). Insurance, not offense.
**Risk:** very low. Prompt change only.

### 5. MsgMiner content-hash dedup
**Evidence:** artifact 5 (3 physical copies of `2_02B_DG_Silvia_Jaume.pdf`; every copy probed / classified / mined separately). Observed by counting `deep_folder_files` entries matching file stems across the 7 projects.
**Fix:** in `automation/fileminer/miners/msg_miner.py`, compute content hash before saving each attachment; if a file with the same hash already exists in the project tree, **skip extraction** (record the duplicate in provenance). Keep only one physical copy per unique content hash.
**Expected win:** ~20-30% reduction in LLM calls per sweep (savings ~$0.50-1 per full 7-project run). No accuracy change expected. Frees up vision cap for new files instead of duplicates.
**Risk:** low-medium. Must preserve the msg→attachment provenance chain — provenance entry should say "extracted from msg X, deduplicated against file Y".

---

## Data gaps encountered (what's NOT persisted today)

From filling in the template, these were the fields I had to mark `not persisted` or infer. Ordered by how often they bit me:

| Gap | Artifacts bit | Blocks analysis? | Fix cost |
|---|---|---|---|
| **Vision extractor output `source_file = null`** in `validation/{planol,sondeig,dpsh,projecte}_extracted.json` | 2, 5 | Yes — for correct-classification cases, we can't see which of the file's signals won. Workaround: cross-reference by role assignment. | ~5 LOC per extractor (4-5 lines total) — write `_metadata.source_file` into the output blob |
| **Groq LLM call prompt + raw response not persisted** — we only see the parsed Signal | 1 | Partially — we know "Groq said X", we don't know "Groq was asked Y and responded Z". Matters for prompt-tuning. | Medium — requires adding a raw-response log file per sweep |
| **ConceptScout "why skipped" reason not logged** in `FileEntry.notes` — blank `notes` could mean "probed and found nothing" or "skipped by gate" | 1, 5 | Minor — can infer from text_extractable + file type, but explicit reason would be cleaner | ~10 LOC — add one-line reason when `probe_unreadable_files` filters a file |
| **MiningResult.signals only exist in-memory** during `auto_extract`; not persisted per project | All | No — the diagnostic's `variables[].signals[]` captures most of them post-hoc | ~5 LOC — dump `mining_result.signals` to `validation/mining_signals.json` at end of phase 0.3/0.4 |
| **No "winner" marker on signals** in diagnostic JSON — have to infer by comparing `pipeline_value` to each signal's `value` | 1, 5 | Minor — inference is reliable, just tedious | ~5 LOC — add `is_winner: bool` during per-project snapshot serialization |
| **Signal entries missing when winner has `source_file = null`** — if vision_planol wins with null source_file, the competition trace has only losing candidates | 2, 5 | Yes — obscures the analysis | Subsumed by the `source_file` backlink fix above |

**Verdict:** the `source_file` backlink for vision extractors is the single highest-value persistence hook. Everything else is "nice to have" — the manual pass was feasible without them, just more cross-referencing required. **Recommend implementing only the source_file fix as a follow-up; defer the rest.**

---

## Methodology gaps (9-field template revisions)

Where the template was ambiguous or hard to fill during the manual pass:

1. **"expected" for skipped stages is circular.** Saying "expected: SKIPPED" provides no validation criterion. **Proposed:** add a `gate_condition` sub-field that explicitly names the boolean predicate the stage checked (e.g., *"text_extractable == True AND file_type in {pdf_vector}"*). That way "actual: skipped" is meaningful only if the gate_condition matches reality.

2. **"replay" often references non-existent commands** — the `scripts/replay_stage.py` CLI is a future plan, so replay lines like `scripts/replay_stage.py probe --file ...` are aspirational. **Proposed:** prefix with `(planned)` when the command doesn't exist today; use a concrete Python one-liner as the actionable fallback.

3. **"knobs" list tends to sprawl** — artifact 1's stage 0.4 lists 6 knobs. Hard to rank. **Proposed:** add a `primary_knob` field that names the ONE knob most worth trying first, separate from the full `knobs` list.

4. **No field for "related files / duplicates / alternatives"** — artifact 5 has 3 physical copies and 10+ mined_images of the same content; the template treats them as 1. **Proposed:** add `related_files: [rel_path, ...]` at the artifact-header level, listing duplicates or related copies.

5. **Downstream impact table confuses two different questions.** "MATCH" sometimes means "the file's signal was correct AND won" (artifact 2 building_type), sometimes "the file's signal was irrelevant but something else produced MATCH" (artifact 3 municipality where comanda Excel won). **Proposed:** split into two columns: `value_correct?` (was this file's extraction right?) and `signal_won?` (did it beat competition?). Four combinations tell different stories — we lose nuance by collapsing them.

6. **"Downstream impact" is artifact-only; doesn't surface cross-artifact patterns.** The README had to synthesize this manually. **Proposed:** add a template field `primary_failure_class` (from a fixed list: `misclassification`, `extraction_failure`, `extraction_wrong_value`, `priority_inversion`, `synthesis_style_mismatch`, `no_failure`) to make cross-artifact aggregation mechanical.

7. **No time-dimension field.** The pipeline re-runs over days produce different results (vision non-determinism on sondeig PDFs is flagged elsewhere). The template captures a single snapshot. **Proposed:** add `observed_in_runs: [diagnostic_run_id, ...]` to let us track whether a failure is stable or flickers.

**Verdict:** the template is functional but blunt. The biggest concrete improvement is #5 (split the downstream impact table) — that alone would have saved me ~10 minutes per artifact. Proposed revisions #3, #4, #6, #7 are smaller wins.

---

## Is the methodology worth automating?

Original question from the plan:

> *"If most of the value was in the hypothesis + knob-tweak naming and the raw data reading was mechanical, that's a strong case for CLI+slash commands; if most of the value was in the investigative reasoning that a human did, the case is weaker."*

My observation from doing this pass:

- **Raw data reading:** ~40% of the time per artifact. Mechanical. Automation would save real hours.
- **Cross-referencing between artifacts (e.g., "did F1 SIT's `municipality=Alpicat` win or lose?"):** ~20% of the time. Also mechanical; a `DownstreamImpact` query is a straight SQL-like join.
- **Hypothesis + knob naming:** ~30% of the time. Requires *judgment* — which stage to blame, which knob to try first. **LLM can assist** (given the structured data), but the quality ceiling depends on how well we encode domain knowledge (Eva's conventions, pipeline architecture). Automation here is partial.
- **Cross-artifact pattern synthesis:** ~10% of the time. This IS valuable and currently manual. An LLM with all 5 structured outputs could produce a README like this one.

**Recommendation:** a tooling follow-up is justified, but scoped to **automate the first two** (raw data reading + cross-referencing) and **assist** the last two (hypothesis + synthesis) rather than replace them. That's roughly what the plan's "sketch" proposed (library + CLI + Claude-narrated slash commands).

Before building tooling, though, **at minimum fix the `source_file` backlink for vision extractors** (data gap #1 above). Without that, artifact-centric analysis is incomplete for exactly the cases where classification went right — which is the case you most want to study to reproduce success.

---

## Sampling bias + next steps

This pass chose 5 artifacts for *breadth of failure modes*, not for *representativeness*. The real 2026-04-19 sweep has:
- ~50 deep-folder files across 7 projects
- ~200 variables × 7 projects = 1400 variable-project cells in the accuracy matrix
- 79 MISMATCHes + 47 NEs in the post-fix run

The 5 files here cover **2 explicit MISMATCHes** (artifact 1's architect_name, artifact 5's expedient) and **3 control/success cases** (artifacts 2, 3, 4). To move the numbers systematically, the next pass should:
1. **Rank MISMATCHes by downstream damage** (how many variables per file) and inspect the top 5-10.
2. **Extend to variable-centric inspection**: pick the top 5 MISMATCH *variables* (e.g., `architect_name` MISMATCH on 4 projects) and trace each instance back to source files. This often points at the same failure class from a different angle.
3. **Ship the top 2-3 knobs from this document** (expedient folder-name, probe gate widening, expedient regex tightening) and re-sweep to confirm numeric lift.

End of README.
