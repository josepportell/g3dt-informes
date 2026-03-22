#!/usr/bin/env python3
"""
G3DT Extraction Prompt Templates

Structured prompts for extracting data from handwritten field documents
using Claude vision. These prompts instruct the model to output JSON
matching the validation schemas.

Usage:
    from validation.prompts import DPSH_EXTRACTION_PROMPT, SONDEIG_EXTRACTION_PROMPT

Author: Eficients.cat
Date: 2026-02-04
"""

# JSON schema examples embedded in prompts for Claude vision extraction

DPSH_JSON_EXAMPLE = '''
{
  "dpsh_tests": [
    {
      "test_id": "P-1",
      "readings": [
        {"depth_m": 0.20, "n20": 15, "confidence": 1.0, "note": null, "torque": null, "water_indicator": false},
        {"depth_m": 0.40, "n20": 18, "confidence": 0.85, "note": "partially smudged", "torque": null, "water_indicator": false},
        {"depth_m": 0.60, "n20": "??", "confidence": 0.0, "note": "illegible", "torque": null, "water_indicator": false}
      ],
      "refusal_depth_m": 1.40,
      "refusal_detected": true,
      "water_detected": false,
      "water_depth_m": null,
      "correction_factor": 0.83,
      "extraction_notes": "Test completed normally"
    }
  ],
  "spt_in_dpsh": {
    "test_id": "SPT-1",
    "location": "P-3",
    "depth_from_m": 0.60,
    "depth_to_m": 1.20,
    "blows": [16, 20, 20, 24],
    "n_spt": 40,
    "confidence": 0.90
  },
  "overall_confidence": 0.85,
  "extraction_notes": "Some values partially illegible due to ink smudges"
}
'''

DPSH_EXTRACTION_PROMPT = f'''Analyze this DPSH (Dynamic Probing Super Heavy) penetration test field sheet.

TASK: Extract all data into a structured JSON format.

DOCUMENT STRUCTURE:
- The document shows penetration test results for one or more test points (P-1, P-2, etc.)
- Each test has a column showing depth (in meters) and corresponding N20 values (blow counts per 20cm)
- May include: torque (PAR) values, water level indicators (N.F.), soil level markers
- A correction factor (typically 0.83) may be shown at the top
- Refusal is indicated by "R" or very high values (>=100)

EXTRACTION RULES:
1. For each test point found, extract ALL depth/N20 pairs
2. Depths are typically in 20cm increments: 0.20, 0.40, 0.60, etc.
3. N20 values are integers (blow counts)
4. Mark any illegible or uncertain values with confidence < 1.0
5. Use "??" for completely illegible N20 values (set confidence to 0.0)
6. Note any refusal (R marker or N20 >= 100). If the field sheet has a handwritten "R x.xx" annotation (e.g. "R 1,35", "R 2,45"), use THAT value as `refusal_depth_m` — it is the exact refusal depth, more accurate than the row depth with N20=100 (which rounds to the 0.20m grid).
7. Note water level if indicated
8. If the field sheet includes an SPT test, extract it to `spt_in_dpsh` with: test_id, location (DPSH point), depth_from_m, depth_to_m, blows (array of 15cm blow counts), n_spt (blows[1]+blows[2]), confidence. Set `spt_in_dpsh` to null if no SPT.

CONFIDENCE SCORING:
- 1.0: Clear, unambiguous value
- 0.7-0.9: Readable but some uncertainty (smudged, faded)
- 0.5-0.7: Partially legible, interpretation required
- <0.5: Uncertain, requires verification
- 0.0: Illegible, use "??" for the value

OUTPUT FORMAT (JSON):
{DPSH_JSON_EXAMPLE}

Extract all visible test data from this document. Be thorough and note any uncertainties.'''


SONDEIG_JSON_EXAMPLE = '''
{
  "sondeig_tests": [
    {
      "test_id": "S-1",
      "total_depth_m": 6.0,
      "num_geological_levels": 2,
      "layers": [
        {
          "depth_from_m": 0.0,
          "depth_to_m": 0.5,
          "description": "Terra vegetal",
          "geological_level": 1,
          "uscs_classification": null,
          "color": "marro",
          "moisture": "humit",
          "consistency": null,
          "density": null,
          "confidence": 1.0,
          "note": null
        },
        {
          "depth_from_m": 0.5,
          "depth_to_m": 3.2,
          "description": "Argila marronosa amb graves",
          "geological_level": 2,
          "uscs_classification": "CL",
          "color": "marro clar",
          "moisture": "humit",
          "consistency": "ferma",
          "density": null,
          "confidence": 0.9,
          "note": "USCS classification uncertain"
        }
      ],
      "spt_results": [
        {
          "test_id": "SPT-1",
          "depth_from_m": 1.00,
          "depth_to_m": 1.60,
          "blows": [24, 14, 28, 30],
          "n_spt": 42,
          "confidence": 0.90
        }
      ],
      "elevation_z": 199.50,
      "water_level_m": null,
      "rock_detected": false,
      "rock_depth_m": null,
      "extraction_notes": null
    }
  ],
  "overall_confidence": 0.9,
  "extraction_notes": "Document in good condition"
}
'''

SONDEIG_EXTRACTION_PROMPT = f'''Analyze this Sondeig (drilling/borehole) field log sheet.

TASK: Extract all soil layer data into a structured JSON format.

DOCUMENT STRUCTURE:
- The document shows a drilling log for one or more boreholes (S-1, S-2, etc.)
- Each borehole has a graphic column showing soil layers
- For each layer: depth range, soil description, color, moisture, consistency/density
- May include USCS classification symbols (CL, SM, SP, GW, etc.)
- Water level (N.F.) may be indicated
- Rock or refusal may be noted at bottom

CRITICAL — "Unitat litològica" COLUMN:
The field sheet has a column labeled "Unitat litològica" (or "U. Litol.") that groups
soil strata into geological LEVELS (NIVELL 1, NIVELL 2, etc.). This is the AUTHORITATIVE
source for the number of geological levels. Multiple soil strata (visible transitions in
the graphic column) may belong to the SAME geological level. For example, if the "Unitat
litològica" column only shows "NIVELL 1" for the entire borehole depth, then
num_geological_levels = 1, even if you see 2 or more distinct soil descriptions.

FALLBACK RULE:
If the document does NOT have a "Unitat litològica" column (common in handwritten field sheets),
set `num_geological_levels = 1` by default. Only set it to >1 if there is EXPLICIT evidence of
separate geological levels marked in the document (e.g., clear "NIVELL 1", "NIVELL 2" labels).
Different material descriptions within the same borehole do NOT automatically mean different
geological levels — they may be sub-layers within the same geological unit.

EXTRACTION RULES:
1. For each borehole, extract ALL soil layers from surface to final depth
2. Depths should be continuous (each layer's depth_to_m = next layer's depth_from_m)
3. Extract soil descriptions in Catalan as written
4. For each layer, set "geological_level" to the NIVELL number from the "Unitat litològica" column
5. Set "num_geological_levels" to the count of DISTINCT values in the "Unitat litològica" column
6. Note USCS classification if visible (typically in a separate column)
7. Moisture states: sec, humit, saturat
8. Consistency (cohesive soils): tova, ferma, dura
9. Density (granular soils): fluixa, mitja, densa
10. Mark uncertain values with appropriate confidence scores
11. If SPT tests are recorded, extract each to `spt_results` array with: test_id, depth_from_m, depth_to_m, blows (array of 15cm blow counts), n_spt (blows[1]+blows[2]), confidence. Use empty array `[]` if no SPT.
12. Extract `elevation_z` (cota z in meters) from the borehole header if present (e.g., "Cota z=199.50m" or "z=199.50"). Set to null if not found.

CONFIDENCE SCORING:
- 1.0: Clear, unambiguous description
- 0.7-0.9: Readable but some uncertainty
- 0.5-0.7: Partially legible
- <0.5: Uncertain
- 0.0: Illegible

OUTPUT FORMAT (JSON):
{SONDEIG_JSON_EXAMPLE}

Extract all soil layer information from this document. Be thorough and note any uncertainties.'''


SONDEIG_ANNEX_EXTRACTION_PROMPT = f'''Analyze this formatted borehole log (sondeig annex).

TASK: Extract all soil layer data into a structured JSON format.

DOCUMENT TYPE: This is a FORMATTED document (vectorial PDF, not handwritten). It is the official
annex version of the borehole log, generated from FreeHand or similar software. Data should be
clearer than handwritten field sheets — use higher base confidence.

DOCUMENT STRUCTURE:
- The document shows a borehole log for one or more boreholes (S-1, S-2, etc.)
- It has a graphic column showing soil layers with depth ranges
- For each layer: depth range, soil description, color, moisture, consistency/density
- May include USCS classification, SPT values, RQD
- Water level (N.F.) may be indicated
- Rock or refusal may be noted at bottom

CRITICAL — "Unitat litològica" COLUMN:
This document has a column labeled "Unitat litològica" (or "U. Litol.", "Nivell", "N") that groups
soil strata into geological LEVELS (NIVELL 1, NIVELL 2, etc. or just 1, 2, etc.).

THIS IS THE AUTHORITATIVE SOURCE for the number of geological levels.

Multiple soil descriptions (material transitions in the graphic column) may belong to the SAME
geological level. For example:
- "Graves en matriu sorrenca" from 0-2m and "Graves en matriu sorrenca carbonatades" from 2-6m
  might BOTH be NIVELL 1 if the "Unitat litològica" column shows a single "1" spanning both.

Rules for `num_geological_levels`:
1. COUNT the distinct values in the "Unitat litològica" column
2. Do NOT count material transitions — only count distinct LEVEL numbers
3. If the column shows only "1" (or "NIVELL 1") for the entire depth, then num_geological_levels = 1

EXTRACTION RULES:
1. For each borehole, extract ALL soil layers from surface to final depth
2. Depths should be continuous (each layer's depth_to_m = next layer's depth_from_m)
3. Extract soil descriptions in Catalan as written
4. For each layer, set "geological_level" to the LEVEL number from the "Unitat litològica" column
5. Set "num_geological_levels" to the count of DISTINCT values in that column
6. Note USCS classification if visible
7. Moisture states: sec, humit, saturat
8. Consistency (cohesive soils): tova, ferma, dura
9. Density (granular soils): fluixa, mitja, densa

CONFIDENCE SCORING (higher base for formatted docs):
- 1.0: Clear printed text (most values in formatted docs)
- 0.9: Readable with minor uncertainty
- 0.7-0.8: Some ambiguity in interpretation
- <0.7: Unclear or partially obscured

OUTPUT FORMAT (JSON):
{SONDEIG_JSON_EXAMPLE}

Extract all soil layer information from this formatted document. Pay special attention to the
"Unitat litològica" column for determining num_geological_levels.'''


# ============================================================================
# Plànol (A.01.pdf) — Architect plan extraction
# ============================================================================

PLANOL_JSON_EXAMPLE = '''
{
  "architect_data": {
    "source_file": "A.01.pdf",
    "project_name": "Habitatge Unifamiliar Aïllat",
    "street_address": "C/ Mestre Ramon Ortiz",
    "municipality": "Bell-Lloc d'Urgell",
    "promotor": "Ramon Mitjana SL",
    "architect": "Jordi Bosch Novell",
    "architect_company": "Bosch Arquitectura SLP",
    "dimensions": {
      "parcel_area_m2": {"pdf_value": 598.0, "confidence": 0.95},
      "building_footprint_m2": {"pdf_value": 296.88, "confidence": 0.90},
      "floor_surfaces": [
        {"floor": "PB", "area_m2": 297.0, "confidence": 0.90},
        {"floor": "P1", "area_m2": 110.0, "confidence": 0.90}
      ],  // NOTE: each floor is a SEPARATE entry — never combine as "PB+P1"
      "num_floors": {"pdf_value": "Pb+P1", "confidence": 1.0},
      "max_height_m": {"pdf_value": 8.38, "confidence": 0.85},
      "plot_length_m": {"pdf_value": 24.57, "confidence": 0.90},
      "plot_width_m": {"pdf_value": 24.72, "confidence": 0.90}
    }
  },
  "floor_plan_bbox": {
    "top_pct": 0.0,
    "left_pct": 0.0,
    "bottom_pct": 71.0,
    "right_pct": 60.0,
    "confidence": 0.90
  },
  "overall_confidence": 0.90,
  "extraction_notes": "Caixetí clear, dimensions from site plan"
}
'''

PLANOL_EXTRACTION_PROMPT = f'''Analyze this architectural plan (plànol) for a construction project.

TASK: Extract project and building data into structured JSON.

IMPORTANT: Architect plans come in MANY different formats and layouts. The title block (caixetí)
may be in any corner or edge of the page. The document may be:
- A formal CAD plan with caixetí (title block) and floor plan drawings
- A site plan (emplaçament) with cadastral map and/or satellite image
- An informal sketch or "punts de sondeig" plan with test point locations
- A photo of a printed plan (rotated, with dark edges and table surface visible)
- A typology sheet with area tables per unit type (no floor plan drawing)
- A simple situation map showing the parcel location

Adapt your extraction to WHATEVER format you see. Extract what is available — do not fail
because the document doesn't match a specific expected layout.

WHERE TO FIND DATA:
- Title block / caixetí (ANY position — bottom-right, bottom-left, bottom-center, or side):
  - Project name/type (e.g., "Habitatge Unifamiliar Aïllat", "Avantprojecte", "Estudi de Detall")
  - Location: street + number (WITHOUT postal code or municipality) → "street_address"
  - Municipality name (WITHOUT postal code or province) → "municipality"
  - Promotor / Propietari: company or individual name
  - Architect: name and college number (nºCol.)
  - Architect company / studio: firm name (may be a logo or letterhead, e.g., "Bunyesc", "Rocar", "Graus")
  - Scale, date
- Plan drawing area (may contain):
  - Parcel area in m²
  - Parcel dimensions (length × width, labeled in meters)
  - Building footprint in m² or as percentage
- Area tables (quadre de superfícies, may be on a separate page or in a table):
  - Per-floor surfaces (PB, P1, PS, PP, "Planta Baja", "Planta Primera", etc.)
  - Per-unit/typology areas (T1, T2, T3 — sum for total)
  - Total built surface
- Section / alzat / sección (if present):
  - Number of floors (PB, PB+1, Ps+PB+2Pp, "Sótano + Planta Baja + Planta 1", etc.)
  - Maximum building height in meters

EXTRACTION RULES:
1. Extract text EXACTLY as written (Catalan or Spanish — do not translate)
2. For dimensions, prefer values with explicit units (m, m²)
3. Number of floors: use the format as written (e.g., "Pb+P1", "Ps+Pb+2Pp", "SÓTANO, PLANTA BAJA y PLANTA 1")
4. If a value has multiple interpretations, use the most specific one
5. Set null for fields not found in the document — this is FINE, not every plan has every field
6. Building footprint may be labeled "ocupació", "superfície construïda", "sup. construida", or similar
7. If architect_company is not separately listed but a logo or studio name is visible, extract that
8. Per-floor surfaces: extract each floor as a SEPARATE entry in `floor_surfaces` array. NEVER combine floors. If a typology table shows areas per unit type, extract the TOTAL per floor across all types
9. If the document is a photo of a plan, ignore background elements (table surface, hands, edges) and focus on the plan content

FLOOR PLAN BOUNDING BOX:
Identify the bounding box of the main drawing area (site plan, floor plan, or sketch).
EXCLUDE the title block, legends, section views, and annotations outside the main drawing.
Return as percentage coordinates of the full page. If no clear drawing area exists (e.g., pure
table of areas or situation map), set floor_plan_bbox to null.

CONFIDENCE SCORING:
- 1.0: Clear printed text, unambiguous
- 0.9: Readable with minimal uncertainty
- 0.7-0.8: Readable but small text or requires interpretation
- 0.5: Difficult to read or ambiguous (e.g., photo of plan, low resolution)
- Use null for values not found

OUTPUT FORMAT (JSON):
{PLANOL_JSON_EXAMPLE}

Extract all visible data from this architectural document. If the document only has partial
information (e.g., only parcel dimensions and no building details), extract what you can.'''


# System prompt for general extraction context
EXTRACTION_SYSTEM_PROMPT = '''You are a geotechnical data extraction specialist. Your task is to
carefully extract data from field documents, architectural plans, and project files, converting
them to structured JSON.

KEY PRINCIPLES:
1. ACCURACY: Only extract what you can clearly see. Never guess or fabricate values.
2. UNCERTAINTY: Mark uncertain values with lower confidence scores.
3. COMPLETENESS: Extract ALL data visible in the document.
4. STRUCTURE: Follow the exact JSON format specified.
5. ADAPTABILITY: Documents come in many formats — formal CAD plans, informal sketches,
   photos of printed documents, screenshots, scanned handwritten sheets. Adapt to whatever
   format you receive. Extract what is available, set null for what is not.

When a value is unclear:
- If partially readable, extract your best interpretation and note confidence < 1.0
- If completely illegible, use "??" and confidence = 0.0
- Always add a note explaining the issue

The output will be reviewed by humans, so marking uncertainty is essential.'''


if __name__ == '__main__':
    print("=== G3DT Extraction Prompts ===\n")
    print("DPSH_EXTRACTION_PROMPT:")
    print("-" * 40)
    print(DPSH_EXTRACTION_PROMPT[:500] + "...")
    print("\nSONDEIG_EXTRACTION_PROMPT:")
    print("-" * 40)
    print(SONDEIG_EXTRACTION_PROMPT[:500] + "...")
