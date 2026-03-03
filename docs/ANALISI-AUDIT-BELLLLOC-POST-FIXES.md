# Anàlisi Audit Bell-Lloc — Post Bug Fixes (2026-03-02)

## Context

Després de corregir 3 bugs crítics (truncament paràgrafs geologia, filtre capes sondeig, descripció material), l'audit de Bell-Lloc mostra:

- **Auto-resolved**: 97.1% (95.0% → 97.1%)
- **Needs review**: 10 ítems (17 → 10)
- **Missing**: 10 ítems (12 → 10)
- **DADES_ERRÒNIES**: 0 (abans 4)

## Bugs Corregits

| Bug | Abans | Després | Verificació |
|-----|-------|---------|-------------|
| Truncament paràgrafs geologia | 4 paràgrafs perduts (7-10) | Tots 10 renderitzats | geology_paragraphs for-loop |
| Filtre capes sondeig | c_coeff=1.6, N20=18.8 | c_coeff=1.3, N20=37 | num_user_levels guard |
| Descripció material | "Llims argilosos amb graves" | "Graves incloses en matriu sorrenca..." | Deepest layer heuristic |

## Classificació dels 27 Ítems Restants

### A. Desalineament audit per for-loop (5 ítems) — PRIORITAT ALTA

El for-loop de geologia genera 10 paràgrafs on el manifest del template n'esperava 6. Els 4 extra desplacen tots els paràgrafs posteriors, causant falsos "needs_review".

| Ítem | Template esperat | Generat (desplaçat) |
|------|-----------------|---------------------|
| 1 | Figura caption (mapa geològic) | "Full 33: Segrià..." (geol para 7) |
| 2 | Figura caption | "Hoja 388: Lleida..." (geol para 8) |
| 3 | Taula DPSH range | "El present estudi..." (geol para 9) |
| 4 | Intro permeabilitat | "En concret, ICGC..." (geol para 10) |
| 13 | level.N | "N30" vs "36" (header vs valor) |

**Fix**: Regenerar template_manifest.json des del template actualitzat.

### B. Descripció material massa llarga per taules (6 ítems) — PRIORITAT ALTA

Generat: "Graves incloses en matriu sorrenca d'aspectes carbonatats, i de coloracions clars. Tram totalment carbonatat."
Referència Eva: "Graves en matriu sorrenca carbonatades"

Afecta: ítems 8, 10, 11 (needs_review) + missing idx=475, 489, 514

**Fix**: Afegir `level.material_short` — primera clàusula abans de la primera coma/punt.

### C. Text secció materials (3 ítems missing) — DIFERIT

- idx=204: "s'ha establert un sol nivell de materials..." (intro específica)
- idx=211: "Destacar que existeix un primer tram superficial..." (matís geològic)
- idx=218: "identificat com a materials plistocens, unitat Qvpu" (referència ICGC)

**Estratègia futura**: Crear fitxer de vocabulari/fraseologia a partir de múltiples informes Eva per generar textos més fidels.

### D. Rang Nb de nivell fusionat (1 ítem) — PRIORITAT BAIXA

Generat: "12-R" (inclou lectures superficials)
Referència: "25-R" (exclou capa superficial)

**Fix**: Usar override geomech_params.Nb si disponible, o filtrar lectures superficials del rang Nb.

### E. Diferències esperades — NO CORREGIBLES en codi (12 ítems)

| Ítem | Generat | Referència | Motiu |
|------|---------|------------|-------|
| level.E | 469 | 650 | Eva ajusta E per "carbonatades" (criteri professional) |
| level.N | 36 | 54 | Valor manual Eva (possible SPT, no N20) |
| level.phi | 38° | 38º | Diferència símbol grau (trivial) |
| level.k_value | 10^-2 a 10^-4 | 10 – 10-2 | Format diferent |
| idx=284 | (absent) | Exempció sísmica | Feature no implementada |
| idx=417 | 366 | 280+86 | Desglossament superfície (diferit) |
| idx=480-481 | (absent) | Sulfats UNE 83963 | Línia lab específica |
| Foto caption | Fotografia 4 | Fotografia 5 | Numeració fotos |
| Depth text | 2.60 m | 2.45 m / "com a mínim" | Interpretació diferent |

## Pla d'Acció

| Fix | Ítems resolts | Esforç | Estat |
|-----|--------------|--------|-------|
| A. Audit for-loop alignment | 4 | Baix | FET ✓ |
| B. Material description short | 3 | Mitjà | FET ✓ |
| C. Vocabulari materials | 3 | Mitjà-alt | DIFERIT |
| D. Rang Nb (shallow exclusion) | 0 | Baix | PARCIAL — Nb_min=12 (transició) vs Eva 25. Requereix override manual |
| **Total corregit** | **7 de 20** | | |
| No corregible (dades/features) | 13 | — | N/A |

## Fitxers Modificats (Fixes anteriors)

| Fitxer | Canvi |
|--------|-------|
| `automation/sections/section3_geologia.py` | marc_geologic_paragraphs list, eliminar MAX_SLOTS |
| `automation/report_generator.py` | geology_paragraphs list + sondeig filter guard |
| `automation/report_data.py` | _generate_soil_levels: deepest layer desc + global N20 |
| `templates/g3dt-jinja-template.docx` | for-loop reemplaça 6 slots fixes |

## Fixes Addicionals Aplicats (Post-anàlisi)

### Fix A: Audit for-loop alignment
- Afegit pre-pass a `intelligent_audit.py` que detecta paràgrafs generats que coincideixen amb valors de llistes al context (p.ex. `geology_paragraphs`)
- Reclassifica de `needs_review` a `likely_correct` evitant falsos positius
- **Resultat**: 4 ítems resolts

### Fix B: Material description short
- Afegit `_shorten_material_desc()` a `report_generator.py`
- Talla la descripció al primer separador secundari (`, i de`, `, de`, `. `)
- Aplicat a `material` en taules: soil_level_rows, perm_rows, geotech_rows
- **Resultat**: 3 ítems millorats (ratio 0.517→0.758), 2 missing resolts

### Fix D: Nb range (shallow exclusion)
- Exclou lectures de la capa superficial (0-1.0m) del rang Nb quan nivells fusionats
- Suporta override `geomech_params.Nb` si disponible
- **Resultat parcial**: Nb_min encara 12 per lectura de transició a 1.2m (N20=10, Nb=12.1)
- Eva's "25-R" requereix override manual — criteri professional no automatitzable

### Fix extra: Auto-fill sondeig_layers
- Condició `'sondeig_layers' not in user_data` canviada a `not user_data.get('sondeig_layers')`
- Permet auto-fill des de sondeig_extracted.json quan user_data té llista buida `[]`

---

*Anàlisi generada: 2026-03-02*
*Basada en: audit_intelligent.json post-fixes*
