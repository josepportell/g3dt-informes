# Agregat M341 — mesura completa `2026-09-07-m341-bloc3b`

Informe generat des de `~/g3dt-e2e/projectes/<projecte>` vs signat. Escalars/narrativa: context de plantilla vs `eva_reference_values.json` (`status_for`); taules: `compare_tables_vs_eva.py` (11 taules). Lectura `_reconsolida-2026-09-06-pend`. Variants: `viaA` = només lectura + via B + Df del signat (7 projectes); `t2` = escalars d'abril de l'Eva + lectura (3).

## Titulars per projecte i variant (escalars+narrativa: M · C · X · ND → % · taules: M · C · X → %)

| projecte | viaA escalars | t2 escalars | viaA taules | t2 taules |
|---|---|---|---|---|
| castellar | 43 · 3 · 10 · 5 → **82 %** | 36 · 5 · 14 · 6 → **75 %** | 50 · 10 · 5 → **92 %** | 48 · 10 · 7 → **89 %** |
| rubi | 36 · 8 · 12 · 4 → **79 %** | 34 · 7 · 16 · 3 → **72 %** | 43 · 8 · 4 → **93 %** | 41 · 8 · 6 → **89 %** |
| bell-lloc | 46 · 6 · 8 · 1 → **87 %** | 42 · 2 · 15 · 2 → **75 %** | 42 · 4 · 9 → **84 %** | 39 · 4 · 12 → **78 %** |
| linyola | 44 · 4 · 13 · 1 → **79 %** | — | 47 · 14 · 6 → **91 %** | — |
| alcoletge | 31 · 5 · 12 · 8 → **75 %** | — | 37 · 13 · 17 → **75 %** | — |
| vilanova (es) | 16 · 10 · 21 · 6 → **55 %** | — | 28 · 23 · 23 → **69 %** | — |
| anciles (es) | 18 · 7 · 22 · 8 → **53 %** | — | 45 · 27 · 24 → **75 %** | — |
| **Total** | 234 · 43 · 98 · 33 → **74 %** | 112 · 14 · 45 · 11 → **74 %** | 292 · 99 · 88 → **82 %** | 128 · 22 · 25 → **86 %** |

## Per GRUP (escalars+narrativa), variant × grup, agregat dels projectes

| variant | grup | MATCH | CLOSE | MISMATCH | NO_DATA | % |
|---|---|--:|--:|--:|--:|--:|
| `viaA` | A | 109 | 7 | 32 | 16 | 78 % |
| `viaA` | calc | 75 | 4 | 24 | 2 | 77 % |
| `viaA` | narr | 34 | 28 | 39 | 8 | 61 % |
| `viaA` | resta | 16 | 4 | 3 | 7 | 87 % |
| `t2` | A | 50 | 4 | 14 | 5 | 79 % |
| `t2` | calc | 40 | 0 | 8 | 0 | 83 % |
| `t2` | narr | 16 | 10 | 20 | 3 | 57 % |
| `t2` | resta | 6 | 0 | 3 | 3 | 67 % |

## Narrativa per IDIOMA del signat (viaA): les cel·les ES són el sostre de la plantilla catalana, no un error

| idioma | projectes | MATCH | CLOSE | MISMATCH | NO_DATA | % |
|---|---|--:|--:|--:|--:|--:|
| ca | castellar, rubi, bell-lloc, linyola, alcoletge | 31 | 18 | 26 | 4 | 65 % |
| es | vilanova, anciles | 3 | 10 | 13 | 4 | 50 % |

`csn_radon_text` fora de la mesura (text fix de la plantilla). Narrativa puntuada forat contra forat (`narr_status`).

## Per VARIABLE (viaA): en quants projectes és MATCH / CLOSE / MISMATCH / NO_DATA

| variable | grup | M | C | X | ND |
|---|---|--:|--:|--:|--:|
| `spt_lithology` | A | 0 | 0 | 6 | 1 |
| `architect_name_upper` | A | 1 | 0 | 5 | 0 |
| `building_type_lower` | A | 1 | 2 | 4 | 0 |
| `client` | A | 4 | 0 | 3 | 0 |
| `data_camp_inici_text` | A | 5 | 0 | 2 | 0 |
| `data_camp_text` | A | 5 | 0 | 2 | 0 |
| `municipality_de` | A | 4 | 1 | 2 | 0 |
| `spt_n30` | A | 5 | 0 | 2 | 0 |
| `superficie_construida` | A | 4 | 1 | 2 | 0 |
| `cota_referencia` | A | 5 | 0 | 1 | 1 |
| `num_dpsh_tests` | A | 6 | 0 | 1 | 0 |
| `plantes` | A | 5 | 0 | 1 | 1 |
| `superficie_parcela` | A | 6 | 0 | 1 | 0 |
| `architect_company` | A | 0 | 2 | 0 | 0 |
| `expedient` | A | 6 | 1 | 0 | 0 |
| `lab_depth` | A | 4 | 0 | 0 | 3 |
| `lab_field_company` | A | 7 | 0 | 0 | 0 |
| `lab_location` | A | 3 | 0 | 0 | 4 |
| `lab_sample_id` | A | 3 | 0 | 0 | 4 |
| `lab_testing_company` | A | 7 | 0 | 0 | 0 |
| `location_sentence` | A | 1 | 0 | 0 | 0 |
| `spt_depth_range` | A | 7 | 0 | 0 | 0 |
| `spt_location` | A | 7 | 0 | 0 | 0 |
| `spt_test_id` | A | 7 | 0 | 0 | 0 |
| `utm_x` | A | 3 | 0 | 0 | 1 |
| `utm_y` | A | 3 | 0 | 0 | 1 |
| `geomech_E` | calc | 2 | 0 | 5 | 0 |
| `settlement_sentence` | calc | 3 | 0 | 4 | 0 |
| `sulfate_level_name` | calc | 4 | 0 | 3 | 0 |
| `table_dpsh_range` | calc | 4 | 0 | 3 | 0 |
| `geomech_cohesion` | calc | 5 | 0 | 2 | 0 |
| `qa_value` | calc | 4 | 1 | 2 | 0 |
| `seismic_ab_text` | calc | 5 | 0 | 2 | 0 |
| `bearing_layer_idx` | calc | 6 | 0 | 1 | 0 |
| `cte_edificacio` | calc | 6 | 0 | 1 | 0 |
| `k30_value` | calc | 1 | 0 | 1 | 0 |
| `cte_sol` | calc | 7 | 0 | 0 | 0 |
| `geomech_gamma` | calc | 5 | 2 | 0 | 0 |
| `geomech_phi` | calc | 6 | 1 | 0 | 0 |
| `radon_zone` | calc | 7 | 0 | 0 | 0 |
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
| `materials_intro` | narr | 4 | 3 | 0 | 0 |
| `photo_site_text` | narr | 1 | 0 | 0 | 2 |
| `radon_sentence` | narr | 4 | 3 | 0 | 0 |
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
| vilanova | 1.1 | 1: Arenas finas-medias, carbonatadas. | 22.2 | 38 | 2.0 | 0.0 | 450 | 3.00 (cap) | 2.50 | 2,50 | 60 |
| anciles | 2.9 | 1: Bolos y gravas en matriz arenosa y arcil | 26.3 | 38 | 2.0 | 0.0 | 450 | 3.50 (cap) | 2.60 | 2,60 | 66 |

## Errors i avisos del generador

- **rubi/viaA**: errors=[] warnings=["Lectura: 1 nivell(s) de l'informe sense litologia llegida (llegits: [1]); es manté la descripció automàtica."]
- **anciles/viaA**: errors=[] warnings=['Assentament: ⚠ 2.60 cm supera el topall de servei de 2.54 cm (1 polzada) per a sabates']

