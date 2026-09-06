#!/usr/bin/env python3
"""Mesura de QUALITAT D'INFORME (bloc 2): informe generat vs informe signat de l'Eva.

No confondre amb `reconsolida_mesura.py` / `agrega_mesura.py` (qualitat de LECTURA:
decisions vs or). Aquí es genera el `.docx` sencer amb `ReportGenerator` i es compara
cel·la a cel·la amb la veritat transcrita dels signats (`scripts/compare_tables_vs_eva.py`,
11 taules, veritat a `docs/golden-read-taules/_eva_truth/<slug>.json`).

Només es poden generar els 3 projectes amb `_user_data_prev.json` reutilitzable a
`reference-material/` (Castellar, Rubí, Bell-lloc): la resta necessita el wizard
(pendent de M341, unificació de semàntica).

Variants (cada una genera un `.docx` i una comparació):

  8b    `_user_data_prev.json` sencer + taules de l'OR de lectura (`_tables_decisions.json`
        via `adapt_legacy`). Rèplica exacta de la mesura de la Fase 8b (2026-08-26):
        Castellar 78 %, Rubí 82 %, Bell-lloc 75 %. Les cel·les γ/c/φ/E de la taula
        geotècnica hi surten dels `geomech_params` manuals de l'Eva, NO del càlcul.
  calc  Igual que `8b` però SENSE `geomech_params`: les cel·les de càlcul (N, Nb, γ, c,
        φ, E) surten del codi. És la columna que el bloc 2 (P0, P2a, P2b) ha de moure.
  t2    Com `calc`, però amb les taules de la LECTURA REAL del runner (referència
        `--lectura-sub`, defecte `_reconsolida-2026-09-06-t2`) en lloc de l'or: el que
        avui sortiria a producció amb la lectura de la via A.
  viab  SENSE cap taula llegida ni `geomech_params`: només via B (Excel DPSH +
        `sondeig_extracted.json` / annex + càlcul). És l'única variant on la litologia
        llegida NO tapa la descripció del sondeig: la que deixa veure P2a (col·lapse
        «vestit de roca» de Rubí) tal com el va descriure l'anàlisi del 2026-09-02 §6.

Ús:
  PYTHONPATH=$PWD G3DT_CACHE_DIR=/home/josep/g3dt-prod-cache \\
    .venv/bin/python docs/wizard-headless/mesures/mesura_informe.py <nom-run> \\
      [--variants 8b,calc,t2] [--projects castellar,rubi,bell-lloc] \\
      [--lectura-sub _reconsolida-2026-09-06-t2] [--docx-dir DIR]

Sortida: `docs/wizard-headless/mesures/runs/<nom-run>/<slug>/<variant>/_compare_informe.{txt,json}`
i `<nom-run>/_AGREGAT.md`. Els `.docx` (7-10 MB cadascun) van a `--docx-dir`
(defecte `~/g3dt-e2e/informes-mesura/<nom-run>/`), FORA del repositori. Cost: 0 (cap LLM).

Comparar dos runs (cel·la a cel·la, no titulars):
  diff <(grep -v '^\\*\\*' runs/A/castellar/calc/_compare_informe.txt) <(grep -v '^\\*\\*' runs/B/castellar/calc/_compare_informe.txt)
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import importlib.util
import io
import json
import logging
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

RUNS = Path(__file__).resolve().parent / "runs"
GOLD_TAULES = REPO / "docs" / "golden-read-taules"
EVA_TRUTH = GOLD_TAULES / "_eva_truth"
MESURA_8 = RUNS / "2026-09-03-mesura-8"
DEFAULT_LECTURA_SUB = "_reconsolida-2026-09-06-t2"

NAMES = {
    "castellar": "3001621 CASTELLAR DEL VALLES",
    "rubi": "3001631 RUBI",
    "bell-lloc": "4001612 BELL-LLOC",
}
VARIANTS = ("8b", "calc", "t2", "viab")
# Les taules on viuen les cel·les que el bloc 2 pot moure (càlcul / tria d'estrat).
BLOC2_TABLES = ("geotecnica", "soil_levels", "sismica", "spt_ma", "sondeig")


def _load_compare_module():
    spec = importlib.util.spec_from_file_location(
        "compare_tables_vs_eva", REPO / "scripts" / "compare_tables_vs_eva.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _gold_tables(name: str) -> dict:
    from automation.lectura.contract import adapt_legacy
    from automation.lectura.tables_report import build_report_tables
    path = GOLD_TAULES / name / "_tables_decisions.json"
    gold = adapt_legacy(json.loads(path.read_text(encoding="utf-8")))
    return build_report_tables(gold)


def _lectura_tables(slug: str, sub: str) -> dict:
    from automation.lectura.tables_report import build_report_tables
    path = MESURA_8 / slug / sub / "_decisions.json"
    decisions = json.loads(path.read_text(encoding="utf-8"))
    return build_report_tables(decisions)


def _user_data(slug: str, variant: str, lectura_sub: str) -> dict:
    name = NAMES[slug]
    ud = json.loads((REPO / "reference-material" / name / "_user_data_prev.json").read_text(encoding="utf-8"))
    ud = copy.deepcopy(ud)
    if variant in ("calc", "t2", "viab"):
        ud.pop("geomech_params", None)
    if variant in ("8b", "calc"):
        ud["lectura_tables"] = _gold_tables(name)
    elif variant == "t2":
        ud["lectura_tables"] = _lectura_tables(slug, lectura_sub)
    elif variant == "viab":
        ud.pop("lectura_tables", None)
        ud.pop("lectura_selections", None)
    else:
        raise ValueError(variant)
    return ud


# Valors SIGNATS de càlcul (taula geotècnica + frase del Qa), `docs/CRITERIS-CALCUL-EVA.md` §5.
SIGNAT_CALC = {
    "castellar": {"Nb": "17-R", "phi": 35, "gamma": 2.20, "c": 1.0, "E": ">500", "Qa": 3.0, "assentament": "<1,0"},
    "rubi": {"Nb": "47-R", "phi": 39, "gamma": 2.0, "c": 0.05, "E": 450, "Qa": 3.5, "assentament": "1,50"},
    "bell-lloc": {"Nb": "25-R", "phi": 38, "gamma": 2.0, "c": 0.0, "E": 650, "Qa": 3.0, "assentament": "<1,20"},
}


def _calc_summary(gen, ud: dict) -> dict:
    """Bolcat del càlcul (Qa no és a cap de les 11 taules del comparador)."""
    from dataclasses import asdict
    rd = gen.report_data
    if rd is None:
        return {}
    tr = rd.terzaghi_result
    keep = ("phi", "cohesion", "gamma", "B", "Df", "qu", "safety_factor", "Qa", "settlement_cm", "settlement_type",
            "Es_used", "qa_terzaghi_peck", "Qa_uncapped", "Fw", "Fd_tp", "qa_governs")
    return {
        "Df_user": ud.get("foundation_depth_m"),
        "num_soil_levels_user": ud.get("num_soil_levels"),
        "soil_types_user": ud.get("soil_types"),
        "dpsh_overall_n20": round(rd.dpsh.overall_average_n20, 2) if rd.dpsh else None,
        "bearing_layer_idx": getattr(rd, "bearing_layer_idx", None),
        "bearing_layer_description": getattr(rd, "bearing_layer_description", ""),
        "soil_levels": [{
            "n": l.level_number, "desc": (l.description or "")[:90], "from": l.depth_from_m, "to": l.depth_to_m,
            "n20_avg": round(l.n20_average, 2), "Nb": round(l.n20_average / 0.83, 1), "soil_type": l.soil_type,
        } for l in (rd.soil_levels or [])],
        "geotechnical_params": asdict(rd.geotechnical_params) if rd.geotechnical_params else None,
        "terzaghi": {k: v for k, v in asdict(tr).items() if k in keep} if tr else None,
    }


def _generate(slug: str, ud: dict, out_docx: Path) -> dict:
    from automation.report_generator import ReportGenerator
    gen = ReportGenerator(project_path=REPO / "reference-material" / NAMES[slug], user_data=ud)
    res = gen.generate(out_docx)
    return {"success": res.success, "errors": list(res.errors), "warnings": list(res.warnings),
            "calc": _calc_summary(gen, ud)}


def _compare(cmp_mod, gen_docx: Path, slug: str, tag: str, out_json: Path) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cmp_mod.main([str(gen_docx), str(EVA_TRUTH / f"{slug}.json"), "--tag", tag, "--json", str(out_json)])
    if rc != 0:
        raise RuntimeError(f"compare_tables_vs_eva rc={rc} ({tag})")
    return buf.getvalue()


def _pct(t: Counter | dict) -> str:
    comp = t.get("MATCH", 0) + t.get("CLOSE", 0) + t.get("MISMATCH", 0)
    return f"{100 * (t.get('MATCH', 0) + t.get('CLOSE', 0)) / comp:.0f} %" if comp else "—"


def _agregat(run: str, results: dict[str, dict[str, dict]], variants: list[str], lectura_sub: str) -> str:
    L = [f"# Agregat mecànic — mesura d'informe `{run}`", ""]
    L.append("Informe generat (`ReportGenerator`, `reference-material/<projecte>` + `_user_data_prev.json`) vs informe "
             "signat (`_eva_truth/<slug>.json`), `scripts/compare_tables_vs_eva.py`, 11 taules. "
             "M = idèntica · C = propera · X = diferent · % = (M+C)/comparables. "
             f"Variants: `8b` = or de taules + `geomech_params` manuals (rèplica Fase 8b); `calc` = or de taules SENSE "
             f"`geomech_params` (cel·les de càlcul del codi); `t2` = lectura real `{lectura_sub}` sense `geomech_params`; "
             "`viab` = només via B (cap taula llegida, cap `geomech_params`).")
    L.append("")
    L.append("## Titulars")
    L.append("")
    L.append("| Projecte | " + " | ".join(f"{v}: M · C · X → %" for v in variants) + " |")
    L.append("|---|" + "---|" * len(variants))
    tot = {v: Counter() for v in variants}
    for slug in results:
        cells = []
        for v in variants:
            r = results[slug].get(v)
            if not r or not r.get("gen", {}).get("success"):
                cells.append("**ERR generació**")
                continue
            t = r["report"]["totals"]
            tot[v].update({k: t.get(k, 0) for k in ("MATCH", "CLOSE", "MISMATCH", "ROW_EXTRA", "ROW_MISSING")})
            cells.append(f"{t.get('MATCH', 0)} · {t.get('CLOSE', 0)} · {t.get('MISMATCH', 0)} → **{_pct(t)}**")
        L.append(f"| {slug} | " + " | ".join(cells) + " |")
    L.append("| **Total** | " + " | ".join(
        f"{tot[v]['MATCH']} · {tot[v]['CLOSE']} · {tot[v]['MISMATCH']} → **{_pct(tot[v])}**" for v in variants) + " |")
    L.append("")

    L.append("## Per taula (M/C/X per variant)")
    L.append("")
    kinds = [k for k, *_ in _load_compare_module().TABLE_TYPES]
    for slug in results:
        L.append(f"### {slug}")
        L.append("")
        L.append("| taula | " + " | ".join(variants) + " |")
        L.append("|---|" + "---|" * len(variants))
        for kind in kinds:
            row = []
            present = False
            for v in variants:
                r = results[slug].get(v)
                tb = ((r or {}).get("report") or {}).get("tables", {}).get(kind)
                if tb is None:
                    row.append("—")
                    continue
                present = True
                if "counts" not in tb:
                    row.append(tb.get("estat", "?"))
                    continue
                c = tb["counts"]
                row.append(f"{c.get('MATCH', 0)}/{c.get('CLOSE', 0)}/{c.get('MISMATCH', 0)}")
            if present:
                L.append(f"| {kind} | " + " | ".join(row) + " |")
        L.append("")

    L.append("## Cel·les del bloc 2 que NO són MATCH (taules " + ", ".join(f"`{k}`" for k in BLOC2_TABLES) + ")")
    L.append("")
    L.append("Per variant i projecte: `fila[col] ESTAT «generat» ↔ «Eva»`. Són les cel·les que P0 / P2a / P2b han de moure "
             "(o deixar quietes); després de cada peça, diff d'aquesta llista, no dels titulars.")
    L.append("")
    for v in variants:
        L.append(f"### variant `{v}`")
        L.append("")
        for slug in results:
            r = results[slug].get(v)
            tables = ((r or {}).get("report") or {}).get("tables", {})
            lines = []
            for kind in BLOC2_TABLES:
                tb = tables.get(kind)
                if not tb:
                    continue
                if "counts" not in tb:
                    lines.append(f"- `{kind}`: {tb.get('estat')}")
                    continue
                for c in tb["cells"]:
                    if c["estat"] == "MATCH":
                        continue
                    if c["estat"] in ("ROW_EXTRA", "ROW_MISSING"):
                        lines.append(f"- `{kind}` {c['row']} **{c['estat']}** «{c.get('gen', c.get('eva', ''))}»")
                    else:
                        lines.append(f"- `{kind}` {c['row']}[{c['col']}] **{c['estat']}** «{c.get('gen', '')}» ↔ «{c.get('eva', '')}»")
            L.append(f"**{slug}** ({len(lines)} cel·les no-MATCH)")
            L.append("")
            L.extend(lines or ["- (cap)"])
            L.append("")

    L.append("## Càlcul (no és a cap de les 11 taules): nivell portant, Nb, φ, γ, c, E, Qa — per variant vs signat")
    L.append("")
    L.append("Nb = N20 mitjà del nivell únic / 0,83 (el que imprimeix la cel·la, sense la «-R»). Qa = Terzaghi amb topalls; "
             "`gov` = qui mana (terzaghi / terzaghi-peck / cap). Signat: `docs/CRITERIS-CALCUL-EVA.md` §5.")
    L.append("")
    L.append("| projecte | variant | Df | nivell portant (idx: descripció) | N20 | Nb | φ | γ | c | E | Qa (uncapped, gov) | assent. cm |")
    L.append("|---|---|--:|---|--:|--:|--:|--:|--:|--:|---|--:|")
    for slug in results:
        sg = SIGNAT_CALC.get(slug, {})
        L.append(f"| **{slug}** | *signat* | | | | {sg.get('Nb', '')} | {sg.get('phi', '')} | {sg.get('gamma', '')} | "
                 f"{sg.get('c', '')} | {sg.get('E', '')} | **{sg.get('Qa', '')}** | {sg.get('assentament', '')} |")
        for v in variants:
            c = ((results[slug].get(v) or {}).get("gen") or {}).get("calc") or {}
            gp = c.get("geotechnical_params") or {}
            tz = c.get("terzaghi") or {}
            lv = c.get("soil_levels") or []
            last = lv[-1] if lv else {}
            bidx = c.get("bearing_layer_idx")
            bdesc = (c.get("bearing_layer_description") or "")[:45]
            qa = tz.get("Qa")
            unc = tz.get("Qa_uncapped")
            L.append(f"| {slug} | `{v}` | {c.get('Df_user', '')} | {'' if bidx is None else bidx}: {bdesc} | "
                     f"{last.get('n20_avg', '')} | {last.get('Nb', '')} | {gp.get('phi', '')} | {gp.get('gamma', '')} | "
                     f"{gp.get('cohesion', '')} | {gp.get('E', '')} | "
                     f"{'' if qa is None else f'{qa:.2f}'} ({'' if unc is None else f'{unc:.2f}'}, {tz.get('qa_governs', '')}) | "
                     f"{'' if tz.get('settlement_cm') is None else f'{tz.get('settlement_cm'):.2f}'} |")
    L.append("")
    L.append("## Avisos del generador")
    L.append("")
    for slug in results:
        for v in variants:
            g = (results[slug].get(v) or {}).get("gen") or {}
            if g.get("errors") or g.get("warnings"):
                L.append(f"- **{slug}/{v}**: errors={g.get('errors')}; warnings={g.get('warnings')}")
    L.append("")
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run", help="nom del run (subcarpeta de runs/)")
    ap.add_argument("--variants", default=",".join(VARIANTS))
    ap.add_argument("--projects", default=",".join(NAMES))
    ap.add_argument("--lectura-sub", default=DEFAULT_LECTURA_SUB,
                    help="subcarpeta de reconsolidació de mesura-8 per a la variant t2")
    ap.add_argument("--docx-dir", default=None, help="on deixar els .docx (defecte ~/g3dt-e2e/informes-mesura/<run>/)")
    args = ap.parse_args()

    logging.basicConfig(level=logging.ERROR)
    for noisy in ("automation", "web"):
        logging.getLogger(noisy).setLevel(logging.ERROR)

    variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    slugs = [s.strip() for s in args.projects.split(",") if s.strip()]
    for v in variants:
        if v not in VARIANTS:
            ap.error(f"variant desconeguda: {v}")
    for s in slugs:
        if s not in NAMES:
            ap.error(f"projecte desconegut: {s} (només {', '.join(NAMES)})")

    run_dir = RUNS / args.run
    docx_dir = Path(args.docx_dir).expanduser() if args.docx_dir else Path.home() / "g3dt-e2e" / "informes-mesura" / args.run
    docx_dir.mkdir(parents=True, exist_ok=True)
    cmp_mod = _load_compare_module()

    results: dict[str, dict[str, dict]] = {}
    for slug in slugs:
        results[slug] = {}
        for v in variants:
            out = run_dir / slug / v
            out.mkdir(parents=True, exist_ok=True)
            docx = docx_dir / f"{slug}_{v}.docx"
            ud = _user_data(slug, v, args.lectura_sub)
            (out / "_user_data_usat.json").write_text(json.dumps(ud, ensure_ascii=False, indent=1), encoding="utf-8")
            gen = _generate(slug, ud, docx)
            entry: dict = {"gen": gen, "docx": str(docx)}
            (out / "_calc.json").write_text(json.dumps(gen.get("calc") or {}, ensure_ascii=False, indent=1, default=str),
                                            encoding="utf-8")
            if gen["success"]:
                txt = _compare(cmp_mod, docx, slug, f"{slug}/{v}", out / "_compare_informe.json")
                (out / "_compare_informe.txt").write_text(txt, encoding="utf-8")
                entry["report"] = json.loads((out / "_compare_informe.json").read_text(encoding="utf-8"))
                t = entry["report"]["totals"]
                print(f"{slug:10s} {v:5s} {t.get('MATCH', 0):3d} M · {t.get('CLOSE', 0):2d} C · {t.get('MISMATCH', 0):2d} X → {_pct(t)}"
                      + (f"   [{len(gen['warnings'])} avisos]" if gen["warnings"] else ""))
            else:
                print(f"{slug:10s} {v:5s} ERR generació: {gen['errors']}")
            results[slug][v] = entry

    agg = _agregat(args.run, results, variants, args.lectura_sub)
    (run_dir / "_AGREGAT.md").write_text(agg, encoding="utf-8")
    print(f"\nAgregat: {run_dir / '_AGREGAT.md'}\n.docx a: {docx_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
