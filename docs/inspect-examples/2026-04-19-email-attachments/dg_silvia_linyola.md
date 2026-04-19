# Artifact: `validation/msg_attachments/RV_ pressupost geotècnic/2_02B_DG_Silvia_Jaume.pdf` (Linyola)

**Original copy (in project subfolder, gets the role):** `25.0616/2_02B_DG_Silvia_Jaume.pdf` — the *same file content* stored twice. FileScanner finds the 25.0616/ copy via filename pattern; MsgMiner also extracts a copy out of the `.msg`; deep-folder classifier sees the extracted copy as a duplicate candidate.
**Type:** `pdf_vector` | **Size:** 6.6 MB (large — multi-page architect project) | **Text extractable:** ✓
**Why we're looking at this:** a case where **classification is correct but doesn't help** because the role is already filled by a twin. Also surfaces that FileMiner's regex-based `expedient` extraction picked up a wrong-but-plausible value ("13/52/04") from the title block of the architect project PDF, which won competition against many other candidates — a real MISMATCH that dragged Linyola's score.

---

## Journey

### Stage 0.0 — FileScanner
- **goal:** assign role by filename match.
- **config:** `ROLE_PATTERNS["architect_project"]` includes `^(?:.*[_\s/])?DG[_\s.].*\.pdf$` (i.e. files with "DG_" prefix in the name).
- **expected:** the in-project copy `25.0616/2_02B_DG_Silvia_Jaume.pdf` matches the DG pattern → assigned to `architect_project` role. The MsgMiner copy at `validation/msg_attachments/.../2_02B_DG_Silvia_Jaume.pdf` would *also* match the pattern, but FileScanner doesn't walk into `validation/` — only the in-project copy reaches this stage.
- **actual:** `file_mapping.roles.architect_project = {path: "25.0616/2_02B_DG_Silvia_Jaume.pdf", detection: "filename_pattern"}`.
- **deviation:** met expectation.
- **knobs:** n/a — DG pattern is doing its job.
- **hypothesis:** n/a.

### Stage 0.3 — MsgMiner extraction
- **goal:** extract .msg attachments.
- **actual:** the same DG file is in **two** emails (`RV_ pressupost geotècnic.msg` and `pressupost geotècnic.msg`, resent thread). MsgMiner extracts it **twice**, once per email:
  - `validation/msg_attachments/RV_ pressupost geotècnic/2_02B_DG_Silvia_Jaume.pdf`
  - `validation/msg_attachments/pressupost geotècnic/2_02B_DG_Silvia_Jaume.pdf`
  Plus the original at `25.0616/2_02B_DG_Silvia_Jaume.pdf`. **Three physical copies** of the same byte content in the project tree.
- **deviation:** met expectation functionally, but redundancy is significant: every downstream stage processes all three copies.
- **knobs:** (1) **dedupe by content hash before promoting** — MsgMiner could compute a content hash per extraction; if the hash matches an existing file in the project, skip extraction. (2) **deep-folder classifier could dedupe** — if we see two files with identical hashes, mark one as `duplicate_of` the other and skip re-processing. Neither is implemented today.
- **hypothesis:** duplication doesn't currently cause downstream harm (the original copy wins competition, duplicates redundantly agree), but it multiplies LLM calls: every copy gets probed, mined, and classified. With the vision cap, this can crowd out genuinely-new files. Vilanova's vision cap was reached partly because ~30% of deep-folder classifier inputs were duplicates.

### Stage 0.3 — FileMiner text mining (PDF text miner)
- **goal:** regex-extract labeled fields from PDF text.
- **expected:** the architect project PDF has a proper title block with labeled fields. Signals for `expedient`, `client_*`, `contact_name`, `field_date`.
- **actual:** `concept_map.file_inventory` for this file shows `concepts_detected=['client_phone', 'client_email', 'contact_name', 'field_date', 'expedient']` — FileMiner text miner extracted 5 concepts. Signal values (from `concept_sources`):
  - `client_phone`: `"973157519"` via regex (confidence 0.75)
  - `client_email`: `"info@bunyesc.com"` via regex (confidence 0.75)
  - `contact_name`: `"info@bunyesc.com - www.bunyesc.com"` via `label_value` (confidence ~0.8)
  - `field_date`: (captured, value not inspected)
  - `expedient`: matched `"13/52/04"` via regex — **this is the file's downstream-damaging signal**
- **deviation:**
  - `client_phone`, `client_email` extracted from the **architect's** contact details (Bunyesc is the architect firm), not the client's. The pipeline may conflate these.
  - `contact_name = "info@bunyesc.com - www.bunyesc.com"` is a parsing artifact — the label was matched but the "value" captured included the URL.
  - `expedient = "13/52/04"` is a **wrong-but-plausible match**. Eva's expedient is `4001607` (the G3DT internal code, visible in filename `4001607_informe.doc` for example). `13/52/04` looks like a visa/project reference from Bunyesc's title block (architect's internal project code). The regex pattern `\d+/\d+/\d+` matched this and fed it into the pipeline.
- **knobs:** (1) **tighten the `expedient` regex** — require a context label nearby: `(?i)(?:expedient|expediente|exp\.?|ref\.?)\s*[:\-]?\s*(\S+)` instead of any slash-number pattern; (2) **priority by source_file type** — signals from `architect_project` files should have lower priority for `expedient` than signals from `DADES PER ANAR A CAMP.xlsx` or the G3DT email header (where the true expedient is written); (3) **source-sheet precedence** — label_value extractions whose value contains a URL should be filtered out (URLs aren't contact names).
- **hypothesis:** the PDF text extraction is structurally working — it's finding labeled fields and running regex patterns. The issue is that **the patterns are too lax** for variables that have a strong source elsewhere. `expedient` has a canonical source (the G3DT-internal filename or the comanda-lab Excel's header); permitting the architect's project code to win competition is a **priority-chain bug**, not an extraction bug.

### Stage 0.4 — GroqMiner
- **expected:** might run on this file since FileMiner already got 5+ signals (>=3, so maybe SKIPPED?). Groq is gated on `<3 mapped signals`.
- **actual:** not immediately clear from diagnostic data. No signals in `variables[].signals[]` with `source_file == this file` AND `component == "groq_llm"` — so Groq either didn't run or its signals lost and weren't serialized.
- **deviation:** behavior consistent with the gate (file had enough signals → Groq skipped).
- **knobs:** the gate is reasonable but arbitrary. (1) **target-concept gating** — run Groq specifically for concepts that have no signal yet, not based on total signal count; (2) **always-run for high-value concepts** — `expedient` and `architect_name` are critical; running Groq unconditionally for them might surface stronger candidates than FileMiner's regex.

### Stage 0.45 — ConceptScout vision probe
- **expected:** SKIPPED — this file is `text_extractable=True` (pdf_vector).
- **actual:** skipped. `concept_probes/078738066180.json` does not exist (md5 hash for this file).
- **deviation:** met expectation.
- **note:** like artifact 1 (`1.0.pdf`), we miss the chance to see the vision probe's opinion. For an architect project PDF, the probe would likely return `document_type: architect_project` (a category the probe DOES know about), validating the filename-based classification downstream. Not a bug here (filename pattern worked), but the gap remains for files without filename hints.

### Stage 0.46 — Deep folder classifier
- **goal:** classify the `validation/msg_attachments/.../2_02B_DG_Silvia_Jaume.pdf` copy.
- **config:** 4-layer classifier.
- **expected:** Layer 1 (filename) matches DG pattern → classify as `architect_project` candidate. Role already filled by the original copy → record as candidate (not promote).
- **actual:** `deep_folder_files["validation/msg_attachments/RV_ pressupost geotècnic/2_02B_DG_Silvia_Jaume.pdf"]`:
  ```json
  {
    "source_origin": "msg:25.0616/RV_ pressupost geotècnic.msg",
    "classifier_used": "filename",
    "role_assigned": null,
    "role_candidate": "architect_project",
    "probe_status": "skipped",
    "probe_detail": "",
    "confidence": 0.9,
    "doc_type": null,
    "concepts_extracted": [],
    "signals_emitted": 0
  }
  ```
- **deviation:** met expectation. Conservative "role already filled" behavior preserved.
- **knobs:** **multi-file role support** (already implemented per commit `9f4064a` — `SmartScan multi-file role support`, `role_files`) — the deep-folder classifier could promote this as a *secondary* source for `architect_project`, which would let Phase 1 vision extractor consult both copies. Since they're identical byte-wise, this offers no new info. BUT for projects where email attachments contain **different** content than the original (e.g., a newer revision), multi-file role support would help. Needs testing on a project where the msg copy differs.
- **hypothesis:** n/a — classifier is doing the right thing; the limitation is the upstream de-dup issue (stage 0.3 MsgMiner).

### Stage 0.47 — Re-mine promoted
- **expected:** n/a — not promoted.
- **actual:** skipped.

### Stage 1 — Vision extractor (vision_projecte)
- **goal:** for the `architect_project` role → run `projecte_arquitecte` vision extractor on the ORIGINAL copy (not this msg copy).
- **config:** per `VISION_BACKEND_BY_TYPE["projecte_arquitecte"] = "openai"` → OpenAI `gpt-4.1` (multi-page prompt via `PROJECTE_EXTRACTION_PROMPT`).
- **expected:** extract architect, promotor, dimensions, areas from the title block of the project PDF.
- **actual:** `validation/projecte_extracted.json` populated (not inspected in full here). Source: pipeline_value `architect_name = "JOSEP BUNYESC PALACIN"` with `source = "planol None"` → the vision_planol extractor (not vision_projecte!) set architect_name. Unclear which file the planol extractor ran on — the `architect_plan` role is assigned to `25.0616/Punts de Sondeig_Silvia_Jaume.pdf`.
- **deviation:** architect_name MISMATCH: pipeline says Josep Bunyesc (the architect who designed the *house*); Eva says Sílvia Eroles Balagueró (who is the CLIENT acting as her own architect). This is a **domain-knowledge gap**, not an extraction gap — both names appear in the document, both have architect-like roles, Eva's reporting convention chose the owner-architect.
- **knobs:** (1) **vision prompt disambiguation** — `PLANOL_EXTRACTION_PROMPT` could instruct: "if the project owner and the plan signer are different, return BOTH; mark the owner as `architect_of_record` and the signer as `architect_of_plan`"; (2) **accept both as valid** — the judge could treat "Bunyesc" AND "Eroles Balagueró" as both valid candidates for `architect_name` when both appear in the document. Today the judge is strict on exact person identity.
- **hypothesis:** this is a gray-area failure — the vision extraction found a reasonable architect name (Bunyesc IS an architect and IS named in the PDF), but not the one Eva uses. A stronger prompt asking for the owner's name specifically would fix it, but the underlying rule ("owner-architect wins over designer-architect when they differ") is a business convention, not a vision-quality problem.

### Stage Synthesis
- `client_name` synthesis output: `"SRA. SÍLVIA EROLES BALAGUERÓ JAUME NADAL ANDREU"` (two people's names concatenated, source `planol None`). Eva has `"SRA. SÍLVIA EROLES BALAGUERÓ"` (one person). → **MISMATCH** from synthesis concatenating both owners of the parcel.
- `architect_name`: **MISMATCH** as discussed above.
- **knobs:** synthesis prompt could say "for `client_name`, if multiple people are listed as owners, use only the primary one or list them with explicit separator". Today it joined them without separator.

### Stage Competition
- `expedient`: 6 signals competing. All values are `"13/52/04"` (wrong). **They all came from files where the architect's project code `13/52/04` appears in the title block** (DG PDF original + duplicates, Punts de Sondeig PDF + copies). The *correct* expedient `4001607` was NEVER extracted — it's in the G3DT internal filename `4001607_informe.doc` but the regex couldn't see filenames, only file contents.
- **deviation:** competition worked (consistent result from 6 sources), but it's the WRONG consistent result. **This is a textbook "garbage in, garbage out" — competition can only choose from submitted candidates; if no source submits the correct value, competition is powerless.**
- **knobs:** (1) **filename-based expedient miner** — add a dedicated extractor that pulls the numeric expedient code from project filenames (patterns `^\d{7}_.*\.doc[x]?$`, `^\d{4}\.\d{4}$`, etc.); (2) **G3DT project folder name miner** — the folder `reference-material/4001607 LINYOLA/` already contains the expedient; extract it deterministically as a constant-priority signal.

### Stage Judge
- `expedient`: MISMATCH (Eva `"4001607"`, pipe `"13/52/04"` — correctly called wrong).
- `architect_name`: MISMATCH (two different people; correct verdict).
- `client_name`: MISMATCH (concatenation vs. single person; correct verdict).

---

## Downstream Impact

| Variable | Final status | Eva | Pipeline | This file's contribution |
|---|---|---|---|---|
| `expedient` | **MISMATCH** | `4001607` | `13/52/04` | Redundant wrong signal (rank 6) — agreed with the original copy's wrong answer |
| `architect_name` | **MISMATCH** | `SÍLVIA EROLES BALAGUERÓ` | `JOSEP BUNYESC PALACIN` | Indirect — the DG file's title block likely influenced the vision extractor's pick |
| `client_name` | **MISMATCH** | `SRA. SÍLVIA EROLES BALAGUERÓ` | `SRA. SÍLVIA EROLES BALAGUERÓ JAUME NADAL ANDREU` | FileMiner pulled "Dades Clienta:" labels from adjacent msg files |
| `client_phone`, `client_email`, `contact_name` | (not checked in detail — likely CLOSE/MISMATCH for contact being the architect's, not client's) | — | — | extracted from this file but represent the architect's info |

**Net impact:** this file **does** contribute to 2-3 MISMATCHes indirectly. The damage is diffused across multiple variables (`expedient` especially). The *direct* extractions (client_phone, client_email) pulled the architect firm's contact info instead of the client's — another domain-knowledge failure.

---

## Hypothesis — which stage to blame

For the **expedient** MISMATCH: **stage 0.3 FileMiner's `expedient` regex is too permissive.** Six files all matched a slash-number pattern that has nothing to do with the G3DT internal expedient number. The correct expedient lives in the folder name and G3DT filename pattern, not in any document's text — so the solution isn't to extract better, it's to **change the source**: read the expedient from the folder name as a deterministic constant, and give it priority 1 (overriding all other candidates).

For the **architect_name** MISMATCH: **stage 1 vision's PLANOL_EXTRACTION_PROMPT doesn't encode the "owner-architect wins over designer-architect" convention.** This is a domain-knowledge problem — fixing it requires either a prompt rule (explicit) or a cross-source tiebreaker ("the architect_name should match the client_name's surname if possible"). Both options are cheap to try.

For the **client_name** concatenation: **stage Synthesis is gluing two names together without a separator.** This looks like a prompt bug — the synthesis prompt examples don't show how to handle multi-owner parcels.

## Recommended knob (highest leverage)

**Promote the expedient to a filename-derived constant.** Linyola's G3DT expedient `4001607` is visible in:
- the project folder name (`reference-material/4001607 LINYOLA/`)
- multiple filenames (`4001607_informe.doc`, `4001607_DPSH.xls`, `comanda laboratori_4001607_LINYOLA.xls`)

A deterministic extractor that reads the folder name's leading 7-digit code and emits an `expedient` signal with source `constant` (priority 1, beats everything) would fix this MISMATCH — across **all 7 projects** that use this naming convention, not just Linyola. Implementation: ~15 LOC in `auto_extractor.py` (compute once at pipeline start, inject as a high-priority signal).

**Secondary knob:** fix the `expedient` regex in FileMiner's PDF text miner to require a context label (`expediente`, `expedient`, `exp.`). This avoids false matches on unrelated slash-number patterns like visa codes. Lower priority now that the constant-source fix would dominate anyway.

**Structural knob (separate workstream):** MsgMiner dedup by content hash before storing. Three identical copies of `2_02B_DG_Silvia_Jaume.pdf` in the project tree is waste — every probe, every extraction multiplied. Costs ~10-20% extra on pipeline runs with heavy email attachment redundancy.

The architect_name / client_name MISMATCHes are domain-knowledge issues that prompt tuning could address; defer to a separate workstream after the expedient fix.
