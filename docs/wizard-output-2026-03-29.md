# Wizard Output Snapshot — 2026-03-29

After full pipeline re-run (clean baseline, no user_data.json).
Captured from localhost:8765/review.html.

## Issues identified

1. **Photo picker UX**: Current implementation groups by topic (Vista general, DPSH, Sondeig, Materials). User wants **report-section-oriented**: one section per image slot in order of appearance in the report, showing system's best pick + alternatives.

2. **Tier C calc notes not displaying**: Overrides Experts shows empty gamma/c/phi/E fields with no calc notes underneath. Only Es_settlement shows its note ("2.5×Nb (Nb=X)"). The `_calc_gamma`, `_calc_phi`, `_calc_E`, `_calc_cohesion` context vars are not reaching the frontend.

3. **Many wizard fields empty**: Several projects missing key data (arquitecte, plantes, superficies, client). Need analysis of what's expected vs what's available.

---

## Bell-Lloc (4001612)

**Vision:** completada (4/4)

### Dades del Projecte
| Camp | Font | Valor |
|------|------|-------|
| Arquitecte | planol A.01.pdf | Jordi Bosch Novell |
| Empresa arquitecte | planol A.01.pdf | Arquitectura Bosch Novell |
| Client / Promotor | planol A.01.pdf+4 | RAMON MITJANA S.L. |
| Adreca del solar | planol A.01.pdf+2 | Carrer Mestre Ramon Ortiz |
| Municipi | planol A.01.pdf | Bell-Lloc d'Urgell |
| Tipus edificacio | planol A.01.pdf+5 | habitatge unifamiliar aïllat |
| Plantes | planol A.01.pdf | ?? |
| Sup. construida | planol A.01.pdf | 297 |
| Sup. parcella | user_data | 607.504 |
| Sup. cadastral | user_data | 607.505 |
| Alcada edificacio | planol A.01.pdf | 6.5 |
| Desc. terreny | plantilla | parcel·la de forma quadrada amb superfície de 607 m2. El terreny es presenta antropitzat |
| Desc. acces | plantilla | El dia dels treballs de camp es realitza l'entrada a la zona d'estudi a través del Carrer Mestre Ramon Ortiz existent al est. |

### Adjacents
| Dir | Font | Valor |
|-----|------|-------|
| Nord | Cadastre API | parcel·la buida |
| Sud | Cadastre API | parcel·la buida |
| Est | Cadastre API | Carrer Mestre Ramon Ortiz |
| Oest | Cadastre API | parcel·la amb construcció |

### Parametres
| Camp | Font | Valor |
|------|------|-------|
| Terreny antropitzat | defecte | Si |
| Nivells sol | sondeig S-1 | 2 |
| Tipus sol N1 | | Granular |
| Tipus sol N2 | | Granular |
| Prof. fonamentacio | DPSH (2 assaigs) | 0,3 |
| Cota referencia | sondeig elevation_z | +199.50 |
| Soterrani | defecte | No |
| Murs contencio | defecte | No |

### Coordenades
| Camp | Font | Valor |
|------|------|-------|
| UTM X | contingut:ANNEXES/... | 314418,9 |
| UTM Y | contingut:ANNEXES/... | 4611117,6 |

### Overrides Experts
| Camp | Font | Valor |
|------|------|-------|
| Codi ICGC | ICGC WMS 1:50k | Qvpu |
| Desc. ICGC | | Graves amb matriu lutítica i llentillons sorrencs |
| Epoca ICGC | | Plistocè |
| gamma | | (buit) |
| c | | (buit) |
| phi | | (buit) |
| E | | (buit) |
| Es settlement | 2.5×Nb (Nb=44.2) | 111 |
| Resultats calculats | | (buit) |

**NOTE:** gamma/c/phi/E fields empty despite pipeline computing them. Calc notes not displayed.

---

## Castellar del Vallès (3001621)

**Vision:** completada (4/4)

### Dades del Projecte
| Camp | Font | Valor |
|------|------|-------|
| Arquitecte | | (buit) |
| Empresa arquitecte | planol | G3 |
| Client / Promotor | contingut:25.0493/...+1 | GRUP ALMA |
| Adreca del solar | planol+2 | Carrer Arbrells Nº 18A-18B-20 |
| Municipi | planol | Castellar del Vallès |
| Tipus edificacio | planol | habitatge unifamiliar aïllat |
| Plantes | | (buit) |
| Sup. construida | | (buit) |
| Sup. parcella | | (buit) |
| Sup. cadastral | Cadastre WFS | 440 |
| Alcada edificacio | | (buit) |
| Desc. terreny | plantilla | El terreny es presenta antropitzat |
| Desc. acces | plantilla | El dia dels treballs de camp es realitza l'entrada a la zona d'estudi a través del Carrer dels Arbrells existent al sud. |

### Adjacents
| Dir | Font | Valor |
|-----|------|-------|
| Nord | Cadastre API | parcel·la amb construcció |
| Sud | Cadastre API | Carrer dels Arbrells |
| Est | Cadastre API | parcel·la amb construcció |
| Oest | Cadastre API | parcel·la buida |

### Parametres
| Camp | Font | Valor |
|------|------|-------|
| Terreny antropitzat | defecte | Si |
| Nivells sol | sondeig S-1 | 2 |
| Tipus sol N1 | | Granular |
| Tipus sol N2 | | Granular |
| Prof. fonamentacio | DPSH (4 assaigs) | 0,3 |
| Cota referencia | sondeig elevation_z | +570.90 |
| Soterrani | defecte | No |
| Murs contencio | defecte | No |

### Coordenades
| Camp | Font | Valor |
|------|------|-------|
| UTM X | contingut:ANNEXES/... | 423181,4 |
| UTM Y | contingut:ANNEXES/... | 4609622,18 |

### Overrides Experts
| Camp | Font | Valor |
|------|------|-------|
| Codi ICGC | ICGC WMS 1:50k | PEcg |
| Desc. ICGC | | Conglomerats heteromètrics |
| Epoca ICGC | | Eocè |
| gamma-E | | (buit) |
| Es settlement | 2.5×Nb (Nb=45.9) | 115 |
| Resultats calculats | | (buit) |

---

## Rubí (3001631)

**Vision:** IA (3/4) — Sondeig pending

### Dades del Projecte
| Camp | Font | Valor |
|------|------|-------|
| Arquitecte | | (buit) |
| Empresa arquitecte | docs intel | JOANA MARTINEZ |
| Client / Promotor | +1 | (buit, placeholder) |
| Adreca del solar | planol+1 | Carrer de la Miranda nº 39 |
| Municipi | planol | Rubí |
| Tipus edificacio | planol | habitatge unifamiliar aïllat |
| Plantes | | (buit) |
| Sup. construida | | (buit) |
| Sup. parcella | | (buit) |
| Sup. cadastral | Cadastre WFS | 1414 |
| Alcada edificacio | | (buit) |

### Overrides Experts
| Camp | Font | Valor |
|------|------|-------|
| Codi ICGC | ICGC WMS 1:50k | NMcg |
| Desc. ICGC | | Conglomerats amb matriu sorrenca sense cimentar |
| Epoca ICGC | | Miocè |
| Es settlement | 2.5×Nb (Nb=47.6) | 119 |

---

## Linyola (4001607)

**Vision:** IA (3/4) — Sondeig pending

### Dades del Projecte
| Camp | Font | Valor |
|------|------|-------|
| Arquitecte | | (buit) |
| Empresa arquitecte | | (buit) |
| Client / Promotor | contingut:25.0616/...+3 | BUNYESC ARQUITECCTURA EFICIENT, SLP |
| Adreca del solar | fileminer:25.0616/...+2 | Carrer Clot de la Llacuna, 16, 25240 Linyola, Lleida |
| Municipi | planol | Linyola |
| Tipus edificacio | fileminer:comanda... | CONSTR HABITATGE |
| Plantes | | (buit) |
| Alcada edificacio | planol | 8.9 |

### Overrides Experts
| Camp | Font | Valor |
|------|------|-------|
| Codi ICGC | ICGC WMS 1:50k | POmgc3 |
| Es settlement | 2.5×Nb (Nb=35.1) | 88 |

---

## Vilanova de Segrià (4001671)

**Vision:** IA (3/4) — Sondeig pending

### Dades del Projecte
| Camp | Font | Valor |
|------|------|-------|
| Arquitecte | | (buit) |
| Client / Promotor | | (buit) |
| Adreca del solar | planol+1 | Calle Santa Gemma nº 4 |
| Municipi | planol | Vilanova de Segrià |
| Tipus edificacio | planol | vivienda unifamiliar |

### Overrides Experts
| Camp | Font | Valor |
|------|------|-------|
| (tot buit) | | |

---

## Anciles (4001679)

**Vision:** completada (4/4)

### Dades del Projecte
| Camp | Font | Valor |
|------|------|-------|
| Arquitecte | | (buit) |
| Client / Promotor | contingut:24.0807/... | MARIA ALBA BARRAU CASTÁN 616523792 |
| Adreca del solar | planol+1 | Calle Gral Ferraz nº20 |
| Municipi | planol | Arciles |
| Tipus edificacio | planol | viviendas adosadas |
| Plantes | fileminer:24.0807/...+1 | SÓTANO, PLANTA BAJA y PLANTA 1 |

### Overrides Experts
| Camp | Font | Valor |
|------|------|-------|
| (tot buit) | | |

---

## Alcoletge (4001670)

**Vision:** IA (3/4) — Sondeig pending

### Dades del Projecte
| Camp | Font | Valor |
|------|------|-------|
| Arquitecte | planol | David Graus Robinet |
| Empresa arquitecte | planol | 2 Graus Arquitectes Tècnics |
| Client / Promotor | fileminer:26.0049/...+1 | ALBERT SANS BONVEHI tel. 675639431 - etesnob91@gmail.com |
| Adreca del solar | planol | Carrer Girassols nº 7 |
| Municipi | planol | Alella |
| Tipus edificacio | planol+2 | habitatge unifamiliar |
| Adjacents | | (tots buits) |
| Coordenades | | (tots buits) |

### Overrides Experts
| Camp | Font | Valor |
|------|------|-------|
| (tot buit) | | |

---

## Cross-project gaps summary

| Camp | BL | Cas | Rub | Lin | Vil | Anc | Alc |
|------|:--:|:---:|:---:|:---:|:---:|:---:|:---:|
| Arquitecte | OK | - | - | - | - | - | OK |
| Client | OK | OK | - | OK | - | OK | OK |
| Plantes | ?? | - | - | - | - | OK | - |
| Sup. construida | OK | - | - | - | - | - | - |
| Sup. parcella | OK* | - | - | - | - | - | - |
| Alcada | OK | - | - | OK | - | - | - |
| gamma/c/phi/E | - | - | - | - | - | - | - |
| Calc notes | - | - | - | - | - | - | - |
| Resultats calcs | - | - | - | - | - | - | - |

*OK* = user_data (pre-existing)
**Key observation:** gamma/c/phi/E and calc results are empty across ALL projects despite the pipeline computing them.
