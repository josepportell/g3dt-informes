# Fase 8 — E2E real del wizard headless (2026-08-24, WSL, claude 2.1.241, skill v1.2→1.3)

**Què:** dos projectes reals (còpies locals a `~/g3dt-e2e/projectes/`, mai `/mnt/c`) llegits per `claude -p` de veritat.
Bell-lloc pel runner directe (driver); **Castellar pel wizard sencer** (Playwright: dropdown → `/api/lectura-stream` →
runner → consolidació → merge → badges de 3 estats a la UI, 0 errors de consola). Evidència: `*_decisions.json` +
`*_telemetry.jsonl` d'aquest directori; comparador `../fase0-acceptacio/compare_consolida.py`.

## Resultat de qualitat (contra l'or de la lectura d'or) — erroni-amb-confiança = 0 als dos projectes

| Projecte | Crides | Errors/timeouts (a 600 s) | Escalars vs or | Taules vs or | Validador |
|---|--:|--:|---|---|---|
| Bell-lloc | 17 only + 1 consolida (1 cache, 1 duplicat) | 0 / 0 | 18 OK · `num_floors` mateix valor reordenat · `utm_x/y` no_trobat (vegeu forat 1) · `architect_company` nou | 18 OK · `spt_ma` en comptes (regla v1) · nivell de cobertura de l'or absent (candidat, no error) | OK |
| Castellar | 13 only + 1 consolida | 0 / 0 | 15 OK · 4 més prudents que l'or (bo dins dels candidats) · `street_address`/`building_type` mateix valor, format/CLOSE | 17 OK · 3 format (`-4,0` vs `-4`) · claus de fila no canòniques (→ skill v1.3) | OK |

Detalls que confirmen les regles d'or en producció: Castellar `cota_referencia` = candidats amb "-4 m (respecte el carrer)"
primer (l'ERR històric no es repeteix); profunditats DPSH -1,08/-0,48/-0,76/-1,55 exactes; n30 = candidats ['R'] mai segur;
Bell-lloc SPT registre [24,34,28,30] amb candidats 62|58.

## Resultat de temps (la troballa dura)

| Mesura | Bell-lloc | Castellar |
|---|---|---|
| Per document (min / mediana / màx) | 108 / 279 / 501 s | 142 / 264 / 418 s |
| Suma de temps `claude` | 86 min | 64 min |
| Consolidació | 562 s | 585 s |
| Paret (concurrència 2, **els dos projectes solapats**) | 58 min | 37 min |

Cost fix per crida ≈ 100-120 s (un `.txt` de 3 línies triga 108-118 s): arrencada del CLI + CLAUDE.md + skill de 40 KB +
exploració Python en sessió. L'estimació del disseny (5-12 min el primer open) **no s'aguanta**: mesurat 35-60 min amb
concurrència 2 i dos projectes alhora. Segona obertura: cache per md5 → 0 crides (verificat: `DADES CLIENT.txt` cached).

## Forats trobats (i estat)

1. **Fonts Python no-g3_templates invisibles al consolidador** (`COORDENADES.txt`, Cadastre): el consolidador cec no les veu
   → `utm_x/y` i `referencia_catastral` surten `no_trobat` a la lectura encara que la via B els ompli. La UI mostra
   "no trobat" al costat d'un camp ple. → Següent: emetre els lectors Python (coordenades, cadastre) com un `_python_readers.json`
   més a `--out`, o enrutar-los a claude (barats). PENDENT.
2. **Timeouts**: 240 s per document matava els pesants; 360 s de consolidació hauria matat totes dues consolidacions.
   → defectes 600 / 900 s (`f91fa0d`, `30920d5`). FET.
3. **Autenticació**: el `.env` de la via B filtra `ANTHROPIC_API_KEY` sense crèdit al fill → `G3DT_LECTURA_AUTH=login` (`bb7b4f3`). FET.
4. **Claus de fila no canòniques** (`prof_extraccio`, `punt`/`cota_inici` al sondeig) → skill v1.3 + àlies + validador (`ce01aa6`). FET.
5. **Progrés invisible durant la lectura** (`#lectura-progress` dins del formulari ocult) → mirall a l'stepper (`f91fa0d`). FET.
6. Seleccions de taula de la UI (`lecturaState.selections`) encara no viatgen al backend/generador. PENDENT (Fase 8b).

## Palanques de temps a decidir (Josep)

- Concurrència 3-4 (les crides són latència d'API, no CPU): paret ÷ ~1,5-2.
- Reduir el cost fix: prompt headless prim (sense CLAUDE.md del repo: `cwd` neutre + skill instal·lat com a user-command),
  skill "mode --only" més curt que el de 40 KB.
- Enrutar menys documents: `*_fotografies.pdf`, `LAB-SIG.pdf`, còpies `Print To PDF` (`tall.pdf`, `pl. situaci.pdf`) quan
  ja hi ha el `PDF/ANNEXES/` equivalent → 4-5 crides menys per projecte.
- Consolidació Python-first (només conflictes a claude): -9 min.

## GO/NO-GO de la Fase 8

✅ Pipeline sencer funciona a WSL amb claude real (runner + servei + UI). ✅ Erroni-amb-confiança = 0 (2 projectes). ✅ Cache.
⏳ Temps del primer open inacceptable tal qual per a l'Eva (35-60 min) — palanques a sobre. ⏳ Windows sense provar.
⏳ Forat 1 i Fase 8b. Veredicte: **GO tècnic, NO-GO de latència** fins a aplicar palanques i remesurar.

---

## Addendum 2026-08-24 (nit) — Fase 9: runner instrumentat + remesura de Castellar SOL (concurrència 2 i 3)

**Què ha canviat al runner** (`automation/lectura/runner.py`, +85 LOC, 73 tests verds): `--model` fixat (`G3DT_LECTURA_MODEL`, defecte `sonnet`) i
`--output-format json` a totes les crides; l'envolupant JSON del CLI (stdout a un sidecar) alimenta `_telemetry.jsonl` amb `num_turns`,
`duration_api_ms`, `cost_usd`, `usage` (tokens) i `models`; el log humà conserva el text final sota `--- result ---`. Verificat amb el CLI real.

**Llibre de mesures:** `docs/wizard-headless/mesures/` (`ledger.py` → `LEDGER.md`; `runs/<etiqueta>/` amb telemetria, decisions, comparador,
per-doc, `meta.json` amb condicions i judici ERR per ERR). Tres files: E2E de la tarda (línia base), run 1 (conc. 2), run 2 (conc. 3).

### Temps (Castellar sol, 13 documents a `claude`, Sonnet 5, login)

| run | paret real | suma `claude` | mediana/doc | turns (docs) | tokens sortida (docs) | consolidació | cost equiv. |
|---|--:|--:|--:|--:|--:|--:|--:|
| E2E tarda (conc. 2, **solapat** amb Bell-lloc) | 37 min | 64 min | 264 s | — | — | 585 s | — |
| run 1 · conc. 2 | *invàlida* (tall de connexió 20:43-22:01; 2 docs contaminats) | 70 min | 290 s | 269 (8-36; ≈ 21/doc) | 342k | 474 s / 26 turns / 49k tok | $17,7 |
| run 2 · conc. 3 (net) | **33 min** (22:26→23:02) | 61 min | 292 s | 268 (10-31; ≈ 21/doc) | 306k | 677 s / 24 turns / 72k tok | $15,4 |

- **La paret reconstruïda per planificació de llista prediu bé** (run 2: 32 min predits vs 33 reals) → serveix per estimar sense córrer:
  conc. 2 ≈ 43 min, conc. 3 ≈ 32, conc. 4 ≈ 26 (amb la consolidació actual).
- **Els turns són estables (≈ 21/doc, 268-269 en total)**: el cost és el *protocol* del skill, no l'atzar. El que varia entre runs és el temps per
  turn (tall.pdf: 34 turns/591 s al run 1 vs 29/349 s al run 2).
- **El temps és de generació, no de context**: 306-342k tokens de sortida per 13 JSON finals de ~2k tokens cadascun (15-25× més del que s'escriu
  al fitxer). Vegeu la sonda de turns més avall.
- **La consolidació és el pas més variable** (474-677 s; 49-72k tokens de sortida) i és l'impost que paga *qualsevol* canvi de fitxer (annex §7.2).
- Cost fix del CLI (arrencada + 1 volta): 4-14 s (benchmark §1 de l'annex). Les xifres d'aquí tenen els 9 MCPs del Josep carregats; a l'ordinador
  de l'Eva no hi seran (−10 s/crida, no més).

### Qualitat (comparador d'or; criteri: erroni-amb-confiança de fons)

| run | escalars OK/CAUTELA/ALERTA/ERR | taules OK/CAUTELA/ALERTA/ERR/ABSENT | **erroni-amb-confiança de fons** |
|---|---|---|--:|
| E2E tarda | 15 / 4 / 1 / 1 | 16 / 1 / 1 / 3 / 6 | 0 |
| run 1 | 14 / 4 / 2 / 1 | 20 / 1 / 2 / 1 / 3 | 0 |
| run 2 | 17 / 1 / 3 / 0 | 17 / 1 / 2 / 3 / 4 | 0 |

Tots els ERR són de format (`-4,0` vs `-4`; `1,0 - 1,2 m` vs `-1,00 a -1,20 m`; variants del mateix carrer). Els ALERTA de fons, un per un:

1. **`cota_referencia` puja a `segur` '570.90 msnm' amb una sola font — 2/2 runs de la Fase 9** (a l'E2E de la tarda era candidats amb el relatiu
   primer). El valor coincideix amb el preferit de l'or (`+570,90`), així que no és un valor erroni; és **excés de confiança reproduïble**: el
   lector cec de l'annex DPSH no emet el "-4 m (respecte el carrer)" com a candidat escalar (només com a `cota_inici` de taula) i el consolidador
   veu una font i tanca. **Guard determinista** (Fase 12, `soft_normalize`): `segur` amb 1 font i sense senyal g3_templates ≥ 0,9 → candidats.
2. `spt_ma_tests` amb 2 files al run 2 (SPT-1 i MA1: mateix punt S-1, mateixa fondària 1,0-1,2 m) = la mateixa mostra amb dos identificadors;
   bloc `candidats`. Regla de fusió determinista punt+fondària (Fase 12).
3. `sondeig_tests[0].cota`: prod candidats només amb el relatiu '-4 m'; or `segur` '570,90 msnm'. **Conflicte entre el skill (Pas 3b: la cel·la és
   relativa, l'absoluta és `cota_referencia`) i l'or** — decisió Josep/Eva, no error del model.
4. `building_type`: CLOSE (article/adjectiu), com sempre.

**Veredicte de qualitat:** 0 erroni-amb-confiança de fons als tres runs; la variació entre runs és de *format* i de *confiança*, i tots dos
casos de confiança tenen guard determinista. No hi ha motiu de qualitat per canviar de model (Fable queda com a opció mesurable:
`G3DT_LECTURA_MODEL=fable ~/g3dt-e2e/fase9/run.sh 3 fable-c3` → nova fila al llibre).

### Sonda de turns (`--output-format stream-json`, `tall.pdf`)

`tall.pdf` amb `stream-json --verbose`: **20 turns, 293 s d'API, 25,8k tokens de sortida**, dels quals només ~7k són visibles (9 Bash + 5 Read +
1 Write + text) → ~75 % és raonament. Dels 15 usos d'eina: 5 són *construir-se l'eina* (`fitz` per comptar pàgines, extreure text,
renderitzar pàgina sencera, meitats i localitzador), 2 redundants (`ls`/`find`, `md5sum` que l'inventari ja té), 2 de cerimònia d'escriptura
(`os.replace` + rellegir) i 6 de lectura/escriptura real. Detall: `docs/wizard-headless/mesures/probes/2026-08-24-tall-stream-json/turns.md`.
**Palanca resultant (no toca la cura):** pre-extracció determinista a l'inventari (text per pàgina, PNG sencer + meitats, Excel→CSV,
.msg→cos+adjunts) + `write_doc_json.py` (payload per stdin, escriptura atòmica al nom canònic). Estimació −35-45 % per document mirant les
mateixes imatges. A mesurar com a fila nova del llibre abans d'adoptar-la.

### Palanques, revisades amb les mesures

| palanca | efecte estimat | toca la cura? |
|---|---|---|
| concurrència 3 (mesurat) / 4 | 43 → 33 (mesurat) / ≈ 26 min | no |
| pre-extracció Python dels documents (text per pàgina, imatges 100 dpi, Excel→CSV, .msg cos+adjunts) perquè el model llegeixi en lloc de construir-se l'eina | a decidir amb la sonda: si ≥ ⅓ dels turns són "obrir el fitxer", −30-40 % de turns i tokens | **no** (llegeix el mateix, més directe) |
| consolidació Python-first (annex §7.2) | −8-11 min per run i per cada canvi de fitxer | només si el comparador d'or ho avala |
| prompt prim (sense CLAUDE.md/MCPs) | −5-10 s/crida | no |

*Fi addendum Fase 9. Instrumentació + remesura: 33 min reals a conc. 3, 0 erroni-amb-confiança, el cost és generació (≈ 21 turns/doc).*

## Addendum 2026-08-25 (matí) — Experiment de pre-extracció determinista (`preext-c3`): −24 % per document, 28 min de paret, NO adoptat encara

Fila `2026-08-25-preext-c3` del llibre (`docs/wizard-headless/mesures/LEDGER.md`; artefactes a `runs/2026-08-25-preext-c3/`).
Codi: `automation/lectura/preext.py`, `scripts/write_doc_json.py`, `scripts/render_clip.py`, skill-còpia
`.claude/commands/g3dt-llegir-projecte-preext.md` (v1.3 amb 4 blocs canviats: accés al document i escriptura; Pas 0/3/3b intactes),
flag `G3DT_LECTURA_PREEXT` al runner (defecte apagat = prompt byte-idèntic). Commit `0dfff32`.

### Temps (Castellar sol, conc. 3, Sonnet 5, login; run net 11:11:16 → 11:39:18)

| | `sonnet-c3` (ref.) | `preext-c3` | Δ |
|---|--:|--:|--:|
| pre-extracció | — | 13,2 s (13/13, 72 MB, 99 PNG, cap > 3 MB) | +13 s |
| mediana/doc | 292 s | **221 s** | **−24 %** |
| suma `claude` docs | 60,6 min | 55,7 min | −8 % |
| turns/doc | 20,6 | 17,3 | −16 % |
| tokens sortida docs | 306k | 239k | −22 % |
| consolidació | 677 s / 24 turns | 539 s / 33 turns | — (banda 474-677) |
| **paret real** | **33 min** | **28 min** | **−15 %** |

Per document, dos règims: els annexos d'una pàgina baixen 30-45 % (`tall.pdf` 349→206 s, `3001621_DPSH.pdf` 292→191,
`3001621_DPSH.xls` 386→212, pressupost `.msg` 196→135) i els **multipàgina pugen** (`ACCEPTACIO` 7 p: 23→28 turns, 276→342 s;
`PENETROS + SONDEIG` 5 p: 31→39 turns; `LAB-SIG` 13→17 turns). Causa (reading_notes): amb sencer + meitats pre-renderitzats
per a totes les pàgines, el model se les mira totes (7 txt + 7 png + 14 meitats) en lloc de renderitzar només el que necessita.

### Qualitat (comparador d'or; judici a `meta.json`)

- **Erroni-amb-confiança de fons = 0.** Els 5 ERR són format: `field_date` `24/10/2025` vs `2025-10-24`; `cota_inici` `-4` vs `-4,0` ×3
  (idèntic a c3); `profunditat` signe/decimals.
- **Regressió de candidats (criteri d'adopció NO complert):** `nivell_freatic` a 5 files (4 DPSH + sondeig) passa de `segur 'No detectat'`
  a `no_trobat`. Causa declarada pel model (`annexes_3001621_dpsh.json` → reading_notes): el Pas 3b exigeix comprovar el **color** de
  cel·la (`xlrd formatting_info=True`) i la pre-extracció v1 no exporta colors → correcte que no ho afirmi, però és cobertura perduda.
  `lab_sample_id` i `num_soil_levels` baixen de `segur` a `candidats` amb el bo dins (n=1; dins la banda de soroll?).
- **Millores:** `spt_ma_tests` ja no duplica SPT-1/MA1; `sondeig_tests[0].cota` porta el valor de l'or entre candidats (c3: no);
  l'excés de confiança a `sondeig_tests[0].spt_ma` desapareix. `cota_referencia` puja a `segur` amb 1 font per 3a vegada → Fase 12.
- El protocol s'aplica intacte: `render_clip.py` usat a ACCEPTACIO (manuscrit p.5 a 400 dpi), PENETROS (450-600 dpi), plànol de situació;
  cap `fitz` escrit a mà; cap `ls`/`md5sum`; escriptura amb `write_doc_json.py` en una ordre.

### Veredicte i v2

**NO adoptat** (candidats empitjoren per un forat corregible). Pre-extracció v2 a mesurar (`preext-v2-c3`):
1. Excel: `sheet-i.colors.txt` (cel·les amb fons no per defecte: `REF<TAB>color<TAB>valor`; xlrd `formatting_info=True` / openpyxl fill).
2. PDF: meitats només per a pàgines amb `text_ok=false`; regla al skill: no mirar meitats si la sencera ja és llegible; clip sota demanda.
3. `text_ok` per producer (Distiller/PScript5 → false encara que hi hagi ≥ 20 alfanumèrics: avui el text brossa del sondeig annex passa per bo).
Criteri d'adopció idèntic: 0 erroni-amb-confiança de fons i cap cel·la que baixi d'estat respecte a `sonnet-c3`.

*Fi addendum 2026-08-25 matí. Pre-extracció v1: −24 % per document, 28 min de paret, 0 erroni-amb-confiança, 5 cel·les de nivell freàtic perdudes pel color d'Excel → v2.*

## Addendum 2026-08-25 (vespre) — Pre-extracció v2 (`preext-v2-c3`): 26 min de paret, −37 % per document, regressió de la v1 resolta; l'effort estava heretat

Fila `2026-08-25-preext-v2-c3` (commit `5fdaa97`). Canvis v1→v2: `sheet-i.colors.txt` (colors de cel·la d'Excel, fons blanc de plantilla filtrat),
meitats de pàgina només quan `text_ok=false`, `text_ok` per ràtio de caràcters normals ≥ 0,75 (producer Distiller només informatiu: l'ACCEPTACIO
és Distiller amb text net), skill-còpia "llegir amb economia".

| | `sonnet-c3` | v1 | **v2** |
|---|--:|--:|--:|
| mediana/doc | 292 s | 221 s | **184 s (−37 %)** |
| turns/doc · tokens sortida | 20,6 · 306k | 17,3 · 239k | **14,8 · 212k** |
| suma docs | 60,6 min | 55,7 | **44,5** |
| consolidació | 677 s | 539 s | 614 s (2a: 589 s) |
| **paret** | **33 min** | 28 | **26,2 min (−21 %)** |

Tots 13 documents més ràpids que la referència; els multipàgina redreçats (ACCEPTACIO 28→16 turns); `DPSH.xls` una mica més lent que a la v1 perquè
ara llegeix 95 cel·les de color (volgut). Pre-extracció: 6,7 s, 55 PNG (v1: 99).

**Consolidació, dues mostres amb els mateixos 13 JSON:** la 1a (dins el run) escriu les cel·les de taula en dialecte pla (`"cota_inici": "-4 m"`) i
perd `num_floors` (que el correu emet) → comparador 23 ABSENT; la 2a (`consolida2/`, cache, 589 s) és canònica. 1 de 6 consolidacions → cop
d'atzar, però cal l'**embolcall determinista de cel·les planes** al contracte (Fase 12). El judici de qualitat va sobre la 2a.

**Qualitat (vs `sonnet-c3`):** erroni-amb-confiança de fons **0** (ERR = format: `street_address`, `cota_inici` ×3, `profunditat`). Cas límit:
`sondeig_tests[0].nivell_freatic` `segur 'No indicat'` vs or `'No detectat'` — mateix fet, redacció → regla de vocabulari al skill.
**Regressió v1 resolta**: `dpsh_tests[*].nivell_freatic` ×4 OK. **Millores**: `cota_referencia` OK (primer run sense excés de confiança),
`spt_ma` sense duplicat ni excés. **Baixades `segur`→`candidats` amb el bo dins**: `lab_sample_id`, `num_soil_levels`, `utm_x`, `utm_y` (1 font →
candidats: el guard de la Fase 12 ho imposaria igual). `merge_degradat` sobre els perdoc dels 3 runs = lectura equivalent → les baixades són soroll del
consolidador.

**Proposta:** adoptable (decisió del Josep: flipar `G3DT_LECTURA_PREEXT` per defecte i portar els 4 blocs al skill de producció).

**Troballa col·lateral (pregunta del Josep):** tots els runs del llibre han corregut a **effort `xhigh`** heretat (`CLAUDE_EFFORT` + `effortLevel`
del settings del Josep); el runner ara fixa `--effort` (`G3DT_LECTURA_EFFORT`, defecte xhigh) i treu `CLAUDE_EFFORT` de l'entorn del fill. Files
següents: Fable@xhigh sobre v2 (decisió Josep: si comparable → Sonnet), després Sonnet@high i @medium.

*Fi addendum 2026-08-25 vespre. Pre-extracció v2: 26 min, −37 %/doc, 0 erroni-amb-confiança, regressió resolta; effort heretat descobert.*
