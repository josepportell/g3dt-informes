# Registre de verificacions del pipeline

**Creat:** 2026-04-10
**Objectiu:** Document viu que recopila troballes verificades i hipòtesis pendents.
Permet confiar en els passos validats i enfocar investigacions en els que falten.

---

## Troballes VERIFICADES (podem confiar-hi)

### V01. Vision del plànol extreu building_type correctament (7/7 projectes)
- **Evidència:** `planol_extracted.json` verificat per tots 7 projectes
- **Detall:** Vision llegeix el caixetí literalment. El valor és fidel al PDF.
- **Matís:** "aïllat" al plànol Bell-Lloc és real (no inventat). Eva l'omet per estil.
- **Traça:** `docs/taller/traca-building-type/TRACA-COMPLETA-BUILDING-TYPE.md` §8.2

### V02. LLM synthesis sobreescriu 4 variables (building_type, architect, client, location)
- **Evidència:** `_set()` (wizard_service.py:717-722) només protegeix source="user"
- **Impacte real:** Sovint el valor no canvia (synthesis rep vision com input). Però
  perd traçabilitat (source passa de "planol_vision" a "llm_synthesis").
- **Model:** claude-sonnet-4-6 — model capaç, el problema no és d'intel·ligència
- **Traça:** `docs/taller/traca-building-type/PLA-VERIFICACIO-HIPOTESIS.md` V4

### V03. FileMiner senyals incorrectes per building_type (label "OBRA")
- **Evidència:** 6 senyals amb concept_id=building_type, cap coincideix amb Eva
- **Causa arrel:** L'etiqueta "OBRA" al pressupost captura l'adreça del projecte,
  no el tipus d'edificació
- **Traça:** `docs/taller/traca-building-type/TRACA-COMPLETA-BUILDING-TYPE.md` §2, §4

### V04. 48/65 conceptes sense format mapping (74%)
- **Evidència:** Script d'audit (report_variables.yaml vs schemas/formats/*.yaml)
- **Desglòs:** ~29 no ho necessiten (computed, API, user-only), ~19 SÍ ho necessiten
- **Més impactants:** 8 lab_*, 4 adjacents, 4 building group
- **Traça:** `docs/taller/traca-building-type/TRACA-COMPLETA-BUILDING-TYPE.md` §0.2

### V05. Format learning 0% per plànol (no compta vision)
- **Evidència:** FileMiner extreu 0/10 expected fields d'A.01.pdf (només phone+email)
- **Causa:** format_learner mesura cobertura de FileMiner regex, no del pipeline total
- **Implicació:** Banner ambar al wizard és enganyós per plànols (vision sí extreu bé)
- **Traça:** `docs/taller/traca-building-type/PLA-VERIFICACIO-HIPOTESIS.md` V2

### V06. Alcoletge "ampliació" és als fitxers (noms d'email)
- **Evidència:** grep + FileMiner: 14 senyals amb "Ampliació" al nom del fitxer,
  totes amb concept=None
- **Causa:** No hi ha miner per extreure senyals dels noms de fitxer/email
- **Traça:** `docs/taller/traca-building-type/PLA-VERIFICACIO-HIPOTESIS.md` V3

### V07. Probe d'adjacents salta carrers estrets (sqrt(sup.) sobreestima)
- **Evidència:** Bell-Lloc sud, probe a 16m: aterra directament en parcel·la veïna,
  cap NULL zone (carrer) detectada
- **Causa:** half_side = sqrt(905)/2 = 15m assumeix parcel·la quadrada.
  Si és rectangular allargada, el costat curt pot ser << 15m
- **Traça:** `docs/taller/traca-adjacents/TRACA-COMPLETA-ADJACENTS.md` H1

### V08. DNPRC no retorna plantes → descripció genèrica
- **Evidència:** Bell-Lloc oest: raw = "parcel·la amb construcció" (floors=0 fallback)
- **Eva diu:** "construcció aïllada de fins a dos plantes sobre rasant"
- **Causa:** DNPRC API retorna floors_above=0 o no el camp
- **Traça:** `docs/taller/traca-adjacents/TRACA-COMPLETA-ADJACENTS.md` H2

### V09. Adjacent formatter funciona correctament
- **Evidència:** Tots els articles (el/la/una/un), prefixes, i language detection correctes
- **Matís menor:** Falta coma al west ("per la part oest amb" vs "per la part oest, amb")
- **Traça:** `docs/taller/traca-adjacents/TRACA-COMPLETA-ADJACENTS.md` §3

### V10. Diagnostic no usa LLM judge → sobrevalora MISMATCH
- **Evidència:** compare_benchmarks.py té _llm_judge_text() (Haiku, amb cache),
  diagnostic_trace.py usa compare_text() (string matching pur)
- **Impacte:** 129 MISMATCH inclou falsos positius (ex: "un habitatge unifamiliar aïllat"
  vs "un nou habitatge unifamiliar" → MISMATCH per strings, CLOSE per semàntica)
- **Traça:** `docs/taller/traca-building-type/TRACA-COMPLETA-BUILDING-TYPE.md` §0.1

### V11. SmartScan Tier 3 ara envia totes les pàgines (fix aplicat)
- **Evidència:** Commit `7973c21`, tier3_vision.py: `_get_images_b64()` amb max_pages=10
- **Safeguards:** 4MB/pàgina, 18MB acumulat, 90s timeout, max(1,...) guard
- **Traça:** memory `project_smartscan_page1_review.md`

---

## Hipòtesis PENDENTS de verificar

### V12. Bell-Lloc COORDENADES.txt apunta a parcel·la EQUIVOCADA
- **Evidència:** Cadastre CPMRC a les coords (314418.9, 4611117.6) retorna
  `"CL VIA FERREA 57"`, però el projecte és a `"Carrer Mestre Ramon Ortiz 15"`
- **Impacte:** TOTES les adjacents de Bell-Lloc es calculen des de la parcel·la equivocada
- **Altres projectes:** Castellar, Rubí, Linyola → OK (coords apunten a la parcel·la correcta)
- **Causa probable:** El punt P-1 del COORDENADES.txt és on es va fer l'assaig de penetració,
  que pot estar a la parcel·la del costat o al carrer (80m d'error confirmat per Josep)
- **Implicació per sistema:** Cal validar que les coordenades cauen dins la parcel·la
  del projecte (comparant LDT amb street_address) abans d'usar-les per adjacents

### P01. LLM judge reclassificaria >=15 MISMATCH com CLOSE
- **Test:** `scripts/compare_benchmarks.py --llm-judge --all`
- **Predicció:** building_type, site_description, location_sentence millorarien
- **Prioritat:** ALTA — determina si l'accuracy real és ~45% i no 37.7%

### P02. Orientació cardinal vs relativa per adjacents
- **Context:** Eva diu "sud = Carrer Antoni Bellet", Cadastre LDT diu "CL VIA FERREA"
- **Hipòtesi:** Eva potser usa orientació relativa al carrer d'accés, no cardinals purs
- **Impacte:** Si confirmat, les 4 direccions podrien estar rotades per alguns projectes
- **Test:** Comparar amb Google Maps/ortofoto per 2-3 projectes

### P03. Geometria WFS eliminaria la majoria de salts de carrer
- **Context:** Ja tenim geometria WFS al geocode. Usant-la per calcular distàncies
  de probe per direcció, els carrers estrets serien detectats
- **Test:** Implementar i comparar adjacents pre/post per Bell-Lloc
- **Prioritat:** ALTA — afecta 22 MISMATCH

### P04. Miner de noms de fitxer milloraria building_type i client_name
- **Context:** Noms com "geotècnic Ampliació Albert Sans municipi Alcoletge"
  contenen building_type, client_name, municipality
- **Test:** Implementar regex miner per noms i mesurar noves senyals
- **Prioritat:** MITJA

---

## Accions en curs

| # | Acció | Estat | Referència |
|---|---|---|---|
| F1 | Integrar LLM judge a diagnostic_trace.py | EN CURS | V10 |
| F2 | _set() respecta source priority | EN CURS | V02 |
| F3 | Probe adjacents amb geometria WFS real | EN CURS | V07 |
| F4 | Treure "OBRA" de pressupost_pdf_v1.yaml | PENDENT | V03 |
| F5 | Completar format schemas (lab_*, building) | PENDENT | V04 |
| F6 | Miner de noms de fitxer | PENDENT | V06 |
| F7 | Coma al formatter west | PENDENT | V09 |
