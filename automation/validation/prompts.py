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

DEPTH PRECISION (CRITICAL — handwritten field sheets):
SPT depths are usually written as round values (e.g. -1.00, -2.00, -3.50).
Be especially careful distinguishing handwritten "1" from "9":
- "-1.00" is a round whole metre, very common as an SPT start depth.
- "-0.90" would be unusual (depths almost always end in ".00" or ".50").
- A digit that LOOKS like "9" with a leading "-0." prefix is almost
  certainly a "1" being read as "9" -- prefer "-1.00" unless you can
  see a clear closed loop on top with a descending tail.

Worked example: a handwritten "−1,00 a −1,60" can look like "−0,90 a −1,60"
when the leading "1" is poorly formed. Default to the round value (−1.00)
unless the digit unambiguously shows the loop+tail of a "9". When in doubt,
lower the confidence rather than guess.

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
  "data_sources_found": ["Title block (caixeti)", "Planning/normativa table", "Site plan drawing"],
  "planning_table_raw": {
    "planejament": {"parcel_min": "600 m2", "occupancy": "30%", "floors": "PB+PP", "height": "6.60 m"},
    "projecte": {"parcel": "995 m2", "occupancy": "296.88 m2", "floors": "PB+PP", "height": "6.88 m"}
  },
  "architect_data": {
    "source_file": "A.01.pdf",
    "project_name": "Habitatge Unifamiliar Aïllat",
    "building_type": "habitatge unifamiliar aïllat",
    "client_name": "RAMON MITJANA S.L.",
    "street_address": "C/ Mestre Ramon Ortiz nº 12",
    "municipality": "Bell-Lloc d'Urgell",
    "promotor": "Ramon Mitjana SL",
    "architect": "Jordi Bosch Novell",
    "architect_company": "Bosch Arquitectura SLP",
    "dimensions": {
      "parcel_area_m2": {"pdf_value": 995.0, "confidence": 0.95, "source": "Projecte column"},
      "building_footprint_m2": {"pdf_value": 296.88, "confidence": 0.90, "source": "Projecte column"},
      "floor_surfaces": [
        {"floor": "PB", "area_m2": 297.0, "confidence": 0.90},
        {"floor": "P1", "area_m2": 110.0, "confidence": 0.90}
      ],
      "num_floors": {"pdf_value": "PB+PP", "confidence": 1.0, "source": "Projecte column"},
      "max_height_m": {"pdf_value": 6.88, "confidence": 0.95, "source": "Projecte column"},
      "plot_length_m": {"pdf_value": 24.57, "confidence": 0.90},
      "plot_width_m": {"pdf_value": 24.72, "confidence": 0.90}
    }
  },
  "overall_confidence": 0.90,
  "extraction_notes": "Caixeti clear. Planning table found: Projecte column used for dimensions."
}
'''

PLANOL_EXTRACTION_PROMPT = f'''You are a senior architect reviewing a colleague's project documentation.

TASK: Analyze this architectural plan and extract project data through structured reasoning.

IMPORTANT: Plans come in many formats — CAD with caixetí, site plans, informal sketches,
photos of printed plans, typology sheets. Adapt to whatever format you see.

Follow these steps IN ORDER:

STEP 1 — IDENTIFY ALL DATA SOURCES ON THE PAGE:
Scan the entire page and list every distinct source of information:
- Title block (caixetí) — usually at the bottom, contains project metadata
- Planning/normativa table — comparing urbanistic limits vs project values
- Site plan drawing — with dimensions, parcel boundaries
- Area tables (quadre de superfícies) — per-floor surface breakdowns
- Section/alzat — showing building height and floor count
- Any other tables, legends, annotations, cadastral references

STEP 2 — EXTRACT RAW DATA FROM THE PLANNING TABLE:
If a planning table exists ("NORMATIVA URBANÍSTICA", "JUSTIFICACIÓ PLANEJAMENT",
"PARÀMETRES URBANÍSTICS", or similar), it typically has TWO columns:
  - Left: "Planejament" / "Ordenació" — urbanistic LIMITS (min/max from regulations)
  - Right: "Projecte" — ACTUAL project values ← THIS is what matters for us
Read EVERY row of BOTH columns and transcribe them into "planning_table_raw".
This is critical — do not skip this step even if the table text is small.

STEP 3 — EXTRACT DATA FROM THE TITLE BLOCK (CAIXETÍ):
Look for (may be in ANY corner or edge of the page):
- Project name/type → "project_name"
- Building type → "building_type": SHORT description (1-4 words: "habitatge unifamiliar aïllat",
  "nau industrial", "viviendas adosadas"). NOT the study title, just the building type.
- Location → "street_address": street + number (WITHOUT postal code or municipality).
  IMPORTANT: include the house/plot number (nº, num, s/n) if visible.
  Get this from the EMPLAÇAMENT field in the caixetí, not from maps or comarca names.
- Municipality → "municipality": town name only (no postal code, no province)
- Promotor / Client → "promotor" and "client_name": Look for "Promotor:", "Promotors:",
  "Client:", "Propietari:", "A petició de:". Person or company name, no titles (Sr/Sra).
- Architect → "architect": name (and college number if visible)
- Architect firm → "architect_company": studio/firm name (may be logo or letterhead)

STEP 4 — MAP TO VARIABLES:
Using data from Steps 2-3, assign values. ALWAYS prefer PROJECTE column over Planejament:
- parcel_area_m2: from PROJECTE column (actual parcel), NOT minimum from planejament
- building_footprint_m2: "ocupació", "sup. construïda" from PROJECTE column. If only percentage,
  calculate: percentage × parcel_area_m2
- num_floors: from PROJECTE column. Format as written ("PB", "PB+PP", "Pb+1Pp", "Ps+PB+2Pp")
- max_height_m: "alçada reguladora", "H. max" from PROJECTE column (meters)
- floor_surfaces: per-floor areas from area tables (if present on any page)
- plot_length_m, plot_width_m: from drawing annotations or table

EXTRACTION RULES:
1. Extract text EXACTLY as written (Catalan or Spanish — do not translate)
2. For dimensions, prefer values with explicit units (m, m²)
3. If a value appears in BOTH planning table AND drawing, prefer the PROJECTE column
4. Set null for fields not found — this is fine, not every plan has every field
5. Per-floor surfaces: each floor as a SEPARATE entry. Never combine floors.
6. CRITICAL: Do NOT leave num_floors or max_height_m empty if a planning table exists.

CONFIDENCE & SOURCE:
- 1.0: Clear printed text — 0.9: Readable — 0.7-0.8: Small or requires interpretation — 0.5: Difficult
- Always indicate "source" for dimensions: "Projecte column", "drawing annotation", "area table"

OUTPUT FORMAT (JSON):
{PLANOL_JSON_EXAMPLE}

Be thorough. Check every corner of every page. The planning table is CRITICAL — do not skip it.'''


# ============================================================================
# Projecte Arquitecte — Multi-page project document extraction
# ============================================================================

PROJECTE_ARQUITECTE_JSON_EXAMPLE = '''
{
  "pages_inventory": {"1": "cover + title block", "3": "normativa table + areas", "7": "sections"},
  "planning_table_raw": {
    "planejament": {"parcel_min": "600 m2", "occupancy": "30%", "floors": "PB+PP", "height": "6.60 m"},
    "projecte": {"parcel": "995 m2", "occupancy": "296.88 m2", "floors": "PB+PP", "height": "6.88 m"}
  },
  "architect_data": {
    "project_name": "Habitatge Unifamiliar Aïllat",
    "building_type": "habitatge unifamiliar aïllat",
    "client_name": "NOM CLIENT",
    "promotor": "NOM PROMOTOR",
    "street_address": "C/ Example nº 12",
    "municipality": "Linyola",
    "architect": "Nom Arquitecte",
    "architect_company": "Nom Estudi",
    "ref_cadastral": "1234567AB1234N0001AB"
  },
  "dimensions": {
    "parcel_area_m2": {"value": 995.0, "confidence": 0.95, "source": "normativa table p3", "page": 3},
    "building_footprint_m2": {"value": 296.88, "confidence": 0.90, "source": "area table p5", "page": 5},
    "total_built_area_m2": {"value": 450.0, "confidence": 0.90, "source": "area table p5", "page": 5},
    "floor_surfaces": [
      {"floor": "PB", "area_m2": 297.0, "confidence": 0.90, "page": 5},
      {"floor": "P1", "area_m2": 110.0, "confidence": 0.90, "page": 5}
    ],
    "num_floors": {"value": "PB+PP", "confidence": 1.0, "source": "normativa table p3", "page": 3},
    "max_height_m": {"value": 6.88, "confidence": 0.95, "source": "normativa table p3", "page": 3},
    "plot_length_m": {"value": 24.57, "confidence": 0.90, "page": 2},
    "plot_width_m": {"value": 24.72, "confidence": 0.90, "page": 2}
  },
  "overall_confidence": 0.90,
  "extraction_notes": "Multi-page project document. Normativa table on page 3."
}
'''

PROJECTE_ARQUITECTE_EXTRACTION_PROMPT = f'''You are a senior architect reviewing a multi-page project document (projecte bàsic / projecte executiu).

TASK: Scan ALL pages and extract project data. This is NOT a single-page plan — it's a complete
project booklet with multiple sections across pages (cover, normativa tables, floor plans, sections, details).

STEP 1 — PAGE-BY-PAGE SCAN:
For each page, briefly note what it contains:
- Cover page (portada): project name, client, architect
- Planning/normativa table: urbanistic limits vs project values
- Floor plans (plantes): room layouts, dimensions
- Area tables (quadre de superfícies): per-floor surface breakdowns
- Sections/alzats: building height, floor-to-floor heights
- Site plan (emplaçament): parcel boundaries, orientation
- Detail pages: structural details, installations
Record this in "pages_inventory" (page number → content type).

STEP 2 — EXTRACT FROM NORMATIVA/PLANNING TABLE:
Find the table comparing urbanistic limits ("Planejament") vs actual project values ("Projecte").
May appear as "NORMATIVA URBANÍSTICA", "JUSTIFICACIÓ PLANEJAMENT", "PARÀMETRES URBANÍSTICS".
It typically has TWO columns:
  - Left: "Planejament" / "Ordenació" — urbanistic LIMITS (min/max from regulations)
  - Right: "Projecte" — ACTUAL project values ← THIS is what matters
Read EVERY row of BOTH columns into "planning_table_raw". Do NOT summarize — transcribe each row.

STEP 3 — EXTRACT FROM TITLE BLOCK / COVER:
- project_name, building_type (1-4 words: "habitatge unifamiliar aïllat", "nau industrial")
- client_name, promotor
- street_address (street + number, NO postal code/municipality)
- municipality (town name only)
- architect, architect_company
- ref_cadastral (if visible)

STEP 4 — EXTRACT FROM AREA TABLES / DRAWINGS:
- parcel_area_m2: actual parcel surface
- building_footprint_m2: "ocupació", "sup. construïda en planta"
- total_built_area_m2: total constructed surface (all floors)
- floor_surfaces: per-floor areas
- num_floors: as written ("PB", "PB+PP", "Ps+PB+2Pp")
- max_height_m: "alçada reguladora", "H. max" in meters
- plot_length_m, plot_width_m: from drawing annotations

EXTRACTION RULES:
1. Extract text EXACTLY as written (Catalan or Spanish — do not translate)
2. CRITICAL — Planejament vs Projecte: The planning table has TWO columns.
   "Planejament" shows REGULATORY LIMITS (minimums/maximums from urban code).
   "Projecte" shows ACTUAL PROJECT VALUES (what the architect designed).
   For dimensions (parcel_area, num_floors, max_height), ALWAYS use the PROJECTE column.
   The Planejament column may show higher/lower values — those are limits, NOT the project.
3. If same data appears on multiple pages, prefer the most detailed/precise source
4. Set null for fields not found
5. CRITICAL: Check ALL pages — the data may be on page 5, 8, or later

CONFIDENCE:
- 1.0: Clear printed text — 0.9: Readable — 0.7-0.8: Small/interpretation needed — 0.5: Difficult

OUTPUT FORMAT (JSON):
{PROJECTE_ARQUITECTE_JSON_EXAMPLE}

Be thorough. Scan EVERY page. The most valuable data is often NOT on page 1.'''


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


# ============================================================================
# Pressupost — Budget document extraction (Via B2)
# Champion-challenger: output goes to pressupost_extracted.json.
# No consumer reads this file yet — it exists for A-vs-B comparison only.
# ============================================================================

PRESSUPOST_JSON_EXAMPLE = '''
{
  "source_file": "PRESSUPOST GEOTEC.CASTELLAR DEL VALLES.pdf",
  "overall_confidence": 0.95,
  "fields": {
    "site_address": {
      "value": "C/ARBRELLS 18A",
      "confidence": 0.95,
      "note": null
    },
    "municipality": {
      "value": "CASTELLAR DEL VALLES",
      "confidence": 0.95,
      "note": null
    },
    "client_name": {
      "value": "ARQUITECTURA BOSCH NOVELL",
      "confidence": 0.90,
      "note": "From CLIENT section header"
    },
    "building_category": {
      "value": "C1",
      "confidence": 0.85,
      "note": null
    },
    "num_planned_dpsh": {
      "value": 4,
      "confidence": 1.0,
      "note": "From campaign sentence and/or line-item table"
    },
    "num_planned_spt": {
      "value": 1,
      "confidence": 1.0,
      "note": null
    },
    "num_planned_sondeig": {
      "value": 0,
      "confidence": 1.0,
      "note": null
    }
  },
  "extraction_notes": "Vectorial PDF. OBRA block clear. Campaign sentence found on page 2."
}
'''

PRESSUPOST_EXTRACTION_PROMPT = f'''Analyze this geotechnical study budget document (pressupost / presupuesto geotècnic).

TASK: Extract project and campaign data from the budget document into structured JSON.

DOCUMENT STRUCTURE:
The budget typically has 3-4 pages:
- Page 1: Reference number, date, OBRA block (project site), CLIENT block (client details)
- Page 2: Study description, site characterization, campaign description with quantities
- Page 3-4: Line-item table with unit quantities and prices (ASSAIGS DPSH, SPT, etc.)

STEP 1 — EXTRACT FROM THE OBRA BLOCK (page 1):
The OBRA block starts with a line "OBRA:" and contains:
  Line 1 (optional): client or firm name
  Line 2: project type — "ESTUDI GEOTECNIC", "ESTUDIO GEOTECNICO", "ESTUDI GEOTECNIC 3HAB.", etc.
  Line 3 (optional): street address — e.g. "C/ARBRELLS 18A", "C/ STA. GEMMA 4, URB.LA SERRA"
  Last line: municipality — e.g. "CASTELLAR DEL VALLES", "ANCILES (HUESCA)"
The block ends when you reach a line starting the next section (e.g. "CLIENT:", "CP I POBLACIÓ:").

Rules:
- "ESTUDI GEO" / "ESTUDIO GEO" line is the project-type marker; extract what comes AFTER it.
- If the line AFTER the project-type looks like a street address → `site_address`
- The LAST non-empty line before the end marker → `municipality`
- If there is NO street line (only municipality after project-type) → `site_address` = null

STEP 2 — EXTRACT FROM THE CLIENT BLOCK (page 1):
The CLIENT block starts with "CLIENT" or "CLIENTE" and contains the client's name, address, phone.
The line immediately after "CLIENT" (or "CLIENTE") is the client or firm name → `client_name`.
Do NOT confuse this with the OBRA block content.

STEP 3 — EXTRACT BUILDING CATEGORY (page 2, if present):
Look for "Categoria de construcció:" / "Categoría de construcción:" followed by C0, C1, C2, or C3.
If not found, set `building_category` = null.

STEP 4 — EXTRACT CAMPAIGN QUANTITIES:
Source A — Prose campaign sentence (page 2, most reliable):
  "s'ha previst la realització de la següent campanya de camp:"
  or "se ha previsto la realización de la siguiente campaña de campo:"
  followed by lines like:
    "N assaigs de penetració dinàmica DPSH"
    "N assaig(s) SPT, amb recuperació de mostra"
    "N sondeig(s) a rotació"
  Extract the integer N for each type.

Source B — Line-item table (pages 3-4, cross-check):
  Look for section "ASSAIGS DPSH'S:" / "PENETRÓMETROS DINÁMICOS:"
  The quantity column shows values like "3,00" (= 3 tests).
  WARNING: PDF text extraction may scramble column order in this table — prefer Source A
  when both are present. Use Source B only to confirm or fill gaps.

Rules for campaign fields:
- If a test type is not mentioned at all → value = 0
- If mentioned but quantity illegible → value = null with a note
- Integer values only (never "3,00" — strip the decimal)

EXTRACTION RULES:
1. Extract text EXACTLY as written (Catalan or Spanish — do not translate)
2. `site_address` is the street line only (no municipality, no postal code)
3. `municipality` is the town name only (strip postal code; keep province in parentheses if present,
   e.g. "ANCILES (HUESCA)" is a valid municipality value)
4. Do NOT fall back to municipality when street is absent — `site_address` = null is correct
5. Set null for any field not found — do not fabricate values

CONFIDENCE SCORING:
- 1.0: Clear printed text, unambiguous
- 0.9: Readable with minor uncertainty
- 0.7-0.8: Some interpretation needed (e.g. abbreviations, unclear layout)
- < 0.7: Uncertain — add an explanatory note

OUTPUT FORMAT (JSON):
{PRESSUPOST_JSON_EXAMPLE}

Output ONLY the JSON object, no surrounding text.'''


if __name__ == '__main__':
    print("=== G3DT Extraction Prompts ===\n")
    print("DPSH_EXTRACTION_PROMPT:")
    print("-" * 40)
    print(DPSH_EXTRACTION_PROMPT[:500] + "...")
    print("\nSONDEIG_EXTRACTION_PROMPT:")
    print("-" * 40)
    print(SONDEIG_EXTRACTION_PROMPT[:500] + "...")
