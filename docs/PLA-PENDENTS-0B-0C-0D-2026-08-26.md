# PLA — Pendents 0b (Cadastre), 0c (residus Groq), 0d (`soil_levels`) i forat de `value_key`

**Escrit:** 2026-08-26 (nit), sessió d'anàlisi amb el Josep. **Per a:** la sessió d'implementació (Sonnet).
**Branca:** `experiment/nivell-a-2026-08`, in-place a `g3dt-prod/`, `HEAD 7fcaa01`. **Decisió del Josep:** aquest pla
substitueix la Fase 17 com a següent feina *després* de la Fase 16; per a Bell-lloc (§8) es fa la **via mínima de la
llegenda del tall**.

Tot el que hi ha aquí està **mesurat avui** (API del Cadastre en viu, punts d'assaig amb shapely, or de taules, flux del
`lab_company` fins al `.docx`, `value_key` reproduït). No hi ha res "de memòria"; on la mesura no arriba, ho diu.

---

## 0. Resum executiu (què hem descobert i què canvia)

| Pendent | Diagnòstic mesurat | Què es fa |
|---|---|---|
| **0b Cadastre** | No falla. Per a «Carrer Arbrells 18A» torna la parcel·la correcta (3298012, 441 m²). L'Eva escriu **1.284 = 441 + 423 + 420** = les tres parcel·les dels **tres portals que els documents anomenen** («18A, 18B i 20», or de lectura). Els 5 punts d'assaig cauen exactament dins d'aquestes tres. Amb l'adreça de la lectura, el Cadastre coincideix amb l'Eva a **6 dels 7 projectes resolubles** (annex A). El «4/8 parcel·la equivocada» del diagnòstic era el *matcher* de la via B acceptant un altre portal (Tulipa 3→11): un bug diferent. | Lector **multi-portal** de la via A (`automation/lectura/cadastre_reader.py`): portals de l'adreça llegida → RC per portal (lletra exacta) → WFS → suma si contigus → `candidats`, mai `segur`. Commutador es queda OFF fins a mesurar; recomanació d'encendre'l (§7.9). |
| **0c Groq** | `lab_company='Lab. Valdemoro'` = cel·la B50 de `PLAN_COST_CATELLAR DEL VALLÈS.xlsx`; **no arriba a l'informe** (no és camp del wizard, no es persisteix, el generador cau a TPS; verificat al `.docx` de l'E2E). `superficie_parcela_m2=32980` = **número de bloc cadastral** imprès a `ANNEXES/ALTRES/m8.png`, llegit com a m² per una probe `document_type: map` (conf 0,8). | Treure `lab_company` de Groq (el lab es resol per NIF); cap probe sobre `map`/`site_photo` pot emetre `superficie_*`. **No** fer que `no_trobat` esborri la via B (§6.3). |
| **0d Castellar CAUTELA `[1].a`** | L'or de taules diu literalment `"≥ -1,20 (fins al final del reconeixement; el tall el dibuixa fins a la base)"`: l'autor de l'or hedgeja *igual* que la regla del Pas 3b, però una cadena plana del dialecte antic s'adapta com a `segur`. **Regla i or coincideixen; el comparador no ho sap.** | Reescriure la cel·la de l'or en dialecte v2 com a `candidats`. La pregunta 8 a l'Eva segueix oberta només per a l'*etiqueta* (transició vs final), no per al valor. |
| **0d Bell-lloc ALERTA `[1].de`** | L'annex de sondeig (que dibuixa l'Eva) diu a la **taula** «NIVELL 1: 0,00–1,80»; el −0,30 de l'or surt de **mesurar píxels** d'una línia discontínua (124 px/m) i de la banda del tall (−0,4; ni coincideixen). L'or ha pres posició sobre la pregunta 3. | Via mínima: el skill emet la fila de cobertura quan la **llegenda del tall** la llista («Sòls vegetals»), sense fondàries; el consolidador deixa el `de` del nivell 1 en `candidats` quan hi ha cobertura sense fondàries. Passa d'ALERTA a CAUTELA sense inventar −0,30. |
| **Forat `value_key`** | Reproduït: `value_key("1.5-1.75")` → `("date", 2075, 1, 5)` (amb punts; amb comes va bé). A més, `"0,50-1,20"` → `(0.5, -1.2)` però `"0,50 - 1,20"` → `(0.5, 1.2)`: el mateix interval no clusteritza segons els espais. | `_parse_date` anclat (`fullmatch`) + guió entre dígits = separador d'interval. |
| **Comparador** (descobert en el camí) | `verdict()` dona **OK** a `candidats` vs `candidats` encara que cap valor coincideixi, i **ALERTA** a qualsevol `no_trobat` contra un or que tingui alguna cosa (tant si prod és un blanc honest com un candidat correcte de fora de la carpeta). | Tres verdictes nous: `BUIT`, `CAUTELA candidats disjunts`, `FORA`. Sense això, D i E no es poden mesurar. |

---

## 1. Marc fixat (no re-litigar) i regles de treball

- **Via B prohibit editar-la**: `automation/ai_pipeline/`, `web/vision_groq.py`, `automation/auto_extractor.py`, `web/vision_fast.py`,
  i també `automation/geocode_coordinates.py`, `automation/parcel_resolver.py`, `automation/cadastre_adjacents.py` (es poden
  **importar**, no modificar). Els tres residus Groq **es mantenen** (decisió del Josep 2026-08-26); només es filtren valors.
- **Mai** proposar pull/merge/desplegament a l'Eva.
- **Mesurar abans de codificar** (memòria `feedback_measure_baseline_before_coding`): abans de cada fix, harness i tests
  sobre el codi sense tocar; després, el diff de verdictes (`diff <(grep -vE '^===== ' A) <(grep -vE '^===== ' B)`).
- **Instruments**: lectura = `docs/wizard-headless/fase12-consolida/harness.py` (5 jocs, 0 crides LLM, 0,03 s);
  informe = `scripts/compare_tables_vs_eva.py`. No barrejar-los.
- **Línia base coneguda** (`HEAD 7fcaa01`, mesurada avui): `sonnet-v2-c3` → `ESCALARS {NOU 1, OK 14, CAUTELA 7}`,
  `TAULES {OK 25, CAUTELA 4}`, **0 ALERTA**. Les 4 CAUTELA de taules: `soil_levels[0].a`, `[0].de`, `[1].a`, `spt_ma_tests[0].n30`.
  Suite: `1569 passed / 32 failed` (els 32 coneguts: SmartScan, ai_pipeline, fileminer Anciles). Els altres 4 jocs: **apunta'ls tu**
  al primer pas (§10).
- **Cap crida LLM sense preguntar al Josep** (només §8.4 en necessita una, d'un sol document). El comparador d'or i els tests
  no en fan cap.
- Un commit per fix (§2), missatge `fix(g3dt):` / `feat(g3dt):` / `docs(g3dt):` / `test(g3dt):`. Mai `git stash` (pila compartida
  entre worktrees): WIP commit si cal apartar feina. `rtk` reescriu `grep`/`find`: `find … -not` i patrons amb `\|` fallen →
  `rtk proxy find …`. `unzip` no existeix: `.docx` amb `python-docx`/`zipfile`.
- No editar `docs/golden-read*` ni `_eva_truth/` **per fer quadrar mesures**. Els dos únics canvis a l'or d'aquest pla (§5 i §7.8)
  són canvis de *dialecte* / *anotació de font externa*, argumentats cadascun, i cap no canvia el valor que l'or afirma.

---

## 2. Ordre de treball i commits

L'ordre importa: el comparador (F) va primer perquè D i E es mesuren amb ell; A i B són trivials i tanquen soroll; C és
independent; D i E són els grossos.

| # | Fix | Fitxers principals | Commit | Temps estimat |
|---|---|---|---|---|
| 1 | **F** comparador: `BUIT`, `candidats disjunts`, `FORA` | `docs/wizard-headless/fase0-acceptacio/compare_consolida.py`, `fase12-consolida/harness.py`, `tests/test_compare_consolida.py` | `test(g3dt): comparador d'or — verdictes BUIT / candidats disjunts / FORA` | 1-1,5 h |
| 2 | **A** `value_key` | `automation/lectura/consolidate.py`, `tests/test_lectura_consolidate.py` | `fix(g3dt): value_key — data només si tota la cadena ho és; guió entre dígits = interval` | 30 min |
| 3 | **B** or Castellar `[1].a` | `docs/golden-read-taules/3001621 CASTELLAR DEL VALLES/_tables_decisions.json`, `docs/golden-read-taules/_RESULTATS.md` | `docs(g3dt): or de taules Castellar — base de l'últim nivell en dialecte v2 (candidats)` | 20 min |
| 4 | **C** residus Groq | `automation/fileminer/miners/groq_miner.py`, `automation/concept_scout/vision_probe.py`, `automation/concept_scout/__init__.py`, tests | `fix(g3dt): Groq no extreu lab_company; cap probe de mapa/foto emet superfícies` | 45 min |
| 5 | **D** lector Cadastre multi-portal (via A) | `automation/lectura/cadastre_reader.py` (nou), `consolidate.py`, `tests/test_lectura_cadastre_reader.py` (nou), or de Castellar (`fora_carpeta`) | `feat(g3dt): lectura — Cadastre per portal de l'adreça llegida (suma de parcel·les contigües, candidats)` | 3-4 h |
| 6 | **E** Bell-lloc via mínima | `.claude/commands/g3dt-llegir-projecte.md` (v1.6), `consolidate.py`, tests, 1 re-lectura del tall | `feat(g3dt): capa de cobertura des de la llegenda del tall; nivell 1 arrenca a candidats si la cobertura no té fondàries` | 2 h + 1 crida LLM |
| 7 | **Docs** | DECISION-LOG, STATUS, PREGUNTES-EVA, `_RESULTATS.md` ×3, session log, handoff | `docs(g3dt): pendents 0b/0c/0d tancats — resultats, STATUS, preguntes` | 1 h |

---

## 3. Fix F — Comparador d'or: tres verdictes nous

**Per què primer.** `verdict()` (`compare_consolida.py:330-348`) té dos forats que impedeixen mesurar D i E:
1. `ge == pe == "candidats"` → `OK` sense mirar valors (Bell-lloc `[1].de`: or `[-0,30 / -0,4]`, prod `[0,00]` sortiria OK).
2. Qualsevol combinació no prevista cau a `ALERTA`: or `segur/candidats` + prod `no_trobat` (un **blanc honest**, tolerat pel
   projecte: "mai fals confiat" és la barra dura, "mai en blanc" la tova), i or `no_trobat` + prod `candidats` (el cas del
   Cadastre: un candidat **correcte** que ve de fora de la carpeta compta igual que un d'equivocat).

**Matriu nova** (`close()` és la funció existent; "solapen" = algun candidat de l'or és `close` a algun candidat de prod):

| or \ prod | `segur` | `candidats` | `no_trobat` |
|---|---|---|---|
| `segur` | OK si `close`, si no ERR *(igual)* | CAUTELA «bo dins» / ALERTA *(igual)* | **`BUIT`** (nou, rang 1) |
| `candidats` | ALERTA «prod puja a segur» *(igual)* | OK si solapen; **`CAUTELA candidats disjunts`** si no (nou) | **`BUIT`** (nou, rang 1) |
| `no_trobat` | ALERTA *(igual)* | **`FORA`** (nou, rang 0) si l'or porta `fora_carpeta` i `prod.candidates[0]` hi és `close`; CAUTELA «fora, no coincideix» si porta `fora_carpeta` i no coincideix; **ALERTA** si l'or no porta `fora_carpeta` *(igual que ara)* | OK *(igual)* |

**Implementació.**
- `verdict()`: afegir les branques; `FORA` llegeix `gold.get("fora_carpeta", {}).get("value")`. Missatges curts i estables (el
  harness fa `diff` de text): `BUIT     k  (or=segur 'x'; prod no_trobat)`, `CAUTELA  k  candidats disjunts: or=[…] prod=[…]`,
  `FORA     k  fora de la carpeta: 1284 (Cadastre)`.
- `harness.py`: `RANK` → afegir `"BUIT": 1, "FORA": 0`; `_LINE` regex → afegir els dos literals.
- **`fora_carpeta`** és una clau *opcional* d'una cel·la de l'or d'escalars (`docs/golden-read/*/_decisions.json`), forma
  `{"value": "...", "font": "...", "note": "..."}`. Comprova que `automation/lectura/contract.py::validate_decisions` **no**
  rebutja claus extra dins d'una cel·la (avui `rule`, `note`, `sources_checked` ja hi conviuen); si les rebutgés, afegeix-la a
  la llista de claus tolerades. `test_golden_scalar_fixture_adapts_clean` i `test_golden_fixtures_are_not_mutated_by_adapt_legacy`
  han de seguir verds. A §7.8 s'omple per a Castellar.
- Tests (`tests/test_compare_consolida.py`, al costat de `test_close`): un `@pytest.mark.parametrize` amb les 9 cel·les de la
  matriu (or, prod, verdicte esperat) + `fora_carpeta` present/absent/no coincident.

**Acceptació.** Harness abans/després als 5 jocs: cap línia `OK` es converteix en `ALERTA`; les úniques diferències són (a)
línies `ALERTA … estat or=X prod=no_trobat` que passen a `BUIT`, (b) parells `candidats`/`candidats` sense solapament que
passen d'invisibles a `CAUTELA candidats disjunts`. **Apunta la taula abans/després per joc** a
`docs/wizard-headless/fase12-consolida/_RESULTATS.md` (secció nova «Comparador v3»): és la nova línia base de D i E.

---

## 4. Fix A — `value_key`: dates anclades i intervals

**Fitxer:** `automation/lectura/consolidate.py`, `_parse_date` (L.167-187), `_numbers` (L.189-190).

**Reproducció (avui):**
```
'1.5-1.75'    -> ('date', 2075, 1, 5)        # MAL: _DATE_DMY_RE.search troba "5-1.75"
'1,5-1,75'    -> ('num', (1.5, -1.75))       # MAL: el guió es llegeix com a signe
'0,50-1,20'   -> ('num', (0.5, -1.2))        # MAL (idem)
'1,20 - 1,75' -> ('num', (1.2, 1.75))        # bé → per tant el mateix interval NO clusteritza segons els espais
'-1,20'       -> ('num', (-1.2,))            # bé, s'ha de conservar
'2025-01-05'  -> ('date', 2025, 1, 5)        # bé, s'ha de conservar
```

**Canvi 1 — data només si TOTA la cadena és data.** A `_parse_date`, sobre `t = _strip_parens(s).strip()`:
`_DATE_ISO_RE.fullmatch(t)`, `_DATE_DMY_RE.fullmatch(t)`, i per al patró de mes (`_DATE_MONTH_RE`) `fullmatch` sobre
`_ascii(t).lower()` amb el patró ampliat a `^(?:\d{1,2}\s+(?:de\s+)?)?([a-zç]+)\s+(?:de\s+)?(\d{4})$` (accepta «maig 2025»,
«maig de 2025», «7 de maig de 2025»; captura el dia si hi és). Mantén la guarda `len(_NUM_RE.findall(t)) <= 3`. És la mateixa
regla que el comparador v2 ja aplica («data només si TOTA la cadena és una data», DECISION-LOG 2026-08-25 nit 2).

**Canvi 2 — guió entre dígits = separador d'interval.** A `_numbers`: abans de `_NUM_RE.findall`, `re.sub(r"(?<=\d)\s*-\s*(?=\d)", " ", text)`.
Efecte: `"1,5-1,75"` → `(1.5, 1.75)`; `"0,50-1,20"` i `"0,50 - 1,20"` → la mateixa clau; `"-1,20"` intacte (el guió no va precedit
de dígit); `"-1,00 a -1,20"` intacte (precedit d'espai). Les cel·les `_ABS_CELLS`/`_ABS_FIELDS` no canvien (ja feien `abs`).

**Tests** (`tests/test_lectura_consolidate.py`, al costat de `test_segur_date_is_canonical_iso_but_quote_keeps_original`, L.212):
`@pytest.mark.parametrize` amb els 6 casos de dalt + `"1.5-1.75" → ('num',(1.5,1.75))`, `"Febrer 2026" → ('date',2026,2,None)`,
`"7 de maig de 2025" → ('date',2025,5,7)`, `"1.20 m (aprox.)" → ('num',(1.2,))`, i un test de `keys_compatible(value_key("0,50-1,20"), value_key("0,50 - 1,20")) is True`.

**Acceptació.** Harness: **0 verdictes canvien** als 5 jocs (cap cas real als jocs, per això era "latent"). Si algun canvia,
atura't i mira quin valor l'ha provocat abans de seguir.

---

## 5. Fix B — Or de Castellar: la base de l'últim nivell en dialecte v2

**Fitxer:** `docs/golden-read-taules/3001621 CASTELLAR DEL VALLES/_tables_decisions.json`, `tables.soil_levels[1]`
(fila «Nivell 1 (1er i únic nivell)»). Avui:
```json
"de": "-0,50",
"a": "≥ -1,20 (fins al final del reconeixement; el tall el dibuixa fins a la base)",
"de_a_estat": {"estat": "segur", "candidats": [...], "rule": "3b: transicions = annex sondeig + tall; ..."}
```
`adapt_legacy` → `wrap_flat_cells` (`automation/lectura/normalize.py:125`) embolcalla la cadena plana amb `estat = estat_bloc`
de la fila (`segur`), i el comparador compara `≥ -1,20 (…)` net d'anotacions amb `-1,20` → «bo dins» → CAUTELA. **El valor és
correcte; l'estat és un artefacte del dialecte.**

**Canvi:** substituir només la cel·la `a` per un dict v2 (deixa `de` i `de_a_estat` com són — `de` segueix `segur` a −0,50,
que és la pregunta 3, no aquesta):
```json
"a": {
  "estat": "candidats",
  "value": "-1,20",
  "candidates": [
    {"value": "-1,20", "font": "PDF/ANNEXES/3001621_sondeig.pdf p.1 + PENETROS + SONDEIG.pdf p.5",
     "quote": "0.50-1.20 / 0,50-1,20 Roca fracturada",
     "note": "final del reconeixement (S-1 s'atura a -1,20), no una transició llegida; el tall el dibuixa fins a la base"}
  ],
  "rule": "Pas 3b: la base de l'últim nivell és el final del reconeixement (≥ -1,20), no una transició → candidats (pregunta 8 a l'Eva per a l'etiqueta)"
}
```
Comprova que `wrap_flat_cells` tolera files **mixtes** (una cel·la dict amb `estat` + cel·les planes): pel codi (L.150-151
`if isinstance(val, dict) and "estat" in val: continue`) sí. Els tests `test_golden_table_fixture_adapts_clean` i
`test_golden_fixtures_are_not_mutated_by_adapt_legacy` han de seguir verds.

**Acceptació.** Harness: als 4 jocs de Castellar, la línia `CAUTELA soil_levels[1].a` desapareix (or `candidats` + prod
`candidats` que solapen → OK). `sonnet-v2-c3` → `TAULES {OK 26, CAUTELA 3}`. Cap ALERTA nova (cap joc té `[1].a` en `segur`
perquè la regla de L.1291-1295 sempre el baixa). Apunta-ho a `docs/golden-read-taules/_RESULTATS.md` (una línia datada).

---

## 6. Fix C — Residus Groq: filtrar a l'origen

### 6.1 `lab_company` fora de Groq
- `automation/fileminer/miners/groq_miner.py:102` (`TARGET_VARIABLES`): **treure** l'entrada `"lab_company"`. El laboratori es
  resol determinísticament pel NIF del peu del GTL (`automation/internal_addresses.py::resolve_lab_company`, `LAB_REGISTRY`,
  memòria `gtl_lab_identity`); `lab_extractor.py:383` ja escriu `lab_testing_company`/`lab_field_company`. Groq només hi pot
  aportar soroll (una línia de cost «Lab. Valdemoro»).
- A `_parse_extractions` (L.478-512) afegir la guarda `if variable not in TARGET_VARIABLES: continue` (amb `logger.info
  "Groq: EXCLUDED unknown variable …"`), perquè el model no pugui tornar variables que no s'han demanat.
- Tests (`tests/test_groq_miner.py`, classe `TestPromptConstruction` / la de parsing): `"lab_company" not in TARGET_VARIABLES`;
  una resposta amb `{"variable": "lab_company", "value": "Lab. Valdemoro"}` no produeix cap `Signal`. El test existent de la L.119
  (`assert "lab_company" not in prompt`) continua verd.
- Evidència que és inofensiu avui (no cal tocar res més): `review.html::collectWizardFields()` no l'inclou; `save_wizard_data`
  no el persisteix; `report_generator.py:858/861` llegeix `report_data.lab_company` de `user_data.json` i cau a `'TPS PROSPECCIÓ
  DEL SUBSÒL SL'`; el `3001621_generated.docx` de `~/g3dt-e2e` diu TPS. `web/api.py:1558/1653` només el llista en un endpoint
  de diagnòstic.

### 6.2 Cap probe de mapa/foto emet superfícies
- Origen del 32980: `reference-material/3001621 CASTELLAR DEL VALLES/validation/concept_probes/988aa416db17.json`
  (`document_type: "map"`, `concepts_found: [{"concept_id": "superficie_parcela_m2", "confidence": 0.8, "signal_preview": "32980"}]`)
  sobre `ANNEXES/ALTRES/m8.png`: un mapa cadastral amb la zona d'estudi dibuixada per l'Eva i el número de **bloc** `32980`
  (els RC de les parcel·les són `32980xx DG2039N`) imprès en lila. Un mapa mostra identificadors, no àrees.
- **Dos punts de tall, tots dos:**
  1. `automation/concept_scout/vision_probe.py::_parse_probe_result` (L.338-376): després de `doc_type`, saltar `cid in
     {"superficie_parcela", "superficie_construida"}` (i els seus àlies `_m2`, vegeu nota) quan `doc_type in {"map", "site_photo"}`,
     amb `logger.debug`.
  2. `automation/concept_scout/__init__.py` (bucle L.~100-145 que converteix `vision_probe:*` en `Signal`, on ja es descarten
     adreces de fonts manuscrites): mateixa guarda per `concept_id`/`doc_type` — així també cobreix probes **ja cachejades**
     a `validation/concept_probes/` de projectes existents (Castellar en té una amb el 32980).
  3. Prompt (`_PROBE_PROMPT`, bloc «MAP-SUBJECT SCOPING»): afegir «Numbers printed on cadastral/topographic maps are parcel or
     block identifiers, never areas: never return superficie_parcela or superficie_construida from a map.»
- **Nota d'investigació obligatòria:** la probe cachejada porta `superficie_parcela_m2` (amb `_m2`) però
  `_VISION_DETECTABLE_CONCEPTS` (vision_probe.py:27) diu `superficie_parcela`. Abans de tocar res, traça amb `grep -rn
  "superficie_parcela_m2"` per on aquest id passa el filtre de `_parse_probe_result` (registre de conceptes? normalització a
  `aggregator.py`?) i posa la guarda **allà on el concepte realment entra**; si no ho trobes, la guarda del punt 2 (sobre el
  `concept_id` amb i sense sufix `_m2`) és la xarxa de seguretat. Documenta-ho al DECISION-LOG.
- Tests (`tests/test_vision_probe_gate_and_prompt.py`): `test_parse_probe_result_drops_areas_on_maps` (map + superficie →
  fora; `architect_plan` + superficie → dins), `test_probe_prompt_forbids_areas_from_maps`, i un test del punt 2 amb un
  `ConceptSource(extraction_method="vision_probe:map", signal_preview="32980")` que no genera senyal.

### 6.3 Què NO fer (i per què)
- **No** implementar «un `no_trobat` de la lectura esborra el valor de la via B» (via (a) de STATUS 0c). Trenca la regla 4 del
  contracte (`_apply_lectura_overlay`, `web/lectura_service.py:170`), i converteix un forat de lectura (una pàgina no mostrejada)
  en un blanc a l'informe. La variant que sí té sentit, i que queda apuntada per a quan es toqui la UI: `no_trobat` + valor de la
  via B → `source: "via_b_no_confirmat"` (badge àmbar), mai blau. No és d'aquest pla (`review.html` fa 10.000 línies i no té tests).
- **No** desactivar probes, `groq_miner` ni ortofoto (decisió presa).
- Amb D (§7), `superficie_parcela` a Castellar passa a tenir un candidat correcte (1.284) i l'overlay escriu `candidates[0]`:
  el 32980 queda tapat també per precedència. §6.2 és igualment necessari (projectes sense adreça resoluble).

---

## 7. Fix D — Lector Cadastre multi-portal de la via A

### 7.1 Evidència (mesurada 2026-08-26, annex A per al detall)
- Castellar: portals `18(A)`=3298012 (441), `18(B)`=3298013 (423), `20`=3298014 (420) → **1.284 = l'informe signat**.
  P-1/P-2 dins 14, S-1 dins 13, P-3/P-4 dins 12; la geocodificació de «18A» dins 12.
- La fila de l'informe es diu literalment «**Superfície de la parcel·la segons plànols cadastrals** (m2)»
  (`templates/g3dt-jinja-template.docx`, taula 0): el Cadastre és *la* font semàntica d'aquesta cel·la.
- Amb l'adreça **de la lectura** (no la de la via B): Alcoletge 1167 = Eva 1167; Tulipa 3 → 564 = Eva 564 (el 759 del
  diagnòstic era el matcher acceptant el portal 11); Linyola 571 = 571; Anciles 1656 ≈ 1.655,01; Bell-lloc 518+494 = 1.012
  (els documents diuen 995 → la porta queda tancada, correcte); Vilanova 406 = la cel·la *construïda* de l'informe (l'Eva hi
  té 100/406, probablement intercanviades → pregunta 9, §9). Rubí («Carrer de la Miranda, 39»): `callejero_address_to_rc`
  no resol → cap senyal (blanc honest).
- **Trampa de les lletres:** `callejero_address_to_rc("Carrer Arbrells, 18B", …)` torna **3298012 (18A)** perquè
  `_pick_nearest_rc_from_numerero` (geocode_coordinates.py:967) treu la lletra i tria el número més proper. El lector nou
  **no pot** delegar-hi el portal: ha de filtrar per `(pnp, plp)` exactes al `numerero`.

### 7.2 Mòdul nou: `automation/lectura/cadastre_reader.py`
Només importa de la via B (`geocode_coordinates._consulta_municipio`, `_consulta_via`, `_parse_address`, `_CATALAN_PROVINCES`;
`cadastre_adjacents.get_parcel_geometry_utm` si fa falta el polígon) i de `automation.config.cache_dir`. Sense LLM.

```
portals_from_address(address: str) -> tuple[str, list[tuple[str, str]]]
    # "Carrer Arbrells, 18A, 18B i 20" -> ("Arbrells", [("18","A"),("18","B"),("20","")])
    # "C/ Mestre Ramon Ortiz 15"       -> ("Mestre Ramon Ortiz", [("15","")])
    # "Carrer Girasols, 7 (Urb. El Roser)" -> ("Girasols", [("7","")])   # parèntesis fora abans de res
    # "18-20"                            -> [("18",""),("20","")] + nota "rang"
    # "entre el carrer X i el carrer Y" / "s/n" / "Polígon X, Nau 5" -> ([], ...)  # cap número de portal
    # ignora números dins de parèntesis i després de nau|km|pk|bloc|esc|pis|porta|cp|\d{5}
resolve_portal(province, municipality_official, via_official, number, letter) -> list[ParcelHit]
    # JSON: https://ovc.catastro.meh.es/OVCServWeb/OVCWcfCallejero/COVCCallejero.svc/json/Consulta_DNPLOC
    #   ?Provincia=..&Municipio=..&Sigla=CL&Calle={via_official}&Numero={number}
    # resposta: consulta_dnplocResult.lrcdnp.rcdnp[] -> rc.pc1+rc.pc2 (14 chars), dt.locs.lous.lourb.dir.{nv,pnp,plp}
    # filtra pnp == number i (plp == letter, o letter=="" i plp=="")
    # si letter=="" i només hi ha entrades amb lletra -> AMBIGU: retorna-les totes marcades ambiguous=True (no se sumen)
    # ATENCIÓ: `debi.sfc` és superfície CONSTRUÏDA (0 a solars), NO la parcel·la
parcel_area_and_polygon(rc14) -> (area_m2: int, polygon: list[tuple[float,float]])
    # WFS: https://ovc.catastro.meh.es/INSPIRE/wfsCP.aspx?service=wfs&version=2.0.0&request=GetFeature
    #   &STOREDQUERIE_ID=GetParcel&refcat={rc14}&srsname=EPSG::25831
    # area = <cp:areaValue uom="m2"> OFICIAL (enter): 441+423+420 = 1284 exacte; l'àrea shapely dona 440,76… i arrodoneix malament
cadastre_portal_signals(key, decided, project_path) -> list[Signal]
```
`cadastre_portal_signals`:
1. Llegeix `decided["street_address"]` i `decided["municipality"]`: agafa `value` si `estat in (segur, candidats)`; si `no_trobat`
   → `[]`. Si `street_address` té diversos candidats amb portals diferents, fes servir **només `candidates[0]`** (l'overlay
   escriu el primer) i anota-ho.
2. Província: prova `_CATALAN_PROVINCES` + `"HUESCA"` amb `_consulta_municipio` (com fa `callejero_address_to_rc`); municipi i via
   oficials via `_consulta_via`. Si la via no es resol → `[]` (Rubí).
3. Per cada portal → `resolve_portal`; per cada RC → `parcel_area_and_polygon`. Màxim **6 portals** i **10 s** per crida
   (`_fetch_url` de la via B ja té timeout; si no, `urllib` propi).
4. Contigüitat: `shapely.ops.unary_union` dels polígons ha de ser **un sol `Polygon`**; si no (o si algun portal és ambigu),
   **no sumis**: emet un candidat per parcel·la (valor = àrea individual, nota «parcel·les no contigües / portal ambigu»).
5. Punts d'assaig (`consolidate.parse_coordenades` sobre `COORDENADES*.txt` del projecte, si n'hi ha): compta quants cauen dins
   la unió → nota «5/5 punts d'assaig dins de la unió» / «1/1 fora (a 113 m)». **Informatiu, no bloqueja.**
6. Senyals (mateix motlle que `http_field_signals`, consolidate.py:892-913: `origin="python"`, `is_a=False`, conf `_HTTP_CONF`
   = 0,5 → mai `segur`; `doc=_HTTP_DOC`, `doc_type="consulta_http"`):
   - `superficie_parcela`: `value = str(suma)` (p. ex. `"1284"`), `font = "(Cadastre: 18A+18B+20 = 3298012+3298013+3298014 DG2039N, 441+423+420 m²)"`,
     `note` = _HTTP_NOTES nova (§7.5) + contigüitat + punts.
   - `referencia_catastral`: **un sol senyal** amb els RC units per `" + "` (amb un portal, un RC). Avui cap consumidor
     (wizard/report) el fa servir (`MAPPING_DECISIONS_WIZARD["referencia_catastral"] = None`); la guarda `parcela` de
     `_guard_for_field` (L.767-772) llegeix `decided["referencia_catastral"]`: amb un sol valor no dispara, i no cal.
7. Qualsevol excepció (xarxa, parse) → `logger.warning` + `[]`. **La consolidació mai no pot fallar per aquest lector.**

### 7.3 Cache
`config.cache_dir("cadastre_portals")` (respecta `G3DT_CACHE_DIR`), un JSON per clau `sha256(prov|muni|via|num|lletra)[:16]`
i un per RC (WFS), `cached_at` + TTL 90 dies (mateix patró que `geocode_coordinates.py:47-49`). Sense xarxa i sense cache →
`[]`. No cal registre per projecte: la consolidació és determinista sobre (adreça llegida, resposta del Cadastre) i les dues
coses tenen empremta pròpia.

### 7.4 Cablejat a `consolidate_python` (consolidate.py:1580-1633)
- `order`: avui alfabètic després de `client_name`/`num_floors`, i `referencia_catastral` < `street_address` < `superficie_parcela`.
  Mou **`referencia_catastral` i `superficie_parcela` al final** de `order` (en aquest ordre: la guarda `parcela` llegeix el RC).
- A la porta dels forats (L.1611-1616), per a aquestes dues claus i només si `"cadastre" in _http_enabled_sources()`:
  `sigs += cadastre_portal_signals(key, fields, project_path)` **abans** de `http_field_signals`.
- `_HTTP_FIELD_SOURCES` (L.833-840): **treure** les dues entrades `cadastre` (llegien `_auto_result.json` = adreça de la via B,
  que és la que el diagnòstic va trobar equivocada a Tulipa/Rubí/Vilanova). ICGC i geocodificació es queden com estan.
- `_http_enabled_sources()` i `G3DT_LECTURA_HTTP_SOURCES`: mateixa semàntica; l'etiqueta `cadastre` ara vol dir el lector nou.

### 7.5 Textos i comentaris a actualitzar (el codi conté afirmacions que ara són falses)
- Bloc de comentari `consolidate.py:853-890` («El Cadastre, en canvi, s'ha mesurat i EMPITJORA…»): reescriure amb la troballa
  d'avui (la parcel·la era correcta; l'Eva suma els portals; 6/7 coincideixen amb l'adreça llegida; lletres).
- `_HTTP_NOTES["cadastre"]`: «suma de les parcel·les cadastrals dels portals de l'adreça llegida (consulta HTTP, no lectura
  d'un document de la carpeta); la fila de l'informe diu "segons plànols cadastrals"; confirmar si el projecte abasta més
  o menys portals dels que diu l'adreça».
- `docs/wizard-headless/fase13-http-cache/_RESULTATS.md` §«Cadastre» (L.65-80): addendum datat que corregeix la lectura
  («no era la parcel·la equivocada: era un portal de tres»).

### 7.6 Tests: `tests/test_lectura_cadastre_reader.py` (nou) — tot amb `monkeypatch`, 0 xarxa
- `portals_from_address`: els 8 exemples de §7.2 (parametritzat).
- `resolve_portal`: fixture JSON real de Castellar (annex B) → `18/A` → 3298012, `18/B` → 3298013, `18/""` → 2 hits `ambiguous`.
- `cadastre_portal_signals` amb `_dnploc`/`_wfs` falsejats: (a) 3 portals contigus → 1 senyal `superficie_parcela` = `"1284"` +
  1 senyal RC amb 3 refs, nota amb «3/3 parcel·les contigües»; (b) 2 portals no contigus → 2 candidats individuals, cap suma;
  (c) portal amb lletra inexistent → `[]`; (d) `street_address` `no_trobat` → `[]` sense cap crida; (e) excepció de xarxa →
  `[]` i `warning`; (f) `COORDENADES.txt` amb 5 punts dins → nota «5/5»; 1 punt fora → nota «0/1».
- A `tests/test_lectura_consolidate.py` (al costat de `test_cadastre_is_off_by_default`, L.597): (g) amb el commutador ON i un
  document que ja diu `superficie_parcela` (Bell-lloc 995) el lector **no es crida** (porta tancada); (h) OFF per defecte → no es
  crida; (i) `order` acaba amb `referencia_catastral, superficie_parcela`.

### 7.7 Mesura (harness) — dues passades obligatòries
1. `G3DT_LECTURA_HTTP_SOURCES` **sense definir** (defecte `icgc,geocodificacio`): els 5 jocs **idèntics** a la línia base post-F.
2. `G3DT_LECTURA_HTTP_SOURCES=icgc,geocodificacio,cadastre` (primera passada amb xarxa; les següents van de cache): Castellar ×4:
   `superficie_parcela` i `referencia_catastral` `no_trobat → candidats` → verdicte **`FORA`** (gràcies a §7.8); Bell-lloc:
   idèntic (porta tancada). **Cap ALERTA.** Apunta les dues taules a `fase12-consolida/_RESULTATS.md`.

### 7.8 L'or de Castellar: anotar la font externa (`fora_carpeta`)
`docs/golden-read/3001621 CASTELLAR DEL VALLES/_decisions.json`, `decisions.superficie_parcela` i `decisions.referencia_catastral`
segueixen `no_trobat` (els documents de la carpeta **no** ho diuen; això no canvia). S'hi afegeix:
```json
"fora_carpeta": {"value": "1284",
  "font": "Cadastre (Callejero DNPLOC + WFS INSPIRE), portals 18A+18B+20 = 3298012+3298013+3298014 DG2039N (441+423+420 m²)",
  "note": "no és lectura de la carpeta; mesurat 2026-08-26; coincideix amb l'informe signat (t0_r1_c1 = 1.284)"}
```
i per al RC `"value": "3298012DG2039N + 3298013DG2039N + 3298014DG2039N"`. És una **anotació**, no un canvi de veredicte de l'or.

### 7.9 Decisió que queda per al Josep (no la prenguis tu)
Encendre `cadastre` per defecte (`_HTTP_SOURCES_DEFAULT`). Recomanació d'aquesta anàlisi: **sí**, després de §7.7 — sempre
`candidats`, mai `segur`; només omple forats; 6/7 coincideixen; Rubí queda en blanc honest. Deixa el commit amb el defecte
**apagat** i la línia per encendre'l al DECISION-LOG.

---

## 8. Fix E — Bell-lloc, via mínima de la llegenda del tall

### 8.1 Què diuen les fonts (mesurat)
- Annex de sondeig de Bell-lloc (`PDF/ANNEXES/4001612_sondeig.pdf`, dibuixat per l'Eva): taula «Unitat litològica» amb **una**
  fila `NIVELL 1 0,00–1,80`. Tall (`tall.pdf`): llegenda amb **«Sòls vegetals»** (banda marró, sense xifra) + «1er nivell: Graves
  amb sorres».
- Lectura actual (`belloc-ws-v12`): cap document emet fila de cobertura → `NIVELL 1.de = 0,00 segur` (1 font A).
- Or de taules: cobertura `de 0,00 segur / a candidats [-0,30 (±0,05) gràfic, -0,4 gràfic]`; nivell 1 `de candidats [idem]`,
  `a candidats [-1,80, -2,45]`. Els −0,30/−0,4 són **píxels mesurats**; el skill, per regla, no mesura píxels.
- A Castellar, quan l'Eva vol la cobertura separada, **l'escriu a la taula** (0,00–0,50 / 0,50–1,20). A Bell-lloc no ho va fer.
  Per això el 0,00 no és un error net: és la pregunta 3.

### 8.2 Skill `.claude/commands/g3dt-llegir-projecte.md` → **v1.6**
- Capçalera de versions (L.11-14): afegir «v1.6 (data): fila de cobertura des de la llegenda del tall / annex de sondeig, sense
  fondàries si no estan impreses».
- Bloc «Nivells del sòl (`soil_levels[]`)» (L.301-310), punt nou després de `nom`:
  > **Capa de cobertura sense número.** Si la llegenda del tall (`annex_tall`) o la «Descripció dels materials» de l'annex de
  > sondeig anomena una capa superficial **sense número de nivell** («Terreny vegetal», «Sòls vegetals», «Reblert», «Relleno»,
  > «Cobertura»), EMET una fila pròpia **abans** del nivell 1: `nom = "<nom de la llegenda> (cobertura, sense número)"`,
  > `litologia` = text de la llegenda, `de` = `"0,00"` només si el document ho imprimeix (si no, `null`), `a` = la xifra impresa
  > si n'hi ha, si no `null`. **No mesuris píxels ni estimis gruixos gràfics.** La cobertura NO compta a `num_soil_levels`
  > (regla existent). Castellar ja ho fa («Terreny Vegetal (sense número a la llegenda)»); Bell-lloc no ho feia.
- `consolidate._COVER_RE` (L.103: `vegetal|cobertura|reblert|relleno|terra vegetal`) ja atrapa «Sòls vegetals»; afegir-hi
  `s[oò]ls? vegetals?` explícit per no dependre de la subcadena.

### 8.3 Consolidador (`consolidate.py`, bloc `soil_levels` de `consolidate_tables`, al costat de la regla de l'últim nivell L.1291-1295)
Després de `rows_out`, si `block == "soil_levels"`:
- **E2b (definicional).** Fila de cobertura (`_COVER_RE` sobre `nom`) amb `de` `no_trobat`: `de` = `{"estat": "segur",
  "value": "0,00", "candidates": [{"value": "0,00", "font": "(definició: la cobertura arrenca a la superfície)", "quote": ""}],
  "rule": "Pas 3b: la capa de cobertura comença a 0,00 per definició"}`. (Or de Bell-lloc: `segur 0,00`; Castellar: ja ho tenia
  del full de camp, la regla no dispara.) Si el Josep prefereix `candidats`, és canviar una paraula.
- **E2 (la que tanca l'ALERTA).** Si hi ha fila de cobertura amb `a` `no_trobat` (cap document li dona la base) **i** la primera
  fila no-cobertura té `de` `segur` amb valor numèric `≤ _SURFACE_TOL` (0,05): `de.estat = "candidats"` (els `candidates` es
  conserven), `de.rule = "Pas 3b: hi ha capa de cobertura (llegenda del tall) sense fondàries llegides i el nivell 1 arrenca a 0,00 → la transició cobertura/nivell 1 no està documentada numèricament: candidats (pregunta 3 a l'Eva)"`,
  `estat_bloc = "candidats"`. A Castellar la cobertura **té** `a` (−0,50 del full de camp) → no dispara → harness intacte.
- Tests (`tests/test_lectura_consolidate.py`, al costat de `_castellar_soil_corpus` L.686): `_belloc_soil_corpus` (tall amb fila
  «Sòls vegetals (cobertura, sense número)» `de/a null` + annex `NIVELL 1 0.00–1.80` + `SONDEIG.pdf` manuscrit `0,00`) →
  cobertura `de segur 0,00`, `a no_trobat`; nivell 1 `de candidats` amb la regla, `a candidats` (regla de l'últim nivell);
  Castellar → cap canvi; corpus sense cobertura → cap canvi; cobertura amb `a` → cap canvi.

### 8.4 Verificació real (1 crida LLM, **preguntar al Josep abans**)
El joc `belloc-ws-v12` llegeix el perdoc de `~/g3dt-e2e/projectes/4001612 BELL-LLOC/validation/lectura/`; el JSON del tall és
de v1.5 (sense la fila). Per veure el flip cal **re-llegir només el tall** amb v1.6:
1. Còpia de seguretat del JSON actual del tall (nom canònic `safe_doc_name`, cf. skill v1.2) a l'scratchpad.
2. Una crida amb la forma del runner (`automation/lectura/runner.py:516`):
   `claude -p "/g3dt-llegir-projecte <proj> --only PDF/ANNEXES/4001612_tall de correlació.pdf --inventory <inv> --out <out>"`
   (model per defecte del runner `sonnet`; `--effort` com el runner el fixa; ~2-4 min).
3. Harness `--only belloc-ws-v12`. Esperat: `soil_levels[0].de` OK; `[0].a` **`BUIT`** (l'or té píxels, nosaltres no: acceptat i
   documentat); `[1].de` **`CAUTELA candidats disjunts`** (or −0,30/−0,4, prod 0,00 — honest, espera la pregunta 3); `[1].a` OK
   (solapen a −1,80). **L'ALERTA desapareix.** Si el skill v1.6 no emet la fila, no toquis el JSON a mà: ajusta el text del skill
   i repeteix (una crida més, preguntant).
4. Deixa el JSON nou al perdoc (és la lectura vigent), apunta el `source_md5` i el temps al DECISION-LOG.

### 8.5 Or de Bell-lloc: **no es toca**
Les cel·les gràfiques (−0,30/−0,4) són lectura humana legítima. Amb F, la diferència queda com a `BUIT` + `CAUTELA disjunts`,
que és exactament la informació que volem conservar fins que l'Eva respongui la pregunta 3.

---

## 9. Documentació (commit 7)

- **DECISION-LOG** (`docs/DECISION-LOG.md`, entrada nova amb el format de 9 seccions): les decisions són (1) comparador v3,
  (2) `value_key` anclat, (3) or Castellar en dialecte v2 (per què és dialecte i no mesura), (4) residus Groq a l'origen i
  per què no «`no_trobat` esborra», (5) lector Cadastre a la via A i no a la via B / per què `candidats` / per què no
  `callejero_address_to_rc` (lletres) / per què `areaValue` i no shapely, (6) via mínima de Bell-lloc i per què no es mesuren
  píxels, (7) què queda per al Josep (encendre Cadastre; E2b segur vs candidats). Validació empírica: taules del harness abans/
  després per a cada fix, comptes de tests (avui 1569/32).
- **STATUS.md**: reescriure 0b/0c/0d (L.257-296) com a «resolts / pendents de decisió» amb una línia cadascun + la capçalera
  `Last updated`. Afegir a «Blockers/decisions» les dues del Josep.
- **`docs/PREGUNTES-EVA-PENDENTS.md`**: pregunta 3 → nota «2026-08-2X: via mínima feta; el `de` del nivell 1 queda `candidats`
  a Bell-lloc fins a la resposta»; pregunta 8 → nota «or corregit a candidats; la pregunta només decideix l'etiqueta»;
  **pregunta 9 nova**: «Vilanova de Segrià: l'informe diu parcel·la 100 m² i construïda 406 m²; el Cadastre diu que la
  parcel·la 8606709CG9280N fa 406 m². Estan intercanviades?». Pregunta 10 nova (Castellar): «La superfície de parcel·la 1.284
  és la suma de les tres parcel·les cadastrals 18A+18B+20 — és el criteri habitual quan l'encàrrec abasta diversos portals?».
- **`_RESULTATS.md`**: fase12 (comparador v3 + taules D/E), fase13 (addendum Cadastre), golden-read-taules (cel·la de Castellar).
- **Session log** del dia (`.claude/sessions/YYYY-MM-DD-session.md`, append-only) i handoff final amb `/for-new-you`.
- **Memòria** (`~/.claude/projects/-home-josep-projects-claudecode-job-clients-g3dt/memory/`): la sessió d'anàlisi ja ha corregit
  `reference_cadastre_not_truth_for_parcel_area` i actualitzat `project_groq_residues_wrong_values_pending` i
  `project_soil_levels_gold_vs_pas3b_open` (vegeu-les abans de començar). Quan acabis, afegeix-hi l'estat final.

---

## 10. Seqüència d'obertura i criteris d'acceptació globals

```bash
git branch --show-current            # experiment/nivell-a-2026-08
git log --oneline -1                 # 7fcaa01 (o posterior de docs)
.venv/bin/python -m pytest tests/ -q -p no:cacheprovider          # 1569 passed / 32 failed (10 min timeout)
.venv/bin/python docs/wizard-headless/fase12-consolida/harness.py --write /tmp/…/base   # APUNTA els 5 jocs
```
Acceptació final (tot alhora):
- Suite: `1569 + nous passed / 32 failed` (els mateixos 32).
- Harness, defecte (Cadastre OFF): **0 ALERTA** als 5 jocs; `sonnet-v2-c3` `TAULES {OK 26, CAUTELA 3}` (B), la resta de canvis
  només `BUIT`/`disjunts` explicables línia a línia.
- Harness, Cadastre ON: Castellar `superficie_parcela`/`referencia_catastral` → `FORA`; Bell-lloc intacte.
- `belloc-ws-v12` després de §8.4: cap ALERTA.
- `grep -rn "4 dels 8\|4/8" automation/lectura/consolidate.py` → 0 (comentaris actualitzats).
- Cap fitxer de la via B modificat: `git diff --stat HEAD~7 -- automation/ai_pipeline web/vision_groq.py automation/auto_extractor.py web/vision_fast.py automation/geocode_coordinates.py automation/parcel_resolver.py automation/cadastre_adjacents.py` buit.

---

## 11. Decisions per al Josep (recollides en un sol lloc)

1. ✅ **DECIDIT (2026-08-31):** encendre `cadastre` per defecte al consolidador després de §7.7.
2. ✅ **DECIDIT (2026-08-31, en implementar Fix E):** `de` de la cobertura = `segur "0,00"` per definició (no `candidats`).
3. ✅ **DECIDIT (2026-08-31):** crida LLM de §8.4 autoritzada; model per defecte del runner (`sonnet`), tal com diu §8.4.
4. Enviar a l'Eva les preguntes 3 + 8 juntes (són la mateixa) i les noves 9 i 10. **Encara pendent** — vegeu
   `docs/PREGUNTES-EVA-PENDENTS.md`.

**Nota (2026-08-31, nit):** pla **implementat i tancat** aquest mateix dia — F/A/B/C/D/E + docs, commits `3694694` a
`2486a53`. Detall complet: `docs/DECISION-LOG.md` entrada 2026-08-31.

---

## Annex A — Cadastre vs Eva als 8 projectes (mesurat 2026-08-26, adreça = or de lectura)

| Projecte | Adreça llegida | RC (portal exacte) | Cadastre m² | Eva | Veredicte |
|---|---|---|---|---|---|
| Castellar | Carrer Arbrells, **18A, 18B i 20** | 3298012 / 3298013 / 3298014 DG2039N | 441 + 423 + 420 = **1.284** | 1.284 | ✅ suma de portals |
| Alcoletge | Carrer Girasols, 7 | 8841701CG0184S | 1.167 | 1.167 | ✅ |
| Tulipa | Carrer Tulipa, 3 | 3445105DF2934E | 564 | 564 | ✅ (diagnòstic: 759 = portal 11, matcher via B) |
| Linyola | Carrer Clot de la Llacuna, 16 | 5098344CG2159N (als documents) | 571 | 571 | ✅ (documents ja ho diuen) |
| Anciles | C/ General Ferraz, 20 | 6184504BH9158N (als documents) | 1.656 | 1.655,01 | ✅ (documents ja ho diuen) |
| Bell-lloc | C/ Mestre Ramon Ortiz 15 | 4613172 + 4613173 CG1141S (fitxes a la carpeta) | 518 + 494 = 1.012 | 995 (plànol) | ✅ porta tancada (documents guanyen); P-1 a 87-113 m de les parcel·les |
| Vilanova | C/ Santa Gemma, 4 | 8606709CG9280N | 406 | **100** (construïda: 406) | ⚠ cel·les de l'informe probablement intercanviades → pregunta 9 |
| Rubí | Carrer de la Miranda, 39 | no resolt pel Callejero | — | 951 | blanc honest |

Punts d'assaig de Castellar (`COORDENADES.txt`): P-1, P-2 → 3298014; S-1 → 3298013; P-3, P-4 → 3298012; geocodificació «18A» → 3298012.

## Annex B — Detalls de l'API (verificats avui)

- **DNPLOC JSON** (`…/COVCCallejero.svc/json/Consulta_DNPLOC?Provincia=BARCELONA&Municipio=CASTELLAR%20DEL%20VALLES&Sigla=CL&Calle=ARBRELLS%20DELS&Numero=18`)
  → `lrcdnp.rcdnp[]` amb `rc.pc1="3298012", rc.pc2="DG2039N"`, `dt.locs.lous.lourb.dir = {nv:"ARBRELLS DELS", pnp:"18", plp:"A"}` i
  `{…, pnp:"18", plp:"B"}` → 3298013. El nom de via ha de ser el **del Cadastre** («ARBRELLS DELS»; «ARBRELLS» sol → error 5,
  «DELS ARBRELLS» → error 33): d'aquí `_consulta_via`.
- **DNPRC JSON** (`…/Consulta_DNPRC?Provincia=…&Municipio=…&RefCat=3298012DG2039N`) → `ldt = "CL ARBRELLS DELS 18(A) Suelo 08211 …"`.
  Útil per a la nota; `sfc` és construïda (0).
- **WFS GetParcel** (URL a §7.2) → `<cp:areaValue uom="m2">441</cp:areaValue>` + `<gml:posList>` EPSG:25831. Retorna
  `ExceptionReport` per a RC inexistents (3298015/16): tractar com a «no parcel·la».
- Fixtures per als tests: desa les respostes JSON/XML reals de Castellar (portals 18A/18B/20, WFS 12/13/14) a
  `tests/fixtures/cadastre_castellar/` (són petites: 2,6 KB per WFS).

## Annex C — Comandes útils

```bash
# harness sencer / un joc, amb sortida escrita per fer diff
.venv/bin/python docs/wizard-headless/fase12-consolida/harness.py --write /tmp/claude-…/scratchpad/A
G3DT_LECTURA_HTTP_SOURCES=icgc,geocodificacio,cadastre .venv/bin/python docs/wizard-headless/fase12-consolida/harness.py --only sonnet-v2-c3 --write …/B
diff <(grep -vE '^===== ' A/sonnet-v2-c3.txt) <(grep -vE '^===== ' B/sonnet-v2-c3.txt)

# comparador d'un sol joc
.venv/bin/python docs/wizard-headless/fase0-acceptacio/compare_consolida.py taules docs/wizard-headless/fase12-consolida/out/sonnet-v2-c3/_decisions.json "3001621 CASTELLAR DEL VALLES"

# reproduir el forat A
.venv/bin/python -c "from automation.lectura.consolidate import value_key as v; print(v('1.5-1.75'), v('0,50-1,20'), v('0,50 - 1,20'))"

# tests per fitxer (ràpid)
.venv/bin/python -m pytest tests/test_lectura_consolidate.py tests/test_compare_consolida.py tests/test_lectura_contract.py -q -p no:cacheprovider
```

*Fi del pla. Tot mesurat el 2026-08-26; res implementat.*
