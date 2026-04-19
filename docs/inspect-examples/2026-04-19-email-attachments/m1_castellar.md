# Artifact: `ANNEXES/ALTRES/M1.png` (Castellar del Vallès)

**Also present as:** only at this path.
**Type:** `image` (PNG) | **Size:** 633 KB | **Text extractable:** ✗
**Why we're looking at this:** a file that worked **perfectly** — classified correctly, probe extracted correct values with appropriate abstention where uncertain, no downstream damage. Useful as the "what does working-as-intended look like" baseline against the three cases with real failures. Also illustrates that M1-M10 maps (Eva's ANNEXES/ALTRES/ convention) are not deep-folder-classifier targets because FileScanner's filename pattern catches them first.

---

## Journey

### Stage 0.0 — FileScanner
- **goal:** assign role by filename match.
- **config:** Filename pattern for `figure_geological_map` includes `^M\d+\.png$` (M1, M2, ..., M10).
- **expected:** assigned to `figure_geological_map` role.
- **actual:** `file_mapping.roles.figure_geological_map.path = "ANNEXES/ALTRES/M1.png"`, `detection = "filename_pattern"`.
- **deviation:** met expectation.
- **knobs:** n/a.

### Stage 0.3 — FileMiner
- **expected:** skipped (image).
- **actual:** skipped.

### Stage 0.4 — GroqMiner
- **expected:** skipped.
- **actual:** skipped.

### Stage 0.45 — ConceptScout vision probe
- **goal:** identify concepts visible in the image.
- **config:** default probe.
- **expected:** `document_type: map`; municipality/province if visible.
- **actual:** `validation/concept_probes/d3b5d106397d.json`:
  ```json
  {
    "document_type": "map",
    "document_description": "Location map showing Castellar del Vallès",
    "concepts_found": [
      {"concept_id": "municipality", "confidence": 1.0, "signal_preview": "Castellar del Vallès", "page": 1},
      {"concept_id": "province",     "confidence": 0.0, "signal_preview": "",                      "page": 1}
    ]
  }
  ```
- **deviation:** met expectation. `municipality` correct at full confidence; `province` **correctly abstained** (empty preview, confidence 0) — the probe didn't invent a value when it couldn't see one.
- **knobs:** this is the behavior we want from the probe. The F1 SIT.png counterexample (artifact 3) showed the probe guessing a wrong municipality at 0.8 confidence — here it chose abstention. **The difference is the image content, not the prompt** — the probe is capable of abstaining; it just doesn't always choose to.
- **hypothesis:** when the map has a single clear subject label (as this Castellar map does), the probe scores high and returns it. When the map is a regional view with multiple labels (as F1 SIT was), the probe defaults to picking one without abstaining. Adding an explicit "prefer abstention over guessing" clause to the probe prompt would make this behavior consistent across cases.
- **replay:** `python -c "from automation.concept_scout.vision_probe import _run_probe; from pathlib import Path; print(_run_probe(Path('reference-material/3001621 CASTELLAR DEL VALLES/ANNEXES/ALTRES/M1.png')))"`.

### Stage 0.46 — Deep folder classifier
- **expected:** SKIPPED — already assigned to `figure_geological_map` by FileScanner filename pattern.
- **actual:** skipped. Confirmed by absence from `deep_folder_files`.
- **note:** had FileScanner *not* assigned, the classifier would have read the probe cache and applied `DOC_TYPE_DISAMBIGUATION["map"]["geologic"]` or `["geològic"]` based on description text. The description is "Location map showing Castellar del Vallès" — **does not contain** "geologic/geològic/topographic/situation/aerial" keywords → would fall through to `DOC_TYPE_TO_ROLE["map"] = None` → unclassified. **Gap noted:** the disambiguation table can't handle "Location map" as a keyword; the filename-based assignment is what saves us here.

### Stage 0.47 — Re-mine promoted
- **expected:** n/a.

### Stage 1 — Vision extractor
- **expected:** SKIPPED (no vision_type mapping for `figure_*` roles).
- **actual:** skipped.

### Stage Synthesis + Competition + Judge
- `municipality`: probe's correct signal (`"Castellar del Vallès"`, confidence 1.0) is logged in `concept_map.concept_sources["municipality"]` with `method=vision_probe:map`. Lost competition to `fileminer_regex` from the comanda Excel (`CASTELLAR DEL VALLÈS`, method=`label_adjacent`, higher priority). Final pipeline_value = `CASTELLAR DEL VALLÈS` → **MATCH**.
- `province`: probe abstained (empty, conf 0). Not a signal. Province winner (if any) came from elsewhere.
- **deviation:** none. Pipeline correct.

---

## Downstream Impact

| Variable | Final status | Eva | Pipeline | This file's contribution | Visible in signals[]? |
|---|---|---|---|---|---|
| `municipality` | **MATCH** | `Castellar del Vallès` | `CASTELLAR DEL VALLÈS` | Correct signal at 1.0 conf; lost to higher-priority Excel | Not directly (probe signals live in concept_map.json, not in diagnostic's competition trace for this variable) |
| `province` | — | — | — | Abstained; no signal | n/a |

**Net impact:** zero damage, zero uplift. File worked as intended; higher-priority source won competition; probe behaved correctly including abstention on province.

---

## Hypothesis — which stage to blame

None. This is the baseline case: pipeline components cooperated as designed, the probe's output was correct or correctly abstained, and the competition math selected the authoritative source. **M1.png is the reference for "healthy pipeline interaction".**

Two observations worth preserving:

1. **FileScanner's filename patterns are strong where they exist.** Filename `M1.png` → `figure_geological_map` saves us from needing the deep-folder classifier to figure it out. This is a hint that **extending filename patterns** (cheap, deterministic, zero LLM cost) is often a better knob than **tuning vision prompts** (expensive, non-deterministic, higher maintenance).
2. **The probe CAN abstain when uncertain.** Province → empty + conf=0 on M1.png, vs. municipality → "Alpicat" at 0.8 on F1 SIT.png. Same prompt, same model, different behavior. If we can reproduce the abstention pattern reliably, we reduce the wrong-guess failure mode.

## Recommended knob (highest leverage)

**No change for this artifact specifically** — it already works.

**Generalizable insight from this file (feeding the cross-artifact README):** **extend filename patterns before tuning vision.** Many of the files that went to the deep-folder classifier's vision layer (artifact 1: `1.0.pdf`; artifact 5: `2_02B_DG_Silvia_Jaume.pdf`) have recognizable filename conventions. Adding patterns like `^\d+\.\d+\.pdf$` (architect plan sheet naming), `^PLANO\s+\d+\.pdf$`, `^\d+_\d+[A-Z]_DG.*\.pdf$` (DG = document grup) to `ROLE_PATTERNS` would intercept them at stage 0.0, bypassing the probabilistic layers entirely.

This artifact's value is as **evidence that filename-based classification is the safest first line of defense**. The other four artifacts show what happens when we fall back to vision: sometimes great (artifact 2), sometimes wrong-confident (artifact 3's probe), sometimes wrongly-routed (artifact 1's classifier). Expanding filename coverage shrinks the attack surface for all those failure modes.
