# Vision Refresh Results — 2026-04-06

**Executat amb:** `/g3dt-visio-projecte --force` per a cada projecte
**Metode:** Claude Code visual PDF reading (Opus 4.6 1M)
**Prompts:** Generic (sense format schemas guiant la visio)
**Branca:** `feature/concept-format-separation`

---

## Resum Global

| Projecte | Planol | DPSH Match | Sondeig | Docs | Confianca |
|----------|--------|------------|---------|------|-----------|
| Bell-Lloc | Full caixeti + taula planejament | 18/18 (100%) | 2 capes + SPT | Pressupost + DADES CLIENT | 0.95 |
| Castellar | **Cap planol** | 14/17 (82%) | Roca a 0.5m | - | 0.88 |
| Rubi | Foto WhatsApp (cataleg prefabricat) | 47/54 (87%) | Cap sondeig | - | 0.60 planol, 0.88 dpsh |
| Linyola | Full caixeti (Bunyesc) | 30/32 (94%) | - | - | 0.92 |
| Alcoletge | Pla situacio (2 Graus) | 17/23 (74%) | Cap sondeig | - | 0.90 planol, 0.70 dpsh |
| Vilanova | Emplacament (Rocar) | 28/35 (80%) | Cap sondeig | 2 SPTs | 0.92 planol, 0.75 dpsh |
| Anciles | Tipologia 7 vivendes | 101/108 (94%) | 2 sondeigs (4+7 capes) | - | 0.93 planol, 0.88 dpsh |

**Nota:** Alcoletge, Vilanova i Anciles son gitignored. JSONs existeixen localment pero no al repo.

---

## 1. 4001612 BELL-LLOC

### Planol: A.01.pdf (conf: 0.95)
- **Format:** CAD amb caixeti estandard (cantonada inferior dreta) + taula JUSTIFICACIO PLANEJAMENT
- **Arquitecte:** Jordi Bosch Novell
- **Empresa:** ARQUITECTURA BOSCH NOVELL
- **Promotor:** RAMON MITJANA SL
- **Adreça:** Carrer Mestre Ramon Ortiz, Bell-Lloc d'Urgell
- **Dimensions (de taula Projecte):**
  - Parcel·la: 995.00 m2
  - Ocupacio: 296.88 m2
  - H max: 8.38 m
  - Plantes: PB+PP
  - IEN: 397.00 m2
  - Facana: 24.07 m
- **Dimensions (de dibuix):**
  - Amplada: 24.72m (sud), Llargada: 24.57m (est)
- **Superficies per planta:** No visibles en aquesta fulla (pot ser en altra fulla)
- **Observacions:** Unic projecte amb taula de planejament completa. Referencia per a format_v1.

### DPSH: PENETROS.pdf (conf: 0.95)
- **Operari:** SINY, Equip: ML60A, Data: 1-10-25
- **P-1:** 6 lectures + refus R 1,35. **18/18 match amb Excel (100%)**
- **P-2:** 12 lectures + refus R 2,45. **18/18 match amb Excel (100%)**
- **SPT:** NO (albara confirma "Assaigs SPT: NO")
- **Observacions:** Lletra molt clara. Millor qualitat de tots els projectes.

### Sondeig: SONDEIG.pdf (conf: 0.92)
- **Operari:** Daniel Fernandez, Equip: ML76A, Data: 6-10-2025
- **S-1:** Profunditat total 1.80m
  - Capa 1: 0.00-1.60m — Grava con arena (Coronas 101 W.B)
  - Capa 2: 1.60-1.80m — Grava carbonatada (Coronas 101 W.B)
- **SPT-1:** 1.00-1.60m, cops [24, 34, 28, 30], N30=62
- **Croquis:** S1 a 4.2m/11m de les vores, cantonada C/Antoni Bellet i C/Mestre Ramon Ortiz

### Docs: docs_extracted.json
- **Pressupost:** ARQUITECTURA BOSCH NOVELL, C1, T1, 2 DPSH, 1 sondeig, 1 SPT
- **DADES CLIENT.txt:** RAMON MITJANA SL, B25771726, representant Ramon Mitjana Grifol, 696 990 400
- **Emails:** Pressupost C1 - Bell-lloc - Jordi Bosch (nom de l'arquitecte al nom del fitxer)

---

## 2. 3001621 CASTELLAR DEL VALLES

### Planol: CAP
- **No hi ha planol d'arquitecte** a la carpeta del projecte
- SmartScan no assigna rol `architect_plan`
- La informacio de l'edifici ve nomes de DADES.xls i pressupost

### DPSH: PENETROS + SONDEIG.pdf (conf: 0.88)
- **Operari:** Daniel Fernandez, Equip: ML76A, Data: 24-10-2025
- **P-1:** 5 lectures + refus R 1,08. Cota inici -4.0m. **5/5 match (100%)**
- **P-2:** 3 lectures + refus R 0,48. **Refus molt superficial.** 3 discrepancies vs Excel (columna estreta, dificil de llegir)
- **P-3:** 3 lectures + refus R 0,76. **3/3 match (100%)**
- **P-4:** 7 lectures + refus R 1,55. 1 discrepancia a -1.0 (visio 23 vs Excel 27)
- **Total:** 14/17 match (82%)

### Sondeig: PENETROS + SONDEIG.pdf pag 5 (conf: 0.85)
- **S-1:** Profunditat total 1.20m
  - Capa 1: 0.00-0.50m — Limos argilosos, con grava
  - Capa 2: 0.50-1.20m — Roca fracturada
- **SPT-1:** 1.00-1.20m — Probablement refus en roca (albara diu "Assaigs SPT: No" pero la fitxa mostra mostra)
- **Perf:** 0.50m sol + 0.70m roca dura = 1.20m total

---

## 3. 3001631 RUBI

### Planol: 25.0794/IMG-20251104-WA0015.jpg (conf: 0.60)
- **Format:** Foto WhatsApp d'un cataleg de casa prefabricada
- **Titol:** "PLANO DE PLANTA MODELO MEDITERRANEO"
- **Empresa:** Rf Mapio (prefabricats), tel 630 72 62
- **Dimensions:** 8.00m x 8.00m = 64 m2, planta unica (PB)
- **NO conte:** adreça, promotor, arquitecte, municipi, superficie parcella
- **Observacions:** Aixo NO es un planol d'arquitecte del projecte. Es una imatge de cataleg. Valor molt limitat per a extraccio.

### DPSH: 3001631 - PENETROS.pdf (conf: 0.88)
- **Operari:** Daniel Fernandez, Equip: ML76A, Data: 14-11-2025
- **P-1:** 22 lectures + refus R 4,55. 1 discrepancia a -2.8 (visio 23 vs Excel 27). **21/22 match**
- **P-2:** 17 lectures + refus R 3,58. **Multiples discrepancies** — columna P2 molt estreta, valors de -1.2 a -3.0 difícils de distingir. Excel mes fiable per P2.
- **P-3:** 15 lectures + refus R 3,13. 1 discrepancia a -2.0 (visio 44 vs Excel 49). **14/15 match**
- **SPT-1:** Pag 3, a P3, 0.60-1.20m, cops [16, 20, 20, 24], N30=40
- **Total:** 47/54 match (87%)

---

## 4. 4001607 LINYOLA

### Planol: 25.0616/Punts de Sondeig_Silvia_Jaume.pdf (conf: 0.92)
- **Format:** CAD amb caixeti complet (BUNYESC logo a baix-esquerra)
- **Arquitecte:** JOSEP BUNYESC PALACIN (Dr. Arquitecte)
- **Empresa:** BUNYESC ARQUITECTURA EFICIENT, S.L.P
- **Promotors:** SILVIA EROLES BALAGUERO + JAUME NADAL ANDREU
- **Adreça:** C. Clot de la Llacuna, 16, Linyola (25240)
- **Expedient:** 13/52/04, Data: AGOST 2025
- **Planol:** 03 PLANTA GENERAL - PARCEL·LA, escala A3 1:100
- **Dimensions (de dibuix):**
  - Parcel·la: ~34.0 x 16.75m (estimat ~569 m2)
  - Amplada: 34.04m (sud), Profunditat: 16.74m (dreta)
- **Plantes:** Pb (planta unica visible)
- **Punts de sondeig:** Marcats en vermell ("2n PUNT SONDEIG", "3r PUNT SONDEIG")
- **NO conte:** Taula de planejament (pot ser en altra fulla)

### DPSH: PENETROS.pdf (conf: 0.90)
- **Operari:** SINY, Equip: ML60A, Data: 01-10-25
- **P-1:** 14 lectures + refus R ~2.9. 1 discrepancia a -1.4 (visio 6 vs Excel 4). **13/14 match**
- **P-2:** 10 lectures + refus R 2,15. 1 discrepancia a -0.8 (visio 27 vs Excel 21). **9/10 match**
- **P-3:** 8 lectures + refus R 1,75. **8/8 match (100%)**
- **SPT1:** Pag 3, a P3, 1.0-1.15m, cops [50] (nomes primer interval, refus). Material: LLIM MARRO I TRAM D'ARGILA AMB GRAVES
- **Total:** 30/32 match (94%)

---

## 5. 4001670 ALCOLETGE

### Planol: A.01.pdf (conf: 0.90)
- **Format:** CAD amb caixeti estandard (cantonada inferior dreta, logo 2 GRAUS)
- **Arquitecte:** DAVID GRAUS ROBINAT, Arquitecte Tecnic Col·legiat N 699
- **Empresa:** 2 GRAUS, Av. del Canal 8B, 25001 Mollerussa
- **Promotor:** ALBERT SANS BONVEHI
- **Adreça:** Carrer Girasols, 7, Urbanitzacio el Roser, 25660 Alcoletge
- **Projecte:** PROJECTE DE TANCAMENT DE PORXO EN HABITATGE UNIFAMILIAR
- **Planol:** SITUACIO EN LA PARCEL·LA, fulla 2, escala 1/200, data JUNY 2022
- **Plantes:** Pb (porxo en planta baixa)
- **Dimensions:** Molt limitades — nomes 2.50m (existent) i 3.00m anotats
- **Observacions:** Projecte d'ampliacio (tancament porxo), no construccio nova. Parcel·la irregular.

### DPSH: PENETROS.pdf (conf: 0.70)
- **Operari:** AZZI - CESAR, Equip: ML60A, Data: 26-02-2026
- **P-1:** 7 lectures + refus. 2 discrepancies (torque marks obscuren digits). **5/7 match**
- **P-2:** 7 lectures + refus a -1.4. **7/7 match (100%)**
- **P-3:** 9 lectures + refus a -1.8. 4 discrepancies (lletra molt dificil). **5/9 match**
- **SPT:** A P3, 0.5-1.4m, cops [5, 9, 21, 33], N30=30. Material: LLIM MARRO
- **Total:** 17/23 match (74%)
- **Observacions:** PITJOR lletra de tots els projectes. Operari AZZI-CESAR te cal·ligrafia molt diferent de SINY/Daniel. Excel es la font fiable.

---

## 6. 4001671 VILANOVA DE SEGRIA

### Planol: 26.0050/1.0.pdf (conf: 0.92)
- **Format:** CAD amb caixeti a la part inferior (logo ROCAR a baix-dreta)
- **Arquitecte:** Jordi Carner Rocar, arquitecte tecnic, enginyer d'edificacio
- **Empresa:** ROCAR arquitectura i enginyeria, www.rocarassociats.com
- **Promotor:** Grupo CUENCA GUERRERO
- **Adreça:** C. Santa Gemma, 4 Urb. La Serra, Vilanova del Segria
- **Projecte:** AVANTPROJECTE D'UN HABITATGE UNIFAMILIAR AILLAT
- **Expedient:** E2557, Data: 24.01.2026, Escala: 1/200
- **Planol:** EMPLACAMENT, fulla 1.0
- **Dimensions (de dibuix):**
  - Parcel·la: 22.86m x 18.80m (estimat ~430 m2)
  - Edifici: ~17.85m x 7.70m (estimat ~137 m2)
  - Retranqueigs: 0.55, 2.80, 5.20, 1.60
- **Plantes:** Pb (planta unica visible, fase avantprojecte)
- **Piscina:** Visible (blau) a la parcel·la

### DPSH: PENETROS.pdf (conf: 0.75)
- **Operari:** PC - KRIM, Equip: ML60A, Data: 19-02-2026
- **P-1:** 7 lectures + refus R 1,48. 1 discrepancia major a -1.4 (visio 37 vs Excel 77). **6/7 match**
- **P-2:** 10 lectures + refus R 2,19. 1 discrepancia major a -2.0 (visio 96 vs Excel 46). Torque marks continus. **9/10 match**
- **P-3:** 18 lectures + refus R 3,78. Humitat detectada. 2 discrepancies. **16/18 match**
- **2 SPTs (pag 3):**
  - SPT1 a P3: 0.8-1.4m, cops [3, 4, 6, 5], N30=10. Material: ARGILA LLIMOSA I SORRENCA, AMB ALGUNES GRAVES
  - SPT1 a P1: 0.8-1.4m, cops [13, 10, 14, 24], N30=24. Material: SORRA FINA-MITJA, COMPACTA (A ZONES CIMENTAT)
- **Total:** 28/35 match (80%)
- **Nota:** Albara diu 5 penetrometres pero nomes 3 a la fitxa (P4/P5 a una segona fulla no inclosa?)

---

## 7. 4001679 ANCILES

### Planol: 24.0807/A01_TIPOL.pdf (conf: 0.93)
- **Format:** Planol de tipologies (4 plantes x 3 tipologies x 7 vivendes)
- **Arquitectes:** ALBA BARRAU (col. 6.408) + MIRIAM CASTEL (col. 6.703)
- **Promotor:** ANDRES AMAT y ENRIQUE M. GARDETA
- **Adreça:** C/ General Ferraz 20, ANCILES - BENASQUE (HUESCA)
- **Projecte:** ESTUDIO DE DETALLE - CASA GRANDE HCS - ANCILES
- **Escala:** A3 1/400 - 1/300, Data: MARZO 2024
- **Planol:** A01 TIPOLOGIAS VIVIENDAS PROPUESTAS
- **Plantes:** Ps + PB + P1 + Pbc (4 nivells)
- **7 vivendes en 3 tipologies:**
  - T1 (V3, V4, V5): PB ~73m2, P1 ~73m2, Pbc ~40m2, Total ~187m2
  - T2 (V1, V7): PB 102-109m2, Pbc 17-40m2, Ps ~50m2, Total 119-150m2
  - T3 (V2, V6): PB 38-40m2, P1 89-92m2, Pbc 42m2, Total 170-174m2
- **Idioma:** Castella (projecte a Arago)
- **Observacions:** Projecte mes complex. 7 habitatges adossats amb superficies detallades per unitat i planta. NO te taula de planejament.

### DPSH: PENETROS + SONDEIGS.pdf (conf: 0.88)
- **Operari:** Daniel Fernandez, Equip: ML76A, Data: 19-02-2026
- **6 assaigs DPSH** (projecte mes gran):
  - P-1: 17 lectures + refus R 3,58. 2 discrepancies menors.
  - P-2: 22 lectures + refus R 4,59. Columna densa.
  - P-3: 17 lectures + refus R 3,77.
  - P-4: 29 lectures + refus R 5,92 (assaig mes llarg de tots els projectes).
  - P-5: 6 lectures + refus R 4,18 (ubicacio S2, inici profund).
  - P-6: 17 lectures + refus R 5,70 (ubicacio S1).
- **Total:** 101/108 match (94%)

### Sondeig: PENETROS + SONDEIGS.pdf pag 5-6 (conf: 0.88)
- **S-1:** Profunditat total 2.40m, 4 capes:
  - 0.00-1.00: Limos con un bolilla (Coronas 101 W.B)
  - 1.60-2.20: Limos (86 W.B)
  - 2.20-2.30: Limos con grava (86 W.B)
  - 2.30-2.40: Granito (86 W.B) — roca al fons
  - SPT-1: 1.00-1.60m, cops [2, 3, 3, 3], N30=6 (sol molt tou)
- **S-2:** Profunditat total 3.00m, 7 capes:
  - 0.00-1.00: Limos (101 W.B)
  - 1.60-1.70: Arenas (86 W.B)
  - 1.70-1.90: Arenas con bolo (86 W.B)
  - 1.90-2.10: Pizarra (86 W.B)
  - 2.10-2.60: Arenas con gravilla (86 W.B)
  - 2.60-2.80: Granito (86 W.B)
  - 2.80-3.00: Gravas (86 W.B)
  - SPT-1: 1.00-1.60m, cops [2, 3, 3, 3], N30=6
  - MA-1: 2.80-3.00m (mostra alterada, cops illegibles)
- **Croquis (pag 7):** 6 punts DPSH + 2 sondeigs. S1-P6 (baix-esquerra), P4, P3 (centre), P2, S2-P5 (dalt-dreta), P1. Separats ~10m. Parcel·la ~50m x 14m. "Camino" al sud.

---

## Patrons Observats

### Operaris i qualitat de lletra
| Operari | Projectes | Qualitat | Fiabilitat visio |
|---------|-----------|----------|-----------------|
| SINY | Bell-Lloc, Linyola | Molt clara | 94-100% |
| Daniel Fernandez | Castellar, Rubi, Anciles | Clara | 82-94% |
| AZZI - CESAR | Alcoletge | Molt dificil | 74% |
| PC - KRIM | Vilanova | Dificil | 80% |

### Formats de planol detectats
| Format | Projectes | Caracteristiques |
|--------|-----------|-----------------|
| CAD amb caixeti + taula planejament | Bell-Lloc | Millor cas. Totes les dades. |
| CAD amb caixeti (sense taula) | Linyola, Alcoletge, Vilanova | Caixeti amb promotor/arquitecte, dimensions al dibuix |
| Tipologia multi-vivenda | Anciles | Superficies per unitat, 4 plantes, 7 habitatges |
| Foto cataleg | Rubi | Nomes dimensions basiques, cap dada projecte |
| Cap planol | Castellar | Tota la info ve d'Excel/pressupost |

### DPSH: Excel vs Visio
- **Excel sempre es mes fiable** per a valors N20 (transcripcio d'Eva, sense ambiguitat)
- La visio es util per: refus exacte (anotacio manuscrita "R x,xx"), SPT, cota inici, metadades
- Discrepancies principals: digits ambigus (3/8, 4/9, 6/0), columnes estretes, torque marks

---

*Document de referencia. Regenerar amb `/g3dt-dev-refresh-vision --all` despres de millorar prompts.*
