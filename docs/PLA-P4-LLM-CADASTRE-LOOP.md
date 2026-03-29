# P4: LLM-in-the-Cadastre-Loop — Parcel Resolution + Corner Streets

Created: 2026-03-29

## Problem Statement

Three Cadastre bugs limit Tier B accuracy:

1. **Wrong parcel (P4a):** DPSH test point coordinates (COORDENADES.txt) may fall on a different parcel than the project. Bell-Lloc: test point 117m from project parcel.
2. **Multi-parcel sites (P4b):** Project spans 2+ parcels but we query one. Bell-Lloc: Eva's 995 m² vs Cadastre 598 m². Also: Linyola (-32%), Anciles (-84%).
3. **Corner streets (P4c):** Parcel at street intersection has one LDT address → same street name for all street-facing sides. Bell-Lloc: south should be "Carrer Antoni Bellet" but gets "Carrer Mestre Ramon Ortiz" (from LDT).

## Architecture

**Key insight:** 80% data-driven, 20% LLM. Pure data approaches first, LLM as safety net.

```
┌──────────────────────────────────────────────────────────┐
│ Phase 2.9: Parcel Resolution (NEW — before adjacents)     │
│                                                            │
│  P4a: Geocoded parcel ALWAYS wins over DPSH coords         │
│  P4b: Area mismatch → shapely merge neighbor parcels       │
│  P4-LLM: Cadastre WMS + plànol → Groq validates merge     │
│                                                            │
│  New: parcel_resolver.py                                   │
│  New: parcel_validator.py (optional LLM)                   │
│  Output: ResolvedParcel (merged polygon, rc14, area)       │
├──────────────────────────────────────────────────────────┤
│ Phase 3: Cadastre adjacents (uses resolved polygon)        │
│                                                            │
│  P4c: Nominatim reverse geocode at street NULL-zone points │
│  Modified: cadastre_adjacents.py                           │
├──────────────────────────────────────────────────────────┤
│ Phase 3.5: Ortho enrichment (uses resolved polygon)        │
│  (unchanged from P3)                                       │
└──────────────────────────────────────────────────────────┘
```

## Implementation Phases

### Phase 1: P4a + P4c (highest impact, simplest)

**P4a — Geocode always wins:**
- In `auto_extractor.py` Phase 3, ensure geocoded parcel overrides DPSH coords for ALL downstream operations (adjacents, ortho enrichment, cadastral area)
- Store `resolved_utm_x/y` in prefills so Phase 3.5 uses correct center
- Clear stale Cadastre cache when address differs from cached coords

**P4c — Nominatim reverse geocode for corner streets:**
- Modify `_probe_from_edge()` in `cadastre_adjacents.py`
- When street detected (NULL zone crossing), record the UTM point in the street
- Convert UTM → lat/lon (pure-Python inverse UTM, already in mapillary_client.py)
- Nominatim reverse: `GET https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&zoom=17`
- Extract `address.road` → use as street name
- Fallback chain: Nominatim > own LDT > neighbor LDT
- Cache results (90 days, same as Cadastre cache)
- Rate limit: 1 req/sec (Nominatim policy). Max 4 calls per project.

**Test projects:**
- **Bell-Lloc (4001612):** P4c should fix adjacent_south from "Mestre Ramon Ortiz" → "Antoni Bellet"
- **Castellar (3001621):** P4c should fix directions (2 street-facing sides)

### Phase 2: P4b (multi-parcel merge)

**New module `parcel_resolver.py`:**
```python
@dataclass
class ResolvedParcel:
    rc14: str
    polygon: list[tuple[float, float]]
    centroid: tuple[float, float]
    area_m2: float
    is_merged: bool
    merged_refs: list[str]
    resolution_method: str    # "dpsh_coords" | "geocode" | "geocode+merge"
    confidence: str
```

**Algorithm:**
1. Get parcel at geocoded coords → polygon, area
2. Get plànol area from prefills (`superficie_parcela_m2`)
3. If |planol_area - cadastre_area| / cadastre_area > 30% → suspect multi-parcel
4. Get neighbor parcels (from Phase 3 probes: refs that share edges)
5. For each neighbor, get polygon via `get_parcel_geometry_utm()`
6. Try `shapely.ops.unary_union()` combinations: our + each neighbor
7. Pick combination where area closest to plànol area (within 15%)
8. Return merged polygon

**Test projects:**
- **Bell-Lloc (4001612):** 598 m² → should merge to ~995 m² (parcels 172+173)
- **Linyola (4001607):** 387 m² → should merge to ~571 m²
- **Anciles (4001679):** 265 m² → should merge to ~1655 m² (may need 2+ neighbors)

### Phase 3: P4-LLM (visual validation)

**New module `parcel_validator.py`:**
- Triggered when: area mismatch > 20% OR geocoded ≠ DPSH parcel
- Downloads Cadastre WMS map: `https://ovc.catastro.meh.es/Cartografia/WMS/ServidorWMS.aspx?SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap&LAYERS=Catastro&SRS=EPSG:25831&BBOX=...&WIDTH=800&HEIGHT=800&FORMAT=image/png`
- Sends Cadastre map + plànol (A.01.pdf page 1) to Groq vision
- Prompt: "Compare Cadastral map vs architect plan. Single parcel? Which parcels merge? Street names per side?"
- Returns validation JSON with confidence
- Cost: ~$0.003 per call, only for ambiguous cases

**Test projects:** Same as Phase 2 (ambiguous cases trigger validation)

## Cost & Performance

| Step | API calls | Cost | Latency |
|------|----------|------|---------|
| P4a | 0 (code logic) | Free | 0s |
| P4c | 1-4 Nominatim | Free | 1-4s (rate limit) |
| P4b | 1-6 Cadastre WFS | Free | 2-3s |
| P4-LLM | 1 Groq vision | $0.003 | 2-3s |

## Expected Impact

| Project | Current Tier B | After P4 (estimated) |
|---------|---------------|---------------------|
| Bell-Lloc | 2/8 (25%) | 5-6/8 (62-75%) |
| Castellar | 0/8 (0%) | 2-3/8 (25-38%) |
| Linyola | 0/7 (0%) | 1-2/7 (14-29%) |
| Overall B | 2/54 (3.7%) | ~12-18/54 (22-33%) |

## Files

| File | Change |
|------|--------|
| `automation/parcel_resolver.py` | **NEW** — Phase 2.9 parcel resolution |
| `automation/parcel_validator.py` | **NEW** — Optional LLM validation |
| `automation/cadastre_adjacents.py` | **MODIFY** — Nominatim street names (P4c) |
| `automation/auto_extractor.py` | **MODIFY** — Wire Phase 2.9, geocode priority (P4a) |
| `web/wizard_service.py` | **MODIFY** — Propagate resolved polygon |
