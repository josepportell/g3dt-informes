# Diagnòstic detallat de producció G3DT — temps, qualitat i models (2026-08-23)

**Branca:** `review/prod-audit-2026-08` a `c0b06fe` (fixes F1-F4e inclosos; `production/g3dt-eva-v1` intacta a `1f1d7fd`).
**Abast (confirmat amb el Josep avui):** temps (Gantt de fases), qualitat (prefills vs informes d'Eva), models (A/B Sonnet 5 vs 4.6).
**Fora d'abast:** estat real de l'ordinador de l'Eva (cap dada posterior al 23 jul; preguntes a AUDIT §6). **No s'ha implementat cap fix.**

## 0. Resum executiu

1. **Temps.** 8 obertures fredes reals (Tulipa + 7 de referència, mode xarxa, workspace i cache nous): **mitjana 300 s, rang 184-619 s**.
   El 47 % és la **visió per tipus en sèrie** (mitjana 140 s) i el 26 % les **probes de ConceptScout amb Groq** (mitjana 78 s).
   Tot el Python (SmartScan, FileMiner, càlculs) suma < 15 s. Amb els 5 tipus de visió, les probes i `deep_folder` en paral·lel
   (4 fils), l'estimació sobre els mateixos logs és **~160 s de mitjana** (295 → 162). Sense tocar cap model.
2. **Variància.** Groq `qwen3.6-27b` ha retornat **503 "over capacity" 8 cops en 8 obertures** (cada un = 30 s perduts, no ho
   controla el codi). Anciles ha trigat 619 s per un `sondeig` **truncat a 4.096 tokens** (F3 només va pujar `dpsh`) i 35 pàgines de
   plànols en **7 trossos en sèrie** (106 s).
3. **Qualitat.** Comparant 341 variables amb els informes signats d'Eva: **59 % MATCH+CLOSE** (125 MATCH, 44 CLOSE, 118 MISMATCH,
   54 sense camp/valor). Dels 118 MISMATCH, **41 són criteris de càlcul** (E, Qa, assentament, K30 — ja documentats com a judici
   professional d'Eva) i **77 són extracció**. Les causes d'extracció són poques i repetides: `client_name` = "G3" (3/8 projectes),
   parcel·la cadastral equivocada (4/8, el matcher accepta un altre número de carrer), `field_date` mai és la data de camp (7/8),
   `vision_probe` guanya a fonts fiables (adreça/municipi/idioma: Rubí en castellà), fallback del concept_map que envia fulls de
   camp a la visió de plànol/projecte (6/8 projectes, 4-16 s perduts cada un).
4. **Models.** A/B Sonnet 5 vs 4.6 (315 lectures N20 amb ground truth, 8 projectes): **empat de qualitat** (S5 +4 pp sense
   l'Excel, −8 pp amb l'Excel per un desplaçament de files; S5 gairebé mai marca "??"), **S5 un 35-45 % més ràpid**, mateix cost.
   No canviar ara: la palanca de temps és el paral·lelisme (−62 s) no el model (−15-25 s).
5. **Decisió que queda per al Josep:** fusionar F1-F4e (resolen crashes i la cadena DPSH) és independent de tot això; la latència
   estructural i la prioritat de fonts són dues sessions separades amb opcions a §5.

## 1. Mètode

- **Entorn:** WSL, servidor `python -m web` amb el flux de producció (mode xarxa: `POST /api/network/select` → sync a workspace →
  `/api/prefills` → `/api/generate` → copy-back). **Un servidor, un workspace i un `G3DT_CACHE_DIR` nous per projecte**
  (primera obertura, com l'Eva amb un projecte nou). Cap execució concurrent amb la suite de tests.
- **Proveïdors:** igual que a producció (`dpsh`/`sondeig`/`sondeig_annex` → Claude Sonnet 4.6; `planol`/`projecte` → gpt-4.1-mini;
  probes/Tier 3 → Groq), amb l'única diferència que Claude va per **OpenRouter** (`G3DT_LLM_PROVIDER=openrouter`, mateix model;
  la clau Anthropic de dev no té crèdit). Els temps de Claude per OpenRouter poden diferir lleugerament dels directes.
- **Projectes:** Tulipa real (`/mnt/c/claude/g3dt/projectes-debug/`) + els 7 de referència (`/mnt/c/claude/g3dt/projectes/`).
  A Castellar i Linyola s'han apartat caches vells (`validation/`, `file_mapping.json`, `user_data.json`) perquè fossin fredes
  (còpia a l'scratchpad). `reference-material/` només s'ha llegit.
- **Referència d'Eva:** `validation/eva_reference_values.json` dels 7 (extractor existent); Tulipa extreta avui del
  `3001706_TULIPA_INFORME_FIX.docx` real (42 variables, **fiabilitat baixa en algunes**: `municipality`="C.Tulipa Cerdanyola",
  `architect_company`="C/TULIPA 3" són errors de l'extractor, no d'Eva).
- **Eines noves (només lectura, a `scripts/`):**
  - `prefills_timeline.py RUN.log --prefills P.json --wall S` → Gantt per fases + crides HTTP per proveïdor + camps del wizard
    per fase (via `source` de cada prefill).
  - `compare_prefills_vs_eva.py --batch TAG=P.json:E.json …` → comparador amb **mapatge de claus** (`client`→`client_name`,
    `plantes`→`num_floors`, `superficie_parcela`→`superficie_cadastral_m2`…), normalitzadors (dates en català, etiquetes
    "Profunditat:", sumes "280+86", narrativa per similitud) i **causa probable** de cada MISMATCH segons la font.
  - `ab_vision_dpsh_sondeig.py run|score` → A/B de models amb prompts/renderitzat de producció i ground truth.
- **Evidència:** scratchpad de sessió `diag/<expedient>/{run.log,prefills.json,timeline.md}`, `diag/compare_all.md`, `diag/ab/`.
  No versionat (reproduïble amb §7).

## 2. Temps

### 2.1 Per fase, 8 obertures fredes (segons)

| projecte | SmartScan +T3 | FileMiner | groq_miner | **Probes** | deep_folder | auto_extract¹ | **Visió** | post-visió² | span | wall |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| Tulipa | 28 | 2 | 10 | 120 | 10 | 3 | 138 | 16 | 329 | 329 |
| Bell-lloc | 1 | 2 | 14 | 60 | 22 | 36 | 106 | 4 | 244 | 250 |
| Rubí | 7 | 1 | 5 | 24 | 12 | 0 | 111 | 25 | 186 | 192 |
| Castellar | 3 | 1 | 8 | 35 | 20 | 51 | 147 | 5 | 269 | 275 |
| Linyola | 5 | 17 | 3 | 104 | 22 | 39 | 115 | 0 | 303 | 309 |
| Alcoletge | 2 | 2 | 5 | 69 | 9 | 34 | 55 | 5 | 181 | 184 |
| Vilanova | 13 | 4 | 12 | 56 | 15 | 41 | 96 | 0 | 238 | 243 |
| Anciles | 3 | 11 | 23 | 153 | 26 | 46 | 351 | 0 | 612 | 619 |
| **mitjana** | 8 | 5 | 10 | **78** | 17 | 31 | **140** | 7 | **295** | **300** |
| **% del span** | 3 % | 2 % | 3 % | **26 %** | 6 % | 11 % | **47 %** | 2 % | 100 % | |

¹ Lab PDF + ICGC + geocode + Cadastre adjacents + `parcel_resolver` + `ortho_enrichment` (5-6 crides Groq de visió d'ortofoto).
² Adjacents des de l'adreça del plànol + síntesi LLM (1 crida Claude). *wall* = `/api/prefills` mesurat per `curl`; *span* = log.
Informe (`/api/generate`): 2-35 s, 8/8 OK, 0 tracebacks.

**Lectura:** el que paga l'Eva és **latència de models en sèrie**, no Python. Dues fases fan el 73 % del temps: la visió per
tipus (5 crides en sèrie, una d'elles de 40-90 s) i les probes de ConceptScout (13-23 crides Groq en sèrie, 1,3-7,2 s cadascuna).

### 2.2 Visió per tipus: on van els 140 s

| projecte | en sèrie (s) | per tipus (s) | si fos paral·lel = màx | estalvi |
|---|--:|---|--:|--:|
| Tulipa | 121 | dpsh 70 · sondeig 16 · annex 25 · plànol 6 · projecte 4 | 70 | 51 |
| Bell-lloc | 86 | plànol 11 · annex 20 · dpsh 30 · sondeig 21 · projecte 4 | 30 | 57 |
| Rubí | 100 | dpsh 55 · plànol 5 · annex 36 · projecte 4 | 55 | 45 |
| Castellar | 126 | annex 18 · dpsh 41 · sondeig 51 · plànol 8 · projecte 8 | 51 | 75 |
| Linyola | 88 | projecte 33 (3 trossos) · dpsh 42 · plànol 5 · annex 7 | 42 | 45 |
| Alcoletge | 46 | plànol 4 · dpsh 38 · projecte 4 | 38 | 8 |
| Vilanova | 77 | dpsh 51 · plànol 6 · annex 16 · projecte 5 | 51 | 26 |
| Anciles | 282 | plànol 10 · annex 29 · **dpsh 91** · **sondeig 45 (FAIL, truncat)** · **projecte 106 (7 trossos)** | 91 | 191 |

- La diferència entre "en sèrie" i la durada de la fase (p. ex. Tulipa 121 vs 138) és **renderitzat de PDF a JPEG 200 dpi**
  (CPU, 5-20 s per projecte; a l'ordinador de l'Eva pot ser diferent).
- **`dpsh` és sempre la crida més llarga (30-91 s)** perquè genera 4-9k tokens de sortida (una lectura per cada 20 cm, amb
  `confidence`, `note`, `torque`, `water_indicator`). El prompt de producció **inclou els N20 de l'Excel** ("EXCEL COMPARISON
  DATA"): la visió DPSH és una *comparació*, no una lectura independent (vegeu §4).
- **El camí de producció és seqüencial per decisió de codi**, no per limitació: `run_vision_groq_sync()` ("Run tasks
  sequentially (better for progress tracking and rate limits)"), mentre que el camí de fons `_run_vision_groq()` ja usa
  `ThreadPoolExecutor(max_workers=3)`. Els 5 tipus són independents i van a 2 proveïdors diferents.
- **`sondeig` s'ha truncat a Anciles** (4.096 tokens, 9.773 caràcters, `stop_reason=max_tokens`): F3 va pujar `dpsh` a 16k però
  `sondeig` continua al valor per defecte; a Anciles el "sondeig" és el mateix `PENETROS + SONDEIGS.pdf` de 5 pàgines (el
  model descriu també els DPSH). Linyola: truncament equivalent a Groq (`finish_reason=length`) en una probe. La regla F3
  ("truncament → la cadena s'atura") ha funcionat: 45 s perduts, no 3 × 45.
- **`projecte_arquitecte` sobre documents llargs es trosseja en sèrie**: Anciles 35 pàgines → 7 crides × 13-19 s = 106 s;
  Linyola 11 pàgines → 3 crides = 33 s. Els trossos són independents.

### 2.3 Probes de ConceptScout (Groq): 78 s de mitjana i la font de la variància

| | Tulipa | Bell-lloc | Rubí | Castellar | Linyola | Alcoletge | Vilanova | Anciles |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| fitxers a la probe | 23 | 15 | 19 | 19 | 21 | 13 | 16 | 20 |
| s per probe | 4,8 | 3,9 | 1,3 | 1,7 | 4,6 | 4,9 | 3,4 | 7,2 |
| Groq **503** | 2 | 1 | 0 | 1 | 2 | 1 | 1 | 0 |

- Una probe Groq "sana" triga 1,3-2,5 s. La mitjana puja a 4-7 s per **HTTP 503 "qwen/qwen3.6-27b is currently over capacity"**:
  Groq manté la connexió **~30 s** abans de respondre el 503 (és el seu servidor, no un timeout nostre), i després el codi
  reintenta amb backoff. **8 × 503 en 8 obertures = ~4-5 min perduts en total**, i és el factor que explica que Tulipa avui
  trigui 329 s i ahir 273 (mateix codi, mateix projecte). Groq gratuït no té SLA; el 429 (rate limit) que dominava els logs
  de l'Eva ha desaparegut amb F4, però el 503 és una altra cara del mateix risc.
- Les probes omplen **6-14 camps** per projecte, però són també la font dels errors de §3.2 (adreça/municipi/client des de fotos).

### 2.4 Altres pèrdues petites però sistemàtiques

- **Geocodificació i adjacents duplicats**: a 6/8 projectes el log mostra "Probing north/south/east/west" **dues vegades**
  (validació de coordenades + fallback d'adjacents amb la mateixa adreça), i Nominatim/CartoCiudad/Cadastre consultats dues
  vegades: ~10-15 s per obertura.
- **`deep_folder_classify`**: 5-15 crides gpt-4.1-mini en sèrie, 7-26 s. Independents entre si.
- **Fallback del concept_map cap a fitxers equivocats** (detall a §3.3): cada un és una crida de visió inútil (4-8 s; a Castellar
  `planol` + `projecte` sobre el PENETROS, 16 s; a Linyola un `sondeig_annex` sobre una imatge del projecte d'arquitecte).

### 2.5 Quants camps hi ha abans de la visió

Els prefills porten la font de cada camp; agrupant-les per fase:

| projecte | camps | disponibles **abans** de la visió (text, probes, Python, geocode, càlculs, defaults) | visió per tipus | síntesi LLM | % abans de la visió |
|---|--:|--:|--:|--:|--:|
| Tulipa | 72 | 59 | 6 | 7 | 82 % |
| Bell-lloc | 108 | 84 | 20 | 4 | 78 % |
| Rubí | 85 | 65 | 11 | 9 | 76 % |
| Castellar | 95 | 85 | 6 | 4 | 89 % |
| Linyola | 95 | 80 | 11 | 4 | 84 % |
| Alcoletge | 86 | 74 | 7 | 5 | 86 % |
| Vilanova | 85 | 71 | 9 | 5 | 84 % |
| Anciles | 87 | 66 | 16 | 5 | 76 % |

**~80 % dels camps existeixen al segon ~100-190 (abans de la visió)**; els que aporta la visió són pocs però importants (nivells
geològics, cota, SPT, plantes, superfícies del plànol) i la síntesi LLM en depèn. El "mostra els prefills bàsics i completa en
segon pla" de l'AUDIT §3.2 és viable: l'Eva veuria el wizard en ~1,5-3 min en lloc de 3-10, amb els camps de visió arribant
després (el wizard ja té SSE: `/api/prefills-stream`).

### 2.6 Estimació si es paral·lelitza (mateixos logs, sense canviar models)

| projecte | span actual | estalvi visió paral·lela | probes /4 | deep_folder /4 | **span estimat** |
|---|--:|--:|--:|--:|--:|
| Tulipa | 329 | 51 | 90 | 7 | **181** |
| Bell-lloc | 244 | 57 | 45 | 17 | **126** |
| Rubí | 186 | 45 | 18 | 9 | **115** |
| Castellar | 269 | 75 | 26 | 15 | **153** |
| Linyola | 303 | 45 | 78 | 17 | **164** |
| Alcoletge | 181 | 8 | 52 | 7 | **114** |
| Vilanova | 238 | 26 | 42 | 11 | **158** |
| Anciles | 612 | 191 | 115 | 19 | **286** |
| **mitjana** | **295** | | | | **162** |

Supòsits: visió = màxim dels tipus (trossos inclosos); probes i `deep_folder` amb 4 fils i sense rate limit (Groq gratuït:
risc real de 429 → cal el pressupost F4 i fallback immediat a OpenAI). No inclou arreglar els 503 (−30 s cadascun), els
truncaments, ni els fallbacks a fitxers equivocats. **No és un pla, és el sostre del que dona la concurrència sola.**

## 3. Qualitat: prefills vs informes signats d'Eva

### 3.1 Agregat (341 variables, 8 projectes)

| projecte | vars | MATCH | CLOSE | MISMATCH | sense valor | sense camp | encert (M+C)/comparables |
|---|--:|--:|--:|--:|--:|--:|--:|
| Tulipa¹ | 34 | 10 | 2 | 14 | 1 | 7 | 46 % |
| Bell-lloc | 48 | 31 | 4 | 12 | 1 | 0 | 74 % |
| Rubí | 43 | 16 | 9 | 17 | 0 | 1 | 60 % |
| Castellar | 48 | 22 | 4 | 11 | 1 | 10 | 70 % |
| Linyola | 46 | 21 | 8 | 15 | 2 | 0 | 66 % |
| Alcoletge | 40 | 11 | 6 | 13 | 1 | 9 | 57 % |
| Vilanova | 42 | 7 | 4 | 18 | 1 | 12 | 38 % |
| Anciles | 40 | 7 | 7 | 18 | 1 | 7 | 44 % |
| **total** | **341** | **125** | **44** | **118** | 8 | 46 | **59 %** |

¹ Referència de Tulipa amb soroll (§1). "Sense camp" = el wizard no té cap camp equivalent (lab_*, spt_* quan no hi ha laboratori
o SPT; `superficie_construida` a 4 projectes).

### 3.2 Els 118 MISMATCH per causa

| causa | n | què és |
|---|--:|---|
| **càlcul (criteri ≠ Eva)** | 41 | E (6/8), Qa (6/8), assentament (7/8), K30 (3/3), φ (3/8), `cte_sol` (3/8), `table_dpsh_range` (5/8), `building_structure_desc`. Conegut i documentat (memòria `implementation_status_calcs`, `docs/METODOLOGIA-EVA.md`): Eva aplica judici (E=650 per graves carbonatades, Qa 3,0-3,5 per sobre del cap) i el wizard té camps d'override. **No és regressió ni extracció.** |
| **visió per tipus** | 19 | `client`/`architect_name`/`building_type` quan el plànol no és un plànol (§3.3); `spt_n30` 54→58 i 5→? (lectura); `superficie_construida`; `cota_referencia` Castellar (−4,0 vs +570,90: Eva usa cota relativa, el wizard l'absoluta del sondeig). |
| **narrativa LLM** | 17 | adjacents i `location_sentence` redactats diferent (4 a Rubí **en castellà**); `building_structure_desc`. |
| **font foto/probe (`vision_probe`)** | 9 | `client`="G 3"/"G3" (Tulipa, Rubí), `municipality` "Població: Cerdanyola" (etiqueta filtrada) / "Sant Quirze del Vallès" (foto d'ubicació, Rubí) / Vilanova, `building_type` "VIVIENDAS MODULARES" (foto WhatsApp), `plantes` Anciles. |
| **narrativa ortho+visió (ICGC)** | 9 | `site_description` 7/7 i `location_sentence`: el text generat des de l'ortofoto no coincideix amb el d'Eva (redacció lliure; similitud < 0,6). |
| **geocode / Cadastre** | 8 | `superficie_parcela` 4 (parcel·la equivocada, §3.3), `radon_zone` 2, `seismic_ab` 2 (Rubí: Eva 0,08 amb confiança 0,28 de l'extractor; taula NCSE-02 diu 0,04 — probablement soroll de referència). |
| **extracció text (fileminer/groq/docs)** | 7 | `field_date` (data del GTL o del pressupost, no de camp), `building_type` "CONSTR 3 HAB UNIF" (comanda laboratori), `municipality`. |
| **extracció Lab (Python)** | 6 | `lab_tests_text` = "Data obertura: DADES INICIALS…" (agafa la capçalera del GTL, no la llista d'assaigs); `field_date`. |
| no extret (default) | 2 | `access_street`, `sulfate_level_name` (Linyola: 2n nivell). |

**Per variable, el que falla a gairebé tots els projectes** (MISMATCH/8): `field_date` 7, `site_description` 7, `settlement` 7,
`building_structure_desc` 7, `building_type` 7, `geomech_E` 6, `qa_value` 6, `client` 5, `municipality` 5, `superficie_parcela` 5,
`table_dpsh_range` 5. **El que va bé**: `expedient` 8/8, `cota_referencia` 7/8, `num_dpsh_tests` 7/8, `radon_zone` 6/8,
`seismic_ab` 6/8, `cte_edificacio` 6/8, lab companyia 6/6, `lab_depth`/`lab_location`/`lab_sample_id` 4/4 quan hi ha camp,
`utm` 4/4, `geomech_gamma` 8/8 (M+C).

### 3.3 Troballes concretes (amb evidència al log), per impacte

**Q1. `client_name` = "G3" a 3/8 projectes (Tulipa, Rubí, Castellar).** La font és el full de camp (`PENETROS…`), on "G3" és la
capçalera de l'empresa. `competition.py` exclou NIFs de proveïdor (`is_non_client_nif`, fix `ad3a369`) i adreces internes de G3,
però **no exclou el nom de G3 com a client**. A Castellar ve via `planol` perquè el "plànol" era el PENETROS (Q3). Afecta
portada i narrativa.

**Q2. Parcel·la cadastral equivocada a 4/8 (`superficie_parcela` MISMATCH a 5/8: 4 via Cadastre + Anciles via plànol; UTM, adjacents i ortofoto derivats).**
`geocode_coordinates.py:2341`: el candidat del Cadastre s'accepta si `overlap > 0.3` de paraules entre l'adreça buscada i la
del Cadastre. Tulipa: "C/TULIPA 3" → acceptat **"CL TULIPA 11"** (score 0,33: coincideix "tulipa", no el número) → 759 m² en lloc
de 564, adjacents d'una altra parcel·la, i l'informe surt amb "No UTM coordinates" + 3 placeholders d'imatge. Rubí: 222 m² vs 951
(l'adreça ja era falsa, Q4). Castellar 441 vs 1.284; Vilanova. Bell-lloc és el cas bo (score 0,71 + `parcel_resolver` fusiona
2 parcel·les fins a 1.012 m² ≈ 995 del plànol).

**Q3. El fallback del concept_map envia fulls de camp o fotos a la visió de plànol/projecte/annex (6/8 projectes; Alcoletge i Anciles són correctes).**
`vision_groq._supplement_from_concept_map()` tria "el fitxer amb més conceptes de plànol" sense mirar el rol SmartScan del
fitxer. Resultat: `projecte_arquitecte` sobre `PENETROS + SONDEIG_img3.jpeg` (Tulipa), sobre `PENETROS.pdf` (Bell-lloc), sobre
una foto WhatsApp (Rubí, Vilanova); `planol` + `projecte` sobre `PENETROS + SONDEIG.pdf` (Castellar, 16 s); `sondeig_annex`
sobre una imatge del projecte d'arquitecte (Linyola) o una foto WhatsApp (Vilanova). Cost: 4-106 s i **camps d'identitat
contaminats** (Q1 a Castellar, `architect_name` "JOSEP BUNYESC PALACÍN - Dr. Arquitecte" vs "Bunyesc Arquitectura Eficient").

**Q4. `vision_probe` guanya a fonts fiables per a adreça/municipi/client/tipus.** Rubí: `street_address` "Calle Juan Coloma
Fajardo 41A" (foto WhatsApp d'ACCEPTACIO) i `municipality` "Sant Quirze del Vallès" (`F1 UBI.png`) → `_get_project_language()`
detecta castellà → **4 adjacents + `site_description` + `location_sentence` en castellà** i la parcel·la de Q2. Tulipa:
`municipality` = "Població: Cerdanyola" (el valor porta l'etiqueta del full de camp). Vilanova i Anciles: `building_type`/`plantes`
des de fotos. `auto_extractor.py:1120-1160` només bloqueja `vision_probe` per a adreces internes de G3; per a la resta, si la
probe "guanya" la competició, s'imposa. És el F6 proposat ahir (PLA §7).

**Q5. `field_date` no és mai la data de camp (7/8).** Fonts: `4677-GTL-25….pdf` (data del laboratori), pressupost, `tall.pdf`
("Febrer 2026"), projecte d'arquitecte ("AGOST 2025"). Eva la posa del full de camp. El DPSH Excel i el PENETROS (Tulipa: "Data:
7-5-2026" via probe, amb etiqueta) la tenen; el concepte `field_date` no prioritza aquestes fonts.

**Q6. `has_basement` / `building_structure_desc` (7/8 MISMATCH).** Bell-lloc: "amb nivell de soterrani" (Eva: "en planta baixa");
Anciles `has_basement` = "BAJO CUBIERTA". El camp computat depèn d'una extracció poc fiable del plànol i condiciona el paràgraf
d'empentes.

**Q7. `cota_referencia` Castellar: +570,90 (sondeig `elevation_z`) vs −4,0 (Eva).** Eva usa cota relativa al plànol quan el
projecte ho demana; el `report_generator` sobreescriu amb l'absoluta del sondeig ("Overrode cota_referencia… from sondeig
elevation_z"). 1/8; els altres 7 coincideixen.

**Q8. Lectura de l'SPT al sondeig manuscrit:** Bell-lloc `spt_n30` 54 → 58 i `spt_lithology` "Graves en matriu sorrenca" →
"Graves carbonatades"; Anciles igual. És l'únic lloc on la *qualitat de lectura* del model (no la selecció de fitxer) explica un
MISMATCH → objecte de l'A/B (§4).

**Q9. (No és una troballa de producció, però cal saber-ho.)** Els 8 informes d'aquest diagnòstic porten 2-4 placeholders
d'imatge i "No UTM coordinates available": `/api/generate` llegeix `user_data.json`, que només existeix quan l'Eva prem
"Guardar" al wizard; aquí s'ha generat sense desar. En el flux real de l'Eva les UTM dels prefills arriben al `.docx` via
`user_data.json`. Generar sense desar produeix un informe degradat **en silenci** (cap avís al wizard).

### 3.4 Què NO s'ha mesurat

- Fidelitat de les taules (`dpsh_tests`, `geotech_rows`, `soil_level_rows`) i dels nivells geològics vs Eva (llistes; el
  comparador les omet). L'A/B de §4 cobreix N20 i nivells del sondeig.
- Narrativa: la similitud textual penalitza redaccions diferents però correctes (`site_description`). Caldria judici humà o
  LLM-jutge (`compare_benchmarks.compare_text_llm` existeix).
- Els 19 projectes reals de l'Eva: només en tenim Tulipa. El 59 % és sobre el corpus de 2025 + Tulipa.

## 4. Models: A/B Sonnet 5 vs Sonnet 4.6 a `dpsh` i `sondeig`

**Muntatge:** 8 projectes, **prompts, renderitzat (200 dpi, ≤5 pàgines) i pressupost de tokens de producció**; tots dos models per
OpenRouter (`anthropic/claude-sonnet-4.6` tal com a prod; `anthropic/claude-sonnet-5` amb `thinking` desactivat, sense
sampling params). `dpsh` en dues condicions: **`xl`** = prompt de producció (inclou "EXCEL COMPARISON DATA" amb els N20) i
**`raw`** = sense l'Excel (lectura real del manuscrit). Ground truth: **315 lectures N20 de 26 assaigs** (Excel DPSH); cota de
rebuig de l'Excel (arrodonida a la graella de 0,2 m — **no és una referència justa** per a la "R 1,35" manuscrita, els
"rebuig ok" són orientatius). `sondeig`: només els 4 projectes amb full de camp manuscrit; referència = informe d'Eva.
Scorer: `scripts/ab_vision_dpsh_sondeig.py score`; sortida completa a l'scratchpad `diag/ab/score.md`. Cost total: 2,6 $.

### 4.1 DPSH (agregat, 8 crides per cel·la)

| condició | model | lectures = GT | ≠ | "??" (il·legible) | no trobades | rebuig ≈ Excel | **s mediana** | s total | $ |
|---|---|--:|--:|--:|--:|--:|--:|--:|--:|
| raw (sense Excel) | Sonnet 4.6 | 269 (85,4 %) | 29 | **17** | 0 | 13/26 | 40,1 | 369 | 0,63 |
| raw (sense Excel) | Sonnet 5 | **283 (89,8 %)** | 29 | 1 | 2 | 14/26 | **29,8** | 255 | 0,62 |
| xl (prod, amb Excel) | Sonnet 4.6 | **314 (99,7 %)** | 1 | 0 | 0 | 20/26 | 49,1 | 404 | 0,72 |
| xl (prod, amb Excel) | Sonnet 5 | 288 (91,4 %) | 27 | 0 | 0 | 16/26 | **27,2** | 248 | 0,67 |

Per projecte (raw, = GT): Tulipa 28/28 vs 28/28 · Bell-lloc **0/18 vs 18/18** (4.6 retorna `n20: null` a totes les lectures de
P-1 i P-2) · Rubí 51/54 vs 54/54 · Castellar 14/17 vs 13/17 · Linyola 29/32 vs 30/32 · Alcoletge 18/23 vs 22/23 · Vilanova
27/35 vs **15/35** (P-3 manuscrit difícil: S5 16 errors, 4.6 7 errors + 2 "??") · Anciles 102/108 vs 103/108.
Amb l'Excel al prompt (xl): 4.6 copia l'Excel (314/315); **Sonnet 5 a Anciles desplaça una fila** els N20 de P-1 i P-3
(26 "errors" = els valors de la fila següent), tot i tenir l'Excel al prompt.

### 4.2 Sondeig (4 projectes; mostra massa petita per decidir)

| projecte | model | profunditat | cota | nivells geol. | N SPT | rang SPT | s |
|---|---|---|---|---|---|---|--:|
| Bell-lloc | 4.6 / 5 | ✅ 1,8 / ✅ | ❌ cap (el full manuscrit no porta cota; prod la treu de l'annex) | ✅ 1 / ✅ 1 | ❌ 54→58 / ❌ 54→62 | ✅ / ✅ | 21,6 / 18,1 |
| Castellar | 4.6 / 5 | ✅ 1,2 / ✅ | ❌ / ❌ | ✅ 1 / ✅ 1 | — | ❌ / ❌ | **57,8 / 19,8** |
| Anciles | 4.6 / 5 | **truncat 4.096 tok** / ❌ 2,4→2,5 | — / ❌ | — / ✅ | — / ✅ 6 | — / ✅ | 44,0 (FAIL) / 22,6 |
| Tulipa | — | referència d'Eva sense `sondeig_tests` (extractor): no comptable | | | | | 14,1 / 13,5 |

### 4.3 Conclusions

1. **Qualitat: empat amb matisos, no hi ha un guanyador clar.** Sense l'Excel, Sonnet 5 llegeix millor (+4,4 pp, i no té el
   col·lapse de Bell-lloc), però **gairebé mai marca "??"** (1 vs 17): decideix en lloc d'avisar, que és el contrari del que vol
   la pestanya DPSH de revisió. Amb l'Excel (el cas de producció), 4.6 és més fiable (un desplaçament de files a Anciles amb S5).
   A Vilanova tots dos fallen al mateix full.
2. **Latència: Sonnet 5 és un 35-45 % més ràpid** a la mateixa crida (mediana 27-30 s vs 40-49 s) amb tokens de sortida i cost
   iguals (≈ 0,08 $/crida). Sobre el camí crític actual (dpsh en sèrie) són **−15 a −25 s per obertura**; O1 (paral·lel) en
   treu −62 de mitjana sense canviar de model.
3. **El valor de la visió DPSH a producció és la validació i les cotes de rebuig**, no els N20 (ja venen de l'Excel). Les cotes
   de rebuig coincideixen amb l'Excel 20/26 (4.6 xl); les 6 restants són precisament on l'anotació manuscrita "R x,xx" és més
   precisa que la graella de l'Excel — no es pot jutjar sense mirar el full.
4. **Sondeig manuscrit: cap dels dos llegeix bé l'N SPT** (54 → 58/62) ni la cota (no hi és). El truncament de 4.6 a Anciles
   és el mateix d'§2.2 (O4). Sonnet 5 és 3× més ràpid a Castellar (58 → 20 s) sense perdre res.
5. **Recomanació: no canviar de model ara.** Si després d'O1 el `dpsh` continua sent el camí crític, provar Sonnet 5 **només a
   `dpsh`** amb (a) un test de desplaçament de files (Anciles) i (b) el prompt reforçat per a "??" — i mantenir 4.6 a `sondeig`.
   GPT-5.6 Luna i Opus 4.7 no s'han provat aquí (fora d'abast; l'harness els accepta: `--models o47,h45`).

## 5. Opcions, amb cost i benefici (res implementat)

| # | Opció | Benefici mesurat/estimat | Cost | Risc |
|---|---|---|---|---|
| O1 | **Visió per tipus en paral·lel** (reutilitzar el `ThreadPoolExecutor(3)` que ja té `_run_vision_groq`, mantenint el progrés SSE) | −8 a −191 s/obertura (mitjana −62 s) | 1 sessió curta; tests existents de `vision_groq` | baix: 2 proveïdors, 5 crides |
| O2 | **Probes ConceptScout amb 4 fils + fallback immediat a OpenAI en 503** (sense esperar els 30 s de Groq) | −18 a −115 s (mitjana −57 s) + elimina la variància dels 503 | mitjà: `vision_probe` + pressupost 429 de F4 | Groq gratuït pot respondre 429 en ràfega → el fallback ha de ser barat (gpt-4.1-mini ≈ 0,3 ¢/probe) |
| O3 | **Prefills bàsics primer, visió en segon pla** (el wizard ja té SSE) | l'Eva veu el ~80 % dels camps al minut 1,5-3 | alt: ordre de `get_prefills_streaming` + merge diferit + UI | mitjà: camps que canvien després de mostrar-se |
| O4 | `MAX_TOKENS_BY_TYPE["sondeig"/"sondeig_annex"] = 8-16k` | evita truncaments (Anciles −45 s i recupera el sondeig) | 1 línia + test | cap |
| O5 | **Fallback concept_map: excloure fitxers amb rol `dpsh_*`/`sondeig_*`/fotos per a `planol`/`projecte`**, i no executar `projecte_arquitecte` sobre fulls de camp | −4 a −106 s i tanca Q1-Castellar, Q3 | petit: `_supplement_from_concept_map` + tests | baix |
| O6 | `client_name`: excloure "G3"/"G 3"/"G3 GEOTÈCNIA" com s'exclou el NIF | tanca Q1 (3/8) | 5 línies a `competition.py` | cap |
| O7 | Cadastre: exigir número de carrer coincident (o score ≥ 0,6) abans d'acceptar la parcel·la; si no, cap UTM en lloc d'una UTM falsa | tanca Q2 (4/8): superfície, adjacents, ortofoto | petit: `geocode_coordinates.py:2341` + test amb Tulipa | pot deixar més projectes "sense UTM" (millor que una UTM equivocada; el wizard té botó Geolocalitzar) |
| O8 | `vision_probe` no pot guanyar `street_address`/`municipality`/`client_name`/`building_type` si existeix una font de text o plànol (F6 d'ahir) + camp d'idioma al wizard | tanca Q4 (Rubí castellà, Tulipa "Població:") | mitjà: `auto_extractor` merge + schema `report_variables.yaml` | decisió de prioritats per concepte (memòria `concept_format_per_concept_priority`) |
| O9 | `field_date`: prioritzar DPSH Excel / full de camp sobre GTL / pressupost | tanca Q5 (7/8) | petit: prioritats del concepte | cap |
| O10 | Dedupe geocode+adjacents (cache per adreça dins l'obertura) | −10-15 s | petit | cap |
| O11 | Sonnet 5 a `dpsh` (després d'O1, amb test de desplaçament de files) | −15-25 s/obertura; qualitat ≈ | 1 línia `.env` + A/B | S5 no marca "??"; desplaçament de files vist a Anciles |

Ordre que suggereixo si el Josep vol una sessió de "latència": O4 + O1 + O2 (un dia, mesurable amb els mateixos 8 logs). Una
sessió de "fonts": O6 + O7 + O5 + O9 + O8. O3 és la que canvia l'experiència de l'Eva però és la més gran.

## 6. Decisions per al Josep

1. Fusionar `review/prod-audit-2026-08` (F1-F4e) a prod i pull a l'Eva — **independent** de tot el d'aquest document; sense
   això la cadena DPSH segueix trencada al seu ordinador (92 % FAIL).
2. Sessió de latència (O1, O2, O4) abans o després de la sessió de fonts (O5-O9)?
3. O3 (prefills progressius): sí/no. És l'única opció que canvia "esperar 5 min" per "esperar 2 i anar veient".
4. Model de visió per a `dpsh`/`sondeig` segons §4.
5. Demanar a l'Eva el `g3dt.log.txt` i 2-3 carpetes recents (AUDIT §6) — sense això, tot el de dalt és sobre corpus de 2025 + Tulipa.

## 7. Reproduir

```bash
cd ~/projects/claudecode-job/clients/g3dt-prod
# 1 obertura freda (servidor nou, workspace i cache nous) — vegeu docs/_FOR-NEW-YOU-20260823.md §5 per a la seqüència
python3 scripts/prefills_timeline.py RUN.log --prefills prefills.json --wall <segons de curl>
python3 scripts/compare_prefills_vs_eva.py --batch "Tulipa=prefills.json:<…>/validation/eva_reference_values.json" …
set -a; . ./.env; set +a
.venv/bin/python scripts/ab_vision_dpsh_sondeig.py run   --out AB_DIR <workspace del projecte>…
.venv/bin/python scripts/ab_vision_dpsh_sondeig.py score --out AB_DIR <workspace del projecte>…
```

Referència de Tulipa: `python -m automation.reference_extractor "<còpia>/3001706_TULIPA_INFORME_FIX.docx"` (escriu a la còpia,
no a `reference-material/`). Caches apartats de Castellar/Linyola: scratchpad `stale-cache-backup/` (restaurar amb `mv` si cal).
