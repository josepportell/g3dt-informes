# Proposta del Josep — interpretació d'adreces i municipi amb intel·ligència, no amb regex

**Data:** 2026-09-01 · **Estat: ANOTADA, NO ANALITZADA.** El Josep demana expressament que quedi registrada
literalment i que l'anàlisi es faci en una **sessió nova**. No implementis res a partir d'aquest document sense
haver fet abans aquella anàlisi amb ell.

---

## 1. Comentari del Josep, literal

> Tema: adreça de la parcel·la: (i també el mateix aplica al municipi)
> Situació:
> 1) Ara ens basem en Claude Code com executor i no estrictament codi determinista.
> 2) L'adreça és una dada absolutament clau. És de la màxima importància obtenir-la bé, entendre-la bé.
> 3) Sabem que la variabilitat de formats d'escriptura de les adreces és elevadíssima. No només canvia com ve
> escrita una adreça entre projecte i projecte, sino que també dins del mateix projecte la trobem escrita de
> maneres diferents, amb o sense comes, amb prefix de tipus de via o sense, amb "i" o sense, amb un o més números
> de portal, etc etc.
> 4) El Cadastre, ICGC, Nominatim, ... totes aquestes plataformes són molt estrictes amb com s'introdueix
> l'adreça. I necessitem no només que trobi l'adreça (i el municipi), sino que la parcel·la sigui exactament la
> parcel·la del projecte. Qualsevol error aquí té conseqüències importants (l'Eva pensarà "està analitzant una
> altra parcel·la!! Què despistada està!! Això no va!!" o similar).
>
> Opino que hem d'aplicar intel·ligència (Claude Code, si pot ser un model d'alt rendiment, Fable o Opus) per
> interpretar les adreces. No sé si seria convenient definir un patró (objecte JSON) que pugui gestionar tota la
> variabilitat alhora que contingui dades amb el format adequat perque siguin sempre vàlides per les plataformes
> que hem de consultar (del tipus {"tipus de via": "carrer", "nom de via": "ONZE DE SETEMBRE" o "Arbrells",
> "numero(s) de bloc": {"18A", "18B", "20"} o {"7"}, "nom_municipi_curt": "Bell-lloc", "nom_munici_llarg":
> "Bell-lloc d'Urgell", "nom_municipi_alternatius: {"BELLLLOC", "BELL-LLOC D URGELL", "BELL-LLOC DE URGELL"}, ...
> }. I, quan consultem aquestes plataformes estrictes, si obtenim zero resultats (o resultats sospitosos),
> poguem refer la query amb dades 'alternatives' (m'explico millor: si no troba el carrer "11 de Setembre", que
> Claude Code pugui repreguntar-li amb el nom de carrer "ONZE DE SETEMBRE", etc.

*(Transcripció literal del missatge del Josep del 2026-09-01, a mitja sessió, mentre corrien els agents de
correcció del code-review. La instrucció que l'acompanyava: «Sisplau, anota literalment el meu comentari, i
l'analitzem en la següent sessió nova.»)*

---

## 1b. Seqüència acordada amb el Josep (2026-09-01, vespre)

Aquest document és **la primera feina d'una sessió nova**, no d'aquesta. Ordre pactat, en aquest ordre exacte:

1. ~~Acabar la segona revisió creuada de les correccions del code-review.~~ (aquesta sessió)
2. ~~Fer el fix de l'`Avda.`~~ (aquesta sessió; vegeu §2, últim punt)
3. **Obrir una sessió nova** — deliberadament, per tenir tota la finestra de context disponible per a l'anàlisi.
4. **Analitzar aquesta proposta** amb el Josep (les preguntes de §3 en són el guió).
5. **Només llavors, mesurar** la qualitat: hold-out headless dels 8 projectes sobre codi ja reparat, amb els
   números d'OK / candidats / blancs / erronis-amb-confiança i els temps per projecte.

El motiu de posar l'anàlisi **abans** de la mesura és del Josep: si l'adreça i el municipi han de canviar
d'arquitectura, mesurar abans seria mesurar una cosa que estem a punt de substituir. Els temps de referència que
ja tenim d'avui (Castellar 27,8 min, Linyola 41,9 min, amb el codi d'abans de les correccions) queden com a
baseline.

## 2. Per què això arriba avui (context mínim, sense analitzar la proposta)

Aquesta proposta neix del que hem trobat aquest mateix dia arreglant el code-review de la branca. Els fils que
hi connecten, per si la sessió que ho analitzi els vol tenir a mà:

- **`docs/audit/CODE-REVIEW-BRANCA-2026-09-01.md` § P1.1** — el lector del Cadastre (`cadastre_reader.py`, enviat
  el 2026-08-31 amb el Fix D) confonia la conjunció «i» de `"Carrer Arbrells, 18 i 20"` amb una lletra de portal,
  i partia carrer i portals pel primer dígit, cosa que destrossa `"Carrer 11 de Setembre, 5"`.
- **Mateix document, § P1.3** — el municipi de PLAN_COST sortia malament a **7 de 10 fitxers reals**
  (`EG VILANOVA SEGRIÀ` → `SEGRIÀ`, perdent «Vilanova»).
- **La correcció d'avui va introduir un llindar difús de 0,85** per verificar el nom de via que torna el
  Callejero. Descarta casos com `"11 de Setembre"` vs `"ONZE DE SETEMBRE"` → **blanc honest en comptes de
  parcel·la possiblement equivocada**. Això és precisament el cas que el Josep posa d'exemple a la seva proposta:
  avui el resolem renunciant, i ell proposa resoldre'l reintentant amb alternatives.
- **`MEMORY.md` → `project_cartociudad_municipio_filter_accent_bug`** — el filtre de municipi de CartoCiudad és
  estricte amb els accents del costat servidor. Mateixa família de problema.
- **`MEMORY.md` → `reference_cadastre_not_truth_for_parcel_area`** — l'Eva escriu 1.284 m² = 441+423+420, la suma
  de **tres portals** («18A, 18B i 20»). La parcel·la correcta depèn d'entendre bé l'adreça sencera, no un portal.
- **Supòsit documentat que la proposta haurà de respectar o superar conscientment**
  (`docs/_FOR-NEW-YOU-20260901.md` §4): `resolve_portal` filtra `(pnp, plp)` **exactes** i mai delega al portal
  més proper, precisament perquè delegar-hi reproduiria un bug conegut de la via B (18B→18A). Qualsevol mecanisme
  de «reintent amb alternatives» ha d'explicar com evita ressuscitar aquell error.

## 3. Preguntes que la sessió d'anàlisi hauria de respondre

Enunciades, no respostes — són el guió de la conversa pendent, no conclusions:

1. Qui interpreta l'adreça: el skill de lectura (que ja llegeix els documents) o una capa nova dedicada?
2. L'objecte JSON proposat, ¿és una **sortida del lector** (una variable més del nivell A) o una **estructura
   interna** del resolutor de parcel·les?
3. D'on surten els noms alternatius de municipi i de via: ¿els genera el model, o d'un padró descarregat una sola
   vegada (INE, ICGC, Cadastre)? Té implicacions de determinisme i de cost.
4. Com es distingeix «zero resultats» de «resultats sospitosos», i qui decideix que un resultat és sospitós.
5. Quantes voltes de reintent són acceptables en latència, tenint en compte que la lectura d'un projecte ja triga
   28-42 minuts (mesurat avui: Castellar 27,8 min, Linyola 41,9 min).
6. Com es presenta a l'Eva quan el sistema no n'està segur: ¿candidats amb popup, com la resta del nivell A?
7. Com es valida que la parcel·la trobada és **la del projecte** i no una altra que casa amb l'adreça — el
   requisit que el Josep marca com a crític. ¿Creuament amb superfície del pressupost, amb el plànol, amb la
   referència cadastral d'algun document?

## 4. Restriccions que ja sabem

- **Mai un valor erroni amb aparença de fiable** (ERR = 0 mana per damunt de la cobertura). Val més `candidats` o
  blanc que una parcel·la equivocada — és exactament el cas que faria dir a l'Eva «està analitzant una altra
  parcel·la».
- `automation/geocode_coordinates.py`, `automation/parcel_resolver.py` i `automation/cadastre_adjacents.py` són
  **via B de producció**: es poden importar i llegir, mai modificar mentre l'Eva hi treballi.
- `automation/g3_templates.py` és per contracte un lector **determinista, cost 0, sense xarxa** (per això avui
  s'ha descartat validar el municipi contra un padró en línia). Si la proposta hi vol intel·ligència o xarxa, ha
  d'anar en una altra capa.

---

*Document d'anotació. No conté anàlisi ni decisió: totes dues queden per a la sessió nova que el Josep convocarà.*
