# Recerca: criteris de càlcul descrits per Eva ALS PROPIS INFORMES signats

**Data:** 2026-09-03
**Tasca:** R del pla `docs/PLA-CRITERIS-CALCUL-AL-CODI-2026-09-03.md`
**Estat:** COMPLETAT — 7/7 informes (6 amb lletra narrativa; Vilanova només annexos, lletra no disponible)
**Mètode:** relectura dirigida dels PDFs signats (`/home/josep/g3dt-e2e/projectes/*/PDF*/`) buscant
enunciats de CRITERI dins el text narratiu, les llegendes de taules i els fulls d'annex. Es distingeix
sempre **CITA LITERAL** (bloc citat, amb pàgina PDF) d'**interpretació** (marcada com a tal).
**Objectius prioritaris:** P1 (què és la cel·la Nb), P3 (criteri de l'E), P4 (Nb representatiu en perfil
d'un sol nivell) — vegeu `ANALISI-CALCUL-N20-E-2026-09-02.md` §4-§5.
**Nota:** Tulipa (3001706) no té informe signat d'Eva en PDF — es salta (7 informes en total).

---

## 1. BELL-LLOC (4001612)

**Fitxer llegit:** `/home/josep/g3dt-e2e/projectes/4001612 BELL-LLOC/PDF/4001612_informe.pdf`
(46 pàgines PDF; llegides: 9-11, 13-16, 21-22, 24-27, 29-31, 36 — text extret amb pdftotext, verificat
sobre la capa de text del PDF).

### 1.1 Nb i N — LA TROBALLA CENTRAL (respon P1)

**CITA LITERAL (p9, §2.4.1, definició del DPSH):**

> "El comptatge del número de cops ens donarà un valor que anomenarem N20 [...] En el cas que el nombre
> de cops necessaris per travessar els 20 cm, sigui superior a 100, o quan es superin 3 intervals
> consecutius de 75 cops considerarem rebuig a la penetració i s'abandonarà l'assaig."

**CITA LITERAL (p10, §2.4.3, definició de l'SPT — regla de càlcul del N30 que no teníem):**

> "No es conten els cops necessaris per introduir els primers 15 centímetres, ja que se suposa que el
> terreny en el fons del sondeig pot estar alterat. Si que es conten els cops realitzats per introduir la
> cullera els següents 45 centímetres en trams de 15. La suma dels colpeigs dels dos trams centrals és el
> "número de penetració estàndard", NSPT o N30. En el cas que el darrer dels trams tingui un valor de
> colpeig menor que el dels dos trams centrals, se sumaran els dos valors més petits dels tres darrers
> trams enregistrats."

**EVIDÈNCIA DOCUMENTAL (p29-p30, fulls d'annex "ASSAIG DE PENETRACIÓ DINÀMICA"):** cada full imprimeix,
literalment, el factor **"0,83"** a la capçalera, entre dues columnes titulades **"Colpeig DPSH"** i
**"Colpeig NB"**. Files reals de P-1 (p29): DPSH 20→NB 24; 27→33; 16→19; 19→23; 32→39; 100→120.

*Interpretació (aritmètica verificada sobre les 6 files de P-1 i les 12 de P-2):* **NB = N20(DPSH) / 0,83,
arrodonit a enter** (20/0,83=24,1→24; 27/0,83=32,5→33; 100/0,83=120,5→120...). El full d'assaig del
propi informe defineix, doncs, què és el "Nb" del vocabulari d'Eva: **el colpeig DPSH dividit per 0,83**
(equivalència Borros→SPT), no el N20 cru.

**CITA LITERAL (p15, narrativa del 1er nivell — com presenta el Nb i el N de la taula):**

> "Des del punt de vista geomecànic es tracta d'uns materials de caràcter granular, amb una densitat i una
> capacitat portant elevada. Dels assaigs de penetració dinàmica DPSH s'obté un valor de **Nb mig des de
> 25 fins assolir rebuig** a la penetració pels trams més carbonatats, i de l'assaig SPT realitzat en
> aquest nivell s'obté un valor de **N de 54**."

*Interpretació:* la cel·la "Nb 25-R" és un **"Nb mig"** (mitjana del colpeig corregit /0,83), i "des de 25
fins assolir rebuig" explica el format "25-R": 25 és el tram superficial, R el tram profund carbonatat.
La cel·la "N" ve **de l'SPT del sondeig**, no del DPSH.

**Dades brutes dels annexos per contrastar (p29-31, 36):**
- P-1 (p29): NB per tram = 24, 33, 19, 23, 39, després R (-1,4 m, DPSH=100→120).
- P-2 (p30): NB = 20, 25, 20, 16, 12, 24, 36, 63, 66, 39, 96, 120 (R a -2,6).
- Tall de correlació (p36): etiqueta **"Nb=27"** a P-1; **"Nb=22"** i **"Nb=56"** a P-2 (dos trams) i
  "Nb=R"; **"N=58"** a S-1.
- Sondeig S-1 (p31): SPT-1 de -1,00 a -1,60 amb colpeigs per tram de 15 cm: **24 / 34 / 28 / 30**;
  anotació "Tram totalment carbonatat".

*Interpretació dels valors del tall:* P-2 tram superficial (-0,4 a -1,6): mitjana NB = 153/7 = 21,9 → 22 ✓;
P-2 tram profund (-1,8 a -2,2): (63+66+39)/3 = 56,0 ✓. P-1: (24+33+19+23+39)/5 = 27,6 → el tall diu 27
(truncat?). El **25 signat** és compatible amb la mitjana dels trams superficials dels dos penetros
((27+22)/2 = 24,5 → 25) i **no** amb cap mitjana que inclogui el tram profund de P-2 (56). Això toca P4
(vegeu §Respostes).

**DISCREPÀNCIA INTERNA DETECTADA (N):** amb la regla textual de p10 i els colpeigs 24/34/28/30, el darrer
tram (30) és menor que un dels centrals → els dos més petits dels tres darrers (34, 28, 30) donen
28+30=**58**, que és exactament el valor del tall (N=58). Però la taula signada i la narrativa de p15
diuen **54** (=24+30? origen no explicat). El propi informe porta 58 al tall i 54 a la taula.

### 1.2 Llegendes (1)(2)(3)(4) de la taula geotècnica — transcripció ÍNTEGRA i literal

Taula 10 (p21): capçaleres "Nivell | Nb | N | Densitat (1) | Cohesió (2) | Angle de fregament intern (3) |
E (4)"; fila única "1er nivell. Graves en matriu sorrenca | 25-R | 54 | 2.0 | 0.0 | 38º | 650".

**CITA LITERAL (p22, les notes al peu, senceres):**

> "Els paràmetres de cohesió i angle de fregament intern, s'han obtingut de les relacions que
> s'estableixen en el llibre "Mecànica de suelos y cimentaciones" de l'autor Carlos Crespo Villalaz, a
> partir de la resistència dels materials.
> (1) Densitat està donada en gr/cm3.
> (2 i 3) La cohesió està expressada en Kg/cm2. Tan la cohesió com l'angle de fregament intern són valors
> efectius o llarg termini.
> (4) Mòdul de deformació, Kg/cm2"

**Troballa negativa important (toca P3):** la llegenda (4) **només dona les unitats** — a Bell-lloc NO hi
ha cap frase que digui d'on surt el 650 ni cap menció explícita de la carbonatació lligada a l'E. Les notes
citen font només per a c i φ (Crespo). El vincle E↔carbonatació queda, en aquest informe, com a inferència
nostra (el material es diu "carbonatades" i el rebuig arriba "pels trams més carbonatats", p15).

### 1.3 Estrat de fonamentació i Qa

**CITA LITERAL (p22, §4.3):**

> "Un cop realitzada l'excavació aflorarà superficialment els materials del primer nivell descrit. [...]
> Per una fonamentació superficial mitjançant sabates, ja sigui aïllades com corregudes, o bé llosa,
> recolzada en els materials del primer nivell **un cop sanejat el tram superficial**, es podrà adoptar
> una tensió admissible de: Qa= 3.0 Kg/cm2 amb un factor de seguretat inclòs de F=3"

### 1.4 Assentaments

**CITA LITERAL (p22):**

> "Els assentaments màxims previstos per la càrrega recomanada anteriorment seran inferiors a 1.20 cm,
> immediats en el temps donat el comportament granular dels materials."

**CITA LITERAL (p27, BASE DE CÀLCUL, el topall d'assentament amb el valor per llosa):**

> "s'haurà de comprovar que els assentaments absoluts de cada una de les sabates és menor a 2.54 (1
> polzada), en el cas de considerar sabates i menor a 5 cm (2 polzades), en el cas de considerar una llosa
> de fonamentació, que són els assentaments màxims admissibles establerts per a les estructures de
> formigó, segons Terzaghi."

### 1.5 Altres

- BASE DE CÀLCUL (p25-27): idèntica a les cites ja recollides a `METODOLOGIA-EVA.md` §1.2-§1.4
  (Rodríguez Ortiz bicapa, Terzaghi corregudes/aïllades, Terzaghi-Peck amb S en polzades, Schmertmann
  2,5/3,5 × colpeig del penetròmetre estàtic, 2B/4B). No es repeteixen aquí.
- Permeabilitat (p16, Taula 7): "1er nivell | 10 – 10-2 | Graves en matriu sorrenca carbonatades" — valor
  de taula per material, sense justificació.

### 1.6 Nou vs METODOLOGIA-EVA: **SÍ**

1. La **regla del N30 SPT amb tram final menor** (p10) no era documentada enlloc.
2. El **full d'annex amb el factor 0,83 imprès i la columna "Colpeig NB"** — evidència directa que
   Nb = N20/0,83 (P1). Ni METODOLOGIA-EVA ni CRITERIS-CALCUL citaven aquesta font.
3. La frase "**Nb mig** des de 25 fins assolir rebuig" (p15) — la cel·la Nb és una mitjana i el format
   "25-R" té lectura pròpia.
4. La cel·la **N ve de l'SPT del sondeig** (p15) — confirma la conclusió §7.3 de l'ANALISI (columna N =
   SPT), i n'hi afegeix la cita.
5. El **topall de 5 cm per llosa** (p27) complementa el 2,54 ja conegut.
6. Llegenda (4) = només unitats → **cap font declarada per a l'E** (troballa negativa per P3).

---

## 2. ANCILES (4001679) — en castellà

**Fitxer llegit:** `/home/josep/g3dt-e2e/projectes/4001679 ANCILES/PDF_V0/4001679_informe_V0.pdf`
(50 pàgines PDF; llegides: 16-17, 24-26, 29-31, 33). **Atenció:** és la versió **V0** (única disponible als
projectes) i conté un placeholder sense omplir a p25: *"se presentan, a priori xxxxxxx al hormigón"* —
esborrany avançat, no necessàriament el text final signat.

### 2.1 Estrat de fonamentació — CONTRADIU el que crèiem

**CITA LITERAL (p25, §4.3 CIMENTACIÓN):**

> "Dada la baja resistencia de los materiales del primer nivel, se realiza una valoración para una
> cimentación **empotrada unos 20-40 cm en los materiales del segundo nivel saneado, superando en todo
> momento los materiales del primer nivel** descrito, que presentan potencias de entre 1.80 a 4.00 metros,
> según los puntos estudiados.
>
> Así, para una cimentación mediante **pozos de cimentación rellenados con hormigón pobre, empotrados un
> mínimo de 20-40 cm de los materiales del segundo nivel saneado**, se podrá adoptar una tensión de
> trabajo de: Qa= 2.0 Kg/cm2 con un factor de seguridad incluido de F=3"

**Contradicció amb el que crèiem:** `CRITERIS-CALCUL-EVA.md` §1 i `METODOLOGIA-EVA.md` §0.4 afirmen que a
Anciles Eva calcula amb **L1 "perquè la fonamentació es recolza en L1 (les argiles), no arriba a L2"**. El
text signat diu el CONTRARI: la fonamentació **travessa L1 i s'encasta 20-40 cm dins L2** (pous de
fonamentació amb formigó pobre). El Qa=2,0 és, doncs, per una fonamentació recolzada a L2 (bolos i graves,
Nb "15-R", φ=38) — i no quadra ni amb Terzaghi-L1 (2,5) ni amb el topall granular dens (3,5).
*Interpretació:* el 2,0 sembla judici conservador per la irregularitat del nivell (Nb "irregulares",
bolos) i/o pel confinament lateral en argiles fluixes — l'informe **no ho explica**.

### 2.2 Nb i N — mateix patró que Bell-lloc

**CITA LITERAL (p16, Resistencia del 1er nivel):**

> "estos materiales presentan un comportamiento de carácter generalmente friccional, con una densidad y
> una capacidad portante baja. A partir del registro dels [sic] ensayos de penetración dinámica DPSH
> realizados, se detectan **valores de Nb medios de 4-6, con valores de Nb medios puntuales de 12 en
> profundidad**, y de los ensayos SPT se obtiene un **valor de N de 6**."

**CITA LITERAL (p17, Resistencia del 2do nivel):**

> "estos materiales presentan un comportamiento granular, con una densidad y una capacidad portante de
> media a elevada. A partir del registro de los ensayos de penetración dinámica DPSH realizados, se les
> asocian **valores de Nb irregulares, con un valor medio de entre 15 a 38**, con valores de rechazo a la
> penetración Nb>100, en alcanzar un bolo de grandes dimensiones."

*Interpretació:* la taula signada porta L1 Nb=**5** (punt mig del rang narrat 4-6, ignorant els "12
puntuales") i L2 Nb=**15-R** (l'extrem BAIX del rang narrat 15-38 + R). Quan el nivell és irregular, Eva
**tria l'extrem inferior del rang de mitjanes** per a la cel·la Nb — un criteri de prudència no documentat
fins ara. La N (=6) torna a sortir de l'SPT.

**EVIDÈNCIA DOCUMENTAL (p33-38, fulls "ENSAYO DE PENETRACIÓN DINÁMICA" P-1..P-6):** capçalera idèntica a
Bell-lloc — factor **"0,83"** imprès entre les columnes **"Golpeo DPSH"** i **"Golpeo NB"**. Confirma P1 en
el segon informe.

### 2.3 Llegendes de la Tabla 10 (p24) — transcripció ÍNTEGRA i literal

Taula: "1er nivel. Arcillas arenosas | 5 | 6 | 1.90 | 0.10 | 28º | 90" i "2do nivel. Bolos y gravas en
matriz areno-arcillosa | 15-R | -- | 2.00 | 0.00 | 38º | >350".

> "(1) Densidad expresada en gr/cm3.
> (2) Cohesión expresada en Kg/cm2. Tanto la cohesión como el ángulo de rozamiento interno son valores
> efectivos o a largo plazo.
> (3 y 4) Módulo de deformación en Kg/cm2
>
> Los parámetros de cohesión y ángulo de rozamiento interno de los materiales se han obtenidos de las
> relaciones que se establecen en el libro "Mecánica de suelos y cimentaciones" del autor Carlos Crespo
> Villalaz, a partir de la resistencia de los materiales."

*Nota:* la numeració de les notes és inconsistent amb Bell-lloc ("(3 y 4) Módulo" quan (3) és l'angle de
fricció — errata d'edició). Semànticament idèntic: **unitats + Crespo per a c/φ; cap font per a l'E**.
L'E=90 del nivell d'argiles fluixes (per sobre del rang CTE 0-82) **no té cap frase de justificació** en
tot l'informe — les úniques mencions d'E són la llegenda (p24) i el boilerplate de Schmertmann (p31).

### 2.4 Assentaments i altres

**CITA LITERAL (p25):** "Los asientos máximos previstos para la carga recomendada anteriormente serán
inferiores a 1.5 cm." (sense la coda "immediats" de Bell-lloc — aquí el material portant és granular però
el text no ho remarca).

**CITA LITERAL (p25-26, §4.4 EMPUJE DE TIERRAS):** "habrá que tener en cuenta los parámetros geomecánicos
de los materiales del primer nivel que se considera el más desfavorable." — mateix criteri narratiu que
Castellar/Rubí (METODOLOGIA §5.5): paràmetres del nivell més desfavorable, sense càlcul.

BASE DE CÁLCULO (p29-31): boilerplate idèntic al de Bell-lloc (Rodríguez Ortiz bicapa, Terzaghi,
Terzaghi-Peck, Schmertmann 2,5/3,5, límits 2,54/5 cm). Res de nou.

### 2.5 Nou vs METODOLOGIA-EVA: **SÍ — i corregeix un error**

1. **La premissa "Anciles fonamenta a L1" és falsa segons el text signat**: pous encastats 20-40 cm a L2.
   Cal revisar la narrativa de METODOLOGIA §0.4 i CRITERIS §1/§6 (l'outlier Qa=2,0 queda MÉS obert, no
   menys: és un Qa sobre L2 competent però irregular).
2. Criteri nou: **cel·la Nb = extrem inferior del rang de mitjanes quan el registre és irregular** (15 de
   "entre 15 a 38").
3. Segona confirmació del factor 0,83/columna NB als fulls d'annex (P1).
4. E=90: cap justificació textual (troballa negativa per P3, consistent amb Bell-lloc).

---

## 3. RUBÍ (3001631)

**Fitxer llegit:** `/home/josep/g3dt-e2e/projectes/3001631 RUBI/PDF/3001631_informe.pdf`
(47 pàgines PDF; llegides: 10, 12-14, 20-21, 28-30, 34).

### 3.1 Un sol nivell — i és el de les GRAVES (context per a l'ANALISI §6)

**CITA LITERAL (p12, §3.2):**

> "A partir dels assaigs in situ realitzats, **s'ha establert un sòl nivell de materials** des del punt de
> vista geològic - geotècnic: [...] 1er nivell. Graves i sorres, carbonatades"

**CITA LITERAL (p13):** "Aquest materials s'associa als materials de la unitat NMgo, amb un tram
superficial alterat i intercalant tram més consolidats en la base." I classificació: "es podran classificar
els materials de com tipus **SM**."

*Interpretació:* Eva descriu **un únic nivell granular** (graves i sorres SM) que engloba també els trams
consolidats de la base — exactament el contrari del col·lapse actual del pipeline, que vesteix el nivell
únic amb la descripció de la capa MÉS PROFUNDA (gresos/lutites → roca). Confirma el diagnòstic
d'`ANALISI-CALCUL-N20-E-2026-09-02.md` §6 amb el text signat.

### 3.2 Nb i N

**CITA LITERAL (p14, Resistència):**

> "Des del punt de vista geomecànic es tracta d'uns materials de caràcter generalment granulars, amb una
> densitat i una capacitat portant **mitja**. Dels assaigs de penetració dinàmica DPSH s'obté un valor de
> **Nb mig de 48** fins assolir rebuig a la penetració, Nb >100, associada a materials de substrat regional
> carbonatat."

**Dades:** Taula 9 (p20) diu **47-R** (narrativa: 48 — discrepància interna d'1 punt). **N=40** surt de
l'assaig SPT: resum p10: "SPT-1 | P-3 | -0.60 a -1.20 | 40 | Graves i sorres" (SPT fet dins del punt P-3).
Tercera confirmació que la columna N = SPT.

**Fulls d'annex (p28-30):** mateix format 0,83 / "Colpeig DPSH" / "Colpeig NB". Valors NB complets
transcrits (P-1: 27,40,36,30,27,29,24,41,42,72,77,57,33,31,39,43,45,34,36,63,80,120R; P-2:
12,29,34,51,57,40,34,42,46,29,48,36,24,33,45,65,120R; P-3: 39,43,34,47,45,39,39,72,59,41,30,43,57,96,120R).

*Interpretació aritmètica (marcada com a tal):* la mitjana global de TOTS els valors NB **incloent els 120
del rebuig** dona 47,7 (→ narrativa 48, taula 47); excloent els rebuigs dona 43,4 (no quadra). A Rubí, el
"Nb mig" sembla cobrir **tot el perfil**, rebuig inclòs — a diferència de Bell-lloc, on el 25 només s'obté
del tram superficial. El tall de correlació (p34) porta etiquetes per tram: Nb=40, Nb=47, Nb=48, Nb=77,
Nb=45 i Nb=R (×3) — el 47 i el 48 signats hi apareixen tots dos. **Cap regla única tancada: P4 queda
parcialment obert** (vegeu Respostes).

### 3.3 Llegendes Taula 9 (p20) — literals

Idèntiques a Bell-lloc, paraula per paraula (Crespo per c/φ; "(1) Densitat està donada en gr/cm3; (2 i 3)
La cohesió està expressada en Kg/cm2. Tan la cohesió com l'angle de fregament intern són valors efectius o
llarg termini; (4) Mòdul de deformació, Kg/cm2"). **Cap font declarada per a l'E=450.** L'única
caracterització narrativa del nivell: "densitat i capacitat portant **mitja**" (p14) — tot i el Qa=3,5
final. Cap menció que lligui la carbonatació amb l'E.

### 3.4 Fonamentació, Qa, assentaments, K30

**CITA LITERAL (p21):**

> "Per una fonamentació mitjançant sabates o bé llosa, **encastada entre 30-40 cm en els materials del
> primer nivell sanejat un cop extret el tram superficial**, es podrà adoptar una tensió admissible de:
> Qa= 3.50 Kg/cm2 amb un factor de seguretat inclòs de F=3
>
> Els assentaments màxims previstos per la càrrega recomanada anteriorment seran **iguals o inferiors a
> 1.50 cm, immediats en el temps donat el comportament granular** dels materials.
>
> Com a valor de coeficient de balast referit a la placa de 30x30, es podrà adoptar un valor de
> K30= 6.0 kg/cm3."

*Nota:* encastament 30-40 cm (Rubí) / 20-40 cm (Anciles) — el número d'encastament mínim al nivell portant
apareix sistemàticament. També apareix (p20, final) la frase "Donada les propietats geomecànica dels
materials del primer i segon nivell" quan l'informe només en descriu UN — romanent de plantilla.

### 3.5 Nou vs METODOLOGIA-EVA: **SÍ**

1. Text signat que confirma que a Rubí el nivell únic és el de les graves (SM), incloent els trams
   consolidats — suport documental per corregir el col·lapse (ANALISI §6).
2. "Nb mig de 48" narratiu vs "47-R" a taula: segona discrepància interna narrativa/taula (com el N 54/58
   de Bell-lloc).
3. Aritmètica del 47-48 compatible només amb mitjana de TOT el perfil rebuig inclòs (P4: comportament
   diferent de Bell-lloc).
4. "capacitat portant mitja" + Qa=3,5: l'adjectiu narratiu no segueix l'escala del topall (a Anciles L2
   "media a elevada" → 2,0; aquí "mitja" → 3,5).

---

## 4. LINYOLA (4001607)

**Fitxer llegit:** `/home/josep/g3dt-e2e/projectes/4001607 LINYOLA/PDF/4001607_informe.pdf`
(49 pàgines PDF; llegides: 14-15, 22-24).

### 4.1 Nb i N

**CITA LITERAL (p14, Resistència 1er nivell):**

> "es tracta d'uns materials amb un comportament des de granular a friccional, amb una densitat i una
> capacitat portant baixa. Dels assaigs de penetració dinàmica s'obté un valor de **Nb mig de 11**."

**CITA LITERAL (p15, Resistència 2on nivell):**

> "es tracta d'uns materials amb un comportament des de friccional a roca tova, amb una densitat i una
> capacitat portant elevada. Dels assaigs de penetració dinàmica s'obté **valors de Nb des de 31, en el
> tram més alterat, i posteriorment rebuig** a la penetració, Nb>100. De l'assaig SPT realitzat en aquest
> nivell s'obté un valor de **N de R (rebuig a la penetració)**."

**Taula 10 (p22):** L1 "13 | -- | 1.90 | 0.05 | 28 | 100"; L2 "31-R | R | 2.20 | 1.0 | 30 | >800".
Llegendes al peu **idèntiques literalment** a Bell-lloc/Rubí (Crespo per c/φ, unitats, res per a l'E).

*Interpretació:* (a) **tercera discrepància narrativa/taula**: "Nb mig de 11" al text, **13** a la taula;
(b) el format "31-R" torna a llegir-se "31 al tram alterat, després R" — el número de l'esquerra és el tram
SUPERIOR del nivell, no cap mitjana de tot el nivell; (c) columna N: "--" quan no hi ha SPT al nivell, "R"
quan l'SPT hi va fer rebuig — N sempre i només de l'SPT.

### 4.2 Expansivitat — DUES FONTS NOVES amb criteri explícit

**CITA LITERAL (p23):**

> "A partir de les taules proposades, Luis I. Gonzalez Vallejo, en el llibre INGENIERIA GEOLÓGICA, quadre
> 2.12, els materials presenten un potencial d'expansivitat baix. L'assaig Lambe per a valorar el
> potencial d'inflament és MARGINAL.
>
> Del capítol 5, del volum III, de "Geotecnia y Cimientos" de J. A. Jiménez Salas y otros, s'ha obtingut
> una fórmula empírica que, basada en el límit líquid del sòl (WL), ens defineix, quan el Lambe ens alerta
> sobre una possible expansivitat, la pressió d'inflament i l'inflament real per una pressió determinada.
>
> Per tant a partir del valor de límit líquid, s'obté un valor de pressió d'inflament un valor de
> 0.82 Kg/cm2."

I el criteri d'ús (p23, literal):

> "Els resultats obtinguts no són preocupants, per tant caldria que la **fonamentació es treballi sobre
> aquests materials a més tensió del potencial d'expansivitat**."

*Interpretació:* cadena completa d'expansivitat: llindar WL>35 dispara l'alerta (p22: "41.7 [...] superior
a 35.0, que seria el valor a partir del qual s'esperaria que provablement es podrien produir problemes") →
González Vallejo quadre 2.12 classifica el potencial → Lambe el valora → si Lambe alerta, fórmula de
Jiménez Salas (Geotecnia y Cimientos III, cap. 5) dona la pressió d'inflament des del WL → **criteri: la
tensió de treball de la fonamentació ha de superar la pressió d'inflament**.

### 4.3 Fonamentació i Qa

**CITA LITERAL (p23-24, §4.4):**

> "tenint en compte les propietats geomecàniques dels materials del primer nivell i el seu diferent
> desenvolupament al llarg de tot el solar, es realitzarà una valoració de fonamentació **combinada entre
> superficial i mitjançant pous reomplerts de formigó pobre, recolzada sobre els materials del segon
> nivell sanejat**. [...] Per una fonamentació combinada entre sabates i pous reomplerts de formigó pobre,
> **encastats entre 30-40 cm els materials del segon nivell sanejat**, es podrà adoptar una tensió de
> treball de: Qa= 3.0 Kg/cm2 amb un factor de seguretat inclòs de F=3
>
> Els assentaments màxims previstos per la càrrega recomanada anteriorment seran **menyspreables o bé
> inferiors a 1.0 cm**."

*Interpretació:* consistent amb CRITERIS §1 (Linyola calcula amb L2). El motiu narrat per baixar a L2 no és
només la fluixedat de L1 sinó **"el seu diferent desenvolupament al llarg de tot el solar"** (L1 inexistent
a P-2 — gruix irregular). I tercer cas del patró d'encastament 20-40 cm al nivell portant sanejat.

### 4.4 Nou vs METODOLOGIA-EVA: **SÍ**

1. **Expansivitat: fonts i cadena noves** (González Vallejo quadre 2.12; Jiménez Salas vol. III cap. 5,
   fórmula WL→pressió d'inflament; llindar WL 35; criteri tensió > pressió d'inflament). METODOLOGIA no en
   parlava.
2. Tercera discrepància narrativa/taula al Nb (11 vs 13) — les cel·les Nb signades NO són sempre
   reproducció del narratiu.
3. Criteri de baixada a L2 inclou la **irregularitat del gruix de L1**, no només la resistència.
4. La frase d'assentaments "menyspreables o bé inferiors a 1.0 cm" (forma exacta de la frase genèrica).

---

## 5. ALCOLETGE (4001670)

**Fitxers llegits:** el PDF signat (`/home/josep/g3dt-e2e/projectes/4001670 ALCOLETGE/PDF/4001670_informe.pdf`,
18 pàgines) **només conté els annexos** (base de càlcul + fulls DPSH + tall). El cos narratiu s'ha llegit de
`/home/josep/g3dt-e2e/projectes/4001670 ALCOLETGE/4001670_informe.doc` convertit a PDF amb LibreOffice al
scratchpad — **les pàgines citades (16-17, 24-25) són d'aquest render, no del PDF signat** (28 pàgines
renderitzades).

### 5.1 Nb i N — el format "5-0" explicat

**CITA LITERAL (p16 render, Resistència 1er nivell):**

> "es tracta d'uns materials de caràcter generalment granular, amb una densitat i una capacitat portant
> **molt baixa**. Dels assaigs de penetració dinàmica DPSH s'obté un valor de **Nb mig de 5, amb
> puntualment valors de 0**."

**CITA LITERAL (p17 render, Resistència 2on nivell):**

> "es tracta d'uns materials amb comportament des de friccional a roca tova i dura, amb una densitat i una
> capacitat portant elevada. Dels assaigs de penetració dinàmica DPSH s'obté un valor de **Nb de rebuig a
> la penetració en profunditat, Nb>100**. De l'assaig SPT s'obté un valor de **N de 20, corresponent al
> primer tram d'alteració**."

*Interpretació:* la cel·la "5-0" de la taula = "Nb mig de 5, amb puntualment valors de 0" — el sufix rere el
guió és el valor extrem puntual (aquí 0; a "25-R"/"31-R"/"47-R" és el rebuig). El guió NO és un rang: és
"mitjana-extrem". La N=20 torna a ser l'SPT, i Eva diu explícitament a QUIN tram correspon (el tram
d'alteració del substrat).

### 5.2 Taula 9 (p24 render) i llegendes

L1 "Sorres argiloses de rebliment | 5-0 | -- | 1.80 | 0.00 | 28º | 50"; L2 "Lutites i sorrenques alterades |
R | 20 | 2.00 | 1.00 | 30º | >400". Llegendes al peu **idèntiques literalment** als altres informes (Crespo
per c/φ; unitats; cap font per a l'E).

### 5.3 Fonamentació i Qa — Qa=3,5 sobre un nivell amb c=1,0

**CITA LITERAL (p25 render, §4.3):**

> "Un cop realitzada l'excavació afloraran superficialment els materials del primer nivell descrit, que
> degut a les seves propietats geomecàniques **es descarta totalment per a recolzar-hi qualsevol element de
> fonamentació**. La fonamentació haurà de quedar recolzada en els materials del segon nivell que es
> detecta entre 1.20 i 1.40 metres. [...] recolzada sobre els materials del segon nivell sanejat, es podrà
> adoptar una tensió de treball de: Qa= 3.50 Kg/cm2 amb un factor de seguretat inclòs de F=3
>
> Els assentaments màxims previstos per la càrrega recomanada anteriorment seran **menyspreable o bé menors
> a 1.0 cm**."

*Interpretació (contradicció amb CRITERIS §1):* el nivell portant signat és L2 ("lutites i sorrenques
alterades", c=1,00, "roca tova i dura") i el Qa signat és **3,5** — però la regla reverse-engineered diu
ROCK (c≥0,5) → cap **3,0**. O bé Eva tracta les "lutites alterades" com a granular dens (tot i c=1,0), o bé
el cap de roca no és 3,0 quan el substrat dona rebuig continu. A més, el "Nb=30 / graves carbonatades /
E=500" que CRITERIS §5 atribueix a Alcoletge no existeix al signat (confirma el lapsus ja anotat a
`ANALISI-CALCUL-N20-E-2026-09-02.md` §6, nota final).

### 5.4 Nou vs METODOLOGIA-EVA: **SÍ**

1. Lectura del format de cel·la "X-Y" (mitjana-extrem puntual, no rang): "5-0" ← "Nb mig de 5, amb
   puntualment valors de 0".
2. Qa=3,5 signat sobre nivell amb c=1,0: **trenca la fila ROCK→3,0** de CRITERIS §1 (Castellar hi queda com
   a únic testimoni del cap 3,0 en roca).
3. N=20 amb atribució explícita de tram ("corresponent al primer tram d'alteració").
4. La cita "es descarta totalment..." ja era a METODOLOGIA §5.9 — aquí se'n confirma el literal.

---

## 6. CASTELLAR DEL VALLÈS (3001621)

**Fitxer llegit:** `/home/josep/g3dt-e2e/projectes/3001621 CASTELLAR DEL VALLES/PDF/3001621_informe.pdf`
(50 pàgines PDF; llegides: 16, 22-23, 31-34, 40). Hoek & Bray, sísmica, K30, empentes i excavabilitat ja
eren transcrits a METODOLOGIA §5 — no es repeteixen.

### 6.1 Nb — la discrepància narrativa/taula MÉS GRAN

**CITA LITERAL (p16, Resistència):**

> "es tracta d'uns materials amb un comportament des de friccional a roca dura, amb una densitat i una
> capacitat portant de mitja a elevada. Dels assaigs de penetració dinàmica s'obté valors de **Nb des de 44
> a ràpidament rebuig** a la penetració en profunditat, Nb>100."

**Taula 10 (p22):** "1er nivell: Bretxes amb intercalacions de lutites i gresos | **17-R** | R | 2.20 | 1.0
| 35º | >500". Llegendes al peu idèntiques als altres (Crespo per c/φ, unitats, cap font per E).

**Dades dels annexos:** fulls DPSH (p31-34, mateix format 0,83/NB): P-1: 7,12,16,46,R; P-2: 18,R; P-3:
19,55,R; P-4: 10,10,14,33,25,34,R. Tall de correlació (p40): etiquetes Nb=19, Nb=16, Nb=18, Nb=33, Nb=10,
Nb=R (×3), N=R.

*Interpretació:* ni el 44 narratiu ni el 17 de la taula tenen una derivació aritmètica exacta dels valors
NB dels annexos (mitjana global sense rebuigs = 23,0; amb els rebuigs convertits a 120 = 45,8 — propera
però no igual al 44 narratiu; mitjana de les tres etiquetes superficials del tall 19/16/18 = 17,7 → 17?).
És la **quarta i més gran discrepància narrativa/taula** (44 vs 17): el 44 narratiu s'assembla a la
mitjana amb rebuigs (45,8) i el 17 de la taula a la dels trams superficials del tall (17,7) — com si
narrativa i taula responguessin a criteris diferents. L'SPT va fer rebuig (N=R), coherent amb la columna
N=R.

### 6.2 Fonamentació

**CITA LITERAL (p23):**

> "Per una fonamentació superficial mitjançant sabates, ja sigui aïllades com corregudes, **encastada entre
> 20-30 cm en els materials de substrat, un cop superats els materials superficials**, es podrà adoptar una
> tensió de treball de: Qa= 3.0 Kg/cm2 amb un factor de seguretat inclòs de F=3
>
> Els assentaments màxims previstos per la càrrega recomanada anteriorment seran menyspreables o bé
> inferiors a 1.0 cm.
>
> Si s'optés per una fonamentació amb llosa, el valor de coeficient de balast, referit a la placa de 30x30,
> es podrà adoptar un valor de K30=8.00 kg/cm3."

*Interpretació:* cinquè cas del patró d'encastament (20-30 cm aquí). El K30 només s'ofereix quan hi ha
opció de llosa — i sense fórmula, com ja sabíem (METODOLOGIA §5.8).

### 6.3 Nou vs METODOLOGIA-EVA: **poc — 2 coses**

1. La discrepància Nb narratiu 44 vs taula 17-R (no anotada enlloc).
2. El patró sistemàtic "encastada entre X-Y cm en el nivell portant sanejat" (aquí 20-30 cm) com a part de
   la frase del Qa. La resta (Hoek & Bray, K30, sísmica, empentes, excavabilitat, permeabilitat) ja era a
   METODOLOGIA §5.

---

## 7. VILANOVA DE SEGRIÀ (4001671) — en castellà, LLETRA NO DISPONIBLE

**Fitxers llegits:** `/home/josep/g3dt-e2e/projectes/4001671 VILANOVA DE SEGRIA/PDF/4001671_informe.pdf`
(20 pàgines: **només annexos** — base de cálculo p2-5, fulls DPSH p7-9, corte p12-13, fotos, actes lab).
**La lletra narrativa no existeix en cap ubicació accessible** (ni .doc/.docx al projecte e2e, ni a
`/mnt/c/claude/g3dt/projectes/`, ni a `dades-eva/`, ni a reference-material; `PDF/LETRA/` només conté la
portada). Per tant **no hi ha cites literals del text narratiu possibles** per a aquest projecte.

### 7.1 El que els ANNEXOS signats sí que diuen (literal)

- Fulls DPSH (p7-9): mateix format que tots els altres — factor **"0,83"** imprès, columnes "Golpeo DPSH" /
  "Golpeo NB". NB per punt: P-1: 7,8,10,22,29,93,120R; P-2: 5,8,10,14,12,14,16,36,55,120R; P-3:
  4,5,8,6,5,7,7,12,10,16,11,14,31,45,48,16,30,120R. Anotacions "SPT1"/"SPT-1" a -0,8 m dins P-1 i P-3.
- Corte de correlación (p13), llegenda literal: "**Nivel 1: Arcilla limosa y arenosa con algunas gravas.**"
  / "**Nivel 2: Arenas finas-medias, carbonatadas.**" / "Cota de cimentación" / "**Cota de nivel
  freático**" (únic projecte dels 7 amb NF marcat al tall). Etiquetes per tram: Nb=8, Nb=11, Nb=8, Nb=25,
  Nb=46, Nb=28 i Nb=R (diversos).

### 7.2 Evidència secundària (extracció pròpia del .doc d'Eva, NO citable com a literal)

`reference-material/4001671 VILANOVA DE SEGRIA/validation/eva_reference_values.json` (reference extractor,
`table_flatten`, confiança 0,95) recull de la taula geotècnica signada:

| Nivell | Nb | N | γ | c | φ | E |
|---|---|---|---|---|---|---|
| 1er nivel: Arcilla limosa y arenosa con gravas | 9 | 10 | 1.90 | 0.10 | 25º | 50 |
| 2do nivel: Areniscas, arenas, sustrato | 57-R | 24 | 2.20 | 0.50 | 34º | 550 |

amb `qa_value` = "2.50 Kg/cm2 con un factor de seguridad incluido de F=3" i `settlement` = "Los asientos
máximos previstos [...] serán menospreciables o inferiores a 1.0 cm." I `conclusions_levels_detected` =
"**dos niveles** de materiales" — coherent amb la llegenda del corte signat (§7.1).

### 7.3 Nou vs METODOLOGIA-EVA: **SÍ — contradiu la taula de referència que fem servir**

**La fila "Vilanova | Llims argilosos | Nb=15 | γ=1.90 | c=0.05 | φ=28 | E=100 | Qa=2.5" de
`CRITERIS-CALCUL-EVA.md` §5 NO quadra amb cap de les dues fonts d'aquí** (annexos signats: 2 nivells;
json: Nb=9/φ=25/E=50 al nivell 1). Sembla un segon lapsus del mateix tipus que el d'Alcoletge (ja anotat a
`ANALISI-CALCUL-N20-E-2026-09-02.md` §6, nota final). Afecta també l'exemple d'"arrodoniment intermedi" de
CRITERIS §1 (que argumenta amb "Vilanova phi=28→30") i deixa E=50 amb Nb=9 com a segon cas de "règim fluix"
per a P3 (50 està dins del rang CTE 0-82, a la part mitjana-alta — com Alcoletge L1). **Pendent: verificar
contra el .doc real si mai torna a estar accessible** (l'extractor el va llegir en el seu moment).

---

## 8. RESPOSTES A P1 / P3 / P4

### P1 — Què és la cel·la "Nb" de la taula geotècnica? → RESOLTA (documentalment)

**Nb = N20 del DPSH dividit per 0,83, arrodonit a enter — i la cel·la porta una MITJANA d'aquests valors.**
Evidència: (a) els fulls d'annex de TOTS els projectes llegits imprimeixen el factor "0,83" entre les
columnes "Colpeig/Golpeo DPSH" i "Colpeig/Golpeo NB", i l'aritmètica NB=DPSH/0,83 quadra fila a fila
(§1.1, §2.2, §3.2, §6.1, §7.1); (b) la narrativa anomena sistemàticament aquest valor "**Nb mig**"
(Bell-lloc 25, Rubí 48, Linyola 11, Alcoletge 5, Anciles 4-6). La conclusió §7.3 de
`ANALISI-CALCUL-N20-E-2026-09-02.md` ("la cel·la Nb probablement no ha de dividir per 0,83") **queda
qüestionada**: el vocabulari d'Eva és inequívoc — Nb ÉS el valor corregit per 0,83. El que queda obert és
només QUIN tram entra a la mitjana (vegeu P4).

**Bonus P1:** la columna "N" ve SEMPRE de l'assaig SPT del sondeig ("--" si no n'hi ha al nivell, "R" si
hi va fer rebuig; cites a §1.1, §2.2, §3.2, §4.1, §5.1) — confirma la conclusió §7.3 de l'ANALISI sobre la
columna N. I la regla textual del N30 (dos trams centrals; si el darrer tram és menor, els dos més petits
dels tres darrers) és a §1.1.

### P3 — El criteri de l'E → NO RESOLTA: els informes NO l'expliquen

Troballa negativa consistent als 6 informes amb lletra: la llegenda "(4)" de la taula diu només "**Mòdul de
deformació, Kg/cm2**" (unitats), la nota de font (Crespo) cobreix NOMÉS c i φ, i **cap frase narrativa
justifica cap valor d'E** (ni el 650 de Bell-lloc, ni el 90 d'Anciles, ni el 450 de Rubí). L'única matèria
prima que els informes ofereixen per a l'E són els adjectius de la secció "Resistència" ("capacitat portant
baixa / molt baixa / mitja / de mitja a elevada / elevada") i la litologia del nom del nivell
("carbonatades"). La correlació adjectiu→E tampoc és neta (Rubí "mitja"→450; Anciles L2 "media a
elevada"→>350; Bell-lloc "elevada"→650). **El criteri de l'E s'ha de demanar a Eva** — els informes signats
no el descriuen. (Les preguntes ja redactades a `CALCUL-E-MODUL-DEFORMACIO.md` §8 continuen sent el camí.)

### P4 — Perfil d'un sol nivell: Nb de tot el perfil o del tram on recolza? → PARCIALMENT RESOLTA

Els tres casos mono-nivell (Bell-lloc, Rubí, Castellar) donen respostes NO idèntiques:
- **Bell-lloc (taula 25):** només s'explica amb els trams superficials — la mitjana de trams del tall és 27
  (P-1) i 22/56 (P-2), i (27+22)/2 = 24,5 → 25; qualsevol mitjana que inclogui el tram profund de P-2 (56)
  o els rebuigs (120) dona 43-45. La frase "Nb mig **des de 25 fins assolir rebuig**" descriu un gradient,
  i pren el valor BAIX (superficial, on recolza la sabata) per a la cel·la.
- **Castellar (taula 17, narrativa 44):** la cel·la de la taula quadra amb els trams superficials del tall
  (19/16/18 → 17,7) i el 44 narratiu amb la mitjana global amb rebuigs (45,8) — taula i narrativa semblen
  seguir criteris diferents (§6.1).
- **Rubí (taula 47, narrativa 48):** tots dos només s'expliquen amb TOT el perfil INCLOENT els rebuigs
  convertits (120): mitjana global = 47,7 (sense rebuigs = 43,4; cap mitjana superficial s'hi acosta).

*Interpretació honesta:* no hi ha una regla algorítmica única als informes. Dos de tres casos posen la
cel·la de la taula als **trams superficials pre-rebuig (la zona on recolza la fonamentació)**; Rubí, amb el
perfil homogèniament competent i el rebuig només al fons, fa la mitjana de tot. El patró compatible amb els
tres: **la cel·la Nb representa el tram on treballarà la fonamentació; quan tot el perfil és aquest tram
(Rubí), la mitjana és global**. La pregunta redactada per a Eva a `ANALISI-CALCUL-N20-E-2026-09-02.md` §4
continua sent necessària; aquestes dades la fan més concreta (es pot preguntar directament amb Bell-lloc,
Castellar i Rubí davant).

---

## 9. CONTRADICCIONS AMB EL QUE CRÈIEM

1. **Anciles NO fonamenta a L1** (§2.1). El text signat: pous de formigó pobre "empotrados un mínimo de
   20-40 cm de los materiales del segundo nivel saneado, superando en todo momento los materiales del
   primer nivel". Contradiu `CRITERIS-CALCUL-EVA.md` §1 ("es recolza en L1... no arriba a L2") i
   `METODOLOGIA-EVA.md` §0.4. L'outlier Qa=2,0 és sobre L2 (bolos, φ=38) — el misteri canvia de forma:
   ja no és "per què usa L1", sinó "per què 2,0 sobre un nivell competent però irregular".
2. **La cel·la Nb SÍ que és N20/0,83** (§8-P1) — contra la hipòtesi de treball de l'ANALISI §7.3 ("la
   cel·la Nb probablement no ha de dividir per 0,83").
3. **Alcoletge Qa=3,5 amb nivell portant de c=1,0** (§5.3) — trenca la fila "ROCK (c≥0,5) → cap 3,0" de
   CRITERIS §1 tal com està formulada (o les "lutites alterades" no compten com a roca al criteri del cap).
4. **La fila Vilanova de CRITERIS §5 sembla un lapsus** (§7.3): el signat té 2 nivells i (via extractor)
   Nb=9/φ=25/E=50 al nivell 1, no "1 nivell, Nb=15/φ=28/E=100". L'exemple d'arrodoniment intermedi de
   CRITERIS ("Vilanova phi=28→30") queda tocat.
5. **Les cel·les de la taula NO sempre reprodueixen el narratiu**: 4 discrepàncies internes
   narrativa↔taula/tall — Bell-lloc N 54 vs 58; Rubí Nb 48 vs 47; Linyola Nb 11 vs 13; Castellar Nb 44 vs
   17-R. Implicació per al pipeline: reproduir Eva "exactament" és impossible fins i tot per a Eva; els
   tests de MATCH han de tolerar aquesta banda (±2 en Nb; a Castellar la banda és enorme i probablement hi
   ha un error humà en un dels dos llocs).
6. **El format de cel·la "X-Y" no és un rang**: és "mitjana(-extrem puntual)": "5-0" = mitjana 5 amb
   puntuals 0 (Alcoletge §5.1); "25-R"/"31-R"/"47-R" = mitjana/valor del tram i rebuig després.

## 10. ALTRES TROBALLES NOVES (resum transversal)

- **Encastament sistemàtic al nivell portant**: la frase del Qa porta sempre "encastada/empotrada entre
  20-30 / 30-40 / 20-40 cm en els materials del [nivell portant] sanejat" (5 projectes; §2.1, §3.4, §4.3,
  §5.3, §6.2). És un paràmetre de sortida de l'informe que el pipeline hauria de generar.
- **Expansivitat (Linyola §4.2)**: cadena completa amb DUES fonts noves — González Vallejo (Ingeniería
  Geológica, quadre 2.12) i Jiménez Salas (Geotecnia y Cimientos III, cap. 5, fórmula WL→pressió
  d'inflament), llindar WL>35, criteri "tensió de treball > pressió d'inflament".
- **Regla del N30 de l'SPT amb tram final menor** (Bell-lloc §1.1) — cap document nostre la tenia.
- **Topall d'assentament per llosa = 5 cm** (2 polzades), a més del 2,54 de sabates (§1.4) — "segons
  Terzaghi".
- **La frase d'assentaments té 3 formes fixes**: "menyspreables o bé inferiors/menors a 1.0 cm" (roca o
  perfil competent), valor precís "inferiors a X cm" (granular amb assentament calculat ≥1), amb coda
  "immediats en el temps donat el comportament granular" quan el nivell portant és granular (§1.4, §3.4).
- **Anciles V0 conté un placeholder "xxxxxxx"** (§2, agressivitat) — el PDF V0 dels projectes no és
  necessàriament l'informe final entregat.

---
*Fi tasca R. Lectura dirigida dels 7 informes signats: P1 resolta (Nb=N20/0,83, mitjana per tram), P3
negativa (l'E no s'explica als informes — cal Eva), P4 parcial (superficial a Bell-lloc, global a Rubí),
4 contradiccions documentades amb CRITERIS/METODOLOGIA/ANALISI.*
