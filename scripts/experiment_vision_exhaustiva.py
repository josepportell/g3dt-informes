#!/usr/bin/env python3
"""
Experiment: Exhaustive Vision — Send ALL pages of multi-page PDFs to vision.

Tests the hypothesis from PLA-VISION-EXHAUSTIVA-FITXERS.md:
- Positive tests: rich architect project PDFs contain critical data (surfaces, height, floors)
- Negative test: budget PDFs should NOT generate false architect data

Usage:
    .venv/bin/python scripts/experiment_vision_exhaustiva.py [--test linyola|anciles|castellar|all]
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import sys
import time
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from automation import config

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Test files ──────────────────────────────────────────────────────────────

TESTS = {
    "linyola": {
        "label": "Linyola — Projecte arquitecte (11p, positive)",
        "pdf": PROJECT_ROOT / "reference-material/4001607 LINYOLA/25.0616/2_02B_DG_Silvia_Jaume.pdf",
        "eva": PROJECT_ROOT / "reference-material/4001607 LINYOLA/validation/eva_reference_values.json",
        "expect_data": True,
    },
    "anciles": {
        "label": "Anciles — Planos completos (35p, positive)",
        "pdf": PROJECT_ROOT / "reference-material/4001679 ANCILES/24.0807/IV_PLANOS.pdf",
        "eva": PROJECT_ROOT / "reference-material/4001679 ANCILES/validation/eva_reference_values.json",
        "expect_data": True,
    },
    "castellar": {
        "label": "Castellar — Pressupost geotec (7p, negative)",
        "pdf": PROJECT_ROOT / "reference-material/3001621 CASTELLAR DEL VALLES/25.0493/PRESSUPOST GEOTEC.CASTELLAR DEL VALLES.pdf",
        "eva": PROJECT_ROOT / "reference-material/3001621 CASTELLAR DEL VALLES/validation/eva_reference_values.json",
        "expect_data": False,
    },
}

# ── Prompt for multi-page architect project documents ───────────────────────

PROJECTE_ARQUITECTE_PROMPT = """You are a senior architect reviewing a multi-page project document (projecte bàsic / projecte executiu).

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
Read EVERY row of BOTH columns into "planning_table_raw".

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
2. Prefer "Projecte" column values over "Planejament" limits
3. If same data appears on multiple pages, prefer the most detailed/precise source
4. Set null for fields not found
5. CRITICAL: Check ALL pages — the data may be on page 5, 8, or later

CONFIDENCE:
- 1.0: Clear printed text — 0.9: Readable — 0.7-0.8: Small/interpretation needed — 0.5: Difficult

OUTPUT FORMAT (JSON):
{
  "pages_inventory": {"1": "cover + title block", "2": "site plan", "3": "normativa table + areas"},
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
  "extraction_notes": "Multi-page project. Normativa table on page 3, area breakdown on page 5."
}

Be thorough. Scan EVERY page. The most valuable data is often NOT on page 1."""

SYSTEM_PROMPT = """You are a geotechnical data extraction specialist. Extract structured data from
architectural and project documents into JSON. Only extract what you can clearly see. Mark uncertain
values with lower confidence. Set null for fields not found."""


# ── PDF rendering ───────────────────────────────────────────────────────────

def render_pdf_to_images(pdf_path: Path, dpi: int | None = None, max_pages: int = 50) -> list[str]:
    """Render PDF pages to base64 JPEG images. Returns list of base64 strings.

    DPI auto-scales based on page count: 200 for <=10p, 150 for <=25p, 120 for >25p.
    """
    import fitz

    doc = fitz.open(str(pdf_path))
    total = len(doc)
    truncated = total > max_pages
    pages_to_render = min(total, max_pages)

    # Auto-scale DPI based on page count
    if dpi is None:
        if pages_to_render <= 10:
            dpi = 200
        elif pages_to_render <= 25:
            dpi = 150
        else:
            dpi = 120
    logger.info("Rendering %d pages at %d DPI", pages_to_render, dpi)

    images = []
    try:
        for page_num in range(pages_to_render):
            page = doc[page_num]
            zoom = dpi / 72
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes(output="jpeg", jpg_quality=80)

            # 4MB limit — reduce quality
            if len(img_bytes) > 4 * 1024 * 1024:
                zoom = 120 / 72
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)
                img_bytes = pix.tobytes(output="jpeg", jpg_quality=70)

            images.append(base64.b64encode(img_bytes).decode("utf-8"))
    finally:
        doc.close()

    if truncated:
        logger.warning("PDF truncated: %d/%d pages rendered (max_pages=%d)", max_pages, total, max_pages)

    total_mb = sum(len(b64) * 3 / 4 for b64 in images) / (1024 * 1024)
    logger.info("Total image payload: %.1f MB (%d images)", total_mb, len(images))

    return images


def get_pdf_metadata(pdf_path: Path) -> dict:
    """Extract PDF metadata using PyMuPDF."""
    import fitz

    doc = fitz.open(str(pdf_path))
    meta = doc.metadata or {}
    info = {
        "pages": len(doc),
        "size_mb": round(pdf_path.stat().st_size / (1024 * 1024), 2),
        "creator": meta.get("creator", ""),
        "author": meta.get("author", ""),
        "producer": meta.get("producer", ""),
        "title": meta.get("title", ""),
    }
    doc.close()
    return info


# ── Vision API call ─────────────────────────────────────────────────────────

def call_openai_vision(prompt: str, images: list[str], system_prompt: str) -> tuple[dict | None, dict]:
    """Call OpenAI gpt-4.1-mini with images. Returns (result, usage_info)."""
    import httpx

    api_key = config.OPENAI_API_KEY
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    model = config.VISION_MODEL_OPENAI

    content: list[dict] = [{"type": "text", "text": prompt}]
    for b64_img in images:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"},
        })

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ],
        "temperature": 0.0,
        "max_tokens": 4096,
        "response_format": {"type": "json_object"},
    }

    t0 = time.monotonic()
    # Large payloads (35+ pages) need longer write timeout
    timeout = httpx.Timeout(connect=30.0, read=180.0, write=180.0, pool=30.0)
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(
            "https://api.openai.com/v1/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    elapsed_s = time.monotonic() - t0

    if resp.status_code != 200:
        logger.error("OpenAI HTTP %d: %s", resp.status_code, resp.text[:300])
        return None, {"elapsed_s": elapsed_s, "error": resp.text[:300]}

    data = resp.json()
    usage = data.get("usage", {})
    content_str = data["choices"][0]["message"]["content"]
    result = json.loads(content_str)

    usage_info = {
        "model": model,
        "elapsed_s": round(elapsed_s, 1),
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
    }

    # Estimate cost (gpt-4.1-mini: $0.4/M input, $1.6/M output)
    cost_input = usage_info["prompt_tokens"] * 0.4 / 1_000_000
    cost_output = usage_info["completion_tokens"] * 1.6 / 1_000_000
    usage_info["estimated_cost_usd"] = round(cost_input + cost_output, 4)

    return result, usage_info


# ── Comparison with Eva ─────────────────────────────────────────────────────

TARGET_VARS = [
    "superficie_construida", "superficie_parcela", "plantes",
    "municipality", "building_type_lower", "client",
    "architect_name_upper", "architect_company",
]


def compare_with_eva(extracted: dict, eva_path: Path) -> list[dict]:
    """Compare extracted values with Eva's reference. Returns comparison rows."""
    if not eva_path.exists():
        return [{"variable": "N/A", "status": "NO_EVA_FILE"}]

    eva = json.loads(eva_path.read_text(encoding="utf-8"))
    eva_vars = eva.get("variables", {})

    comparisons = []
    dims = extracted.get("dimensions", {})
    arch = extracted.get("architect_data", {})

    # Map extracted fields to Eva variable names
    field_map = {
        "superficie_construida": _get_dim_value(dims, "total_built_area_m2", "building_footprint_m2"),
        "superficie_parcela": _get_dim_value(dims, "parcel_area_m2"),
        "plantes": _get_dim_value(dims, "num_floors"),
        "municipality": arch.get("municipality"),
        "building_type_lower": arch.get("building_type"),
        "client": arch.get("client_name") or arch.get("promotor"),
        "architect_name_upper": arch.get("architect"),
        "architect_company": arch.get("architect_company"),
    }

    for var_name in TARGET_VARS:
        eva_entry = eva_vars.get(var_name)
        extracted_val = field_map.get(var_name)

        if eva_entry is None:
            comparisons.append({
                "variable": var_name,
                "eva": None,
                "extracted": str(extracted_val) if extracted_val else None,
                "status": "NO_EVA_VALUE",
            })
            continue

        eva_val = str(eva_entry.get("value", "")).strip()
        ext_val = str(extracted_val).strip() if extracted_val else ""

        if not ext_val:
            status = "MISSING"
        elif eva_val.lower() == ext_val.lower():
            status = "MATCH"
        elif eva_val.replace(" ", "") == ext_val.replace(" ", ""):
            status = "CLOSE"
        elif _numeric_close(eva_val, ext_val):
            status = "CLOSE"
        else:
            status = "MISMATCH"

        comparisons.append({
            "variable": var_name,
            "eva": eva_val,
            "extracted": ext_val,
            "status": status,
        })

    return comparisons


def _get_dim_value(dims: dict, *keys: str):
    """Get first available value from dimensions dict."""
    for key in keys:
        val = dims.get(key)
        if val is None:
            continue
        if isinstance(val, dict):
            return val.get("value") or val.get("pdf_value")
        return val
    return None


def _numeric_close(a: str, b: str, tolerance: float = 0.05) -> bool:
    """Check if two strings represent close numeric values."""
    try:
        va = float(a.replace(",", ".").replace(">", "").replace("<", ""))
        vb = float(b.replace(",", ".").replace(">", "").replace("<", ""))
        if va == 0 and vb == 0:
            return True
        return abs(va - vb) / max(abs(va), abs(vb)) <= tolerance
    except (ValueError, ZeroDivisionError):
        return False


# ── Main ────────────────────────────────────────────────────────────────────

def run_test(name: str, test: dict) -> dict:
    """Run a single test and return results."""
    pdf_path = test["pdf"]
    label = test["label"]

    print(f"\n{'='*70}")
    print(f"TEST: {label}")
    print(f"FILE: {pdf_path.name}")
    print(f"{'='*70}")

    if not pdf_path.exists():
        print(f"  ERROR: PDF not found at {pdf_path}")
        return {"error": "file_not_found"}

    # 1. Metadata
    meta = get_pdf_metadata(pdf_path)
    print(f"\n  Metadata:")
    print(f"    Pages: {meta['pages']}")
    print(f"    Size: {meta['size_mb']} MB")
    print(f"    Creator: {meta['creator'] or '(empty)'}")
    print(f"    Author: {meta['author'] or '(empty)'}")

    # 2. Render
    t0 = time.monotonic()
    images = render_pdf_to_images(pdf_path, dpi=200, max_pages=50)
    render_s = time.monotonic() - t0
    print(f"\n  Rendered {len(images)} pages in {render_s:.1f}s")

    # 3. Call vision
    print(f"  Sending to {config.VISION_MODEL_OPENAI}...")
    result, usage = call_openai_vision(PROJECTE_ARQUITECTE_PROMPT, images, SYSTEM_PROMPT)

    if result is None:
        print(f"  ERROR: Vision call failed — {usage.get('error', 'unknown')}")
        return {"error": "vision_failed", "usage": usage}

    print(f"\n  Usage:")
    print(f"    Time: {usage['elapsed_s']}s")
    print(f"    Tokens: {usage['prompt_tokens']:,} in + {usage['completion_tokens']:,} out")
    print(f"    Cost: ${usage['estimated_cost_usd']:.4f}")

    # 4. Show pages inventory
    pages_inv = result.get("pages_inventory", {})
    if pages_inv:
        print(f"\n  Pages inventory ({len(pages_inv)} pages described):")
        for pg, desc in sorted(pages_inv.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0):
            print(f"    p{pg}: {desc}")

    # 5. Show key extracted values
    dims = result.get("dimensions", {})
    arch = result.get("architect_data", {})
    print(f"\n  Extracted values:")
    print(f"    building_type: {arch.get('building_type')}")
    print(f"    client: {arch.get('client_name')}")
    print(f"    architect: {arch.get('architect')}")
    print(f"    municipality: {arch.get('municipality')}")
    print(f"    street_address: {arch.get('street_address')}")
    print(f"    ref_cadastral: {arch.get('ref_cadastral')}")

    for dim_name in ["parcel_area_m2", "building_footprint_m2", "total_built_area_m2", "num_floors", "max_height_m"]:
        val = dims.get(dim_name)
        if isinstance(val, dict):
            print(f"    {dim_name}: {val.get('value')} (conf={val.get('confidence')}, source={val.get('source', '?')}, p{val.get('page', '?')})")
        elif val is not None:
            print(f"    {dim_name}: {val}")
        else:
            print(f"    {dim_name}: null")

    # 6. Compare with Eva
    eva_path = test.get("eva")
    if eva_path and Path(eva_path).exists():
        comparisons = compare_with_eva(result, Path(eva_path))
        print(f"\n  Comparison with Eva:")
        for c in comparisons:
            status_icon = {"MATCH": "+", "CLOSE": "~", "MISMATCH": "X", "MISSING": "-", "NO_EVA_VALUE": "?"}
            icon = status_icon.get(c["status"], "?")
            print(f"    [{icon}] {c['variable']}: eva={c.get('eva', 'N/A')} vs extracted={c.get('extracted', 'N/A')} → {c['status']}")

        matches = sum(1 for c in comparisons if c["status"] in ("MATCH", "CLOSE"))
        total = sum(1 for c in comparisons if c["status"] != "NO_EVA_VALUE")
        if total:
            print(f"\n    Score: {matches}/{total} ({100*matches/total:.0f}%)")
    else:
        comparisons = []

    # 7. False positive check for negative tests
    if not test["expect_data"]:
        arch_fields = [v for v in [arch.get("building_type"), arch.get("client_name"),
                                    arch.get("architect")] if v]
        dim_fields = [v for k, v in dims.items()
                      if v is not None and k in ("parcel_area_m2", "building_footprint_m2",
                                                  "num_floors", "max_height_m")]
        if dim_fields:
            print(f"\n  ⚠ FALSE POSITIVE WARNING: {len(dim_fields)} dimension fields extracted from non-architect document!")
        else:
            print(f"\n  NEGATIVE TEST PASSED: No dimension false positives")

    # 8. Save results
    output_dir = PROJECT_ROOT / "docs" / "experiments"
    output_dir.mkdir(exist_ok=True)
    output = {
        "test": name,
        "label": label,
        "pdf": str(pdf_path),
        "metadata": meta,
        "usage": usage,
        "render_seconds": round(render_s, 1),
        "result": result,
        "comparisons": comparisons,
    }
    output_path = output_dir / f"vision_exhaustiva_{name}.json"
    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Results saved: {output_path.relative_to(PROJECT_ROOT)}")

    return output


def main():
    parser = argparse.ArgumentParser(description="Experiment: Exhaustive Vision")
    parser.add_argument("--test", choices=["linyola", "anciles", "castellar", "all"],
                        default="all", help="Which test to run")
    args = parser.parse_args()

    tests_to_run = TESTS if args.test == "all" else {args.test: TESTS[args.test]}

    print("=" * 70)
    print("EXPERIMENT: Exhaustive Vision — Multi-page PDF extraction")
    print(f"Model: {config.VISION_MODEL_OPENAI}")
    print(f"Tests: {', '.join(tests_to_run.keys())}")
    print("=" * 70)

    all_results = {}
    total_cost = 0
    total_time = 0

    for name, test in tests_to_run.items():
        result = run_test(name, test)
        all_results[name] = result
        if "usage" in result:
            total_cost += result["usage"].get("estimated_cost_usd", 0)
            total_time += result["usage"].get("elapsed_s", 0)

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"  Total API time: {total_time:.1f}s")
    print(f"  Total cost: ${total_cost:.4f}")
    print(f"  Tests run: {len(all_results)}")

    for name, result in all_results.items():
        if "error" in result:
            print(f"  {name}: ERROR — {result['error']}")
        else:
            usage = result.get("usage", {})
            comps = result.get("comparisons", [])
            matches = sum(1 for c in comps if c.get("status") in ("MATCH", "CLOSE"))
            total = sum(1 for c in comps if c.get("status") not in ("NO_EVA_VALUE",))
            score = f"{matches}/{total} ({100*matches/total:.0f}%)" if total else "N/A"
            print(f"  {name}: {usage.get('elapsed_s', '?')}s, ${usage.get('estimated_cost_usd', 0):.4f}, score={score}")


if __name__ == "__main__":
    main()
