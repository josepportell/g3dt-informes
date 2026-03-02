# Procediment: Obtenir coordenades UTM per a projectes sense GPS

Quan un projecte no té COORDENADES.txt (GPS de camp), podem derivar coordenades
aproximades a partir de l'adreça del projecte usant APIs públiques.

## Dades necessàries

- Adreça de l'obra (carrer, número, municipi)
- Número de punts d'assaig (P-1, P-2, S-1, etc.)
- Cota de referència del report (per validar)

## Pas 1: Geocodificar l'adreça (Nominatim)

```python
import urllib.request, urllib.parse, json

def nominatim_geocode(address):
    url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(address)}&format=json&limit=1"
    req = urllib.request.Request(url, headers={"User-Agent": "G3DT/1.0"})
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read())
    if data:
        return float(data[0]["lat"]), float(data[0]["lon"])
    return None, None
```

**Nota:** Nominatim usa noms OSM, que poden diferir dels oficials (ex: "Passeig de la Miranda" vs "Carrer de la Miranda"). Provar variacions si no troba.

## Pas 2: Trobar la parcel·la cadastral (Cadastre OVC API)

L'adreça geocodificada pot caure al carrer (sense parcel·la). Cal fer una cerca en graella:

```python
import xml.etree.ElementTree as ET

def cadastre_rccoor(lon, lat):
    url = (f"https://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/"
           f"OVCCoordenadas.asmx/Consulta_RCCOOR?SRS=EPSG:4326"
           f"&Coordenada_X={lon}&Coordenada_Y={lat}")
    req = urllib.request.Request(url, headers={"User-Agent": "G3DT/1.0"})
    resp = urllib.request.urlopen(req, timeout=15)
    root = ET.fromstring(resp.read().decode())
    ns = {"c": "http://www.catastro.meh.es/"}
    rc1 = root.find(".//c:pc1", ns)
    rc2 = root.find(".//c:pc2", ns)
    ldt = root.find(".//c:ldt", ns)
    if rc1 is not None:
        return {
            "rc": (rc1.text or "") + (rc2.text or ""),
            "address": ldt.text if ldt is not None else "",
        }
    return None

# Cerca en graella al voltant del punt geocodificat
for dlat in [x*0.0002 for x in range(-8, 9)]:
    for dlon in [x*0.0002 for x in range(-8, 9)]:
        result = cadastre_rccoor(lon+dlon, lat+dlat)
        if result and "NOM_CARRER" in result["address"] and "NUMERO" in result["address"]:
            # Parcel·la trobada!
            break
```

**Clau:** La resposta inclou l'adreça cadastral completa (ex: "CL MIRANDA 39 PARC. 6-105 B RUBI (BARCELONA)"). Comparar amb l'adreça del report.

## Pas 3: Obtenir geometria de la parcel·la (INSPIRE WFS)

```python
def get_parcel_geometry(rc14):
    """rc14 = 14 chars de la referència cadastral (amb lletra de control)."""
    url = (f"https://ovc.catastro.meh.es/INSPIRE/wfsCP.aspx?"
           f"service=WFS&version=2.0.0&request=GetFeature"
           f"&StoredQuery_id=GetParcel&REFCAT={rc14}&srsname=EPSG:25831")
    req = urllib.request.Request(url, headers={"User-Agent": "G3DT/1.0"})
    resp = urllib.request.urlopen(req, timeout=15)
    root = ET.fromstring(resp.read().decode())
    for elem in root.iter():
        if "posList" in elem.tag:
            vals = elem.text.strip().split()
            return [(float(vals[i]), float(vals[i+1])) for i in range(0, len(vals), 2)]
    return []
```

**Important:** REFCAT ha de ser exactament 14 caràcters. El resultat és un polígon en EPSG:25831 (UTM zona 31N).

## Pas 4: Distribuir punts d'assaig dins la parcel·la

- Calcular centroide i extensió del polígon
- Col·locar punts amb 7-12m d'espaiament (típic de camp)
- Per parcel·les allargades: distribuir al llarg de l'eix principal
- Per parcel·les quadrades: distribució en triangle o línia

## Pas 5: Obtenir elevació (ICGC MDT 2m)

```python
from automation.icgc_geology import get_elevation
z = get_elevation(utm_x, utm_y)  # EPSG:25831
```

**Validació:** Comparar Z obtingut amb la cota_referencia del report. Tolerància: ±3m.

## Pas 6: Generar COORDENADES.txt

Format (idèntic al de Castellar):
```
Coordenades UTM (X);(Y);(Z);
P-1
314487.0 ; 4611157.0 ; 199.2

P-2
314497.0 ; 4611158.0 ; 199.3
```

Ubicació: `reference-material/{expedient}/ANNEXES/ALTRES/COORDENADES.txt`

## Validació creuada

| Check | Font | Tolerància |
|-------|------|-----------|
| Elevació Z vs cota report | ICGC MDT vs PDF | ±3m |
| Adreça cadastral vs report | Cadastre OVC vs portada | Coincidència carrer+número |
| Punts dins polígon | INSPIRE WFS | Visual |
| Espaiament punts | 7-12m entre consecutius | Típic camp G3DT |

## APIs usades

| API | URL base | SRS | Nota |
|-----|----------|-----|------|
| Nominatim (OSM) | nominatim.openstreetmap.org/search | WGS84 | Geocodificació adreça→lat/lon |
| Cadastre OVC | ovc.catastro.meh.es/.../OVCCoordenadas.asmx | EPSG:4326 | RC des de coordenades |
| Cadastre INSPIRE WFS | ovc.catastro.meh.es/INSPIRE/wfsCP.aspx | EPSG:25831 | Geometria parcel·la |
| ICGC MDT 2m | geoserveis.icgc.cat/icgc_mdt2m/wms/service | EPSG:25831 | Elevació |

## Limitacions

- **No substitueix GPS de camp.** Les coordenades són aproximades (parcel·la, no punt exacte).
- **Espaiament fabricat.** La distribució de punts dins la parcel·la és estimada, no mesurada.
- **Nominatim pot fallar** amb noms de carrers catalans. Provar variacions (CL/Carrer/Passeig).
- **Cadastre grid search necessari.** El punt geocodificat sol caure al carrer, cal buscar la parcel·la amb offsets.
