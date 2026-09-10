# Agregat M341 — mesura completa `2026-09-07-m341-bloc1a`

Informe generat des de `~/g3dt-e2e/projectes/<projecte>` vs signat. Escalars/narrativa: context de plantilla vs `eva_reference_values.json` (`status_for`); taules: `compare_tables_vs_eva.py` (11 taules). Lectura `_reconsolida-2026-09-06-pend`. Variants: `viaA` = només lectura + via B + Df del signat (7 projectes); `t2` = escalars d'abril de l'Eva + lectura (3).

## Titulars per projecte i variant (escalars+narrativa: M · C · X · ND → % · taules: M · C · X → %)

| projecte | viaA escalars | t2 escalars | viaA taules | t2 taules |
|---|---|---|---|---|
| castellar | 40 · 4 · 10 · 5 → **81 %** | 35 · 5 · 13 · 6 → **75 %** | 48 · 11 · 6 → **91 %** | 48 · 10 · 7 → **89 %** |
| rubi | 29 · 8 · 12 · 4 → **76 %** | 28 · 6 · 16 · 3 → **68 %** | 43 · 7 · 5 → **91 %** | 41 · 8 · 6 → **89 %** |
| bell-lloc | 41 · 6 · 11 · 1 → **81 %** | 38 · 1 · 18 · 2 → **68 %** | 41 · 5 · 9 → **84 %** | 38 · 5 · 12 → **78 %** |
| linyola | 32 · 6 · 13 · 4 → **75 %** | — | 45 · 14 · 8 → **88 %** | — |
| alcoletge | 19 · 5 · 14 · 11 → **63 %** | — | 34 · 12 · 21 → **69 %** | — |
| vilanova (es) | 16 · 8 · 18 · 9 → **57 %** | — | 27 · 22 · 25 → **66 %** | — |
| anciles (es) | 12 · 6 · 21 · 11 → **46 %** | — | 45 · 25 · 26 → **73 %** | — |
| **Total** | 189 · 43 · 99 · 45 → **70 %** | 101 · 12 · 47 · 11 → **71 %** | 283 · 96 · 100 → **79 %** | 127 · 23 · 25 → **86 %** |

## Per GRUP (escalars+narrativa), variant × grup, agregat dels projectes

| variant | grup | MATCH | CLOSE | MISMATCH | NO_DATA | % |
|---|---|--:|--:|--:|--:|--:|
| `viaA` | A | 81 | 11 | 33 | 16 | 74 % |
| `viaA` | calc | 63 | 3 | 24 | 6 | 73 % |
| `viaA` | narr | 29 | 25 | 39 | 16 | 58 % |
| `viaA` | resta | 16 | 4 | 3 | 7 | 87 % |
| `t2` | A | 41 | 2 | 17 | 5 | 72 % |
| `t2` | calc | 38 | 0 | 7 | 0 | 84 % |
| `t2` | narr | 16 | 10 | 20 | 3 | 57 % |
| `t2` | resta | 6 | 0 | 3 | 3 | 67 % |

## Narrativa per IDIOMA del signat (viaA): les cel·les ES són el sostre de la plantilla catalana, no un error

| idioma | projectes | MATCH | CLOSE | MISMATCH | NO_DATA | % |
|---|---|--:|--:|--:|--:|--:|
| ca | castellar, rubi, bell-lloc, linyola, alcoletge | 27 | 18 | 26 | 8 | 63 % |
| es | vilanova, anciles | 2 | 7 | 13 | 8 | 41 % |

`csn_radon_text` fora de la mesura (text fix de la plantilla). Narrativa puntuada forat contra forat (`narr_status`).

## Per VARIABLE (viaA): en quants projectes és MATCH / CLOSE / MISMATCH / NO_DATA

| variable | grup | M | C | X | ND |
|---|---|--:|--:|--:|--:|
| `architect_name_upper` | A | 1 | 0 | 5 | 0 |
| `building_type_lower` | A | 1 | 1 | 5 | 0 |
| `client` | A | 3 | 1 | 3 | 0 |
| `data_camp_text` | A | 4 | 0 | 3 | 0 |
| `municipality` | A | 2 | 2 | 3 | 0 |
| `spt_lithology` | A | 0 | 0 | 3 | 1 |
| `superficie_parcela` | A | 4 | 0 | 3 | 0 |
| `plantes` | A | 1 | 3 | 2 | 1 |
| `spt_n30` | A | 2 | 0 | 2 | 0 |
| `cota_referencia` | A | 5 | 0 | 1 | 1 |
| `num_dpsh_tests` | A | 6 | 0 | 1 | 0 |
| `spt_test_id` | A | 3 | 0 | 1 | 0 |
| `superficie_construida` | A | 4 | 1 | 1 | 0 |
| `architect_company` | A | 0 | 2 | 0 | 0 |
| `expedient` | A | 6 | 1 | 0 | 0 |
| `lab_depth` | A | 4 | 0 | 0 | 3 |
| `lab_field_company` | A | 7 | 0 | 0 | 0 |
| `lab_location` | A | 3 | 0 | 0 | 4 |
| `lab_sample_id` | A | 3 | 0 | 0 | 4 |
| `lab_testing_company` | A | 7 | 0 | 0 | 0 |
| `location_sentence` | A | 1 | 0 | 0 | 0 |
| `spt_depth_range` | A | 4 | 0 | 0 | 0 |
| `spt_location` | A | 4 | 0 | 0 | 0 |
| `utm_x` | A | 3 | 0 | 0 | 1 |
| `utm_y` | A | 3 | 0 | 0 | 1 |
| `geomech_E` | calc | 3 | 0 | 4 | 0 |
| `settlement` | calc | 3 | 0 | 4 | 0 |
| `sulfate_level_name` | calc | 4 | 0 | 3 | 0 |
| `table_dpsh_range` | calc | 4 | 0 | 3 | 0 |
| `geomech_cohesion` | calc | 5 | 0 | 2 | 0 |
| `qa_value` | calc | 4 | 1 | 2 | 0 |
| `radon_zone` | calc | 5 | 0 | 2 | 0 |
| `cte_edificacio` | calc | 5 | 0 | 1 | 0 |
| `geomech_gamma` | calc | 6 | 0 | 1 | 0 |
| `k30_value` | calc | 1 | 0 | 1 | 0 |
| `seismic_ab_text` | calc | 2 | 0 | 1 | 4 |
| `cte_sol` | calc | 6 | 0 | 0 | 0 |
| `geomech_phi` | calc | 5 | 2 | 0 | 0 |
| `sulfate_baumann` | calc | 2 | 0 | 0 | 0 |
| `sulfate_classification` | calc | 4 | 0 | 0 | 1 |
| `sulfate_value` | calc | 4 | 0 | 0 | 1 |
| `adjacent_north_fmt` | narr | 1 | 0 | 6 | 0 |
| `site_description` | narr | 0 | 1 | 6 | 0 |
| `adjacent_east_fmt` | narr | 1 | 1 | 5 | 0 |
| `adjacent_west_fmt` | narr | 0 | 2 | 5 | 0 |
| `access_street` | narr | 3 | 0 | 4 | 0 |
| `adjacent_south_fmt` | narr | 1 | 2 | 4 | 0 |
| `building_structure_desc` | narr | 2 | 1 | 3 | 0 |
| `conclusions_aggressivity_statement` | narr | 2 | 1 | 3 | 0 |
| `conclusions_water_statement` | narr | 2 | 3 | 2 | 0 |
| `site_condition` | narr | 4 | 2 | 1 | 0 |
| `adjacent_intro` | narr | 2 | 5 | 0 | 0 |
| `conclusions_levels_detected` | narr | 5 | 2 | 0 | 0 |
| `empentes_paragraph` | narr | 0 | 0 | 0 | 2 |
| `estabilitat_paragraph` | narr | 0 | 0 | 0 | 1 |
| `lab_tests_text` | narr | 2 | 2 | 0 | 3 |
| `materials_intro` | narr | 1 | 2 | 0 | 4 |
| `photo_site_text` | narr | 1 | 0 | 0 | 2 |
| `radon_sentence` | narr | 2 | 1 | 0 | 4 |
| `data_signatura_text` | resta | 5 | 0 | 2 | 0 |
| `architect_name` | resta | 0 | 0 | 1 | 0 |
| `client_name` | resta | 1 | 0 | 0 | 0 |
| `geo_p` | resta | 0 | 0 | 0 | 7 |
| `lab_field_description` | resta | 5 | 2 | 0 | 0 |
| `lab_testing_description` | resta | 5 | 2 | 0 | 0 |

## Càlcul per projecte (viaA): nivell portant, Nb, φ, E, Qa, assentament

| projecte | Df | nivell portant | Nb | φ | γ | c | E | Qa (gov) | assent. | imprès | Es |
|---|--:|---|--:|--:|--:|--:|--:|---|--:|---|---|
| castellar | 0.3 | 1: Roca / material dur (roca pochimada / fo | 27.2 | 35 | 2.2 | 1.0 | 500 | 3.00 (cap) | 2.30 | <1,0 ✓ | 68 |
| rubi | 1.0 | 0: Graves i sorres (Nivell 1) | 52.2 | 39 | 2.0 | 0.0 | 450 | 3.50 (cap) | 1.80 | 1,80 ✗ | 100 |
| bell-lloc | 0.3 | 0: Graves carbonatades | 22.6 | 38 | 2.0 | 0.0 | 450 | 3.00 (cap) | 1.00 | 1,00 ✗ | 155 |
| linyola | 1.7 | 1: Lutites i sorrenques, Substrat | 37.8 | 30 | 2.2 | 1.0 | 500 | 3.00 (cap) | 1.60 | <1,0 | 94 |
| alcoletge | 1.0 | 1: Lutites, substrat | 39.4 | 30 | 2.2 | 1.0 | 500 | 3.00 (cap) | 1.50 | <1,0 | 98 |
| vilanova | 0.3 | 0:  | 22.2 | 28 | 1.9 | 0.1 | 50 | 2.00 (terzaghi) | 4.10 | <1,0 | 25 |
| anciles | 2.9 | 1:  | 26.3 | 38 | 2.0 | 0.0 | 450 | 3.00 (cap) | 2.20 | 2,20 | 66 |

## Errors i avisos del generador

- **rubi/viaA**: errors=[] warnings=["Lectura: 1 nivell(s) de l'informe sense litologia llegida (llegits: [1]); es manté la descripció automàtica."]
- **linyola/viaA**: errors=['Section 3 generation failed: unsupported format string passed to NoneType.__format__'] warnings=[]
- **alcoletge/viaA**: errors=['Section 3 generation failed: unsupported format string passed to NoneType.__format__'] warnings=[]
- **vilanova/viaA**: errors=['Section 3 generation failed: unsupported format string passed to NoneType.__format__'] warnings=['Assentament: ⚠ 4.10 cm supera el topall de servei de 2.54 cm (1 polzada) per a sabates']
- **anciles/viaA**: errors=['Section 3 generation failed: unsupported format string passed to NoneType.__format__'] warnings=[]

