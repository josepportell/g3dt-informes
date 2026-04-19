# Recerca: Pràctica Geotècnica — Metodologia d'Eva + Best Practices

**Data:** 2026-02-25
**Context:** Investigació de la metodologia real d'Eva (extraient dels informes de referència + converses amb Josep) i best practices espanyoles per calibrar l'automatització G3DT

**Fonts principals:**
- 4 informes de referència G3DT (Bell-Lloc, Castellar, Rubí, Linyola) — text "Base de Càlcul"
- Converses Eva ↔ Josep (recordades)
- Recerca externa: literatura acadèmica, CTE DB SE-C, Eurocodi 7, fòrums professionals

---

## 1. Descobriments clau dels informes d'Eva

### Llibres de referència citats als 4 informes

| Ref | Llibre | Usat per |
|-----|--------|----------|
| 1 | **Carlos Crespo Villalaz** — "Mecánica de suelos y cimentaciones" | c, phi (correlacions N → paràmetres) |
| 2 | **J.M. Rodríguez Ortiz y otros** — "Curso aplicado de cimentaciones", cap. 2 | Qa (Terzaghi bicapa), assentaments |
| 3 | **Schmertmann** | Assentaments (E = 2.5×qc aïllades, 3.5×qc corregudes) |
| 4 | **Terzaghi & Peck** | Qa empírica des de SPT (N/12) |
| 5 | **Hoek & Bray (1977)** | Estabilitat de talussos (àbacs) |
| 6 | **L.I. González Vallejo** — "Ingeniería Geológica", quadre 2.12 | Expansivitat (classificació) |
| 7 | **J.A. Jiménez Salas** — "Geotecnia y Cimientos", vol. III, cap. 5 | Pressió d'inflament |

### Text exacte dels informes (idèntic als 4)

**Per c i phi:**
> "Els paràmetres de cohesió i angle de fregament intern, s'han obtingut de les **relacions que s'estableixen en el llibre "Mecánica de suelos y cimentaciones" de l'autor Carlos Crespo Villalaz**, a partir de la resistència dels materials."

**Per Qa (Terzaghi clàssic, sabates aïllades):**
```
Qd = 1.3 × c × Nc + γ × Z × Nq + 0.4 × γ × B × Nw
```
Amb F=3. "Qa = X.X Kg/cm² amb un factor de seguretat inclòs de F=3"

**Per Qa (Terzaghi-Peck, empírica, sabates >1.2m):**
```
Qadm = N/12 × S / ((B + 0.3) / B)²
```
On N=SPT, S=1 polzada (2.54cm), B=ample sabata (m)

**Per assentaments (Schmertmann):**
```
S = Ci × q × Σ(I × Δz / E)
```
On E_schmertmann = **2.5** × qc (aïllades) o **3.5** × qc (corregudes).
"El colpeig s'obtén de la relació entre N (Nspt), amb uns factors de conversió establerts per cada un dels diferents tipus de material."

### Conversió Nb → N als Excel

Factor **0.83** visible als headers dels Excel (columna Nb → N). Per Rubí: Nb=47, N=47×0.83≈39→40.

---

## 2. El que Eva ha explicat directament (converses amb Josep)

| Tema | El que va dir Eva | Implicació |
|------|-------------------|------------|
| **N20** | Usa N20 directament, no recorda N30 | Descarta hipòtesi N20→N30 (×1.5) |
| **N20 aplicació** | "Antigament només s'aplicava a sorres, però ara s'aplica a tots" | N20 és vàlid per tots els tipus de sòl |
| **E** | "Combina N amb tipus de materials" | No és fórmula pura, és judici: N20 + litologia |
| **gamma** | "Mira el CTE D.27, peso específico, agafa el valor de la taula" | Valor directe per tipus de sòl, NO interpolació amb N20 |
| **K (permeabilitat)** | "Feu servir sempre K(10⁻² a 10⁻⁴)" | Rang fix, probablement cm/s (a verificar unitats) |
| **Mètode general** | "Es basa tant com pot en les taules del CTE" i "no es busca complicacions" | Simplicitat i taules > fórmules complexes |

---

## 3. Comparació: El que Eva fa vs el que nosaltres fem

| Paràmetre | Eva fa | Font Eva | Nosaltres fem | Font nostra | Gap |
|-----------|--------|----------|---------------|-------------|-----|
| **c, phi** | Correlació N → c,phi | **Crespo Villalaz** (llibre) | Interpolació N20 → phi | **CTE Taula 4.1** | **FONT DIFERENT** |
| **E** | N20 + tipus material → judici | Crespo Villalaz? + criteri | CTE D.23 banda baixa (10% rang) | CTE D.23 | **Mètode diferent** |
| **gamma** | D.27 valor directe per litologia | **CTE D.27** ("peso específico") | D.27 interpolació N20/50 | CTE D.27 | **Mateixa font, mètode diferent** |
| **Qa** | Terzaghi F=3 + Terzaghi-Peck N/12, el menor | Rodríguez Ortiz + T&P | Terzaghi F=3 sol | Terzaghi | **Falta T&P** |
| **Assentament** | **Schmertmann** (Ci×q×Σ(I×Δz/E)) | Rodríguez Ortiz | Fórmula elàstica simple (Qa×B/E) | — | **MÈTODE DIFERENT** |
| **K30** | Valor empíric (no explicitat) | — | E/75 (granular), E/60 (roca) | Winkler | Acceptable (±5%) |
| **K (perm.)** | "Sempre 10⁻² a 10⁻⁴" | Instrucció directa | D.28 per tipus de sòl | CTE D.28 | **Valor fix vs taula** |

---

## 4. Anàlisi d'impacte — Què explica cada desviació?

### 4.1 gamma (+7-12% sistemàtic en granulars)

**Causa confirmada:** Nosaltres interpol·lem `gamma = gamma_min + (N20/50) × rang`. Eva agafa el valor directe de D.27 per tipus de sòl.

**D.27 valors per "peso específico":**

| Tipus sòl | D.27 gamma (kN/m³) | Equivalent (g/cm³) | Eva usa |
|-----------|-------------------|--------------------|---------|
| Grava | 19-22 | 1.94-2.24 | ~2.0 |
| Arena | 17-20 | 1.73-2.04 | ~2.0 |
| Limo | 17-20 | 1.73-2.04 | ~1.90 |
| Arcilla | 15-22 | 1.53-2.24 | Variable |

Eva agafa un valor fix raonable dins el rang. Per graves i sorres → 2.0 g/cm³ (part mitjana-baixa del rang). Nosaltres amb N20=40: 2.0 + (40/50)×0.3 = 2.18 g/cm³ (part alta).

**Solució:** Per granulars (graves, sorres), usar gamma=2.0 fix. Per llims, 1.90. Per roca, 2.20.

### 4.2 phi — Funciona per granulars, falla per cohesius

**Causa probable:** Nosaltres usem CTE 4.1, Eva usa Crespo Villalaz. Per granulars coincideixen (~38-39° amb N20=40). Per cohesius (Linyola, llims argilosos, N20=13), divergeixen: nosaltres 35.8° vs Eva 28°.

**Implicació:** La taula 4.1 del CTE és per sòls granulars. Crespo Villalaz té taules per tots els tipus. Caldria o bé implementar Crespo Villalaz, o bé usar una taula diferent per cohesius.

### 4.3 E — Judici professional, no fórmula pura

**Eva combina N20 + litologia.** No hi ha fórmula explícita als informes per l'E de la Taula 10. Els valors d'Eva:
- Graves amb N20 alt → E=450-650
- Llims amb N20 baix → E=100
- Roca → E>500-800

La nostra banda conservadora CTE D.23 (E_min + 10% rang) dona 469 per tot el rang "medios". Massa simple.

### 4.4 Qa — Dos mètodes, el menor

Eva calcula Terzaghi clàssic (F=3) I Terzaghi-Peck (N/12), i pren el menor. Nosaltres només fem Terzaghi clàssic. En 3/4 projectes Eva dona 3.0, suggerint que Terzaghi-Peck (N/12) dona ≤3.0 i governa.

**Verificació Terzaghi-Peck per Rubí (N=40, B≈1.2m):**
```
Qadm = 40/12 × 1 / ((1.2+0.3)/1.2)² = 3.33 / 1.5625 = 2.13 kg/cm²
```
Hmm, més baix que 3.50 d'Eva. Potser B diferent o correccions addicionals. **Pregunta oberta.**

### 4.5 Assentament — Schmertmann vs elàstic simple

**Descobriment major:** Eva usa Schmertmann, nosaltres usem una fórmula simplificada. Schmertmann incorpora:
- Factor d'empotrament (Ci)
- Distribució de tensions en profunditat (I)
- E variable per capes
- Profunditat d'influència 2B (aïllades) o 4B (corregudes)

Això explica les diferències d'assentament (0.72 vs 1.50 a Rubí).

---

## 5. Permeabilitat K — La instrucció d'Eva

Eva va dir: "Feu servir sempre K(10⁻² a 10⁻⁴)".

Als informes, K s'expressa en m/s:
- Bell-Lloc (graves): 10⁰ - 10⁻² m/s
- Rubí (graves): ~10⁻¹ m/s
- Linyola Niv1 (llims): 10⁻³ - 10⁻⁵ m/s

El rang "10⁻² a 10⁻⁴" podria ser:
- **m/s**: cobriria graves fines a llims (rang molt ampli)
- **cm/s**: 10⁻² cm/s = 10⁻⁴ m/s, 10⁻⁴ cm/s = 10⁻⁶ m/s → llims a argiles

**No afecta càlculs de Qa, E ni assentament.** Afecta només §4.2 (drenatge) i la presentació a la Taula 10. Resoluble un cop confirmades les unitats.

---

## 6. Recerca externa — Troballes rellevants

### SPT → E (4 correlacions comparades)

| Correlació | Fórmula | Per N20=40 | Comentari |
|-----------|---------|-----------|-----------|
| CTE D.23 (rang medios) | 40-100 MN/m² | 408-1020 kg/cm² | Rang massa ampli |
| D'Appolonia (sorres precons.) | E = 540+13.5×N | 1080 kg/cm² | Massa alt |
| Bowles | E = 10×(7.5+0.5×N) | 275 kg/cm² | Massa baix |
| Schmertmann (E=2.5×qc) | Variable amb qc | Variable | Eva l'usa per assentaments |

Cap correlació sola reprodueix els valors d'Eva (450-650). Confirma que Eva usa criteri professional.

### Qa — Topall pràctic confirmat

La recerca confirma que **Qa ≈ 3.0 kg/cm²** és un topall habitual per fonamentacions residencials a Espanya. La fórmula N/12 és preferida sobre N/8 per la seva naturalesa conservadora.

### gamma — D.27 directe

Confirmat que la pràctica habitual és agafar valors tabulats de D.27, no interpolar amb N.

---

## 7. Preguntes que queden per Eva (actualitzades)

Després d'analitzar els informes i recordar converses, **algunes preguntes ja estan resoltes**:

| # | Pregunta | Estat |
|---|---------|-------|
| ~~1~~ | ~~N20 → N30~~ | **Substituïda per pregunta sobre Nb→N (0.83)** |
| 2 | Qa — topall o càlcul? T. clàssic vs T&P? | **AL CORREU** |
| ~~3~~ | ~~Gamma — d'on~~ | **RESOLT: D.27, peso específico, valor directe per litologia** |
| 4 | E — com hi arriba | **AL CORREU** |
| ~~5~~ | ~~Assentament — mètode~~ | **RESOLT: Schmertmann (dels informes)** |
| ~~6~~ | ~~Cohesió mínima~~ | **Baixa prioritat, no al correu** |
| 7 | c i phi: Crespo Villalaz, quina taula? Especialment cohesius | **AL CORREU (clau per Linyola)** |
| 8 | Nb→N: factor 0.83, quin valor usa per buscar paràmetres? | **AL CORREU (possible causa de desviacions)** |

**Troballes de la recerca sobre correlacions SPT→phi:**

Per granulars, la correlació Peck (1974) `φ = 27.1 + 0.30N - 0.00054N²` dona valors quasi idèntics a CTE 4.1 i Eva. **No cal canviar res per granulars.**

Per cohesius, **NO existeix correlació fiable SPT→phi**. Eva usa Crespo Villalaz (taules per tipus de sòl + compacitat), no una fórmula pura. La nostra CTE 4.1 és per granulars i falla per llims/argiles (Linyola: 35.8° vs Eva 28°).

---

## 8. Prioritats d'implementació (ordenades per impacte)

| Prioritat | Canvi | Impacte | Dificultat |
|-----------|-------|---------|------------|
| **1** | **gamma: valor fix per litologia** (2.0 granulars, 1.90 llims, 2.20 roca) | Elimina biaix +7-12% | Fàcil |
| **2** | **Qa: afegir Terzaghi-Peck (N/12)** i prendre el menor dels dos | Pot explicar topall 3.0 | Mitjà |
| **3** | **Assentament: implementar Schmertmann** | Elimina discrepàncies grans | Complex |
| **4** | **phi per cohesius: Crespo Villalaz o taula alternativa** | Corregeix Linyola (+28%) | Mitjà (cal llibre) |
| **5** | **E: afinar criteri N20+litologia** | Redueix dispersió | Complex (criteri subjectiu) |
| **6** | **K permeabilitat: rang fix** | Cosmètic | Fàcil |

**Nota:** Prioritats 1 i 2 es poden fer sense esperar resposta d'Eva. Prioritats 3-5 necessiten o bé la resposta d'Eva o bé el llibre de Crespo Villalaz.

---

*Document de treball intern — base per correu a Eva, febrer 2026*
*Actualitzat amb troballes dels informes de referència i converses Eva ↔ Josep*

---

## 9. Apèndix — Taules Crespo Villalaz (recercat 2026-04-17)

Font del llibre: Carlos Crespo Villalaz, *"Mecánica de suelos y cimentaciones"*, Limusa (5ª-6ª ed., ~2004). Les taules següents es troben al **Cap. 20 — Capacidad de carga** (Tabla ~20.3) i/o **Cap. 33 — Tablas generales** (Tabla 33.2), pp. 280-295 de la 5ª edició. Reproduïdes a diversos informes geotècnics colombians/equatorians i espanyols.

### 9.1 Taula principal φ — sòls cohesius (arcilles i llims)

Etiquetes: primer l'espanyola (font original Crespo), després la catalana
(ús professional d'Eva, acord femení amb "consistència").

| Consistència (es / ca)         | N (SPT) | qu (kg/cm²) | c = qu/2 (kg/cm²) | φ (°) |
|--------------------------------|---------|-------------|-------------------|-------|
| muy blanda / molt tova         | < 2     | < 0.25      | < 0.125           | 0     |
| blanda / tova                  | 2-4     | 0.25-0.50   | 0.125-0.25        | 0-5   |
| media / mitjana                | 4-8     | 0.50-1.00   | 0.25-0.50         | 5-10  |
| firme / ferma                  | 8-15    | 1.00-2.00   | 0.50-1.00         | 10-15 |
| muy firme / molt ferma         | 15-30   | 2.00-4.00   | 1.00-2.00         | 15-20 |
| dura / dura                    | > 30    | > 4.00      | > 2.00            | 20-25 |

**Notes de la font:**
- φ són valors efectius (φ'), drained conditions.
- c' és estimació de cohesió no drenada.
- **Per argila limosa / llim pur, restar 2-5° del valor de φ respecte a argila pura.**
- Rangs reflecteixen variabilitat per plasticitat (IP).

### 9.2 Taula Hunt (via Crespo) — consistència → qu → c → φ

Taula alternativa/reproduïda al mateix capítol, variant amb límits de φ lleugerament diferents:

| Consistència (es / ca)         | qu (kg/cm²) | c (kg/cm²) | φ (°) |
|--------------------------------|-------------|------------|-------|
| muy blanda / molt tova         | < 0.25      | < 0.125    | 0     |
| blanda / tova                  | 0.25-0.50   | 0.125-0.25 | 0-4   |
| plástico / plàstica            | 0.50-1.00   | 0.25-0.50  | 4-8   |
| firme / ferma                  | 1.00-2.00   | 0.50-1.00  | 8-12  |
| muy firme / molt ferma         | 2.00-4.00   | 1.00-2.00  | 12-18 |
| dura / dura                    | > 4.00      | > 2.00     | 18-25 |

### 9.3 Cross-check amb altres fonts espanyoles

- **González de Vallejo** (*"Geología aplicada"*, Cap. 5): taula similar, φ 0° (blanda) a 22° (dura) per argiles. Concordança ±2° amb Crespo.
- **Jiménez Salas** (*"Geotecnia"*, Vol. 5, Tabla 14.2): φ per cohesius des N, ex. N=4-8 → φ=6-12°.
- **Calavera** (*"Cimentaciones"*): referència directa a Crespo/Hunt per φ en llims/argiles.

### 9.4 Impacte sobre la pipeline G3DT

- **CTE DB-SE-C 4.1** (la nostra correlació actual per cohesius) **sobreestima φ ~20-28%** respecte a Crespo per N baixos. Exemple: N=4 → CTE ~25° vs Crespo ~5°. Això explica la desviació de Linyola (+28% vs Eva).
- **Però** per Linyola (Nb=22.6, llim argilós, Eva φ=28°), Crespo pur donaria φ=15-20° (rang "muy firme"), massa baix. Amb ajust de -3° per llim argilós, seria encara més baix. **Eva sembla usar Schmertmann (1970) amb factor n de gra**, no Crespo pur. Veure `Spt-correlacions.doc`: n=1.25 per sandy silts, n=2 per silty sands, n=2.5 per slightly silty sands.

**Conclusió per a implementació:**
1. **Per cohesius purs (argiles)**: Crespo/Hunt → φ = f(N) per consistència.
2. **Per llims i llim-argiles (materials intermedis)**: Schmertmann-(n), amb n=1.25-2 segons % de fins. **Aquesta és probablement la metodologia d'Eva per Linyola.**
3. **Per granulars**: manté CTE 4.1 o Schmertmann-(n) amb n=2.5.
4. **Per cohesió c (tots els sòls cohesius)**: Hunt table → c = f(N).

### 9.5 Fonts citades

- `libreriaingeniero.com/2018/07/mecanica-de-suelos-y-cimentaciones.html` — índex del llibre i PDF 5ª ed.
- `espacacias.com/.../06.-ESTUDIO-GEOTECNICO-1.pdf` — reprodueix la taula principal
- `repositorio.puce.edu.ec/.../` — tesi equatoriana que cita Crespo directament
- `cdnfomento.blob.core.windows.net/.../18100_a12_gcim.pdf` — document Fomento (Espanya) amb referència a Crespo
- `estudiosgeotecnicos.info/index.php/spt-suelos-cohesivos/` — article online amb les mateixes correlacions
