# Agregat M341 — mesura completa `2026-09-10-wsl-sense-claus-bell-lloc_reconsolida-2026-09-06-pend`

Informe generat des de `~/g3dt-e2e/projectes/<projecte>` vs signat. Escalars/narrativa: context de plantilla vs `eva_reference_values.json` (`status_for`); taules: `compare_tables_vs_eva.py` (11 taules). Lectura `_reconsolida-2026-09-06-pend`. Variants: `viaA` = només lectura + via B + Df del signat (7 projectes); `t2` = escalars d'abril de l'Eva + lectura (3).

## Titulars per projecte i variant (escalars+narrativa: M · C · X · ND → % · taules: M · C · X → %)

| projecte | viaA escalars | viaA taules |
|---|---|---|
| bell-lloc | 60 · 6 · 13 · 1 → **84 %** | 42 · 4 · 9 → **84 %** |
| **Total** | 60 · 6 · 13 · 1 → **84 %** | 42 · 4 · 9 → **84 %** |

## Per GRUP (escalars+narrativa), variant × grup, agregat dels projectes

| variant | grup | MATCH | CLOSE | MISMATCH | NO_DATA | % |
|---|---|--:|--:|--:|--:|--:|
| `viaA` | A | 21 | 3 | 2 | 0 | 92 % |
| `viaA` | calc | 13 | 0 | 2 | 0 | 87 % |
| `viaA` | narr | 9 | 3 | 4 | 0 | 75 % |
| `viaA` | fix | 14 | 0 | 5 | 0 | 74 % |
| `viaA` | resta | 3 | 0 | 0 | 1 | 100 % |

## Narrativa per IDIOMA del signat (viaA): les cel·les ES són el sostre de la plantilla catalana, no un error

| idioma | projectes | MATCH | CLOSE | MISMATCH | NO_DATA | % |
|---|---|--:|--:|--:|--:|--:|
| ca | bell-lloc | 9 | 3 | 4 | 0 | 75 % |

`csn_radon_text` fora de la mesura (text fix de la plantilla). Narrativa puntuada forat contra forat (`narr_status`).

## Imatges (viaA): presència per forat — present · pendent («[Imatge pendent]») · absent (buit)

| projecte | present | pendent | absent | forats pendents |
|---|--:|--:|--:|---|
| bell-lloc | 10 | 0 | 3 | — |

Absent = vistes generals no triades (`photo_site_image_*`), foto del sondeig sense sondeig, 2a imatge de situació, figures del projecte o d'assaigs que no hi són (blocs condicionals, peça 7a): no és cap defecte. Pendent = `image_manager` no ha trobat o no ha pogut baixar la imatge. La correcció del contingut es mira al full de control visual (`_IMATGES.md`, una vegada a mà).

## Imatges (viaA): MATEIXA FONT que l'Eva, per figura del signat — M (mateixa imatge) · C (mateixa font, altre retall) · X · ND (no posem res)

| projecte | M | C | X | ND | % | sobrants | X i ND (ranura de l'Eva) |
|---|--:|--:|--:|--:|--:|--:|---|
| bell-lloc | 5 | 1 | 2 | 2 | 75 % | 1 | `fig_situacio`:ND, `fig_situacio`:X, `fig_projecte`:ND, `fig_geologic`:X |
| **total** | **5** | **1** | **2** | **2** | **75 %** | | |

| ranura de l'Eva | M | C | X | ND | % |
|---|--:|--:|--:|--:|--:|
| `fig_geologic` | 0 | 0 | 1 | 0 | 0 % |
| `fig_projecte` | 0 | 0 | 0 | 1 | — |
| `fig_situacio` | 0 | 0 | 1 | 1 | 0 % |
| `fig_tall` | 0 | 1 | 0 | 0 | 100 % |
| `foto_dpsh` | 1 | 0 | 0 | 0 | 100 % |
| `foto_materials` | 1 | 0 | 0 | 0 | 100 % |
| `foto_sondeig` | 1 | 0 | 0 | 0 | 100 % |
| `foto_vista` | 2 | 0 | 0 | 0 | 100 % |

Llindars: M = phash ≤ 10; C = NCC·min(1, PSR/6) ≥ 0.7 (veritat dins nostra, o nostra dins veritat per a figures). Fora: cullera SPT, estàtiques, figures «extra» sense ranura (D10), duplicats del signat. X per hash pot ser mateixa font a ull (línia fina): tendència, no veredicte. Detall per projecte a `<slug>/viaA/_compare_imatges.txt`.

## Per VARIABLE (viaA): en quants projectes és MATCH / CLOSE / MISMATCH / NO_DATA

| variable | grup | M | C | X | ND |
|---|---|--:|--:|--:|--:|
| `spt_lithology` | A | 0 | 0 | 1 | 0 |
| `spt_n30` | A | 0 | 0 | 1 | 0 |
| `architect_company` | A | 0 | 1 | 0 | 0 |
| `architect_name_upper` | A | 1 | 0 | 0 | 0 |
| `building_type_lower` | A | 0 | 1 | 0 | 0 |
| `client` | A | 1 | 0 | 0 | 0 |
| `cota_referencia` | A | 1 | 0 | 0 | 0 |
| `data_camp_inici_text` | A | 1 | 0 | 0 | 0 |
| `data_camp_text` | A | 1 | 0 | 0 | 0 |
| `expedient` | A | 1 | 0 | 0 | 0 |
| `lab_depth` | A | 1 | 0 | 0 | 0 |
| `lab_field_company` | A | 1 | 0 | 0 | 0 |
| `lab_location` | A | 1 | 0 | 0 | 0 |
| `lab_sample_id` | A | 1 | 0 | 0 | 0 |
| `lab_testing_company` | A | 1 | 0 | 0 | 0 |
| `location_sentence` | A | 1 | 0 | 0 | 0 |
| `municipality_de` | A | 1 | 0 | 0 | 0 |
| `num_dpsh_tests` | A | 1 | 0 | 0 | 0 |
| `plantes` | A | 1 | 0 | 0 | 0 |
| `spt_depth_range` | A | 1 | 0 | 0 | 0 |
| `spt_location` | A | 1 | 0 | 0 | 0 |
| `spt_test_id` | A | 1 | 0 | 0 | 0 |
| `superficie_construida` | A | 0 | 1 | 0 | 0 |
| `superficie_parcela` | A | 1 | 0 | 0 | 0 |
| `utm_x` | A | 1 | 0 | 0 | 0 |
| `utm_y` | A | 1 | 0 | 0 | 0 |
| `geomech_E` | calc | 0 | 0 | 1 | 0 |
| `settlement_sentence` | calc | 0 | 0 | 1 | 0 |
| `bearing_layer_idx` | calc | 1 | 0 | 0 | 0 |
| `cte_edificacio` | calc | 1 | 0 | 0 | 0 |
| `cte_sol` | calc | 1 | 0 | 0 | 0 |
| `geomech_cohesion` | calc | 1 | 0 | 0 | 0 |
| `geomech_gamma` | calc | 1 | 0 | 0 | 0 |
| `geomech_phi` | calc | 1 | 0 | 0 | 0 |
| `qa_value` | calc | 1 | 0 | 0 | 0 |
| `radon_zone` | calc | 1 | 0 | 0 | 0 |
| `seismic_ab_text` | calc | 1 | 0 | 0 | 0 |
| `sulfate_classification` | calc | 1 | 0 | 0 | 0 |
| `sulfate_level_name` | calc | 1 | 0 | 0 | 0 |
| `sulfate_value` | calc | 1 | 0 | 0 | 0 |
| `table_dpsh_range` | calc | 1 | 0 | 0 | 0 |
| `fig_correlation_num` | fix | 0 | 0 | 1 | 0 |
| `fig_geological_num` | fix | 0 | 0 | 1 | 0 |
| `fig_situacio_2_num` | fix | 0 | 0 | 1 | 0 |
| `fig_spt_cullera_num` | fix | 0 | 0 | 1 | 0 |
| `section_resum_num` | fix | 0 | 0 | 1 | 0 |
| `fig_situacio_num` | fix | 1 | 0 | 0 | 0 |
| `photo_dpsh_num` | fix | 1 | 0 | 0 | 0 |
| `photo_materials_num` | fix | 1 | 0 | 0 | 0 |
| `photo_sondeig_num` | fix | 1 | 0 | 0 | 0 |
| `section_excavabilitat_num` | fix | 1 | 0 | 0 | 0 |
| `section_rado_num` | fix | 1 | 0 | 0 | 0 |
| `section_sismica_num` | fix | 1 | 0 | 0 | 0 |
| `section_sondeig_num` | fix | 1 | 0 | 0 | 0 |
| `section_spt_num` | fix | 1 | 0 | 0 | 0 |
| `table_lab_num` | fix | 1 | 0 | 0 | 0 |
| `table_lab_values_num` | fix | 1 | 0 | 0 | 0 |
| `table_permeability_num` | fix | 1 | 0 | 0 | 0 |
| `table_seismic_num` | fix | 1 | 0 | 0 | 0 |
| `table_soil_chars_num` | fix | 1 | 0 | 0 | 0 |
| `access_street` | narr | 0 | 0 | 1 | 0 |
| `building_structure_desc` | narr | 0 | 0 | 1 | 0 |
| `conclusions_aggressivity_statement` | narr | 0 | 0 | 1 | 0 |
| `site_description` | narr | 0 | 0 | 1 | 0 |
| `adjacent_east_fmt` | narr | 1 | 0 | 0 | 0 |
| `adjacent_intro` | narr | 1 | 0 | 0 | 0 |
| `adjacent_north_fmt` | narr | 1 | 0 | 0 | 0 |
| `adjacent_south_fmt` | narr | 0 | 1 | 0 | 0 |
| `adjacent_west_fmt` | narr | 0 | 1 | 0 | 0 |
| `conclusions_levels_detected` | narr | 1 | 0 | 0 | 0 |
| `conclusions_water_statement` | narr | 1 | 0 | 0 | 0 |
| `lab_tests_text` | narr | 1 | 0 | 0 | 0 |
| `materials_intro` | narr | 1 | 0 | 0 | 0 |
| `photo_site_text` | narr | 1 | 0 | 0 | 0 |
| `radon_sentence` | narr | 1 | 0 | 0 | 0 |
| `site_condition` | narr | 0 | 1 | 0 | 0 |
| `data_signatura_text` | resta | 1 | 0 | 0 | 0 |
| `geo_p` | resta | 0 | 0 | 0 | 1 |
| `lab_field_description` | resta | 1 | 0 | 0 | 0 |
| `lab_testing_description` | resta | 1 | 0 | 0 | 0 |

## Càlcul per projecte (viaA): nivell portant, Nb, φ, E, Qa, assentament

| projecte | Df | nivell portant | Nb | φ | γ | c | E | Qa (gov) | assent. | imprès | Es |
|---|--:|---|--:|--:|--:|--:|--:|---|--:|---|---|
| bell-lloc | 0.3 | 0: Graves carbonatades | 22.6 | 38 | 2.0 | 0.0 | 450 | 3.00 (cap) | 1.00 | 1,00 ✗ | 155 |

## Errors i avisos del generador


