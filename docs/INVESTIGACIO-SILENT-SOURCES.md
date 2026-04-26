# Investigation — Silent Sources (Stage 4 produced 0 candidates)

**Data:** 2026-04-26
**Branca:** `experiment/ai-pipeline`
**Trigger:** trace tool surfaced 8 silent sources on Alcoletge — Stage 4 paid LLM calls but extracted no candidates.
**Scope:** the 4 sources outside dev-only parents (sources 1, 2, 7, 8). The other 4 will be filtered automatically by D17 dev-only rules on next Stage 2 refresh.

---

## Per-source verdict

### 1. `ANNEXES/COORDENADES.txt` — coordinates text file

**Content** (64 bytes):
```
Coordenades UTM (X);(Y);(Z);
P-1
308781,86 ; 4613950.63 ; 198.9
```

**Class C — Useful by deterministic parsing, not LLM.**

Stage 4 silently failed because the LLM has no good way to extract concept candidates from a tightly structured 3-line CSV-like file. The data IS valuable (it's Eva's GPS field-recording for utm_x / utm_y / utm_z), but a 5-line regex does the job perfectly without LLM cost.

The legacy `auto_extractor.py` Phase 0.1 already parses UTM from various sources; this file format just needs a small dedicated parser.

### 2. `DTE.txt` — accounting memo

**Content** (76 bytes):
```
EN DATA 02/03 DTO AQUEST INFORME PER UN IMPORT DE 1016,40€ - VCT: 30/03/26
```

**Class B — Pre-skippable.**

This is a legacy accounting memo (date stamped on report, invoice amount, value-by date). It contains zero geotechnical / site / structural content. Stage 4 correctly emitted no candidates — the source is genuinely irrelevant to the 88 concepts.

### 7. `validation/ai_pipeline/extracted/PLAN_COST_ALCOLETGE/img_000.png` — logo

**Content**: bright-green circular G3 logo, no plan content visible.

**Class B — Pre-skippable.**

A logo that escaped the pHash detector. The logo filter library already has variants but this specific extraction either has different proportions, anti-aliasing, or the parent's PLAN_COST PDF rendered it slightly differently. Either:
- Pre-skip rule: "extracted images named `img_000` from `PLAN_COST_*` parents are usually the company logo header" (heuristic, may false-fire on real plans).
- Add this exact image to `schemas/ai_pipeline/logo_references/` as a new variant — the principled fix.

### 8. `validation/ai_pipeline/extracted/PRESSUPOST_GEOTEC.ALCOLETGE_SIGNAT-SCAN/img_005.jpeg` — boilerplate

**Content**: contractual-terms page from a scanned pressupost ("Condicions específiques assumides amb la firma i acceptació del pressupost geotècnic"). Catalan text, no numeric data, no project-specific information.

**Class B — Pre-skippable.**

Stage 4 correctly produced 0 candidates because there is genuinely nothing extractable. But the LLM call still cost ~$0.05.

---

## Recommended Stage 2 rules

### Rule A — `coordinates_text` category for `*COORDENADES*.txt`

In `automation/ai_pipeline/typology.py`, add a new category in `_classify_file`:

```python
# Before the generic txt fallthrough:
if fmt == "txt" and "COORDENADES" in Path(path).name.upper():
    return ("coordinates_text", True, "structured UTM coordinates",
            "parse_deterministically")
```

Stage 3 conversion sees `parse_deterministically` and skips LLM-readying conversion (no markdown / image generation needed). Stage 4 sees the category and skips the LLM call entirely. The legacy `auto_extractor.py` already pulls UTM from various places; if it's still configured to read this path, the deterministic value flows in.

If we want the AI Pipeline to ALSO have these UTM values, add a 5-line parser to `automation/ai_pipeline/inventory.py` or a new `automation/ai_pipeline/coordinates_parser.py`:

```python
def parse_coordenades_txt(filepath: Path) -> dict[str, Any] | None:
    """Parse ANNEXES/COORDENADES.txt — header + (test_id) + (x;y;z) per row."""
    try:
        text = filepath.read_text(encoding='utf-8-sig').strip()
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        if len(lines) < 3:
            return None
        test_id = lines[1]
        parts = [p.strip().replace(',', '.') for p in lines[2].split(';')]
        if len(parts) >= 2:
            return {
                'test_point_id': test_id,
                'utm_x': float(parts[0]),
                'utm_y': float(parts[1]),
                'utm_z': float(parts[2]) if len(parts) > 2 else None,
            }
    except Exception:
        pass
    return None
```

The output dict can be injected as candidates directly into Stage 4's manifest (synthesizing a "deterministic_parser" SourceAnalysis) without any LLM call. Bonus: this fixes the silent UTM-swap bug Pass C produced — if Stage 4 has a deterministic UTM source at confidence 1.0, Pass A will rank it top-1 and Pass C will leave it alone.

### Rule B — Skip `DTE.txt` and small accounting-memo `.txt` files

In `automation/ai_pipeline/typology.py`:

```python
if fmt == "txt":
    name_upper = Path(path).name.upper()
    if name_upper == "DTE.TXT":
        return ("accounting_memo", False,
                "invoice stub (DTE.txt convention), not project data", "skip")
    # Generic small-text-with-no-tech-pattern guard:
    if size_kb < 0.15:  # < 150 bytes
        try:
            preview = abs_path.read_text(encoding="utf-8", errors="replace")[:200]
        except OSError:
            preview = ""
        # No coordinate-shaped or depth-shaped patterns found?
        if not re.search(r"\d{6,7}[.,]?\d*\s*[;,]\s*\d{6,7}", preview) and \
           not re.search(r"-\s*\d+[.,]\d+\s*m", preview):
            return ("text_stub", False,
                    "small text file with no technical pattern", "skip")
```

This skips DTE.txt by name and any small generic text file with no coordinate/depth pattern.

### Rule C — Skip pressupost boilerplate images

For extracted images whose parent stem starts with `PRESSUPOST` AND whose index is in the first ~5 positions (cover, terms, logo header), skip:

```python
# In typology.py extracted-image classification:
parent_stem = Path(parent_path).stem if parent_path else ""
img_name = Path(rel).name
m = re.match(r"img_0*(\d+)\.", img_name)
img_index = int(m.group(1)) if m else 999

if parent_stem.upper().startswith("PRESSUPOST") and img_index < 6:
    return ("pressupost_boilerplate", False,
            f"pressupost page {img_index} (cover/terms), no project data", "skip")
```

The cutoff `<6` is arbitrary; tune by inspection. We could also pHash-match against signature/seal samples once we have a few collected.

### Rule D — Add the escaped logo to the reference library

The simplest fix for source 7 (PLAN_COST_ALCOLETGE/img_000.png):

```bash
cp "reference-material/4001670 ALCOLETGE/validation/ai_pipeline/extracted/PLAN_COST_ALCOLETGE/img_000.png" \
   schemas/ai_pipeline/logo_references/g3_plan_cost_header.png
```

Then verify pHash detection on Alcoletge — if it now triggers, the silent source is gone. If it still escapes, the threshold (Hamming ≤ 6) may need to be relaxed to 8 for this variant, OR the image needs preprocessing (crop, resize) before hashing.

---

## Cost saved per re-run

- 4 silent sources × ~$0.05 each = **$0.20/project**
- × 7 projects = **$1.40 per full batch**

Modest in absolute terms, but: (a) the COORDENADES.txt deterministic parser also unlocks UTM extraction for the AI pipeline (which currently extracts wrong UTM from emails — see the Pass C utm_x/y "worse" verdict), so Rule A has compound value; (b) the rules are cheap to implement (~50 lines of Python total, all in typology.py + a parser file).

---

## Notes for the implementer

- Rule A is the **highest-ROI** of the four — it eliminates one silent source AND fixes the UTM extraction quality on the next run.
- Rules B, C, D are pure cost savings (~$0.20/project combined).
- All rules are pre-Stage-4 — they save the LLM call entirely.
- After landing, re-run Stage 2 with `?refresh=true` on Alcoletge to verify the new typology classifications take effect.
- Don't generalize the "small file = skip" rule too aggressively — small `.txt` files containing structured field data (e.g., a 3-line UTM file) ARE valuable. Rule A handles that case explicitly; Rule B's pattern guard avoids false-positive skips.
- The 4 dev-only-parent silent sources (3, 4, 5, 6) need no special handling — D17's filename patterns will drop their parents on next Stage 2 run, which cascades to filter the extracted images too.

---

*Investigation report — 2026-04-26.*
