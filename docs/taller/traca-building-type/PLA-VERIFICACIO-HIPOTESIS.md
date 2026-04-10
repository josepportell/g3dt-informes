# Pla de verificació d'hipòtesis — building_type trace

**Data:** 2026-04-10
**Context:** Traça completa de `building_type` amb hipòtesis formulades. Cal verificar-les.

---

## Estat de cada hipòtesi

### H1. LLM synthesis sobreescriu valors amb millor prioritat

**Estat: VERIFICADA — ÉS CERT, però amb matisos**

Codi (`wizard_service.py:717-722`):
```python
def _set(key, value, source='llm_synthesis'):
    existing = merged.get(key)
    if isinstance(existing, dict) and existing.get('source') == 'user':
        return  # NOMÉS protegeix 'user'
    if value:
        merged[key] = {'value': value, 'source': source}
```

`_set()` només protegeix la font `user`. Qualsevol altra font (incloent `planol_vision`
amb prioritat 20) és sobreescrita per `llm_synthesis`.

**Matís important:** La synthesis NO és inútil aquí. El valor raw del vision és
`"habitatge unifamiliar aïllat"` (sense article). Eva escriu `"un habitatge unifamiliar"`.
La synthesis afegeix l'article `"un"` → `"un habitatge unifamiliar aïllat"`.
La transformació és útil; el problema és que la synthesis hauria de **transformar**
el valor de vision, no **substituir-lo** amb una síntesi independent.

**Conclusió:** No cal eliminar la synthesis, cal que respecti les fonts de qualitat alta.
Fix: `_set()` hauria de comparar la prioritat de la font existent amb un llindar.

---

### H2. El 20% de coverage del format learning és enganyós

**Estat: VERIFICADA — ÉS CERT**

El format_learner (`format_learner.py:96-111`) calcula:
```
expected = EXPECTED_FIELDS["architect_plan"]  → 10 camps
extracted = concept_ids de senyals FileMiner per aquest fitxer
coverage = extracted ∩ expected / expected
```

Per Bell-Lloc A.01.pdf:
- FileMiner extreu 18 senyals del plànol
- Però només 2 tenen concept_id assignat: `client_phone` i `client_email`
- D'aquests 2, cap està a EXPECTED_FIELDS → 0 coincidències
- Aleshores coverage = 0/10 = 0% (?!)

**Atenció:** El deep trace deia 20%, no 0%. Pot ser que algunes senyals sense
concept_id tinguin maps_to que coincideixi amb expected_fields. Cal verificar.

**En tot cas:** Vision extreu building_type, architect, client, municipality, street,
superficies del plànol — 6-8 camps dels 10 expected. Però el format learning
NO compta les extraccions vision. Això fa que es mostri un banner ambar
("format desconegut") per fitxers on el pipeline de fet extreu bé.

**Conclusió:** El format learning mesura una cosa diferent del que pensem.
Mesura la capacitat del FileMiner regex, no la capacitat total del pipeline.
Opció A: Integrar les extraccions vision al càlcul de coverage.
Opció B: Documentar clarament que coverage = "cobertura de FileMiner" i
no confondre-la amb la cobertura total.

---

### H3. A Linyola, SmartScan classifica malament el plànol

**Estat: REFUTADA — El plànol s'extreu correctament**

`planol_extracted.json` de Linyola conté:
```
source_file: "Punts de Sondeig_Silvia_Jaume.pdf"
building_type: "habitatge unifamiliar aïllat"
project_name: "PROJECTE BÀSIC D'UN HABITATGE UNIFAMILIAR AÏLLAT"
architect: "JOSEP BUNYESC PALACÍN"
```

Malgrat el nom enganyós del fitxer ("Punts de Sondeig"), el PDF conté el plànol
de l'arquitecte i vision l'extreu correctament. SmartScan o bé el classifica bé,
o bé la fallback del concept_map l'identifica correctament.

**Conclusió:** No hi ha problema de classificació a Linyola. El problema és que
Eva diu "un **nou** habitatge" i el plànol no diu "nou" — "nou" és informació
contextual que Eva afegeix pel seu coneixement del projecte.

---

### H4. L'etiqueta "OBRA" causa senyals dolentes als pressupostos

**Estat: VERIFICADA — ÉS CERT**

FileMiner extreu de "Pressupost C1" amb el mètode `label_value`, i el valor és
`"Bell-lloc - CL MESTRE RAMON ORTIZ 15"` — clarament una adreça, no un building_type.
L'etiqueta "OBRA" al pressupost fa referència a la descripció/ubicació de l'obra,
no al tipus d'edificació.

Però la comanda lab ("CONSTR HABITATGE" via `label_adjacent`) sí és pertinent,
tot i ser genèrica. La qüestió és que les senyals dolentes del pressupost
tenen prioritat 30 (millor que la comanda lab a 50) → guanyen la competició.

**Conclusió:** Doble problema:
1. "OBRA" al pressupost captura dades incorrectes
2. Les senyals incorrectes guanyen la competició perquè tenen millor prioritat

Fix: O eliminar "OBRA" de `pressupost_pdf_v1.yaml`, o afegir validació de contingut.

---

### H5. L'LLM judge reclassificaria MISMATCH com CLOSE

**Estat: NO VERIFICADA — Cal testejar**

**Pla de verificació:**
```bash
.venv/bin/python scripts/compare_benchmarks.py --llm-judge --all
```

Predicció basada en l'anàlisi manual de building_type per 7 projectes:
- Bell-Lloc: CLOSE → seguiria CLOSE (score 4-5)
- Linyola: MISMATCH → CLOSE (score 3-4, "nou" vs "aïllat")
- Castellar: MISMATCH → MISMATCH (score 1-2, completament diferent)
- Rubí: CLOSE → CLOSE (score 3-4)
- Alcoletge: MISMATCH → MISMATCH (score 1, "habitatge" vs "ampliació")
- Vilanova: depèn de si compara CA vs ES
- Anciles: CLOSE (falta "unifamiliares")

---

### H6. Vision sempre diu "habitatge unifamiliar aïllat" (NOVA)

**Estat: VERIFICADA — Patró clar**

| Projecte | Vision building_type | Eva building_type | Correcte? |
|---|---|---|---|
| Bell-Lloc | habitatge unifamiliar aïllat | un habitatge unifamiliar | SÍ (Eva omet aïllat) |
| Castellar | habitatge unifamiliar aïllat | 3 habitatges unifamiliars d'estructura lleugera, fusta | NO |
| Rubí | habitatge unifamiliar | un habitatge unifamiliar aïllat modular | PARCIAL |
| Linyola | habitatge unifamiliar aïllat | un nou habitatge unifamiliar | PARCIAL |
| Alcoletge | habitatge unifamiliar | l'ampliació d'un edifici en planta baixa | NO |
| Vilanova | habitatge unifamiliar aïllat | una vivienda unifamiliar aislada | SÍ (traducció) |
| Anciles | 7 viviendas adosadas | 7 viviendas unifamiliares adosadas | PARCIAL |

**Anàlisi:**
- 2/7 correctes (Bell-Lloc, Vilanova)
- 3/7 parcials — la base és correcta, falten qualificadors
- 2/7 incorrectes (Castellar: 3 unitats + fusta; Alcoletge: és ampliació)

Vision extreu el que diu el caixetí del plànol literalment. El caixetí sovint diu
"HABITATGE UNIFAMILIAR AÏLLAT" com a títol genèric del projecte, sense matisos.
Els matisos (quantitat, material, si és reforma/ampliació) estan en altres parts
del document o en el context del projecte.

**Conclusió:** Vision fa bé la seva feina (extreu el que hi ha). El problema
és que el caixetí NO conté tota la informació que Eva posa al building_type.
Les fonts complementàries (comanda lab, emails, pressupost) haurien d'aportar
els matisos, i la synthesis hauria de combinar-los — però ara la synthesis
sobreescriu en comptes de combinar.

---

### H7. Alcoletge és insoluble sense context humà (NOVA)

**Estat: VERIFICADA**

Eva: "l'ampliació d'un edifici en planta baixa"
Vision: "habitatge unifamiliar"
Plànol: El caixetí diu "HABITATGE UNIFAMILIAR" — NO diu "AMPLIACIÓ"

El concepte "ampliació" probablement ve de:
- La comanda laboratori (potser diu "AMPLIACIÓ" o "REFORMA")
- Conversa directa amb el client
- Coneixement del context del projecte

**Pla de verificació:**
```bash
# Buscar "ampliac" als fitxers del projecte
grep -ri "ampliac\|reforma\|extensi" "reference-material/4001670 ALCOLETGE/"
```

Si cap fitxer del projecte conté "ampliació", aleshores aquesta variable
és de Tier C ("professional judgment") i no la podem extreure automàticament.
Si algun fitxer sí ho diu, cal millorar l'extracció per detectar-ho.

---

## Pla d'accions ordenat per impacte

### Fase 1: Verificacions pendents (1 hora)

| # | Verificació | Comanda | Resultat esperat |
|---|---|---|---|
| V1 | LLM judge impacte real | `compare_benchmarks.py --llm-judge` | Quants MISMATCH → CLOSE? |
| V2 | Coverage real format learning | Analitzar maps_to vs concept_id a signals Bell-Lloc | Per què diu 20% i no 0%? |
| V3 | Alcoletge: "ampliació" als fitxers? | grep als fitxers del projecte | Context o judgment? |
| V4 | Quantes variables sobreescriu llm_synthesis? | Log pre/post synthesis | Quantificar impacte |

### Fase 2: Fixes d'alt impacte (2-3 hores)

| # | Fix | Impacte | Risc |
|---|---|---|---|
| F1 | `_set()` respecta source_priority | Evita sobreescriure planol_vision (pri=20) | Baix — ja tenim el schema |
| F2 | Integrar LLM judge a diagnostic_trace.py | Mesura correcta d'accuracy | Zero — és diagnòstic, no producció |
| F3 | Eliminar "OBRA" de pressupost_pdf_v1.yaml | Elimina senyals dolentes per building_type | Baix — verificar que no trenca altres conceptes |

### Fase 3: Completar sistema (4-6 hores)

| # | Fix | Impacte | Risc |
|---|---|---|---|
| F4 | Format schemas per lab (gtl_report) | 8 conceptes lab sense mapping | Mig — cal estudiar format GTL |
| F5 | Completar planol_vision_v1.yaml | De 9 a ~15 mappings | Baix |
| F6 | Format learning: integrar vision | Coverage reflecteix realitat | Mig — canvi de mètriques |

### Fase 4: Refinament (2-3 hores)

| # | Fix | Impacte | Risc |
|---|---|---|---|
| F7 | Prompt synthesis: no inventar qualificadors | Menys "aïllat" inventat | Baix |
| F8 | LLM synthesis: combinar en comptes de substituir | Millor ús de múltiples fonts | Mig |

---

---

## Resultats de les verificacions (executades 2026-04-10)

### V1: LLM judge — PENDENT (executar manualment)

Comanda: `.venv/bin/python scripts/compare_benchmarks.py --llm-judge --all`
No executada perquè requereix API calls i temps. Planificada per la propera sessió.

### V2: Format learning coverage — RESOLT

**Resultat:** El plànol A.01.pdf de Bell-Lloc realment té **0% coverage** (no 20%).

FileMiner extreu 6 senyals d'A.01.pdf, però les úniques amb concept_id són
`client_phone` i `client_email` — CAP dels 10 expected fields per architect_plan.

El 20% que apareixia al deep trace venia d'un **altre fitxer** (pressupost o email),
no del plànol. El plànol té 0% de cobertura FileMiner.

**Implicació:** El plànol depèn 100% del vision per extreure dades. FileMiner no
n'extreu res útil (només phone/email). Això no és necessàriament un problema —
els plànols són PDFs d'imatge amb caixetí, el text extret per PyMuPDF és fragmentat.
Però el format learning mostra 0% i activa el banner ambar innecessàriament.

**Acció:** El format learning per `architect_plan` hauria de considerar les
extraccions vision (planol_extracted.json), no només FileMiner.

### V3: Alcoletge "ampliació" — RESOLT (és EXTRACTIBLE, no judgment)

**Resultat:** La paraula "Ampliació" SÍ apareix als fitxers del projecte:

```
- 26.0049/RE_ geotècnic Ampliació Albert Sans munici...  (email .msg)
- 26.0049/geotècnic Ampliació Albert Sans municipi d...    (email .msg)
- msg_attachments/RE_ geotècnic Ampliació Albert Sans...   (adjunts)
```

FileMiner detecta les senyals (14 coincidències!) però **totes tenen concept=None**.
La paraula "Ampliació" apareix al **nom del fitxer/email**, no com a valor extret
amb concept_id assignat.

**Causa:** No hi ha cap regex ni label mapping que converteixi "Ampliació" al nom
d'un fitxer/email en un senyal `building_type`. FileMiner mina el contingut dels
fitxers, no els noms. SmartScan classifica pel nom, però no genera senyals building_type.

**Acció concreta:** El nom del fitxer/email conté informació valuosa:
"geotècnic Ampliació Albert Sans municipi Alcoletge" → building_type="ampliació",
client_name="Albert Sans", municipality="Alcoletge". Cal un miner que extregui
senyals dels noms de fitxer/email.

### V4: Synthesis overwrite — RESOLT (4 variables, impacte moderat)

**Resultat:** LLM synthesis sobreescriu exactament **4 variables** per Bell-Lloc:

| Variable | Valor synthesis | Font sobreescrita |
|---|---|---|
| building_type | "un habitatge unifamiliar aïllat" | planol_vision (pri=20) |
| architect_name | "JORDI BOSCH NOVELL" | planol_vision (pri=20) |
| client_name | "RAMON MITJANA S.L" | planol_vision (pri=20) |
| location_sentence | "al Carrer Mestre Ramon Ortiz de Bell-Lloc d'Urgell" | (no tenia font prèvia) |

De les 4:
- `location_sentence`: Correcte — no tenia valor previ, synthesis aporta
- `architect_name`: Synthesis posa el mateix valor que vision → overwrite inofensiu
- `client_name`: Synthesis posa el mateix valor que vision → overwrite inofensiu
- `building_type`: Synthesis afegeix l'article "un" → útil, però sobreescriu la font

**Conclusió:** L'impacte real de F1 és menor del que pensàvem per Bell-Lloc.
La synthesis sovint produeix el MATEIX valor que vision (perquè rep el valor vision
com a input). Però el source canvia de "planol_vision" a "llm_synthesis", cosa que:
1. Perd traçabilitat (no sabem que ve del planol)
2. En projectes sense planol, la synthesis inventa (Alcoletge)

**Fix mínim:** `_set()` hauria de preservar el source original quan el valor no canvia
significativament. Si synthesis output ≈ existing value → mantenir source original.

---

## Conclusions sòlides (post-verificació)

### Confirmat
1. **LLM synthesis sobreescriu 4 vars** però sovint amb el mateix valor → el fix F1
   és de traçabilitat, no tant d'accuracy
2. **Format learning 0% per plànol** perquè no compta vision → necessita integració
3. **Alcoletge "ampliació" és extractible** dels noms d'email → necessita un miner nou
4. **"OBRA" als pressupostos captura adreces** → eliminar del format schema

### Refutat
5. **Linyola NO té problema de classificació** — vision extreu correctament del plànol
6. **Synthesis NO és un problema d'intel·ligència** — és Sonnet 4.6, suficient.
   El problema és que sobreescriu i no preserva la traçabilitat

### Pendent
7. **LLM judge (V1)** — cal executar per quantificar falsos MISMATCH
