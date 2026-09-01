# Disseny — interpretació d'adreces i municipi (sessió d'anàlisi, 2026-09-01 nit)

**Estat: ANALITZAT I DECIDIT.** Aquest document tanca
`docs/PROPOSTA-JOSEP-ADRECES-I-MUNICIPI-2026-09-01.md` (que quedava «ANOTADA, NO ANALITZADA»). Les set preguntes
de §3 d'aquell document tenen resposta acordada amb el Josep, i la pregunta A1 també.

**Encara no hi ha codi cablejat.** L'única cosa entregada avui és un fitxer de dades inert
(`automation/data/municipis_padro_cadastre.json`), que ningú importa.

---

## 1. Diagnòstic: on es perd la informació

Cadena real d'avui, de l'adreça llegida a la superfície de la parcel·la:

```
skill de lectura (Claude Code)  →  street_address = text lliure, tal com surt al document
        ↓
portals_from_address()          →  regex: (nom_carrer, [(núm, lletra), …])
        ↓
_cached_consulta_municipio()    →  prova LLEIDA/BCN/GIRONA/TGN/HUESCA, fuzzy del Cadastre
        ↓
_cached_consulta_via()          →  via B: escurçament progressiu → difflib 0,80 → picker LLM (Groq)
        ↓
_via_name_matches()  (guarda nostra, 0,85)          ← AQUÍ ES DESCARTA
        ↓
resolve_portal()  (pnp, plp) EXACTES  →  WFS: àrea + polígon  →  contigüitat  →  senyals
```

Ja hi havia intel·ligència a la cadena (`_llm_pick_street`, Groq, dins de via B) i **la guarda que vam estrenar
el 2026-09-01 la descarta**. Mesurat executant el codi:

| llegit | oficial del Callejero | ràtio | resultat avui |
|---|---|---:|---|
| `11 de Setembre` | `ONZE DE SETEMBRE` | **0,750** | ❌ descartat → blanc |
| `Girassols` | `GIRASOLS DELS` | 0,941 | ✅ acceptat |
| `Major` | `MAJOR DE BALAFIA` | 0,556 | ❌ (correcte: és un altre carrer) |

**El problema no és partir l'adreça** — `portals_from_address` aguanta bé després dels fixos del code-review:

```
'Carrer Arbrells, 18A, 18B i 20'   → ('Arbrells', [('18','A'),('18','B'),('20','')])
'Carrer 11 de Setembre, 5'         → ('11 de Setembre', [('5','')])
'Avda. Catalunya 24, 3r 2a'        → ('Catalunya', [('24','')])
'Ctra. de Lleida, km 3'            → ('Lleida', [])        ← sense portal, honest
```

**Ni consultar** — les consultes existeixen i funcionen. El problema és **(a)** que no tenim grafies
alternatives per reintentar i **(b)** que la guarda d'acceptació compara contra una sola grafia.

## 2. La regla que evita ressuscitar el bug 18B→18A

`docs/PROPOSTA-JOSEP-ADRECES-I-MUNICIPI-2026-09-01.md` §2 exigia explicar com un mecanisme de «reintent amb
alternatives» evita reproduir el bug conegut de la via B (delegar al portal més proper). Resposta:

> **Els alternatius es permeten a l'eix via/municipi, mai a l'eix portal.**

Les variants de via i municipi són **ortogràfiques** (`11`↔`ONZE`, `GIRASSOLS`↔`GIRASOLS`, accents, ca/es):
designen el mateix objecte del món. Les variants de portal són **edificis diferents** — 18A i 18B són dues
parcel·les amb dos propietaris. `resolve_portal` continua filtrant `(pnp, plp)` exactes i no delega mai.

## 3. Decisions

| # | Decisió | Motiu |
|---|---|---|
| **D1** | **Qui interpreta: el skill de lectura**, no una capa nova | És l'únic lloc que veu totes les grafies de la mateixa adreça dins del projecte (comanda N20, pressupost bloc OBRA, fitxa C7, plànol, correus) i ja té el municipi de 3 fonts. Ja paguem la passada LLM |
| **D2** | **L'objecte estructurat és sortida del lector**, al costat de `street_address` (que es queda com a text humà per a l'informe) | L'Eva la pot veure al popup, viatja amb la cache de lectura, no costa una segona passada, i el 0-diff la veu |
| **D3a** | **Municipi: padró local.** Fitxer genèric per a tots els projectes; si un municipi no hi és, consultar el Cadastre i **ampliar el fitxer** | Determinista, cost 0, sense xarxa. Fet avui per a les 4 províncies catalanes (§4) |
| **D3b** | **Via: conjunt tancat.** El model tria **d'una llista real** de carrers del municipi; Python **verifica que el nom triat hi és literalment** | L'al·lucinació esdevé estructuralment impossible: un carrer inventat no és a la llista i es rebutja |
| **D4** | **«Zero» = cap resultat o la guarda els rebutja tots. «Sospitós» = arriba resultat però falla una comprovació creuada.** Qui decideix: **Python determinista**, no el model | El model proposa candidats; la verificació és geomètrica. Així ERR = 0 es manté |
| **D5** | **El límit no és el nombre d'intents sinó el criteri d'acceptació** | Cada consulta són ~0,3-1 s i queda a la cache 90 dies; una lectura són 28-42 min. El criteri no es pot afluixar perquè portem molts intents fets |
| **D6** | **Presentació a l'Eva: igual que la resta del nivell A** — `candidats` + popup, amb l'àrea de cada parcel·la a l'etiqueta. Blanc = **blanc amb nota visible**, mai silenci | Avui el fracàs és un `logger.warning` que l'Eva no veu mai |
| **D7** | **Veto per punts de camp** (§6) | La comprovació més forta disponible, i gratis |
| **A1** | **Prompt amb esquema + exemples, validació a Python i re-pregunta si no parseja** | `claude -p` no dona temperatura ni descodificació restringida. Anar per API per tenir *structured output* significaria desfer la decisió de la via A del 2026-08-23. No cal: el contingut es verifica igualment contra el Cadastre. Un JSON mal format costa un reintent, no una parcel·la equivocada |

## 4. Padró de municipis — ENTREGAT AVUI

**Ja en teníem la meitat sense saber-ho.** `automation/data/municipalities_catalunya_ine.json` (947 municipis,
4 províncies, grafia oficial INE) existeix des del 2026-02-04. I l'`ine_code` **és** la parella `(cp, cm)` del
Cadastre: `25048` = cp 25 / cm 48.

Faltava la grafia del Cadastre. Baixada el 2026-09-01 amb 4 crides a `ConsultaMunicipio` (Municipio buit), 2,1 s:

```
LLEIDA 231 · BARCELONA 311 · GIRONA 221 · TARRAGONA 184  =  947
aparellats amb l'INE: 947/947      orfes: 0 als dos costats

25048  INE="Bell-lloc d'Urgell"     Cadastre="BELL-LLOC D'URGELL"
08051  INE='Castellar del Vallès'   Cadastre='CASTELLAR DEL VALLES'
25243  INE='Vielha e Mijaran'       Cadastre='VIELHA E MIJARAN'
```

→ **`automation/data/municipis_padro_cadastre.json`** (947 municipis, 178 KB). Camps: `ine_code`, `name_ine`,
`name_cadastre`, `province`, `province_cadastre`, `cp`, `cm`. **Ningú l'importa encara.**

Conseqüències:

- Per a un projecte català, **el municipi es resol 100 % offline**. Desapareix una crida de xarxa per projecte
  i el bucle de 5 províncies de `_cadastre_portal_signals_impl`.
- El residu de PLAN_COST (`EG VILANOVA SEGRIÀ` → `SEGRIÀ`, malament a 7 de 10 fitxers reals) deixa de ser una
  cosa que s'ha de creure: es casa contra 947 noms reals.
- Fora de Catalunya cal consultar en línia i ampliar el fitxer (anotat al seu `metadata`).

### 4.1 Peça 2 — cablejat del padró (2026-09-01 nit)

`automation/municipis.py` — càrrega mandrosa, índexs en memòria, `PADRO_FILE` substituïble pels tests.
`lookup(hint)` en tres capes, totes exigint un **sol guanyador**:

1. **exacte** — la clau del llegit és la d'un municipi;
2. **forma curta** — el llegit és el començament d'**un sol** municipi: `BELL-LLOC` → `Bell-lloc d'Urgell`,
   `CERDANYOLA` → `Cerdanyola del Vallès`. `CASTELLAR` encaixa amb quatre → `None`;
3. **preposicions** — mateixes paraules ignorant `de/del/la/i/…`: `VILANOVA SEGRIÀ` → `Vilanova de Segrià`.

**Sense capa difusa, a posta:** `CATELLAR` (errata real d'un fitxer del corpus) ha de quedar sense confirmar,
no acostar-se a `Castellar del Vallès`.

Detall que no es veu a ull nu i que va costar trobar: **136 municipis porten l'article a l'altra banda** —
`"Ametlla del Vallès, L'"` a l'INE i `"L' AMETLLA DEL VALLES"` al Cadastre. La clau de comparació el treu dels
dos extrems, i així `L'Ametlla`, `Ametlla` i `AMETLLA DEL VALLES` cauen totes al mateix lloc.

**Consumidor 1 — municipi sense xarxa** (`cadastre_reader`): el padró substitueix el bucle de fins a **5
crides** `ConsultaMunicipio` per projecte i encerta la província a la primera. El bucle en línia es manté com a
sortida per als casos que el padró no pot decidir: fora de Catalunya (**Anciles és de Benasc, Osca**) o noms
ambigus. Verificat de punta a punta: Castellar dona 1.284 m² amb `_consulta_municipio` saboteja.

**Consumidor 2 — validació del residu de PLAN_COST** (`g3_templates._plan_cost_municipi_confianca`). Regla de
disseny: **el padró només afegeix dubte, mai en treu.** Un residu que avui es corrobora es queda a 0,6. Motiu:
`_decisions.json` dels 9 corpus és la prova de no-regressió del projecte i pujar confiances hi mouria decisions
que avui són correctes. Mesurat sobre els 10 `PLAN_COST*.xlsx` reals:

| residu d'E9 | abans | ara | què hi guanyem |
|---|---:|---:|---|
| `CASTELLAR DEL VALLÈS`, `RUBI`, `LINYOLA`, `ALCOLETGE` | 0,6 | 0,6 | confirmats contra 947 noms reals |
| `CERDANYOLA`, `BELL-LLOC` | 0,6 | 0,6 | nota amb la **forma oficial** (`Cerdanyola del Vallès`, `Bell-lloc d'Urgell`) |
| `VILANOVA SEGRIÀ` | 0,6 | 0,6 | nota: és `Vilanova de Segrià` sense les preposicions |
| `ANCILES` | 0,6 | **0,5** | «no consta al padró: o és de fora de Catalunya, o no és un municipi» |

El cas d'Anciles és el que justifica la peça: **Anciles no és un municipi** — és un llogaret de Benasc (Osca) —
i fins avui sortia amb la mateixa confiança que `Linyola`.

**Error de disseny que va destapar la suite, i que val la pena recordar:** el primer cablejat consultava el
padró **abans** que `_municipi_corroborat`, i així un PLAN_COST de Bell-lloc dins d'una carpeta de Torregrossa
tornava a pujar a 0,6 — el padró confirmava «Bell-lloc» i la contradicció amb la carpeta quedava tapada. Són
**guardes independents i mana la del context**: que «X» sigui un municipi de debò no vol dir que sigui el
d'aquest projecte. Ho va enxampar el test existent
`test_plan_cost_municipi_sense_corroborar_baixa_de_confianca`, i ara hi ha un test propi que ho fixa.

**Pendent conscient, no fet:** emetre la forma oficial llarga com a **candidat competidor** (avui només va a la
nota). És un canvi de valor, no de confiança, i mereix mesura pròpia sobre els corpus abans de fer-lo.

Tests: `tests/test_municipis_padro.py`, 33 casos, 0 xarxa. Dos tests existents de
`test_g3_templates.py` actualitzats: un perquè ara hi ha nota informativa on abans no n'hi havia cap, l'altre
només de docstring (el seu assert de 0,4 és justament el que va destapar l'error de dalt).

## 5. Via — el servei ja el tenim, i té un forat

`_consulta_via_all_streets()` fa `ConsultaVia` amb `NombreVia` buit → **la llista sencera de carrers del
municipi**. Una crida, ≤1 s. Mides mesurades el 2026-09-01:

| municipi | carrers | temps |
|---|---:|---:|
| Bell-lloc d'Urgell | 112 | 0,5 s |
| Castellar del Vallès | 481 | 0,6 s |
| Cerdanyola del Vallès | 577 | 0,8 s |
| Rubí | 835 | 0,8 s |

### 5.1 ⚠ El llindar de 500 — DEUTE OBERT, NO POT QUEDAR PENDENT

`geocode_coordinates._consulta_via` només activa el fuzzy i el picker LLM si `len(all_streets) <= 500`
(línia ~620). **Rubí (835) i Cerdanyola/Tulipa (577) queden fora**: si l'adreça no casa exactament, torna `None`
sense provar res més. Són **2 dels 8 projectes del corpus**, i el forat no estava documentat enlloc.

`_consulta_via` és **via B de producció: intocable mentre l'Eva hi treballi**. Per tant la solució no és pujar
el llindar allà, sinó que **la tria de carrer es faci a la nostra capa** (via A), que no té llindar. Mentre això
no estigui fet, els municipis grans no tenen resolució d'adreça per aproximació.

### 5.2 Per què la llista, i no variants inventades

**(a) Porta el `tipo_via` oficial, i importa.** A Bell-lloc, «11 de Setembre» és:

```
PZ ONZE DE SETEMBRE      ← plaça, no carrer
```

Un document que digui «Carrer 11 de Setembre» necessita **alhora** la variant del nom i la sigla correcta.
Inventar variants a cegues no dona la sigla.

**(b) La llista és bruta d'una manera que el difflib no pot resoldre.** Bell-lloc, literal:

```
CL ESCUELAS NACION      CL PARCERISA MIQUE     CL GENERALITAT CAT
CL TORREBADELLA DR      CL DESL CUPS           CL URBANIZAC MOR
TR TELEGRAFOS / TR TELEGRAFS        TR PANE JOSE / CL JOSE PANE
```

Noms truncats pel Cadastre, duplicats català/castellà, cognom-nom invertit. Això és el que un model llegint la
llista sencera resol i una ràtio de semblança no.

### 5.3 Peça 1 — FETA (2026-09-01 nit)

**Diagnòstic corregit per la mesura.** El llindar **no** bloqueja l'encert exacte: el camí exacte de
`_consulta_via` consulta el servidor pel nom i funciona igual a Rubí que a Bell-lloc. El que el llindar bloqueja
és **la recuperació** quan l'exacte falla. I la recuperació que amaga no era innocent: a Castellar (481, per
sota del llindar) «11 de Setembre» tornava **`POL 011 FABRICA NOVA`**, i només la guarda de 0,85 ho aturava.

**Baseline mesurat abans de tocar res** (9 casos: adreces reals dels documents de Castellar, Linyola i
Bell-lloc + noms reals de les llistes de Rubí i Cerdanyola):

```
BASELINE  7/9   — els 2 fallats: "11 de Setembre" a Rubí (None, sense recuperació)
                  i a Castellar (POL 011 FABRICA NOVA, aturat per la guarda)
DESPRÉS   9/9   — sense cap coincidència nova d'un carrer equivocat
```

**Implementació:** `resolve_via()` a `automation/lectura/cadastre_reader.py`, sobre la llista sencera del
municipi (`_cached_street_list`, cache 90 dies), **sense llindar de mida**. Quatre capes, i totes exigeixen un
**sol guanyador** — empat vol dir blanc, mai triar:

1. literal: mateixes paraules significatives (ordre i articles no compten);
2. literal «conté», amb la regla d'una sola paraula (`Major` ≠ `MAJOR DE BALAFIA`);
3. 1 i 2 amb els **nombres canonicalitzats** (`ONZE` == `11`, ca i es, 1-31) — resol el cas del Josep
   **sense cap LLM**, i de retruc dona el `tipo_via` correcte (`ONZE DE SETEMBRE` és una **plaça**);
4. difusa ≥ 0,85 i **només si cap altre carrer del municipi arriba al llindar**.

El nom retornat surt sempre de la llista: un carrer inexistent no en pot sortir per construcció.

**Cablejat additiu:** via B continua sent el primer intent (barata, cacheada, exacta). `resolve_via` només
entra quan via B no troba res **o** torna un carrer que no és el llegit. El que ja funcionava no canvia de camí.

**Dos errors trobats implementant** (bateria negativa de 10 casos, la que compta per a ERR = 0):

- La canonicalització de nombres convertia `ONZE` en `11`, un token de 2 caràcters — **la mateixa longitud que
  les abreviatures del Callejero** (`PD`, `DS`), que la regla d'una sola paraula perdona. Resultat: el hint
  `Setembre` casava amb `ONZE DE SETEMBRE`. Corregit: un token de nombre sempre compta com a significatiu.
- El marge numèric sobre el segon millor de la capa difusa era arbitrari i deixava passar
  `Telegraf` → `TELEGRAFS` (0,94) tenint `TELEGRAFOS` (0,89) al costat — dues grafies del mateix carrer amb `cv`
  diferent. Substituït per una regla explicable: **si un segon carrer arriba al llindar, blanc**.

Bateries finals: **positius 9/9, negatius i casos límit 10/10.** Cadena sencera de Castellar sense regressió
(1.284 m², 3/3 contigües, 5/5 punts dins). Tests nous: `tests/test_lectura_via_resolver.py`, 25 casos, 0 xarxa.
Suite: **1922 passed / 32 failed**, el mateix baseline conegut i les mateixes famílies (cap fallada nova).

Un test existent va caldre actualitzar-lo, i val la pena saber per què:
`test_lectura_cadastre_reader.py::test_cadastre_portal_signals_rejects_wrong_street_name` afirmava el text del
warning antic («via descartada») i, amb el cablejat nou, **arribava a la xarxa** — el fitxer és «0 xarxa» per
contracte. Ara fixa també la llista del municipi i comprova les DUES portes: `FONTANELLA` no passa ni la guarda
de via B ni la tria del conjunt tancat (`FONT` vs `FONTANELLA` = 0,57). La intenció original del test —cap
parcel·la d'un altre carrer— queda més ben coberta que abans, no pitjor.

### 5.4 Altres serveis: descartats ara

CartoCiudad (IGN) i el geocodificador de l'ICGC són gratuïts i tenen bones grafies catalanes, però tornen **els
seus** noms, i nosaltres hem d'alimentar `Sigla`+`Calle` **tal com els escriu el Cadastre** per obtenir la
referència cadastral. Servirien com a generadors de pistes, mai com a font final. A més,
[[project_cartociudad_municipio_filter_accent_bug]] ja ens va costar una sessió. **No afegir cap servei nou ara.**

## 5.5 Peces 3 i 4 — objecte estructurat i alternatives (2026-09-01 nit)

Les dues peces conflueixen: la tria per conjunt tancat (D3b) ja la fa `resolve_via` amb capes deterministes
(§5.3), i el que hi faltava —les **grafies alternatives**— ha de venir del lector (D1/D2), no d'un segon LLM
dins de Python. Un sol mecanisme, doncs, i no dos.

**Contracte.** El skill emet un concepte EXTRA, `street_address_struct`, com una entrada més de `tier_a`:

```json
{"tipus_via": "plaça", "nom_via": "Onze de Setembre",
 "nom_via_alternatives": ["11 de Setembre"], "portals": ["5"],
 "municipi": "Bell-lloc d'Urgell", "municipi_alternatives": ["BELL-LLOC"]}
```

**On viu** (resposta a la pregunta oberta §8.1): com que `street_address_struct` no és cap de les
`ALLOWED_FIELD_KEYS`, el consolidador el deixa a `extra_concepts` de l'arrel — que el validador del contracte
**ignora**. No toca cap de les variables de l'informe ni el `_decisions.json` que la UI llegeix.

**Validació a Python** (`automation/lectura/address_struct.py`) — l'A1 en dues meitats: esquema + exemples al
prompt del skill, i aquí la validació. `nom_via` i `municipi` obligatoris; alternatives amb text i almenys una
lletra, deduplicades sense distingir majúscules, màxim 8; portals `\d{1,4}` amb lletra opcional, màxim 6.

**Per què NO hi ha bucle de re-pregunta:** un objecte invàlid es descarta sencer i la cadena continua amb el
text lliure de sempre. Es perd la millora, mai s'hi guanya un error — i una degradació segura no justifica el
cost i la complexitat d'una segona crida.

**Fusió entre documents.** Cada document pot portar la seva grafia (la comanda escriu `C/ARBRELLS`, el
pressupost `Carrer Arbrells, 18A-18B-20`). `from_extra_concepts` es queda la primera lectura vàlida com a
principal i converteix les altres en alternatives. La variabilitat *dins* d'un mateix projecte —el que el Josep
descriu com el problema— és aquí el material útil.

**Com s'usen** (`_resolve_street`, `_resolve_municipality`): via B → conjunt tancat amb el nom llegit → conjunt
tancat amb cada alternativa. Municipi: padró amb cada grafia → bucle en línia. **Una alternativa és només un
intent de consulta més**; el nom acceptat surt sempre de la llista real del municipi o del padró.

Verificat sobre dades reals de Bell-lloc:

```
resolve_via('Telegraf')                        -> None   (empat TELEGRAFS 0,94 / TELEGRAFOS 0,89)
_resolve_street(... alternatives=[])           -> None
_resolve_street(... alternatives=['Telegrafs'])-> ('TELEGRAFS', 'TR', '72')   ← rescatat
_resolve_street(... ['Avinguda Imaginària'])   -> None   ← un carrer inventat no hi és, no passa
```

**L'eix portal segueix tancat.** Els portals de l'objecte **no** s'usen per consultar: manen els de
`portals_from_address`. Hi ha test que ho fixa (l'objecte diu `["99","100"]`, es consulta `18A`). És la regla
del §2, ara executable.

**Un bug que va caçar el test i una duplicació eliminada:** el validador acceptava `"3r"` com a portal (pis
escrit com a ordinal). El guard ja existia a `cadastre_reader._FLOOR_ORDINAL_RE`; en comptes de copiar-lo, la
definició ha passat a `address_struct.FLOOR_ORDINAL_RE` i `cadastre_reader` la importa — **una sola definició**,
amb test que ho fixa. Duplicar vocabulari d'adreces és exactament l'error que va costar car amb
`COMPONENT_VALUE_ALIASES`.

Tests: `tests/test_lectura_address_struct.py`, 30 casos, 0 xarxa.

## 6. El veto per punts de camp

### 6.1 Material que ja tenim i no fem servir per decidir

- Molts projectes porten `ANNEXES/…/COORDENADES.txt` amb les coordenades **GPS reals dels punts on l'equip va
  assajar** (DPSH, sondeigs), en UTM ETRS89 fus 31 (**EPSG:25831**).
- El WFS del Cadastre torna, per a cada RC, el **polígon de la parcel·la** en el **mateix sistema**. Sense
  conversions ni aproximacions.

Es pot fer, doncs, una pregunta purament geomètrica: **els punts on l'Eva va anar a treballar, cauen dins de la
parcel·la que hem deduït de l'adreça?**

### 6.2 Verificació en viu (Castellar, el cas Arbrells)

```
adreça llegida : "Carrer Arbrells, 18A, 18B i 20"
via oficial    : ARBRELLS DELS (CL)
parcel·les     : 18A→3298012DG2039N 441 m² · 18B→…013 423 m² · 20→…014 420 m²
suma           : 1284 m²          ← exactament l'1.284 que escriu l'Eva
unió           : un sol polígon (contigües)
punts 1..5     : dins=True, distància=0,0 m   (5/5)
```

`_points_note()` **ja calcula exactament això** — i n'escriu una nota informativa («5/5 punts d'assaig dins de
la unió») al costat del valor. **No toca la decisió:** si els 5 punts caiguessin a 400 m, el valor sortiria
igualment, amb la mateixa cara de fiable.

### 6.3 Formulació del veto (confirmada pel Josep)

La regla només pot **vetar**, mai **exigir** — la meitat dels projectes no tenen fitxer de coordenades:

| projecte | punts |
|---|---:|
| Castellar | 5 |
| Linyola | 3 |
| Bell-lloc | 1 |
| Alcoletge | 1 |
| Rubí · Tulipa · Vilanova · Anciles | **0** |

```
punts FORA  → mai `segur`  (candidats o blanc, amb la distància a la nota)
punts DINS  → corrobora, permet `segur`
CAP punt    → neutre, com avui
```

Amb un sol punt (Bell-lloc, Alcoletge) el veto continua valent: un punt a 400 m és igual de concloent que cinc.

### 6.4 L'Eva ha de saber que ha estat per les coordenades

**Requisit explícit del Josep (2026-09-01).** Context: en una conversa anterior l'Eva va dir que **no considera
les coordenades UTM del tot fiables ni garantides**. Si un dia el veto li amaga una superfície i no sap per què,
la conclusió que en traurà serà sobre el sistema, no sobre les coordenades.

Per tant, **cada vegada que el veto dispari, el motiu ha de ser visible al popup**, amb la distància concreta.
Redacció proposada:

```
Superfície no confirmada: els punts d'assaig del projecte cauen FORA de la parcel·la
que correspon a aquesta adreça (0/5 dins, el més llunyà a 412 m).
Comprova l'adreça o les coordenades de ANNEXES/ALTRES/COORDENADES.txt.
```

### 6.5 Peça 5 — FETA (2026-09-01 nit)

**El canal ja existia i no calia cap camp nou.** `consolidate.decide()` recull el `note` dels senyals **sense
valor** i el posa a la cel·la `no_trobat`. Així el veto s'implementa emetent un senyal amb `value=None` i el
motiu escrit: el camp queda en blanc —mai un número d'una altra parcel·la— però amb l'explicació enganxada.
L'única cosa que faltava era pintar-lo: `review.html`, branca `no_trobat`, ara mostra `cell.note` entre les
fonts revisades i la línia d'acció.

**Què dispara el veto** (`PointsCheck.vetoes`): **cap** punt dins **i** el més proper a més de
`_MAX_POINT_DRIFT_M` = **10 m**. Amb algun punt dins no es veta —la parcel·la és com a mínim en part correcta i
un punt solt fora sol ser deriva de GPS o un assaig al carrer—, però l'avís hi queda igualment.

Els 10 m són un criteri de judici, i el raonament importa més que el número: el GPS de camp mostra ~0,6 m de
diferència contra l'ICGC, i una parcel·la **veïna** de 441 m² ja és a ~20 m. 10 m deixa passar la deriva
d'instrument sense deixar passar una parcel·la equivocada. **A revisar amb dades reals** quan n'hi hagi de més
projectes.

La comprovació es fa **sempre** sobre la unió de totes les parcel·les resoltes, encara que no siguin contigües
o hi hagi un portal ambigu: la pregunta «són aquestes les parcel·les del projecte?» no depèn de si es poden
sumar.

**Verificat amb el projecte real de Castellar**, desplaçant-ne les coordenades 500 m:

```
punts reals        -> superficie_parcela = 1284   nota: «5/5 punts d'assaig dins de la unio»
punts desplaçats   -> superficie_parcela = None
   cel·la: estat=no_trobat, note = "No s'ha omplert la superfície: els punts d'assaig del
   projecte cauen FORA de la parcel·la que correspon a l'adreça llegida (portals 18A+18B+20;
   0/5 dins, el més llunyà a 703 m). Comprova l'adreça del projecte o les coordenades de
   ANNEXES/…/COORDENADES.txt."
```

El text diu **d'on ve la sospita** (les coordenades), **quant** de lluny i **on mirar**. És el requisit del
Josep: si el veto amaga un valor i l'Eva no sap per què, la conclusió que en traurà serà sobre el sistema.

Tests: `tests/test_lectura_points_veto.py`, 14 casos, 0 xarxa. Un test existent
(`test_cadastre_portal_signals_points_note_point_outside`) **canvia d'expectativa a posta**: afirmava que amb
un punt a ~692 m la superfície sortia igualment amb una nota informativa, que és exactament el que la peça 5
substitueix. Ara documenta el veto i remet al fitxer nou per als límits.

Ancoratge alternatiu, per si algun dia el veto ha de deixar candidats en comptes de blanc: amb
`estat = candidats` el motiu pot anar al `font` de cada candidat, que el popup ja pinta (`lp-font`).

## 7. Restriccions respectades

- `automation/geocode_coordinates.py`, `automation/parcel_resolver.py`, `automation/cadastre_adjacents.py` són
  **via B de producció**: llegits, mai modificats (per això el llindar de 500 es resol a la nostra capa, §5.1).
- `automation/g3_templates.py` continua sent **determinista, cost 0, sense xarxa**. Un fitxer de dades enviat al
  repo compleix el contracte: el contracte prohibeix **xarxa**, no **dades**.
- `resolve_portal` manté el filtre `(pnp, plp)` exacte i no delega mai al portal més proper (§2).
- ERR = 0 mana per damunt de la cobertura: val més `candidats` o blanc que una parcel·la equivocada.

## 8. Preguntes obertes d'implementació (no bloquegen)

1. ~~On viu l'objecte estructurat~~ — **resolt**: `extra_concepts`, que el validador del contracte ignora (§5.5).
2. ~~Qui fa la crida de la llista de carrers~~ — **resolt**: Python. El skill no toca la xarxa; emet grafies i
   Python les prova contra la llista real. Així la lectura es manté cacheable i repetible.
3. ~~Forma exacta de l'esquema JSON~~ — **resolt** (§5.5). Queda per mesurar amb execucions reals **quants
   exemples** calen al prompt perquè el skill l'emeti de forma estable; avui n'hi ha tres, del corpus.
4. Si el veto de punts s'aplica també a `referencia_catastral` o només a `superficie_parcela`.
5. **Nou:** el padró només cobreix Catalunya i el corpus ja té un projecte de fora (Anciles, de Benasc, Osca —
   confirmat pel Josep). Avui cau al bucle en línia i funciona. Afegir-hi Osca seria una crida més i ~200
   municipis; decisió del Josep si val la pena o si la sortida en línia ja és prou.

## 9. Feina pendent, per ordre

1. ~~**Pujar/eludir el llindar de 500** movent la tria de carrer a la via A~~ — **FET** (§5.3): `resolve_via`
   sobre la llista sencera del municipi, 7/9 → 9/9, sense cap coincidència errònia nova.
2. ~~Cablejar el padró: resolució de municipi offline + validació del residu de PLAN_COST~~ — **FET** (§4.1).
   Queda obert, a posta: emetre la forma oficial llarga com a **candidat competidor**, no només com a nota.
3. ~~Tria de via sobre conjunt tancat + verificació de pertinença a la llista (D3b).~~ — **FET** (§5.3 i §5.5).
4. ~~Objecte estructurat com a sortida del lector (D1, D2, A1).~~ — **FET** (§5.5): `street_address_struct` a
   `extra_concepts`, esquema + exemples al skill, validació a `address_struct.py`.
5. ~~Veto per punts (D7) **amb el missatge visible a l'Eva**~~ — **FET** (§6.5).
6. **Següent:** la mesura de qualitat dels 8 projectes (era la tasca 5 de
   `docs/_FOR-NEW-YOU-20260901-2000.md`): % camps bé / % popup / % blanc / **erronis-amb-confiança (objectiu 0)**
   / minuts per projecte, i `compare_tables_vs_eva` contra els informes signats. Llindars pactats:
   OK ≥ 80 %, candidats ≤ 20 %, ERR = 0.

---

*Fi de l'anàlisi d'adreces i municipi. Set preguntes respostes, vuit decisions, un fitxer de dades entregat i
un forat nou trobat (el llindar de 500).*
