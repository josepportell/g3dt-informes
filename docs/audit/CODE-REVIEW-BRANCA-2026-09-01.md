# Code review de la branca sencera — `production/g3dt-eva-v1...experiment/nivell-a-2026-08`

**Data:** 2026-09-01 · **Abast:** el diff complet que rebria l'Eva en un merge (674 fitxers, ~136k línies;
el gruix són docs i datasets d'or — el codi revisat és el subconjunt real) · **Nivell:** high (local, no ultra).
**Resultat:** ~50 candidats de 10 angles → **30 CONFIRMADES, 5 PLAUSIBLES, 2 REFUTADES**; 8 més d'un escombrat
final de llacunes (2 provades executant el codi sobre fitxers reals de projecte).

> **Estat inicial: cap fix aplicat.** Aquest document es va escriure com a inventari per reparar-les *a
> posteriori* (decisió del Josep, 2026-09-01: hi havia lectures headless corrent i no volíem tocar el codi sota els
> processos). Cada entrada porta fitxer:línia, escenari de fallada i direcció de correcció. **Res d'això s'ha de
> fusionar a l'ordinador de l'Eva fins que els blocs P0 i P1 estiguin tancats.**
>
> **Actualització 2026-09-01, 14:10** — El Josep decideix aturar el hold-out després de Linyola i reparar-ho tot
> abans de continuar amb els 6 projectes restants. Les 15 troballes prioritàries estan repartides entre 4
> implementadors amb fitxers disjunts. El motiu de l'ordre és directe: **P1.1 i P1.3 contaminarien els números de
> qualitat** que el hold-out havia de mesurar, o sigui que mesurar primer i reparar després hauria estat mesurar
> soroll.

## Com llegir-ho

Ordenat per **impacte sobre l'Eva**, no per l'ordre en què la revisió les va trobar:

| Prioritat | Criteri |
|---|---|
| **P0** | Pot destruir dades o generar un informe amb dades d'un altre projecte / d'un projecte buit |
| **P1** | Produeix un valor **erroni amb aparença de fiable** al `.docx` (viola la mètrica ERR = 0) |
| **P2** | Degrada el servei o el fa inoperant (però no menteix) |
| **P3** | Fuita de dades del client o soroll |

---

## P0 — Pèrdua de dades i contaminació entre projectes

### P0.1 · Un tall de xarxa transitori pot buidar el projecte sencer
`automation/sync_workspace.py:656`

`sync_delta` tracta un escaneig de xarxa il·legible com un escaneig **buit** — cada `OSError` per directori es
menja amb un warning i continua. Si `os.scandir` peta a mitja passada (hiccup d'SMB) després que
`resolve_network_path` hagi tingut èxit, `net={}` → **tots** els fitxers locals semblen esborrats a la xarxa →
amb `check_only=False` tot el projecte es mou a `_esborrats/` (l'`os.replace` és local, així que funciona
perfectament amb la compartició morta) → `api.py` veu estat `ok` i arrenca la lectura sobre una carpeta buida,
produint `no_trobat` i decisions parcials amb tota la confiança. No hi ha cap guarda "xarxa buida però local
ple → avorta" entre les línies 639-689.

**Correcció:** guarda explícita abans de qualsevol moviment — si `net` és buit i el local no ho és, avortar amb
error, mai esborrar. I propagar l'`OSError` per directori en comptes d'empassar-se'l.

### P0.2 · Una còpia inicial interrompuda queda marcada com a completa per sempre
`automation/sync_workspace.py:422`

El camí de salt comprova només `dst.exists()` i tot seguit **"repara" el marcador de completesa que falta**. Si
la primera sincronització d'un projecte de diversos GB mor al 40 % (procés mort, caiguda d'SMB), `dst` existeix
sense marcador; la crida següent fa `dst.exists() and not force` → `_read_marker` torna `None` → **s'escriu el
marcador igualment** → estat `skipped: already in workspace`. Tots els camins clàssics (`GET /api/prefills`,
`/api/prefills-stream`, `GET /api/lectura-stream`) usen `sync_to_workspace(force=False)`, així que el salt és
permanent: el wizard genera informes a partir del 40 % del projecte amb PENETROS/SONDEIG absents en silenci.

**Correcció:** no escriure mai el marcador al camí de salt; si falta, tractar el destí com a incomplet i
re-sincronitzar.

### P0.3 · Les tries de taula d'un projecte viatgen a un altre
`templates/validation/review.html:9334`

`lecturaState.selections` s'inicialitza un sol cop i **no es reinicia mai en canviar de projecte**. L'Eva clica
un chip n30 al projecte A (`selections['spt_ma_tests.0.n30']`), després tria el projecte B al desplegable dins la
mateixa pestanya (sense recàrrega): en desar B s'envia la clau d'A, i `tables_report._selected` la casa per
`'{block}.{index}.{cell}'` contra el `_decisions.json` de B — el mateix índex genèric hi existeix — de manera que
**el valor N30 del projecte A queda congelat al `user_data` de B** i surt al seu informe. Només hi ha escriptures
additives a `.selections` (9452/9566/9570/9573/9614); cap reinici.

**Correcció:** buidar `lecturaState.selections` al canvi de projecte (i idealment qualificar les claus amb
l'expedient).

---

## P1 — Valors erronis amb aparença de fiables (violen ERR = 0)

### P1.1 · El lector del Cadastre confon la conjunció «i»/«y» amb una lletra de portal
`automation/lectura/cadastre_reader.py:66` — **codi enviat ahir (Fix D, `349ecca`)**

Provat executant-lo: `portals_from_address('Carrer Arbrells, 18 i 20')` → `[('18','I'), ('20','')]`.
`resolve_portal` filtra per `plp=='I'`, que cap portal real no té, de manera que **el portal 18 torna `[]` en
silenci** i només sobreviu el 20 → `superficie_parcela = 420` en lloc de 861, amb la font
`(Cadastre: 20 = 3298013DG2039N, 420 m²)` — confiada i incompleta —, i la `referencia_catastral` perd l'RC del 18.
La `b` de «bis» cau al mateix parany. A banda, la separació carrer/portal pel primer dígit destrossa els noms de
carrer amb xifres: `'Carrer 11 de Setembre, 5'` → carrer `'Carrer'`, portals `[('11','D'), ('5','')]`, i
`_consulta_via` puntua 60 per a qualsevol nom que simplement *contingui* «CARRER» (p. ex. CARRERADA) → un portal
pot resoldre's al carrer equivocat.

**Correcció:** llista de paraules-frontera (`i`, `y`, `bis`, `núm`) fora del grup de lletra; separar carrer i
portals per l'última coma, no pel primer dígit; exigir coincidència de nom de via més estricta que "conté".
**Rellevància directa:** és exactament el patró d'adreça de Castellar («18A, 18B i 20»), el cas que va motivar el
Fix D.

### P1.2 · La superfície construïda perd els sumands
`automation/lectura/tables_report.py:415`

`_superficie()` agafa **només el primer número** de la cel·la de total, però el consolidador mateix sintetitza
totals en forma de suma (`consolidate.py:1579` construeix `total='280+86'`). Verificat per execució: `'280+86'` →
`280.0`, i el dialecte del lector `'72 m2 + 20 m2 porxada'` → `'72'`. L'informe diu 280 m² on l'Eva signa 366. El
recurs de sumar components no s'activa mai (ja s'ha trobat un número) i, si s'activés, fallaria amb components en
forma de diccionari.

**Correcció:** avaluar la suma quan la cel·la té forma `a+b+c`; arreglar el recurs de components per a dicts.

### P1.3 · El regex de municipi de PLAN_COST captura la cua de la descripció
`automation/g3_templates.py:298`

Hi ha un espai dins la classe de caràcters final (`[A-ZÀ-Ü' .-]`), de manera que el grup mandrós s'atura a la
primera paraula i el municipi s'endú la cua de la descripció.

**Ampliat el 2026-09-01 executant `read_plan_cost` sobre els PLAN_COST reals dels 8 projectes: 7 de 10 fitxers
donen un municipi erroni.** No és un cas aïllat de Linyola:

| E9 real | Municipi actual | Correcte |
|---|---|---|
| `EG 3 HAB UNIF CASTELLAR DEL VALLÈS` | `HAB UNIF CASTELLAR DEL VALLÈS` | `CASTELLAR DEL VALLÈS` |
| `EG HAB UNIF RUBI` | `UNIF RUBI` | `RUBI` |
| `EG HAB UNIF CERDANYOLA` | `UNIF CERDANYOLA` | `CERDANYOLA` |
| `EG HAB UNIF LINYOLA` | `UNIF LINYOLA` | `LINYOLA` |
| `EG HAB UNIF BELL-LLOC` | `UNIF BELL-LLOC` | `BELL-LLOC` |
| `EG AMPL ALCOLETGE` | `ALCOLETGE` ✓ | `ALCOLETGE` |
| `EG VILANOVA SEGRIÀ` | **`SEGRIÀ`** (perd «Vilanova») | `VILANOVA SEGRIÀ` |
| `EG 7 VIVIENDAS ANCILES` | `VIVIENDAS ANCILES` | `ANCILES` |

Quan la comanda i el pressupost no donen municipi, això esdevé `concepts['municipality'][0]` amb confiança 0,6 al
`_g3_templates.json`, i `applyTemplatesFields` l'escriu directament a l'input `site_municipality` del wizard.
`tests/test_g3_templates.py` només comprova el valor consolidat amb la comanda primer, així que el camí no té test.

**Correcció — el fix ingenu NO serveix:** treure l'espai de la classe donaria `VALLÈS` a Castellar i `SEGRIÀ` a
Vilanova (municipis multi-paraula). Cal **consumir per l'esquerra els tokens de tipus coneguts** (`EG`, dígits,
`HAB`, `UNIF`, `VIVIENDAS`, `AMPL`…) i quedar-se tota la resta. Verificar contra els 10 fitxers reals i afegir un
test del camí PLAN_COST-only.

### P1.4 · Un valor provisional es queda a l'input mentre el badge n'ensenya un altre
`templates/validation/review.html:9693`

Asimetria de guardes: `applyTemplatesFields` **sobreescriu** qualsevol camp no-usuari amb el valor provisional de
la plantilla G3, però la branca `segur` d'`applyLecturaDecisions` només omple camps **buits**. TEMPS 1a escriu
superfície `'120 m2'`; TEMPS 3 decideix `segur = '135 m2'`; la guarda `(!el.value || el.value === "")` ja no es
compleix → **l'input es queda amb 120 mentre el badge i el popup diuen 135**. L'Eva genera l'informe amb el
provisional. L'ordre d'esdeveniments està garantit (`runner.py:1008`: `templates_fields` precedeix totes les
emissions de decisions) i la branca `candidats` **sí** que sobreescriu, cosa que confirma que l'anòmala és la de
`segur`.

**Correcció:** que la branca `segur` sobreescrigui tot el que no tingui origen usuari, igual que fa `candidats`.

### P1.5 · Les tries congelades de l'Eva es perden en recarregar la pàgina
`web/wizard_service.py:2736`

`save_wizard` reconstrueix incondicionalment `lectura_tables` des del `_decisions.json` actual, i després d'una
recàrrega la UI envia seleccions buides. L'Eva tria el candidat 2 per a `soil_levels.0.litologia` i desa
(congelat); recarrega (res no restaura `lecturaState.selections` des de `user_data`); edita un escalar i desa:
`_build_lectura_block(project_path, {})` → `_selected()` torna `None` → `resolve_cell` cau al `candidates[0]` →
`wizard.py:1050` `existing.update(extra)` **substitueix `lectura_tables`**. La tria validada revesteix en silenci
al `.docx`, desfent la congelació documentada, i la clau `lectura_selections` obsoleta sobreviu deixant el
`user_data` contradictori amb si mateix.

**Correcció:** restaurar `selections` des de `user_data` en carregar; no reconstruir blocs congelats quan
l'entrada ve buida.

### P1.6 · Documents substituïts continuen alimentant les decisions
`automation/lectura/inventory.py:149`

Dues llacunes independents. (a) El directori de quarantena del delta-sync, `_esborrats/`, **no l'exclou cap
escàner**: `inventory.py:149` mira només `g3_templates.EXCLUDE_DIRS` (que no el conté; igual el `_SKIP_DIRS` de
fileminer, l'escàner de concept_scout i els `_EXCLUDED_DIRS` d'auto_result_cache), així que l'A.01.pdf vell posat
en quarantena es torna a encaminar com a `claude` i es rellegeix. (b) Els `{doc}.json` d'`out_dir` no es poden mai
quan el document font es reanomena o s'esborra: `load_corpus` (`consolidate.py:549`) ingereix tots els
`out_dir/*.json` filtrats només per noms reservats, sense contrastar `source_path` amb l'inventari actual — i pel
dedup md5 de les línies 556-559 **l'orfe pot guanyar com a canònic** mentre el fitxer viu queda marcat de
duplicat.

**Correcció:** afegir `_esborrats/` a les exclusions dels quatre escàners; a `load_corpus`, descartar els JSON el
`source_path` dels quals no és a l'inventari.

### P1.7 · Els punts sense lletra desapareixen de les taules
`automation/lectura/consolidate.py:991`

`_point_key` **ignora el paràmetre `default_letter`**, de manera que els identificadors de punt sense lletra no
resolen mai. Provat: `_point_key('3','P')` és `None` tot i que els cridants de 1221/1225/1403 passen `'P'`/`'S'`
esperant un recurs. A 1221/1225 la guarda `if k:` **descarta la fila** dpsh/sondeig, que no arriba ni al
`_decisions.json`; a 1403 la fila SPT cau a `'S-?'`, que segons la línia 1410 es fusiona amb **qualsevol** grup
d'interval compatible — agrupació al sondeig equivocat.

**Correcció:** fer servir `default_letter` (per a això hi és) i, per a l'inclassificable, un cistell que no es
fusioni amb ningú.

### P1.8 · Les files de superfície construïda es dupliquen a cada consolidació
`automation/lectura/consolidate.py:1561`

`_superficie_construida` fa àlies de la llista del document del corpus (`entries = raw`) i l'estén **mentre la
recorre**; i la funció s'executa **dues vegades** per consolidació sobre el mateix corpus en memòria
(`consolidate_python` línia 1641 i després `consolidate_tables` línia 1323, amb `load_corpus` corrent un sol cop a
1614). Provat: la llista del corpus creix 1 → 2 → 3 i el compte de components va d'1 a 2. La segona crida —la que
s'envia— duplica cada component i cada senyal del `_decisions.json`, i els senyals idèntics duplicats poden
**inflar el consens de `decide()`**.

**Correcció:** copiar la llista abans d'estendre-la; i decidir quina de les dues crides mana (o fer la funció
idempotent).

---

## P2 — Servei degradat o inoperant

### P2.1 · Amb Claude Code instal·lat per npm, l'Eva es queda sense lectura **i** sense visió
`automation/lectura/runner.py:352`

La porta d'existència del CLI fa servir `shutil.which` (que honora `PATHEXT` i troba `claude.cmd`) però
**descarta el camí resolt**; després `Popen` rep el nom pelat, que `CreateProcess` no pot executar per a un
`.cmd`. Amb una instal·lació `npm install -g @anthropic-ai/claude-code` (només `claude.cmd`, sense `.exe`):
`lectura_service.py:342` passa la porta, així que **no s'emet cap `lectura_fallback`**; cada `_run_claude` llança
`FileNotFoundError` i tots els documents acaben `failed`; la consolidació encara torna decisions no-nul·les només
des de `_g3_templates.json` → `has_lectura=True` → `_merge_prefills(skip_vision=True)` **també salta la visió per
API de la via B**. El resultat net és pitjor que qualsevol dels dos camins: ni lectura ni visió, i sense cap
bàner.

**Correcció:** passar el resultat de `shutil.which()` a `Popen`. **Verificació obligatòria a la Fase 17
(presencial Windows): `where claude` a l'ordinador de l'Eva.**

### P2.2 · La memòria cau de consolidació no pot encertar mai en mode job
`automation/lectura/runner.py:60`

`_RESERVED_JSON_NAMES` del runner omet `_job.json` (la còpia de `consolidate.py` sí que el té).
`JobRegistry.start` escriu `_job.json` al mateix `out_dir` abans d'arrencar el fil (`jobs.py:453`) i el reescriu a
cada `lectura_doc`, de manera que `_consolida_cache_valid` sempre el veu més nou que `_decisions.json`:
**re-executar un projecte sense canvis torna a pagar `consolidate_python`** i, si hi ha conflictes, el
`claude -p --consolida` de diversos minuts (timeout 900 s). A més `_merge_minimal` (línia 854) ingereix
`_job.json` com un document, afegint `'_job.json'` a `sources_read` i desactivant el sentinella de zero documents
llegits. **Acoblat:** `_consolida_cache_valid` no fa `stat` de cap fitxer font i ignora
`_g3_templates.json`/`_inventory.json`, així que en el moment que es reservi `_job.json`, editar `PLAN_COST.xlsx`
o `COORDENADES.txt` servirà decisions rancioses **precisament al botó que existeix per recollir els canvis**.

**Correcció:** els dos canvis alhora, mai un de sol — reservar `_job.json` **i** fer que la validesa de la memòria
cau miri les mtimes de les fonts.

### P2.3 · Una caiguda transitòria d'ICGC es replica durant 30 dies
`web/wizard_service.py:2004`

`auto_result_cache` desa **incondicionalment** i valida només versió/TTL/empremta, de manera que una execució
degradada per fallades transitòries d'ICGC/Cadastre/Groq es reprodueix fins a 30 dies. Si ICGC cau deu minuts
mentre l'Eva obre un projecte, `auto_extract` es menja les fallades a `steps_skipped` i torna prefills degradats;
`save()` ignora aquest senyal. L'Eva prem «Actualitzar prefills» → el camí SSE crida `_auto_extract_cached`
**sense `force_refresh`** (`wizard_service.py:2373`, `lectura_service.py:314`) → encert de memòria cau → els
mateixos prefills buits, amb els events de progrés replicats, fins que canviï algun fitxer. A banda,
`inputs_fingerprint` es calcula **dins de `save()` després** de l'extracció de 43-141 s, de manera que un A.01.pdf
que arribi a mitja execució queda dispersat a l'empremta encara que el resultat no l'hagi vist mai — una entrada
rancosa amb aspecte de vàlida permanentment.

**Correcció:** no desar execucions amb `steps_skipped` no buit; calcular l'empremta **abans** de l'extracció;
que «Actualitzar prefills» forci el refresc.

### P2.4 · Per sota del tall, però reals

| Què | On |
|---|---|
| `normalize._repair_cell` llança `KeyError` amb candidats en forma de dict → descarta una lectura sencera reeixida | `automation/lectura/normalize.py` |
| `jobsRefresh` atura el sondeig de 5 s **permanentment** a la primera resposta no-ok | `templates/validation/review.html` |
| `POST /api/jobs` fa 404 quan la compartició no es pot abastar tot i haver-hi una còpia local completa | `web/api.py` |
| La cadena de backends de visió avorta a la primera truncació en lloc de provar el següent proveïdor | `web/vision_*.py` |
| `docs_done` compta els duplicats saltats → la taula ensenya «9/7» | UI + runner |
| Els jobs cancel·lats ofereixen un botó «Veure progrés» que sempre peta | UI |
| `String(job.error)` i `sc.components.join('+')` renderitzen `[object Object]` | UI |
| La telemetria no es trunca per job → els correus de notificació barregen execucions i poden adjuntar el log de fallada d'un job anterior | `automation/lectura/notify.py` |

---

## P3 — Fuita de dades del client

### P3.1 · Els camins de Windows reals no es censuren als correus de telemetria
`automation/lectura/notify.py:164`

L'escombrada de camins de Windows de `sanitize_log` exigeix **dues barres invertides literals** després de la
lletra d'unitat, de manera que els camins reals amb una sola barra —**l'única forma que existeix a la plataforma
de producció**— no es censuren mai. Verificat executant `sanitize_log`:
`'ENOENT: no such file C:\g3dt-ia\projectes\4001612 BELL-LLOC\PENETROS DPSH.pdf'` passa intacte (el regex només
casa `'C:\\...'`) i la línia sobreviu al filtre `_LOG_KEEP`. Sempre que les substitucions d'àlies/projecte fallin
—`_inventory.json` il·legible i per tant `aliases={}`, o un fitxer que no vagi per la ruta `claude`— **el camí
sencer amb la carpeta del projecte del client i el nom del document s'envia per correu a Eficients**, trencant la
garantia de disseny «cap nom de fitxer». Cap test cobreix camins amb barra invertida.

**Correcció:** regex amb una barra o més; test amb camins de barra simple.

---

## Segona volta — la revisió creuada de les 15 correccions (2026-09-01, vespre)

Un revisor independent ha comprovat les 15 correccions. **Veredicte: REQUEST_CHANGES.**

**El que va sortir bé** (verificat executant, no llegint):
- **0 regressions.** Es va re-consolidar amb codi vell i nou **9 corpus reals** (els 2 hold-out d'avui + els 7
  `*/perdoc` de les mesures d'agost): **0 diferències semàntiques**. La suite passa de 1640 a 1773 amb
  **exactament els mateixos 32 noms de test fallats** (tots per `reference-material` absent, cap pel diff).
- **Els supòsits documentats de `_FOR-NEW-YOU-20260901.md` §4 segueixen tots dempeus** (portals exactes,
  `cp:areaValue`, bloc E2/E2b de `soil_levels`, ordre dels camps de Cadastre).
- **La fixture `synth` ampliada no amaga res**: les 6 entrades noves són exactament els 6 `{doc}.json` que la
  mateixa fixture crea, amb els md5 que ja tenien, duplicat deliberat inclòs.
- **Qualitat dels tests nous, alta**: cap test tautològic trobat; els de JS executen les funcions reals sota Node.

**Tres camins que violen ERR = 0, dos d'ells oberts per la nostra pròpia tanda** (→ segona volta de correcció,
llançada 2026-09-01 vespre):

| # | On | Què |
|---|---|---|
| C1 | `consolidate.py:545` | `_inventory_paths` **inclou** les entrades `route="skip"` → el filtre d'orfes no serveix i **P1.6 segueix obert**; incoherent amb `_consolida_fingerprint`, que sí que les salta |
| C2 | `wizard_service.py:2766` | Les tries congelades es ressusciten **sense validar-les** contra el `_decisions.json` actual → valor d'una lectura vella estampat sobre una fila diferent, i l'Eva no ho veu |
| C3 | `tables_report.py:186` | `_components_sum` converteix blancs honestos en xifres errònies: `["P1: 85 m2","PB: 120 m2"]` → **121** |

**Quatre avisos, també enviats a la segona volta:**
- `_point_key` massa ampli: `"SPT-2"`→`S-2`, `"MA1"`→`S-1`, `"03/09/2025"`→`P-3`. El cistell `S-?` que acabàvem
  d'aïllar es queda sense feina perquè ara gairebé mai no torna `None`.
- Regressió d'adreces: `"Avda. Catalunya 24, 3r 2a"` perd el portal 24 (se'n va al nom del carrer).
- `sync_delta` falla en dur amb **una sola** entrada il·legible → HTTP 404 → **l'Eva no pot ni començar**. I la
  guarda no cobreix les desaparicions *parcials* (un `ANNEXES/` que deixa de veure's encara s'aparta sencer).
- `("ConceptScout", str(exc))` no és a la llista de fallades externes → una tarda de 429/503 queda cachejada 30
  dies. I al revés: `("Geocodificació", "no s'han trobat coordenades")` compta com a externa, així que un projecte
  rural que mai geocodifica **no escriurà mai la cache** i pagarà els 43-141 s a cada obertura.

**Dada de calibratge que val la pena retenir:** el revisor va recórrer els `{doc}.json` dels 9 corpus i **els
únics tres `total` reals de `superficie_construida` són `'120'`, `'120 m2'` i `'250.91 m²'` — cap amb `+`**. Tot
el camí de suma que vam arreglar (P1.2) està **sense exercitar contra el dialecte real del lector**: la forma
`'280+86'` només la sintetitza el consolidador, i encara no ha passat mai.

## Tercera passada — revisió de la segona volta (2026-09-01, nit)

**Veredicte: REQUEST_CHANGES** (1 crítica, 4 avisos, 6 suggeriments). Tot verificat executant.

**Confirmat que està tancat:** C1, C2 i C3 i els quatre avisos de la volta anterior. Amb números:
`municipality` de la quarantena passa de `candidats "BELL-LLOC"` (document mort guanyant) a `segur "LINYOLA"`;
la tria morta `"Sorres fines amb graves (lectura ANTERIOR)"` ja no arriba a la taula; `["P1: 85 m2","PB: 120 m2"]`
passa de `121` a `205`, i amb un sumand il·legible a blanc honest.

**Regressió: 0 diferències semàntiques** sobre els 9 corpus reals (l'única diferència a tot l'arbre JSON és la
marca de temps `generated`), `orfes=0` als 9 — el filtre nou no dona cap fals positiu sobre dades reals. Suite
**1835 passed / 32 failed**, els 32 del baseline, cap als mòduls tocats.

**El canvi fora de brief d'Agent A (`_component_m2`) queda justificat amb dades**, seguint el camí en tres estats:

| | cel·la `value` | `.docx` |
|---|---|---|
| HEAD | `'1+120'` | `'1'` |
| 1a volta, sense `_component_m2` | `'1+120'` | **`'121'`** ← el pitjor cas |
| ara | `'85+120'` | `'205'` |

**La fixture `_fake_via` tocada és legítima**, contrastada amb les respostes reals cachejades
(`{"value": ["ARBRELLS DELS", "CL", "372"]}`): el camp `nv` mai no porta el tipus de via. I els 7 carrers reals
dels projectes segueixen casant.

**La decisió de latència sobre `Geocodificació` no costa res al corpus real:** dels 7 projectes de referència, 4
tenen `COORDENADES.txt` i els altres 3 geocodifiquen tots amb èxit → **0 de 7 pagarien l'espera** per aquesta tria.

### Pendents d'aquesta passada (5 accions)

| # | On | Què |
|---|---|---|
| **A1 (crítica)** | `consolidate.py:595` | L'escapatòria «tots orfes» **reobre C1 en un racó**: quan TOTS els `{doc}.json` són de fitxers en quarantena, el filtre es desactiva sencer i un document de la carpeta d'esborrats decideix un camp **a `segur`**. Cal disparar-la només quan cap `source_path` sigui a **cap** entrada de l'inventari (incloses les `skip`) — una ruta coneguda-però-en-quarantena és un orfe *sabut*, no un indici d'inventari incomparable |
| A2 | `wizard_service.py` | `_build_lectura_block` ha d'escriure `lectura_selections` **sempre** (encara que buit), perquè `existing.update(extra)` netegi la clau morta; i `load_user_data` ha de validar també el camí de `user_data.json` (ara el docstring promet una cosa que només fa a mitges) |
| A3 | `sync_workspace.py:756` | La branca de desaparició massiva **bloqueja l'Eva sense sortida**: 3 de 5 fitxers esborrats a posta → HTTP 404 amb el consell equivocat («comprova la xarxa»). Incoherent amb la branca germana de `net_errors`, que davant del mateix risc deixa passar sense apartar res |
| A4 | `wizard_service.py:1990` | `Deep folder classify` (visió amb OpenAI, `auto_extractor.py:975/1015`) no és a `_EXTERNAL_SKIP_STEPS` → una tarda de 429/503 es cacheja 30 dies. Mateix defecte que acabàvem de tancar per a ConceptScout |
| A5 | `consolidate.py:1636` | Les dues funcions «bessones» de sumand **no ho són**: `_component_m2` no llegeix la clau `valor`, que és el dialecte real de Linyola → `28.55 m²` es perd. No és regressió (HEAD fa igual), és cobertura perduda |

### Deute conegut anotat (no bloqueja)

- `review.html:10029` — `sc.components.join('+')` amb components en forma d'embolcall: l'Eva veu
  **`[object Object] (null)`** al valor de la superfície. Era P2.4; ara és **l'única forma que hi arriba** als dos
  projectes del hold-out.
- `tables_report._superficie:517` — la branca `chosen` no passa per `_sum_total`: una tria de `"280+86"` aniria
  crua al `.docx`. Inabastable per la UI d'avui, latent.
- `review.html:4878` — canviar de projecte mentre viatja `/api/user-data/A` deixa B **sense restaurar** les seves
  tries. No hi ha contaminació (això ja està tancat), només pèrdua de funcionalitat.
- `_POINT_RE` sense tocar: `"Sorres 3"`→`S-3`, `"PS-1"`→`S-1`. La classe «identificador inventat» queda tancada
  al **recurs** però no a la **cerca**.
- `build_inventory` fa md5 de tota la quarantena a cada execució i `_esborrats/` creix indefinidament → latència
  que puja amb el temps.
- N1 (`building_type`) i N3 (`loadProjectDataFallback`) segueixen oberts.

## Quarta passada — tercera volta de correcció (2026-09-01, nit)

Les 5 accions de la tercera passada, més el fix de l'`Avda.` aprovat pel Josep. Suite **1882 passed / 32 failed**
(els 32 del baseline). Pendent de revisió final.

| # | Estat | Detall |
|---|---|---|
| A1 | fet | L'escapatòria d'orfes compara ara contra **totes** les rutes de l'inventari, quarantena inclosa. Repro del revisor: `segur 'MUNICIPI MORT'` → `no_trobat`. S'hi va afegir un segon guard (inventari 100 % `skip`) que anava més enllà del brief |
| A2 | fet | `_build_lectura_block` escriu `lectura_selections` **sempre**; `load_user_data` valida també el camí de `user_data.json` i **esborra** la clau quan no sobreviu cap tria. Verificats els 2 únics consumidors abans de canviar què retorna |
| A3 | fet | La desaparició massiva amb `check_only=False` retorna `ok`, copia, **no aparta res** i avisa sense acusar la xarxa. `check_only=True` segueix sent error, intacte. `web/api.py` no ha calgut tocar-lo |
| A4 | fet | `Deep folder classify` a `_EXTERNAL_SKIP_STEPS` + el seu motiu estructural. **Encreuament complet dels 41 `steps_skipped`: només en faltava aquest** |
| A5 | fet | Vegeu avall — va resultar més gran i més ben resolt del previst |
| Avda | fet | `_STREET_PREFIX_RE` ordena formes llargues abans que curtes + lookahead de lletra |

### A5 · La normalització de components: una instrucció meva era errònia

Jo havia dit de posar la normalització a `contract.py` (`_adapt_tables_dialect`). **L'agent ho va verificar i va
trobar que `contract.adapt_legacy` no és una porta de producció**: només l'invoca
`docs/wizard-headless/fase0-acceptacio/compare_consolida.py` per llegir els fixtures d'or, i cap fixture d'or no
porta `components`. Posar-hi la normalització no hauria arreglat res a producció.

Les portes reals per on entra un dialecte del lector són dues: `consolidate.load_corpus` (per als `{doc}.json`) i
`normalize.soft_normalize` (per al `_decisions.json` de la crida `--consolida`). La normalització va a
**`normalize.py`**, que és stdlib pur i el poden importar tots dos.

Resultat: **una sola llista d'àlies a tot el projecte** (`COMPONENT_VALUE_ALIASES`), una clau canònica
(`COMPONENT_VALUE_KEY = "value"`), i les dues llistes ad-hoc esborrades. Ordre de certesa decreixent per resoldre
un sumand: clau canònica amb xifra → àlies conegut amb xifra → **xifra ancorada a `m2`/`m²`** (xarxa per forma) →
intacte (blanc honest, mai una xifra inventada).

**Rastre de claus desconegudes → `notes_estructurals`**, dins del `_decisions.json` de cada projecte. Raonament de
l'agent, que comparteixo: un log es perd o es trunca; un avís de contracte convertiria un dialecte nou en
degradació de la lectura, que és pitjor que llegir-lo per forma. És el mateix canal que ja porta duplicats, orfes
i lectures fallides.

**0-diff sobre els 9 corpus reals**, amb els fitxers «abans» reconstruïts de debò en un arbre ombra (no
monkeypatch): 0 diferències a 8 corpus; a Linyola, 12 diferències que són **només el renom `valor` → `value`** —
cap valor, cap `total`, cap cel·la del `.docx` afectats. `orfes=0` i `contracte_errors=0` als 9, i **cap nota de
dialecte desconegut** (els dialectes reals ja són tots coneguts).

**Cobertura guanyada però no visible avui:** el dialecte `valor` només es perdia quan el document **no** dona
total, i cap dels 9 corpus té aquesta combinació. Provat sintèticament: `{"concepte","valor"}` sense total passa
de blanc a `56.75+165.61`; una clau nova ancorada a unitat (`sup_planta: "280 m²"`) passa de blanc a `366`.

### Trobat de passada: un segon bug de prefix de via, viu i no reportat

Repassant el patró «abreviatura curta que és prefix d'una de llarga»: `cam[ií]` es menjava la «i» de
**`"Camino Viejo 5"` → `'no Viejo'`**. Mateix defecte que l'`Avda.`, en un altre tipus de via. Amb el lookahead
nou, una abreviatura **no** llistada (p. ex. `Pge.`) degrada a deixar l'adreça sencera intacta en comptes de
donar mig nom amb pinta de bo.

### Deute nou anotat

- **Els avisos del delta-sync no arriben mai a la pantalla de l'Eva** — ni el de desaparició massiva ni el
  d'escaneig incomplet, que ja hi era. Es queden al resultat intern i al log. Vol dir que el sistema pot prendre
  una decisió prudent (no apartar cap document) i **no dir-ho a ningú**. Falten poques línies a `web/api.py`.
- **El dialecte del `total`** (`total`/`total_m2`/`value` a `consolidate.py`) és la mateixa classe de problema una
  capa amunt, sense normalitzar. Assenyalat per l'agent, fora d'encàrrec.

## Cinquena passada — revisió final: **APPROVE** (2026-09-01, nit)

Els 5 pendents tancats i verificats executant. **Regressió nul·la a la sortida que arriba al `.docx`**:
`build_report_tables` és **byte-idèntic als 9 corpus**; les úniques diferències al `_decisions.json` són les 12 de
Linyola (renom de clau, mateix valor). Cap camí on l'Eva quedi bloquejada, cap on s'aparti res indegudament, cap
violació d'ERR = 0 reproduïble amb el dialecte real. Suite **1882 passed / 32 failed**, i els 12 mòduls del diff
donen **536 passed** en aïllament.

Verificat també: el renom de clau **no deixa cec cap consumidor** (grep Python + JS), funciona amb els
`_decisions.json` **antics** ja escrits a disc, i la funció és **idempotent** (2× i 3× sobre 8 formes). El fix P0.2
del marcador **no provocarà cap re-sincronia massiva el dia del merge** (els workspaces de l'Eva ja en porten).
Els prefixos de via milloren en 5 formes i no en regressa cap de les 20 reals.

### ⚠ La troballa que importa: A4 (i el seu germà de la 2a volta) **no funcionen**

**`web/wizard_service.py` — el comentari afirma una protecció que no existeix.** Verificat executant: amb la visió
de la fase 0.46 fallant a cada fitxer, `steps_skipped == []` i `_external_service_failures()` torna `[]` → **el
resultat degradat es desa i se serveix 30 dies igualment**. La causa és aigües amunt: `_layer2_vision`
(`auto_extractor.py`) i `concept_scout/vision_probe.py` **s'empassen l'excepció** i no emeten cap `steps_skipped`.

Això val **tant per a `Deep folder classify` (3a volta) com per a `ConceptScout` (2a volta)**: hem "arreglat" dues
vegades una cosa que no arregla res. El veto de memòria cau només funciona de debò per a ICGC, Cadastre,
Geocodificació i Groq Deep Mine, que sí que propaguen l'excepció.

**Un comentari que promet una protecció inexistent és pitjor que no tenir-la**: la propera persona hi confiarà.
Com a mínim s'ha de corregir el comentari; la correcció bona és que aquells dos passos reportin la fallada.
Nota: `auto_extractor.py` i `concept_scout/` són **via B** — canviar-los demana decisió explícita del Josep.

### Deute conegut que va a la sessió nova

**P1 — ERR latent, al codi que acabem d'escriure (petits, ~3 línies cadascun)**

1. `tables_report._component_number`, **camí DICT**: no aplica la regla d'ancoratge que sí aplica el camí STRING.
   `{"value": "…(porxo 22.15…) 28.55 m²"}` → **22.15** en comptes de 28,55; al `.docx`, `187.76` vs `194.16`.
2. Les «bessones» **no ho són**: `consolidate._numbers` treu els parèntesis, `tables_report._num` no → el total
   sintètic desat i la cel·la del `.docx` poden divergir.
3. `normalize._has_figure` accepta **qualsevol dígit**: `{"value":"P1","valor":"85 m2"}` → `1.0`, i **sense
   rastre**. Ha d'exigir xifra ancorada o nua.
4. `_anchored_key` pot triar l'etiqueta quan la xifra real ve numèrica sota clau desconeguda:
   `{"planta":"PB (porxo 22.15 m²)","area":165.61}` → 22,15. Cas perillós real: «Superfície útil 515,62 m²», que
   el document de Linyola avisa expressament de no confondre amb la construïda.

Tots quatre viuen al camí «sumands en forma de dict, document sense total», que **cap dels 9 corpus exercita**.

**P2 — fixos que diuen més del que fan**

5. A4/ConceptScout: vegeu l'avís de dalt.
6. ~~Els avisos del delta-sync no arriben a la pantalla de l'Eva.~~ **FET (2026-09-01, nit).** `POST /api/jobs`
   propaga `warnings` + `sync` (`scan_incomplete`/`mass_disappearance`/`scan_errors`/`vanished`), i `review.html`
   els ensenya en un bàner ambre dins `#jobsPanel` (no dins el formulari: amb «Preparar» el formulari no s'obre
   mai). El text de `sync_workspace` viatja **verbatim** i s'hi afegeix què pot fer l'Eva. Es neteja en canviar de
   projecte. Suite **1897 passed / 32 failed**.
   **Residu conegut:** el camí `check_only=True` (la taula d'estat, botó «Actualitzar») **segueix callat a posta**
   — `lectura_service.py:559` decideix que val més no dir res que dir «res ha canviat» sense haver-ho pogut mirar
   tot. Defensable (la taula no bloqueja ningú), però si l'Eva mira la taula i no arrenca cap job, no s'assabenta
   de res. Tocar-ho és `lectura_service.py`.

**P3 — preexistents, ara amb més abast**

7. Separador de milers: `"1.284 m2"` → `1.284` (idèntic a HEAD, però ara `_sum_total` hi arriba: `"1.284+86"` →
   `87.284`). **1.284 m² és una xifra real d'aquest domini** (Castellar).
8. `"20 m2 porxada + 30 m2"` → `20` (etiqueta entre xifra i `+`), documentat com a límit.
9. `soft_normalize` (camí `--consolida`) canonicalitza **sense** rastre de dialecte.
10. `review.html:10029` — `sc.components.join('+')` → `[object Object]` al popup (només UI; l'input no s'hi toca).
11. `tables_report._superficie:521`, branca `chosen`: no passa per `_sum_total`.
12. `_POINT_RE` sense tocar: `"Sorres 3"`→`S-3`, `"PS-1"`→`S-1` (el recurs està tancat, la **cerca** no).
13. `build_inventory` fa md5 de tota la quarantena a cada execució i `_esborrats/` creix indefinidament.
14. N1 `building_type` = E9 sencer — **confirmat obert**. El municipi sí que surt net.
15. N3 `loadProjectDataFallback` força `?refresh=true` — **confirmat obert** (`review.html:5031`).
16. `Avinguda 11 de Setembre 30` **sense coma**: el carrer segueix perdent-se (igual que a HEAD).
17. `STATUS.md` a 318 línies (regla del CLAUDE.md: ~50) i tres logs de sessió per sobre de 100.

**Aprenentatge d'àlies — decisió de disseny pendent** (pregunta del Josep, 2026-09-01): el rastre de claus noves
va a `notes_estructurals` **per projecte**, i ningú l'agrega. Cal (a) un agregador que recorri tots els projectes,
i (b) fer-lo viatjar pel correu de telemetria, que és l'únic canal des de la màquina de l'Eva. **L'adopció d'un
àlies ha de seguir sent un canvi de codi revisat**, mai automàtica: un nom desconegut pot ser el model
equivocant-se, i adoptar-lo cimentaria l'error.

## Obertes de nou, trobades mentre reparàvem (2026-09-01)

### N1 · `building_type` de PLAN_COST és l'E9 sencer, municipi inclòs
`automation/g3_templates.py` (~línia 295)

En arreglar el municipi (P1.3) es va veure que el senyal germà de la mateixa cel·la emet **l'E9 sencer** com a
tipus d'edifici: `building_type = 'EG HAB UNIF BELL-LLOC'`, amb confiança 0,6. Va darrere de `comanda_lab_g3` a
`PRIORITY`, així que només guanya quan la comanda no dona tipus — però llavors el wizard ensenya un tipus
d'edifici que porta el municipi enganxat i el prefix comptable «EG».

No s'ha tocat deliberadament: canviar-ho és un canvi de comportament fora de l'encàrrec del fix, i
`test_plan_cost_cel_les` asserta el valor actual. El partidor nou (`_split_plan_cost_title`) ja té el tipus net
(`'EG HAB UNIF'`) disponible, o sigui que el fix és barat quan es decideixi.

**Pendent de decisió:** ni l'E9 sencer ni `'EG HAB UNIF'` són el que l'Eva escriu a l'informe («habitatge
unifamiliar»). Val la pena mirar què diuen els informes signats abans de triar; és candidat a mesurar-ho amb el
comparador de taules en comptes de decidir-ho a ull.

### N3 · `loadProjectDataFallback()` força el refresc incondicionalment
`templates/validation/review.html:5008` (i el bloc bessó de ~5811)

Crida `/api/prefills/...?refresh=true` **sempre**, no només quan l'Eva prem el botó. És el camí de recurs quan
l'SSE peta: si es dispara en una obertura normal, se salta la memòria cau i tornem als **43-141 s** d'espera.
Preexistent (no el va introduir cap fix d'avui), però és **l'únic forat que queda** del requisit «el botó força,
l'obertura normal no».

**Correcció:** que el fallback propagui el `refresh` que li arriba en comptes de fixar-lo a `true`.

### N4 · Dos tests del runner són inestables sota càrrega
`tests/test_lectura_runner.py::test_telemetry_has_cli_metrics_when_json` i `::test_telemetry_without_json_is_marked`

Fan subprocessos amb `G3DT_LECTURA_TIMEOUT=2` (fixture preexistent). En una passada sencera amb la màquina
carregada van fallar (34 failed); en la següent, no (32 failed); en aïllament passen sempre. **No tenen relació
amb els canvis d'avui** (verificat corrent la suite amb i sense els fitxers nous), però desquadren el recompte si
algú compta les fallades d'una sola passada. Si es toca el fixture, pujar el timeout.

### N2 · Una tolerància de test existeix per emmascarar el bug del municipi
`tests/test_lectura_consolidate.py:102`

`keys_compatible("HAB UNIF CASTELLAR DEL VALLÈS", "Castellar del Vallès")` — una tolerància escrita
*precisament* perquè el municipi arribava brut. Segueix passant (és un test de strings), però ara ja no fa falta.
Revisar si amagava res més.

## Refutades (no perdre-hi temps)

- **Cursa d'escriptura fora del pany a `Job.emit`** — producció té un únic fil emissor.
- **Deriva del mapatge JS/Python** — les 12 claus compartides són idèntiques.

## Fora d'abast d'aquesta passada (netedat i governança)

Descartats sota el límit de "correcció primer", però anotats: set còpies de `_write_json_atomic`; deriva de
`_NEVER_SEGUR_CELLS` entre tres mòduls; mapatge escrit a mà que duplica `report_variables.yaml`. I tres
incompliments del CLAUDE.md: `STATUS.md` té 318 línies contra la regla de ~50, i tres logs de sessió passen de
100 línies.

---

## Lectura creuada amb la mesura de qualitat en curs

Tres troballes toquen **directament** els números que estem mesurant avui amb el hold-out headless, i cal tenir-ho
present en interpretar-los:

- **P1.1** (Cadastre «18 i 20») afecta `superficie_parcela` i `referencia_catastral` — els dos camps que el harness
  ja marcava `FORA` a Castellar.
- **P1.3** (municipi `'UNIF LINYOLA'`) afecta `municipality` a Linyola, Bell-lloc i Anciles quan PLAN_COST és
  l'única font.
- **P1.2** (superfície `'280+86'` → `280`) afecta `superficie_construida` al `.docx` final, no a la lectura: no el
  veurem al comparador de lectura, **sí** al de taules contra els informes signats.

*Fi de l'inventari. 15 troballes prioritàries + 8 sota el tall + 2 refutades, cap reparada.*
