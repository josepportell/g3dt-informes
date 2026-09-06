# Run parcial L1 — Linyola (preparat nit 5; LLANÇAT nit 6 amb permís del Josep)

Còpia de `2026-09-03-mesura-8/linyola/` (lectures cachejades per md5) SENSE `penetros.json` ni `_preext/` (el runner la regenera per al document que llegeix): el runner només re-llegirà
`PENETROS.pdf` (3 pàgines, manuscrit TPS) amb el skill v1.8 (L1: el full d'assaig SPT p.3 emet la fila `spt_ma_tests`
amb el registre de colpeig; 50 al primer tram → n30 «R»). Cost esperat: 1 document (vegeu STATUS §1.5). Sense
`_telemetry.jsonl` del run mare perquè el cost d'aquest run quedi aïllat.

Llançament (des de l'arrel del worktree; `login` = sessió claude.ai, no la clau API del `.env`):
    R=/home/josep/projects/claudecode-job/clients/g3dt-prod; cd "$R"
    PYTHONPATH=$PWD G3DT_CACHE_DIR=/home/josep/g3dt-prod-cache G3DT_LECTURA_CONSOLIDA=python .venv/bin/python - <<'PY'
    import json, time
    from pathlib import Path
    from automation.lectura.runner import run_lectura
    out = Path("docs/wizard-headless/mesures/runs/2026-09-05-l1-linyola"); t0 = time.time()
    ev = lambda k, d: print(json.dumps({"t": round(time.time()-t0, 1), "ev": k, **{a: b for a, b in d.items() if isinstance(b, (str, int, float, bool, type(None)))}}, ensure_ascii=False), flush=True)
    res = run_lectura(Path.home() / "g3dt-e2e/projectes/4001607 LINYOLA", out_dir=out, on_event=ev)
    print("DONE", (time.time()-t0)/60, "min; degraded", res.degraded)
    PY
Després: `compare_consolida.py` sobre `_decisions.json` d'aquesta carpeta vs `linyola/_reconsolida-2026-09-05-l3/` (cel·la
objectiu: `spt_ma_tests[0].n30`, or segur «R (rebuig; registre: 50 cops al primer tram de 15 cm)»).

## Resultat (2026-09-05, nit, 6)
- 8,6 min totals; `PENETROS.pdf` 463 s, 45 torns, **1,63 USD** (Sonnet 5, xhigh; run mare 2,07 USD); 19 documents en cache;
  cap timeout; consolidació Python 0,06 s, 0 conflictes. `_telemetry.jsonl` d'aquesta carpeta = només aquest run.
- La lectura 1.8 emet la fila `spt_ma_tests` («SPT1», P3, 1,00 a 1,75, `registre` [50, null, null, null], candidat «R» a la
  clau `value_candidates`). El consolidador la deixava en blanc (clau desconeguda + `int(None)` a la suma): arreglat al
  consolidador (DECISION-LOG nit, 6), NO al lector.
- `_reconsolida-2026-09-05-l1/`: consolidació amb el codi arreglat + `_compare_*.txt` vs l'or: `spt_ma_tests[0].n30` BUIT →
  CAUTELA «R» (or segur, n30 mai segur). Cap altra cel·la canvia respecte de `linyola/_reconsolida-2026-09-05-l3/`.
- `penetros.json` copiat al run mare (`2026-09-03-mesura-8/linyola/`); la lectura 1.6 substituïda és a `_anterior-skill-1.6/`
  (subcarpeta: `load_corpus` no hi entra).
