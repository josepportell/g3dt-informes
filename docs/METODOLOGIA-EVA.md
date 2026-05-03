---
title: "Metodologia d'Eva"
subtitle: "síntesi dels informes reals"
date: "30 Abril 2026"
author: "Eficients.cat"
lang: ca
titlepage: true
titlepage-color: "0066cc"
titlepage-text-color: "ffffff"
titlepage-rule-color: "ffffff"
titlepage-rule-height: 2
toc: false
toc-own-page: false
colorlinks: true
linkcolor: "0066cc"
urlcolor: "0066cc"
header-left: "Metodologia d'Eva"
header-center: ""
header-right: "30 Abril 2026"
code-block-font-size: \footnotesize
header-includes:
  - \DefineVerbatimEnvironment{Highlighting}{Verbatim}{xleftmargin=2em,fontsize=\footnotesize}
  - \clearpairofpagestyles
  - \ihead{Metodologia d'Eva}
  - \ohead{30 Abril 2026}
  - \cfoot{\thepage}
---

**Font**: els 7 informes signats d'Eva (format `*_informe.pdf` als
directoris `reference-material/*/PDF/`).
**Data**: 2026-04-17 (lectura inicial).
**Estat**: document viu — cada nova troballa s'hi afegeix.

Aquest fitxer documenta la metodologia real d'Eva tal com s'explica als seus
informes signats. Serveix de base per auditar el pipeline G3DT i prioritzar
correccions.

---

## 1. Fonts bibliogràfiques citades textualment als informes

### 1.1 Crespo Villalaz — per cohesió (c) i angle de fricció intern (φ)

Cita exacta (apareix als 7 informes):

> *"Els paràmetres de cohesió i angle de fregament intern, s'han obtingut de les
> relacions que s'estableixen en el llibre «Mecànica de suelos y cimentaciones»
> de l'autor Carlos Crespo Villalaz, a partir de la resistència dels materials.
> Tan la cohesió com l'angle de fregament intern són **valors efectius o llarg
> termini**."*

**Implicacions:**
- φ i c són **valors efectius (drenats)**, no no-drenats.
- Entrada a les taules = "resistència dels materials" (probablement N-SPT
  per cohesius, Dr per granulars).
- **Helpers G.2a ja implementen les taules principals de Crespo** (cohesius
  pures). Les taules per materials transicionals (llims sorrencs, argila
  limosa) encara requereixen confirmació d'Eva.

### 1.2 Rodríguez Ortiz — per tensió admissible en sòls heterogenis

Cita exacta (apareix a Alcoletge; probablement a tots on el perfil és bicapa):

> *"donat que partim de la premissa que els sòls sota la cota de fonamentació
> són heterogenis, a efectes de càlcul s'aplica el mètode que proposa el
> llibre de «Curso aplicado de cimentaciones», en el seu capítol 2, de
> J. Maria Rodríguez Ortiz y otros. En aquest llibre es proposen pel càlcul
> de tensions admissibles de fonamentacions superficials [...] els **criteris
> de trencament dels terrenys bicapa**."*

**Implicacions (divergència important amb el nostre pipeline):**
- Eva **no aplica Terzaghi mono-capa** quan el perfil és heterogeni.
- Redueix el perfil a **2 capes** mitjançant **mitjana ponderada** de les capes
  sota la superfície de trencament.
- Aplica **correccions per la relació** entre les característiques de
  resistència de les dues capes.
- Pren la superfície de trencament **més desfavorable**.
- **El nostre pipeline no fa això** — aplica Terzaghi mono-capa directament.
  Això és candidat a task G.5 (nou).

### 1.3 Schmertmann (1970) — per assentaments

Cita exacta (apareix als 7 informes):

> *"E = mòdul de deformació definit per Schmertmann, que s'obté de multiplicar
> **2.5 en el cas de sabates aïllades i 3.5 en el cas de corregudes**, pel
> colpeig del penetròmetre estàtic. Aquest colpeig s'obté de la relació entre
> N (Nspt), amb uns **factors de conversió establerts per cada un dels
> diferents tipus de material**."*

Equació de Schmertmann (transcrita literalment a les cites completes):

> *"Els assentaments queden limitats a una profunditat de **2B** en el cas de
> sabates aïllades o llosa de fonamentació i **4B** en el cas de sabates
> corregudes."*

**Implicacions:**
- El factor "n" de l'`Spt-correlacions.doc` NO és per φ — és per **conversió
  N → qc**.
- La cadena és: `qc = n_factor × N` → `E = shape_factor × qc` (on shape =
  2.5 aïllada, 3.5 correguda) → integració Iz fins a 2B (aïllades) o 4B
  (corregudes).
- **Helpers G.2c rescoped (2026-04-17)** implementen aquesta cadena:
  `nspt_to_qc`, `schmertmann_E_from_qc`, `schmertmann_E_from_nspt`.

### 1.4 Terzaghi + Terzaghi-Peck — per tensió de trencament (fórmula mono-capa)

Fórmules textuals:

Sabates corregudes:
```
Qd = C · Nc + γ · Z · Nq + 0.5 · γ · B · Nw
```

Sabates aïllades:
```
Qd = 1.3 · C · Nc + γ · Z · Nq + 0.4 · γ · B · Nw
```

**Nc, Nq, Nw** = factors de càrrega des de φ (taules de Terzaghi).

Per terrenys granulars/sorrencs, fórmula simplificada (Terzaghi-Peck):

Sabates < 1.2 m:
```
Qadm = N × S / 8
```

Sabates > 1.2 m:
```
Qadm = N / 12 × S / ((B + 0.3) / B)²
```

**Implicacions:**
- Aquestes són fórmules **mono-capa** — Eva les aplica **capa a capa** i
  després aplica el criteri bicapa de Rodríguez Ortiz (§1.2) per combinar
  les capes dels dos estrats.
- El nostre pipeline implementa Terzaghi mono-capa correctament, però
  **no implementa el pas de combinació bicapa**.

---

## 2. Paràmetres geomecànics per litologia (confirmats per MEMORY.md)

| Material | γ (gr/cm³) | c (kg/cm²) | φ (°) | E (kg/cm²) | Qa cap (kg/cm²) |
|---|---|---|---|---|---|
| Graves i sorres | 2.0 | 0.0-0.05 | 38-39 | 450-650 | 3.0 (soft) / 3.5 (dense) |
| Llims argilosos | 1.90 | 0.05 | 28 | 100 | 3.0 |
| Roca (bretxes, lutites, carbonates) | 2.20 | 1.0 | 30-35 | >500-800 | 3.0-4.5 |

Font: MEMORY.md + corroborat amb els informes signats.

---

## 3. Questions encara obertes (per G.3 email a Eva)

### 3.1 Quina taula de Crespo per llim argilós?

Crespo té diverses taules (cohesius purs vs granulars vs mixtes). Per
Linyola (llim argilós, Nb=22.6):
- Taula cohesius pures: φ ≈ 15-20° (muy_firme)
- φ d'Eva: 28°

Aquest gap (8°) suggereix que Eva fa servir una taula **intermèdia** de
Crespo, o aplica un ajust per argila limosa/llim sorrenc. Possibilitats:
- Taula de Crespo per "arenes limoses" o "llims sorrencs" (granular-ish)
- Ajust manual basat en % de fines i índex de plasticitat
- Taula de Hunt via Crespo per qu, que Eva després converteix a c via c=qu/2
  i φ via correlació

**Al correu G.3**: demanar la citació exacta (capítol, taula, pàgina).

### 3.2 Aplicació del criteri bicapa de Rodríguez Ortiz

- En quins projectes ha aplicat Eva el criteri bicapa vs mono-capa?
- Com determina la "superfície de trencament més desfavorable"?
- Quin factor de reducció aplica entre capes?
- Té disponible el capítol 2 del llibre per poder-lo llegir o digitalitzar?

### 3.3 Factor n per projecte (cadena N→qc→E)

Confirmació: quin valor de n ha utilitzat per cada un dels 7 projectes?
- n = 2.5 (sorres lleugerament llimoses)
- n = 2.0 (sorres llimoses)
- n = 1.25 (llims sorrencs)
- Algun valor intermedi?

### 3.4 Casos especials

- **Bell-Lloc** ("carbonatades"): es tracten com a roca (c=1.0, cap 3.0) o
  com a dens granular (c=0, cap 3.5)? Els valors d'Eva són ambigus.
- **Alcoletge**: com es tria l'Nb quan el perfil té capa superficial tova i
  refús profund? (Nb_avg=9.4 però Eva dóna Qa=3.5 → dens.)

---

## 4. Gap entre pipeline i metodologia d'Eva (a 2026-04-17)

| Pas | Pipeline G3DT | Eva (via informes) | Estat |
|---|---|---|---|
| γ (pes volumètric) | CTE D.27 per litologia | D.27 + taules Crespo | ✅ Coincideix |
| c (cohesió) | `soil_type_to_cohesion` (valor pla) | Taules Crespo + Hunt | ⚠️ Simplificat — G.2c-wire |
| φ (angle fricció) | CTE 4.1 per granulars, valor fix per cohesius | Taules Crespo (taula concreta per confirmar) | ❌ G.3 bloquejat + G.2c-wire |
| Nc, Nq, Nw | Taules Terzaghi interpolades | Taules Terzaghi (implícites) | ✅ Coincideix |
| Qa mono-capa | Terzaghi amb shape factors 1.3/0.4 | Terzaghi idèntic + Terzaghi-Peck granular | ✅ Coincideix |
| Qa multi-capa | **No implementat** | **Bicapa Rodríguez Ortiz Cap. 2** | ❌ **Gap major** — task G.5 (nou) |
| E (mòdul) | CTE D.23 per N | `E = shape_factor × n_factor × N` (Schmertmann) | ⚠️ Diferent fórmula — G.2c-wire |
| Assentament | Schmertmann Iz | Schmertmann Iz fins a 2B/4B | ✅ Coincideix en mètode |
| K30 (balast) | E/75 granular, E/60 roca | (sense cita explícita encara) | ⚠️ No confirmat per informes |

---

## 5. Altres fonts i mètodes trobats al lectura sistemàtica (G.6, 2026-04-17)

### 5.1 Acceleració sísmica — NCSE-02 complet (confirmat)

Fórmula textual (Castellar, aplicable a tots):

```
AC = S · AB · ρ
```

On:
- **AB** = acceleració sísmica bàsica (del Mapa de Perillositat Sísmica de la NCSE-02)
- **ρ** = coeficient adimensional de risc (1.0 importància normal, 1.3 importància especial)
- **S** = coeficient d'amplificació del terreny:
    - Si ρ·AB < 0.1g: `S = C/1.25`
    - Si 0.1g ≤ ρ·AB < 0.4g: `S = C/1.25 + 0.33·(ρ·AB/g - 0.1)·(1 - C/1.25)`
    - Si ρ·AB ≥ 0.4g: `S = 1.0`
- **C** = coeficient del terreny (depèn de característiques geotècniques — taula NCSE-02)

**Valors d'exemple trobats:**
- Castellar del Vallès: AB = 0.04 g

**Implicacions:** el càlcul és **totalment reproducible**. El pipeline G3DT
pot (i probablement ja ho fa) automatitzar aquesta fórmula amb la taula
municipal d'AB + la classificació del terreny per C.

### 5.2 Radó — CTE DB HS-6 (RD 732/2019) + Apèndix B

Cita textual:

> *"En el DB Secció HS-6 Protección frente a la exposición al radón del CTE
> (RD 732/2019) es determina que es necessari limitar el risc previsible
> d'exposició dels usuaris a concentracions inadequades de radó en edificis
> tancats situats en els termes municipals inclosos a l'apèndix B del
> document. [...] Per a limitar el risc d'exposició, s'estableix un nivell
> de referència per a la mitjana anual de concentració de radó a l'interior
> dels mateixos de **300 Bq/m³**. Les solucions [...] segons la localització
> del terme municipal en **ZONA 1 o en ZONA 2** són: [...]"*

**Implicacions:** Mapa municipi → zona radó (I, II, o no inclòs) és una
simple **taula de mapping** publicada al Apèndix B del RD 732/2019.
Totalment reproducible un cop incorporada la taula.

### 5.3 Excavabilitat — narrativa qualitativa, no fórmula

Cita textual (Castellar):

> *"L'excavació dels trams superficials dels materials del nivell 1 es
> realitzarà fàcilment amb una retroexcavadora convencional. En canvi, en
> profunditat, [...] el rendiment de la màquina podria disminuir, essent
> possiblement necessària la utilització de maquinaria més contundent tipus
> «martell pneumàtic»."*

**Implicacions:** **No hi ha un mètode quantitatiu.** Eva produeix prosa
descriptiva basada en la classificació del material (nivell, tipus,
alteració, RMR si n'hi ha). Això és terreny per a un **generador de text
basat en regla** al pipeline — no per un càlcul numèric.

### 5.4 Estabilitat de vessants — Hoek & Bray (1977)

Cita textual (Castellar, únic projecte amb pendent):

> *"El mètode ràpid de càlcul utilitzat per les recomanacions de talussos és
> el proposat per Hoek & Bray (1977), utilitzant els valors numèrics de
> cohesió, angle de fregament i densitat exposat anteriors."*

Premisses explícites:
- Pendent existent 20-25°
- Talussos sense nivell freàtic
- Factor de seguretat F = 1.8 (objectiu)
- Columna de materials dominada pel 1er nivell

**Implicacions:** **Hoek & Bray 1977 abacs** (no fórmula tancada). Requereix
digitalització dels abacs si es vol automatitzar, com el Schmertmann chart.
Poc prioritari — només aplica a un dels 7 projectes (Castellar).

### 5.5 Empentes de terres — recomanacions narratives, no fórmula

Cita textual (Castellar i Rubí):

> *"Pel dimensionament del murs que es projectin i pel càlcul de les
> empentes de terres caldrà tenir en compte els paràmetres geomecànics dels
> materials del 1er nivell que es considera el més desfavorables. Cal tenir
> en compte que en el trasdors del mur, caldrà instal·lar un correcte
> drenatge per a evitar que s'acumuli aigua i es produeixi un sobrecàrrega
> en el seu trasdors."*

**Implicacions:** **Eva NO calcula empentes**. Dóna només recomanacions
sobre quins paràmetres utilitzar (cohesió, φ, densitat del nivell més
desfavorable) i requeriments constructius (drenatge). El càlcul real el fa
l'arquitecte/estructurista amb aquests paràmetres. El nostre pipeline
probablement genera un text similar.

### 5.6 Permeabilitat K — rangs directes per material

Cita textual (Castellar):

> *"A continuació s'exposen els valors del coeficient de permeabilitat (K)
> associats als materials detectats al subsòl del solar: [taula]"*

Rangs trobats als informes:
- **10⁻¹ – 10⁻³ m/s**: graves i sorres
- **10⁻³ – 10⁻⁵ m/s**: sorres fines / sorres llimoses
- **10⁻⁵ – 10⁻⁷ m/s**: bretxes amb lutites i gresos (rocs semi-impermeables)

**Implicacions:** **K és un rang discret per tipus de material**, no un
càlcul. Taula de lookup trivial d'implementar. Confirma la línia a MEMORY:
"Eva va dir: Feu servir sempre K(10⁻² a 10⁻⁴)" és probablement una
simplificació d'Eva per defaults granulars.

### 5.7 Agressivitat al formigó — Codi Estructural 21 (RD 470/2021)

Cita textual:

> *"Per a classificar el grau d'agressivitat dels materials front al formigó
> segons la taula de classificació de l'agressivitat química del **Código
> Estructural 21 (Real decreto 470/2021, de 29 de junio, publicat al BOE
> amb data 10/08/21)**, a més a més del contingut en sulfats es deurà
> realitzar un assaig d'acidesa de **Baumann-Gully**, tot i que en aquest
> cas, i degut a les característiques dels materials no es considera
> necessària realitzar aquest assaig."*

Assaig de sulfats: **UNE 83963:2008**.

**Implicacions:**
- Taula de classificació del Codi Estructural 21 — **reproducible**.
- Baumann-Gully és **opcional** (Eva sovint el salta amb justificació).

### 5.8 K30 (coeficient de balast) — valors directes, probablement via E

**Dades empíriques observades als informes:**
- Castellar (roca/bretxes): K30 = 8.00 kg/cm³ (per llosa)
- Rubí (granular): K30 = 6.0 kg/cm³

**Forma de presentació als informes:**

> *"Si s'optés per una fonamentació amb llosa, el valor de coeficient de
> balast, referit a la placa de 30x30, es podrà adoptar un valor de
> K30 = 8.00 kg/cm³."*

**Implicacions:** Eva **no cita una fórmula explícita** (E/60, E/75) als
informes. Els valors són assignats directament. El nostre pipeline usa
E/60 (roca) / E/75 (granular), que ha donat deviacions del +4% (vegeu
MEMORY deviation matrix). La coherència entre E/75 i els valors d'Eva
suggereix que **Eva sí que fa servir aquesta relació, però internament**
(de Jiménez Salas 1981 segons Spt-correlacions.doc §4). Pipeline correcte.

### 5.9 Aplicació del bicapa de Rodríguez Ortiz — CONDICIONAL, no sistemàtica

**Actualització crítica sobre §1.2:** el bicapa NO s'aplica a cada projecte
automàticament. Exemple Alcoletge (projecte amb perfil bicapa clar):

Paràmetres geomecànics declarats:
| Nivell | Nb | N | γ | c | φ | E |
|---|---|---|---|---|---|---|
| 1r: Sorres argiloses de rebliment | 5-0 | -- | 1.80 | 0.00 | 28° | 50 |
| 2n: Lutites i sorrenques alterades | R | 20 | 2.00 | 1.00 | 30° | >400 |

**Qa declarat per Eva: 3.50 kg/cm²** — valor basat **només en el 2n nivell**,
no una mitjana ponderada. Citat textualment:

> *"Un cop realitzada l'excavació afloraran superficialment els materials
> del primer nivell descrit, que degut a les seves propietats geomecàniques
> **es descarta totalment per a recolzar-hi qualsevol element de
> fonamentació**. La fonamentació haurà de quedar recolzada en els materials
> del segon nivell que es detecta entre 1.20 i 1.40 metres. [...] mitjançant
> sabates [...] recolzada sobre els materials del segon nivell sanejat, es
> podrà adoptar una tensió de treball de: Qa = 3.50 Kg/cm² amb un factor de
> seguretat inclòs de F=3"*

**Implicacions (revisió de G.5):**

El "criteri bicapa de Rodríguez Ortiz" que Eva cita a la part metodològica
**és condicional**:
- Quan les dues capes contribueixen a la superfície de trencament → bicapa
  reduction amb mitjana ponderada.
- Quan el 1r nivell és tan feble que es descarta → **skip-top-layer**, usar
  només el bearing layer (com Alcoletge).
- Quan el projecte preveu excavació fins a un nivell competent → usar aquest
  nivell directament.

**Això simplifica G.5 significativament.** L'algoritme probable:
1. Identificar la "competent layer" (on va la fonamentació).
2. Si la capa superficial pot ser sanejada/eliminada → usar competent layer
   directament (nostre pipeline + G.1 funciona).
3. Si hi ha layering real dins la bearing zone → bicapa weighted-average
   (nou; encara pendent del Cap. 2 Rodríguez Ortiz).

### 5.10 φ = 28° per a sorres argiloses — patró repetit

**Ambdós projectes amb llims/sorres argiloses tenen el mateix φ = 28°:**
- Linyola: llim argilós, Nb ≈ 22.6, φ = 28°
- Alcoletge 1er nivell: sorres argiloses, Nb ≈ 6 (molt feble), φ = 28°

**Implicacions:** Eva sembla usar un **valor fix de φ = 28° per a
materials transicionals cohesius-granulars** amb Nb baix-mitjà,
independentment del valor exacte d'Nb. Això és consistent amb un read
d'una taula Crespo específica per a "sòl cohesiu-sorrenc / llim sorrenc"
que dóna φ ≈ 28° independent de N (o amb molt poca variació).

**Hipòtesi per validar a G.3**: existeix a Crespo una taula per a
**materials mixtes (llim sorrenc / sorra llimosa / sorra argilosa)** amb
φ ≈ 28° com a valor estàndard. El nostre `crespo_phi_cohesive` per
materials cohesius purs dóna 15-20° per Nb=22.6 (band "muy firme"); per
mixtes necessitem una taula diferent.

**Simplificació per G.2c-wire**: si Eva confirma que per a materials
mixtes usa un valor fix de 28°, podem implementar-ho com una condició
especial en `nspt_to_phi` quan `soil_type in ('cohesive', 'silty_clay',
'clayey_sand')` sense complexitat addicional de Schmertmann-n.

## 6. Capítol 2 de Rodríguez Ortiz — contingut extret (2026-04-17)

PDF arxivat: `docs/research/books/Rodriguez-Ortiz-Curso-aplicado-de-cimentaciones.pdf`.
Capítol 2 cobreix pàgines 41–88 del llibre.

### 6.1 Fórmula general de Terzaghi (Cuadro 2.3 — factors Nc/Nq/Nγ)

```
q_h = c·N_c + q·N_q + 0.5·γ·B·N_γ        (faja infinita / strip)
```

Factors tabulats per φ ∈ [0°, 50°]. Exemples de la taula:

| φ (°) | Nc | Nq | Nγ |
|---|---|---|---|
| 0 | 5.14 | 1.00 | 0.00 |
| 10 | 8.35 | 2.47 | 1.22 |
| 20 | 14.83 | 6.40 | 5.39 |
| 25 | 20.72 | 10.66 | 10.88 |
| 30 | 30.14 | 18.40 | 22.40 |
| 35 | 46.12 | 33.30 | 48.03 |
| 40 | 75.31 | 64.20 | 109.41 |

**Discrepància amb els informes d'Eva (§1.4):**
- Llibre: `q_h = 1.2·c·N_c + q·N_q + 0.3·B·γ·N_γ` per zapata quadrada/circular
- Eva informes: `Qd = 1.3·c·N_c + γ·Z·N_q + 0.4·γ·B·N_w` per sabates aïllades

Els factors de forma d'Eva (**1.3 i 0.4**) són els de Terzaghi-1943 original
(encara comunament usats a la pràctica espanyola). Els del llibre (**1.2 i
0.3**) són de versions posteriors Vesic/Brinch Hansen. **Diferència pràctica:
~2% en q_h.** Eva és lleugerament més optimista; cap risc en el nostre pipeline.

### 6.2 Bicapa — Fig. 2.9 (G.5 CLAU)

**Cita textual de pàgina 49:**

> *"Cuando en la zona de influencia de la cimentación existen dos o más
> capas de terrenos diferentes ya no son aplicables los métodos antes
> expuestos. Un procedimiento aproximado puede ser combinar las presiones
> de hundimiento obtenidas para cada capa, suponiendo que ella sola
> constituye el terreno de apoyo. [...] Otro método aproximado es el de la
> fig. 2.9, donde q_h1 es la presión de hundimiento que se obtendría si todo
> el terreno fuera T1, y q_h2 análogamente para T2."*

**Fórmules explícites de Fig. 2.9:**

**Cas a) q_h1 > q_h2**  *(capa forta sobre capa feble)*:
```
t/B > 0.7 :  q_h = q_h2
t/B < 0.7 :  q_h = q_h1 − (q_h1 − q_h2)/0.7 · t/B
```

**Cas b) q_h1 > q_h2**  *(mateix ordre de capes, geometria diferent)*:
```
t/B ≤ 0.2  :  q_h = q_h2
0.2 < t/B < 1 :  q_h = q_h2 − (q_h1 − q_h2)/0.8 · (t/B − 0.2)
t/B > 1    :  q_h = q_h1
```

On **t** = espessor de la capa superior (distància de la fonamentació a la
interfície entre capes).

**Subseccions especialitzades (més precises que Fig. 2.9):**

- **6.1.a) Dos estrats argilosos** (c₁, c₂; φ=0):
  - Si superior més tova: `q_h = c₁·N_m + q`, amb N_m de Vesic (1970),
    Cuadro 2.4 (funció de c₂/c₁ i B/H).
  - Si superior més resistent: Brown & Meyerhof (1969):
    `N_m = 2(B+L)H/BL + (c₂/c₁)·s_c·N_c`
  - **Cuadro 2.4** té la taula completa de N_m per c₂/c₁ ∈ [1, ∞] i
    B/H ∈ [2, ∞].

- **6.1.b) Dos estrats granulars** (Hanna 1981):
  ```
  q_h = q_b + γ₁·H²·(1 + 2D/H)·K_s·tg(φ₁)/B − γ₁·H
  q_b = 0.5·γ₂·B·N_γ2 + γ₁·(H+D)·N_q2
  ```
  K_s (coeficient resistència al punzonament) dels gràfics Fig. 2.12 i 2.17.

- **6.1.c) Dos estrats de diferent naturalesa**:
  - Estrat tou sobre substrat rígid: Jürgenson (1934) + Mandel/Salençon
    (Fig. 2.14 per N'γ).
  - Capa resistent sobre terra tova (Tcheng 1957 / Vesic 1970):
    ```
    q_h = q_hc / [1 − (2H/B)·sen(φ)/tg(45+φ/2)·exp(-(π/2−φ)·tgφ)]
    ```
    Vàlid per H ≤ 1.5B. Despreciable si H ≥ 3.5B.

### 6.3 Terzaghi-Peck per arenes granulars (§7.2, p.58)

**Cita textual:**

> *"El método más antiguo es el de Terzaghi y Peck (1948) que da las
> expresiones siguientes:
> `q_adm = N·s/8`   per `B ≤ 1.20 m`
> `q_adm = N·s/12 · ((B+0.3)/B)²`   per `B > 1.20 m`
> siendo q_adm la presión admisible en Kp/cm² y s el asiento tolerable en
> pulgadas, que en la fig. 2.22 se ha fijado como de 1 pulgada (2.54 cm)."*

**MATCH EXACTE amb els informes d'Eva.** Confirmat que Eva aplica aquesta
fórmula literalment per a granulars.

### 6.4 Schmertmann — taula qc/N completa (§7.2, Fig. 2.24, p.59)

**Cita textual literalment:**

> *"En el método de Schmertmann [...] se supone que los asentamientos
> quedan limitados a una profundidad de z_lim = 2B (zapatas circulares o
> cuadradas de lado B) o z_lim = 4B (zapatas corridas). El asiento se
> calcula por s = C₁ · q · Σ(I_zi/E_i · Δz_i) siendo [...] **E_i el módulo
> de deformabilidad, que según Schmertmann puede estimarse por
> E = 2.5 q_c para zapatas cuadradas o circulares, E = 3.5 q_c para
> zapatas corridas, siendo q_c la resistencia a la penetración estática con
> cono, la cual se puede relacionar con el N del ensayo estándar en la
> forma siguiente:"*

**Taula qc/N (Rodríguez Ortiz, pàgina 59):**

| Tipus de sòl | q_c/N (Kp/cm²) |
|---|---:|
| Arcilla blanda, turba | 2 |
| Limos | 3 |
| Arena fina limosa | 3–4 |
| Arena media | 4–5 |
| Arena gruesa | 5–8 |
| Grava | 8–12 |

**Comparació amb els valors d'Eva (Spt-correlacions.doc):**
- Eva: n = 1.25 (llims sorrencs), 2.0 (sorres llimoses), 2.5 (sorres
  lleugerament llimoses)
- Llibre: més alts — mínim 2 (argila blanda), Limos=3, etc.

**Possibles explicacions:**
1. Eva pot aplicar la taula a **Nb (DPSH)** en comptes d'N (SPT); si Nb ≈
   N/0.83, els factors efectius sobre N serien `n_book = n_eva/0.83`, fent
   2.5→3.0, 2.0→2.4, 1.25→1.5.
2. Eva pot haver **simplificat la taula a 3 classes** per a ús pràctic
   català.
3. Eva pot usar **valors lleugerament conservadors** per sòls de transició.

**Per validar:** comparar qc_eva vs qc_book en projectes amb DPSH+CPT per
veure quin és l'us real.

### 6.5 Fórmula de Meyerhof per forma de sabata (§5.2.2.a, p.47)

Zapata cuadrada o circular:
```
q_h = 1.2·c·N_c + q·N_q + 0.3·B·γ·N_γ
```

Zapata rectangular (B×L):
```
q_h = (1 + B/L · N_q/N_c)·c·N_c + (1 + B/L·tg φ)·q·N_q + 0.5·(1 − 0.4·B/L)·B·γ·N_γ
```

A efectes pràctics es pot prendre `N_q/N_c ≈ 0.2`.

### 6.6 Skempton (1951) per argiles homogènies (§7.1, p.56)

```
q_h = c·N_c*
```

On **N_c*** (fig. 2.21) és el factor modificat per profunditat d'encastament
d/B. Valors de la Fig. 2.21:
- Faja infinita B/L=0: N_c* parteix de ~5.14 a d/B=0 i creix a ~7.7 per d/B→∞.
- Circular/quadrada B/L=1: N_c* parteix de ~6.2 a d/B=0 i creix a ~9.0 per d/B→∞.

**Valors ADMISSIBLES**:
```
q_adm = c·N_c / F  +  q        (Eva usa F=3, confirmat als informes)
```

### 6.7 Cimentacions a prop de talussos (§6.3, Fig. 2.19–2.20)

Meyerhof (1957): `q_h = c·N_cq + 0.5·γ·B·N_γq`

On N_cq i N_γq vénen dels àbacs Fig. 2.19 i 2.20 en funció de:
- Angle d'inclinació del talús β
- Factor d'estabilitat del talús N_s = γ·H/c
- Distància del cimbre a la coronació del talús

**Implicacions per G3DT:** només aplica a Castellar (pendent 20–25°).
Àbacs requereixen digitalització — baix prioritari.

---

## 7. Implicacions per al pipeline G3DT

### 7.1 Implementable ara (sense dependència d'Eva)

- **G.5 — Bicapa Rodríguez Ortiz §6.2**: tenim les fórmules explícites.
  Implementable immediat.
- **qc/N taula** (§6.4): podem afegir `NSPT_TO_QC_FULL_TABLE` com a
  alternativa a Eva's simplified 3-values, per comparar en benchmarks.
- **Skempton N_c*** (§6.6): pot reemplaçar el N_c bàsic per a argiles
  en sabates aïllades superficials.

### 7.2 Pendent d'Eva o d'altres fonts

- **Crespo sub-table per materials transicionals** (Finding #10) — encara
  obert; respuesta d'Eva és la via més ràpida.
- **Shape factors**: Eva usa 1.3/0.4; llibre usa 1.2/0.3. Diferència <2% en
  q_h. No urgent, però podem oferir tots dos com configuració.
- **Hoek & Bray abacs** (§6.7 llibre mostra Meyerhof, no Hoek & Bray) —
  resta pendent d'aquella font.

---

## 8. Investigacions relacionades (referència durable)

Aquests documents són **font autoritativa** per a les decisions metodològiques
i de pipeline. S'han de consultar abans de modificar càlculs, prompts
d'extracció o regles d'autoritat. Estan a `docs/`:

### Càlculs i metodologia
- **`INVESTIGACIO-GEOMECH-STRATUM.md`** — *Bearing stratum semantics*. Demostra
  amb 7 projectes que Eva sempre reporta `geomech_E/phi/cohesion/gamma` del
  nivell de recolzament (última fila de la taula), no del superficial. Inclou
  cita textual d'Alcoletge ("es descarta totalment per a recolzar-hi...") i
  les correccions específiques per Alcoletge / Linyola / Vilanova. **Consulta
  obligada abans de tocar `_flatten_loop_table_concepts` o qualsevol prompt
  d'extracció geomecànica.**
- **`INVESTIGACIO-ENGINEERING-DELEGATION.md`** — *Phase 1 calculator delegation*.
  Catàleg dels 8 conceptes que Eva computa (`qa_value`, `settlement_cm`,
  `geomech_E`, `geomech_phi`, `geomech_cohesion`, `geomech_gamma`,
  `Es_settlement`, `k30_value`), quina funció legacy els implementa, quins
  inputs requereixen, i el risc del gap `QA_CAP_ROCK = 3.0` (codi) vs Eva
  (4.0–4.5 per roca). **Consulta obligada abans d'estendre la calculator pass
  o canviar qualsevol constant numèrica.**

### Pipeline (extracció / ranking)
- **`INVESTIGACIO-ARCHITECT-NAME.md`** — Quatre patrons que Eva fa servir per
  identificar l'arquitecte al cos del informe (estàndard / truncat /
  auto-promogut / firm-led). Pot guiar la lectura d'altres camps amb
  alineació posicional fràgil.
- **`INVESTIGACIO-SILENT-SOURCES.md`** — Per què 8 fonts produien 0
  candidats a Stage 4, i les regles de pre-skip resultants
  (`coordinates_text`, `accounting_memo`, `text_stub`, `pressupost_boilerplate`).
- **`INVESTIGACIO-PASS-BC-EFFECTIVENESS.md`** — Auditoria cost-vs-benefici de
  les Pass B / Pass C del ranker per grup. Origen de la regla "no fer Pass C
  sobre el grup `coordinates`" i del flag `G3DT_AI_SKIP_GROUPS`.

### Resum de sessió i handoffs
- `_RESUM-SESSIO-20260426.md` — exhaustiu, fix-by-fix.
- `_FOR-NEW-YOU-20260427.md` — handoff per a la propera sessió.
- `INVESTIGACIONS-CREDIT-BLACKOUT-2026-04-27.md` — strategy + matrius +
  backlog vigents durant el credit blackout.

