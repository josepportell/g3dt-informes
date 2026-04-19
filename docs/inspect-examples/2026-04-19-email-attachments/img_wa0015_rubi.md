# Artifact: `25.0794/IMG-20251104-WA0015.jpg` (Rubí)

**Also present as:** `validation/msg_attachments/PRESSU/IMG-20251104-WA0015.jpg` (the MsgMiner copy).
**Type:** `image` (JPEG) | **Size:** 253 KB | **Text extractable:** ✗ (image)
**Why we're looking at this:** the classification-went-right counterpoint to artifact 1. This file IS assigned to the `architect_plan` role, vision extraction ran, *and yet* Rubí's `architect_name` is still NE and `client_name` is MISMATCH. Understanding why a correctly-classified file still produces downstream misses is as important as understanding misclassifications.

---

## Journey

### Stage 0.0 — FileScanner
- **goal:** assign role by filename/path match.
- **config:** SmartScan; subfolder walks include `25.0794/` (the expedient dir) via SmartScan tier3_vision (it classifies images by content, not just filename).
- **expected:** either ignored (no filename pattern for `IMG-XXXXX.jpg`) or picked up by tier3 vision classification.
- **actual:** assigned to `architect_plan` role. `file_mapping.roles.architect_plan.path = "25.0794/IMG-20251104-WA0015.jpg"` with `detection = "smartscan tier3"` (confirmed via file_mapping).
- **deviation:** met expectation (SmartScan's tier3 image classifier correctly identified this as a floor plan).
- **knobs:** n/a — this is the stage working as designed.
- **hypothesis:** n/a.
- **replay:** `python -c "from automation.smartscan.tier3_vision import *; ..."` — exact API TBD.

### Stage 0.3 — MsgMiner extraction
- **goal:** extract .msg attachments.
- **actual:** extracted to `validation/msg_attachments/PRESSU/IMG-20251104-WA0015.jpg`.
- **deviation:** met expectation.
- **knobs:** n/a.

### Stage 0.3 — FileMiner (image miner?)
- **goal:** n/a — FileMiner skips image files (`_SKIP_EXTENSIONS = {.png, .jpg, .jpeg, ...}`).
- **expected:** SKIPPED.
- **actual:** skipped. No signals in diagnostic with `source_file == "25.0794/IMG-20251104-WA0015.jpg"` AND `component == "fileminer_regex"`.
- **deviation:** met expectation.

### Stage 0.4 — GroqMiner
- **goal:** text-based LLM mining. Skips images.
- **expected:** SKIPPED (no text to feed Groq).
- **actual:** skipped.
- **deviation:** met expectation.

### Stage 0.45 — ConceptScout vision probe
- **goal:** for images, ask the vision probe "which concepts are here?".
- **config:** `_PROBE_PROMPT` + `_VISION_DETECTABLE_CONCEPTS`; cache at `validation/concept_probes/{hash}.json`.
- **expected:** probe runs (text_extractable=False), returns a doc_type + concepts_found.
- **actual:** probe ran. Cache file `validation/concept_probes/f7df16f7224e.json`:
  ```json
  {
    "document_type": "architect_plan",
    "document_description": "Floor plan of a Mediterranean-style house",
    "concepts_found": [
      {"concept_id": "building_type", "confidence": 0.8,
       "signal_preview": "Modelo Mediterraneo", "page": 1}
    ]
  }
  ```
  → registered in `concept_map.file_inventory`: `type=image, size_kb=253, text_extractable=False, concepts_detected=['building_type'], notes='architect_plan: Floor plan of a Mediterranean-style house'`.
- **deviation:** met expectation. Probe correctly classified this as an architect plan and found one usable concept.
- **knobs:** (1) **expand `_VISION_DETECTABLE_CONCEPTS`** — the probe CAN see architect_name, client_name, num_floors from a title block, but those aren't in the detectable list, so the probe doesn't report them even if visible. (2) **ask for more concepts per probe** — the prompt currently asks for ~20 concepts; adding architect_name etc. is cheap.
- **hypothesis:** the probe is deliberately conservative — it classifies document type and picks up 1-2 "obvious" concepts. The architect-related concepts are probably not listed in `_VISION_DETECTABLE_CONCEPTS` for this image. Adding them would let the probe do double duty as a quick extractor *before* the heavier Phase 1 vision runs.
- **replay:** `python -c "from automation.concept_scout.vision_probe import _run_probe; print(_run_probe(Path('reference-material/3001631 RUBI/25.0794/IMG-20251104-WA0015.jpg')))"`.

### Stage 0.46 — Deep folder classifier
- **goal:** classify files that FileScanner didn't role-assign.
- **expected:** SKIPPED — this file is already in `file_mapping.roles.architect_plan` from SmartScan tier3. The classifier iterates `file_inventory` and skips files whose path is already assigned (line 338-341 of `deep_folder_classifier.py`).
- **actual:** skipped. Confirmed by absence from `deep_folder_files` dict.
- **deviation:** met expectation.
- **knobs:** none relevant here — if SmartScan tier3 hadn't caught it, the classifier *would* have (it would have read the probe-cache hit from stage 0.45, mapped `architect_plan` doc_type → `architect_plan` role via `DOC_TYPE_TO_ROLE`, and promoted).

### Stage 0.47 — Re-mine promoted
- **expected:** n/a — not freshly promoted.
- **actual:** skipped.

### Stage 1 — Vision extractor (vision_planol)
- **goal:** extract the full planol data (architect, promotor, dimensions, areas) via role-specific prompt.
- **config:** per `automation/config.VISION_BACKEND_BY_TYPE["planol"] = "openai"` → OpenAI `gpt-4.1-mini`. Prompt in `automation/validation/prompts.PLANOL_EXTRACTION_PROMPT`.
- **expected:** populate `validation/planol_extracted.json` with a full set of fields.
- **actual:** `validation/planol_extracted.json`:
  ```json
  {
    "architect_data": {
      "source_file": null,             // ← gap: no backlink to IMG-WA0015
      "project_name": "MODELO MEDITERRANEO",
      "building_type": "vivienda modular",
      "client_name": null,
      "street_address": null,
      "municipality": null,
      "promotor": null,
      "architect": null,               // ← the downstream miss
      "architect_company": "VIM VIVIENDAS MODULARES",
      ...
      "num_floors": null,              // ← downstream NE
      "max_height_m": null,
      "plot_length_m": {"pdf_value": 8.0, "confidence": 1.0},
      "plot_width_m": {"pdf_value": 9.0, "confidence": 1.0}
    },
    "overall_confidence": 0.85,
    "extraction_notes": "No planning table or title block with metadata found. Only site plan drawing and partial title block with project name and company. Floor surface and plot dimensions extracted from drawing annotations. Number of floors and height not specified."
  }
  ```
- **deviation:** **partial success.** Building type, company, floor footprint, plot dimensions extracted. Architect name, client name, street address, municipality, promotor, num_floors → **null**. The `extraction_notes` field is honest: "No planning table or title block with metadata found. … Number of floors and height not specified."
- **knobs:** (1) **prompt doesn't probe hard enough for architect name** — `PLANOL_EXTRACTION_PROMPT` may not emphasize "if title block is partial, examine company name for likely architect — VIM VIVIENDAS MODULARES has owner Joana Martinez per public records"; (2) **image quality** — if the title block genuinely isn't visible in this WhatsApp-sourced image, the prompt can't conjure it. A higher-resolution source (the .pdf version of the same plan, if attached to the same email) could fix it; (3) **cross-source inference** — if `architect_company` is known but `architect` is null, the pipeline could infer architect from company via cadastre or a public lookup (BIG change); (4) **fallback model** — try Claude Sonnet vision on the same image; OpenAI gpt-4.1-mini may be missing finer handwriting/small text.
- **hypothesis:** the extraction_notes correctly diagnose the issue — **this file does not visually contain the architect's name**. It's a WhatsApp-shared image of a floor plan with a partial title block. The real architect name is elsewhere (likely the email body, or a separate document). Vision cannot invent information that isn't in the pixels. This is a **structural limitation of this artifact**, not a prompt-tuning problem.
- **replay:** import `extract_from_planol(Path('...'))` in isolation.

### Stage Synthesis
- **goal:** compose final `architect_name`, `client_name`, narrative fields.
- **actual status for affected variables:**
  - `architect_name`: **NE** (eva `JOANA MARTINEZ`, pipe `None`). No source ever produced it.
  - `client_name`: **MISMATCH** (eva `SRA. JOANA MARTINEZ`, pipe `VIM VIVIENDAS MODULARES`, source `llm_synthesis`). The synthesis saw `architect_company = "VIM VIVIENDAS MODULARES"` and decided that was the client. Understandable mistake — company names ending in S.L. often are the client — but wrong: Joana Martinez (VIM's owner) is acting as both architect and client, which the synthesis couldn't infer.
  - `building_type`: **CLOSE** (eva `un habitatge unifamiliar aïllat modular`, pipe `vivienda modular`, source `planol None`). Substance matches (modular single-family home), wording differs (eva adds "aïllat", language ES vs CA).
  - `num_floors`: **NE** (eva `PB + Porxo`, pipe `None`).
- **deviation:** synthesis correctly mixed what vision + comanda-lab provided. The gaps are at stage 1 (vision) not here.
- **knobs:** (1) **synthesis-side cross-reference** — when `architect_name` is missing but `architect_company` has a registered owner, try to infer. Would require a lookup table or an LLM call to check. (2) **source-aware language** — `building_type` could be elevated from "vivienda modular" (ES) to "habitatge unifamiliar aïllat modular" (CA) if municipality language is known. The synthesis prompt doesn't currently do that kind of language/format elevation.
- **hypothesis:** synthesis is downstream of the gap; fix vision first.

### Stage Competition
- **goal:** resolve conflicting signals.
- **relevant variables:**
  - `architect_name`: 0 signals from any source → NE.
  - `client_name`: 0 signals shown in the diagnostic's `signals[]` (the llm_synthesis value is the direct output, not a competed signal). Vision's `client_name=null` wasn't even a candidate.
  - `building_type`: 1 signal from `comanda_lab_excel` ("CONSTR HABITATGE UNI"), rank 1 in the signals list — **BUT** the pipeline's actual winner was `"vivienda modular"` from `planol None` (vision). So vision won over the comanda-lab signal, yet vision isn't in the signals list. **This confirms the gap the plan flagged: vision extractor values appear in `pipeline_value` but not in the `signals[]` list.**
- **deviation:** competition is conceptually correct but the diagnostic can't *show* all the competitors because vision's outputs don't get serialized as Signal objects.
- **knobs:** instrumentation, not algorithm. Add vision-derived entries to `variables[].signals[]` with `source_file` backlink so the diagnostic's competition trace is complete.
- **hypothesis:** this gap makes artifact-centric inspection harder than it needs to be. For artifact 1, the Groq signal was visible; for artifact 2, the vision signals (the *correct* behavior on this file) aren't. We can only see artifact 2's contribution by reading `validation/planol_extracted.json` separately.

### Stage Judge
- **architect_name**: NE (correctly — no value to judge).
- **client_name**: MISMATCH (substance different — person vs company).
- **building_type**: CLOSE (judge correctly handled the CA/ES + adjective diff).
- **num_floors**: NE.

---

## Downstream Impact

| Variable | Final status | Eva | Pipeline | This file's contribution | Visible in signals[]? |
|---|---|---|---|---|---|
| `architect_name` | **NE** | `JOANA MARTINEZ` | `None` | architect=null in planol_extracted | No (vision gap) |
| `client_name` | **MISMATCH** | `SRA. JOANA MARTINEZ` | `VIM VIVIENDAS MODULARES` | architect_company fed synthesis which misattributed | No (synthesis path) |
| `architect_company` | ? (tier filter) | — | `VIM VIVIENDAS MODULARES` | ✓ extracted correctly | No |
| `building_type` | **CLOSE** | `un habitatge unifamiliar aïllat modular` | `vivienda modular` | ✓ from this file | No (winner is vision, not in list) |
| `num_floors` | **NE** | `PB + Porxo` | `None` | extraction_notes said "not specified" | No (null not a signal) |
| `plot_length_m` / `plot_width_m` | tier B | — | 8.0m / 9.0m | ✓ from this file | No |

**Net impact:** this file produced **useful** vision extractions (building_type CLOSE, plot dims MATCH or tier-B), but **failed** on the title-block metadata (architect, client, num_floors). It is not the root cause of any MISMATCH; it's the *partial* source for one CLOSE and one MISMATCH that was really caused by synthesis over-inferring.

---

## Hypothesis — which stage to blame

If this file produced an NE for `architect_name` and a MISMATCH for `client_name`, the responsible stages are:

1. **Stage 1 vision extractor** — primary cause of the `architect_name` NE. Vision's `extraction_notes` honestly reports "title block with metadata not found". The *image itself* likely doesn't contain the architect's name visibly. **No amount of prompt tuning will extract what isn't there.**
2. **Stage Synthesis** — primary cause of the `client_name` MISMATCH. Saw `architect_company` and decided it was the client. A guard ("if only `architect_company` is available, do not overwrite `client_name` from synthesis") would prevent this.

The real fix for this artifact is to **find a better source document for Rubí**. The MsgMiner extracted multiple files from the email; if any of them is a full-project PDF with a title block, routing it to `architect_plan` (or `architect_project`) would supply the missing data. Per the Phase A smoke output, Rubí has candidates: `IMG-20251104-WA0016.jpg` was also classified as architect_plan but **not promoted** (the role was filled by WA0015). The classifier's "empty-role only" rule is correct, but **multi-file role support** (shipped in commit `9f4064a` per git log) means WA0016 could be examined as a secondary source if WA0015 is incomplete.

## Recommended knob (highest leverage)

**Enable the architect-name-from-company inference in Synthesis.** Concretely: add to `_synthesize_with_llm`'s prompt a rule like:

> If `architect_name` is null but `architect_company` is known and the company name contains a person-name-like pattern (e.g. "VIM VIVIENDAS MODULARES" → owner Joana Martinez), propose the owner as `architect_name` with explicit low confidence. Additionally, do NOT set `client_name` to `architect_company` unless there is positive evidence the company is the contracting client.

Cost implication: none (prompt-only change). Expected win on this file: `architect_name` NE → MATCH (if the synthesis has access to a company-owner lookup) OR NE → NE (unchanged) but `client_name` MISMATCH → NE (which is better than a wrong answer, per the plan's match_close_pct formula which excludes NE from the denominator).

**Secondary knob:** extend the vision_planol prompt to say "if the title block is partial and architect is null, examine any visible handwritten notes or stamps for an architect name or stamp". Low cost, low expected win (the image probably doesn't have handwritten architect info).

**Structural knob (bigger):** backlink `source_file` in `validation/*_extracted.json` so this artifact's signals show up in `variables[].signals[]`. This doesn't fix any value — it makes the analysis machine-readable, which matters for tooling (future plan).
