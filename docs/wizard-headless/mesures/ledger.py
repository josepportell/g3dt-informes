#!/usr/bin/env python3
"""Llibre de mesures del wizard headless — regenera LEDGER.md a partir de runs/*/.

Cada run és una carpeta `runs/<label>/` amb, com a mínim: `meta.json` (condicions,
judici de qualitat), `_telemetry.jsonl` (files del runner), `escalars.txt` i
`taules.txt` (sortida de `../fase0-acceptacio/compare_consolida.py`). Opcionals:
`_decisions.json`, `run.log`, `consolida.log`, `perdoc/`.

Ús:  python3 docs/wizard-headless/mesures/ledger.py            # regenera LEDGER.md
     python3 docs/wizard-headless/mesures/ledger.py --json     # resum per run a stdout

Afegir un run: copiar els artefactes a runs/<label>/, escriure meta.json (copia'n
un d'existent), executar aquest script. No editar LEDGER.md a mà.
"""
from __future__ import annotations
import ast, json, statistics, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"


def _totals(path: Path) -> dict:
    if not path.exists():
        return {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("TOTALS:"):
            try:
                return ast.literal_eval(line.split(":", 1)[1].strip())
            except Exception:
                return {}
    return {}


def _wall_reconstructed(docs: list[dict], cons_s: float, k: int) -> float:
    slots = [0.0] * k
    for r in sorted(docs, key=lambda r: r.get("ts_start", "")):
        i = slots.index(min(slots)); slots[i] += r["elapsed_s"]
    return max(slots) + cons_s


def summarize(run_dir: Path) -> dict:
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    rows = []
    tp = run_dir / "_telemetry.jsonl"
    if tp.exists():
        rows = [json.loads(l) for l in tp.read_text(encoding="utf-8").splitlines() if l.strip()]
    docs = [r for r in rows if r.get("mode") == "only" and not r.get("cached")]
    # Consolidacio: la DARRERA (LLM sencera `consolida`, o Fase 12 `consolida_python` + opcional `consolida_only`).
    cons_all = [r for r in rows if str(r.get("mode", "")).startswith("consolida")]
    last_full = max((i for i, r in enumerate(cons_all) if r["mode"] in ("consolida", "consolida_python")), default=None)
    cons = cons_all[last_full:] if last_full is not None else []
    contaminated = set(meta.get("contaminated_docs") or [])
    clean = [r for r in docs if r.get("doc") not in contaminated]
    el = [r["elapsed_s"] for r in docs]
    el_clean = [r["elapsed_s"] for r in clean]
    turns = [r.get("num_turns") for r in docs if r.get("num_turns") is not None]
    out_tok = [((r.get("usage") or {}).get("output_tokens") or 0) for r in docs if r.get("cli_json_ok")]
    cost = [r.get("cost_usd") or 0 for r in rows if r.get("cost_usd") is not None]
    cons_s = sum(r["elapsed_s"] for r in cons) if cons else 0.0
    cons_llm = [r for r in cons if r["mode"] in ("consolida", "consolida_only")]
    k = int(meta.get("concurrency") or 2)
    s = {
        "label": meta["label"], "date": meta.get("date"), "model": meta.get("model"),
        "concurrency": k, "skill_version": meta.get("skill_version"),
        "changes": meta.get("changes_since_previous", ""),
        "n_docs": len(docs), "n_ok": sum(1 for r in docs if r.get("rc") == 0 and r.get("json_valid")),
        "n_timeouts": sum(1 for r in docs if r.get("timeout")),
        "sum_s": round(sum(el)), "median_s": round(statistics.median(el_clean)) if el_clean else None,
        "min_s": round(min(el_clean)) if el_clean else None, "max_s": round(max(el_clean)) if el_clean else None,
        "turns_total": sum(turns) if turns else None,
        "turns_per_doc": round(sum(turns) / len(turns), 1) if turns else None,
        "output_tokens_docs": sum(out_tok) if out_tok else None,
        "consolida_s": round(cons_s, 2) if cons else None,
        "consolida_mode": "+".join(r["mode"] for r in cons) if cons else None,
        "consolida_turns": cons_llm[0].get("num_turns") if cons_llm else (0 if cons else None),
        "consolida_out_tok": ((cons_llm[0].get("usage") or {}).get("output_tokens")) if cons_llm else None,
        "cost_equiv_usd": round(sum(cost), 2) if cost else None,
        "wall_real_s": meta.get("wall_real_s"),
        "wall_reconstructed_s": round(_wall_reconstructed(docs, cons_s, k)) if docs else None,
        "escalars": _totals(run_dir / "escalars.txt"), "taules": _totals(run_dir / "taules.txt"),
        "erroni_amb_confianca_fons": (meta.get("quality_judgement") or {}).get("erroni_amb_confianca_fons"),
        "quality_notes": (meta.get("quality_judgement") or {}).get("notes", []),
        "contaminated_docs": sorted(contaminated), "contamination_note": meta.get("contamination_note"),
        "conditions": meta.get("conditions", ""),
        "comparator_revision": meta.get("comparator_revision"),
    }
    return s


def _m(x, unit=""):
    return "—" if x is None else f"{x}{unit}"


def _min(x):
    return "—" if x is None else f"{x/60:.0f} min"


def render(summaries: list[dict]) -> str:
    L = ["# Llibre de mesures — wizard headless (Castellar, 13 documents a `claude`)", "",
         "Generat per `ledger.py` a partir de `runs/*/`. **No editar a mà.** Una fila per run; els artefactes crus són a la carpeta del run.",
         "Criteri de qualitat que mana: **erroni-amb-confiança de fons = 0** (valor `segur` diferent de l'or); ERR/ALERTA de format es llegeixen un per un (`meta.json` → `quality_judgement.notes`).", "",
         "## Temps", "",
         "| run | model | conc. | canvi respecte l'anterior | docs OK | suma claude | mediana/doc (nets) | turns/doc | tokens sortida docs | consolidació | paret real | paret reconstruïda | cost equiv. |",
         "|---|---|--:|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|"]
    for s in summaries:
        L.append(f"| `{s['label']}` | {s['model']} | {s['concurrency']} | {s['changes']} | {s['n_ok']}/{s['n_docs']} "
                 f"({s['n_timeouts']} timeouts) | {_min(s['sum_s'])} | {_m(s['median_s'],' s')} ({_m(s['min_s'])}-{_m(s['max_s'])}) | {_m(s['turns_per_doc'])} "
                 f"| {_m(s['output_tokens_docs'])} | {_m(s['consolida_s'],' s')} / {_m(s['consolida_turns'])} turns ({s['consolida_mode'] or '—'}) | {_min(s['wall_real_s'])} | {_min(s['wall_reconstructed_s'])} | {_m(s['cost_equiv_usd'],' $')} |")
    L += ["", "*paret reconstruïda* = planificació de llista dels `elapsed_s` per document amb `conc.` slots + consolidació (model, no mesura). "
          "*cost equiv.* = `total_cost_usd` del CLI (amb subscripció no es factura; és el pes de la feina).", "",
          "## Qualitat (comparador d'or `compare_consolida.py`)", "",
          "Comparador **v2** (2026-08-25, normalitzadors de format + files de taula alineades per clau): els `.txt` de tots els runs s'han regenerat; "
          "els totals d'abans (v1) són a «Condicions» per a cada run (`meta.json` → `comparator_revision`).", "",
          "| run | erroni-amb-confiança (fons) | escalars OK / CAUTELA / ALERTA / ERR / NOU | taules OK / CAUTELA / ALERTA / ERR / ABSENT | lectura dels no-OK |",
          "|---|--:|---|---|---|"]
    for s in summaries:
        e, t = s["escalars"], s["taules"]
        L.append(f"| `{s['label']}` | **{_m(s['erroni_amb_confianca_fons'])}** | {e.get('OK',0)} / {e.get('CAUTELA',0)} / {e.get('ALERTA',0)} / {e.get('ERR',0)} / {e.get('NOU',0)} "
                 f"| {t.get('OK',0)} / {t.get('CAUTELA',0)} / {t.get('ALERTA',0)} / {t.get('ERR',0)} / {t.get('ABSENT',0)} | " + "<br>".join(s["quality_notes"]) + " |")
    L += ["", "## Condicions i contaminacions", ""]
    for s in summaries:
        cr = s.get("comparator_revision") or {}
        before = (f" · comparador v1 (abans del {cr.get('date')}): escalars {cr.get('escalars_before')} · taules {cr.get('taules_before')}"
                  + (f" · {cr['note']}" if cr.get("note") else "")) if cr else ""
        L.append(f"- `{s['label']}` — {s['conditions']}" + (f" · **contaminats:** {', '.join(s['contaminated_docs'])} ({s['contamination_note']})" if s["contaminated_docs"] else "") + before)
    L += ["", "## Per a la taula «abans/després» de l'Eva", "",
          "L'*abans* de l'Eva és la via B a producció (`docs/audit/DIAGNOSTIC-PROD-2026-08-23.md`: prefills Castellar 275 s, 59 % de camps iguals als de l'Eva sobre els 8 projectes; "
          "`docs/audit/VERIFICACIO-FIXES-2026-08-22.md`). Les mètriques que li importen són *camps correctes sense tocar-los*, *camps que ha hagut de corregir*, "
          "*temps fins al formulari* i *temps fins a l'informe*; aquest llibre guarda els artefactes crus perquè es puguin recomputar amb `scripts/compare_tables_vs_eva.py` "
          "i `docs/golden-read-taules/_eva_truth/` quan la Fase 8b (taules → generador) estigui feta.", ""]
    return "\n".join(L) + "\n"


def main() -> int:
    summaries = [summarize(d) for d in sorted(RUNS.iterdir()) if (d / "meta.json").exists()]
    if "--json" in sys.argv:
        print(json.dumps(summaries, ensure_ascii=False, indent=1)); return 0
    (HERE / "LEDGER.md").write_text(render(summaries), encoding="utf-8")
    print(f"LEDGER.md: {len(summaries)} runs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
