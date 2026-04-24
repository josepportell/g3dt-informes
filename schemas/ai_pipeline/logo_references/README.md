# Logo reference library

G3DT-specific logo variants used by Stage 2's pre-LLM logo filter
(`automation/ai_pipeline/typology.py`). Each extracted image is hashed
with `imagehash.phash()` and compared against every file here; a
Hamming distance ≤ 6 to any reference marks the image as
`category="logo_image"`, `useful=False`.

Design + validation data: `docs/PLA-D1-LOGO-FILTER.md`.

## Current references

| File | Origin | Style captured |
|------|--------|----------------|
| `g3_tight.png` | Alcoletge `PLAN_COST_ALCOLETGE/img_000.png` | G3 circular logo, tight crop (~33×33) |
| `g3_large_circle.jpg` | Alcoletge `RE_ .../image001.jpg` | G3 circular logo, larger with padding |
| `g3_watermark.jpg` | Alcoletge `PRESSUPOST/img_000.jpeg` | G3 as full-bleed watermark, tone clear |
| `25anys_banner.jpg` | Alcoletge `RE_ .../image008.jpg` | "25 anys — Compromesos amb el teu projecte" |

## Adding a new reference

1. Drop the image in this folder.
2. Add a row to the table above.
3. Run `.venv/bin/python -m pytest tests/test_ai_pipeline_typology.py -k logo`
   — the self-match test verifies the new reference hashes to itself at
   Hamming 0, which guards against corrupt or mis-named files.
4. If the new reference is very close to an existing one (mutual Hamming
   ≤ 6), prefer NOT to add it — redundant coverage inflates per-image
   compare cost without value.

## Removing a reference

Just delete the file. No other action needed — the loader enumerates
the directory each cache-miss.

## Client-scoping (future)

If Eficients ever installs G3DT onto a second client's environment,
we'll move to `logo_references/<client_id>/` and select the subdir
per project. Today single-client, single folder.
