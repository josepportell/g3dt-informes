# Pla de Millora: Parcel·les Adjacents (Secció 2.1.1)

Data: 2026-03-15
Branca: `improve/adjacents-section-2.1.1`
Commit: `66c1be2`

## Estat

| Fase | Estat | Commit |
|------|-------|--------|
| Fase 2: Neteja noms de carrer | ✅ Implementada | `66c1be2` |
| Fase 1: Sondeig per geometria | ✅ Implementada | `66c1be2` |
| Fase 3: DNPRC edificació veïna | ✅ Implementada | `66c1be2` |
| Fase 4: Cross-ref plànol | ❌ Descartada | — |

## Problema

La secció 2.1.1 descriu què limita amb la parcel·la d'estudi en cada direcció cardinal. Actualment el sistema genera descripcions pobres comparades amb el que Eva escriu manualment.

### Generat (incorrecte)
```
La parcel·la objecte d'estudi es situa al sud-oest del municipi de Bell-Lloc4,
pren una morfologia rectangular, i limita:
  • Per la part nord amb el Carrer Antoni Bellet I Perez Bell-Lloc D'Urgell.
  • Per la part sud amb desconegut.
  • Per la part est amb una parcel·la veïna.
  • I finalment, per la part oest amb una parcel·la veïna.
```

### Referència d'Eva (correcte)
```
La parcel·la objecte d'estudi es situa al oest del municipi de Bell-Lloc d'Urgell,
pren una morfologia rectangular i limita:
  • Per la part est amb el Carrer Mestre Ramon Ortiz.
  • Per la part sud amb el Carrer Antoni Bellet.
  • Per la part nord amb una parcel·la buida.
  • I finalment, per la part oest, amb una parcel·la amb una construcció aïllada
    de fins a dos plantes sobre rasant.
```

## Causes Arrel

| # | Causa | Efecte visible |
|---|-------|---------------|
| 1 | Sondeig des del centroide amb sqrt(àrea)/2 assumint parcel·la quadrada | Direccions incorrectes (nord↔sud invertit) |
| 2 | LDT del Cadastre mal netejat | "I Perez Bell-Lloc D'Urgell" brut al nom del carrer |
| 3 | Cap informació de l'edificació veïna | "parcel·la veïna" genèric, sense descripció |

## Arquitectura Actual

```
auto_extractor.py  _phase3_adjacents()
        ↓
cadastre_adjacents.py  get_adjacent_parcels(utm_x, utm_y, superficie)
        ↓
  Per cada direcció (N/S/E/O):
    _probe_direction(centroide, dx, dy, sqrt(area)/2)
        ↓
    _query_ref_by_coords() → ref + LDT
        ↓
    Si ref==NULL → carrer → _translate_street_name(LDT)
    Si ref!=nostre → "parcel·la veïna"
        ↓
  Resultat: {north: "...", south: "...", east: "...", west: "..."}
```

---

## Fases d'Implementació

### Fase 2: Neteja de Noms de Carrer (la més simple, impacte visual immediat)

**Fitxer:** `automation/cadastre_adjacents.py` — funció `_translate_street_name()`

**Problemes actuals:**
- Regex `r'\s+\d+\s+[A-Z].*$'` no captura tots els formats de municipi
- `.title()` capitalitza "I" → hauria de ser "i" (conjunció catalana)
- "Y" castellà no es tradueix a "i" català
- Noms castellans (ANTONIO → Antoni) no es tradueixen
- Eva escurça els cognoms dobles ("Antoni Bellet i Perez" → "Antoni Bellet")

**Canvis:**

1. **Paràmetre `municipality`** opcional a `_translate_street_name()` per eliminar-lo explícitament del string
2. **Post-processament de conjuncions/preposicions** després de `.title()`:
   ```python
   CATALAN_LOWERCASE_WORDS = {'I', 'De', 'Del', "D'", 'La', 'El', 'Les', 'Els'}
   ```
   Només s'aplica quan NO és la primera paraula.
3. **Traducció "Y" → "i"** (castellà → català en cognoms)
4. **Diccionari de noms propis** castellà → català:
   ```python
   CASTILIAN_TO_CATALAN_NAMES = {
       'ANTONIO': 'Antoni', 'FRANCISCO': 'Francesc', 'JOSE': 'Josep',
       'JUAN': 'Joan', 'PEDRO': 'Pere', 'MIGUEL': 'Miquel',
       'JAIME': 'Jaume', 'JORGE': 'Jordi', 'LUIS': 'Lluís',
   }
   ```
5. **Escurçament de cognoms** (opt-in, default True): si el nom conté "i" + cognom al final, truncar-lo.
   Heurística: si després del tipus de via hi ha ≥4 paraules i la penúltima-o-antepenúltima és "i", tallar allà.

**Tests unitaris:**
| Input LDT | Output esperat |
|-----------|---------------|
| `"CALLE ANTONIO BELLET Y PEREZ 0005 BELL-LLOC D'URGELL (LLEIDA)"` | `"Carrer Antoni Bellet"` |
| `"CL MESTRE RAMON ORTIZ"` | `"Carrer Mestre Ramon Ortiz"` |
| `"AVENIDA CATALUNYA 15 RUBI (BARCELONA)"` | `"Avinguda Catalunya"` |
| `"CAMINO DE LA FONT"` | `"Camí de la Font"` |

---

### Fase 1: Sondeig Basat en Geometria del Polígon (la més impactant per correcció)

**Fitxer:** `automation/cadastre_adjacents.py`

**Problema:** Sondejar des del centroide + `sqrt(àrea)/2` assumeix parcel·la quadrada. Parcel·les reals són irregulars → les sondes surten per la direcció equivocada.

**Solució:** Utilitzar el polígon WFS (ja tenim `get_parcel_geometry_utm(rc14)`) per sondejar des del punt mig de cada aresta cap a fora.

**Noves funcions:**

1. **`_classify_edges_by_direction(polygon) -> dict[str, list]`**
   - Per cada aresta del polígon, calcula el vector normal exterior (perpendicular a l'aresta, apuntant fora del centroide)
   - Classifica per direcció cardinal: si `|ny| > |nx|` i `ny > 0` → "north", etc.
   - Per cada direcció, selecciona l'aresta amb la projecció més llarga (la més representativa)
   - Retorna `{north: [(midpoint, normal), ...], ...}`

2. **`_probe_from_edge(midpoint, normal, our_ref, max_distance=30, step=2) -> str`**
   - Substitueix `_probe_direction()` per la via geomètrica
   - Comença a `midpoint + normal * 1m` (just fora del límit)
   - Sondeja cap a fora seguint el vector normal
   - Mateixa lògica de detecció: street (NULL) vs neighbor (ref diferent)

3. **Modificació de `get_adjacent_parcels()`**
   - Nou paràmetre opcional `rc14: str | None = None`
   - Si `rc14` proporcionat → obté polígon via WFS → sondeig per arestes
   - Si no → fallback al mètode actual (centroide)

**Versionat de cache:** Afegir `_v2` al hash de la clau de cache per invalidar resultats antics.

**Dependència:** Necessita el `rc14` (referència cadastral). Ve de:
- `user_data.json` camp `cadastral_ref`
- `auto_extractor.py` el calcula a `_phase3_cadastral_area()`
- Disponible després de geocodificació

---

### Fase 3: Descripció d'Edificació Veïna via DNPRC (funcionalitat nova)

**Fitxer:** `automation/cadastre_adjacents.py`

**Problema:** Quan trobem una parcel·la veïna directa (sense carrer entremig), retornem `"parcel·la veïna"` sense cap descripció. Eva escriu coses com "parcel·la amb una construcció aïllada de fins a dos plantes sobre rasant".

**API:** Cadastre `Consulta_DNPRC`
- URL: `https://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/OVCCallejero.asmx/Consulta_DNPRC`
- Paràmetres: `Provincia`, `Municipio`, `RC`
- Retorna XML amb:
  - `<lcons>` → pisos: `<stl>` (SUELO/PLANTA/SOTANO), `<cpt>` (superfície per planta)
  - `<debi><luso>` → ús primari (RESIDENCIAL, INDUSTRIAL, AGRARIO, ALMACEN...)
  - `<sfc>` → superfície total construïda

**Noves funcions:**

1. **`_query_building_data(ref: str) -> dict | None`**
   ```python
   # Retorna:
   {
       'num_floors_above': int,   # PLANTA + SUELO
       'num_floors_below': int,   # SOTANO
       'total_built_m2': float,
       'primary_use': str,        # 'RESIDENCIAL', 'INDUSTRIAL', etc.
       'has_building': bool,
   }
   ```

2. **`_describe_neighbor(ref: str) -> str`**
   - Crida `_query_building_data(ref)`
   - Genera descripció en català:

   | Condició | Descripció generada |
   |----------|-------------------|
   | `has_building=False` | `"parcel·la buida"` |
   | 1 planta | `"parcel·la amb construcció aïllada d'una planta sobre rasant"` |
   | 2+ plantes | `"parcel·la amb construcció aïllada de fins a {n} plantes sobre rasant"` |
   | Amb soterrani | append `" i soterrani"` |
   | INDUSTRIAL | `"nau industrial"` |
   | AGRARIO | `"terreny agrícola"` |

   - Fallback si l'API falla: `"parcel·la veïna"` (comportament actual)

3. **Modificació de `_probe_direction()` / `_probe_from_edge()`**:
   - Quan es detecta un veí directe (sense carrer): cridar `_describe_neighbor(ref)` en lloc de retornar `"parcel·la veïna"`.

**Rate limiting:** 1 crida DNPRC addicional per veí trobat. Pitjor cas: 4 crides extra. Utilitza el mateix `_fetch_xml()` amb retry.

**Cache:** Incloure dades DNPRC dins la cache d'adjacents existent.

---

### ~~Fase 4: Referència Creuada amb Plànol~~ (descartada)

**Motiu de descart:** Les fases 1-3 ja resolen els problemes principals. La cross-referència amb plànol afegiria valor marginal perquè:
1. `planol_extracted.json` només existeix després que el pipeline de visió s'executi al wizard d'Eva (no disponible durant auto-extracció)
2. Eva ja veu `street_address` als prefills del wizard i pot verificar manualment
3. La geometria WFS (Fase 1) ja corregeix les direccions, que era el problema principal

## Què Seguirà Necessitant Revisió Manual d'Eva

| Aspecte | Per què no és automatitzable |
|---------|---------------------------|
| Estat de parcel·les buides | "vegetació petita alçada", "pavimentada" → requereix visita de camp |
| Detalls qualitatius | "construccions similars" → observació visual |
| Forma de la parcel·la | "rectangular" → podria automatitzar-se amb anàlisi del polígon (futur) |
| Posició dins el municipi | "est", "oest" → podria automatitzar-se amb centroide del municipi (futur) |
| Infraestructures no cadastrals | Vies de tren, rius, camins agrícoles |

Les badges de font al wizard (blau=auto, verd=user) indicaran correctament què ve de l'API i què ha editat Eva.

## Fitxers Modificats

| Fitxer | Canvis |
|--------|--------|
| `automation/cadastre_adjacents.py` | Fases 1, 2, 3: geometria, neteja noms, DNPRC (+485 línies) |
| `automation/auto_extractor.py` | Passa `rc14` i `municipality` a adjacents |
| `automation/report_generator.py` | Passa `rc14` i `municipality` al fallback d'adjacents |

Fitxers que NO va caldre tocar:
- `section2_treballs.py` — ja renderitza el text correctament, les millores són a l'input
- `report_data.py` — estructura `adjacent_parcels: dict` no canvia
- `review.html` — els 4 camps del wizard no canvien
