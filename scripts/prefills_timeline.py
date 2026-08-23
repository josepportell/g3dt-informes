#!/usr/bin/env python3
"""Timeline (Gantt) d'una obertura del wizard a partir del `g3dt.log` del servidor.

Per cada fase del pipeline de prefills: inici (s des del sync), durada, crides
HTTP per proveïdor dins la fase, i — si es passa `--prefills` — quants camps
del wizard porten una font ("source") que prové d'aquesta fase.

Marcadors (estables a `production/g3dt-eva-v1` + `review/prod-audit-2026-08`):
  sync             "synced <p>: N files"
  SmartScan        "SmartScan: N entries found"  (inclou Tier 3 Groq)
  FileMiner        "Content discovery:"
  groq_miner       "Phase 0.4 Groq: N missing variables"
  ConceptScout     "ConceptScout scanner:"  →  "ConceptScout: N concepts found (…ms)"
  deep_folder      "deep_folder_classifier: N candidates"
  geocode pre      primera línia geocode_coordinates després de deep_folder
  visió            "Vision phase: running extraction"  (+ "VISION OK|FAIL … type=X elapsed_ms=N")
  post-visió       primera línia wizard_service/cadastre_adjacents després de la visió
  síntesi LLM      "LLM synthesis:"  (fi dels prefills)
  informe          "Copied report to network" / "Error generating report"

Ús:
    python3 scripts/prefills_timeline.py RUN.log [--prefills prefills.json] [--wall SEG]
`--wall` = temps total de la crida /api/prefills mesurat fora (per calcular el sync).
Només lectura.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
from datetime import datetime
from pathlib import Path

TS = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(\d+) (\S+?):\d+ (\w+): (.*)$")
HOSTS = {"api.openai.com": "OpenAI", "api.groq.com": "Groq", "api.anthropic.com": "Anthropic",
         "openrouter.ai": "OpenRouter", "nominatim": "Nominatim", "catastro": "Cadastre",
         "icgc.cat": "ICGC", "mapillary": "Mapillary", "cartociudad": "CartoCiudad"}

PHASE_START = [
    ("SmartScan + Tier 3", re.compile(r"SmartScan: \d+ entries found")),
    ("FileMiner (text)", re.compile(r"Content discovery:")),
    ("groq_miner (0.4)", re.compile(r"Phase 0\.4 Groq: \d+ missing")),
    ("ConceptScout probes (0.45)", re.compile(r"ConceptScout scanner:")),
    ("deep_folder_classify", re.compile(r"deep_folder_classifier: \d+ candidates")),
    ("Visió per tipus (Fase 1)", re.compile(r"Vision phase: running extraction")),
    ("(fi) Síntesi LLM", re.compile(r"LLM synthesis:")),
]

# Font (prefills[k]["source"]) → fase que l'ha produïda
SOURCE_RULES = [
    ("ConceptScout probes (0.45)", re.compile(r"^(vision_probe:|concept_scout)")),
    ("groq_miner (0.4)", re.compile(r"^groq_llm:")),
    ("FileMiner (text)", re.compile(r"^(fileminer|contingut:)")),
    ("auto_extract Python (Excel/Lab/docs)", re.compile(r"^(docs intel|DPSH|lab |excel|dpsh_excel|/.*\.(pdf|xls|xlsx)$|.*GTL.*\.pdf$)", re.I)),
    ("Visió per tipus (Fase 1)", re.compile(r"^(sondeig|planol|dpsh vision|projecte|vision_(openai|anthropic|groq|chunked)|.*vision$|vision \(fotos)", re.I)),
    ("auto_extract: Lab/ICGC/geocode/adjacents/ortho", re.compile(r"^(Cadastre|geocode|ICGC|NCSE-02|CTE DB HS6|Nominatim|CartoCiudad|RD 470)", re.I)),
    ("Síntesi LLM", re.compile(r"^llm_synthesis")),
    ("Càlculs (Python)", re.compile(r"^(computed|Terzaghi|Schmertmann|Winkler|CTE D\.|CTE DB SE-C|2\.5×Nb|soil_type=|Hunt|Bowles)", re.I)),
    ("Defaults / sistema", re.compile(r"^(system|constant|default|plantilla|template|Eva template)", re.I)),
]


def parse(path: Path):
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = TS.match(line)
        if m:
            t = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").timestamp() + int(m.group(2)) / 1000
            rows.append((t, m.group(3), m.group(4), m.group(5)))
    return rows


def host_of(msg: str) -> str | None:
    m = re.search(r"https?://([^/\s\"]+)", msg)
    if not m:
        return None
    h = m.group(1)
    for k, v in HOSTS.items():
        if k in h:
            return v
    return h


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("log")
    ap.add_argument("--prefills")
    ap.add_argument("--wall", type=float, help="segons totals de /api/prefills (extern)")
    ap.add_argument("--opening", type=int, default=-1, help="índex d'obertura dins el log (per defecte l'última)")
    args = ap.parse_args()

    rows = parse(Path(args.log))
    # Split openings at each "synced" (network mode) or "SmartScan: N entries" line
    starts = [i for i, r in enumerate(rows) if re.search(r"^synced .*: \d+ files", r[3])]
    if not starts:
        starts = [i for i, r in enumerate(rows) if re.search(r"SmartScan: \d+ entries found", r[3])]
    if not starts:
        raise SystemExit("cap obertura trobada al log")
    i0 = starts[args.opening]
    i1 = starts[args.opening + 1] if args.opening + 1 < len(starts) and args.opening != -1 else len(rows)
    rows = rows[i0:i1]
    t0 = rows[0][0]

    # Phase boundaries
    bounds: list[tuple[str, float]] = []
    seen = set()
    vision_end = None
    for t, lg, lv, msg in rows:
        for name, rx in PHASE_START:
            if name not in seen and rx.search(msg):
                seen.add(name); bounds.append((name, t))
        if "Visió per tipus (Fase 1)" in seen and "Post-visió: adjacents + síntesi LLM" not in seen:
            if lg in ("web.wizard_service", "automation.cadastre_adjacents") and "Vision phase" not in msg:
                seen.add("Post-visió: adjacents + síntesi LLM"); bounds.append(("Post-visió: adjacents + síntesi LLM", t)); vision_end = t
        if "deep_folder_classify" in seen and "auto_extract: Lab/ICGC/geocode/adjacents/ortho" not in seen \
                and "Visió per tipus (Fase 1)" not in seen \
                and lg in ("automation.lab_extractor", "automation.icgc_geology", "automation.geocode_coordinates",
                           "automation.cadastre_adjacents", "automation.parcel_resolver", "automation.ortho_enrichment"):
            seen.add("auto_extract: Lab/ICGC/geocode/adjacents/ortho")
            bounds.append(("auto_extract: Lab/ICGC/geocode/adjacents/ortho", t))
    bounds.sort(key=lambda b: b[1])
    t_end = None
    report_t = None
    for t, lg, lv, msg in rows:
        if "LLM synthesis:" in msg:
            t_end = t
        if "Copied report to network" in msg or "Error generating report" in msg or "Generated report" in msg:
            report_t = t
    if t_end is None:
        t_end = rows[-1][0]

    # HTTP calls per phase
    def phase_at(t: float) -> str:
        cur = "sync / inici"
        for name, ts in bounds:
            if t >= ts:
                cur = name
        return cur

    http = collections.defaultdict(collections.Counter)
    http_err = collections.defaultdict(collections.Counter)
    vision_calls = []
    probe_ok = probe_fail = 0
    for t, lg, lv, msg in rows:
        if t > t_end:
            break
        ph = phase_at(t)
        if lg == "httpx" and "HTTP Request" in msg:
            h = host_of(msg) or "?"
            http[ph][h] += 1
            code = re.search(r'"HTTP/1\.1 (\d{3})', msg)
            if code and not code.group(1).startswith("2"):
                http_err[ph][f"{h} {code.group(1)}"] += 1
        if lg == "g3dt.vision":
            m = re.search(r"VISION (\w+) provider=(\S+) model=(\S+) file=(.+?) type=(\S+) .*elapsed_ms=(\d+)", msg)
            if m:
                vision_calls.append((m.group(5), m.group(1), m.group(2), m.group(3), m.group(4), int(m.group(6)) / 1000, ph))
        if lg == "automation.concept_scout.vision_probe":
            if "type=" in msg:
                probe_ok += 1
            elif "unprobed" in msg or "failed" in msg.lower():
                probe_fail += 1

    # Fields per phase
    fields = collections.Counter()
    unmapped = collections.Counter()
    total_fields = 0
    if args.prefills:
        pf = json.loads(Path(args.prefills).read_text(encoding="utf-8"))
        for k, v in pf.items():
            if k.startswith("_") or not isinstance(v, dict):
                continue
            total_fields += 1
            src = str(v.get("source") or "")
            for name, rx in SOURCE_RULES:
                if rx.search(src):
                    fields[name] += 1
                    break
            else:
                unmapped[src] += 1
                fields["(altres)"] += 1

    # ---- Output
    wall = args.wall
    span = t_end - t0
    print(f"Obertura: {rows[0][3][:70]}")
    print(f"Log span (sync → LLM synthesis): **{span:.0f} s**" + (f" · wall /api/prefills: **{wall:.0f} s** (sync+arrencada ≈ {wall - span:.0f} s)" if wall else ""))
    if report_t:
        print(f"Informe: {report_t - t_end:.1f} s després de la síntesi")
    print()
    print("| # | Fase | inici (s) | durada (s) | % | crides HTTP | errors HTTP | camps del wizard amb font d'aquí |")
    print("|--:|---|--:|--:|--:|---|---|--:|")
    allb = [("sync / inici", t0)] + bounds + [("(fi)", t_end)]
    for i in range(len(allb) - 1):
        name, ts = allb[i]
        dur = allb[i + 1][1] - ts
        calls = ", ".join(f"{h} {n}" for h, n in http[name].most_common()) or "—"
        errs = ", ".join(f"{h} ×{n}" for h, n in http_err[name].most_common()) or "—"
        fc = fields.get(name, "")
        print(f"| {i} | {name} | {ts - t0:.0f} | {dur:.1f} | {100 * dur / span:.0f}% | {calls} | {errs} | {fc} |")
    if args.prefills:
        others = {k: v for k, v in fields.items() if k not in dict(allb)}
        print()
        print(f"Camps del wizard (sense `_meta`): **{total_fields}**. Fonts que no corresponen a una fase del cronograma: "
              + ", ".join(f"{k} {v}" for k, v in others.items()))
        if unmapped:
            print("Fonts no classificades: " + "; ".join(f"`{k}` ×{v}" for k, v in unmapped.most_common()))
    print()
    print("Visió per tipus (ordre d'execució, en sèrie):")
    print()
    print("| tipus | resultat | proveïdor | model | fitxer | s |")
    print("|---|---|---|---|---|--:|")
    for vt, res, prov, model, f, s, ph in vision_calls:
        if vt == "deep_folder_classify":
            continue
        print(f"| {vt} | {res} | {prov} | {model} | {f} | {s:.1f} |")
    dfc = [c for c in vision_calls if c[0] == "deep_folder_classify"]
    if dfc:
        print(f"\ndeep_folder_classify: {len(dfc)} crides, {sum(c[5] for c in dfc):.1f} s en sèrie")
    print(f"ConceptScout probes amb resultat: {probe_ok}")


if __name__ == "__main__":
    main()
