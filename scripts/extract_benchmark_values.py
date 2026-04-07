#!/usr/bin/env python3
"""Extract structured benchmark values from reference text files via Claude API.

Reads docs/benchmarks/{expedient}-text.txt files (produced by extract_reference_text.py),
sends each to Claude for structured extraction, and writes per-project benchmark JSON
plus an _index.json.

Usage:
    python scripts/extract_benchmark_values.py
    python scripts/extract_benchmark_values.py --dry-run
    python scripts/extract_benchmark_values.py --project 4001612
    python scripts/extract_benchmark_values.py --force
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import os

from anthropic import Anthropic

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_env():
    """Load .env file from project root if it exists."""
    env_path = _PROJECT_ROOT / '.env'
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, value = line.partition('=')
                os.environ.setdefault(key.strip(), value.strip())
BENCHMARKS_DIR = _PROJECT_ROOT / "docs" / "benchmarks"

MODEL = "claude-sonnet-4-6"

# Same list as extract_reference_text.py
PROJECTS = [
    ("3001621", "Castellar del Valles", "3001621_informe_v0.docx"),
    ("3001631", "Rubi", "3001631_informe.docx"),
    ("4001607", "Linyola", "4001607_informe.docx"),
    ("4001612", "Bell-Lloc", "4001612_informe.docx"),
    ("4001670", "Alcoletge", "4001670_informe.docx"),
    ("4001671", "Vilanova de Segria", "4001671_informe.docx"),
    ("4001679", "Anciles", "4001679_informe_V0.docx"),
]

# Scalar variable keys to extract, grouped by category with descriptions.
# Skips array fields (dpsh_tests, sondeig_tests, geology_paragraphs,
# soil_level_rows, perm_rows).
EXTRACTION_VARIABLES: dict[str, list[tuple[str, str]]] = {
    "Identificacio": [
        ("client", "Client or promotor name"),
        ("expedient", "Expedient number (e.g. 4001612)"),
        ("architect_name", "Architect full name"),
        ("architect_company", "Architect company or practice name"),
        ("data_camp_text", "Fieldwork date(s) as text"),
        ("data_signatura_text", "Report signature/signing date as text"),
    ],
    "Ubicacio": [
        ("street_address", "Street address of the site"),
        ("municipality", "Municipality name"),
        ("location_sentence", "Full sentence describing the site location"),
        ("adjacent_north", "What borders the site to the north"),
        ("adjacent_south", "What borders the site to the south"),
        ("adjacent_east", "What borders the site to the east"),
        ("adjacent_west", "What borders the site to the west"),
    ],
    "Edificacio": [
        ("building_type", "Type of building (e.g. habitatge unifamiliar)"),
        ("num_floors", "Number of floors (integer)"),
        ("superficie_construida", "Built surface area in m2 (number)"),
        ("superficie_parcela", "Plot surface area in m2 (number)"),
        ("cota_referencia", "Reference elevation in meters (number)"),
        ("site_condition", "Current condition of the terrain/site"),
        ("site_description", "Description of the site/plot"),
        ("access_description", "Description of how to access the site"),
    ],
    "Camp DPSH": [
        ("num_dpsh_tests", "Number of DPSH tests performed (integer)"),
        ("dpsh_test_ids", "DPSH test identifiers as comma-separated string"),
        ("dpsh_avg_n20", "Average N20 value across DPSH tests (number)"),
    ],
    "Camp Lab": [
        ("sulfate_value", "Sulfate content in mg/kg (number)"),
    ],
    "Geologia": [
        ("radon_zone", "Radon zone classification (e.g. Zona I, Zona II)"),
        ("seismic_ab_text", "Seismic coefficient ab text (e.g. ab < 0.04g)"),
    ],
    "Geotecnia": [
        ("geotech_density", "Soil density gamma in t/m3 or kN/m3 (number)"),
        ("geotech_cohesion", "Cohesion c in kg/cm2 (number)"),
        ("geotech_phi", "Friction angle phi in degrees (number)"),
        ("geotech_E", "Deformation modulus E in kg/cm2 (number)"),
        ("geotech_nb", "Nb value - bearing capacity blow count (number)"),
    ],
    "Calculs": [
        ("qa_value", "Allowable bearing capacity Qa in kg/cm2 (number)"),
        ("settlement", "Predicted settlement in cm (number)"),
        ("k30_value", "Subgrade reaction coefficient K30 in kg/cm3 (number)"),
    ],
}


def _build_extraction_prompt(text: str) -> str:
    """Build the structured extraction prompt for Claude."""
    variable_lines: list[str] = []
    for category, variables in EXTRACTION_VARIABLES.items():
        variable_lines.append(f"\n## {category}")
        for key, description in variables:
            variable_lines.append(f"- **{key}**: {description}")

    variables_block = "\n".join(variable_lines)

    return f"""You are extracting structured data from a Catalan geotechnical report.

Below is the full text of the report (paragraphs and tables). Extract the value for each variable listed below.

**Rules:**
1. Return numeric values as numbers (int or float), not strings. E.g. 2.98, not "2.98".
2. Return text values as strings.
3. Return null for any value you cannot find in the document.
4. For geotechnical parameters (geotech_density, geotech_cohesion, geotech_phi, geotech_E, geotech_nb, qa_value, settlement, k30_value), look in the "Parametres geotecnics" table, the "Capacitat portant" section, and the "Assentament" section.
5. For adjacents (adjacent_north/south/east/west), look for "Limita al nord amb...", "Limita al sud amb...", etc. or similar boundary descriptions.
6. dpsh_avg_n20 is the average of N20 blow counts across all DPSH penetration tests.
7. For each extracted value, provide a short note explaining where in the document you found it.

**Variables to extract:**
{variables_block}

**Return ONLY a JSON object** with this exact structure (no markdown fences, no extra text):
{{
  "variables": {{
    "client": <value or null>,
    "expedient": <value or null>,
    ...all keys listed above...
  }},
  "notes": {{
    "client": "Found in header: 'Promotor: ...'",
    ...one note per extracted key (skip keys where value is null)...
  }}
}}

---
DOCUMENT TEXT:
{text}"""


def _parse_response_json(response_text: str) -> dict[str, Any]:
    """Parse JSON from Claude's response, stripping markdown fences if present."""
    text = response_text.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline == -1:
            text = text.strip("`").strip()
        else:
            last_fence = text.rfind("```")
            text = text[first_newline + 1:last_fence].strip()
    return json.loads(text)


def extract_one(
    client: Anthropic,
    expedient: str,
    municipality: str,
    source_docx: str,
    text: str,
) -> dict[str, Any]:
    """Call Claude API to extract benchmark values from one project's text."""
    prompt = _build_extraction_prompt(text)

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = response.content[0].text
    parsed = _parse_response_json(response_text)

    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens

    return {
        "expedient": expedient,
        "municipality": municipality,
        "source": source_docx,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "variables": parsed.get("variables", {}),
        "notes": parsed.get("notes", {}),
        "_usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract benchmark values from reference text files via Claude API",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be extracted without calling the API",
    )
    parser.add_argument(
        "--project",
        type=str,
        default=None,
        help="Process a single project by expedient number (e.g. 4001612)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing benchmark JSON files",
    )
    args = parser.parse_args()

    if not BENCHMARKS_DIR.exists():
        print(f"ERROR: Benchmarks directory not found: {BENCHMARKS_DIR}")
        print("Run scripts/extract_reference_text.py first.")
        sys.exit(1)

    projects = PROJECTS
    if args.project:
        projects = [(e, m, s) for e, m, s in PROJECTS if e == args.project]
        if not projects:
            print(f"ERROR: Unknown expedient '{args.project}'")
            print(f"Available: {', '.join(e for e, _, _ in PROJECTS)}")
            sys.exit(1)

    # Collect work items
    work: list[tuple[str, str, str, Path]] = []
    for expedient, municipality, source_docx in projects:
        text_path = BENCHMARKS_DIR / f"{expedient}-text.txt"
        if not text_path.exists():
            print(f"  SKIP {expedient} ({municipality}): {text_path.name} not found")
            continue

        out_path = BENCHMARKS_DIR / f"{expedient}-benchmark.json"
        if out_path.exists() and not args.force:
            print(f"  SKIP {expedient} ({municipality}): {out_path.name} already exists (use --force)")
            continue

        work.append((expedient, municipality, source_docx, text_path))

    if not work:
        print("\nNothing to process.")
        return

    # Cost estimate
    all_keys = []
    for variables in EXTRACTION_VARIABLES.values():
        all_keys.extend(k for k, _ in variables)
    num_keys = len(all_keys)

    print(f"\nProjects to process: {len(work)}")
    print(f"Variables per project: {num_keys}")
    print(f"Model: {MODEL}")

    total_chars = sum(p.read_text(encoding="utf-8").__len__() for _, _, _, p in work)
    est_input_tokens = total_chars // 3  # rough chars-to-tokens
    est_cost = (est_input_tokens * 3.0 / 1_000_000) + (len(work) * 4096 * 15.0 / 1_000_000)
    print(f"Estimated input: ~{est_input_tokens:,} tokens across {len(work)} calls")
    print(f"Estimated cost: ~${est_cost:.3f}")

    if args.dry_run:
        print("\n--- DRY RUN ---")
        for expedient, municipality, source_docx, text_path in work:
            text = text_path.read_text(encoding="utf-8")
            chars = len(text)
            lines = text.count("\n")
            print(f"  {expedient} ({municipality}): {chars:,} chars, {lines} lines -> {expedient}-benchmark.json")
        print(f"\nWould extract {num_keys} variables per project.")
        print("Keys:", ", ".join(all_keys))
        return

    # Real extraction
    _load_env()
    client = Anthropic()
    results: list[dict[str, Any]] = []
    total_input = 0
    total_output = 0

    for idx, (expedient, municipality, source_docx, text_path) in enumerate(work, 1):
        text = text_path.read_text(encoding="utf-8")
        print(f"\n[{idx}/{len(work)}] {expedient} ({municipality})...", end=" ", flush=True)

        try:
            result = extract_one(client, expedient, municipality, source_docx, text)

            out_path = BENCHMARKS_DIR / f"{expedient}-benchmark.json"
            out_path.write_text(
                json.dumps(result, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            usage = result.get("_usage", {})
            inp = usage.get("input_tokens", 0)
            out = usage.get("output_tokens", 0)
            total_input += inp
            total_output += out

            num_filled = sum(1 for v in result["variables"].values() if v is not None)
            num_total = len(result["variables"])
            print(f"{num_filled}/{num_total} values extracted ({inp}+{out} tokens) -> {out_path.name}")

            results.append({
                "expedient": expedient,
                "municipality": municipality,
                "file": f"{expedient}-benchmark.json",
            })

        except Exception as e:
            print(f"ERROR: {e}")
            continue

        # Rate limit between calls
        if idx < len(work):
            time.sleep(1)

    # Write index
    if results:
        index = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "projects": results,
        }
        index_path = BENCHMARKS_DIR / "_index.json"
        index_path.write_text(
            json.dumps(index, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"\nIndex written: {index_path}")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Processed: {len(results)}/{len(work)} projects")
    print(f"Total tokens: {total_input:,} input + {total_output:,} output")
    actual_cost = (total_input * 3.0 / 1_000_000) + (total_output * 15.0 / 1_000_000)
    print(f"Estimated cost: ${actual_cost:.4f}")
    print(f"Output: {BENCHMARKS_DIR}/")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
