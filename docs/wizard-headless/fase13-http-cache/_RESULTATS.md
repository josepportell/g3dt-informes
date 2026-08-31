# Fase 13 — `auto_result` a disc + fonts HTTP al consolidador (2026-08-26, tarda)

**Què tanca:** la fila 13 del pla de l'annex (`../../DISSENY-ANNEX-TRES-BOTONS-JOBS-NOTIFICACIONS-2026-08-24.md` §10),
en les seves dues meitats — §7.1 (`auto_result` persistit) i el que quedava del forat 1 de `../fase8-e2e/_RESULTATS.md`
(fonts Python invisibles al consolidador). Commits `65786a1` (a) i `89b8df2` (b).

---

## (a) `auto_result` a disc — latència

TEMPS 1 (FileMiner + `groq_miner` + probes ConceptScout + deep-folder classify + APIs HTTP) es tornava a executar
**sencer a cada arrencada del servidor**, encara que ni un fitxer del projecte hagués canviat. Ara
`AutoExtractionResult` viu a `validation/_auto_result.json`.

**Mesura** (Castellar, còpia local a l'scratchpad, `get_prefills` sencer — no només `auto_extract`):

| | cache freda | cache calenta |
|---|--:|--:|
| paret | 40,4 s | **5,6 s** |
| claus del wizard | 121 | 121 |
| claus diferents | — | **1** |

L'única diferència és `terrain_observation`: prosa d'una crida de visió sobre les fotos de camp que `_merge_prefills`
fa fresca sempre. Varia igual entre dues execucions **sense** cache — no és un efecte d'aquesta fase.
La segona càrrega no crida `auto_extract` en absolut (verificat amb `auto_extract` substituït per una excepció).

A la màquina de l'Eva la línia de sortida és més alta que 40 s: el diagnòstic 23/08 dona ~141 s per a TEMPS 1.

**Empremta (`inputs_md5`) — md5 del CONTINGUT, no `mida+mtime`.** El delta-sync de la Fase 11 copiarà fitxers de la
xarxa al workspace i una còpia canvia l'mtime sense canviar res: amb `mtime` la cache no encertaria mai després d'un
sync. Cost mesurat: 0,46 s per als 56 MB de Castellar.

**Exclusions verificades empíricament**, no deduïdes: snapshot md5 de les 173 entrades de Castellar abans i després d'un
`auto_extract` → l'únic fitxer que canvia fora de `validation/` és `file_mapping.json`. La llista és curta a posta:
excloure de menys costa una re-execució, excloure de més serveix dades velles.

**Quatre barreres d'invalidació:** `inputs_md5` · TTL 30 dies (els camps d'ICGC/Cadastre poden canviar sense que cap
fitxer es mogui) · `CACHE_VERSION` · sortides acompanyants (`file_mapping.json`, `validation/concept_map.json` són fora
de l'empremta perquè canvien a cada execució, però `_merge_prefills` les rellegeix del disc: es desa quines hi havia i
es comprova que hi segueixin sent).

---

## (b) Cadastre / ICGC / geocodificació al consolidador

`auto_extract` ja consultava el Cadastre i l'ICGC; el consolidador no ho veia mai. Ara `http_field_signals()` llegeix
`validation/_auto_result.json` **via `auto_result_cache.load()`** — o sigui només si l'empremta encara quadra i
l'entrada no ha caducat. Cap crida de xarxa nova dins del consolidador.

**Només omplen forats.** La crida viu darrere la mateixa porta que `derived_field_signals` (només quan CAP document de
la carpeta ha dit res del camp). És la traducció literal de la regla: *cap font Python pot guanyar un camp contra la
lectura*. Per això no cal afinar la confiança perquè "no bloquegi" — mai coexisteix amb un senyal de document.

| camp nivell A | prefill | font | per defecte |
|---|---|---|---|
| `cota_referencia` | `cota_referencia` | ICGC MDT 2m | **encès** |
| `utm_x` / `utm_y` | `_resolved_utm_x/_y` | geocodificació | **encès** |
| `referencia_catastral` | `cadastral_ref` | Cadastre | apagat |
| `superficie_parcela` | `superficie_cadastral_m2` | Cadastre | apagat |

### Per què el Cadastre queda apagat

El handoff avisava que connectar-lo «no és automàticament un guany» i que calia comprovar-ho projecte a projecte.
Comprovat, a l'únic projecte on es pot mesurar:

- L'or de lectura de Castellar diu **`no_trobat`** per a `referencia_catastral` i `superficie_parcela`: els documents de
  la carpeta no els contenen.
- El Cadastre respon **441 m²**. L'informe signat de l'Eva diu **1.284**
  (`reference-material/3001621 CASTELLAR DEL VALLES/validation/eva_reference_values.json`, llegit, no citat de memòria).
- Encendre'l canvia els dos camps de `no_trobat` a `candidats` amb un valor equivocat. `compare_consolida.py` passa de
  **14 OK / 7 CAUTELA** a **12 OK / 7 CAUTELA / 2 ALERTA** als quatre jocs de Castellar.

Concorda amb el diagnòstic 2026-08-23 (parcel·la equivocada a 4 dels 8 projectes). Bell-lloc no es mou: allà els
documents ja diuen els dos camps i la porta queda tancada tota sola — que és exactament el comportament que es volia.

**No s'esborra**: als projectes on el Cadastre encerta és l'única font d'aquests dos camps.
`G3DT_LECTURA_HTTP_SOURCES="icgc,geocodificacio,cadastre"` l'encén, `""` ho apaga tot, el defecte és `icgc,geocodificacio`.
Decisió d'encendre'l (potser per projecte, quan hi hagi la validació visual de parcel·la del treball P4): del Josep.

**Comparador d'or amb el defecte:** sortida idèntica a la base als 5 jocs (4 de Castellar + Bell-lloc), verdicte a verdicte.

---

## §8 — residus Groq a TEMPS 1: decisió presa (Josep, 2026-08-26)

**Mantenir els tres** (probes ConceptScout, `groq_miner`, ortofoto). Raonament amb què es va decidir:

- Amb 13(a) ja no es paguen a cada obertura, sinó **una vegada per projecte**. La palanca de latència que motivava
  treure'ls ha desaparegut.
- Són l'única font de ~15 camps de **grup B** (adjacents enriquits, descriptors visuals, prosa d'ortofoto) que el nivell
  A no cobreix, i l'objectiu és l'informe complet.
- Els valors dolents es tapen amb **precedència**, no esborrant la font.

Dels 69 prefills d'`auto_extract` a Castellar, 23 depenen de Groq. Tres tenen valor equivocat i convé tenir-los fitxats:

| camp | valor Groq | realitat | qui el tapa |
|---|---|---|---|
| `client_name` | `G3` | la lectura el té `segur` i correcte | `_apply_lectura_overlay` (verificat) |
| `superficie_parcela_m2` | `32980` (vision_probe) | l'Eva escriu 1.284 | **ningú avui**: la lectura diu `no_trobat` i l'overlay no escriu |
| `lab_company` | `Lab. Valdemoro` | el lab sempre és TPS (memòria `gtl_lab_identity`) | **ningú**: no és a `MAPPING_DECISIONS_WIZARD` |

Les dues últimes files són feina pendent, no d'aquesta fase.

---

## Guanys ocults

- El round-trip ha destapat que el comentari de `AutoExtractionResult.mining_alternatives` («var → `[Signal, ...]`») és
  **fals**: `auto_extractor.py` L.634 i L.748 hi posen dicts plans. Documentat i cobert amb test.
- La cache de 13(a) ha resultat ser **l'habilitador de 13(b)**: dona al consolidador un registre a disc, datat i
  validat per empremta, de les consultes HTTP — sense posar-hi xarxa ni dependre de l'ordre dels dos fils.
- La mesura ha convertit una fase que semblava «connectar el Cadastre» en una **troballa**: al projecte de referència
  el Cadastre no és una font de veritat per a la superfície de parcel·la.

---

## Addendum — capa vegetal (peça 3 del tram 1, `cef49ba`)

Fet just després, al mateix fitxer (`consolidate.py`). Al joc `sonnet-v2-c3` de Castellar, `soil_levels[0].de` i `.a`
sortien `no_trobat` tot i que la consolidació LLM del MATEIX joc les tenia.

**Causa.** La capa vegetal és «sense número a la llegenda». El `tall.pdf` la dibuixa sense fondàries i l'annex de sondeig
només numera el substrat → la fila primària `cover` no té interval. Les fondàries reals (0,00-0,50) són **només** al full
de camp, que les numera amb la seva pròpia numeració («1er nivell» = la capa vegetal, «2on nivell» = NIVELL 1 de l'Eva) —
i `level_key()` ignora a posta la numeració del full de camp. Sense interval amb què solapar, la fila 0,00-0,50 queia al
calaix `de{iv[0]}` i creava una **tercera fila espúria** mentre la capa vegetal es quedava buida.

**Regla nova, purament posicional:** si la capa vegetal no té fondàries de ningú, l'única fila que li'n pot donar és la
que arrenca a la superfície (≤ 5 cm). No dispara si el solapament ja ha trobat fila, ni si un document dona un nom de
nivell explícit, ni si la capa vegetal ja té interval. **No depèn de la regla del Pas 3b** sobre el `de` del nivell 1
(pregunta 3, pendent de l'Eva).

| joc | abans | després |
|---|---|---|
| `sonnet-v2-c3` TAULES | 26 OK · 1 CAUTELA · **2 ALERTA** | 25 OK · **4 CAUTELA · 0 ALERTA** |
| els altres 4 jocs | — | sense canvis |

La CAUTELA nova (`soil_levels[1].a`) no és un efecte secundari: en desaparèixer la fila espúria, NIVELL 1 passa a ser
l'últim nivell i s'hi aplica una regla del Pas 3b que ja existia («la base de l'últim nivell és el final del
reconeixement, no una transició»). El joc `sonnet-c3-v13` ja la tenia — els dos jocs de Castellar ara coincideixen.

**Comprovat i deixat obert:** l'ALERTA de Bell-lloc (`soil_levels[1].de = 0.00 segur`, un erroni-amb-confiança) **no és
del consolidador**. Cap document d'aquella lectura reporta la capa vegetal: l'annex emet una sola fila 0.00-1.80 amb la
litologia dels dos trams i l'or la parteix llegint la transició gràfica del log (−0,30 m ±0,05) i la primera frase de la
descripció. És un forat de **lectura**, i partir-la és exactament la regla del Pas 3b que espera la pregunta 3.

---

## Addendum (2026-08-31) — «no era la parcel·la equivocada: era un portal de tres»

La secció «Per què el Cadastre queda apagat» (dalt) diu que el Cadastre respon 441 m² per a Castellar mentre l'Eva
escriu 1.284, i ho llegeix com un error del Cadastre. **Re-analitzat amb mesura en viu (`PLA-PENDENTS-0B-0C-0D-2026-08-26.md`
§7.1, annex A):** el Cadastre no s'equivocava de parcel·la — l'adreça llegida és «Carrer Arbrells, **18A, 18B i 20**»
(tres portals), i 441 m² és la resposta CORRECTA per al portal 18A sol. L'Eva suma les tres parcel·les dels tres
portals que els documents anomenen: 441 + 423 + 420 = **1.284**, exacte. El «4 dels 8 projectes amb la parcel·la
equivocada» del diagnòstic 2026-08-23 era un bug diferent, al *matcher* de la via B (`_pick_nearest_rc_from_numerero`
traient la lletra del portal i triant el número més proper — Tulipa 3→11), no al Cadastre en si. Amb l'adreça de la
lectura (no la de la via B), el Cadastre coincideix amb l'Eva a 6 dels 7 projectes resolubles (annex A del pla).

**Fix D** (`automation/lectura/cadastre_reader.py`, commit `349ecca`) reemplaça el mecanisme vell (`_HTTP_FIELD_SOURCES`
llegint `_auto_result.json`, l'adreça equivocada) per un lector que llegeix `decided["street_address"]` de la LECTURA,
en parseja els portals, resol cada un per `(número, lletra)` EXACTE (mai el més proper) i suma només si les parcel·les
són contigües (`shapely.unary_union`), sempre com a `candidats`, mai `segur`. `_HTTP_SOURCES_DEFAULT` s'ha encès
(decisió del Josep 2026-08-31): `("icgc", "geocodificacio", "cadastre")`.

**Mesurat (harness, 2 passades):**

| passada | Castellar (×4 jocs) | Bell-lloc |
|---|---|---|
| Cadastre OFF explícit (`icgc,geocodificacio`) | idèntic al post-Fix-C: `referencia_catastral`/`superficie_parcela` absents del veredicte (cap font) | idèntic |
| Cadastre ON (defecte nou) | `referencia_catastral`/`superficie_parcela`: `no_trobat` → **`FORA`** (2 FORA cadascun; l'or porta `fora_carpeta` amb el valor 1.284 verificat) — **0 ALERTA nova** | intacte: `superficie_parcela` ja ve d'un document (995), el lector nou no es crida (porta tancada, `consolidate.py:1611-1616`) |

Detall complet, decisions arquitectòniques (per què `candidats` sempre, per què `areaValue` del WFS i no `shapely.area`,
per què no delegar el portal amb lletra) i evidència de l'API en viu: `docs/DECISION-LOG.md` (entrada 2026-08-31, Fix D)
i `docs/PLA-PENDENTS-0B-0C-0D-2026-08-26.md` §7 + Annex A/B.

---
*Fi Fase 13. TEMPS 1 deixa de repetir-se; el consolidador ja veu l'ICGC i la geocodificació; el Cadastre queda mesurat i apagat.*
