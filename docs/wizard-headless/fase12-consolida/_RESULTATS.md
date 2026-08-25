# Fase 12 — Consolidació Python-first: acceptació contra l'or (2026-08-25, nit)

**Què és:** `automation/lectura/consolidate.py` substitueix la crida LLM `--consolida` sencera (8-10 min, 3 lliçons de
pèrdua en 2 dies) per una consolidació determinista sobre els `{doc}.json`, `_g3_templates.json`, `_inventory.json` i dues
fonts Python noves (nom de la carpeta → `expedient`; `ANNEXES/ALTRES/COORDENADES.txt` → `utm_x`/`utm_y`/z). Els conflictes
reals (dues fonts d'autoritat A de documents diferents que discrepen) van a una crida LLM curta `--consolida --only-fields`
(skill v1.5) que escriu `_consolida_only.json`; Python en fusiona només les cel·les demanades si passen el contracte.
Mode del runner: `G3DT_LECTURA_CONSOLIDA=auto` (defecte: Python + LLM només amb conflictes) | `python` | `llm` (Fases 3-11).

**Instrument:** `harness.py` — per a cada joc de perdoc ja llegit (4 de Castellar, 1 de Bell-lloc), consolida amb Python,
valida el contracte, passa `compare_consolida.py` (escalars + taules) i compara **cel·la a cel·la** amb el veredicte de la
consolidació LLM de referència del MATEIX joc (OK > CAUTELA > ALERTA/ERR/ABSENT). Sortides a `out/<joc>/`. Cap crida LLM.

## 1. Resultat (5 jocs, 0 erroni-amb-confiança de fons a tots)

| joc de perdoc (lectura) | referència LLM | escalars Python OK/CAUT/ALERTA/ERR | taules Python OK/CAUT/ALERTA/ERR/ABSENT | cel·les **per sota** de la ref. | per sobre | conflictes → LLM | temps |
|---|---|---|---|--:|--:|---|--:|
| Sonnet v2 c3 (`preext-v2-c3`) | `consolida2` (2a consolidació Sonnet) | 14 / 5 / 2 / 0 | 20 / 1 / 1 / 3 / 2 | **0** | 5 | 0 | 0,02 s |
| Fable v2 c3 | `fable-preext-v2-c3` | 15 / 5 / 1 / 0 | 23 / 2 / 0 / 0 / 2 | **0** | 1 (`lab_depth`) | 0 | 0,02 s |
| Opus 4.8 @high v2 c3 | `opus48-high-preext-v2-c3` | 14 / 5 / 2 / 0 | 22 / 1 / 1 / 1 / 2 | **0** | 2 (`num_floors`, `cte_edificacio`) | 0 | 0,02 s |
| Sonnet v1.3 c3 (24-08, sense preext) | `sonnet-c3` | 14 / 5 / 2 / 0 | 20 / 2 / 0 / 3 / 2 | 4 (tot CAUTELA amb el bo dins) | 5 | 2 (`utm_x/y`) | 0,02 s |
| Bell-lloc v1.2 (24-08) | — (or directe) | 12 / 9 / 0 / 0 | 16 / 3 / 0 / 0 / 2 | — | — | 1 (`street_address`, cantonada) | 0,02 s |

**Criteri d'acceptació de l'annex §7.2/§11 — complert:** 0 erroni-amb-confiança de fons als 2 projectes (i als 3 models);
cap cel·la per sota de `consolida2`/Fable; consolidació < 60 s (és < 0,1 s). Les 4 cel·les "per sota" del joc v1.3 són
`candidats` amb l'or dins (utm P-1 vs S-1, MA-1 vs SPT-1, 1 vs 2 nivells): conservadores, no errònies.

### Lectura dels no-OK que queden (tots de format o de fixture)
- `dpsh_tests[*].cota_inici` ERR ×3 (jocs Sonnet): `-4 m (respecte el carrer)` (literal de l'annex DPSH) vs or `-4,0 m …`. Mateix
  fet; el comparador compara cadenes normalitzades. Fable/Opus van llegir `-4,0` i surt OK.
- `spt_ma_tests[0].profunditat` ERR (joc Opus): `1,0 - 1,2 m` (GTL, autoritat A per a `lab_depth`/`profunditat`) vs or
  `-1,00 a -1,20 m`. Mateix interval.
- `street_address` ALERTA (jocs Sonnet/Opus): `candidats` amb 3 formes de la mateixa adreça; l'or (`Carrer Arbrells, 18A, 18B i 20`,
  del correu del client) no és entre les 3 formes literals (sí a `altres`). Fable la té (conf. 0,85 al seu perdoc) → OK.
- `sondeig_tests[0].cota` ALERTA (jocs Sonnet-v2/Opus): regla d'or Pas 3b aplicada (sistema relatiu: `-4 m` primer, absoluta
  segona, mai `segur`); l'or de taules (anterior a la regla) diu `segur 570,90` i la forma literal `570.90 msnm (absolut, segons…)`
  no li és "close". Contingut correcte segons la regla; fixture per revisar.
- `building_type` ALERTA (tots els jocs i tots els models): comparació CLOSE (`feedback_building_type_close_match`).
- `soil_levels[*].de_a_estat` ABSENT ×2: cel·la que només existeix al fixture d'or de Castellar.

## 2. Què fa el consolidador (regles codificades, `consolidate.py`)

1. **Senyals:** `tier_a` de cada `{doc}.json` (+ `NOT_*` → `descartats`; conceptes fora de les 22 claus → `extra_concepts`;
   `utm_x_utm_y`/`lab`/`cte` desglossats), `_g3_templates.json` (autoritat A si conf ≥ 0,9), Python (carpeta, COORDENADES).
   Duplicats per md5 no compten; document previst sense JSON → `"lectura fallida: {doc}"` a `sources_checked`.
2. **Compatibilitat de valors:** dates (completes/parcials, `24/10/25` = `2025-10-24` = `Octubre 2025`), numèrics (`-4 m` =
   `-4,0 m`; fondàries amb `abs`: `1,0 - 1,2` = `-1,00 a -1,20`), text (accents/puntuació/stopwords fora; `S-1` = `S1`;
   prefix/sufix = lectura parcial del mateix valor: `C/ ARBRELLS 18 A` ⊂ `C/ARBRELLS 18A-18B-20`; MAI contenció interior:
   `entre el carrer X i el carrer Y` no fusiona X amb Y). Union-find → clusters ordenats per (té A, nº documents, suma conf).
3. **`segur`** només amb 1 font A (claude conf ≥ 0,8 / g3 ≥ 0,9 / Python) sense contradicció, o convergència de ≥ 3 documents
   independents amb conf ≥ 0,6; contradicció = altre cluster amb A o conf ≥ 0,4 (camps; `client_name` 0,6: el formulari p.5
   mana) / només A (cel·les de taula: els altres documents són corroboració, Pas 3b). Formes A diferents dins el cluster →
   `candidats` amb totes les formes.
4. **Guards de camp (Pas 3):** `cte_*` mai segur; `architect_name` mai segur si persona+despatx o = client; `client_name` mai
   segur si conté ARQUITECT o és G3; `referencia_catastral` mai segur sense consulta del Cadastre; `num_soil_levels` mai
   segur sense annex/tall; `superficie_parcela` mai segur amb 2+ RC; `num_floors` mai segur si "1 de N unitats".
   Taules: `n30`, `litologia`, `spt_ma` mai segur; `a` de l'últim nivell mai segur; `id` SPT annex≠GTL → candidats sense
   conflicte LLM; **sistema de cotes**: si les cotes DPSH de l'annex són relatives, la cota del sondeig és relativa primer
   (documentada al manuscrit, o "prestada" del DPSH amb font `(sistema relatiu del projecte: cota DPSH)`), l'absoluta segona, mai segur.
5. **Derivats sancionats pel skill, sempre etiquetats i mai segur:** `architect_name` ← client `(practica Eva…)`;
   `cte_edificacio` ← superfície construïda `(derivat: regla Eva C0/C1…)`; `cte_sol` `T-1` i `lab_testing_company` `TPS`
   `(coneixement previ…)` només quan cap document ho diu. `nivell_freatic` absent → `No detectat` (vocabulari v1.5).
6. **Cap senyal es perd:** `candidates` (≤ 3) + `altres` (la resta, amb font i cita). Test automàtic sobre els 7 jocs de
   perdoc del llibre: cada `tier_a` és a candidats/altres/descartats/extra.
7. **Conflictes** (`conflicts[]`, paths `fields.x` / `tables.bloc[fila].cel·la`): A-vs-A de documents diferents (dues alternatives
   del mateix document són una cautela del lector, no un conflicte) → crida `--only-fields`. Castellar (3 jocs v2): 0.

## 3. Runner (mode `auto`) mesurat in situ — Castellar, 13 documents en cache

`run_lectura(force=False)` amb `_decisions.json` esborrat: 5,4 s de paret (pre-extracció 5 s + inventari + consolidació **0,04 s**),
0 crides LLM, `_decisions.json` escrit pel runner (abans l'escrivia el skill), comparador idèntic al harness (14/5/2/0 · 22/1/1/1/2).
Fila del llibre: `2026-08-25-opus48-docs-python-consolida` (mateixos perdoc que `opus48-high-preext-v2-c3`, l'únic canvi és el
consolidador: 480 s → 0,04 s; `num_floors` recuperat, `cte_edificacio` amb font, cap `-4,20 m` inventat).

## 4. Crida real `--only-fields` — Bell-lloc (1 conflicte: `street_address`, cantonada)

Run real `run_lectura(force=False)` amb `G3DT_LECTURA_CONSOLIDA=auto` sobre el workspace de Bell-lloc (18 documents en cache, perdoc
v1.2 del 24-08; `_decisions.json` esborrat abans). Artefactes a `out/belloc-auto-real/`.

- Pre-extracció 11,4 s + inventari + consolidació Python 0,02 s → 1 conflicte (`fields.street_address`: `C/MESTRE RAMON ORTIZ 15` A ×3 vs
  `C/ ANTONI BALLET` A ×1 de la comanda, cantonada) → crida `claude -p /g3dt-llegir-projecte … --consolida --only-fields fields.street_address`
  (Sonnet @xhigh): **228 s, 18 turns, 20k tokens de sortida, 0,91 $ equiv.** Paret total 241 s.
- El skill (v1.5) ha fet exactament el que diu el Pas 5b: cap document obert (només `_decisions.json`, 7 `{doc}.json` implicats,
  `_g3_templates.json`), ha escrit `_consolida_only.json` amb `{schema_version, fields: {street_address: cel·la v1}, notes}`; 3 candidats,
  **tots amb valor present als senyals** (cap invenció): 1) `Situat entre el carrer Antoni Bellet i el carrer Mestre Ramon Ortiz (Bell-lloc)`
  (plànol de situació; "redacció de l'Eva, corroborada per 3 annexos"), 2) `C/MESTRE RAMON ORTIZ 15` (pressupost, "aporta el número de portal"),
  3) `C/ ANTONI BALLET` (comanda; "grafia probable error de transcripció de Bellet; mantingut per transparència"). `estat: candidats`.
- `merge_only_fields` l'ha aplicat (`llm_only_fields: true`, `altres` de Python conservats: 20 senyals); contracte net; comparador d'or
  idèntic a la sortida Python sola (12 OK / 9 CAUTELA / 0 ERR; taules 16/3/0/0/2): l'or diu `candidats` i el LLM ha confirmat l'ordre
  que Python ja tenia (regla "entre el carrer X i el carrer Y" → candidat 1).
- Lectura: la crida funciona i és segura (guards + contracte + fusió selectiva), però en aquest cas no aporta qualitat (mateix estat, mateix
  ordre) i costa 3,8 min. Objectiu del skill (< 3 min) no assolit per poc; n=1. Si als propers projectes el patró es repeteix (el LLM
  confirma Python), `G3DT_LECTURA_CONSOLIDA=python` és el defecte candidat i la crida es reserva per a conflictes d'escalars d'identitat
  (`client_name`, `expedient`) — decisió pendent amb dades de 2-3 projectes més.

## 5. Tests

`tests/test_lectura_consolidate.py` (55 tests: claus de compatibilitat, regles de `decide`, projecte sintètic complet amb
COORDENADES/duplicat md5/lectura fallida/NOT_/utm/lab/cte, sistema de cotes, guards, `merge_only_fields`, `wrap_flat_cells`,
i els 7 jocs de perdoc del llibre) + 8 tests nous al runner (auto sense conflictes = 0 crides + fitxer escrit; conflicte
sintètic → `--only-fields fields.expedient` + fusió; `python` mai LLM; resposta LLM invàlida → es queda la Python; `llm` = via
antiga; degradat escriu fitxer; cache; mode invàlid → auto). Suite de lectura **193 passed / 2 skipped**.

## 6. Limitacions conegudes
- Les regles semàntiques codificades són les del Pas 3/3b tal com estan escrites avui; una regla nova al skill demana codi.
- El comparador d'or compara cadenes: els ERR/ALERTA de format (§1) demanen els normalitzadors del comparador (tasca següent) o
  revisar els 2 fixtures (`sondeig cota` de Castellar, `de_a_estat`).
- `superficie_parcela` cadastral (RC → WFS) continua sent derivació Python fora d'aquest mòdul (forat 1 parcialment tancat:
  carpeta + COORDENADES sí; Cadastre/ICGC no).
- Jocs de perdoc antics (v1.2/v1.3) amb dialectes variats es consoliden (Bell-lloc: contracte net) però amb més `candidats`.
