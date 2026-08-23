#!/usr/bin/env python3
"""Comparador prefills del wizard (sortida de /api/prefills) vs informe real d'Eva.

A diferència de `compare_eva_vs_pipeline.py` (que executa `auto_extract` in-process
sobre `reference-material/`), aquest llegeix el `prefills.json` que ha retornat el
servidor en una obertura real (mode xarxa, cache fred) i el compara amb
`validation/eva_reference_values.json` del mateix projecte, amb **mapatge de claus**
(les variables de la plantilla d'Eva no es diuen igual que els camps del wizard).

Per variable: MATCH / CLOSE / MISMATCH / NO_DATA (el wizard no té valor) /
NOT_MAPPED (no hi ha camp equivalent al wizard). Per als MISMATCH, classifica la
**causa probable** segons la font (`source`) del prefill.

Ús:
    python3 scripts/compare_prefills_vs_eva.py --prefills P.json --eva E.json [--name TAG] [--md]
    python3 scripts/compare_prefills_vs_eva.py --batch "TAG=P.json:E.json" ... --md   # agregat
Només lectura.
"""
from __future__ import annotations

import argparse
import collections
import difflib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from compare_benchmarks import TEXT_NORMALIZERS, compare_numeric, parse_numeric  # noqa: E402

# Variable d'Eva → candidats de camp del wizard (primer que tingui valor)
EVA_TO_PREFILL: dict[str, list[str]] = {
    "architect_name_upper": ["architect_name", "architect_company"],
    "architect_name": ["architect_name", "architect_company"],
    "architect_company": ["architect_company"],
    "building_type_lower": ["building_type"],
    "plantes": ["num_floors"],
    "client": ["client_name"],
    "client_name": ["client_name"],
    "adjacent_east_fmt": ["adjacent_east_fmt", "adjacent_east"],
    "adjacent_south_fmt": ["adjacent_south_fmt", "adjacent_south"],
    "adjacent_north_fmt": ["adjacent_north_fmt", "adjacent_north"],
    "adjacent_west_fmt": ["adjacent_west_fmt", "adjacent_west"],
    "superficie_parcela": ["superficie_parcela_m2", "superficie_cadastral_m2"],
    "superficie_construida": ["superficie_construida_m2", "building_footprint_m2"],
    "data_camp_text": ["field_date"],
    "access_street": ["access_description"],
    "num_dpsh_tests": ["num_dpsh_tests"],
    "spt_n30": ["spt_n30", "spt_n_value"],
    "sulfate_value": ["sulfate_value", "sulfate_mg_kg"],
    "sulfate_classification": ["sulfate_classification", "aggressivity_class"],
    "sulfate_level_name": ["sulfate_level_name"],
    "sulfate_baumann": ["sulfate_baumann"],
}

SKIP_VARS = {
    "geo_p", "materials_intro", "conclusions_levels_detected", "conclusions_water_statement",
    "conclusions_aggressivity_statement", "csn_radon_text", "radon_zone_description",
    "empentes_paragraph", "estabilitat_paragraph", "photo_site_text", "data_signatura_text",
    "lab_field_description", "lab_testing_description",  # text fix de plantilla
    "geotech_rows", "dpsh_tests", "sondeig_tests", "seismic_rows", "perm_rows", "soil_level_rows",
}

NUMERIC_VARS = {
    "superficie_parcela": 5.0, "superficie_construida": 5.0, "cota_referencia": 0.5,
    "sulfate_value": 5.0, "qa_value": 5.0, "settlement": 10.0, "k30_value": 10.0,
    "geomech_E": 10.0, "geomech_cohesion": 10.0, "geomech_gamma": 5.0, "geomech_phi": 3.0,
    "utm_x": 0.05, "utm_y": 0.005, "num_dpsh_tests": 0.0, "radon_zone": 0.0, "spt_n30": 0.0,
}

NARRATIVE_VARS = {
    "site_description", "site_condition", "location_sentence", "building_structure_desc",
    "access_street", "lab_tests_text", "adjacent_east_fmt", "adjacent_south_fmt",
    "adjacent_north_fmt", "adjacent_west_fmt", "num_dpsh_tests",
}

# Font del prefill → causa probable d'un MISMATCH
CAUSE_RULES = [
    ("font foto/probe (vision_probe)", re.compile(r"^(vision_probe:|concept_scout|vision \(fotos)")),
    ("narrativa ortho+visió (ICGC)", re.compile(r"^ICGC ortho")),
    ("extracció Lab/Excel (Python)", re.compile(r"^(/.*\.(pdf|xls|xlsx)$|.*GTL.*\.pdf$|DPSH|lab )", re.I)),
    ("extracció text (fileminer/groq/docs)", re.compile(r"^(fileminer|contingut:|groq_llm:|docs intel)", re.I)),
    ("visió per tipus (sondeig/planol/dpsh)", re.compile(r"^(sondeig|planol|dpsh|projecte|vision_)", re.I)),
    ("geocode / Cadastre / ICGC", re.compile(r"^(Cadastre|geocode|ICGC|NCSE-02|CTE DB HS6|Nominatim)", re.I)),
    ("narrativa LLM", re.compile(r"^llm_synthesis")),
    ("càlcul (criteri ≠ Eva)", re.compile(r"^(computed|Terzaghi|Schmertmann|Winkler|CTE D\.|CTE DB SE-C|2\.5×Nb|soil_type=)", re.I)),
    ("no extret (default/sistema)", re.compile(r"^(system|constant|default|plantilla)", re.I)),
    ("usuari", re.compile(r"^user$")),
]

_CA_MONTHS = {"gener": 1, "febrer": 2, "març": 3, "abril": 4, "maig": 5, "juny": 6, "juliol": 7,
              "agost": 8, "setembre": 9, "octubre": 10, "novembre": 11, "desembre": 12}


def _norm_date(s: str) -> str:
    s = str(s).strip().lower()
    m = re.search(r"(\d{1,2})\s+d[e']\s*(\w+)\s+(?:de\s+)?(\d{4})", s)
    if m and m.group(2) in _CA_MONTHS:
        return f"{int(m.group(3)):04d}-{_CA_MONTHS[m.group(2)]:02d}-{int(m.group(1)):02d}"
    m = re.search(r"(\d{4})[-.](\d{2})[-.](\d{2})", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    return s


def _norm_text(s: str) -> str:
    s = str(s).lower().replace("’", "'").replace("l·l", "ll")
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _norm_floors(s: str) -> str:
    s = _norm_text(s).replace("planta baixa", "pb").replace("planta primera", "pp").replace("soterrani", "ps")
    return s.replace(" ", "").replace("+", "")


_LABELS = re.compile(r"^(profunditat|punt|mostra|cota|zona)\s*:?\s*", re.I)


def _first_num(s: str):
    """Primer número d'un text ('Els assentaments … 1,50 cm' → 1.5; '280+86' → 366)."""
    s = str(s).replace("−", "-")
    if re.fullmatch(r"\s*[\d.,]+(\s*\+\s*[\d.,]+)+\s*", s):
        return sum(float(x.replace(",", ".")) for x in s.split("+"))
    n = parse_numeric(s)
    if n is not None:
        return n
    m = re.search(r"-?\d+(?:[.,]\d+)?", s)
    return float(m.group(0).replace(",", ".")) if m else None


def _nums(s: str) -> list[float]:
    return [round(float(x.replace(",", ".")), 2) for x in re.findall(r"-?\d+(?:[.,]\d+)?", str(s).replace("−", "-"))]


def status_for(var: str, eva, pipe) -> str:
    e, p = str(eva).strip(), str(pipe).strip()
    if not e or not p:
        return "NO_DATA"
    if var in NUMERIC_VARS:
        en, pn = _first_num(e), _first_num(p)
        if var == "num_dpsh_tests":
            m = re.match(r"\s*(\d+)", e); en = float(m.group(1)) if m else en
            m = re.match(r"\s*(\d+)", p); pn = float(m.group(1)) if m else pn
        if en is not None and pn is not None:
            if NUMERIC_VARS[var] == 0.0:
                return "MATCH" if en == pn else "MISMATCH"
            _, st = compare_numeric(en, pn, NUMERIC_VARS[var])
            return st
    if var == "data_camp_text":
        return "MATCH" if _norm_date(e) == _norm_date(p) else "MISMATCH"
    if var == "plantes":
        return "MATCH" if _norm_floors(e) == _norm_floors(p) else ("CLOSE" if _norm_floors(e) in _norm_floors(p) or _norm_floors(p) in _norm_floors(e) else "MISMATCH")
    if var in TEXT_NORMALIZERS:
        e, p = TEXT_NORMALIZERS[var](e), TEXT_NORMALIZERS[var](p)
    e, p = _LABELS.sub("", e), _LABELS.sub("", p)
    a, b = _norm_text(e), _norm_text(p)
    if a == b or re.sub(r"\W", "", a) == re.sub(r"\W", "", b):
        return "MATCH"
    # Valors curts amb números (lab_depth, spt_depth_range…): mateixa seqüència numèrica = MATCH
    if len(a) <= 40 and _nums(e) and _nums(e) == _nums(p):
        return "MATCH"
    if var in NARRATIVE_VARS or len(a) > 60:
        r = difflib.SequenceMatcher(None, a, b).ratio()
        return "MATCH" if r >= 0.92 else ("CLOSE" if r >= 0.6 else "MISMATCH")
    if a in b or b in a:
        return "CLOSE"
    return "MISMATCH"


def cause_for(source: str) -> str:
    for name, rx in CAUSE_RULES:
        if rx.search(source or ""):
            return name
    return f"altres ({source[:25]})" if source else "sense font"


def compare(prefills: dict, eva: dict) -> list[dict]:
    rows = []
    pf = {k: v for k, v in prefills.items() if isinstance(v, dict)}
    for var, info in sorted(eva.items()):
        if var in SKIP_VARS:
            continue
        ev = info.get("value") if isinstance(info, dict) else info
        if ev is None or isinstance(ev, (list, dict)) or str(ev).strip() in ("", "---"):
            continue
        cands = EVA_TO_PREFILL.get(var, [var])
        key = next((c for c in cands if c in pf and str(pf[c].get("value") or "").strip() != ""), None)
        if key is None:
            st = "NOT_MAPPED" if not any(c in pf for c in cands) else "NO_DATA"
            rows.append({"var": var, "key": cands[0], "eva": ev, "pipe": None, "source": "", "status": st, "cause": ""})
            continue
        pv, src = pf[key].get("value"), str(pf[key].get("source") or "")
        st = status_for(var, ev, pv)
        rows.append({"var": var, "key": key, "eva": ev, "pipe": pv, "source": src, "status": st,
                     "cause": cause_for(src) if st == "MISMATCH" else ""})
    return rows


def _t(s, n=38) -> str:
    s = str(s).replace("\n", " ").replace("|", "/")
    return s if len(s) <= n else s[: n - 1] + "…"


def print_project(name: str, rows: list[dict]) -> None:
    c = collections.Counter(r["status"] for r in rows)
    print(f"\n### {name} — MATCH {c['MATCH']} · CLOSE {c['CLOSE']} · MISMATCH {c['MISMATCH']} · NO_DATA {c['NO_DATA']} · NOT_MAPPED {c['NOT_MAPPED']}\n")
    print("| variable Eva | camp wizard | Eva | wizard | font | estat | causa |")
    print("|---|---|---|---|---|---|---|")
    order = {"MISMATCH": 0, "CLOSE": 1, "NO_DATA": 2, "NOT_MAPPED": 3, "MATCH": 4}
    for r in sorted(rows, key=lambda r: (order[r["status"]], r["var"])):
        print(f"| {r['var']} | {r['key']} | {_t(r['eva'])} | {_t(r['pipe'] if r['pipe'] is not None else '—')} | {_t(r['source'], 30)} | {r['status']} | {r['cause']} |")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prefills"); ap.add_argument("--eva"); ap.add_argument("--name", default="projecte")
    ap.add_argument("--batch", nargs="*", help="TAG=prefills.json:eva.json")
    ap.add_argument("--md", action="store_true")
    args = ap.parse_args()
    jobs = []
    if args.batch:
        for b in args.batch:
            tag, rest = b.split("=", 1); p, e = rest.split(":", 1)
            jobs.append((tag, Path(p), Path(e)))
    else:
        jobs.append((args.name, Path(args.prefills), Path(args.eva)))

    all_rows: dict[str, list[dict]] = {}
    for tag, p, e in jobs:
        pf = json.loads(p.read_text(encoding="utf-8"))
        ev = json.loads(e.read_text(encoding="utf-8")).get("variables", {})
        all_rows[tag] = compare(pf, ev)
        print_project(tag, all_rows[tag])

    if len(all_rows) > 1:
        print("\n## Agregat\n")
        print("| projecte | vars | MATCH | CLOSE | MISMATCH | NO_DATA | NOT_MAPPED | encert (MATCH+CLOSE)/(comparables) |")
        print("|---|--:|--:|--:|--:|--:|--:|--:|")
        tot = collections.Counter()
        for tag, rows in all_rows.items():
            c = collections.Counter(r["status"] for r in rows); tot.update(c)
            comp = c["MATCH"] + c["CLOSE"] + c["MISMATCH"]
            print(f"| {tag} | {len(rows)} | {c['MATCH']} | {c['CLOSE']} | {c['MISMATCH']} | {c['NO_DATA']} | {c['NOT_MAPPED']} | {100 * (c['MATCH'] + c['CLOSE']) / comp if comp else 0:.0f}% |")
        comp = tot["MATCH"] + tot["CLOSE"] + tot["MISMATCH"]
        print(f"| **total** | {sum(len(r) for r in all_rows.values())} | {tot['MATCH']} | {tot['CLOSE']} | {tot['MISMATCH']} | {tot['NO_DATA']} | {tot['NOT_MAPPED']} | {100 * (tot['MATCH'] + tot['CLOSE']) / comp if comp else 0:.0f}% |")

        print("\n### MISMATCH per causa probable\n")
        print("| causa | n | variables (projecte) |")
        print("|---|--:|---|")
        by_cause = collections.defaultdict(list)
        for tag, rows in all_rows.items():
            for r in rows:
                if r["status"] == "MISMATCH":
                    by_cause[r["cause"]].append(f"{r['var']} ({tag})")
        for cause, items in sorted(by_cause.items(), key=lambda x: -len(x[1])):
            print(f"| {cause} | {len(items)} | {', '.join(items)} |")

        print("\n### Per variable (tots els projectes)\n")
        print("| variable | MATCH | CLOSE | MISMATCH | NO_DATA | NOT_MAPPED |")
        print("|---|--:|--:|--:|--:|--:|")
        by_var = collections.defaultdict(collections.Counter)
        for rows in all_rows.values():
            for r in rows:
                by_var[r["var"]][r["status"]] += 1
        for var, c in sorted(by_var.items(), key=lambda x: (-(x[1]["MISMATCH"] + x[1]["NO_DATA"] + x[1]["NOT_MAPPED"]), x[0])):
            print(f"| {var} | {c['MATCH']} | {c['CLOSE']} | {c['MISMATCH']} | {c['NO_DATA']} | {c['NOT_MAPPED']} |")


if __name__ == "__main__":
    main()
