#!/usr/bin/env python3
"""M341 — MESURA COMPLETA de l'informe: totes les variables de la plantilla vs els informes signats de l'Eva, 7 projectes.

Tanca l'ajornament del 2026-08-25 («unificar veritat, camps i semàntica»). Les tres unificacions:

  * **Veritat**: `reference-material/<projecte>/validation/eva_reference_values.json` (extractor de referència sobre el
    signat, 56-65 variables amb el NOM de la plantilla) per als escalars i la narrativa; `_eva_truth/<slug>.json` (11
    taules transcrites) per a les taules. Cap veritat nova: les dues ja existien, aquí es fan servir juntes.
  * **Camps**: el CONTEXT Jinja que el generador passa a la plantilla (`_build_template_context`, capturat en el
    `render_template` real, cap re-extracció del `.docx` generat): la variable `X` del signat es compara amb `context[X]`.
    Els 100 noms de la plantilla són l'univers; les llistes (taules) van pel comparador de taules.
  * **Semàntica**: `status_for` de `scripts/compare_prefills_vs_eva.py` (MATCH / CLOSE / MISMATCH amb tolerància per
    variable) per als escalars i la narrativa; `scripts/compare_tables_vs_eva.py` per a les taules. Un sol valor per
    costat (el que s'imprimeix): els candidats de la lectura no compten aquí, només el defecte.

Variants:
  viaA  Els 7 projectes generats NOMÉS amb la via A + via B (carpeta amb Fase 0 feta: `reference-material/` on hi és,
        amb els JSON de visió de producció; si no, el corpus de lectura amb SmartScan nivell 1): escalars de `_decisions.json` (superposició
        `web/lectura_service._apply_lectura_overlay`, la mateixa del wizard), taules llegides
        (`automation/lectura/tables_report.build_report_tables`), Excel DPSH del projecte, i UNA assumpció per
        projecte: la Df (`DF_SIGNAT`, la fonamentació que l'Eva descriu al signat: pous a Linyola i Anciles). Cap
        `_user_data_prev.json`, cap `geomech_params`, cap `Es_settlement`. És «el que el sistema faria sol».
  t2    Només els 3 amb `_user_data_prev.json` (Castellar, Rubí, Bell-lloc): mateixa variant que `mesura_informe.py`
        (escalars d'abril de l'Eva + taules de la lectura), per veure què aporten els escalars manuals.

Ús:
  PYTHONPATH=$PWD G3DT_CACHE_DIR=/home/josep/g3dt-prod-cache \\
    .venv/bin/python docs/wizard-headless/mesures/mesura_341.py <nom-run> [--variants viaA,t2] [--projects …]
      [--lectura-sub _reconsolida-2026-09-06-pend] [--projectes-dir ~/g3dt-e2e/projectes] [--docx-dir DIR]

Sortida: `runs/<nom-run>/<slug>/<variant>/_compare_341.{txt,json}` (escalars + narrativa per grup), `_compare_informe.*`
(11 taules), `_calc.json`, `_user_data_usat.json`, `_context_usat.json` (sense imatges), i `<nom-run>/_AGREGAT-341.md`.
Els `.docx` van FORA del repositori. Cost: 0 (cap LLM).
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import importlib.util
import io
import json
import logging
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
MESURA_8 = RUNS / "2026-09-03-mesura-8"
DEFAULT_LECTURA_SUB = "_reconsolida-2026-09-06-pend"
DEFAULT_PROJECTES = Path.home() / "g3dt-e2e" / "projectes"

NAMES = {
    "castellar": "3001621 CASTELLAR DEL VALLES", "rubi": "3001631 RUBI", "bell-lloc": "4001612 BELL-LLOC",
    "linyola": "4001607 LINYOLA", "alcoletge": "4001670 ALCOLETGE", "vilanova": "4001671 VILANOVA DE SEGRIA",
    "anciles": "4001679 ANCILES",
}
WITH_PREV = ("castellar", "rubi", "bell-lloc")
VARIANTS = ("viaA", "t2")

#: Df (m) que la fonamentació descrita al signat implica (tests/test_bearing_layer_rule.py, RECERCA-CRITERIS §):
#: sabates encastades 20-40 cm al primer nivell sanejat (0,3), Rubí sabata a 1,0, pous a Linyola (L2 a 1,4 → 1,7)
#: i Anciles (L2 a 2,6 → 2,9), Alcoletge sota el rebliment (1,0). ASSUMPCIÓ documentada: és l'única dada que al
#: wizard posa l'Eva i que cap document llegit dona.
DF_SIGNAT = {"castellar": 0.3, "rubi": 1.0, "bell-lloc": 0.3, "linyola": 1.7, "alcoletge": 1.0, "vilanova": 0.3, "anciles": 2.9}

#: Grup de cada variable de la plantilla (v1, 2026-09-06). A = nivell A (lectura de documents); calc = criteris de
#: càlcul; narr = narrativa generada; taula = llistes (comparador de taules); fix = text fix / numeració / figures.
GROUPS = {
    "A": {"architect_company", "architect_name_upper", "building_type_lower", "client", "plantes", "expedient",
          "municipality", "municipality_upper", "superficie_parcela", "superficie_construida", "data_camp_text",
          "data_camp_inici_text", "num_dpsh_tests", "lab_depth", "lab_location", "lab_sample_id", "lab_testing_company",
          "lab_field_company", "cota_referencia", "utm_x", "utm_y", "spt_test_id", "spt_location", "spt_depth_range",
          "spt_n30", "spt_lithology", "location_sentence", "has_sondeig", "num_soil_levels"},
    "calc": {"qa_value", "settlement", "settlement_sentence", "k30_value", "geomech_E", "geomech_cohesion", "geomech_gamma",
             "geomech_phi", "cte_edificacio", "cte_sol", "seismic_ab_text", "radon_zone", "table_dpsh_range",
             "sulfate_value", "sulfate_baumann", "sulfate_classification", "sulfate_level_name", "show_granulometric",
             "include_earth_pressure", "include_expansivity", "include_slope_stability"},
    "narr": {"adjacent_east_fmt", "adjacent_north_fmt", "adjacent_south_fmt", "adjacent_west_fmt", "access_street",
             "site_description", "site_condition", "building_structure_desc", "lab_tests_text", "materials_intro",
             "conclusions_level_1", "conclusions_levels_detected", "conclusions_water_statement",
             "conclusions_aggressivity_statement", "geology_paragraphs", "empentes_paragraph", "estabilitat_paragraph",
             "photo_site_text", "csn_radon_text", "radon_zone_description"},
    "taula": {"dpsh_tests", "sondeig_tests", "spt_ma_tests", "soil_levels", "soil_level_rows", "perm_rows", "seismic_rows",
              "geotech_rows"},
}


def group_of(var: str) -> str:
    for g, vs in GROUPS.items():
        if var in vs:
            return g
    if var.startswith(("fig_", "photo_", "section_", "table_")) or var.endswith(("_num", "_image")):
        return "fix"
    return "resta"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


MI = _load(HERE / "mesura_informe.py", "mesura_informe")
CPE = _load(REPO / "scripts" / "compare_prefills_vs_eva.py", "compare_prefills_vs_eva")


def _decisions(slug: str, sub: str) -> dict:
    return json.loads((MESURA_8 / slug / sub / "_decisions.json").read_text(encoding="utf-8"))


def _lith_text(row: dict) -> str:
    for k in ("litologia", "description", "descripcio", "nom"):
        v = row.get(k)
        if isinstance(v, dict):
            v = v.get("value")
        if v:
            return str(v)
    return ""


def user_data_from_lectura(slug: str, decisions: dict) -> dict:
    """`user_data` de la via A sola: escalars per la superposició del wizard, taules llegides, Df del signat."""
    from web.lectura_service import _apply_lectura_overlay
    from automation.lectura.tables_report import build_report_tables
    from automation.cte_geomech import detect_soil_type
    merged: dict = {}
    _apply_lectura_overlay(merged, decisions)
    ud = {k: (v.get("value") if isinstance(v, dict) else v) for k, v in merged.items()}
    ud = {k: v for k, v in ud.items() if v not in (None, "")}
    # El wizard converteix els tipus en desar; aquí ho fem igual: UTM i superfície numèrics («571 m²» → 571.0).
    for k in ("utm_x", "utm_y", "superficie_parcela_m2", "superficie_construida_m2"):
        if isinstance(ud.get(k), str):
            m = re.search(r"-?\d+(?:[.,]\d+)?", ud[k].replace(".", "") if k.startswith("superficie") and re.search(r"\d\.\d{3}", ud[k]) else ud[k])
            ud[k] = float(m.group(0).replace(",", ".")) if m else None
            if ud[k] is None:
                del ud[k]
    tables = build_report_tables(decisions)
    ud["lectura_tables"] = tables
    levels = tables.get("soil_levels") or []
    if isinstance(levels, dict):
        levels = levels.get("rows") or []
    if levels:
        ud["num_soil_levels"] = len(levels)
        ud["soil_types"] = [detect_soil_type(_lith_text(r)) for r in levels]
    ud.setdefault("num_soil_levels", 1)
    ud["foundation_depth_m"] = DF_SIGNAT[slug]
    ud["expedient"] = NAMES[slug].split()[0]
    ud["_metadata"] = {"origen": "mesura_341 viaA: lectura + Df del signat", "Df_assumida": DF_SIGNAT[slug]}
    return ud


def _project_path(name: str, projectes: Path) -> Path:
    """Carpeta del projecte per a la via B: `reference-material/<projecte>` si ja té `file_mapping.json` (Fase 0 feta:
    Excel DPSH + JSON de visió del plànol/sondeig, com a producció), si no la del corpus de lectura. Sense
    `file_mapping.json`, el generador cau a l'inventari antic (només `ANNEXES/`) i no troba l'Excel de Vilanova
    (`ANEXOS/`) ni d'Anciles (`ANEJOS/`): es fa la Fase 0 amb SmartScan de nivell 1 (regex de noms, cap LLM) i es desa
    al costat del projecte, com faria el wizard."""
    ref = REPO / "reference-material" / name
    if (ref / "file_mapping.json").exists():
        return ref
    path = projectes / name
    if not (path / "file_mapping.json").exists():
        from automation.smartscan import scan_project
        result = scan_project(path, max_tier=1, include_vision=False)
        # `to_file_mapping()` ja és el JSON de `file_mapping.json` (format que llegeix `FileScanner.load`)
        (path / "file_mapping.json").write_text(json.dumps(result.to_file_mapping(), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _jsonable(v):
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    return f"<{type(v).__name__}>"


def _generate(project_path: Path, ud: dict, out_docx: Path) -> tuple[dict, dict, object]:
    from automation.report_generator import ReportGenerator
    gen = ReportGenerator(project_path=project_path, user_data=ud)
    captured: list[dict] = []
    orig = gen.render_template

    def _render(context, output_path):
        captured.append(context)
        return orig(context, output_path)

    gen.render_template = _render  # type: ignore[method-assign]
    res = gen.generate(out_docx)
    ctx = captured[0] if captured else {}
    return {"success": res.success, "errors": list(res.errors), "warnings": list(res.warnings),
            "calc": MI._calc_summary(gen, ud)}, ctx, gen


def _gen_value(var: str, ctx: dict, ud: dict, calc: dict, eva=None):
    if var == "settlement" and isinstance(eva, str) and "assentaments" in eva.lower():
        return ctx.get("settlement_sentence") or ctx.get("settlement")   # el signat porta la frase sencera
    if var in ctx:
        return ctx[var]
    gp = (calc or {}).get("geotechnical_params") or {}
    if var == "geomech_E":
        return gp.get("E")
    if var == "geomech_cohesion":
        return gp.get("cohesion")
    if var == "geomech_gamma":
        return gp.get("gamma")
    if var == "geomech_phi":
        return gp.get("phi")
    for k in (var, {"superficie_parcela": "superficie_parcela_m2", "superficie_construida": "superficie_construida_m2",
                    "municipality": "site_municipality", "client": "client_name"}.get(var, "")):
        if k and k in ud:
            return ud[k]
    return None


def compare_scalars(eva: dict, ctx: dict, ud: dict, calc: dict) -> list[dict]:
    rows = []
    for var, info in sorted(eva.items()):
        ev = info.get("value") if isinstance(info, dict) else info
        g = group_of(var)
        if g == "taula" or isinstance(ev, (list, dict)):
            continue
        if ev is None or str(ev).strip() in ("", "---"):
            continue
        gv = _gen_value(var, ctx, ud, calc, ev)
        if isinstance(gv, (list, dict)):
            rows.append({"var": var, "grup": g, "eva": ev, "gen": "<llista>", "status": "NO_DATA"})
            continue
        if gv is None or str(gv).strip() == "":
            rows.append({"var": var, "grup": g, "eva": ev, "gen": None, "status": "NO_DATA"})
            continue
        st = CPE.status_for(var, ev, gv)
        rows.append({"var": var, "grup": g, "eva": ev, "gen": gv, "status": st,
                     "method": (info.get("extraction_method") if isinstance(info, dict) else "")})
    return rows


def _fmt_rows(rows: list[dict], tag: str) -> str:
    L = [f"# {tag} — escalars i narrativa vs signat (`eva_reference_values.json`)", ""]
    by = defaultdict(Counter)
    for r in rows:
        by[r["grup"]][r["status"]] += 1
    L.append("| grup | MATCH | CLOSE | MISMATCH | NO_DATA | % (M+C)/comparables |")
    L.append("|---|--:|--:|--:|--:|--:|")
    for g in ("A", "calc", "narr", "fix", "resta"):
        c = by.get(g)
        if not c:
            continue
        L.append(f"| {g} | {c['MATCH']} | {c['CLOSE']} | {c['MISMATCH']} | {c['NO_DATA']} | {MI._pct(c)} |")
    L.append("")
    for r in rows:
        if r["status"] == "MATCH":
            continue
        L.append(f"- [{r['grup']}] `{r['var']}` **{r['status']}** gen=«{str(r['gen'])[:90]}» ↔ eva=«{str(r['eva'])[:90]}»")
    return "\n".join(L) + "\n"


def _agregat(run: str, results: dict, variants: list[str], sub: str) -> str:
    L = [f"# Agregat M341 — mesura completa `{run}`", ""]
    L.append(f"Informe generat des de `~/g3dt-e2e/projectes/<projecte>` vs signat. Escalars/narrativa: context de plantilla "
             f"vs `eva_reference_values.json` (`status_for`); taules: `compare_tables_vs_eva.py` (11 taules). Lectura `{sub}`. "
             f"Variants: `viaA` = només lectura + via B + Df del signat (7 projectes); `t2` = escalars d'abril de l'Eva + lectura (3).")
    L.append("")
    L.append("## Titulars per projecte i variant (escalars+narrativa: M · C · X · ND → % · taules: M · C · X → %)")
    L.append("")
    L.append("| projecte | " + " | ".join(f"{v} escalars" for v in variants) + " | " + " | ".join(f"{v} taules" for v in variants) + " |")
    L.append("|---|" + "---|" * (2 * len(variants)))
    tot_s = {v: Counter() for v in variants}
    tot_t = {v: Counter() for v in variants}
    for slug, per in results.items():
        cells_s, cells_t = [], []
        for v in variants:
            r = per.get(v)
            if not r or not r["gen"]["success"]:
                cells_s.append("**ERR**" if r else "—")
                cells_t.append("**ERR**" if r else "—")
                continue
            c = Counter(x["status"] for x in r["scalars"])
            tot_s[v].update(c)
            cells_s.append(f"{c['MATCH']} · {c['CLOSE']} · {c['MISMATCH']} · {c['NO_DATA']} → **{MI._pct(c)}**")
            t = r["report"]["totals"] if r.get("report") else {}
            tot_t[v].update({k: t.get(k, 0) for k in ("MATCH", "CLOSE", "MISMATCH")})
            cells_t.append(f"{t.get('MATCH', 0)} · {t.get('CLOSE', 0)} · {t.get('MISMATCH', 0)} → **{MI._pct(t)}**" if t else "—")
        L.append(f"| {slug} | " + " | ".join(cells_s) + " | " + " | ".join(cells_t) + " |")
    L.append("| **Total** | " + " | ".join(
        f"{tot_s[v]['MATCH']} · {tot_s[v]['CLOSE']} · {tot_s[v]['MISMATCH']} · {tot_s[v]['NO_DATA']} → **{MI._pct(tot_s[v])}**"
        for v in variants) + " | " + " | ".join(
        f"{tot_t[v]['MATCH']} · {tot_t[v]['CLOSE']} · {tot_t[v]['MISMATCH']} → **{MI._pct(tot_t[v])}**" for v in variants) + " |")
    L.append("")
    L.append("## Per GRUP (escalars+narrativa), variant × grup, agregat dels projectes")
    L.append("")
    L.append("| variant | grup | MATCH | CLOSE | MISMATCH | NO_DATA | % |")
    L.append("|---|---|--:|--:|--:|--:|--:|")
    for v in variants:
        by = defaultdict(Counter)
        for per in results.values():
            r = per.get(v)
            if r and r["gen"]["success"]:
                for x in r["scalars"]:
                    by[x["grup"]][x["status"]] += 1
        for g in ("A", "calc", "narr", "fix", "resta"):
            c = by.get(g)
            if c:
                L.append(f"| `{v}` | {g} | {c['MATCH']} | {c['CLOSE']} | {c['MISMATCH']} | {c['NO_DATA']} | {MI._pct(c)} |")
    L.append("")
    L.append("## Per VARIABLE (viaA): en quants projectes és MATCH / CLOSE / MISMATCH / NO_DATA")
    L.append("")
    byvar = defaultdict(Counter)
    for per in results.values():
        r = per.get("viaA")
        if r and r["gen"]["success"]:
            for x in r["scalars"]:
                byvar[x["var"]][x["status"]] += 1
    L.append("| variable | grup | M | C | X | ND |")
    L.append("|---|---|--:|--:|--:|--:|")
    for var in sorted(byvar, key=lambda k: (group_of(k), -byvar[k]["MISMATCH"], k)):
        c = byvar[var]
        L.append(f"| `{var}` | {group_of(var)} | {c['MATCH']} | {c['CLOSE']} | {c['MISMATCH']} | {c['NO_DATA']} |")
    L.append("")
    L.append("## Càlcul per projecte (viaA): nivell portant, Nb, φ, E, Qa, assentament")
    L.append("")
    L.append("| projecte | Df | nivell portant | Nb | φ | γ | c | E | Qa (gov) | assent. | imprès | Es |")
    L.append("|---|--:|---|--:|--:|--:|--:|--:|---|--:|---|---|")
    for slug, per in results.items():
        r = per.get("viaA")
        c = ((r or {}).get("gen") or {}).get("calc") or {}
        gp, tz, lv = c.get("geotechnical_params") or {}, c.get("terzaghi") or {}, c.get("soil_levels") or []
        last = lv[-1] if lv else {}
        sg = MI.SIGNAT_CALC.get(slug, {})
        L.append(f"| {slug} | {c.get('Df_user', '')} | {c.get('bearing_layer_idx', '')}: {(c.get('bearing_layer_description') or '')[:40]} | "
                 f"{last.get('Nb', '')} | {gp.get('phi', '')} | {gp.get('gamma', '')} | {gp.get('cohesion', '')} | {gp.get('E', '')} | "
                 f"{'' if tz.get('Qa') is None else f'{tz.get('Qa'):.2f}'} ({tz.get('qa_governs', '')}) | "
                 f"{'' if tz.get('settlement_cm') is None else f'{tz.get('settlement_cm'):.2f}'} | "
                 f"{MI._settle_cell(tz, sg.get('assentament'))} | {(tz.get('Es_used') and f'{tz.get('Es_used'):.0f}') or ''} |")
    L.append("")
    L.append("## Errors i avisos del generador")
    L.append("")
    for slug, per in results.items():
        for v, r in per.items():
            g = r["gen"]
            if g["errors"] or g["warnings"]:
                L.append(f"- **{slug}/{v}**: errors={g['errors']} warnings={g['warnings'][:8]}")
    L.append("")
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run")
    ap.add_argument("--variants", default=",".join(VARIANTS))
    ap.add_argument("--projects", default=",".join(NAMES))
    ap.add_argument("--lectura-sub", default=DEFAULT_LECTURA_SUB)
    ap.add_argument("--projectes-dir", default=str(DEFAULT_PROJECTES))
    ap.add_argument("--docx-dir", default=None)
    args = ap.parse_args()
    logging.basicConfig(level=logging.ERROR)
    for noisy in ("automation", "web"):
        logging.getLogger(noisy).setLevel(logging.ERROR)

    variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    slugs = [s.strip() for s in args.projects.split(",") if s.strip()]
    projectes = Path(args.projectes_dir).expanduser()
    run_dir = RUNS / args.run
    docx_dir = Path(args.docx_dir).expanduser() if args.docx_dir else Path.home() / "g3dt-e2e" / "informes-mesura" / args.run
    docx_dir.mkdir(parents=True, exist_ok=True)
    cmp_mod = MI._load_compare_module()

    results: dict[str, dict[str, dict]] = {}
    for slug in slugs:
        name = NAMES[slug]
        eva_path = REPO / "reference-material" / name / "validation" / "eva_reference_values.json"
        eva = json.loads(eva_path.read_text(encoding="utf-8"))["variables"]
        results[slug] = {}
        for v in variants:
            if v == "t2" and slug not in WITH_PREV:
                continue
            if v == "viaA":
                ud = user_data_from_lectura(slug, _decisions(slug, args.lectura_sub))
                project_path = _project_path(name, projectes)
            else:
                ud = MI._user_data(slug, "t2", args.lectura_sub)
                project_path = REPO / "reference-material" / name
            out = run_dir / slug / v
            out.mkdir(parents=True, exist_ok=True)
            (out / "_user_data_usat.json").write_text(json.dumps(ud, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
            docx = docx_dir / f"{slug}_{v}.docx"
            gen, ctx, _ = _generate(project_path, ud, docx)
            entry: dict = {"gen": gen, "docx": str(docx)}
            (out / "_calc.json").write_text(json.dumps(gen.get("calc") or {}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
            if gen["success"]:
                (out / "_context_usat.json").write_text(json.dumps(_jsonable(ctx), ensure_ascii=False, indent=1), encoding="utf-8")
                rows = compare_scalars(eva, ctx, ud, gen.get("calc") or {})
                entry["scalars"] = rows
                (out / "_compare_341.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
                (out / "_compare_341.txt").write_text(_fmt_rows(rows, f"{slug}/{v}"), encoding="utf-8")
                try:
                    txt = MI._compare(cmp_mod, docx, slug, f"{slug}/{v}", out / "_compare_informe.json")
                    (out / "_compare_informe.txt").write_text(txt, encoding="utf-8")
                    entry["report"] = json.loads((out / "_compare_informe.json").read_text(encoding="utf-8"))
                except Exception as exc:  # la veritat de taules pot faltar o no alinear
                    entry["report"] = None
                    gen["warnings"].append(f"taules: {exc}")
                c = Counter(r["status"] for r in rows)
                t = (entry.get("report") or {}).get("totals") or {}
                print(f"{slug:10s} {v:5s} escalars {c['MATCH']:3d} M · {c['CLOSE']:2d} C · {c['MISMATCH']:2d} X · {c['NO_DATA']:2d} ND → {MI._pct(c)}"
                      f" | taules {t.get('MATCH', 0)} M · {t.get('CLOSE', 0)} C · {t.get('MISMATCH', 0)} X → {MI._pct(t) if t else '—'}"
                      + (f"   [{len(gen['warnings'])} avisos]" if gen["warnings"] else ""), flush=True)
            else:
                entry["scalars"] = []
                print(f"{slug:10s} {v:5s} ERR generació: {gen['errors']}", flush=True)
            results[slug][v] = entry

    (run_dir / "_AGREGAT-341.md").write_text(_agregat(args.run, results, variants, args.lectura_sub), encoding="utf-8")
    print(f"\nAgregat: {run_dir / '_AGREGAT-341.md'}\n.docx a: {docx_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
