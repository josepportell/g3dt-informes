# Estat de l'Automatització - Informes Geotècnics G3DT

**Data:** 5 de febrer de 2026
**Projecte referència:** 4001612 Bell-Lloc d'Urgell
**Contacte tècnic:** Eva (G3DT)

---

## 1. Resum General

L'automatització genera un informe geotècnic .docx complet a partir de:
- Les dades de camp (Excel DPSH, fulls de sondeig)
- El plànol de l'arquitecte (A.01.pdf)
- Un fitxer de dades del projecte (`user_data.json`)
- APIs públiques (Cadastre, ICGC, NCSE-02, CSN)

**Estat actual: ~88% de coincidència** amb l'informe de referència (4001612).

| Categoria | Paràgrafs | % |
|-----------|-----------|---|
| Correcte (>95% match) | ~200 | 88% |
| Parcialment correcte (80-95%) | ~12 | 5% |
| Pendent d'implementar (<50%) | ~15 | 7% |

---

## 2. Què funciona correctament

### 2.1 Dades automàtiques (sense intervenció)

| Dada | Font | Mètode |
|------|------|--------|
| Dades DPSH (N20, profunditats, refús, cota) | `DPSH.xls` | Extracció directa d'Excel |
| Nombre d'assaigs, tipus, ubicació | `DPSH.xls` | Comptatge automàtic |
| Correlacions geotècniques (φ, γ, E, c) | N20 mitjà | Taules Bowles/Terzaghi-Peck |
| Capacitat portant Qa (Terzaghi) | Correlacions + Df | Fórmula sabata aïllada quadrada |
| Classificació CTE (C-0/C-1/C-2) | Plantes + superfície | DB SE-C, Article 3.2 |
| Sísmica (ac, K, ab, coef. sòl) | Municipi + tipus sòl | NCSE-02 Annex 1 + Taula 2.1 |
| Potencial radó | Coordenades UTM | CSN mapa zonificació |
| Coordenades UTM parcel·la | Ref. catastral | API WFS Cadastre (centroide) |
| Zona geològica regional | Coordenades UTM | ICGC WMS |
| Permeabilitat, expansivitat, empenta | Tipus de sòl | Taules normatives |
| Estabilitat de talussos | Pendent + φ | Factor de seguretat |
| Classificació sòl (S-1 a S-4) | N20 | Taula NCSE-02 |
| Format legal empresa | Nom client | S.L. / S.L.U. automàtic |
| Data en català | Data generació | Diccionari de mesos |

### 2.2 Taules parametritzades (8 taules)

Totes les taules de l'informe es generen amb dades reals del projecte:

| Taula | Contingut | Font |
|-------|-----------|------|
| Assaigs DPSH | ID, cota, profunditat, refús, aigua | DPSH.xls |
| Assaigs SPT | ID, punt, rang, N30, litologia | user_data.json |
| Laboratori | Tipus assaig, mostra, punt, profunditat | user_data.json |
| Nivells de sòl | Descripció, gruix, N20 mitjà | DPSH.xls + user_data |
| Permeabilitat | Material, coeficient K, tipus | Correlacions |
| Sulfats | Valor mg/kg, classificació UNE | user_data.json |
| Sísmica | Nivell, gruix, coeficient C | NCSE-02 |
| Geotècnica | Nb, N30, γ, c, φ, E | Correlacions |

### 2.3 Seccions del cos

- Secció 1: Antecedents, ubicació, normativa (tot parametritzat)
- Secció 2: Treballs de camp, DPSH, SPT, laboratori
- Secció 3: Geologia (zona correcta), hidrogeologia, sísmica, radó
- Secció 4: Geotècnica, fonamentació, Terzaghi, assentaments
- Secció 5: Conclusions i recomanacions (parcialment)
- Condicionals: Sondeig (si/no), soterrani (si/no), geotèrmia (si/no)

---

## 3. Què necessita ajust tècnic (automatitzable)

### 3.1 Unitat geològica ICGC: P8G vs Qvpu (PRIORITAT ALTA)

**Problema:** La consulta a ICGC retorna **P8G** (paleogen) en lloc de **Qvpu** (quaternari al·luvial).

**Causa:** El codi consulta la capa geològica a escala **1:250.000**, que mostra la roca mare (substrat paleogen). A escala **1:50.000**, els dipòsits quaternaris superficials (graves al·luvials del Pla d'Urgell) sí apareixen com a Qvpu.

**Impacte:** La secció 3.1 (marc geològic) descriu correctament la Depressió de l'Ebre, però la unitat geològica específica és incorrecta. Això afecta la descripció litològica i la classificació del terreny.

**Solució prevista:** Canviar la consulta WMS d'ICGC de la capa `unitats-geologiques-250000` a la capa `unitats-geologiques-50000`. Tècnicament senzill — és canviar un paràmetre de la consulta.

**Pregunta per Eva:** Quin mapa geològic consulteu normalment? El 1:50.000 de l'ICGC? O teniu una altra font per la unitat geològica?

### 3.2 Coordenades UTM des del Cadastre (FET, verificar)

Les coordenades UTM ara s'obtenen de l'API WFS del Cadastre Espanyol a partir de la referència catastral (14 caràcters). Retorna el centroide de la parcel·la en ETRS89 UTM Huso 31.

**Abans:** Geocodificació de l'adreça → error de ~500m en X.
**Ara:** Cadastre WFS → centroide exacte (X=314508.67, Y=4611192.86).

L'automatització pot fer la consulta automàticament si es proporciona la referència catastral. **La referència catastral es pot extreure del pressupost o de la comanda.**

### 3.3 Diferència Qa: 3.18 vs 3.0 kg/cm² (PRIORITAT BAIXA)

**Fórmula de Terzaghi implementada correctament.** La diferència residual de 6% ve d'un sol paràmetre:

| Paràmetre | Referència (Eva) | Automatitzat | Diferència |
|-----------|-----------------|-------------|------------|
| Df (prof. fonament.) | 0.3 m | 0.3 m | ✅ Corregit |
| γ (densitat) | **2.0** g/cm³ | **2.1** g/cm³ | **6%** |
| φ (fregament) | 38° | 38° | ✅ Idèntic |
| c (cohesió) | 0.0 | 0.0 | ✅ Idèntic |
| Nb, N30, B, F | Idèntics | Idèntics | ✅ |

La correlació automàtica per N20≥30 (grava densa) dóna γ=2.1 (taula Bowles). G3DT utilitza γ=2.0 per judici professional. Amb γ=2.0, Qa seria 3.03 kg/cm² — pràcticament idèntic a la referència.

**Opcions:**
- A) Canviar default γ de 2.1 a 2.0 per materials granulars densos (N20≥30)
- B) Afegir camp `gamma_override` a user_data.json per ajust manual
- C) Deixar com està (diferència de 6% és conservadora — γ=2.1 dóna Qa més alta)

**Pregunta per Eva:** Quina γ feu servir normalment per graves denses? Sempre 2.0, o depèn del projecte?

### 3.4 Mòdul de deformació E: ~400 vs 650 kg/cm²

La correlació automàtica (E = 10×N20) dóna ~350-400 kg/cm². La referència utilitza E=650.

**No afecta Qa** (Terzaghi no usa E). Afecta el càlcul d'**assentaments**.

**Pregunta per Eva:** Quina correlació feu servir per E? O és un valor que ajusteu manualment per cada projecte?

---

## 4. Què requereix dades d'entrada (user_data.json)

### 4.1 Dades que ja s'extreuen automàticament

| Dada | Font automàtica |
|------|----------------|
| Nom arquitecte | Plànol A.01.pdf (caixetí) |
| Tipus edifici | Plànol A.01.pdf |
| Nº plantes | Plànol A.01.pdf |
| Superfície parcel·la | Plànol A.01.pdf |
| Superfície construïda | Plànol A.01.pdf |
| Soterrani sí/no | Plànol A.01.pdf |
| Forma parcel·la | Plànol A.01.pdf |
| Sòl urbà sí/no | Plànol A.01.pdf |
| Murs de contenció | Detecció de carpeta |
| Sondeig sí/no | Detecció de carpeta |
| Coordenades UTM | Cadastre WFS (ref. catastral) |

### 4.2 Dades que Cal Proporcionar per Cada Projecte

Aquestes dades **no es poden automatitzar** perquè vénen de l'observació de camp o del coneixement del tècnic:

| Dada | Descripció | Exemple Bell-Lloc |
|------|-----------|-------------------|
| `adjacent_north/south/east/west` | Veïns de la parcel·la | "parcel·la buida", "Carrer Antoni Bellet" |
| `site_description` | Descripció del solar (visita) | "Solar anivellat, 15cm sota rasant" |
| `access_description` | Com s'hi accedeix | "Des del Carrer existent al sud" |
| `cota_referencia` | Cota topogràfica ICGC | "+199.50" |
| `is_anthropized` | Presència materials antròpics | true/false |
| `is_sloped` | Pendent significativa | true/false |
| `field_work_dates_text` | Dates de camp (text) | "1 i 6 d'octubre de 2025" |
| `foundation_depth_m` | Profunditat fonamentació (Df) | 0.3 |
| `spt_data` | Resultats SPT (si n'hi ha) | N30=54, -1.00 a -1.60 |
| `lab_tests` | Assaigs de laboratori | Sulfats UNE 83963:2008 |
| `sulfate_mg_kg` | Contingut en sulfats | 89.8 |

### 4.3 Possibles automatitzacions futures

| Dada | Font potencial | Viabilitat |
|------|---------------|------------|
| `cota_referencia` | ICGC API topogràfic MDT | Alta — API disponible |
| `field_work_dates` | Capçalera DPSH.xls | Alta — ja hi és la data |
| `referencia_catastral` | Pressupost o comanda | Mitjana — OCR del document |
| `adjacent_*` | Cadastre WFS (parcel·les veïnes) | Mitjana — requereix lògica espacial |
| `spt_data` | Full de camp SONDEIG.pdf | Ja implementat (skill `/g3dt-validar-sondeig`) |

---

## 5. Plantilles de text geològic (PENDENT DE G3DT)

### Situació actual

El sistema detecta correctament la zona geològica (Depressió de l'Ebre per Bell-Lloc) i genera text genèric adequat. Però el text de la referència és molt més detallat (6 paràgrafs d'evolució Eocè-Oligocè, conca endorreica, etc.).

### Què necessitem de G3DT

**Les plantilles de text geològic regional** que teniu al vostre servidor intern. El sistema ja selecciona la zona correcta — només necessitem el contingut real que utilitzeu.

Zones mínimes necessàries:
1. **Depressió de l'Ebre** (projectes Pla d'Urgell, Segrià, etc.)
2. **Vallès-Penedès** (projectes Vallès Oriental/Occidental)
3. Altres zones que genereu habitualment

### Format ideal

Fitxers de text (.txt o .docx) amb els paràgrafs que s'insereixen a la secció 3.1 de l'informe per cada zona.

---

## 6. Text descriptiu del sondeig (PENDENT)

La secció condicional del sondeig (`{% if has_sondeig %}`) funciona — apareix quan hi ha sondeig i s'omet quan no n'hi ha. Però els 3-5 paràgrafs descriptius de la tècnica (sondeig a rotació amb bateria contínua, característiques de l'equip) encara no estan al template.

**Acció:** Necessitem el text estàndard que G3DT utilitza per descriure la tècnica del sondeig. És text fix que no canvia entre projectes.

---

## 7. Flux de treball proposat

### Per a cada nou projecte:

```
1. G3DT rep encàrrec de l'arquitecte
   ↓
2. Crear carpeta del projecte amb estructura estàndard
   ↓
3. L'automatització extreu dades automàtiques:
   - Plànol A.01.pdf → tipus edifici, plantes, superfícies
   - DPSH.xls → dades de camp, correlacions
   - Ref. catastral → coordenades UTM (Cadastre WFS)
   - Coordenades → zona geològica (ICGC), sísmica (NCSE-02), radó (CSN)
   ↓
4. G3DT completa les dades manuals:
   - Resposta a ~10 preguntes (adjacents, accés, cota, Df, SPT, lab...)
   - Temps estimat: 5-10 minuts
   ↓
5. Generació automàtica de l'informe .docx
   ↓
6. G3DT revisa i ajusta l'informe generat
   - Verificar text geològic
   - Ajustar paràmetres si cal (γ, E)
   - Afegir observacions de camp específiques
```

### Temps estimat d'estalvi

| Fase | Sense automatització | Amb automatització |
|------|---------------------|--------------------|
| Recollida de dades | 30-45 min | 5-10 min (preguntes) |
| Càlculs | 20-30 min | Automàtic |
| Redacció informe | 2-3 hores | Automàtic (revisió 15-30 min) |
| **Total** | **~3-4 hores** | **~30-45 minuts** |

---

## 8. Accions pendents (ordenades per prioritat)

| # | Acció | Qui | Esforç |
|---|-------|-----|--------|
| 1 | Canviar ICGC de 1:250k a 1:50k | Eficients | 1 hora |
| 2 | Automatitzar cota des d'ICGC MDT | Eficients | 2-3 hores |
| 3 | Extreure dates de camp de DPSH.xls | Eficients | 1 hora |
| 4 | **Proporcionar plantilles text geològic** | **G3DT** | - |
| 5 | **Proporcionar text estàndard sondeig** | **G3DT** | - |
| 6 | **Confirmar γ default (2.0 vs 2.1)** | **G3DT** | - |
| 7 | **Confirmar correlació E preferida** | **G3DT** | - |
| 8 | Ajustar γ i E segons resposta G3DT | Eficients | 30 min |
| 9 | Format ordinals ("1er Nivell") | Eficients | 30 min |
| 10 | Descripció litològica detallada | Eficients + G3DT | 1-2 hores |

---

*Document preparat per Eficients.cat — Automatització amb Claude Code*
