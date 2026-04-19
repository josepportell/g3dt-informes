# Artifact: `ANEXOS/OTROS/F1 SIT.png` (Vilanova de Segrià)

**Also present as:** only at this path.
**Type:** `image` (PNG, large) | **Size:** 1810 KB | **Text extractable:** ✗
**Why we're looking at this:** a classification that went **partially right and partially wrong** — correctly identified as a map, correctly assigned to the `figure_situation_map` role (figure-level, for the final report), but the probe's concept extraction on the map surfaced a **wrong municipality** ("Alpicat" instead of "Vilanova de Segrià"). The wrong extraction lost competition against higher-priority sources, so no harm reached the final report — but the *pattern* of probe picking the wrong town label off a map is worth understanding.

---

## Journey

### Stage 0.0 — FileScanner / SmartScan
- **goal:** assign role.
- **config:** SmartScan. The `ANEXOS/OTROS/` subdirectory is walked by SmartScan (SmartScan walks deeper than FileScanner). `figure_situation_map` is a well-known role for map images tagged "F1 SIT" or "SIT" in the filename.
- **expected:** assigned to `figure_situation_map` role (role is for report figure, not input data).
- **actual:** assigned. `file_mapping.roles.figure_situation_map.path = "ANEXOS/OTROS/F1 SIT.png"`.
- **deviation:** met expectation.
- **knobs:** n/a.
- **hypothesis:** n/a.
- **replay:** n/a.

### Stage 0.3 — FileMiner
- **expected:** skipped (image extension).
- **actual:** skipped.

### Stage 0.4 — GroqMiner
- **expected:** skipped (no text).
- **actual:** skipped.

### Stage 0.45 — ConceptScout vision probe
- **goal:** identify which report concepts are visible in this image.
- **config:** `_PROBE_PROMPT` with concept list including `municipality`, `province`; image is not text-extractable → probe runs.
- **expected:** `document_type: map` (correct — it's a situation map); `concepts_found: [municipality, province]` extracted from map labels.
- **actual:** probe ran and cached at `validation/concept_probes/0adba9cf38be.json`:
  ```json
  {
    "document_type": "map",
    "document_description": "Map showing study area",
    "concepts_found": [
      {"concept_id": "municipality", "confidence": 0.8, "signal_preview": "Alpicat", "page": 1},
      {"concept_id": "province",     "confidence": 0.8, "signal_preview": "Lleida",  "page": 1}
    ]
  }
  ```
- **deviation:** `municipality: Alpicat` is **wrong** — the actual municipality is Vilanova de Segrià. Alpicat is a neighboring town (~10 km away) whose name likely appears on the map's edge/region view. The probe picked up the first visible municipality label without understanding which one is the subject of the study. `province: Lleida` is correct.
- **knobs:** (1) **probe prompt** — current prompt doesn't say "identify THE subject of the map, not incidental labels"; add a rule: *"For maps: identify the municipality that is the CENTRAL FOCUS of the map (indicated by a marker, highlighted polygon, or largest label), not neighboring towns visible at the frame edges."*; (2) **bounding-box grounding** — ask the probe to return the location of the label on the image (x,y); post-process to prefer labels closer to the image center; (3) **confidence calibration** — the model reports 0.8 confidence for a wrong answer; calibration training on known-wrong examples would help, but that's a larger project; (4) **cross-source sanity check** — flag probe outputs that conflict with another source (cadastre, project filename). Vilanova's filename literally contains "VILANOVA DE SEGRIA" — a simple conflict check would catch this.
- **hypothesis:** the probe model reads the first prominent town label it sees on the map. For a regional situation map, that's often a neighbor town rather than the subject. The prompt doesn't tell the model to scope to the map's subject, so it defaults to "any municipality name visible = return it".
- **replay:** `python -c "from automation.concept_scout.vision_probe import _run_probe; from pathlib import Path; print(_run_probe(Path('reference-material/4001671 VILANOVA DE SEGRIA/ANEXOS/OTROS/F1 SIT.png')))"`.

### Stage 0.46 — Deep folder classifier
- **expected:** SKIPPED — already in `file_mapping.roles`.
- **actual:** skipped. Confirmed by absence from `deep_folder_files`.
- **deviation:** met expectation.
- **note:** if this file *hadn't* been pre-assigned, the deep-folder classifier would have seen the probe cache hit (`doc_type: map`) and applied `DOC_TYPE_DISAMBIGUATION["map"]["situation"] = "situation_plan"` — *not* `figure_situation_map`. The two roles are subtly different: `situation_plan` is the architect's ubication drawing (input); `figure_situation_map` is the geotechnical map figure (output). The disambiguation entry actually gets this case wrong; "situation" keyword routes to `situation_plan` in my deep-folder classifier, which would have been a misclassification here.

### Stage 0.47 — Re-mine promoted
- **expected:** n/a.

### Stage 1 — Vision extractor (role-specific)
- **goal:** `figure_situation_map` is a report-figure role; no vision extractor is registered for it (it's just copied into the final report DOCX).
- **config:** n/a.
- **expected:** SKIPPED (no vision_type mapping for figure_* roles — confirmed in `ROLE_DEFINITIONS`).
- **actual:** skipped.
- **deviation:** met expectation.
- **knobs:** n/a.

### Stage Synthesis + Competition + Judge
- `municipality`: The probe's wrong `"Alpicat"` signal appears in `concept_map.concept_sources["municipality"]` with `confidence=0.8, method=vision_probe:map`. **But** the diagnostic's `variables.municipality.signals[]` shows only 1 signal — the *winning* one, from `comanda laboratori_4001671_VILANOVA DE SEGRIÀ.xls` with value `"VILANOVA DE SEGRIÀ"`. The comanda-lab signal outranked the vision_probe signal (priority-based competition). **Result: MATCH.**
- `province`: not shown as a diagnostic variable in the sampled output — no downstream effect to trace, though the value was correct anyway.
- **deviation from expected:** none in the final report. The probe's wrong signal was correctly dominated.

---

## Downstream Impact

| Variable | Final status | Eva | Pipeline | This file's contribution | Visible in signals[]? |
|---|---|---|---|---|---|
| `municipality` | **MATCH** | `… VILANOVA DE SEGRIÀ` | `VILANOVA DE SEGRIÀ` | Wrong signal ("Alpicat") lost competition | Not directly (wrong signal isn't in competition trace in final diagnostic, only in concept_map) |
| `province` | — | — | (probably MATCH from cadastre) | Correct signal ("Lleida") | Not checked |

**Net impact:** **zero damage** in the final output. This is a "probe was wrong but priority math saved us" case. Important to understand because it tells us the vision probe's 0.8 confidence is not trustworthy enough to be the sole source, and *that's OK* because the priority chain explicitly de-prioritizes it.

---

## Hypothesis — which stage to blame

No stage to blame in the **output** sense — final values are correct. But there's a **process concern** worth flagging:

The vision probe is producing **plausibly-wrong answers with high stated confidence** (0.8 for "Alpicat" which is objectively wrong). Today this is harmless because competition has higher-priority sources for `municipality`. But:

- If a project had **no other source** for municipality (no comanda-lab Excel, no cadastre hit), the probe's wrong answer would win by default.
- If we extend `_VISION_DETECTABLE_CONCEPTS` (as artifact 2's hypothesis suggests), we'd pull the probe into **more** variable competitions — increasing the blast radius of mis-reads.

The probe's role is "cheap sanity check on image content", not "authoritative extractor". The design currently respects that (low priority). A future tuning direction: **the probe should abstain rather than guess**. For a map, if it can't distinguish subject from incidental labels, it should return concepts_found=[] and just tag document_type. Current prompt doesn't encourage abstention.

## Recommended knob (highest leverage)

**Add a "subject scoping" clause to `_PROBE_PROMPT` for maps:**

```
For document_type='map': identify the municipality and province that are
the SUBJECT of this map (marked with a highlighted polygon, legend marker,
or a text label near the image center). Do NOT return the names of
neighboring towns visible at the frame edges. If you cannot distinguish
the map subject from incidental labels, return concepts_found=[] for
municipality and province — prefer abstaining over guessing.
```

Cost implication: none (prompt only). Expected win: this file's wrong `municipality=Alpicat` → abstain. Doesn't change this sweep's numbers (municipality is MATCH via Excel anyway) but reduces the risk of wrong wins in projects with fewer sources.

**Secondary knob:** post-process the probe output — for each `concepts_found` entry, run a cheap sanity check against known project metadata (project folder name contains municipality? cadastre returned a municipality?). If the probe's value disagrees with another source, drop confidence to 0.3.

**Note on the `DOC_TYPE_DISAMBIGUATION["map"]` entry:** it currently routes `map` + "situation" description → `situation_plan` role. For this file, the probe's description was "Map showing study area" (no "situation" keyword), so the disambiguation wouldn't have promoted. But if the description had said "situation map of Vilanova", the classifier would have wrongly tried to assign it to `situation_plan` — which is an input-data role, not a figure role. Worth double-checking that map-disambiguation logic doesn't miscategorize maps already handled by SmartScan.
