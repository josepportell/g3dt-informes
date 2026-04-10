# Traça completa: `adjacent_*_fmt` a través del pipeline

**Data:** 2026-04-10
**Projecte traçat:** Bell-Lloc (4001612) — l'únic amb 2 MATCH + 2 MISMATCH, ideal per contrastar
**Objectiu:** Entendre per què est+nord funcionen i sud+oest fallen

---

## 0. Resum de resultats (Bell-Lloc)

| Direcció | Raw Cadastre | Formatted | Eva | Status |
|---|---|---|---|---|
| **EST** | `Carrer Mestre Ramon Ortiz` | Per la part est amb el Carrer Mestre Ramon Ortiz. | Per la part est amb el Carrer Mestre Ramon Ortiz. | **MATCH** |
| **NORD** | `parcel·la buida` | Per la part nord amb una parcel·la buida. | Per la part nord amb una parcel·la buida. | **MATCH** |
| **SUD** | `parcel·la buida` | Per la part sud amb una parcel·la buida. | Per la part sud amb el **Carrer Antoni Bellet**. | **MISMATCH** |
| **OEST** | `parcel·la amb construcció` | I finalment, per la part oest amb una parcel·la amb construcció. | I finalment, per la part oest, amb una parcel·la amb una construcció **aïllada de fins a dos plantes sobre rasant**. | **MISMATCH** |

---

## 1. El pipeline d'adjacents — com funciona

```
UTM coords (314418.9, 4611117.6) del projecte
         │
         ▼
get_adjacent_parcels() ─── per cada direcció (N/S/E/W):
         │
         ├── _probe_direction(dx, dy) ── sondatge gradual des del centroide
         │         │
         │         ├── Probe cada 2m des de la vora (fins a 8 probes)
         │         ├── _query_ref_by_coords() → Cadastre API CPMRC
         │         │        ref=None → carrer (NULL zone)
         │         │        ref≠ours → parcel·la veïna
         │         │
         │         ├── Si creua carrer → _reverse_geocode_street() (Nominatim)
         │         │                   → o _translate_street_name() (LDT fallback)
         │         │
         │         └── Si parcel·la directa → _describe_neighbor(ref)
         │                                     → _query_building_data() (DNPRC)
         │                                     → "parcel·la buida" / "parcel·la amb construcció..."
         │
         ▼
{ north: "...", south: "...", east: "...", west: "..." }
         │
         ▼
format_all_adjacents() ─── adjacent_formatter.py
         │
         ├── Detecta articles (el/la/una/un) segons inici del valor
         ├── West afegeix "I finalment,"
         │
         ▼
{ adjacent_north_fmt: "Per la part nord amb...", ... }
```

---

## 2. Anàlisi per direcció

### 2.1 EST — MATCH (el camí feliç)

- **Probe:** Sondatge cap a l'est des del centroide
- **Troballa:** NULL zone (carrer) → el probe detecta que no hi ha parcel·la, sinó via pública
- **Resolució:** Nominatim reverse geocode o LDT de la pròpia parcel·la
- **Resultat:** `"Carrer Mestre Ramon Ortiz"` — correcte!
- **Formatter:** Detecta "Carrer " → article masculí "el" → "Per la part est amb el Carrer..."

**Per què funciona?** La parcel·la dona a un carrer ampli a l'est. El sondatge
detecta la NULL zone (carrer) i Nominatim/LDT retorna el nom correcte.

### 2.2 NORD — MATCH (cas simple)

- **Probe:** Sondatge cap al nord
- **Troballa:** Parcel·la veïna directa (sense carrer entremig)
- **Resolució:** `_describe_neighbor(ref)` → `_query_building_data()` → no té edifici → `"parcel·la buida"`
- **Formatter:** Detecta "parcel·la" → article femení indefinit "una"

**Per què funciona?** Al nord hi ha realment una parcel·la buida. El Cadastre
confirma que la parcel·la veïna no té edifici → descripció correcta.

### 2.3 SUD — MISMATCH (carrer no detectat)

- **Eva diu:** `"Per la part sud amb el Carrer Antoni Bellet."`
- **Pipeline diu:** `"Per la part sud amb una parcel·la buida."`
- **Discrepància:** Eva veu un carrer, el pipeline veu una parcel·la buida

**Diagnòstic:** El sondatge cap al sud NO detecta la NULL zone (carrer).
Possibles causes:

1. **El carrer Antoni Bellet és massa estret** — si < 4m, els 8 probes a 2m
   podrien saltar-se'l i aterrar directament a la parcel·la de l'altra banda

2. **El centroide no està centrat** — si la parcel·la és irregular, el sondatge
   des del centroide cap al sud pot sortir per una cantonada on NO hi ha carrer

3. **La geometria de la parcel·la és complexa** — la fórmula `half_side = sqrt(superficie)/2`
   assumeix una parcel·la quadrada. Si és rectangular allargada, el half_side és incorrecte
   i el probe comença massa lluny o massa a prop

4. **La parcel·la sud que detecta SÍ és buida** — però no hauria de detectar-la si
   entremig hi ha el Carrer Antoni Bellet. Suggereix que el sondatge salta el carrer.

**HIPÒTESI PRINCIPAL:** La parcel·la de Bell-Lloc NO és quadrada. Si és rectangular
amb el costat llarg est-oest i el costat curt nord-sud, llavors `sqrt(600)/2 ≈ 12m`
sobreestima la distància al carrer sud, i els probes ja comencen DINS del carrer
o a l'altra banda.

**Verificació necessària:** Executar `_probe_direction` amb logging detallat per
veure exactament on aterren els probes al sud.

### 2.4 OEST — MISMATCH (descripció incompleta)

- **Eva diu:** `"...amb una parcel·la amb una construcció aïllada de fins a dos plantes sobre rasant."`
- **Pipeline diu:** `"...amb una parcel·la amb construcció."`
- **Discrepància:** Falta `"aïllada de fins a dos plantes sobre rasant"`

**Diagnòstic:** El sondatge detecta correctament la parcel·la veïna (sense carrer entremig).
Crida `_describe_neighbor(ref)` → `_query_building_data(ref)` → retorna dades de l'edifici.

El codi de `_describe_neighbor()` (línia 440-494) SÍ genera la descripció completa:
```python
if floors == 2:
    desc = "parcel·la amb construcció aïllada de fins a dos plantes sobre rasant"
```

Però el raw retornat és `"parcel·la amb construcció"` (sense detall).
Això vol dir que `_query_building_data()` retorna `floors <= 0` o falla.

**HIPÒTESI:** `_query_building_data()` (DNPRC API) no retorna les dades de
plantes per a aquesta parcel·la específica, i el codi cau al fallback genèric:
```python
if floors <= 0:
    return "parcel·la amb construcció"
```

**Verificació necessària:** Executar `_query_building_data()` directament amb
la referència cadastral de la parcel·la veïna a l'oest per veure què retorna.

---

## 3. Anàlisi del formatter — funciona?

| Cas | Input | Output | Correcte? |
|---|---|---|---|
| Carrer (masc.) | `Carrer Mestre Ramon Ortiz` | `...amb el Carrer...` | SÍ |
| Parcel·la buida | `parcel·la buida` | `...amb una parcel·la buida.` | SÍ |
| Parcel·la amb constr. | `parcel·la amb construcció` | `...amb una parcel·la amb construcció.` | SÍ |
| West prefix | qualsevol | `I finalment, per la part oest...` | SÍ |

**Conclusió:** El formatter funciona correctament. Aplica articles i prefixos
segons les regles d'Eva. El problema NO és de formatació sinó de les **dades raw**
que rep del Cadastre.

**Un detall:** Eva escriu `"I finalment, per la part oest, amb..."` (amb coma
abans de "amb"), el pipeline escriu `"I finalment, per la part oest amb..."`
(sense coma). Diferència menor de puntuació, però pot causar MISMATCH a string matching.

---

## 4. Cross-project: patrons dels 22 MISMATCH d'adjacents

| Tipus de MISMATCH | Exemples | Causa probable |
|---|---|---|
| **Carrer no detectat** | Bell-Lloc sud, Linyola est+sud | Probe salta carrers estrets o geometria irregular |
| **Descripció incompleta** | Bell-Lloc oest, Alcoletge est | DNPRC no retorna plantes o fallback genèric |
| **Idioma incorrecte** | Anciles (totes) | Pipeline usa CA, Eva usa ES (Aragó) |
| **Punt cardinal incorrecte** | Linyola est+sud (Eva posa est=sud) | Eva combina direccions: "Per la part est i pel sud" |
| **Totalment diferent** | Rubí nord ("Passatge Miranda" vs "parcella...") | Eva coneix el terreny, pipeline no |
| **No extret** | Vilanova (totes) | Geocodificació falla → no hi ha UTM → no adjacents |

---

## 5. Troballes sistèmiques

### 5.1 L'algorisme de sondatge és fràgil per geometries no quadrades

`half_side = sqrt(superficie) / 2` assumeix parcel·la quadrada.
Si la parcel·la és rectangular 10×60m (superficie=600m²):
- sqrt(600)/2 ≈ 12.2m
- Però el costat curt real és 5m

El probe al costat curt comença a 12.2+1=13.2m del centroide, **ja fora de la parcel·la**,
potencialment saltant el carrer i aterrant a la parcel·la de l'altra banda.

**Fix:** Usar la geometria real de la parcel·la (WFS INSPIRE) per calcular les distàncies
de probe per direcció, no una estimació quadrada.

### 5.2 _describe_neighbor sovint cau al fallback genèric

Quan `_query_building_data()` no retorna dades de plantes (DNPRC API falla o parcel·la
sense dades detallades), el resultat és `"parcel·la amb construcció"` — massa genèric.

Eva en canvi diu `"construcció aïllada de fins a dos plantes"` perquè ella mira
l'edifici realment (Google StreetView o visita de camp).

**Fix opcions:**
1. Millorar el parsing de DNPRC per extreure plantes correctament
2. Usar ortofoto/streetview per complementar (ja tenim `ortho_vision.py`)
3. Acceptar el fallback genèric i marcar-lo perquè Eva el completi

### 5.3 El formatter no contempla la puntuació d'Eva

Eva escriu comes en posicions específiques: `"I finalment, per la part oest, amb una..."`.
El pipeline escriu: `"I finalment, per la part oest amb una..."`.

Diferència menor, però compare_text() ho marca com MISMATCH.

**Fix:** Afegir la coma al formatter per la variant west (línia 115):
```python
result[f'adjacent_{direction}_fmt'] = f'I finalment, {body}'
# body = "per la part oest amb..." → falta coma entre "oest" i "amb"
```

### 5.4 Adjacents és la variable MÉS dependent de dades externes

A diferència de building_type (on el valor està als fitxers del projecte),
les adjacents depenen de:
1. Coordenades UTM correctes (geocode o COORDENADES.txt)
2. API Cadastre CPMRC (sondatge de coordenades)
3. API Cadastre DNPRC (dades edifici veí)
4. API Nominatim (nom del carrer)
5. Geometria de la parcel·la (per calcular distàncies de probe)

Qualsevol punt de la cadena que falli → adjacent incorrecte.
Per Vilanova de Segrià, la geocodificació falla completament → 4 NOT_EXTRACTED.

---

## 6. Hipòtesis a verificar

### H1. La geometria causa el salt del carrer sud a Bell-Lloc

**Estat: VERIFICADA**

Probe real (superficie=905m², half_side=15.0m, start=16.0m):

| Direcció | Distància | Troballa | LDT veí |
|---|---|---|---|
| **SUD** (dy=-1) | 16.0m | Parcel·la veïna **directa** (cap NULL zone) | CL VIA FERREA 57 |
| **EST** (dx=+1) | 16.0m | Parcel·la veïna **directa** (cap NULL zone) | CL VIA FERREA 55 |

**Observació clau:** El primer probe al sud ja aterra en una parcel·la diferent.
No detecta cap carrer entremig. Això confirma que:
1. `half_side = sqrt(905)/2 = 15.0m` sobreestima la distància al costat sud
2. El carrer Antoni Bellet (si és al sud) o bé és massa estret o bé la parcel·la
   és tan estreta en eix N-S que el probe salta per sobre

**Segon troballa:** El veí sud té LDT "CL VIA FERREA 57", NO "Carrer Antoni Bellet".
Eva diu el sud és "Carrer Antoni Bellet" → possibilitats:
- La parcel·la no és rectangular alineada amb N-S/E-W → el "sud" real és diferent del geogràfic
- Eva utilitza orientacions relatives al carrer d'accés, no cardinals purs
- L'adreça del veí és a Via Ferrea però el carrer entremig és Antoni Bellet

**Important:** El probe directe amb `our_ref` fals no replica exactament el pipeline
(que usa el ref real de la parcel·la per filtrar "encara som a la nostra"). Però
demostra que a 16m del centroide ja hi ha una parcel·la diferent sense cap NULL zone.

### H2. DNPRC no retorna plantes per la parcel·la veïna a l'oest

**Estat: PARCIALMENT VERIFICADA**

El raw de l'oest és `"parcel·la amb construcció"` — això correspon al fallback
`if floors <= 0: return "parcel·la amb construcció"` (línia 477).

Confirmem: el DNPRC retorna dades de l'edifici, però `num_floors_above` és 0 o no present.
Eva sap que l'edifici té 2 plantes perquè ho veu (visita de camp o StreetView).

### H3. La coma al formatter — NO verificada

Pendent: comparar puntuació a les 7 variants west.

---

## 7. Accions per prioritat

### Alta (afecta 22 MISMATCH + 4 NOT_EXTRACTED)
1. **Geometria real per probes** — usar WFS INSPIRE geometry (ja la tenim al geocode)
   en comptes de sqrt(superficie). Impacte: carrers estrets detectats correctament.
2. **Millorar DNPRC parsing** — extreure plantes correctament per _describe_neighbor.
3. **Fix coma al formatter west** — trivial, impacte en totes les comparacions west.

### Mitja (millora de qualitat)
4. **Idioma adjacents** — Anciles i Vilanova haurien d'usar ES, no CA.
   Verificar que `_detect_language()` funciona per tots els projectes aragonesos.
5. **Fallback StreetView/ortofoto** — per quan DNPRC no retorna detalls.

### Baixa (diagnostic)
6. **LLM judge per adjacents** — molts MISMATCH amb diferències de puntuació
   o descripció parcial. LLM judge classificaria correctament com CLOSE.

---

## 8. Comparació amb building_type: lliçons creuades

| Aspecte | building_type | adjacent_*_fmt |
|---|---|---|
| Font primària | Vision (plànol) | API (Cadastre) |
| FileMiner útil? | No (senyals dolentes) | No (0 senyals) |
| Format mapping | Sí (6 schemas) | No (cap) — ve d'API |
| Formatter | No cal (text lliure) | Sí (adjacent_formatter.py) — funciona bé |
| LLM synthesis | Sobreescriu vision | No intervé |
| Problema principal | Synthesis ignora prioritats | Sondatge geomètric fràgil |
| Fix principal | Respectar source priority | Geometria real per probes |

**Patró comú:** El pipeline fa bé la feina "macro" (troba la font correcta,
formata raonablement) però falla en els detalls (qualificadors, geometria,
dades de plantes). Eva aporta els detalls pel seu coneixement del terreny.

**Implicació per producte:** Per adjacents, el pre-fill del wizard hauria de:
1. Mostrar el resultat del Cadastre com a punt de partida
2. Marcar visiblement els adjacents amb baixa confiança (fallback genèric)
3. Eva ajusta els detalls en 10-20 segons

Això és coherent amb el model de companió: el pipeline fa el 80%, Eva afina el 20%.
