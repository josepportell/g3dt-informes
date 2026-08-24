"""Acceptació Fase 0: compara _decisions.json produïts pels agents --consolida vs l'or.

Ús: python3 compare_consolida.py escalars|taules
Veredictes per camp: OK (mateix estat), CAUTELA (or segur -> produït candidats amb el bo dins),
ALERTA (produït més confiat que l'or, o valor segur != or), NOU (clau v1 sense or), ERR (valor segur discrepant).
"""
import json, re, sys, unicodedata
from pathlib import Path

S = Path(__file__).parent
REPO = Path("/home/josep/projects/claudecode-job/clients/g3dt-prod")

def norm(v):
    if v is None: return ""
    s = unicodedata.normalize("NFKD", str(v)).encode("ascii", "ignore").decode()
    return re.sub(r"[\s.,;:+()\-']+", "", s).lower()

def close(a, b):
    na, nb = norm(a), norm(b)
    return na == nb or (na and nb and (na in nb or nb in na))

def flat_gold_scalars():
    d = json.load(open(REPO / "docs/golden-read/4001612 BELL-LLOC/_decisions.json", encoding="utf-8"))["decisions"]
    out = {}
    for k, v in d.items():
        st = v.get("status") or v.get("estat")
        if k in ("lab", "cte") and isinstance(v.get("value"), dict):
            for sk, sv in v["value"].items():
                out[sk] = {"estat": st, "value": sv}
        elif k == "utm_x_utm_y":
            m = re.search(r"X\s*([\d.]+)\s*;\s*Y\s*([\d.]+)", str(v.get("value", "")))
            out["utm_x"] = {"estat": st, "value": m.group(1) if m else v.get("value")}
            out["utm_y"] = {"estat": st, "value": m.group(2) if m else v.get("value")}
        else:
            out[k] = {"estat": st, "value": v.get("value")}
    return out

def cand_values(f):
    return [c.get("value") for c in (f.get("candidates") or []) if isinstance(c, dict)]

def verdict(gold, prod):
    ge, pe = gold["estat"], prod.get("estat")
    gv, pv = gold.get("value"), prod.get("value")
    if pe == ge:
        if ge == "segur" and not close(gv, pv):
            return "ERR", f"segur discrepant: or={gv!r} prod={pv!r}"
        return "OK", ""
    if ge == "segur" and pe == "candidats":
        if any(close(gv, c) for c in cand_values(prod)) or close(gv, pv):
            return "CAUTELA", f"or segur, prod candidats (bo dins): {gv!r}"
        return "ALERTA", f"or segur {gv!r} NO entre candidats {cand_values(prod)!r}"
    if ge == "candidats" and pe == "segur":
        ok = any(close(pv, c) for c in cand_values(gold)) or close(gv, pv)
        return "ALERTA", f"prod puja a segur ({pv!r}); or candidats" + ("" if ok else " i valor fora dels candidats d'or!")
    return "ALERTA", f"estat or={ge} prod={pe} (or value={gv!r})"

def run_escalars():
    gold = flat_gold_scalars()
    prod = json.load(open(S / "consolida-escalars/_decisions.json", encoding="utf-8"))
    assert prod.get("schema_version") == 1, "schema_version != 1"
    pf = prod["fields"]
    bad_dialect = [k for k, v in pf.items() if "status" in v or any("source" in c for c in (v.get("candidates") or []) if isinstance(c, dict))]
    if bad_dialect: print("DIALECTE ANTIC a:", bad_dialect)
    counts = {}
    for k in sorted(set(gold) | set(pf)):
        if k not in gold:
            print(f"NOU      {k:22s} prod={pf[k].get('estat')}"); counts["NOU"] = counts.get("NOU", 0) + 1; continue
        if k not in pf:
            print(f"ABSENT   {k:22s} (or={gold[k]['estat']})"); counts["ABSENT"] = counts.get("ABSENT", 0) + 1; continue
        v, msg = verdict(gold[k], pf[k])
        counts[v] = counts.get(v, 0) + 1
        if v != "OK": print(f"{v:8s} {k:22s} {msg}")
    print("TOTALS:", counts)

def run_taules():
    gold = json.load(open(REPO / "docs/golden-read-taules/4001612 BELL-LLOC/_tables_decisions.json", encoding="utf-8"))["tables"]
    prod = json.load(open(S / "consolida-taules/_decisions.json", encoding="utf-8"))
    pt = prod["tables"]
    counts = {}
    for block in ("dpsh_tests", "sondeig_tests", "spt_ma_tests", "soil_levels"):
        g, p = gold.get(block) or {}, pt.get(block) or {}
        grows = g.get("rows") or []
        prows = p.get("rows") or []
        print(f"-- {block}: or {len(grows)} files / prod {len(prows)} files")
        for i, gr in enumerate(grows):
            pr = prows[i] if i < len(prows) else {}
            for cell, gv in gr.items():
                if not isinstance(gv, dict) or "estat" not in gv: continue
                pv = pr.get(cell)
                if not isinstance(pv, dict):
                    print(f"ABSENT   {block}[{i}].{cell} (or={gv['estat']})"); counts["ABSENT"] = counts.get("ABSENT", 0) + 1; continue
                # regles dures
                if cell == "n30" and pv.get("estat") == "segur":
                    print(f"VIOLACIO {block}[{i}].n30 = segur (prohibit)"); counts["VIOLACIO"] = counts.get("VIOLACIO", 0) + 1
                v, msg = verdict(gv, pv)
                counts[v] = counts.get(v, 0) + 1
                if v != "OK": print(f"{v:8s} {block}[{i}].{cell} {msg}")
    sl = (pt.get("soil_levels") or {}).get("rows") or []
    for i, r in enumerate(sl):
        lit = r.get("litologia") if isinstance(r.get("litologia"), dict) else None
        if lit and lit.get("estat") == "segur":
            print(f"VIOLACIO soil_levels[{i}].litologia = segur (prohibit)"); counts["VIOLACIO"] = counts.get("VIOLACIO", 0) + 1
    print("TOTALS:", counts)

if __name__ == "__main__":
    (run_escalars if sys.argv[1] == "escalars" else run_taules)()
