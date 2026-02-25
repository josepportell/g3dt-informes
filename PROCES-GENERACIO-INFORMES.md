# Procés de Generació Automatitzada d'Informes Geotècnics

## Resum

L'automatització genera informes geotècnics complets per a G3DT a partir de la carpeta de projecte que es rep habitualment. El sistema llegeix els documents de camp, extreu dades, fa els càlculs geotècnics, consulta fonts oficials (ICGC, CSN, NCSE-02) i genera un document Word amb el format i contingut de l'informe final.

Tot el treball s'ha fet a partir de l'informe de referència `4001612_informe.doc` (projecte Bell-Lloc), amb les indicacions detallades de G3DT a `4001612_informe_DETALLAT.doc` i `EXPLICACIÓ DETALLS.docx`, que explicaven secció per secció d'on surten les dades i com s'elabora cada paràgraf.

---

## Com funciona: Visió general

```
Carpeta del projecte          Dades manuals (JSON)
(Excel, PDFs, fotos)          (arquitecte, edifici, parcel·la)
         │                              │
         ▼                              ▼
┌─────────────────────────────────────────────┐
│         EXTRACCIÓ AUTOMÀTICA                │
│  · Excel DPSH → valors N20                  │
│  · Dades client → empresa, NIF              │
│  · Inventari de fitxers                     │
└─────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│         CÀLCULS GEOTÈCNICS                  │
│  · Correlacions N20 → φ, E, γ               │
│  · Terzaghi → capacitat portant (Qa)        │
│  · CTE → classificació edifici i terreny    │
└─────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│         FONTS EXTERNES                      │
│  · ICGC → geologia oficial                  │
│  · NCSE-02 → acceleració sísmica           │
│  · CSN → potencial de radó                  │
└─────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│    GENERACIÓ DE L'INFORME (4 seccions)      │
│  Plantilla Word + Jinja2 → informe.docx     │
└─────────────────────────────────────────────┘
```

---

## Pas 1: Carpeta del projecte

Cada projecte arriba amb una carpeta estandarditzada:

```
{expedient}-{poblacio}/
├── ACCEPTACIO/
│   └── DADES CLIENT.txt         ← Dades del client
├── ANNEXES/
│   ├── {exp}_DPSH.xls           ← Resultats assaigs DPSH
│   └── Resultats laboratori     ← Anàlisi de sòls
├── FOTOGRAFIES/
│   ├── DPSH/                    ← Fotos de l'assaig
│   └── SONDEIG/                 ← Fotos del sondeig
├── PDF/
│   └── ANNEXES/LAB-SIG.pdf      ← Informe del laboratori
├── PENETROS.pdf                 ← Full de camp DPSH (a mà)
├── SONDEIG.pdf                  ← Full de camp sondeig (a mà)
└── comanda laboratori_*.xls     ← Comanda al laboratori
```

El sistema extreu automàticament:
- **Expedient i municipi** del nom de la carpeta
- **Dades del client** del fitxer DADES CLIENT.txt (empresa, NIF, adreça)
- **Dades DPSH** de l'Excel (profunditats, valors N20, factor de correcció)
- **Inventari de fitxers** (quins documents hi ha disponibles)

## Pas 2: Dades manuals

Algunes dades no estan als documents de la carpeta i s'han d'entrar manualment en un fitxer JSON (`user_data.json`):

| Camp | Exemple | D'on surt |
|------|---------|-----------|
| Arquitecte | Jordi Bosch Novell | Del plànol A.01 |
| Tipus edificació | Habitatge unifamiliar | Del plànol |
| Plantes | Pb + 1Pp | Del plànol |
| Adreça | C/ Antoni Bellet, Bell-Lloc | Del plànol |
| Parcel·les adjacents | Nord: parcel·la buida, Sud: carrer... | Visita de camp |
| Té sondeig? | Sí / No | Carpeta del projecte |
| Té soterrani? | Sí / No | Del plànol |
| Murs de contenció? | Sí / No | Del projecte |
| Terreny en pendent? | Sí / No | Visita de camp |

---

## Pas 3: Validació de dades de camp

Abans de generar l'informe, es poden validar les dades dels fulls de camp escrits a mà:

### DPSH (PENETROS.pdf vs Excel)
```
/g3dt-validar-penetros PENETROS.pdf
```
Claude llegeix el PDF visualment, extreu cada valor N20, i el compara amb l'Excel. Si hi ha diferències, es marquen per revisió. Resultat a Bell-Lloc: 18 valors, 18 coincidències, 0 discrepàncies.

### Sondeig (SONDEIG.pdf)
```
/g3dt-validar-sondeig SONDEIG.pdf
```
Claude extreu les capes de sòl, les descripcions i els resultats SPT. Com que no hi ha Excel de referència, cada valor porta un nivell de confiança.

### Plànol (A.01.pdf)
```
/g3dt-extreure-planol A.01.pdf
```
Claude extreu les dimensions i dades del projecte des del caixetí i les cotes del plànol.

Els fitxers generats es revisen al formulari `review.html` (tres pestanyes, una per document). G3DT només ha de verificar els valors marcats.

---

## Pas 4: Càlculs geotècnics

### Correlacions N20

A partir de la mitjana de cops N20 dels assaigs DPSH, el sistema calcula:

| Paràmetre | Fórmula / Font | Exemple (N20=37) |
|-----------|-----------------|-------------------|
| Angle de fricció (φ) | Correlació geotècnica | ~38° |
| Mòdul de deformació (E) | Correlació geotècnica | ~370 kg/cm² |
| Densitat (γ) | Correlació geotècnica | ~2.1 g/cm³ |
| Densitat relativa | Classificació | Dens |

### Capacitat portant (Terzaghi)

Amb els paràmetres derivats, el sistema calcula:

```
qu = c·Nc·sc + γ·Df·Nq·sq + 0.5·γ·B·Nγ·sγ

Qa = qu / F    (F = 3, factor de seguretat)
```

On:
- Nc, Nq, Nγ = factors de capacitat portant (depenen de φ)
- sc, sq, sγ = factors de forma (depenen del tipus de fonament)
- B = amplada del fonament, Df = profunditat

### Classificació CTE

Segons el Codi Tècnic de l'Edificació (DB SE-C):

| Classificació edifici | Criteri |
|----------------------|---------|
| C-0 | Pb, <300 m² |
| C-1 | Pb+1-2, 300-3000 m² |
| C-2 | Pb+3+, >3000 m² |

| Classificació terreny | Criteri |
|----------------------|---------|
| T-1 (Favorable) | N20 mitjà ≥ 30 |
| T-2 (Intermedi) | N20 mitjà 10-29 |
| T-3 (Desfavorable) | N20 mitjà < 10 |

---

## Pas 5: Fonts de dades externes

### ICGC - Geologia (Secció 3.1)

Consulta l'Institut Cartogràfic i Geològic de Catalunya per obtenir la unitat geològica oficial del terreny a partir de les coordenades UTM.

**Dada obtinguda:** Codi de la unitat, descripció, època geològica.
**Ús a l'informe:** Marc geològic de la secció 3.

### NCSE-02 - Sísmica (Secció 3.6/3.7)

Taula de consulta amb les 947 municipis de Catalunya. Cada municipi té l'acceleració sísmica bàsica (ab) segons la norma NCSE-02.

**Dada obtinguda:** Acceleració sísmica (ex: ab = 0.04g).
**Ús a l'informe:** Apartat de sísmica.

### CSN - Radó (Secció 3.7/3.8)

Consulta el mapa de potencial de radó del Consell de Seguretat Nuclear (2017) mitjançant coordenades UTM.

**Dada obtinguda:** Nivell de risc (molt baix / baix / moderat / alt / molt alt) i rang Bq/m³.
**Ús a l'informe:** Apartat de radó.

---

## Pas 6: Generació de l'informe

L'informe final es genera amb una plantilla Word (`g3dt-jinja-template.docx`) que s'omple automàticament. L'informe té 4 seccions principals:

### Secció 1: Presentació i Metodologia

Conté:
- Dades del projecte (expedient, client, arquitecte)
- Objecte de l'estudi
- Descripció de l'emplaçament i parcel·les adjacents
- Normativa aplicable (CTE, EHE-08)
- Metodologia dels treballs

**D'on surten les dades:** Carpeta del projecte + dades manuals.

### Secció 2: Treballs Realitzats

Conté:
- 2.1: Plànols de situació (referències a figures)
- 2.2: Posició de l'edifici
- 2.3: Assaigs DPSH (taules amb dades de cada assaig P-1, P-2, etc.)
- 2.4: Sondeig a rotació *(condicional: només si n'hi ha)*
  - Descripció del sondeig
  - Resultats SPT
  - Resum dels assaigs in situ
- 2.5: Fotografies

**D'on surten les dades:** Excel DPSH + fotos + dades manuals.

### Secció 3: Descripció Geològica

Conté:
- 3.1: Marc geològic *(ICGC)*
- 3.2: Materials identificats (capes de sòl)
- 3.3: Hidrogeologia (nivell freàtic, permeabilitat)
- 3.4: Agressivitat (sulfats, EHE-08)
- 3.5: Expansivitat *(condicional: segons tipus de sòl)*
- 3.5/3.6: Excavabilitat (dificultat d'excavació segons N20)
- 3.6/3.7: Sísmica *(NCSE-02)*
- 3.7/3.8: Radó *(CSN/CTE)*
- Geotèrmia *(condicional: si s'activa)*

**D'on surten les dades:** ICGC + municipal_data + CSN + laboratori + DPSH.

### Secció 4: Conclusions i Recomanacions

Conté:
- 4.1: Resum geològic
- 4.2: Classificació CTE (edifici + terreny)
- 4.3: Fonamentació (Qa amb Terzaghi, F=3)
- 4.4: Empentes de terres *(condicional: si hi ha soterrani o murs)*
- 4.5: Estabilitat de talussos *(condicional: si terreny en pendent)*
- 4.X: Assentaments (predicció)
- 4.X: Recomanacions de construcció

**D'on surten les dades:** Terzaghi + CTE + DPSH + dades manuals.

---

## Seccions condicionals

L'informe s'adapta a les característiques de cada projecte:

| Condició | Secció que apareix/desapareix |
|----------|------------------------------|
| Té sondeig | 2.4 Sondeig (amb subseccions) |
| Sòl expansiu | 3.5 Expansivitat |
| Geotèrmia activada | 3.X Geotèrmia |
| Soterrani o murs | 4.4 Empentes de terres |
| Terreny en pendent | 4.X Estabilitat de talussos |

Quan una secció condicional apareix o desapareix, la numeració de les seccions posteriors s'ajusta automàticament. El mateix passa amb la numeració de figures, fotografies i taules.

---

## Numeració dinàmica

### Figures
S'assignen en ordre: figures del projecte → plànol situació → posició edifici → cullera SPT → mapa geològic → secció de correlació. El número depèn de quantes figures de projecte hi ha.

### Fotografies
En ordre: vistes generals → màquina DPSH → màquina sondeig (si n'hi ha) → detall materials. Si no hi ha sondeig, les fotos posteriors avancen un número.

### Taules
En ordre: resum edifici → classificació CTE → taules DPSH (una per assaig) → taula sondeig (si n'hi ha) → laboratori → permeabilitat → paràmetres geotècnics → sísmica.

---

## Exemple: Projecte Bell-Lloc (4001612)

| Element | Valor |
|---------|-------|
| Expedient | 4001612 |
| Municipi | Bell-Lloc d'Urgell |
| Client | Ramon Mitjana SL |
| Arquitecte | Jordi Bosch Novell |
| Edificació | Habitatge unifamiliar, Pb+1 |
| Assaigs DPSH | 2 (P-1, P-2) |
| N20 mitjà | 36.7 |
| Sondeig | Sí (S-1, 1.80m) |
| Qa calculat | ~12.5 kg/cm² (F=3) |
| Classificació CTE | C-1 / T-1 |

---

## Estructura dels mòduls

```
automation/
├── project_extractor.py     Extreu dades de la carpeta del projecte
├── dpsh_extractor.py        Llegeix l'Excel DPSH (N20, profunditats)
├── report_data.py           Unifica totes les dades en un sol model
├── report_generator.py      Orquestra tot el procés de generació
├── terzaghi_calculator.py   Calcula la capacitat portant (Qa)
├── cte_classifier.py        Classifica edifici i terreny (CTE)
├── icgc_geology.py          Consulta geologia ICGC
├── csn_radon.py             Consulta potencial de radó CSN
├── municipal_data.py        Dades municipals (sísmica, radó)
├── sections/
│   ├── section1_presentacio.py   Secció 1: Presentació
│   ├── section2_treballs.py      Secció 2: Treballs
│   ├── section3_geologia.py      Secció 3: Geologia
│   └── section4_conclusions.py   Secció 4: Conclusions
└── validation/
    ├── schemas.py            Models de dades per validació
    ├── prompts.py            Prompts d'extracció visual
    └── extractor.py          Comparació PDF vs Excel
```

---

## Com executar

```bash
# Generar un informe
python3 -m automation.report_generator \
    reference-material/4001612-bell-lloc \
    --user-data reference-material/4001612-bell-lloc/user_data.json \
    --output samples/4001612_generated.docx

# Validar dades de camp prèviament (opcional)
/g3dt-validar-penetros reference-material/4001612-bell-lloc/PENETROS.pdf
/g3dt-validar-sondeig reference-material/4001612-bell-lloc/SONDEIG.pdf
/g3dt-extreure-planol reference-material/4001612-bell-lloc/A.01.pdf
```

---

*Eficients.cat - Automatització amb Claude Code*
*Febrer 2026*
