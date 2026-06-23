# PLA: Correcció de `site_address` + Avaluació Dual (Determinista vs Visió) del Pressupost

Data: 2026-06-23
Branca de treball: `fix/pipeline-routing` (base: `production/g3dt-eva-v1`)
Document germà: `docs/ANALISI-PIPELINE-DEBUG-VACARISSES.md` (§4 — diagnòstic) — vegeu també §4.4 (cas `num_dpsh_tests`, ja corregit).

---

## 0. Decisió central d'aquest pla

Abans d'implementar la millora determinista (regex → parser de la secció OBRA),
**hem de considerar moure aquesta extracció a la part de visió del pipeline.**

**Raonament (Josep, 2026-06-23):**
- El determinista és adequat **quan hi ha un patró**. Al PDF del pressupost tenim
  *quelcom que podem anomenar patró* (la secció OBRA), però amb **molta variabilitat**:
  de vegades falten dades que necessitem, i els humans escriuen les adreces de manera
  caòtica.
- L'extracció de **text** del PDF **destrueix aquest patró** (desordena l'ordre de
  lectura — ho hem comprovat empíricament amb la taula DPSH, §4.4). Per tant, és
  **extremadament difícil** que un script Python determinista (regex) capturi de
  manera **consistent** les dades que necessitem.
- En canvi, un **LLM amb visió** pot recollir aquestes dades de manera ràpida i precisa.

**Estratègia:** provar **les dues vies alhora**, **duplicant** la captura de dades
inicialment (mantenim el procés determinista **i** afegim un de visió LLM). Segons
els resultats i la **fiabilitat** que observem, decidirem quina ens quedem.
És un esquema *champion–challenger*: cap via es retira fins que les dades de comparació
ho justifiquin.

**Evidència empírica que ja tenim a favor de la visió (Vacarisses):**

| Camp OBRA | Regex determinista (`docs_extracted.json`) | Visió (`projecte_extracted.json`, `vision_chunked`) | Cert |
|-----------|---------------------------------------------|------------------------------------------------------|------|
| `street_address` | ❌ `"DE LA MAQUINA DE PENETRACIO,"` | ✅ `"C/DE LA BARCELONETA 23"` | C/DE LA BARCELONETA 23 |
| `municipality` | (no l'extreu aquí) | ✅ `"VACARISSES"` | VACARISSES |
| `client_name` | ❌ (confós) | ✅ `"MARC VIDAL"` | MARC VIDAL |
| `architect_company` | ❌ | ❌ `"G3 DESENVOLUPAMENT..."` (confusió d'entitat) | *(tasca separada)* |
| confiança | — | 0.8 | — |

→ La visió ja encerta **3/4** dels camps OBRA (només falla l'arquitecte, que és el
problema de **confusió d'entitat**, tasca a banda). El regex encerta **0/1** en
`site_address`. Això reforça la hipòtesi: **per a aquest document, la visió és més
fiable que el regex.** Aquest pla ho posa a prova de manera controlada en els 5+ projectes
de referència, no només en Vacarisses.

---

## 1. El problema (`site_address`)

`web/vision_fast.py:390` fa *match* amb el primer `EMPLAÇAMENT|SITUACIÓ|Adreça` del
text del pressupost. Sortides reals als 5 pressupostos que el codi llegeix avui:

| Projecte | `site_address` actual | Hauria de ser |
|----------|------------------------|----------------|
| Vacarisses | `"DE LA MAQUINA DE PENETRACIO,"` (nota del camió ploma) | `C/DE LA BARCELONETA 23, VACARISSES` |
| Castellar | `"CP I POBLACIÓ:"` (etiqueta de formulari) | `C/ARBRELLS 18A, CASTELLAR DEL VALLES` |
| Rubí | `"CP I POBLACIÓ:"` | *(sense carrer al pressupost — només municipi)* |
| Bell-lloc | `"CP I POBLACIÓ:"` | `C/MESTRE RAMON ORTIZ 15, BELL-LLOC` |
| Alcoletge | `"CP I POBLACIÓ:"` | `C/GIRASOLS 7, URB.EL ROSER, ALCOLETGE` |

**5/5 incorrectes.** El mot "EMPLAÇAMENT" apareix en text boilerplate
("emplaçament de la màquina", "emplaçament de l'estructura"), de manera que
ancorar-se en ell és intrínsecament poc fiable.

## 2. Troballa clau: `site_address` SÍ es consumeix (≠ `num_planned_dpsh`)

A diferència de `num_planned_dpsh` (que era dada morta), `site_address` **s'utilitza**:
- `web/wizard_service.py:2001-2020` → omple/millora **`street_address`** i
  **`site_municipality`** (via `_split_address`).
- `automation/auto_extractor.py:1560-1570` → **fallback de geocodificació** (→ UTM).

Per tant, el valor brossa pot corrompre l'adreça de l'informe **i** les coordenades.
La lògica d'omplir només sobreescriu `street_address` quan és buit o no té número de
carrer — per això l'informe de Vacarisses no es va trencar visiblement (va guanyar el
valor de l'Eva, i la brossa no tenia número). Però el risc és real, sobretot en el
**cas freqüent sense plànol d'arquitecte** (§6 de l'anàlisi): quan no hi ha plànol, la
secció OBRA del pressupost pot ser **l'única font estructurada** de l'adreça del solar
i de la geocodificació.

## 3. L'estructura OBRA real (verificada empíricament, en ordre d'extracció)

```
OBRA:
[nom del client]        ← present 4/5 (absent a Castellar)
ESTUDI/ESTUDIO GEO...   ← tipus de projecte, sempre (pot tenir sufix: "3HAB.")
C/<carrer> <núm>        ← adreça del solar, present 4/5 (absent a Rubí)
MUNICIPI                ← sempre, última línia abans del marcador de fi
CLIENT:                 ← marcador de fi
```

A diferència de la taula DPSH, **aquest bloc SÍ surt en ordre de lectura net** — per
això un parser per línies hi és fiable (Via A). Tot i això, vegeu la variabilitat
de §5: Castellar sense línia de client, Rubí sense carrer, Linyola en una sola línia.

Dump real (línies extretes, índexs reals):

| Projecte | línia post-OBRA | línia ESTUDI | línia carrer | línia municipi |
|----------|-----------------|--------------|--------------|----------------|
| Vacarisses | `MARC VIDAL` | `ESTUDI GEOTECNIC` | `C/DE LA BARCELONETA 23` | `VACARISSES` |
| Castellar | *(cap)* | `ESTUDI GEOTECNIC 3HAB.` | `C/ARBRELLS 18A` | `CASTELLAR DEL VALLES` |
| Rubí | `JOANA MARTINEZ` | `ESTUDI GEOTECNIC` | *(cap)* | `RUBI` |
| Bell-lloc | `ARQUITECTURA BOSCH NOVELL` | `ESTUDI GEOTECNIC` | `C/MESTRE RAMON ORTIZ 15` | `BELL-LLOC` |
| Alcoletge | `SANS BONVEHI, ALBERT` | `ESTUDI GEOTECNIC` | `C/GIRASOLS 7, URB.EL ROSER` | `ALCOLETGE` |

---

## 4. Via A — Millora determinista (regex → parser de la secció OBRA)

Substituir el regex d'`EMPLAÇAMENT` (línies 389-402 de `_extract_docs_python`) per un
**parser del bloc OBRA**:

1. Trobar la primera línia `OBRA:`.
2. Recollir les línies no buides següents fins a un marcador de fi (una línia que
   acaba en `:` com `CLIENT:` / `CP I POBLACIÓ:`, o una línia de codi de pressupost
   tipus `26·0332`).
3. Localitzar la línia de tipus de projecte (`^ESTUDI[O]?\s+GEO`). Les línies
   **posteriors** a ella fins al marcador = `[carrer?, municipi]`.
4. L'**última** d'aquestes = municipi; el que va **abans** = carrer.
5. Si hi ha línia de carrer → emetre `site_address = "<carrer>, <municipi>"` (el format
   que espera el consumidor `_split_address`). Si **no hi ha** carrer (Rubí) → no emetre
   res (cap valor és millor que un de fals).
6. **No tocar** el bucle OBRA existent que omple `architect_company` (línies 318-335) —
   és una tasca a banda (punt 2 de l'anàlisi).

**Per què compondre `"CARRER, MUNICIPI"`:** `_split_address` ho torna a separar i omple
correctament `street_address` i `site_municipality`, complint el contracte documentat
(exemple al codi: `"C/MESTRE RAMON ORTIZ 15, BELL-LLOC"`).

### 4.1 Casos límit i tractament

| Cas | Exemple | Tractament |
|-----|---------|-----------|
| Sense línia de client | Castellar | ✅ ancora a la línia ESTUDI, no a la posició |
| Sense carrer | Rubí → només `RUBI` | ✅ no emetre res (no confondre municipi amb carrer) |
| Coma extra al carrer | Alcoletge `URB.EL ROSER` | ✅ municipi = última línia; el carrer conserva les seves comes |
| Castellà + província | Anciles `ANCILES (HUESCA)` | ✅ `ESTUDIO`; `_split_address` treu `(HUESCA)` |
| Una sola línia combinada | Linyola `Clot de la Llacuna, 16 -25240- Linyola` | ⚠️ **limitació coneguda** — sense PDF a reference-material per verificar; el fallback emet la línia sencera. Marcar, no sobre-ajustar. |

---

## 5. Via B — Anàlisi de visió del PDF del pressupost

**Objectiu:** que un LLM amb visió llegeixi el(s) PDF(s) del pressupost i extregui els
camps estructurats de manera robusta a la variabilitat humana, sense dependre de
l'ordre del text extret.

### 5.1 Infraestructura existent reaprofitable
- Ja existeix `projecte_extracted.json` (`extraction_method: vision_chunked`) que
  llegeix un document de pressupost i ja encerta `street_address`/`municipality`/
  `client_name` (vegeu §0). El tipus de visió associat és `projecte_arquitecte`
  (`wizard_service.py:2038`).
- `vision_fast.py` ja sap llançar `claude -p` amb prompts autocontinguts per tasques
  de PDF; `concept_scout/vision_probe.py` ja fa proves de visió (Groq→Claude).

### 5.2 Disseny (DECIDIT: B2 — tasca dedicada)
- ✅ **B2 (escollida):** afegir un `vision_type = pressupost` amb prompt focalitzat
  sobre el(s) `PRESSUPOST*.pdf`, sortida a `pressupost_extracted.json` pròpia.
  - Avantatge sobre B1: separa la responsabilitat (el pressupost ≠ projecte arquitecte),
    prompt i sortida dedicats, comparació neta amb la Via A, i no embruta la visió
    `projecte` existent.
- ~~B1 (estendre `projecte`/`projecte_arquitecte`)~~ — descartada.

**Camps objectiu de la visió** (mínim per a aquesta avaluació): `site_address` (carrer),
`municipality`, `client_name`, `building_type`/`building_category` (C0–C3),
`num_planned_dpsh` / `num_planned_spt` / `num_planned_sondeig` (campanya prevista),
`client_nif`, `contact_name`, dates. *(La campanya prevista enllaça amb la pregunta de
§2.3 de l'anàlisi sobre sondeig=0.)*

### 5.3 Duplicació (no substitució) en aquesta fase
- Mantenir `docs_extracted.json` (Via A) **i** afegir la sortida de visió (Via B) en
  **paral·lel**. Cap consumidor (`wizard_service`, `auto_extractor`, geocodificació)
  canvia de font encara: seguim alimentant-los amb la Via A fins que la comparació
  decideixi. La Via B s'escriu al seu propi JSON per a comparació, sense connectar-la
  als camps de l'informe en aquesta fase.

### 5.4 Notes
- Sovint hi ha **dos** pressupostos: el vectorial (`26.0332/PRESSUPOST*.pdf`, enviat
  inicialment) i l'escanejat signat (`ACCEPTACIO/Presupost*.pdf`). La comparació ha
  d'anotar **quin fitxer** llegeix cada via (poden diferir; tots dos contenen OBRA).
- Model de visió: variable de test, no prescrit. (Memòria: l'Eva és l'única usuària →
  no fer servir "cost a volum" per justificar un model més feble; prioritzar fiabilitat.)
- Latència: la visió afegeix segons; acceptable (mai escatimar fidelitat).

---

## 6. Comparació i criteris de decisió

Per a cada projecte de referència, executar **les dues vies** i registrar tots dos
valors costat a costat, contra el *ground truth* (els blocs OBRA que el Josep ha
transcrit per a 8 projectes + `eva_reference_values.json`).

**Mètriques per via i per camp:**
- **Exactitud**: % de valors correctes quan la via emet un valor.
- **Cobertura**: % de projectes on la via troba un valor (no buit).
- **Mode de fallada**: brossa silenciosa (pitjor) vs. cap valor (acceptable).

**Regla de decisió (a aplicar amb dades, no ara):**
- Si la visió ≥ determinista en exactitud **i** cobertura, amb fallades més segures →
  candidata a quedar-se com a font primària (determinista com a *fallback* o retirat).
- Si empaten o el determinista és prou bo en el seu àmbit → mantenir determinista i
  descartar la visió per a aquest camp (estalvi de latència).
- Decisió **per camp**, no global: pot ser que la visió guanyi en `site_address` i
  l'extracció de campanya, i el determinista basti per a NIF/dates.

**Important:** anotar tota decisió al `DECISION-LOG.md` quan es prengui.

---

## 7. Pla de validació (abans de donar res per fet)

1. **Via A — empíric, pel codi real pegat** (dirs temporals, sense tocar els fitxers de
   l'Eva): assertar `site_address` als 5 pressupostos verificables contra el ground truth.
2. **Via A — downstream**: executar `_split_address(site_address)` per a cadascun →
   confirmar `(carrer, municipi)` correctes.
3. **Via A — test de lògica** contra els 8 blocs OBRA transcrits (cobreix
   Linyola/Vilanova/Anciles que el globber no abasta).
4. **Via B — execució** sobre els pressupostos disponibles → registrar valors.
5. **Comparació A vs B** amb la taula de mètriques de §6.
6. **Regressió**: suite completa vs. la línia base (s'ha de mantenir 32-failed/981-passed;
   cap test referencia l'extracció de `site_address`, però es confirmarà).

## 8. Abast de canvis i decisions obertes

**Abast del codi:**
- Via A: confinat al bloc `site_address` de `_extract_docs_python` (`web/vision_fast.py`).
- Via B: nova tasca/extensió de visió + nou JSON de sortida; **sense** reconnectar
  consumidors en aquesta fase.
- **No** tocar el bucle `architect_company` (tasca separada) ni la lògica d'omplir de
  `wizard_service.py:2014` (vegeu decisió oberta).

**Abast del doc:** durant la implementació, actualitzar **només** la part de
`site_address` de `ANALISI-PIPELINE-DEBUG-VACARISSES.md` (afegir §4.5, corregir
l'anotació de §4.1) i marcar §9/A5 com a realitzada. Aquest pla és el document de treball.

**Decisions preses (2026-06-23, Josep):**
1. ✅ **B2** — tasca de visió `pressupost` **dedicada** (no estendre la visió `projecte`
   existent). Sortida pròpia a `pressupost_extracted.json`.
2. ✅ **Regla de decisió: per camp** (confirmada). Pot guanyar la visió en `site_address`
   i campanya, i bastar el determinista en NIF/dates.
3. ✅ **Retirada de via**: una via es retira **quan no aporti valor**, però **NOMÉS
   després** d'implementar les **dues** vies i provar-les amb **TOTS els projectes
   (8 actualment)**. Ara encara no ho sabem → no decidir amb n=1, no retirar res abans
   de la comparativa completa.
4. ⏳ **Prioritat de font** (diferida, no bloqueja): en aquesta fase la Via B **no**
   reconnecta cap consumidor, així que no cal decidir-ho encara. Es manté el comportament
   conservador actual (`wizard_service.py:2014`) fins que la comparativa ho justifiqui.

**Conjunt de prova obligatori — els 8 projectes:** Vacarisses, Bell-lloc, Castellar,
Rubí, Linyola, Alcoletge, Vilanova de Segrià, Anciles.
- 5 tenen `PRESSUPOST*.pdf` estàndard que el globber actual llegeix (Vacarisses,
  Castellar, Rubí, Bell-lloc, Alcoletge).
- **Prerequisit (RESOLT — PDFs localitzats):**
  - Vilanova: `4001671 VILANOVA DE SEGRIA/26.0050/PRESUPUESTO GEOTEC.VILANOVA DE SEGRIA.pdf`
  - Anciles: `4001679 ANCILES/24.0807/PRESUPUESTO GEOTEC.ANCILES.pdf`
  - Linyola: `4001607 LINYOLA/validation/msg_attachments/pressupost geotècnic/2_02B_DG_Silvia_Jaume.pdf`
    (adjunt de correu, **nom no estàndard** — el cas més difícil)
  - (rutes canòniques completes a `/mnt/c/claude/g3dt/AI-pipeline/reference-material/`)

> ⚠️ **TROBALLA — bretxa de descobriment compartida per les DUES vies.**
> `_extract_docs_python` fa glob de `PRESSUPOST*.pdf` (**només català**). Vilanova i
> Anciles anomenen el pressupost `PRESUPUESTO GEOTEC.*.pdf` (**castellà**) → el globber
> **els ignora completament** i `docs_extracted.json` no rep cap camp OBRA per a ells.
> Linyola arriba com a adjunt amb nom arbitrari → tampoc el troba. Conseqüència:
> - La **Via A** no pot llegir el pressupost de Vilanova/Anciles/Linyola tal com està.
> - La **Via B** (visió) també necessita **descobrir** el PDF correcte abans de llegir-lo.
> → **Pas 0 compartit**: un descobridor de pressupost robust al català/castellà i a noms
> no estàndard (glob `PRESSUPOST*|PRESUPUESTO*` + rol `budget`/concept_map com a
> *fallback*). Això connecta amb el tema general català-vs-castellà (cf. tests
> `test_smartscan` ES-variants). Decidir si s'aborda dins aquesta correcció o com a
> pas previ separat.

---

## 9. Ordre d'execució proposat

0. **Prerequisit**: localitzar els PDFs de pressupost de **Linyola, Vilanova, Anciles**
   per poder provar les dues vies sobre els **8** projectes (vegeu §8).
1. Implementar **Via A** (parser OBRA determinista) + validar (§7.1–7.3) + regressió.
2. Implementar **Via B** (`vision_type=pressupost` dedicada, duplicada, sense reconnectar
   consumidors) + executar (§7.4) sobre els 8.
3. **Comparar** A vs B (§6) sobre **els 8 projectes**.
4. **Decidir per camp** quina via es queda (o totes dues); retirar només el que no aporti
   valor; anotar a `DECISION-LOG.md`.
5. Actualitzar `ANALISI-...md` §4.5 i §9/A5.

*Fi del pla. Cap canvi de codi ni de consumidors fet encara. Branca: `fix/pipeline-routing`.*
