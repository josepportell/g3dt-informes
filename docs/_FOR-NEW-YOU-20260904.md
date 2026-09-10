# FOR NEW YOU — 2026-09-04 (nit) — Mesura dels 8 FETA i agregada; ara toca prioritzar els fixes (fila 0b)

**Escrit:** 2026-09-04, tancament ordenat. Arbre net, tot committejat (`1bd7ab9` + aquest), branca
`experiment/nivell-a-2026-08` **ahead ~24 d'origin — SENSE push** (decisió del Josep pendent; pregunta-li).
Substitueix `_FOR-NEW-YOU-20260903.md` (que va quedar pedaçat dia a dia; conserva'l com a història).

## Ordre de lectura (30 min)

1. Aquest document.
2. `docs/wizard-headless/mesures/runs/2026-09-03-mesura-8/_AGREGAT-8.md` — **el resultat**: titular, els 4 ERR, on es
   perd la confiança, temps, cost, què queda.
3. `…/2026-09-03-mesura-8/_DIAGNOSTICS-INDEX.md` — taxonomia de causes (R1-R6, F1, D1-D6, I1, L1-L3, T1-T2, S1, C, G),
   fila per projecte i recompte transversal. Cada projecte: `{slug}/_NOTES.md` (números) + `_DIAGNOSTIC.md` (causes,
   amb línies de codi).
4. `STATUS.md` capçalera + `docs/PLA-CRITERIS-CALCUL-AL-CODI-2026-09-03.md` §Ordre (fila **0b** = els fixes sortits
   de la mesura, **pendents de prioritzar amb el Josep**).
5. `docs/DECISION-LOG.md` entrada 2026-09-04 (decisions de mètode + GO/NO-GO).
6. `docs/wizard-headless/mesures/CRITERIS-MESURA-2026-09-03.md` (amb l'esmena: Vilanova entra) i memòries
   `project_geotech_criteria_not_formulas`, `reference_fh11_readable_via_libfreehand`.

## Estat en una frase

El sistema **llegeix bé** (cap ERR de lectura per document als 7 comparables) i **decideix malament**: 64 % OK / 34 %
CAND / 4 ERR (1 de font d'Eva, 3 del consolidador per desempats mecànics contra informació que `_decisions.json` ja té).
Cap llindar pactat complert; estimació sense tocar criteris d'Eva: R1+R3+D3 → ~75 % OK, +R5+R2 → ~85 %.

## Decisions que només pot prendre el Josep (no les prenguis tu)

1. **Push** de la branca.
2. **Prioritat de la fila 0b**: D2 (dates), D3 (municipi/padró), R6 (taules: evidència positiva), I1 (`PDF_V0` /
   `.FH11`), R1 (equivalències: abreviatures G3, persona/despatx, TPS, adreces), R3 (`"1 de"`), D5 (CTE × N unitats),
   D4/D6 (runner), T1/T2 (latència), S1 (multi-casa: disseny), C (comparador, **abans de l'agregat mecànic**).
3. **Paquet de preguntes a Eva** (a `docs/PREGUNTES-EVA-PENDENTS.md` quan ho digui): E (P3), regla N20 (P4), T del
   pressupost = T de l'informe (R4), persona o despatx a `architect_name` (Linyola), **SPT P-1/P-3 creuats a Vilanova**
   (signat vs annex+tall), cota P-2 de Rubí (+212 vs +212,50).

## Què faria primer si em diu «endavant» sense més detall

Comparador (C) → regenerar `_compare_*.txt` dels 8 → `ledger.py` → comprovar que l'agregat mecànic coincideix amb
`_AGREGAT-8.md`. Després D2 + D3 + R3 (bugs purs, amb test cadascun) i re-mesurar només Linyola i Vilanova
(runs desacoblats, ~45 + ~32 min, ~30 USD). No tocar R2/R4/R5/F1 sense la resposta d'Eva o decisió explícita.

## Trampes conegudes (les d'ahir segueixen vigents: `_FOR-NEW-YOU-20260903.md` §Trampes i `…20260902.md` §3-§5)

- **Runs sempre desacoblats**: `setsid nohup .venv/bin/python docs/wizard-headless/mesures/run_mesura.py "<NOM>" <slug>
  > $SCRATCH/x.log 2>&1 < /dev/null &` + Monitor sobre el log (pgrep `run_mesura.py <expedient>`). Mai dos alhora.
  Un run mort es reprèn al mateix directori (cache per md5): aparta `_decisions.json`, `_elapsed.txt`,
  `_consolida_cache.json`; conserva `_telemetry.jsonl`. Temps = compost, digues-ho.
- **`PYTHONPATH=$PWD G3DT_CACHE_DIR=/home/josep/g3dt-prod-cache`** sempre; `cd` al worktree primer.
- **Abans de citar números**: grep DNS als logs (`/tmp/g3dt-lectura-<projecte>-*.log`, mtime ≥ inici del run) i al
  stdout; els `/tmp` desapareixen amb un reinici (el stdout del run 1 de Vilanova es va perdre).
- **Els ERR/ALERTA del comparador NO són ERR fins que els contrastes amb `_eva_truth/{slug}.json`** (18 falsos).
- `compare_consolida.py` peta amb Tulipa (or per casa); `classify_table` no entén capçaleres castellanes (Vilanova).
- El test `test_bell_lloc_bearing_idx_and_n20` és VERMELL a posta. Suite: `pytest tests/ -q --tb=no -rf > fitxer`.
- `reference-material/4001671 VILANOVA DE SEGRIA/4001671_informe.docx` és una còpia local NO versionada (l'original és
  a `C:\claude\g3dt\AI-pipeline\reference-material\…`); si falta, torna-la a copiar. Mai escriure a `/mnt/c`.
