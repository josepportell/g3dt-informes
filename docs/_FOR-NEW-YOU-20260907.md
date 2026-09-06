# FOR NEW YOU — 2026-09-07 — Bloc 1 tancat en codi (1.1 → 1.6), tot commitejat (T2 = `676070b`); següent 1.7 (Eva) i bloc 2

> **Substituït el mateix dia (17:05) per `_FOR-NEW-YOU-20260907-1705.md`** (bloc 2 fet i commitejat). Aquest document continua vigent per al costat de LECTURA (bloc 1).


**Escrit:** 2026-09-06, 13:50 (retocat 14:05: T2 commitejat). Per a la sessió següent (1.7 amb l'Eva; bloc 2).
Substitueix `_FOR-NEW-YOU-20260905-2315.md` com a punt d'entrada; conserva'l (§Regles d'interpretació, §Invariants dels
derivats, §Procediments de re-lectura parcial continuen vigents i no es repeteixen aquí). Branca `experiment/nivell-a-2026-08`,
in-place a `g3dt-prod/` (estat esperat).

**En una frase:** el matí ha commitejat 1.4 i 1.5 (`4c0e60d`, `19d6ca1`) i ha fet la peça 1.6 T2 a cost 0: la passada LLM de
conflictes (`claude -p --consolida --only-fields`) queda apagada per defecte després de codificar en Python les dues regles
que aportava; escalars **118/23/5/1/0 → 119 OK (81 %) / 22 CAND / 5 / 1 / 0**, taules **144/28/6/19/0** intactes, conflictes
A-vs-A 7 → 3, suite 31 vermells idèntics. **T2 commitejat: `676070b`** (33 fitxers: codi, tests, docs, `_reconsolida-2026-09-06-t2/` ×7, sessió). Arbre net.

## Ordre de lectura (15 min)

1. Aquest document.
2. `STATUS.md`: capçalera (2026-09-06) i §«Pendents de revisió» (or d'Alcoletge `soil_levels[1].a`; Linyola
   `mostra_del_nivell` material vs interval → pregunta 13).
3. `docs/DECISION-LOG.md`, entrada **2026-09-06** (T2: per què GTL > annex, per què la comanda NO és un nivell, què no s'ha
   fet a posta). Si cal el context de la nit anterior: entrades 2026-09-05 (nit, 4) → (nit, 8).
4. `docs/_FOR-NEW-YOU-20260905-2315.md` §Regles d'interpretació i §Invariants (derivats D1-D5, `_ma_sample_has_no_n30`,
   dialectes de `n30`): tot continua igual.
5. `docs/wizard-headless/mesures/runs/2026-09-03-mesura-8/_AGREGAT-8.md` §2026-09-06 i `_DIAGNOSTICS-INDEX.md` fila T2.
6. Per a 1.7: `docs/PREGUNTES-EVA-PENDENTS.md` (files 11-13; la 12 pot invertir els nivells de `lab_sample_id`).
7. Memòria: `project_mesura8_fila0b_fixes_2026-09-05` (actualitzada 2026-09-06).

## El que ha passat amb T2 i per què importa (no és al codi)

- **El handoff del 05 deia «la passada LLM no ha mogut cap valor, 9 de 9 iguals». Era fals.** La comparació era tautològica:
  la mesura v19 ja portava la resposta LLM fusionada (`llm_only_fields: True`), i es va comparar contra ella mateixa. Sense
  fusió, la passada pujava 3 escalars de `candidats` a `segur` (Castellar `utm_x`/`utm_y`, Rubí `lab_sample_id`), tots bons
  contra l'or → en `python` el marcador queia a 115 OK (78 %). **Lliçó:** quan un handoff diu «mesurat», torna a mesurar
  sense la fusió abans de decidir. La recepta és a §Procediments (script `t2_pyonly`-like: `consolidate_python` sol).
- **Les dues regles ara són precedència per camp** (`automation/lectura/consolidate.py` l.144-162, `_FIELD_PRECEDENCE`):
  `utm_x`/`utm_y` → el tipus `coordenades_gps` (senyal Python de `COORDENADES.txt`, P-1 per regla Pas 3) mana sobre qualsevol
  caixetí; `lab_sample_id` → `informe_laboratori` > {`annex_sondeig`, `annex_dpsh`}; comanda i full manuscrit fora de la
  llista (corroboren, mai bloquegen).
- **Evidència de GTL > annex (4/4 signats amb GTL):** Castellar «MA-1 (S1)» = GTL «MA1 S1», no l'annex «SPT-1»; Bell-lloc
  «SPT1 S1»; Rubí i Linyola «SPT-1 (P3)» = GTL «SPT1 P3». La frase del skill (Pas 3: «l'annex de l'Eva mana per l'etiqueta»)
  i la resposta de l'LLM contradiuen el signat de Castellar. Ors a `docs/golden-read/<projecte>/_decisions.json` →
  `decisions.lab.value.lab_sample_id`.
- **La comanda NO és un tercer nivell a posta** (a diferència de `lab_depth`, F1): Alcoletge, Vilanova i Anciles no tenen GTL
  ni annex amb etiqueta; pujarien a `segur` des de la comanda sola i els tres ors són `candidats` → el comparador marca
  «ALERTA prod puja a segur». No ho «arreglis» afegint-la.
- **El «P3» del manuscrit («Assaig de referència») és el punt, no l'etiqueta.** Era l'únic bloquejador de Rubí. El lector el
  posa a `lab_sample_id`; no cal tocar el skill: fora de la llista ja no bloqueja.
- **Els 3 conflictes que queden són `street_address`** (Castellar 18A vs 18A-18B-20; Bell-lloc dues vies de cantonada;
  Vilanova amb/sense número). L'LLM tampoc els resolia (tornava `candidats`). Són de la via A d'adreces
  (`docs/DISSENY-ADRECES-I-MUNICIPI-2026-09-01.md`), no d'aquesta peça.

## Invariants de codi (no desfer)

- `consolidate._FIELD_PRECEDENCE["utm_x"/"utm_y"]` = `(frozenset({"coordenades_gps"}),)`: sense el fitxer no hi ha senyal
  d'aquest tipus i els lectors competeixen com sempre (test `test_T2_utm_…`, cas `two`). No hi afegeixis cap altre tipus.
- `_annotate_utm_other_points` (l.334): només anota (`altres[].note` «= punt S-1 de COORDENADES.txt …»), mai canvia estat ni
  valor; compara un sol eix a ±1 m amb `extra["punts"]` del senyal Python. Es crida a la branca `segur` de `decide`.
- `_precedence_tier` (l.321) filtra QUI BLOQUEJA, no qui és primer: el guanyador continua sent `clusters[0]` (recompte de
  documents A, suma de confiança). Si mai dos caixetins coincidissin en S-1 i superessin el fitxer, P-1 no manaria: limitació
  apuntada al DECISION-LOG, cap cas al corpus. No la «resolguis» reordenant sense un cas i una mesura.
- `runner._load_config` (l.177): defecte `python`; el mode invàlid també hi cau. Tests: `test_default_consolida_mode_is_python_no_llm_pass`,
  `test_invalid_consolida_mode_falls_back_to_python`. `auto`/`llm` només per variable d'entorn.
- `reconsolida_mesura.py` ja NO fusiona `_consolida_only.json` (flag `--amb-llm`). Les subcarpetes fins a `-v19` la porten
  dins; `-t2` no. Comparar `-t2` amb `-v19` és comparar «Python amb regles» contra «Python + LLM»: és el que volem.
- El test sintètic `test_synthetic_project_contract_clean_and_fields` (l.853) té 2 assercions girades al comportament nou
  (`lab_sample_id` segur «MA1 S1»; `utm_x` segur amb S-1 anotat). Si un canvi les fa caure, mira primer si has tocat la
  precedència.
- Tot el de la nit anterior continua: `_derive_soil_levels` DESPRÉS de `_cota_relative_system` i `_depths_from_msnm`;
  `_ma_sample_has_no_n30` només si TOTES les etiquetes són MA; alies de claus de `n30`; «≥ 50 cops → R» només sense candidat
  escrit; `_preext/` de runs nous mai versionat (els dels runs parcials del 05 ja s'han esborrat).

## Procediments

```bash
R=/home/josep/projects/claudecode-job/clients/g3dt-prod; cd "$R"
git branch --show-current                                            # experiment/nivell-a-2026-08
# tests dels mòduls tocats (30 s)
PYTHONPATH=$PWD .venv/bin/python -m pytest tests/test_lectura_consolidate.py tests/test_lectura_service.py tests/test_field_dates_text.py tests/test_lectura_runner.py -q --no-header -p no:cacheprovider
# línia base (ha de donar 119/22/5/1/0 i 144/28/6/19/0)
PYTHONPATH=$PWD .venv/bin/python docs/wizard-headless/mesures/agrega_mesura.py --sub _reconsolida-2026-09-06-t2
# reconsolidació dels 7 a cost 0 (SENSE fusió LLM, com el runner) + TOTES les cel·les que canvien
PYTHONPATH=$PWD G3DT_CACHE_DIR=/home/josep/g3dt-prod-cache .venv/bin/python docs/wizard-headless/mesures/reconsolida_mesura.py _reconsolida-<data>-<motiu> _reconsolida-2026-09-06-t2
M=docs/wizard-headless/mesures/runs/2026-09-03-mesura-8; for s in castellar bell-lloc rubi linyola alcoletge vilanova anciles; do for k in escalars taules; do diff <(grep -v '^TOTALS' $M/$s/_reconsolida-2026-09-06-t2/_compare_$k.txt) <(grep -v '^TOTALS' $M/$s/_reconsolida-<data>-<motiu>/_compare_$k.txt) | grep '^[<>]' | sed "s/^/$s $k: /"; done; done
grep -o '[0-9]* conflictes A-vs-A' $M/*/_reconsolida-<data>-<motiu>/_decisions.json      # 1/1/0/0/0/1/0 (castellar … anciles)
# suite sencera (4 min) a fitxer, diff de NOMS vermells (31 esperats); després esborra el diagnòstic regenerat del dia
PYTHONPATH=$PWD .venv/bin/python -m pytest tests -q --no-header -p no:cacheprovider > /tmp/suite.txt 2>&1; diff <(grep '^FAILED' /tmp/suite.txt | sed 's/ - .*//' | sort) <(grep -v '^#' docs/wizard-headless/mesures/suite-vermells-esperats.txt | sort)
rm -f docs/diagnostics/ai_pipeline_demo-project_$(date +%Y%m%d).md   # la suite el crea amb la data del dia (untracked)
```

- **Mesurar què faria el runner sense cap ajut** (la comprovació que va desmuntar el handoff del 05): `consolidate_python(run,
  project_path=PROJECTES/name, project_name=name)` per slug, comparador `compare_consolida.py escalars|taules <decisions> <name>`,
  diff de veredictes contra la referència. `reconsolida_mesura.py` ja ho fa així per defecte.
- Dades: `~/g3dt-e2e/projectes/<NNNNNNN NOM>/`. Cache HTTP: `/home/josep/g3dt-prod-cache` (no netejar). Lectures = `{doc}.json`
  per md5 dins de cada run; cap lectura nova aquesta sessió (0 USD). Re-lectura parcial d'un document: recepta al handoff del
  05 §Procediments (dir sempre el cost abans: 0,6-2,1 USD per document, projecte sencer ≈ 18 USD).
- `rtk` retalla sortides llargues: redirigeix a fitxer i `grep`.

## Seqüència d'obertura suggerida

1. `git branch --show-current` + `git status --short` (esperat: arbre NET; `git log --oneline -4` = `676070b` T2,
   `1040591` handoff, `19d6ca1` 1.5, `4c0e60d` 1.4). Si hi ha canvis pendents, atura't i pregunta.
2. `git show --stat 676070b` si vols veure exactament què és T2 (33 fitxers).
3. Reprodueix la línia base t2 amb `agrega_mesura.py` (119/22/5/1/0; 144/28/6/19/0). Si no coincideix, atura't.
4. Tests dels 4 mòduls (verd) abans de tocar res.
5. Decideix amb el Josep l'ordre: 1.7 necessita l'Eva (R4 CTE imprès: 9 cel·les `cte_*`; persona/despatx `architect_name`
   Linyola; preguntes 11-13). Si l'Eva no hi és, bloc 2 amb línia base ABANS de codificar (`compare_tables_vs_eva.py`,
   memòria `reference_compare_tables_vs_eva_harness`: harness diferent del comparador de lectura).
6. Qualsevol canvi del consolidador: reconsolidació a cost 0 contra `-t2` + llista de cel·les + suite a fitxer amb diff de noms.

## Què NO fer

- No afegir `comanda_lab_g3` a `_FIELD_PRECEDENCE["lab_sample_id"]` (ALERTA a 3 projectes; vegeu més amunt).
- No reordenar clústers per precedència sense un cas real i una mesura.
- No fiar-se d'una mesura «amb LLM» per decidir sobre l'LLM: reconsolida sense fusió (ara és el defecte del script).
- No re-llegir documents per mesurar un canvi del consolidador; cap lectura sense dir-ne el cost.
- No tocar l'or (`docs/golden-read*/`): els pendents d'Alcoletge i Linyola són decisió del Josep.
- No afegir perdó al comparador; no canviar el format dels derivats per igualar un or.
- No proposar pull/merge a l'Eva; no tocar `geocode_coordinates.py` (via B).
- No versionar `docs/diagnostics/ai_pipeline_demo-project_<avui>.md` (la suite el crea) ni cap `_preext/` de run nou.
- No parlar en codis al Josep («T2», «D3»): tradueix a què passa, on, què costa; rutes absolutes.

## Tasques obertes

- **1.7 (amb l'Eva):** R4 CTE imprès, persona/despatx; preguntes 11-13 de `docs/PREGUNTES-EVA-PENDENTS.md`. La 12 (SPT-1 vs
  MA-1 a Castellar) decideix si `lab_sample_id` es queda GTL > annex (ara) o s'inverteix (una línia a `_FIELD_PRECEDENCE`).
- **Pendents de revisió del Josep** (`STATUS.md` §): or d'Alcoletge `soil_levels[1].a` (`no_trobat` vs «fins al fons»);
  Linyola `mostra_del_nivell` material vs interval.
- **Bloc 2:** P0 columna N, P2a col·lapse de nivells, P2b fondària de sabata, M341 mesura completa amb línia base primer
  (`docs/PLA-CRITERIS-CALCUL-AL-CODI-2026-09-03.md`). **Bloc 3:** S1 multi-casa (capa intermèdia a la branca, després branca nova).
- **Peces futures apuntades, no planificades** (del handoff del 05): banda de color «Nivells» de l'annex DPSH com a font
  explícita de transició per punt; «N=R» del tall cap a `n30`; rastre de dialectes de claus; «material vs interval».
- **`street_address` amb dues fonts A** (3 projectes): via A d'adreces, no T2.

## Guanys que no surten a cap taula

- **Producció sense la crida LLM de conflictes:** per a cada projecte nou de l'Eva, 205-264 s menys (523 s a Tulipa), ~1 USD
  de subscripció menys i un punt de fallada menys (el CLI no emet res fins al final; Vilanova va penjar-se un cop). El que
  l'LLM decidia bé ara és determinista i testejat; el que decidia malament (Castellar «SPT-1» primer) ja no passa.
- **Els commits del matí deixen la història neta per peça:** `4c0e60d` = 1.4 (amb STATUS reconstruït a l'estat de la nit 4),
  `19d6ca1` = 1.5 + skill v1.9 + runs parcials sense `_preext` (2 × 37 MB regenerables esborrats). `git show --stat` de
  cadascun diu exactament què és de qui.
- **Una manera de verificar handoffs:** el script de comprovació (consolidació Python sola + comparador + diff contra la
  referència) ha costat 0 USD i 2 minuts, i ha canviat la decisió. Val la pena repetir-lo a l'obertura de cada peça que
  parteixi d'una afirmació «mesurada» d'una sessió anterior.
