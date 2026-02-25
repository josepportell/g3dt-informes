# Auditoria Automatització Informe Geotècnic - v6
## Projecte referència: 4001612 Bell-Lloc d'Urgell

**Data:** 2026-02-06
**Versió:** v6.1 (bugs 14-16 corregits + 2 bugs addicionals)
**Branca:** `main`
**Basat en:** v6 + fix 5 bugs (3 planificats + 2 detectats en verificació)

---

### Resum Executiu

**Millora global:** De ~93% (v6) a **~95%** (v6.1 — 5 bugs corregits)

v6 havia detectat 3 bugs nous. Tots 3 **corregits**, més 2 bugs addicionals trobats durant verificació:

| # | Bug | Severitat | Estat |
|---|-----|-----------|-------|
| 14 | Text nivell 2 duplicat del nivell 1 | **CRÍTIC** | ✅ **CORREGIT** |
| 15 | Frase accés malformada ("a través de L'accés...") | **ALT** | ✅ **CORREGIT** |
| 16 | Contradicció "un sol nivell" amb 2 nivells | **ALT** | ✅ **CORREGIT** |
| 20 | Caption gràfic "primer nivell" hardcoded dins loop | **MITJÀ** | ✅ **CORREGIT** |
| 21 | Conclusions "un sòl nivell" hardcoded (P407) | **MITJÀ** | ✅ **CORREGIT** |

**Canvis sessió 2026-02-06 (nit):**
1. Fix template: 6 paràgrafs modificats (P107, P231, P244, P247, P256, P407)
2. Fix report_generator.py: `soil_levels[]` enriquit amb `materials_text` per-nivell, `materials_intro` dinàmic, `conclusions_levels_detected` dinàmic
3. Verificació completa: zero "primer nivell" hardcoded dins loop, zero "un sòl nivell" a tot el document

---

### Bugs corregits (v6 → v6.1)

#### BUG 14: Text nivell 2 duplicat [CRÍTIC] — ✅ CORREGIT

**Símptoma:** Secció 3.2.2 ("2n Nivell") tenia text idèntic a 3.2.1 ("1er Nivell").

**Causa arrel:** Template P244 usava `{{ materials_level_1 }}` (variable fixa) dins del loop `{%p for level in soil_levels %}`.

**Fix aplicat:**
- Template P244: `{{ materials_level_1 }}` → `{{ level.materials_text }}`
- Template P247: "primer nivell" → `{{ level.ordinal }} nivell`
- Template P262: `{{ materials_depth_text }}` → `{{ level.depth_text }}`
- Template P266: `{{ materials_geomech_text }}` → `{{ level.geomech_text }}`
- report_generator.py: `soil_levels[]` mogut a després de section3 processing, enriquit amb `materials_text` per-nivell de `s3.materials_levels[i]`

**Verificació:** L1 = "grava con arenas", L2 = "grava cementada" — text únic per nivell.

#### BUG 15: Frase accés malformada [ALT] — ✅ CORREGIT

**Símptoma:** "a través de L'accés al solar es realitza des del Carrer existent al sud."

**Fix aplicat:** Template P107 — tret text estàtic, ara només `{{ access_description }}`.

**Verificació:** `L'accés al solar es realitza des del Carrer existent al sud.` — frase neta.

#### BUG 16: Contradicció "un sol nivell" secció 3 [ALT] — ✅ CORREGIT

**Símptoma:** Text introductori deia "un sol nivell" amb 2 subseccions renderitzades.

**Fix aplicat:**
- Template P231: text hardcoded → `{{ materials_intro }}`
- report_generator.py: `context['materials_intro'] = s3.materials_intro` (genera text dinàmic amb plural correcte)

**Verificació:** `s'han identificat 2 nivells geotècnics fins a la fondaria investigada.`

#### BUG 20: Caption gràfic hardcoded dins loop [MITJÀ] — ✅ CORREGIT

**Símptoma:** P256 "Gràfic 1. Distribució granulomètrica dels materials del primer nivell." — "primer nivell" hardcoded, repetit idèntic per cada iteració del loop.

**Detectat:** Durant verificació post-fix dels bugs 14-16.

**Fix aplicat:** Template P256: "primer nivell" → `{{ level.ordinal }} nivell`.

**Verificació:** L1 = "1er nivell", L2 = "2n nivell".

#### BUG 21: Conclusions "un sòl nivell" hardcoded [MITJÀ] — ✅ CORREGIT

**Símptoma:** P407 "Es detecta un sòl nivell de materials..." — hardcoded singular a la secció 4.

**Detectat:** Durant verificació post-fix dels bugs 14-16.

**Fix aplicat:**
- Template P407: text hardcoded → `{{ conclusions_levels_detected }}`
- report_generator.py: nou context variable amb plural condicional

**Verificació:** `Es detecten 2 nivells de materials des del punt de vista geològic/geotècnic en el subsòl del solar en estudi.`

---

### Comparació detallada: Generat vs Referència

#### Secció 1 — PRESENTACIÓ DE L'ESTUDI

| Element | Generat | Referència | Match |
|---------|---------|-----------|-------|
| Client | RAMON MITJANA S.L. | RAMON MITJANA S.L. | ✅ |
| Arquitecte | Jordi Bosch Novell | JORDI BOSCH NOVELL | ✅ (majúscules) |
| Adreça | Carrer Mestre Ramon Ortiz, 25220 Bell-Lloc d'Urgell | Carrer Antoni Bellet / Carrer Mestre Ramon Ortiz | ⚠️ Generat: 1 carrer. Ref: 2 carrers |
| Plantes | PB+P1 | Pb+1Pp | ✅ equivalent |
| Superfície parcel·la | 598 m² | 995 m² | ❌ Ref diferent (edició manual?) |
| Superfície construïda | 297 m² | 280+86 m² | ❌ Ref diferent |
| Classificació | C-1, T-1 | C-1, T-1 | ✅ |
| Objectius (6 punts) | Presents | Presents | ✅ |

> **Nota:** Les diferències de superfícies suggereixen que la referència va ser editada manualment post-generació. Les dades del generat coincideixen amb `planol_extracted.json` (598 m², 296.88 m²).

#### Secció 2 — TREBALLS DE CAMP

| Element | Generat | Referència | Match |
|---------|---------|-----------|-------|
| Dates camp | "1 i 6 d'octubre de 2025" | "1 i 6 d'octubre de 2025" | ✅ |
| Adjacent nord | Carrer Inventat, 3 | parcel·la buida | ⚠️ user_data manual |
| Adjacent sud | Carrer d'Antoni Bellet i Pérez | Carrer Antoni Bellet | ✅ equivalent |
| Adjacent est | Carrer Mestre Ramon Ortiz | Carrer Mestre Ramon Ortiz | ✅ |
| Adjacent oest | construcció aïllada de 2 plantes | construcció aïllada de 2 plantes | ✅ |
| Descripció accés | ✅ "L'accés al solar es realitza des del Carrer existent al sud." | "des del Carrer existent al sud" | ✅ |
| Descripció solar | "pendent de 155" (typo) | "15cm per sota de la rasant" | ⚠️ user_data |
| DPSH P-1 profunditat | -1.40m | -1.35m | ⚠️ |
| DPSH P-2 profunditat | -2.60m | -2.45m | ⚠️ |
| DPSH refús | Sí (ambdós) | Sí (ambdós) | ✅ |
| SPT N30 | 54 | 54 | ✅ |
| Lab test | UNE 83963:2008 | UNE 83963:2008 | ✅ |
| Sulfats | 89.8 mg/kg | 89.8 mg/kg | ✅ |
| Taula sondeig separada | No existeix | Sí (T5 ref) | ❌ Falta |

**Nota DPSH:** Les profunditats del generat venen de `DPSH.xls` (via `dpsh_extractor.py`). Les diferències de 5-15 cm poden ser arrodoniments manuals a la referència.

#### Secció 3 — GEOLOGIA I GEOTÈCNIA

| Element | Generat | Referència | Match |
|---------|---------|-----------|-------|
| Unitat geològica | P8G (codi ICGC) | Qvpu (Pleistocè) | ⚠️ Codi vs nom |
| Nre. nivells narratiu | ✅ "2 nivells geotècnics" | 1 nivell | ✅ Dinàmic |
| Nre. nivells taules | 2 nivells | 1 nivell | ⚠️ Diferent criteri |
| Nivell 1 descripció | "grava con arenas" | "graves en matriu sorrenca carbonatades" | ⚠️ Detall |
| Nivell 2 descripció | ✅ "grava cementada" (text únic) | N/A (1 sol nivell) | ✅ |
| Nivell freàtic | No detectat | No detectat | ✅ |
| Sulfats | 89.8 mg/kg, No Agressius | 89.8 mg/kg, No Agressius | ✅ |
| Sísmica AB | 0.04g | < 0.04g | ✅ |
| Radó | ZONA 1 | ZONA 1 | ✅ |
| Permeabilitat | K = 10⁻² a 10⁻⁴ m/s | K = 10 a 10⁻² m/s | ❌ Diferent |

**Paràmetres geotècnics (Taula 9 generat vs Taula 12 referència):**

| Paràmetre | Gen. Nivell 1 | Gen. Nivell 2 | Referència (1 nivell) | Nota |
|-----------|--------------|--------------|----------------------|------|
| Nb | 16-33 | 12-R | 25-R | Split vs global |
| N (SPT equiv.) | 18 | 34 | 54 | ❌ Ref usa N30 directe |
| γ (g/cm³) | 1.9 | 2.1 | 2.0 | ⚠️ Pendent G3DT |
| c (kg/cm²) | 0.00 | 0.00 | 0.0 | ✅ |
| φ (°) | 35 | 38 | 38 | ⚠️ Nivell 1 diferent |
| E (kg/cm²) | 188 | 345 | 650 | ❌ Pendent G3DT |

> **Anàlisi:** La referència tracta tot el terreny com 1 nivell únic amb els valors SPT directes (N=54). El generat parteix les lectures DPSH per capa de sondeig (0-1m i 1-1.8m), donant valors menors per cada capa individualment. Ambdós enfocaments són vàlids tècnicament, però el resultat final és diferent. **Cal confirmar amb Eva quin criteri prefereix.**

#### Secció 4 — CONCLUSIONS

| Element | Generat | Referència | Match |
|---------|---------|-----------|-------|
| Fonamentació | Superficial (sabates/llosa) | Superficial (sabates/llosa) | ✅ |
| Qa | 3.18 kg/cm² | 3.0 kg/cm² | ❌ (γ) |
| Assentament | 0.72 cm | < 1.20 cm | ⚠️ Valors diferents |
| K30 | 3.7 kg/cm³ | No explícit | ⚠️ |
| Signatura | Eva Vazquez Marcet, col 4302 | Eva Vázquez Marcet, col 4302 | ✅ |
| "xxxx" placeholder | No | Sí (secció 4.2 ref) | ✅ Generat millor |

---

### Inventari de taules: Generat vs Referència

| Generat | Contingut | Referència | Contingut | Match |
|---------|-----------|-----------|-----------|-------|
| T0 | Dades edificació | T0 | Dades edificació | ✅ (valors ≠) |
| T1 | Classificació CTE | T2 | Classificació CTE | ✅ |
| T2 | DPSH resultats | T4 | DPSH resultats | ✅ (profunditats ≠) |
| — | — | T5 | Sondeig resum | ❌ **Falta** |
| T3 | SPT resultats | T6 | SPT resultats | ✅ |
| T4 | Assaigs lab | T7 | Assaigs lab | ✅ |
| T5 | Nivells sòl (2 files) | T8 | Nivells sòl (1 fila) | ⚠️ |
| T6 | Permeabilitat (2 files) | T9 | Permeabilitat (1 fila) | ⚠️ |
| T7 | Agressivitat | T10 | Agressivitat | ✅ |
| T8 | Sísmica (2 files) | T11 | Sísmica (1 fila) | ⚠️ |
| T9 | Paràmetres geotècnics (2 files) | T12 | Paràmetres geotècnics (1 fila) | ⚠️ (valors ≠) |
| T10 | Signatura | T13 | Signatura | ✅ |
| — | — | T1, T3 | Separadors buits | N/A |

**Resum:** 11 taules generades vs 14 referència. Falta la taula resum de sondeig. 2 taules separadores de la referència no calen. Diferència real: **1 taula faltant**.

---

### Actualització estat elements pendents

| # | Element | v5.1 | v6 | Acció |
|---|---------|------|----|-------|
| ~~1-8~~ | (resolts en versions anteriors) | ✅ | ✅ | FET |
| 9 | Qa = 3.18 → 3.0 (γ) | Esperant G3DT | Sense canvis | Eva confirma γ |
| 10 | E = ~400 → 650 | Esperant G3DT | Sense canvis | Eva confirma correlació |
| 11 | Plantilles geologia | Esperant contingut | Sense canvis | G3DT proporciona textos |
| 12 | Text sondeig descriptiu | Esperant contingut | Sense canvis | G3DT proporciona paràgrafs |
| 13 | Descripció litològica | Contingut | Sense canvis | "Graves en matriu sorrenca carbonatades" |
| ~~14~~ | ~~Text nivell 2 duplicat~~ | NOU CRÍTIC | ✅ **CORREGIT** | Template P244 + report_generator.py |
| ~~15~~ | ~~Frase accés malformada~~ | NOU ALT | ✅ **CORREGIT** | Template P107 |
| ~~16~~ | ~~Contradicció "un sol nivell"~~ | NOU ALT | ✅ **CORREGIT** | Template P231 + report_generator.py |
| **17** | **Taula sondeig faltant** | N/A | **PENDENT MITJÀ** | Afegir taula resum sondeig al template |
| **18** | **Permeabilitat diferent** | N/A | **PENDENT BAIX** | Revisar correlació K vs N20 |
| **19** | **Criteri 1 vs 2 nivells** | N/A | **PENDENT MITJÀ** | Confirmar amb Eva: split per capes o nivell únic? |
| ~~20~~ | ~~Caption gràfic hardcoded~~ | N/A | ✅ **CORREGIT** | Template P256 |
| ~~21~~ | ~~Conclusions "un sòl nivell"~~ | N/A | ✅ **CORREGIT** | Template P407 + report_generator.py |

---

### Taula comparativa v1 → v6

| Mètrica | v1 | v2 | v3 | v5.1 | v6 | v6.1 | Tendència |
|---------|-----|-----|-----|------|-----|------|-----------|
| ✅ Correcte (>95% match) | 171 (75%) | ~200 (88%) | ~210 (92%) | ~219 (96%) | ~213 (93%) | ~218 (95%) | ↑ recuperant |
| ⚠️ Modificat (80-95%) | 23 (10%) | ~12 (5%) | ~8 (4%) | ~4 (2%) | ~7 (3%) | ~5 (2%) | ↓ |
| ❌ No implementat (<50%) | 33 (15%) | ~15 (7%) | ~9 (4%) | ~4 (2%) | ~7 (3%) | ~5 (2%) | ↓ |

> **Nota:** v6 va detectar 3+2 bugs. v6.1 els corregeix tots 5. Elements pendents: taula sondeig (17), permeabilitat (18), criteri nivells (19).

---

### Resum de cobertura (actualitzat)

```
┌─────────────────────────────────────────────────────────┐
│  AUTOMATITZACIÓ user_data.json — v6                      │
│                                                          │
│  █████████████████████████████░░ 29 camps (66%) AUTO     │
│  ███████░░░░░░░░░░░░░░░░░░░░░░   7 camps (16%) SEMI-AUTO│
│  █████░░░░░░░░░░░░░░░░░░░░░░░░   5 camps (11%) MANUAL   │
│  ███░░░░░░░░░░░░░░░░░░░░░░░░░░   3 camps  (7%) DEFAULTS │
│                                                          │
│  Total: 44 camps                                         │
│  Automatització efectiva: 82% (auto + semi-auto)         │
│  Requereix intervenció: 18% (manual + defaults)          │
│                                                          │
│  QUALITAT GENERACIÓ .docx: 95% (228 elements)            │
│  Bugs bloquejants: 0 (5 corregits a v6.1)               │
└─────────────────────────────────────────────────────────┘
```

---

### Wizard AskUserQuestion — Estat

**Operatiu des de v6.** Flux testat en viu:

1. ✅ Lectura JSONs i computació prefills (4 fonts amb prioritat)
2. ✅ Parsing nom carpeta (expedient + municipi)
3. ✅ Resum visual amb fonts per camp
4. ✅ AskUserQuestion 3 preguntes (multiSelect) per selecció de camps
5. ✅ Follow-up per camps seleccionats
6. ✅ Merge user_data.json (preserva camps existents)
7. ✅ Pregunta si generar .docx
8. ✅ Execució report_generator.py

**Millora detectada:** L'accés_description tenia "sonta" i "carer" — corregits a "sota" i "carrer" durant la sessió wizard.

---

### Recomanació pròxims passos

**~~Immediat (bugs bloquejants)~~ — ✅ TOTS CORREGITS (v6.1)**

~~1. BUG 14: Text nivell duplicat~~ ✅
~~2. BUG 15: Frase accés~~ ✅
~~3. BUG 16: Contradicció nivells~~ ✅
~~4. BUG 20: Caption gràfic~~ ✅
~~5. BUG 21: Conclusions nivells~~ ✅

**Curt termini (pròxima sessió):**
1. Afegir taula resum sondeig al template (element 17)
2. Confirmar amb Eva: criteri 1 vs 2 nivells (element 19)
3. Confirmar γ i correlació E (elements 9-10)
4. Poblar `depth_text` i `geomech_text` per-nivell (ara són stubs buits)

**Mitjà termini:**
5. Templates site/access description (quick wins — redueix camps manuals)
6. Plantilles geologia regional (element 11)
7. Descripció litològica detallada (elements 12-13)

---

### Fitxers modificats (v6.1)

| Fitxer | Bugs | Canvis aplicats |
|--------|------|-----------------|
| `templates/g3dt-jinja-template.docx` | 14, 15, 16, 20, 21 | 6 paràgrafs: P107, P231, P244, P247, P256, P407 |
| `automation/report_generator.py` | 14, 16, 21 | `soil_levels[]` enriquit + `materials_intro` + `conclusions_levels_detected` |

### Notes tècniques (v6.1)

- `depth_text` i `geomech_text` dins `soil_levels[]` són stubs buits (TODO). Cal implementar la generació per-nivell a `Section3Generator`.
- `materials_level_1` es manté al context per compatibilitat amb `conclusions_level_1` (secció 4).
- El bloc `soil_levels` context s'ha mogut a després del processament de section3 per tenir accés a `s3.materials_levels`.

---

*Auditoria v6.1 actualitzada: 2026-02-06. 5 bugs corregits (3 planificats + 2 detectats en verificació). Qualitat puja de 93% a 95%. Zero bugs bloquejants.*
