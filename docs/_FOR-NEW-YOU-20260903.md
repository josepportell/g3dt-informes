# FOR NEW YOU — 2026-09-03 — Castellar 1/8 i Bell-lloc 2/8 fets, or Castellar corregit; queden 6 projectes de mesura

**Escrit:** 2026-09-03, tancament abrupte (tall de connexió del Josep). Arbre net, tot committejat, branca
`experiment/nivell-a-2026-08` **ahead 8 d'origin — SENSE push** (el Josep no el va demanar; pregunta-li).

## Ordre de lectura

1. Aquest document.
2. `STATUS.md` capçalera + `docs/PLA-CRITERIS-CALCUL-AL-CODI-2026-09-03.md` §Ordre (la taula és l'estat viu).
3. `docs/RECERCA-CRITERIS-DESCRITS-ALS-INFORMES-2026-09-03.md` — el repàs R: 7/7 informes, cites amb pàgina.
4. `docs/ANALISI-CALCUL-N20-E-2026-09-02.md` — sobretot la **postil·la final** (correccions post-R).
5. `docs/wizard-headless/mesures/CRITERIS-MESURA-2026-09-03.md` — els criteris de la mesura en curs.
6. Memòria `project_geotech_criteria_not_formulas` — el destil·lat de tot.

## Què va passar avui (2026-09-02 tarda → 09-03)

- **Tasca 0 tancada:** el test vermell de N20 és deriva de fixture de visió, NO regressió de càlcul. Es queda
  VERMELL (decisió Josep) fins a P4. Marc «criteris, no fórmules» persistit a 4 capes.
- **Mesura 1/8 — Castellar:** 33,4 min, taules 28/1/0, **ERR de sistema = 0**. Els 2 «ERR» d'escalars (utm)
  són **errors de L'OR** (l'or porta l'S-1 de l'annex; el signat porta el P-1 de COORDENADES.txt, que és el
  que el sistema va triar). Vegeu `runs/2026-09-03-mesura-8/castellar/_NOTES.md`.
- **Repàs R fet** (agent paral·lel): P1 (cel·la Nb) **descartada** — el /0,83 és correcte, factor imprès als
  fulls DPSH; P3 (E) negatiu → **pregunta a Eva imprescindible**; P4 patró parcial («el tram on treballarà la
  fonamentació») + **banda de tolerància obligatòria** (Eva té 4 discrepàncies internes als seus informes);
  **Anciles capgirat** (fonamenta a L2 via pous encastats 20-40 cm — CRITERIS-CALCUL-EVA §1 ho llegia al revés);
  troballa d'or: **la frase del Qa del signat DECLARA el nivell portant** (5 projectes).

## Sessió 2 (2026-09-03 vespre, tallada per bateria)

- **Or de Castellar corregit** (utm = P-1) i recompte definitiu **14/5/2/1, ERR 0** (`ad4912d`). Punt 2 de sota FET.
- **Bell-lloc 2/8 FET** (`d4dd1fa`): ERR 0; escalars **11 OK / 10 CAUTELA** (l'or segur, prod candidats amb el bo
  dins — `municipality`, `field_date`, `lab_testing_company`… = **infraconfiança**, pendent de diagnosticar);
  taules 17/3/1/0. **Temps compost 34,9 + 13,1 = 48 min, NO comparable**: el run 1 va morir als 34,9 min per causa
  externa (tall). Vegeu `runs/2026-09-03-mesura-8/bell-lloc/_NOTES.md`.
- **Lliçó:** llança el driver **desacoblat** de la sessió (`setsid nohup … &` + Monitor sobre el log), no com a
  Bash en segon pla del harness: un tall de connexió mata la tasca del harness, no el procés `setsid`.
- Branca ahead **11** d'origin, sense push (pregunta-li).

## La feina següent, per ordre

1. **Continuar la mesura (6 projectes: Rubí primer)** — seqüencial, mai dos alhora:
   ```bash
   cd ~/projects/claudecode-job/clients/g3dt-prod
   PYTHONPATH=$PWD G3DT_CACHE_DIR=/home/josep/g3dt-prod-cache \
     setsid nohup .venv/bin/python docs/wizard-headless/mesures/run_mesura.py "3001631 RUBI" rubi > $SCRATCH/rubi.log 2>&1 < /dev/null &
   # després: "4001607 LINYOLA" linyola · "4001670 ALCOLETGE" alcoletge ·
   # "4001671 VILANOVA DE SEGRIA" vilanova · "4001679 ANCILES" anciles · "3001706 C.TULIPA CERDANYOLA" tulipa
   ```
   Després de cada projecte: `compare_consolida.py escalars|taules "<run>/_decisions.json" "<CARPETA OR>"`
   (la carpeta or és el NOM sota `docs/golden-read/`), desar `_compare_*.txt` + `_NOTES.md`, grep DNS, commit.
2. ~~Corregir l'or de Castellar~~ FET (sessió 2). ~~Diagnosticar la infraconfiança de Bell-lloc~~ FET (2026-09-04):
   `runs/2026-09-03-mesura-8/bell-lloc/_DIAGNOSTIC-INFRACONFIANCA.md` — **cap dels 10 és error de lectura; tot és
   política de `consolidate.decide()`** (5 causes R1-R5: formes de la mateixa entitat com a contradicció ×4, concepte
   veí bloquejant ×2, bug substring `"1 de"` al guard de `num_floors`, `_NEVER_SEGUR_FIELDS` sobregeneralitzat ×2,
   convergència amb lectors humils ×1). R1+R3 sols → 16/21. NO aplicar fins acabar la mesura dels 8.
3. **P0** (columna N = SPT N30) i **P2a** (col·lapse Rubí) — després que la mesura estigui completa.
4. **M341** (mesura de les 341 variables) — vegeu pla.
5. **Paquet de preguntes a Eva**: criteri de l'E (R ho fa imprescindible), regla N20 mono-nivell, `.doc` de
   Vilanova. Afegir-les a `docs/PREGUNTES-EVA-PENDENTS.md` quan el Josep digui.

## Trampes conegudes

- El driver necessita `PYTHONPATH` (el sys.path agafa el dir del script, no el cwd).
- **Mai** dos projectes de mesura en paral·lel (límit d'ús = HTTP 400 silenciós que degrada el run).
- El test `test_bell_lloc_bearing_idx_and_n20` és VERMELL a posta — no el «repareu» (anàlisi §1).
- Suite: `pytest tests/` des de l'arrel amb `-q --tb=no -rf > fitxer` SENSE pipe; 32 fallades preexistents
  (ara 33 amb el N20 documentat) — compara NOMS.
- Tota la resta de regles del handoff anterior (`_FOR-NEW-YOU-20260902.md` §3-§5) segueixen vigents.
