# Reference Extractor: Enginyeria Inversa dels Informes d'Eva

**Data:** 2026-04-05
**Fitxer:** `automation/reference_extractor.py`

---

## Que fa

Extreu valors estructurats (~30-37 variables per projecte) dels informes `.doc`/`.docx` reals d'Eva, guardant-los com a JSON amb **posicio exacta** (paragraf, taula-fila-columna) per a comparacio amb el pipeline.

## Per que es important

Els informes reals d'Eva son la referencia definitiva. Fins ara, la comparacio es feia via LLM (`docs/benchmarks/`) sense posicions. Ara tenim extraccio determinista amb coordenades de document, reutilitzable per a qualsevol comparacio futura.

## Com funciona

### Estrategia: extraccio guiada per plantilla

La plantilla Jinja (`templates/g3dt-jinja-template.docx`) defineix ON apareix cada variable. L'extractor:

1. **Converteix `.doc` → `.docx`** via LibreOffice (headless)
2. **Carrega l'estructura de la plantilla** — 489 paragrafs cos + 162 paragrafs taula, 123 amb variables
3. **Carrega els paragrafs de referencia** de l'informe d'Eva
4. **Alinea** cada paragraf de plantilla amb el corresponent de referencia (similitud de text >= 50%)
5. **Extreu** la diferencia entre el text estatic de la plantilla i el text de referencia = el valor de la variable
6. **Per a taules**: mapeja coordenades de plantilla → coordenades de referencia via fingerprinting de capçaleres

### Tres metodes d'extraccio

| Metode | Que fa | Confianca | Exemples |
|--------|--------|-----------|----------|
| `paragraph_single` | Paragraf amb 1 sola variable: prefix/sufix | 0.60-0.95 | client, qa_value, data_camp_text |
| `table_cell` | Cel·la de taula per coordenada directa | 0.95 | plantes, cte_edificacio, sulfate_value |
| `loop_table` | Taules amb files repetides (for loops) | 0.85 | geotech_rows, dpsh_tests, seismic_rows |

### Taules conegudes de la plantilla

| Taula | Contingut | Metode | Columnes |
|-------|-----------|--------|----------|
| t0 | Info edificacio | table_cell | plantes, superficie_parcela, superficie_construida |
| t2 | Classificacio CTE | table_cell | cte_edificacio, cte_sol |
| t4 | Resultats DPSH | loop_table | test_id, cota, depth, refusal, water |
| t5 | Resultats Sondeig | loop_table | test_id, cota, depth, spt_ma, water |
| t6 | SPT | table_cell | spt_test_id, spt_location, spt_depth_range, spt_n30, spt_lithology |
| t7 | Laboratori | table_cell | lab_sample_id, lab_location, lab_depth, lab_tests_text |
| t9 | Permeabilitat | loop_table | name, k_value, material |
| t10 | Sulfats | table_cell | sulfate_level_name, sulfate_value, sulfate_baumann, sulfate_classification |
| t11 | Sismica | loop_table | num, terrain_type, thickness, c_coeff |
| t12 | Parametres geomecanics | loop_table | name, nb, n, density, cohesion, phi, E |

## Resultats (2026-04-05)

| Projecte | Variables | Taxa | Obs |
|----------|-----------|------|-----|
| 4001612 Bell-Lloc | 36 | 64.3% | Referencia principal |
| 3001621 Castellar | 37 | 66.1% | Mes variables cos |
| 3001631 Rubi | 32 | 57.1% | — |
| 4001607 Linyola | 31 | 55.4% | — |
| 4001670 Alcoletge | 31 | 55.4% | — |
| 4001671 Vilanova | 32 | 57.1% | Unic .docx natiu |
| 4001679 Anciles | 30 | 53.6% | V0, menys contingut |

**Variables d'alta prioritat extretes correctament**: cte_edificacio, cte_sol, plantes, superficie_parcela, superficie_construida, qa_value, geotech_rows (gamma, phi, E, Nb, N), dpsh_tests, sulfate_value, SPT data.

## Us

```bash
# Un projecte
.venv/bin/python -m automation.reference_extractor "reference-material/4001612 BELL-LLOC"

# Tots els projectes
.venv/bin/python -m automation.reference_extractor
```

## Sortida

`reference-material/{projecte}/validation/eva_reference_values.json`:

```json
{
  "project": "4001612 BELL-LLOC",
  "source_file": "4001612_informe.doc",
  "extraction_date": "2026-04-05T...",
  "extractor_version": "1.0",
  "statistics": { "total_extracted": 36, "extraction_rate": 64.3 },
  "variables": {
    "client": {
      "value": "RAMON MITJANA S.L.",
      "position": "p053",
      "position_description": "Body paragraph 53",
      "confidence": 0.95,
      "extraction_method": "paragraph_single"
    },
    "geotech_rows": {
      "value": [{"name": "1er nivell...", "nb": "25-R", "density": "2.00", "phi": "38", "E": "650"}],
      "position": "t12",
      "confidence": 0.85,
      "extraction_method": "loop_table"
    }
  }
}
```

## Codi reutilitzat

De `automation/intelligent_audit.py`:
- `extract_docx_paragraphs()` — lectura de paragrafs
- `extract_template_paragraphs()` — estructura de la plantilla amb variables Jinja
- `_build_table_coords_map()` — coordenades de taula
- `_flat_idx_to_elem_id()` — IDs estables (p042, t0_r1_c2)
- `JINJA_VAR_RE`, `JINJA_ANY_RE` — regex per a `{{ var }}`

## Limitacions

- **~55-65% taxa d'extraccio**: els paragrafs amb multiples variables o text molt diferent de la plantilla no es troben (llindar similitud 50%)
- **Imatges** (fig_*, photo_*): no extraibles del text
- **Numeracio interna** (section_*_num): no rellevant per a comparacio
- **Paragrafs condicionals** ({% if %}): poden no existir a l'informe d'Eva
- **Format .doc**: requereix libreoffice instal·lat per a conversio

## Proxims passos

- [ ] `scripts/compare_eva_vs_pipeline.py` — matriu comparativa Eva vs pipeline per variable
- [ ] Analisi de preferencia de fonts: quan Eva i el pipeline difereixen, de quina font ve el valor d'Eva?
- [ ] Millorar taxa d'extraccio: baixar llindar per a variables especifiques, afegir regex dedicats
