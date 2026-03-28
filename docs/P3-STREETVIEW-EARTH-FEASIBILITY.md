# P3: ICGC + Mapillary Feasibility Study for Tier B Variables

Created: 2026-03-28
Source: Claude research synthesis

## Overview

To reproduce Eva's site description sections (2.1.1 adjacents, 2.1.2 site condition), use **ICGC as the primary evidence source** and **Mapillary as the street-level enrichment layer**. ICGC is better for parcel geometry, surface condition, vegetation, accesses, enclosure lines, and change over time, while Mapillary is better for façades, fences, gates, visible floor count, street edge condition, and "what you would notice if you were standing there."

**Important:** Google Street View is NOT suitable for automated production pipeline — Google's published guidance prohibits creating data by analyzing or extracting information from Street View images. For automation, ICGC + Mapillary is the cleaner combination.

## Source Roles

The cleanest split is: ICGC answers "what is on each side of the parcel from above," and Mapillary answers "what do those edges look like from the street."

- **ICGC Territorial Orthophoto**: annual coverage, 25 cm pixels in recent years
- **ICGC Local Orthophoto**: 10 cm resolution in urban areas via [WMS](https://catalegs.ide.cat/geonetwork/srv/api/records/orto-local-wms?language=spa)
- **Mapillary API**: image positions, sequences, timestamps, compass angles, thumbnails, detections

| Report statement | Best source | Why |
|---|---|---|
| "Per la part est amb el Carrer…" | Cadastre + ICGC ortho | Street adjacency is best confirmed from parcel geometry and orthophoto continuity. |
| "Parcel·la buida" | ICGC recent ortho + historical ortho | Recent imagery shows current occupation; historical imagery helps avoid mislabeling a cleared or changing lot. |
| "Construcció aïllada de fins a dos plantes" | ICGC + Mapillary | ICGC confirms detached building footprint and yard; Mapillary is the better source for visible floor count. |
| "Entrada a través del carrer existent al sud" | ICGC + Mapillary | ICGC shows likely access opening; Mapillary shows curb cut, gate, or actual street-side entrance condition. |
| "Sense pavimentar, amb vegetació de petita alçada" | ICGC local ortho, optionally IRC | High-resolution orthophoto is the strongest source for bare soil, gravel, paving, and low vegetation patterns. |
| "No presentaven patologies aparents…" | Mapillary or field-only | Orthophoto is usually insufficient for façade pathology; street-level imagery is the only remote source that can approximate that statement. |

## From ICGC

For subsection 2.1.1, extract parcel-side descriptors from a narrow buffer around each boundary segment, not from the whole neighboring parcel. ICGC's territorial product is annual and historical, and its local orthophoto has much finer urban detail, so you can classify each adjacent edge as street frontage, vacant open lot, detached building with yard, party-wall edge, agricultural edge, or service/access strip.

For subsection 2.1.2, use ICGC to infer the solar's visible state: relative level against the street edge, paving versus unpaved cover, low vegetation versus dense vegetation, visible enclosures, internal clear area, and nearby building pattern. ICGC also serves orthophotos by WMS, which makes it practical to automate image requests centered on the parcel and clipped to fixed scales for repeatable feature extraction.

### ICGC Feature Set Per Side

- **Boundary type**: street, neighboring parcel, open edge, uncertain.
- **Edge line evidence**: wall, fence, hedge, curb, none visible.
- **Adjacent occupation**: vacant, building footprint, yard/garden, paved open area, cultivated area.
- **Surface and cover**: bare soil, gravel, asphalt, concrete, mixed, herbaceous vegetation, trees/shrubs.
- **Building relation**: isolated building, attached building, rear yard, side yard, auxiliary structure.
- **Time stability**: unchanged, recently transformed, uncertain, using two or more ICGC years.

### Orthophoto Chips Strategy

Use two scales:
- **Tight chip** (~30–50 m margin): for descriptive writing about the parcel itself
- **Wide chip** (~80–120 m margin): for contextual statements ("in nearby plots there are buildings of similar characteristics")

## With Mapillary

Mapillary should be queried only after you know which parcel sides touch a public street or are visible from one.

### Core Workflow

1. Build a bbox around the parcel or around the bordering street segments.
2. Query `/images` with `bbox`, `fields=id,captured_at,computed_geometry,compass_angle,thumb_1024_url,sequence`.
3. Keep only images within a distance threshold from the street-facing edges, then score them.

### Scoring Rule

- **Distance score**: best if the camera is within 5–20 m of the relevant edge.
- **Facing score**: best if the image compass angle roughly points toward the parcel centroid or toward the boundary midpoint.
- **Recency score**: prefer the newest images, but keep one older image if the newest is occluded.
- **Coverage score**: prefer sequences with 2–4 consecutive images spanning the frontage.

### Mapillary Extraction Targets

- Visible number of floors from the street.
- Façade type, finish, and whether the building is isolated or between party walls.
- Fence type, gate presence, retaining wall, sidewalk condition, curb cut.
- Whether the parcel appears level with the street, slightly below, or behind a raised edge.
- Whether nearby visible façades show obvious cracks, settlement signs, or no obvious external pathology.

## Text Generation

Generate the report from **fixed micro-fields** rather than from a general LLM prompt.

### Data Schema Per Boundary

```
side, adjacency_type, street_name_or_neighbor_class, building_presence,
building_detached, estimated_visible_floors, surface_state, enclosure,
access_presence, vegetation_state, street_relation, nearby_building_pattern,
subsoil_visibility, confidence, evidence_sources
```

### 2.1.1 Adjacents Templates

- `Per la part {side_cat} amb {street_name}.`
- `Per la part {side_cat} amb una parcel·la buida.`
- `Per la part {side_cat} amb una parcel·la amb una construcció aïllada de fins a {n} plantes sobre rasant.`
- `Per la part {side_cat} amb una parcel·la parcialment ocupada per edificació i espai lliure interior.`

### 2.1.2 Site Description Templates (4–6 sentences)

1. **Access**: `L'entrada a la zona d'estudi es realitza a través del carrer existent al {side}.`
2. **Delimitation**: `La parcel·la es troba delimitada per {fences/walls/adjacent closures}.`
3. **Level**: `La parcel·la es troba {a nivell de la rasant / lleugerament per sota / lleugerament per sobre}, aproximadament {x} cm {per sota/per sobre} del carrer.`
4. **Surface**: `El solar es presenta {sense pavimentar / parcialment pavimentat} i amb {vegetació de petita alçada / vegetació dispersa / escassa cobertura vegetal}.`
5. **Surroundings**: `En solars propers s'observen construccions de característiques similars a l'obra projectada.`
6. **Visibility**: `No s'observen afloraments dels materials del subsòl ni a la parcel·la ni a l'entorn proper.`

**Rule**: Each sentence tied to minimum evidence condition. Only say `fins a dos plantes` if Mapillary shows enough façade; only say `uns 15 cm per sota` if curb/grade heuristic available.

## Extraction Logic

### ICGC: Three Passes

1. Intersect subject parcel with adjacent parcel geometries and street centerlines → know which boundary = which neighbor
2. Request orthophoto chips per segment at fixed scale and year
3. Classify visible occupation and edge condition from chips

### Mapillary: One Pass Per Public Boundary

1. Query images along bordering street
2. Rank by angle and distance
3. Keep best 3–5 images
4. Run multimodal model on thumbnails to extract: façade height, enclosure type, gate/access, sidewalk condition, retaining elements, visible pathology cues

### Image Analysis Prompt

> "Describe only what is visible on the parcel frontage and the immediately adjacent parcels; identify fence/wall/gate, visible number of floors, pavement state, vegetation, relative level to street, and whether there are obvious external pathologies; do not infer hidden features or legal land use."

## Reliability Rules

| Confidence | Source | Good for |
|------------|--------|----------|
| **High** | ICGC ortho | Street adjacency, vacant/built classification |
| **Medium** | ICGC + Mapillary | Fence/access/vegetation/level cues |
| **Low-medium** | Mapillary | Floor count, absence of visible pathology |

## API References

- ICGC Orthophoto WMS: https://catalegs.ide.cat/geonetwork/srv/api/records/orto-local-wms?language=spa
- ICGC Local Orthophoto: http://www.icgc.cat/es/Geoinformacion-y-mapas/Datos-y-productos/Imagen/Ortofoto-local
- Mapillary API: https://www.mapillary.com/developer/api-documentation
