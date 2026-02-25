# Pla: Fase 2 — Afinament de la Generació Automàtica d'Informes

Data: 2026-02-24

## Context

Primer test end-to-end amb Castellar del Vallès (3001621) completat. Comparant l'informe generat amb el de referència de G3DT, el document té ~60-65% de contingut correcte (estructura, boilerplate, radó, sísmica, adjacents) però ~35-40% amb errors significatius (geologia regional equivocada, unitat ICGC diferent, paràmetres geomecànics incorrectes, seccions absents).

**Objectiu d'aquesta fase:** Cicle iteratiu de generació → comparació → anàlisi → correcció fins que els informes generats s'aproximin al màxim als de referència per qualsevol localitat i projecte.

## Part 1: Infraestructura — Carpeta de proves i documentació

### 1a. Crear estructura de carpetes

```
clients/g3dt/proves-fase2/
├── README.md                          # Explica la metodologia del cicle iteratiu
├── 3001621-castellar/
│   ├── run-001_2026-02-24.md          # Primera execució (avui)
│   ├── run-001_3001621_generated.docx  # Còpia de l'informe generat
│   └── (futures execucions: run-002_..., run-003_...)
├── 3001631-rubi/
├── 4001607-linyola/
└── 4001612-bell-lloc/
```

**Convenció de noms:**
- `run-NNN_YYYY-MM-DD.md` — Document de comparació (anàlisi + causes + fixes proposats)
- `run-NNN_{expedient}_generated.docx` — Còpia de l'informe generat en aquella execució
- Numeració seqüencial per run dins cada projecte

### 1b. Document de comparació (run-001 Castellar)

Guardar l'anàlisi comparativa ja feta com a `proves-fase2/3001621-castellar/run-001_2026-02-24.md`.

**Format estàndard de cada document de comparació:**

```markdown
# Run NNN — {Projecte} — {Data}

## Resum
| Mètrica | Valor |
|---------|-------|
| Informe referència | {path} |
| Informe generat | {path} |
| Coincidència estimada | X% |
| Errors crítics | N |
| Errors significatius | N |

## Diferències Crítiques
| # | Secció | Referència | Generat | Causa arrel | Fix proposat |

## Diferències Significatives
| # | Secció | Referència | Generat | Causa arrel | Fix proposat |

## Elements Correctes
(llista de què funciona bé)

## Fixes Aplicats des de l'Última Execució
(a partir de run-002+)

## Pròxims Passos
```

### 1c. README.md de proves-fase2

Document curt que explica:
- Objectiu de la fase 2
- Metodologia del cicle iteratiu
- Convenció de noms
- Com executar una prova i documentar-la

## Part 2: Fixes identificats — Prioritzats per impacte

### Fix 1: Bug d'accents a `determine_region()` [CRÍTIC] — RESOLT

**Causa arrel descoberta:** `determine_region()` compara municipi sense normalitzar accents.
- `parse_folder_name("3001621 CASTELLAR DEL VALLES")` → `"Castellar Del Valles"` (sense accent)
- `REGION_MAPPING['valles_penedes']['municipalities']` conté `"Castellar del Vallès"` (amb accent)
- Comparació case-insensitive `"castellar del valles" in "castellar del vallès"` → **False**
- Resultat: cau al default `depressio_ebre` → **tota la geologia equivocada**

**Fix:** A `icgc_geology.py:determine_region()`, normalitzar accents (unicodedata NFKD) abans de comparar:
```python
import unicodedata
def _normalize(s): return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
```
Aplicar tant al municipi d'entrada com als de la llista.

**Fitxer:** `automation/icgc_geology.py` (línies 564-570)

### Fix 2: Unitat ICGC 1:50.000 vs 1:25.000 [CRÍTIC] — RESOLT (camp manual)

**Causa:** L'API ICGC WMS només ofereix capa 1:50.000 (`unitats-geologiques-50000`). G3DT usa mapa 1:25.000 manualment i obté unitat més detallada (ECbc vs PEcg).

**Investigació (2026-02-24):**
- WMS NO té capa 25k. Només 50k i 250k.
- La 25k existeix com a **vector tiles** (Mapbox PBF): `https://geoserveis.icgc.cat/servei/catalunya/infogeo/vt/{z}/{x}/{y}.pbf`
- Cobertura parcial (~49% Catalunya). Visor: `https://visors.icgc.cat/infogeol25m`
- Per Castellar: 50k=PEcg (Conglomerats), 25k=Tm2 (Lutites i gresos vermells, Triàsic)
- Integrar vector tiles requeriria `mapbox-vector-tile` + `shapely` + gestió cobertura parcial

**Solució implementada:** Camp manual d'override a `user_data.json`:
- `icgc_unit_code`: Codi de la unitat (ex: "ECbc")
- `icgc_unit_description`: Descripció (ex: "Bretxes calcàries")
- `icgc_unit_epoch`: Època (ex: "Eocè")

Si presents, s'usen en comptes de la query WMS 50k. Si absents, funciona com abans (WMS 50k → fallback 250k).

**Fitxers modificats:** `automation/report_data.py`, `automation/sections/section3_geologia.py`

**Pendent futur:** Integració automàtica amb vector tiles ICGC 25k (requereix `mapbox-vector-tile` + `shapely` + point-in-polygon + gestió cobertura parcial ~49%)

### Fix 3: Plantilla de materials usa regió equivocada [CRÍTIC]

**Dependent del Fix 1.** Un cop `determine_region()` retorni `valles_penedes`, la plantilla de §3.2 usarà automàticament "coloracions marrons a vermelloses" i "composició silícia" en comptes de "coloracions clars a marró clar" i "carbonatades".

**Però:** La referència G3DT descriu "bretxes amb intercalacions de lutites i gresos vermells" — text molt específic que NO surt de cap plantilla genèrica. La `lithology` ve de `sondeig_extracted.json → layers[].description`. Caldrà verificar que el sondeig extret tingui la litologia correcta.

**Fitxer:** `automation/sections/section3_geologia.py` (MATERIALS_TEMPLATES dict, línia 230+)

### Fix 4: Paràmetres geomecànics (Taula 10) [CRÍTIC] — RESOLT

**Causa:** El pipeline calcula Nb, φ, γ, E automàticament des de N20 amb correlacions estàndard (Peck/Hanson). G3DT usa criteri expert diferent:

| Paràmetre | Pipeline | G3DT Referència | Diferència |
|-----------|----------|-----------------|-----------|
| Nb | 7-R | 17-R | Nb mínim diferent |
| N | 38 | R | G3DT posa R (refús) |
| γ | 2.1 | 2.20 | Densitat roca vs granular |
| c | 0.00 | 1.0 | G3DT assigna cohesió a roca |
| φ | 38° | 35° | Correlació diferent |
| E | 381 | >500 | Mòdul roca vs granular |

**Causa fonamental:** El pipeline tracta tots els materials com a sòl granular. Castellar té **roca** (bretxes, substrat rocós), que requereix paràmetres completament diferents.

**Fonts normatives a integrar:**
- **γ (densitat):** CTE SE-C secció D-27, taula amb pes específic en funció de penetròmetre.
- **N→φ/c/E:** N20 és vàlid per tots els materials (confirmat Eva), però les correlacions actuals (Peck/Hanson) són per sorres. Cal verificar si D-27 dona correlacions alternatives per roca.
- **Nivells:** La mitjana ponderada de N20 per gruix dona el conjunt de paràmetres del nivell. G3DT no calcula per capa sinó per nivell geotècnic.
- **Nb:** El Nb mínim depèn del rang de N20 del nivell sencer (mínim ponderat), no de la lectura individual més baixa.

**Fix proposat (fases):**
1. **Fase A — Lookup D-27:** Implementar taula de propietats de la secció D-27 del CTE. Això donaria γ, K, i possiblement φ per tipus de material.
2. **Fase B — Detecció roca vs sòl:** Si N20 > threshold (p.ex. refús ràpid) + litologia conté "roca/bretxa/substrat" → aplicar paràmetres de roca.
3. **Fase C — Override manual:** Permetre override via `user_data.json` de qualsevol paràmetre geomecànic.

**Fitxers:** `automation/dpsh_extractor.py` (GeotechCorrelations), `automation/sections/section4_conclusions.py` (generate_taula10), `automation/data/` (nova taula D-27)

### Fix 5: Cota relativa vs absoluta [SIGNIFICATIU]

**Causa:** El pipeline usa cota absoluta ICGC MDT (+569.50 msnm). La referència G3DT usa cota relativa al carrer (-4.0 m).

**Anàlisi:** Castellar és un cas especial amb desnivell de ~4m entre carrer i zona d'assaigs. La cota relativa és una observació de camp que NO es pot automatitzar.

**Fix proposat:**
- Afegir camp `cota_relativa_carrer` a `user_data.json` (opcional).
- Si present, usar-lo per a les taules DPSH en comptes de cota ICGC absoluta.
- Si absent, usar cota ICGC com fins ara (millor que res).
- Afegir al wizard: "Cota relativa al carrer (m)? [buit = cota absoluta ICGC]"

**Fitxers:** `automation/user_data_schema.json`, `automation/sections/section2_treballs.py`

### Fix 6: Seccions §4.4 i §4.5 no generades [SIGNIFICATIU]

**Causa:** Les seccions existeixen al codi (`generate_empentes()`, `generate_estabilitat()`) però estan condicionades a flags que no s'activen:
- §4.4 Empentes: requereix `has_retaining_walls=True` o `has_basement=True`
- §4.5 Estabilitat: requereix `is_sloped=True`

**Per Castellar:** El terreny té pendent (20-25° segons referència), però `is_sloped` no es detecta automàticament.

**Fix proposat:**
- L'ICGC MDT pot calcular pendent automàticament (ja existeix `get_slope()` a `icgc_geology.py`).
- Verificar que `get_slope()` s'integra correctament amb `is_sloped` flag.
- Si pendent > 10°, activar §4.5 automàticament.
- Per §4.4: afegir al wizard pregunta sobre murs de contenció.

**Fitxers:** `automation/report_generator.py` (línia 638-656), `automation/sections/section4_conclusions.py`

### Fix 7: Classificació CTE C-0 vs C-1 [SIGNIFICATIU]

**Causa:** El wizard no recull nombre de plantes ni superfície. Sense dades, el classificador CTE assumeix C-0 (mínim). Castellar hauria de ser C-1 (3 habitatges, >100m²).

**Fix:** Assegurar que el wizard recull `num_floors` (o `floor_description` com "Pb+1Pp") i `area_m2`. Amb aquestes dades, `cte_classifier.py` classificarà correctament.

**Fitxers:** skill `g3dt-generar-informe.md` (wizard camps), `automation/cte_classifier.py`

### Fix 8: Dades de client i edificació buides [MENOR]

**Causa:** El wizard no recull nom del client, adreça exacta, ni descripció de l'edificació. Aquests camps surten del plànol de l'arquitecte (que Castellar no té) o es donen manualment.

**Fix:** Afegir camps opcionals al wizard: `client_name`, `street_address`, `building_description`.

### Fix 9: SPT i sulfats no integrats [MENOR]

**Causa:** Les dades SPT i resultats de laboratori no s'extreuen automàticament. El sondeig_extracted.json no inclou dades SPT per Castellar.

**Fix futur:** Ampliar l'extracció de sondeig per incloure SPT. Integrar resultats lab de LAB-SIG.pdf.

## Part 3: Fonts normatives de G3DT (info d'Eva)

### 3a. Permeabilitat — CTE SE-C-120, Taula D.23
- **Problema actual:** Castellar genera K=10⁻³ a 10⁻⁵, referència diu K=10⁻⁵ a 10⁻⁷.
- **Clau:** Compte amb les UNITATS (metres vs centímetres). Possible font dels 2 ordres de magnitud de discrepància.
- **Eva (Bell-Lloc):** K(10⁻² a 10⁻⁴) és correcte per Bell-Lloc (material diferent).
- **Acció:** Buscar Taula D.23 del CTE SE-C, verificar unitats, actualitzar `section3_geologia.py` permeabilitat lookup.

### 3b. Radó — DB secció HS-6
- Ja implementat correctament (ZONA 1/2 via CSN + apèndix B RD 732/2019).
- **Confirmat:** Coincideix amb criteri G3DT.

### 3c. Sísmica — NCSE-02 parte general y de edificación
- Conté llistat de municipis amb acceleració sísmica bàsica.
- **Regla:** Si el municipi del projecte no existeix al llistat → aplicar AB < 0.04g.
- **Acció:** Verificar que `municipal_data.py` implementa aquest fallback correctament.

### 3d. Gamma (densitat) — CTE SE-C, secció D-27
- **Taula amb propietats:** pes específic en funció del penetròmetre.
- **Acció:** Buscar Taula D-27, implementar lookup de γ per tipus de material en comptes de la correlació lineal N→γ actual.

### 3e. Criteri d'1 nivell — Mitjana ponderada
- **Eva:** El criteri d'1 nivell és perquè fan una mitjana ponderada dels valors N20.
- **Interpretació:** Fins i tot si el sondeig mostra capes amb litologies diferents, G3DT pot agrupar-les en 1 sol nivell geotècnic si el comportament mecànic és similar. La "mitjana ponderada" de N20 ponderada per gruix dona un sol conjunt de paràmetres.
- **Indicador de nivells:** Als fulls de camp dels penetròmetres, G3DT marca 1 o 2 colors. 1 color = 1 nivell, 2 colors = 2 nivells.
- **Bell-Lloc:** 1 color al penetròmetre, "Nivell 1" al sondeig → confirma 1 nivell.
- **Acció:** Quan s'extreuen els penetròmetres, detectar canvis de color (si és visible al PDF). Això dona `num_soil_levels` directament.

### 3f. N20 per tots els materials
- **Eva:** N20 era originalment per sorres, però ara s'usa per tots els materials.
- **Impacte:** Validar que les correlacions N20→paràmetres s'apliquen universalment (no només a granulars).

### 3g. Nota sobre directori d'execució
- **Observació:** El run-001 de Castellar es va fer des de `claudecode-job/` (arrel), no des de `clients/g3dt/`. Alguns skills d'extracció no van estar disponibles i es van executar "manualment" (extracció directa amb Python en comptes d'invocar el skill).
- **Decisió:** Les proves de fase 2 sempre s'executaran des de `clients/g3dt/` per assegurar que tots els skills i paths relatius funcionen correctament.
- **Acció:** Documentar al README.md de proves-fase2 que el directori de treball és `clients/g3dt/`.

## Part 4: Ordre d'execució

### Pas 1: Infraestructura (avui)
1. Crear carpeta `proves-fase2/` amb subcarpetes per projecte
2. Guardar comparació Castellar com a `run-001_2026-02-24.md`
3. Copiar `3001621_generated.docx` a la carpeta de proves
4. Crear `README.md`

### Pas 2: Fixes ràpids (alt impacte, poc esforç)
5. **Fix 1** — Normalitzar accents a `determine_region()` (5 línies de codi)
6. **Fix 3** — Verificar que amb Fix 1, les plantilles de materials funcionen
7. Regenerar Castellar i documentar com `run-002`

### Pas 3: Fix ICGC
8. **Fix 2** — Investigar capa 1:25.000 a ICGC WMS
9. Si disponible: implementar query 25k
10. Si no: documentar limitació, afegir camp manual d'override

### Pas 4: Paràmetres geomecànics
11. **Fix 4** — Afegir detecció roca vs sòl
12. Integrar fonts normatives de G3DT quan disponibles
13. Regenerar i documentar com `run-003`

### Pas 5: Seccions condicionals i wizard
14. **Fix 5** — Cota relativa al wizard
15. **Fix 6** — Activar §4.4/§4.5 automàticament
16. **Fix 7** — Classificació CTE amb dades completes
17. Regenerar i documentar com `run-004`

### Pas 6: Repetir cicle amb Rubí, Linyola, Bell-Lloc
18. Generar informes per als 3 projectes restants
19. Comparar amb referències
20. Documentar en les seves carpetes respectives
21. Identificar errors nous → nous fixes → nou cicle

## Verificació

Per cada run:
```bash
# 1. Generar informe (des de clients/g3dt/)
.venv/bin/python -c "
from automation.report_generator import ReportGenerator
from pathlib import Path
project = Path('reference-material/{CARPETA}')
gen = ReportGenerator(str(project), str(project / 'user_data.json'))
result = gen.generate(str(project / '{EXPEDIENT}_generated.docx'))
print('Success:', result.success)
for w in result.warnings: print('WARNING:', w)
for e in result.errors: print('ERROR:', e)
"

# 2. Comparar amb referència (text extraction + diff)
# Usar PyMuPDF per extreure text de la referència PDF
# Comparar secció per secció

# 3. Documentar resultats a proves-fase2/{projecte}/run-NNN.md
```

## Fitxers principals a modificar

| Fitxer | Fix | Canvi |
|--------|-----|-------|
| `automation/icgc_geology.py` | 1, 2 | Normalitzar accents, investigar 25k |
| `automation/dpsh_extractor.py` | 4 | Detecció roca vs sòl |
| `automation/sections/section4_conclusions.py` | 4, 6 | Taula params roca, activar §4.4/4.5 |
| `automation/sections/section2_treballs.py` | 5 | Cota relativa |
| `automation/report_generator.py` | 6 | Integrar slope detection |
| `automation/user_data_schema.json` | 5, 8 | Nous camps |
| `automation/cte_classifier.py` | 7 | Verificar inputs |
| `.claude/commands/g3dt-generar-informe.md` | 7, 8 | Nous camps wizard |
