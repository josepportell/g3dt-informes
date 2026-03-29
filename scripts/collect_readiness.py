#!/usr/bin/env python3
"""Collect report-readiness data for all G3DT projects.

Replicates the /api/report-readiness/{project} endpoint logic
but runs standalone without the web server.

Usage:
    python scripts/collect_readiness.py
    python scripts/collect_readiness.py --output-dir docs/validation-2026-03-27
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path so automation/web imports work
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

# ---------------------------------------------------------------------------
# READINESS_VARIABLES — copied from web/api.py (lines 861-922)
# ---------------------------------------------------------------------------
READINESS_VARIABLES: dict[str, list[dict]] = {
    "Identificacio": [
        {"key": "client", "label": "Client / Promotor"},
        {"key": "expedient", "label": "Expedient"},
        {"key": "architect_name", "label": "Arquitecte"},
        {"key": "architect_company", "label": "Despatx arquitecte"},
        {"key": "data_camp_text", "label": "Data de camp"},
        {"key": "data_signatura_text", "label": "Data signatura"},
    ],
    "Ubicacio": [
        {"key": "street_address", "label": "Adreca"},
        {"key": "municipality", "label": "Municipi"},
        {"key": "location_sentence", "label": "Frase ubicacio"},
        {"key": "adjacent_north", "label": "Limita nord"},
        {"key": "adjacent_south", "label": "Limita sud"},
        {"key": "adjacent_east", "label": "Limita est"},
        {"key": "adjacent_west", "label": "Limita oest"},
    ],
    "Edificacio": [
        {"key": "building_type", "label": "Tipus edifici"},
        {"key": "num_floors", "label": "Plantes"},
        {"key": "superficie_construida", "label": "Sup. construida"},
        {"key": "superficie_parcela", "label": "Sup. parcela"},
        {"key": "cota_referencia", "label": "Cota referencia"},
        {"key": "site_condition", "label": "Estat terreny"},
        {"key": "site_description", "label": "Descripcio solar"},
        {"key": "access_description", "label": "Acces"},
    ],
    "Camp DPSH": [
        {"key": "num_dpsh_tests", "label": "Num. assaigs DPSH", "check": "truthy_nonzero"},
        {"key": "dpsh_test_ids", "label": "IDs assaigs"},
        {"key": "dpsh_avg_n20", "label": "N20 mitja"},
        {"key": "dpsh_tests", "label": "Taula DPSH", "check": "array_filled"},
    ],
    "Camp Sondeig": [
        {"key": "sondeig_tests", "label": "Taula sondeig", "check": "array_filled",
         "conditional": "has_sondeig"},
    ],
    "Camp Lab": [
        {"key": "sulfate_value", "label": "Sulfats (mg/kg)"},
    ],
    "Geologia": [
        {"key": "geology_paragraphs", "label": "Paragrafs geologia", "check": "array_filled"},
        {"key": "radon_zone", "label": "Zona rado"},
        {"key": "seismic_ab_text", "label": "Coeficient sismic ab"},
        {"key": "materials_level_1", "label": "Materials nivell 1"},
    ],
    "Geotecnia": [
        {"key": "geotech_density", "label": "Densitat gamma"},
        {"key": "geotech_cohesion", "label": "Cohesio c"},
        {"key": "geotech_phi", "label": "Angle friccio phi"},
        {"key": "geotech_E", "label": "Modul deformacio E"},
        {"key": "geotech_nb", "label": "Nb"},
        {"key": "soil_level_rows", "label": "Taula nivells sol", "check": "array_filled"},
        {"key": "perm_rows", "label": "Taula permeabilitat", "check": "array_filled"},
    ],
    "Calculs": [
        {"key": "qa_value", "label": "Qa capacitat portant"},
        {"key": "settlement", "label": "Assentament"},
        {"key": "k30_value", "label": "Coef. balast K30"},
    ],
}


def _is_filled(value: Any, check: str = "truthy") -> bool:
    """Check if a template context value is meaningfully filled."""
    if check == "truthy_nonzero":
        return value is not None and value != '' and value != 0 and value != '0'
    if check == "array_filled":
        if not isinstance(value, list) or len(value) == 0:
            return False
        first = value[0]
        if isinstance(first, dict):
            return any(bool(v) for v in first.values())
        return bool(first)
    return bool(value)


def process_project(project_folder: str, *, full_pipeline: bool = False) -> dict[str, Any]:
    """Run readiness check for a single project. Returns the API-equivalent dict."""
    from web import wizard_service
    from automation.report_generator import ReportGenerator

    t0 = time.monotonic()

    project_path = wizard_service._resolve_project(project_folder)

    # Run vision extraction before prefills if full_pipeline requested
    if full_pipeline:
        try:
            from web.vision_groq import groq_available, run_vision_groq_sync
            if groq_available():
                run_vision_groq_sync(project_path)
            else:
                logging.getLogger(__name__).warning(
                    "--full-pipeline: no GROQ_API_KEY, skipping vision for %s", project_folder
                )
        except Exception as e:
            logging.getLogger(__name__).warning("Vision failed for %s: %s", project_folder, e)

    prefills = wizard_service.get_prefills(project_folder)

    user_data_path = project_path / 'user_data.json'
    merged_ud: dict[str, Any] = {}
    if user_data_path.exists():
        try:
            merged_ud = json.loads(user_data_path.read_text(encoding='utf-8'))
        except Exception:
            pass

    for k, v in prefills.items():
        if k.startswith('_'):
            continue
        val = v.get('value') if isinstance(v, dict) else v
        source = v.get('source', '') if isinstance(v, dict) else ''
        if val and k not in merged_ud:
            merged_ud[k] = val
        elif val and source == 'ICGC ortho+visió':
            # Enriched values override non-user entries
            merged_ud[k] = val

    generator = ReportGenerator(project_path=str(project_path), user_data=merged_ud)
    result = generator.build_context_preview()

    ctx = result.context
    categories = []
    total_filled = 0
    total_count = 0

    for cat_name, var_defs in READINESS_VARIABLES.items():
        cat_vars = []
        cat_filled = 0
        cat_total = 0

        for vdef in var_defs:
            key = vdef["key"]
            cond = vdef.get("conditional")
            if cond and not ctx.get(cond):
                continue

            check = vdef.get("check", "truthy")
            value = ctx.get(key)
            filled = _is_filled(value, check)
            cat_total += 1
            if filled:
                cat_filled += 1

            display = ""
            if value is not None:
                if isinstance(value, list):
                    display = f"[{len(value)} items]"
                else:
                    display = str(value)[:120]

            cat_vars.append({
                "key": key,
                "label": vdef["label"],
                "filled": filled,
                "value": display,
            })

        total_filled += cat_filled
        total_count += cat_total
        categories.append({
            "name": cat_name,
            "filled": cat_filled,
            "total": cat_total,
            "pct": round(cat_filled / cat_total * 100, 1) if cat_total else 0,
            "variables": cat_vars,
        })

    elapsed_ms = round((time.monotonic() - t0) * 1000)

    return {
        "overall": {
            "filled": total_filled,
            "total": total_count,
            "pct": round(total_filled / total_count * 100, 1) if total_count else 0,
        },
        "categories": categories,
        "errors": result.errors,
        "warnings": result.warnings,
        "elapsed_ms": elapsed_ms,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect report-readiness data for all G3DT projects")
    parser.add_argument(
        "--output-dir",
        default="docs/validation-latest",
        help="Output directory relative to project root (default: docs/validation-latest)",
    )
    parser.add_argument(
        "--skip-vision",
        action="store_true",
        help="Skip vision extraction (only run auto_extract phases 0-3)",
    )
    parser.add_argument(
        "--project",
        help="Run only this project (expedient or substring, e.g. '4001612' or 'bell-lloc')",
    )
    args = parser.parse_args()

    output_dir = _PROJECT_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    from web.wizard_service import list_projects
    projects = list_projects()

    if not projects:
        print("No projects found in reference-material/")
        sys.exit(1)

    # Filter to single project if requested
    if args.project:
        needle = args.project.lower()
        projects = [p for p in projects if needle in p["folder"].lower() or needle in p["municipality"].lower()]
        if not projects:
            print(f"No project matching '{args.project}'")
            sys.exit(1)

    total = len(projects)
    full_pipeline = not args.skip_vision
    mode = "full pipeline (auto_extract + vision)" if full_pipeline else "auto_extract only (--skip-vision)"
    print(f"Collecting readiness for {total} project(s) ({mode}) -> {output_dir}\n")

    summary_entries: list[dict[str, Any]] = []

    for idx, proj in enumerate(projects, 1):
        folder = proj["folder"]
        municipality = proj["municipality"]

        log_path = output_dir / f"{folder}-log.txt"
        file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)

        try:
            result = process_project(folder, full_pipeline=full_pipeline)

            result_path = output_dir / f"{folder}.json"
            result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

            ov = result["overall"]
            mark = "OK" if ov["pct"] == 100 else f"{ov['pct']}%"
            print(f"[{idx}/{total}] {municipality}... {ov['pct']}% ({ov['filled']}/{ov['total']}) {mark}")

            cat_summary = {}
            for cat in result["categories"]:
                cat_summary[cat["name"]] = {
                    "filled": cat["filled"],
                    "total": cat["total"],
                    "pct": cat["pct"],
                }

            summary_entries.append({
                "folder": folder,
                "municipality": municipality,
                "overall_pct": ov["pct"],
                "filled": ov["filled"],
                "total": ov["total"],
                "categories_summary": cat_summary,
                "errors_count": len(result.get("errors", [])),
                "warnings_count": len(result.get("warnings", [])),
            })

        except Exception as e:
            print(f"[{idx}/{total}] {municipality}... ERROR: {e}")
            logging.getLogger(__name__).exception("Failed processing %s", folder)
            summary_entries.append({
                "folder": folder,
                "municipality": municipality,
                "overall_pct": None,
                "filled": 0,
                "total": 0,
                "categories_summary": {},
                "errors_count": 1,
                "warnings_count": 0,
                "error": str(e),
            })

        finally:
            root_logger.removeHandler(file_handler)
            file_handler.close()

            # Rate limit between projects when running vision (batch mode)
            if full_pipeline and idx < total:
                time.sleep(2)

    summary_path = output_dir / "_summary.json"
    summary_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "projects": summary_entries,
    }
    summary_path.write_text(json.dumps(summary_data, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"{'Project':<30} {'Filled':>6} {'Total':>6} {'Pct':>7}  {'Err':>4} {'Warn':>4}")
    print(f"{'-'*60}")
    for entry in summary_entries:
        pct_str = f"{entry['overall_pct']}%" if entry["overall_pct"] is not None else "ERR"
        print(
            f"{entry['municipality']:<30} "
            f"{entry['filled']:>6} "
            f"{entry['total']:>6} "
            f"{pct_str:>7}  "
            f"{entry['errors_count']:>4} "
            f"{entry['warnings_count']:>4}"
        )
    print(f"{'='*60}")
    print(f"\nResults saved to {output_dir}/")


if __name__ == "__main__":
    main()
