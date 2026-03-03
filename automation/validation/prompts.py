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
6. Note any refusal (R marker or N20 >= 100)
7. Note water level if indicated

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
      "layers": [
        {
          "depth_from_m": 0.0,
          "depth_to_m": 0.5,
          "description": "Terra vegetal",
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
          "uscs_classification": "CL",
          "color": "marro clar",
          "moisture": "humit",
          "consistency": "ferma",
          "density": null,
          "confidence": 0.9,
          "note": "USCS classification uncertain"
        }
      ],
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

EXTRACTION RULES:
1. For each borehole, extract ALL soil layers from surface to final depth
2. Depths should be continuous (each layer's depth_to_m = next layer's depth_from_m)
3. Extract soil descriptions in Catalan as written
4. Note USCS classification if visible (typically in a separate column)
5. Moisture states: sec, humit, saturat
6. Consistency (cohesive soils): tova, ferma, dura
7. Density (granular soils): fluixa, mitja, densa
8. Mark uncertain values with appropriate confidence scores

CONFIDENCE SCORING:
- 1.0: Clear, unambiguous description
- 0.7-0.9: Readable but some uncertainty
- 0.5-0.7: Partially legible
- <0.5: Uncertain
- 0.0: Illegible

OUTPUT FORMAT (JSON):
{SONDEIG_JSON_EXAMPLE}

Extract all soil layer information from this document. Be thorough and note any uncertainties.'''


# ============================================================================
# Plànol (A.01.pdf) — Architect plan extraction
# ============================================================================

PLANOL_JSON_EXAMPLE = '''
{
  "architect_data": {
    "source_file": "A.01.pdf",
    "project_name": "Habitatge Unifamiliar Aïllat",
    "location": "C/ Mestre Ramon Ortiz, 25220 Bell-Lloc d'Urgell",
    "promotor": "Ramon Mitjana SL",
    "architect": "Jordi Bosch Novell",
    "architect_company": "Bosch Arquitectura SLP",
    "dimensions": {
      "parcel_area_m2": {"pdf_value": 598.0, "confidence": 0.95},
      "building_footprint_m2": {"pdf_value": 296.88, "confidence": 0.90},
      "num_floors": {"pdf_value": "Pb+P1", "confidence": 1.0},
      "max_height_m": {"pdf_value": 8.38, "confidence": 0.85},
      "plot_length_m": {"pdf_value": 24.57, "confidence": 0.90},
      "plot_width_m": {"pdf_value": 24.72, "confidence": 0.90}
    }
  },
  "overall_confidence": 0.90,
  "extraction_notes": "Caixetí clear, dimensions from site plan"
}
'''

PLANOL_EXTRACTION_PROMPT = f'''Analyze this architectural plan (plànol) for a construction project.

TASK: Extract project and building data into structured JSON.

DOCUMENT STRUCTURE:
- Caixetí/title block (typically bottom-right corner):
  - Project name/type (e.g., "Habitatge Unifamiliar Aïllat", "Nau Industrial")
  - Location: street, number, postal code, municipality
  - Promotor: company or individual name
  - Architect: name and college number
  - Architect company: SLP or firm name (may be separate from architect name)
  - Scale, date
- Site plan / emplaçament:
  - Parcel area in m²
  - Parcel dimensions (length × width)
  - Building footprint in m² or percentage
- Section / alzat:
  - Number of floors (PB, PB+1, Ps+PB+2Pp, etc.)
  - Maximum building height in meters

EXTRACTION RULES:
1. Extract text EXACTLY as written (Catalan/Spanish)
2. For dimensions, prefer values with explicit units (m, m²)
3. Number of floors: use the format as written (e.g., "Pb+P1", "Ps+Pb+2Pp")
4. If a value has multiple interpretations, use the most specific one
5. Set null for fields not found in the document
6. Building footprint may be labeled "ocupació", "superfície construïda", or similar
7. If architect_company is not separately listed, set null (do not guess from architect name)

CONFIDENCE SCORING:
- 1.0: Clear printed text, unambiguous
- 0.9: Readable with minimal uncertainty
- 0.7-0.8: Readable but small text or requires interpretation
- 0.5: Difficult to read or ambiguous
- Use null for values not found

OUTPUT FORMAT (JSON):
{PLANOL_JSON_EXAMPLE}

Extract all visible data from this architectural plan.'''


# System prompt for general extraction context
EXTRACTION_SYSTEM_PROMPT = '''You are a geotechnical data extraction specialist. Your task is to
carefully extract data from handwritten field documents and convert them to structured JSON.

KEY PRINCIPLES:
1. ACCURACY: Only extract what you can clearly see. Never guess or fabricate values.
2. UNCERTAINTY: Mark uncertain values with lower confidence scores.
3. COMPLETENESS: Extract ALL data visible in the document.
4. STRUCTURE: Follow the exact JSON format specified.

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
