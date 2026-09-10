# Agregat M341 — mesura completa `2026-09-06-m341-mesura`

Informe generat des de `~/g3dt-e2e/projectes/<projecte>` vs signat. Escalars/narrativa: context de plantilla vs `eva_reference_values.json` (`status_for`); taules: `compare_tables_vs_eva.py` (11 taules). Lectura `_reconsolida-2026-09-06-pend`. Variants: `viaA` = només lectura + via B + Df del signat (7 projectes); `t2` = escalars d'abril de l'Eva + lectura (3).

## Titulars per projecte i variant (escalars+narrativa: M · C · X · ND → % · taules: M · C · X → %)

| projecte | viaA escalars | t2 escalars | viaA taules | t2 taules |
|---|---|---|---|---|
| castellar | 30 · 4 · 17 · 7 → **67 %** | 30 · 3 · 19 · 6 → **63 %** | 45 · 12 · 8 → **88 %** | 46 · 11 · 8 → **88 %** |
| rubi | 25 · 6 · 16 · 5 → **66 %** | 25 · 5 · 20 · 2 → **60 %** | 43 · 6 · 6 → **89 %** | 41 · 7 · 7 → **87 %** |
| bell-lloc | 31 · 7 · 17 · 3 → **69 %** | 33 · 2 · 21 · 2 → **62 %** | 39 · 6 · 10 → **82 %** | 36 · 6 · 13 → **76 %** |
| linyola | 26 · 8 · 17 · 3 → **67 %** | — | 35 · 10 · 6 → **88 %** | — |
| alcoletge | 14 · 4 · 20 · 10 → **47 %** | — | 36 · 13 · 18 → **73 %** | — |
| vilanova (es) | 14 · 4 · 26 · 6 → **41 %** | — | 23 · 24 · 27 → **64 %** | — |
| anciles (es) | 11 · 4 · 24 · 10 → **38 %** | — | 44 · 27 · 25 → **74 %** | — |
| **Total** | 151 · 37 · 137 · 44 → **58 %** | 88 · 10 · 60 · 10 → **62 %** | 265 · 98 · 100 → **78 %** | 123 · 24 · 28 → **84 %** |

## Per GRUP (escalars+narrativa), variant × grup, agregat dels projectes

| variant | grup | MATCH | CLOSE | MISMATCH | NO_DATA | % |
|---|---|--:|--:|--:|--:|--:|
| `viaA` | A | 80 | 12 | 33 | 16 | 74 % |
| `viaA` | calc | 57 | 5 | 32 | 2 | 66 % |
| `viaA` | narr | 3 | 16 | 64 | 19 | 23 % |
| `viaA` | resta | 11 | 4 | 8 | 7 | 65 % |
| `t2` | A | 41 | 2 | 17 | 5 | 72 % |
| `t2` | calc | 35 | 0 | 10 | 0 | 78 % |
| `t2` | narr | 6 | 8 | 30 | 2 | 32 % |
| `t2` | resta | 6 | 0 | 3 | 3 | 67 % |

## Narrativa per IDIOMA del signat (viaA): les cel·les ES són el sostre de la plantilla catalana, no un error

| idioma | projectes | MATCH | CLOSE | MISMATCH | NO_DATA | % |
|---|---|--:|--:|--:|--:|--:|
| ca | castellar, rubi, bell-lloc, linyola, alcoletge | 3 | 15 | 43 | 13 | 30 % |
| es | vilanova, anciles | 0 | 1 | 21 | 6 | 5 % |

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
| `location_sentence` | A | 0 | 1 | 0 | 0 |
| `spt_depth_range` | A | 4 | 0 | 0 | 0 |
| `spt_location` | A | 4 | 0 | 0 | 0 |
| `utm_x` | A | 3 | 0 | 0 | 1 |
| `utm_y` | A | 3 | 0 | 0 | 1 |
| `cte_sol` | calc | 1 | 0 | 5 | 0 |
| `geomech_E` | calc | 3 | 0 | 4 | 0 |
| `table_dpsh_range` | calc | 3 | 0 | 4 | 0 |
| `geomech_cohesion` | calc | 4 | 0 | 3 | 0 |
| `geomech_phi` | calc | 4 | 0 | 3 | 0 |
| `settlement` | calc | 4 | 0 | 3 | 0 |
| `sulfate_level_name` | calc | 4 | 0 | 3 | 0 |
| `cte_edificacio` | calc | 4 | 0 | 2 | 0 |
| `qa_value` | calc | 3 | 2 | 2 | 0 |
| `seismic_ab_text` | calc | 5 | 0 | 2 | 0 |
| `k30_value` | calc | 1 | 0 | 1 | 0 |
| `geomech_gamma` | calc | 4 | 3 | 0 | 0 |
| `radon_zone` | calc | 7 | 0 | 0 | 0 |
| `sulfate_baumann` | calc | 2 | 0 | 0 | 0 |
| `sulfate_classification` | calc | 4 | 0 | 0 | 1 |
| `sulfate_value` | calc | 4 | 0 | 0 | 1 |
| `adjacent_north_fmt` | narr | 0 | 0 | 7 | 0 |
| `adjacent_west_fmt` | narr | 0 | 0 | 7 | 0 |
| `materials_intro` | narr | 0 | 0 | 7 | 0 |
| `radon_zone_description` | narr | 0 | 0 | 7 | 0 |
| `adjacent_east_fmt` | narr | 0 | 1 | 6 | 0 |
| `conclusions_aggressivity_statement` | narr | 0 | 0 | 6 | 0 |
| `site_condition` | narr | 0 | 1 | 6 | 0 |
| `adjacent_south_fmt` | narr | 0 | 2 | 5 | 0 |
| `building_structure_desc` | narr | 0 | 2 | 5 | 0 |
| `conclusions_levels_detected` | narr | 0 | 5 | 2 | 0 |
| `conclusions_water_statement` | narr | 2 | 3 | 2 | 0 |
| `lab_tests_text` | narr | 0 | 2 | 2 | 3 |
| `photo_site_text` | narr | 1 | 0 | 2 | 0 |
| `access_street` | narr | 0 | 0 | 0 | 6 |
| `empentes_paragraph` | narr | 0 | 0 | 0 | 2 |
| `estabilitat_paragraph` | narr | 0 | 0 | 0 | 1 |
| `site_description` | narr | 0 | 0 | 0 | 7 |
| `data_signatura_text` | resta | 0 | 0 | 7 | 0 |
| `architect_name` | resta | 0 | 0 | 1 | 0 |
| `client_name` | resta | 1 | 0 | 0 | 0 |
| `geo_p` | resta | 0 | 0 | 0 | 7 |
| `lab_field_description` | resta | 5 | 2 | 0 | 0 |
| `lab_testing_description` | resta | 5 | 2 | 0 | 0 |

## Càlcul per projecte (viaA): nivell portant, Nb, φ, E, Qa, assentament

| projecte | Df | nivell portant | Nb | φ | γ | c | E | Qa (gov) | assent. | imprès | Es |
|---|--:|---|--:|--:|--:|--:|--:|---|--:|---|---|
| castellar | 0.3 | 1: Roca / material dur (roca pochimada / fo | 27.2 | 35 | 2.2 | 1.0 | 500 | 3.00 (cap) | 2.30 | <1,0 ✓ | 68 |
| rubi | 1.0 | 0: Graves i sorres (Nivell 1) | 52.2 | 39 | 2.0 | 0.0 | 450 | 3.00 (cap) | 1.50 | 1,50 ✓ | 100 |
| bell-lloc | 0.3 | 0: Graves carbonatades | 22.6 | 38 | 2.0 | 0.0 | 450 | 3.00 (cap) | 1.00 | 1,00 ✗ | 155 |
| linyola | 1.7 | 0:  | 22.6 | 38 | 2.0 | 0.0 | 450 | 3.00 (cap) | 2.60 | <1,0 | 57 |
| alcoletge | 1.0 | 1:  | 21.5 | 38 | 2.0 | 0.0 | 450 | 3.00 (cap) | 3.00 | <1,0 | 50 |
| vilanova | 0.3 | 0:  | 22.2 | 29 | 2.0 | 0.0 | 50 | 1.00 (terzaghi) | 2.00 | 2,00 | 25 |
| anciles | 2.9 | 1:  | 26.3 | 38 | 2.0 | 0.0 | 450 | 3.00 (cap) | 2.20 | 2,20 | 66 |

## Errors i avisos del generador

- **rubi/viaA**: errors=[] warnings=["Lectura: 1 nivell(s) de l'informe sense litologia llegida (llegits: [1]); es manté la descripció automàtica."]
- **linyola/viaA**: errors=[] warnings=['Assentament: ⚠ 2.60 cm supera el topall de servei de 2.54 cm (1 polzada) per a sabates']
- **alcoletge/viaA**: errors=[] warnings=['Assentament: ⚠ 3.00 cm supera el topall de servei de 2.54 cm (1 polzada) per a sabates']

