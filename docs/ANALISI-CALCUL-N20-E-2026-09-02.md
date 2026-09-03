# Anàlisi: com calculem N20 i E — revisada amb el marc de pràctica geotècnica

**Data:** 2026-09-02 (v2, mateixa tarda) · **Branca:** `experiment/nivell-a-2026-08` · **Motiu:** tasca 0 del
handoff (test vermell N20 Bell-lloc), ampliada pel Josep a anàlisi completa de N20 i E, i **revisada** després
de rellegir la família de documents sobre com decideixen els geotècnics (v1 no els havia tingut en compte).

**Decisions ja preses avui (Josep):** el test es queda **vermell**; el forat de l'E **només s'apunta** (aquest
document és l'apunt). Cap línia de codi de càlcul s'ha tocat.

**Documents base d'aquesta revisió** (tots al worktree dev, `../g3dt/docs/`):

| Document | Què aporta |
|---|---|
| `RECERCA-PRACTICA-GEOTECNICA-ESPANYA.md` (02-25, apèndix Crespo 04-17) | pràctica espanyola; cap correlació publicada sola reprodueix l'E d'Eva; taules Crespo per a cohesius |
| `CRITERIS-CALCUL-EVA.md` (04-10) | cadena Qa reverse-engineered, **6/7 MATCH exacte**; topalls per règim; arrodoniment professional confirmat amb 4 fonts externes |
| `ANALISI-SETTLEMENT-BACK-ENGINEERING.md` §5 (02-26) | el procés de decisió del geotècnic qualificat; carbonatació→E↑; «precisió millor que ±50 % és il·lusòria» |
| `CALCUL-E-MODUL-DEFORMACIO.md` (02-25) | racional de la v1 de l'E (banda baixa), proposta v2 pendent, preguntes per a Eva |
| `docs/METODOLOGIA-EVA.md` (aquí, 04-17) | bicapa condicional, φ=28° fix per a materials transicionals |

---

## 0. El marc: els geotècnics han acordat divergir de les fórmules — i Eva ho fa exactament així

La recerca del febrer–abril (documents de dalt) va establir que **les fórmules (Terzaghi, Schmertmann, taules
CTE) són punts de partida, no resultats**, i que la professió sencera divergeix d'elles amb criteris pactats i
raonables. Verificat amb fonts externes (inforcivil, geotecniafacil, verificacioncte, PFC UPM) i contra els 7
informes signats:

1. **Arrodoniment professional.** Qa a passos de 0,5; E a desenes o 50s (80, 90, 100, 350, 450, 500, 650,
   800 — 7/7 projectes); φ a graus enters; les taules de referència del sector són TOTES de valors rodons.
   «No un caprici d'Eva» — és l'estàndard.
2. **Topalls professionals a la Qa**, encara que Terzaghi doni molt més: 3,0 sòl / 3,5 granular dens /
   3,0 roca mixta (4,0–4,5 només roca massissa sana, cap cas al corpus). El Terzaghi teòric amb φ=38–39 dona
   Qa ≫ 3 i **ningú del sector ho signa**.
3. **Ajustos per litologia, no per fórmula.** Bell-lloc E=650 vs Rubí E=450 amb el mateix rang d'N: la
   **carbonatació** (cimentació natural) justifica el +44 %. «Combina N amb tipus de materials» (Eva).
4. **L'estrat que mana és on RECOLZA la fonamentació** — ni el primer ni el més profund. Linyola: L2 (lutites),
   no L1. **Anciles: L1 (argiles febles), no L2 (bolos competents)** — perquè la sabata no hi arriba.
5. **L'assentament és verificació de servei, no predicció**: la pregunta és «està ben per sota de 2,54 cm?»,
   no el segon decimal. Precisió millor que ±50 % és il·lusòria en geotècnia.
6. **Simplicitat deliberada**: «es basa tant com pot en les taules del CTE i no es busca complicacions» (Eva).
   Cap correlació publicada sola (D'Appolonia, Bowles, CTE D.23 interpolada…) reprodueix els seus E — perquè
   el mètode són els **criteris**, no una fórmula.

**Conseqüència per a tota l'anàlisi:** el pipeline ha de modelar *criteris* (règim + ajust litològic +
arrodoniment + topall), no perseguir precisió decimal de fórmula. I bona part d'aquests criteris **ja estan
implementats i validats** (topalls per règim a `terzaghi_calculator.py:417-430`, γ fix per litologia, arrodonit
Qa 0,5, Es=2,5×Nb) — la cadena Qa dona 6/7 MATCH exacte. Els forats que queden són als **inputs** (N20 de
geometria fràgil) i a l'**E** (l'únic paràmetre on el criteri encara no està modelat).

## 1. El test vermell: diagnòstic tancat

`tests/test_bearing_stratum_n20_regression.py::test_bell_lloc_bearing_idx_and_n20` (N20=34,3 vs ≈49,8).

**No és una regressió de càlcul. És deriva del fixture.** Prova amb el codi actual idèntic:

| Entrada | Capes llegides | N20 resultant |
|---|---|---|
| `sondeig_extracted.json` del dia que es va escriure el test (`d70030c`, 17-abr) | 0–1,6 / **1,6**–1,8 | **49,8** |
| `sondeig_extracted.json` d'avui (refresc de sweep `e042a37`/`fa8b22b`, 18/19-abr) | 0–1,0 / **1,0**–1,8 | **34,3** |

49,8 és exactament la mitjana de les 5 lectures DPSH ≥ 1,6 m; 34,3 la de les 10 lectures ≥ 1,0 m. El test es
va calibrar contra la primera lectura de visió i un refresc posterior la va substituir. **Cap dels dos límits
de capa és real:**

- El full de camp del sondeig és manuscrit, fotografiat girat 90°, i la lectura té confiança **0,60–0,65**
  amb notes «partially legible». El límit intern (1,6 o 1,0) és interpretació del model, i ha canviat de lloc
  entre lectures.
- L'annex que dibuixa la mateixa Eva diu **un sol nivell** («Unitat litològica» = NIVELL 1 per tot el sondeig).
- L'informe signat diu **un sol nivell** («1er nivell. Graves en matriu sorrenca carbonatades»), sondeig fins
  a −1,80 m.

**Amb la geometria correcta (una sola capa 0–1,8 m), el codi actual retorna 25,1** — i la taula signada diu
**Nb = «25-R»** (vegeu §3 sobre la lectura d'aquesta xifra). El càlcul reprodueix l'Eva quan l'entrada és bona;
el que falla és la lectura del full de camp — la tesi del nivell A, confirmada des del costat dels càlculs.

Contra φ = 38° signat: N20=34,3 → φ 37,0° (−1,0°); N20=49,8 → φ 40,6° (**+2,6°, costat insegur**). El valor
«trencat» és el millor dels dos. La Qa no es mou: el topall professional la fixa a 3,0 als dos casos — el
marc de §0 absorbeix aquest soroll.

**Defecte estructural del test:** la seva capçalera diu que existeix perquè *«future refactors can't silently
shift calibrated values»*, però el seu fixture és `validation/sondeig_extracted.json`, un artefacte
**regenerable** per qualsevol refresc de visió. No vigila el càlcul: segueix l'última passada de visió. (Es
queda vermell per decisió del Josep 2026-09-02, fins a resoldre §4.)

## 2. Com es calcula N20 avui — tres èpoques que conviuen

| # | Càlcul | On | Què fa | Qui el consumeix |
|---|---|---|---|---|
| 1 | `overall_average_n20` | `dpsh_extractor.py:139` | mitjana **ponderada 2×** de les 5 primeres lectures per assaig (≈ primer metre), exclou rebuig (≥100) | fallback dels altres dos; projectes sense capes de sondeig |
| 2 | `_bearing_stratum_n20` | `report_data.py:1064` | mitjana **no ponderada** de les lectures dins del rang del «ferm» (capa competent més profunda, via `bicapa`), exclou rebuig; sense límit inferior quan ferm = capa més profunda | `avg_n20` → γ, φ (via Nb), E, Terzaghi-Peck, Es d'assentament (`report_data.py:451-511`); prefill del wizard (`wizard_service.py:694`) |
| 3 | agrupació per `geological_level` | `report_data.py:1115,1196` | un N20 per grup de «Unitat litològica» (criteri Eva); col·lapse a 1 nivell → delega a #2 | files de la taula geotècnica de l'informe (`report_generator.py:1404-1483`) |

**Incoherències i errors de concepte detectats:**

1. **La metodologia canvia amb el nombre de capes, no només el rang.** Amb <2 capes → mitjana ponderada 2×
   al primer metre (#1); amb ≥2 capes → mitjana plana del tram del ferm (#2). Dues heurístiques de
   generacions diferents, totes dues «calibrades a Eva».
2. **La restricció per fondària penja d'un límit de capa llegit per visió amb confiança 0,6.** A Bell-lloc,
   moure'l 0,6 m (sobre un sondeig d'1,8!) mou el N20 un 45 % — i ha passat dues vegades sense tocar codi.
3. **La tria del ferm és «competent més profund»; el criteri d'Eva és «on recolza la fonamentació».**
   Coincideixen sovint, però **Anciles els separa**: Eva usa L1 (argiles, Nb=5) i no L2 (bolos, Nb=15) perquè
   la sabata no arriba a L2 (`CRITERIS-CALCUL-EVA.md` §1). El nostre `_select_bearing_layer_idx` triaria els
   bolos. Sense fondària de fonamentació real, «més profund» és un proxy que aquest cas signat desmenteix.
4. **La columna «N» de la taula imprimeix un concepte equivocat.** Eva hi posa **l'N30 de l'assaig SPT del
   projecte** — confirmat als signats: Bell-lloc 54 (SPT-1 a S-1), **Rubí 40 (SPT-1 a P-3)**, Anciles 6,
   Castellar «R» (SPT rebutja), Linyola «--» (sense SPT). El pipeline hi posa `int(avg_n20)` del DPSH
   (`report_generator.py:1469`) — Bell-lloc «34» vs «54». El valor correcte ja el llegim
   (`spt_results[].n_spt`).
5. **La cel·la «Nb» probablement infla un 20 %.** Nosaltres imprimim `N20/0,83`. Però l'Nb d'Eva segueix el
   N20 **cru** del seu full (els Excel de camp ja porten la columna Nb; la relació ×0,83 als headers va
   d'Nb→N): Bell-lloc «25» = N20 ponderat 25,1 **clavat**; Castellar «17» vs N20 cru 18,7 (nostre «27-R»);
   Rubí «47» vs N20 del ferm 43,3 (nostre «52-R»). **Als tres casos, el N20 cru s'acosta més que N20/0,83.**
   Compte: això és la cel·la de *display*; la cadena de CÀLCUL (Nb=N20/0,83 → φ → Terzaghi) està validada
   extrem a extrem (6/7 MATCH) i no s'ha de tocar per això.

## 3. L'Nb signat: judici sobre una base identificable

| Projecte | nivells signats | N20 global (#1) | N20 ferm (#2) | Eva Nb | més a prop |
|---|---|---|---|---|---|
| Castellar | 1 | 18,7 | 22,6 | **17-R** | global |
| Bell-lloc | 1 | 25,1 | 34,3 | **25-R** | global (clavat) |
| Rubí | 1 | 34,7 | 43,3 | **47-R** | ferm |

Tots tres d'un sol nivell signat, i tot i això dos arran del global i un arran del tram profund. Llegit amb el
marc de §0: l'Nb de la taula és **la caracterització de judici del nivell** («típic ~X, puja fins a rebuig»),
ancorada al full de camp — no la sortida d'una fórmula única. Calibrar-hi una fórmula a sobre és perseguir
soroll; el que sí que és objectiu és **no alimentar el càlcul amb geometria inventada** (§1) i no inflar la
cel·la amb el factor 0,83 (§2.5).

## 4. La decisió de fons que queda oberta (per al Josep, potser per a Eva)

Quan el perfil és d'un sol nivell real, ¿el N20 representatiu surt de tot el perfil o del tram on recolza la
fonamentació? L'evidència 2-de-3 no ho resol, i el criteri «on recolza» (§0.4) demana una dada que sovint no
tenim llegida amb confiança: la **fondària de fonamentació**. D'això depèn:

- el valor esperat que hauria de fixar el test de Bell-lloc (25,1 / 34,3 / un altre);
- si `_bearing_stratum_n20` ha de consultar `geological_level` i la fondària de sabata abans de restringir.

Pregunta candidata per a Eva (sense pressa): «quan tot el sondeig és un sol nivell, l'Nb de la taula el treus
de tot el perfil o de la zona on recolza la fonamentació?»

## 5. Com es calcula E avui — l'únic paràmetre on el criteri encara no està modelat

`nspt_to_E_kg_cm2` (`cte_geomech.py:156`): taula CTE D.23 per trams d'N, banda conservadora
`E_min + 10 % del rang` → **funció esglaonada de 4 valors** per a sòl (8 / 114 / 469 / 1.428 kg/cm²); roca →
valor fix 500 (`rock_params_default`). L'E alimenta el K30 (E/75 granular, E/60 roca — validat 2/2) i la
cel·la «E (4)». L'assentament NO en depèn: va per Schmertmann amb Es=2,5×Nb (camí a part, validat ±8 %).

La «banda baixa» de la v1 es va calibrar quan només hi havia **un** cas granular de referència (Rubí 450;
`CALCUL-E-MODUL-DEFORMACIO.md` §3 i §6). Amb els **9 nivells signats** d'avui, el patró real és un altre:

| Projecte · nivell | material | Eva Nb | Eva E | E fórmula | desviació | on cau Eva dins el rang CTE |
|---|---|---|---|---|---|---|
| Alcoletge · 1 | sorres argiloses rebliment | 5-0 | **50** | 8 | **−84 %** | part mitjana-alta (rang 0–82) |
| Anciles · 1 | argiles sorrenques | 5 | **90** | 8 | **−91 %** | **per SOBRE del rang** (0–82) |
| Linyola · 1 | llims argilosos | 13 | **100** | 114 | +14 % | banda baixa (82–408) |
| Rubí · 1 | graves i sorres | 47-R | **450** | 469 | +4 % | banda baixa (408–1.020) |
| Bell-lloc · 1 | graves **carbonatades** | 25-R | **650** | 469 | **−28 %** | banda mitjana (ajust litològic ↑) |
| Castellar · 1 | bretxes (roca) | 17-R | **>500** | 500 | ~0, sense «>» | — |
| Linyola · 2 | lutites (roca) | 31-R | **>800** | 500 | **−37 %** | — |
| Alcoletge · 2 | lutites alterades (roca) | R | **>400** | 500 | dins del rang | — |
| Anciles · 2 | bolos i graves | 15-R | **>350** | 500 | dins del rang | — |

La lectura amb el marc de §0:

1. **«Banda baixa» només val per a trams mitjos** (Linyola +14 %, Rubí +4 %). Per a **sòls fluixos Eva va a la
   part ALTA del rang, i a Anciles per sobre i tot** (90 > 82): cap professional escriu un mòdul d'un dígit,
   el nostre E=8 és un absurd que cap informe signaria. I per a **carbonatats** puja a banda mitjana (650).
   No és «conservadorisme uniforme»: és **evitar els extrems irreals del rang, per règim**.
2. La **proposta v2** del document de l'E (escalar amb la posició dins del rang, pendent de validar amb més
   casos) **empitjoraria els sòls fluixos** (N=5 → 4 kg/cm²): resol el règim mitjà, no el problema real.
3. **Eva arrodoneix l'E a desenes o 50s** (§0.1); el nostre 469 exhibeix una precisió que el sector no usa.
4. **Roca:** valor únic 500 contra judicis per projecte «>350…>800», i mai imprimim el prefix «>» que Eva posa
   sempre en roca.
5. L'esglaó 469→1.428 a N=50 (×3) queda: Bell-lloc amb el fixture antic (N20 49,8) era a un punt del precipici.

**Direcció de millora coherent amb §0** (cap d'implementada): modelar el criteri, no refinar la fórmula —
sòl fix per règim fluix (mai per sota de ~50–100 segons litologia), banda baixa només a trams mitjos, ajust
↑ per «carbonatad-/cimentad-» a la descripció, arrodonir a 10/50, «>» en roca; i presentar-ho com a
**candidats amb procedència** (valor de taula + valor ajustat per litologia) aprofitant l'override expert que
ja existeix. Les preguntes per validar-ho amb Eva ja són redactades a `CALCUL-E-MODUL-DEFORMACIO.md` §8.

## 6. Troballa col·lateral: el col·lapse a 1 nivell pot vestir de roca un nivell granular (Rubí)

Amb el fixture actual de Rubí (graves 0–3,35 gl=1; **gresos/lutites** 3,35–4,55 gl=2) i `num_soil_levels=1`,
el col·lapse (`report_data.py:1168-1194`) pren **la descripció de la capa més profunda** per al nivell únic →
«gresos amb… lutites» → `is_rock=True` → paràmetres de roca:

| | Nb | N | γ | c | φ | E |
|---|---|---|---|---|---|---|
| pipeline (col·lapse actual) | 52-R | 43 | 2,20 | 1,0 | **35** | **500** |
| Eva signat | 47-R | 40 | 2,0 | 0,05 | **39** | **450** |

És el mateix error de criteri que §2.3: Eva anomena i parametritza el nivell **on recolza la fonamentació**
(les graves), no el substrat de sota — coherent amb el precedent d'Anciles. Sis cel·les signades divergeixen
d'un sol cop d'origen. (Pendent de contrastar amb el run de mesura; verificat a nivell de fórmula.)

Nota menor: la fila «Alcoletge 1: Graves carbonatades, Nb=30, E=500» de `CRITERIS-CALCUL-EVA.md` §5 no quadra
amb la taula signada transcrita a `_eva_truth/alcoletge.json` (sorres argiloses de rebliment / lutites);
probablement un lapsus d'aquell document. Aquí mana `_eva_truth`.

## 7. Conclusions (v2)

1. **El marc primer:** els geotècnics divergeixen de les fórmules amb criteris pactats (arrodoniment, topalls,
   ajust litològic, estrat on recolza, assentament com a verificació), i Eva és un cas de manual d'aquesta
   pràctica. El gruix d'aquests criteris **ja és al codi i validat** (cadena Qa 6/7 MATCH exacte; topalls
   3,0/3,5/3,0 a `terzaghi_calculator.py:417`; γ fix; Es=2,5×Nb). El sistema no està «lluny d'Eva»: està a
   dos forats concrets — l'entrada del N20 i el criteri de l'E.
2. **El test vermell no és cap regressió de càlcul**: és deriva del fixture de visió (0,6 de confiança) que
   el test mai hauria d'haver usat com a àncora. Amb geometria bona, el codi reprodueix l'Nb signat (25,1 vs
   «25-R»). Reforça la via A: la inversió va a llegir bé, no a recalibrar fórmules. Queda vermell (decisió
   Josep) fins a resoldre §4; llavors, geometria congelada dins del test.
3. **Dos errors de concepte a la taula geotècnica, petits i segurs de corregir:** la columna «N» ha de dur
   l'N30 de l'SPT (no `int(avg_n20)`), i la cel·la «Nb» probablement no ha de dividir per 0,83 (als 3 casos
   comprovats, el N20 cru s'acosta més al signat). Cap dels dos toca la cadena de càlcul validada.
4. **La tria del ferm ha de ser «on recolza la fonamentació», no «competent més profund»**: Anciles (signat)
   i Rubí (col·lapse vestit de roca, §6) són els dos testimonis. Requereix la fondària de sabata com a input
   conscient.
5. **L'E és l'únic paràmetre amb el criteri sense modelar**: banda baixa només als trams mitjos; règim fluix
   amb sòl mínim (Eva 50–90, mai 8); ajust ↑ per cimentació; arrodoniment a 10/50; «>» en roca. Millor com a
   candidats amb procedència que com a fórmula nova. Preguntes per a Eva ja redactades.
6. **Qa és robusta per disseny** (topalls + arrodoniment absorbeixen el soroll d'N20 als perfils densos), però
   **no als fluixos**: a Vilanova (2,5) i Anciles (2,0) governa Terzaghi i allà φ/N20 sí que mouen el número
   signat. La immunitat de Bell-lloc no és generalitzable.
7. **Per a la mesura dels 8 projectes** (tasca 1): les cel·les Nb, N, E (i γ/c/φ a Rubí) tenen causes de
   MISMATCH conegudes i documentades aquí — llegir els resultats amb aquest document al costat per no
   re-diagnosticar-les.

Ordre suggerit quan toqui: columna N (trivial) → cel·la Nb sense /0,83 (petit, validar amb Josep) → material
del col·lapse/ferm-on-recolza (petit-mitjà) → E per criteris i candidats (disseny) → regla N20 global/ferm
(§4, necessita Eva o decisió del Josep).

---
*Fi anàlisi 2026-09-02 (v2). El sistema ja modela la majoria de criteris professionals d'Eva; els forats són
l'entrada del N20 (geometria de visió), dos conceptes de display (N, Nb) i el criteri de l'E.*
