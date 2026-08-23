# Anàlisi: què cal perquè el sistema "(quasi) faci la feina de l'Eva, sempre" — nivell A

**Data:** 2026-08-23 (vespre) · **Branca:** `review/prod-audit-2026-08` (anàlisi, cap canvi de codi)
**Brief:** `docs/_FOR-NEW-YOU-20260823-1545.md` §0 (comentari del Josep) + les seves respostes d'avui a les 5 preguntes (§1).
**Evidència nova d'avui:** inventari real de les 8 carpetes, *mapa de veritat* del nivell A (on viu cada dada de l'Eva),
lectura dels tres precedents (pipeline clàssic, AI Pipeline Fases 1-5, CC-Agentic T1-T4). Eina: `scripts/tier_a_truth_map.py`
(sortida completa a `docs/audit/tier-a-truth-map-2026-08-23.json`); no s'ha executat cap pipeline ni cap crida a model.

## 0. Resum executiu

1. **La hipòtesi del Josep ("obrir cada fitxer i entendre'l") ja està construïda dues vegades** en aquest repositori (AI
   Pipeline Fases 1-5, abril; CC-Agentic T1, abril) i les dues van quedar per sota del pipeline clàssic. Però **cap de les
   tres arquitectures falla llegint: les tres fallen triant** (`client`="G3", expedient = ID del laboratori, parcel·la 11 per
   la 3, municipi d'una foto). Llegir-ho tot, sol, produeix més candidats (Alcoletge: 620 candidats, 48 conflictes), no més
   certesa.
2. **El que no té cap de les tres és el que té un humà: saber, per a cada camp, a quin document mira primer i com
   verifica.** Avui he construït aquest mapa a partir de les 8 carpetes (§3). Resultat: **el nivell A viu majoritàriament en
   5 documents que G3 mateix genera amb plantilla fixa a 8/8 projectes** (pressupost, fitxa de camp, comanda de laboratori,
   PLAN_COST, Excel DPSH), no en documents de proveïdors amb formats canviants. El municipi és en 6-16 documents de text de
   cada carpeta i producció el treu d'una foto de WhatsApp.
3. **Els "principis d'autoritat" de l'AI Pipeline (268 línies) no mencionen mai aquestes 5 plantilles de G3**; per a
   `expedient` diuen que la font és "el caixetí de l'informe" — la sortida de l'Eva. El playbook es va escriure des del
   raonament, no des de les carpetes. Això explica el 27,66 % tant com explica el 59 %.
4. **Proposta (§6, alternativa D):** no un lector nou, sinó *lector per document* (Fase 4 existent) + **playbook per camp
   derivat del mapa de veritat** (nou, petit, verificable) + **verificació creuada** (un valor és "segur" només si ≥ 2 fonts
   independents coincideixen; si no, llista de candidats) + **popup de candidats** (ampliar l'existent). Cost per projecte
   1-3 € i 2-4 min en segon pla; cost de desenvolupament acotat per runs parcials amb la cache per font que la Fase 4 ja té.
5. **Mètrica "sempre" (§7):** per a cada projecte × camp del nivell A, un de quatre resultats: *correcte* / *candidats que
   contenen el correcte* / *no trobat i marcat* / **erroni amb confiança**. Objectiu: **erroni-amb-confiança = 0 a 8/8**,
   correcte ≥ 80 %, candidats ≤ 20 %. Hold-out 5+3 amb rotació. Avui el sistema no mesura ni tan sols l'últim.

## 1. Marc fixat pel Josep (respostes d'avui)

| Pregunta | Resposta | Conseqüència per a l'anàlisi |
|---|---|---|
| Què és "(quasi) fer la feina" | **Nivell A** (dades que un humà obté obrint fitxers) s'ha de fer *molt bé*; nivell B (càlculs, narrativa) és una conversa diferent, després | Tot el document jutja només el nivell A (§2) |
| Buit vs ple-i-equivocat | Cap dels dos: **llista de candidats ordenats per confiança + popup per triar**. Buit = "derrota"; ple amb falsa confiança = indueix error i després ràbia | Cal una sortida de tres estats (segur / candidats / no trobat) i la UI que la mostri |
| Corpus | **Només els 8** (7 de referència + Tulipa) | Hold-out dins dels 8; cap afirmació sobre els 19 reals |
| Pressupost | 5 min / 2-5 € acceptables *si el resultat és fiable*; 0,01 € malament és caríssim; segon pla acceptable. **Cost de desenvolupament sí que importa** → runs parcials per etapa | Dissenyar la validació sobre artefactes cacheats per etapa |
| Línies tancades | Cap | L'AI Pipeline es reconsidera (§5) |

Dues observacions del Josep que el document assumeix com a premisses:
- **Lògica emocional de l'Eva:** si fallem el nivell A, "el sistema és tonto" i la conversa és negativa; si el nivell A és
  correcte i Terzaghi no, la conversa és relaxada. Sí, s'entén: un becari que equivoca el client o el municipi és acomiadat;
  un que aplica malament Terzaghi és corregit. La UI ha de fer visible *d'on* surt cada dada ("trobat al PRESSUPOST, pàg. 1")
  perquè l'encert es percebi com a competència i el dubte com a honestedat, no com a fallada.
- **Escriptura a mà evitable:** l'Eva transcriu els DPSH a Excel a 8/8 projectes (`ANNEXES/{exp}_DPSH.xls`, un full per
  penetro). Els N20 no són nivell A en risc. El sondeig manuscrit *no* té Excel (0/8); els nivells geològics surten del
  sondeig i del criteri de l'Eva (memòria `eva_geological_levels_and_photo_id`) → frontera A/B, vegeu §2.

## 2. El nivell A, camp per camp, i a quina classe de font pertany

Classes de font (les necessitarem a §3-§6):
- **G3-plantilla (estable):** documents que G3 produeix amb la mateixa plantilla a cada projecte. Format fix, etiquetes fixes.
- **Proveïdor (variable):** plànols, projectes i correus de l'arquitecte/client. Format diferent a cada projecte.
- **Derivat (API/criteri):** Cadastre, ICGC, CTE, o criteri de l'Eva. No és *a* cap document del proveïdor.
- **Sortida de l'Eva:** annexos FreeHand exportats (`PDF/ANNEXES/*_sondeig.pdf`, `tall.pdf`, `pl situ.pdf`), informes previs.
  **Existeixen a les 8 carpetes perquè són projectes acabats; en un projecte nou que l'Eva obre per primer cop, no hi són.**

| Camp | On és de veritat (8 projectes, §3) | Classe | Prod avui |
|---|---|---|---|
| `expedient` | nom de carpeta 8/8; `comanda laboratori` "NÚM. D'EXPEDIENT" 8/8; GTL | G3-plantilla | 8/8 ✓ |
| `client_name` | pressupost bloc OBRA/CLIENT 7/8; fitxa de camp "CLIENT" 5/8; plànol (Bell-lloc); `DADES CLIENT.txt`; correus | G3-plantilla + regla semàntica (§3.2) | 5/8 ✗ ("G3" 3/8) |
| `street_address` | pressupost adreça d'OBRA 7/8; fitxa "ADREÇA OBRA" 5/8; comanda "ADREÇA" 6/8; plànol | G3-plantilla | ✗ (foto WhatsApp a Rubí) |
| `municipality` | comanda "POBLACIÓ" 8/8; pressupost 8/8; PLAN_COST títol 8/8; GTL | G3-plantilla | 5/8 ✗ (foto/etiqueta) |
| `architect_name` | caixetí del plànol (text vectorial 4/8); pressupost quan el sol·licitant és l'arquitecte (4/8); signatura de correu; **Vilanova: en cap text** | Proveïdor | ✗ parcial |
| `building_type` | PLAN_COST "DESCRIPCIÓ TITÒL" 8/8 (`EG HAB UNIF …`); comanda "OBRA" 8/8; pressupost p.1; correus | G3-plantilla (redacció de l'Eva ≠) | 1/8 ✓ |
| `num_floors` | plànol / projecte (variable); correus; **no és a cap plantilla G3** | Proveïdor | ✗ parcial |
| `superficie_parcela` | plànol / projecte (text a 3/8); Cadastre per ref. cadastral (PDFs del Cadastre a la carpeta de Bell-lloc); **Tulipa: dins d'un `.zip` amb 3 `.dwg`** | Proveïdor + Derivat | 3/8 ✓ (parcel·la equivocada 4/8) |
| `field_date` | fitxa "dies de camp" 5/8; comanda "DATA DE PRESA" 8/8 (data de mostra, ≠ primer dia a Bell-lloc); **noms de foto WhatsApp amb data 7/8**; GTL | G3-plantilla + regla (primer dia de camp) | 1/8 ✓ |
| `num_dpsh_tests` | fulls de l'Excel DPSH 8/8; pressupost "N assaigs DPSH" 8/8; fitxa "2 (P)" | G3-plantilla (3 fonts independents) | 7/8 ✓ |
| `cota_referencia` | `COORDENADES.txt` (z) 4/8; ICGC MDT a les UTM; annex sondeig (sortida de l'Eva) | Derivat | 7/8 ✓ **via annex de l'Eva** |
| `num_soil_levels` | sondeig manuscrit + criteri de l'Eva ("Unitat litològica") | Frontera A/B | proposar, confirmar sempre |
| `utm_x/y`, `referencia_catastral` | `COORDENADES.txt` 4/8; PDFs del Cadastre a la carpeta (Bell-lloc); geocodificació estricta | Derivat | 4/4 ✓ quan hi ha txt; parcel·la errònia 4/8 sense |
| lab (`lab_*`) | comanda 8/8 (lab = TPS sempre, memòria `gtl_lab_identity`); GTL 5/8 | G3-plantilla | ✓ |
| `cte_edificacio` / `cte_sol` | pressupost p.2 "Tipus d'edifici: C1 / Tipus de terreny: T1" 6/8 | G3-plantilla | 6/8 ✓ (coincidència; no el llegeix d'aquí) |

**Lectura:** 9 dels 15 camps del nivell A viuen en plantilles de G3. Dos (`architect_name`, `num_floors`) i mig
(`superficie_parcela`) depenen de documents del proveïdor. Tres són derivats (cota, UTM, parcel·la via Cadastre). Un és
criteri de l'Eva. **El problema "documents amb estructures noves" afecta de ple 2,5 camps, no 15.** Per a la resta, el
problema és que el sistema no mira on mira l'Eva.

Caveat honest: les plantilles de G3 **no sempre estan omplertes** (fitxa de camp buida a Rubí, Alcoletge, Vilanova; el
pressupost de Castellar no porta la línia "Tipus d'edifici"; Linyola té el pressupost amb el nom `25·0616.pdf`). "Sempre"
no es pot construir sobre una sola font: cal redundància (§6.3).

## 3. Evidència: què hi ha de veritat a una carpeta (inventari de les 8)

### 3.1 Invariants (presents a 8/8, tret que s'indiqui)

```
{exp} {MUNICIPI}/
├── {YY.NNNN}/                      codi comercial del pressupost (25.0647, 26.0049…)
│   ├── DADES PER ANAR A CAMP_v1.xlsx   fitxa interna G3: CLIENT, ADREÇA OBRA, contacte, PREVISIÓ ("2 (P)", "5P+2S"),
│   │                                   TENIM PLÀNOLS, EDIFICACIÓ EXISTENT, EMPRESA (TPS ERUGA), "dies de camp" = DATA
│   ├── PLAN_COST_{municipi}.xlsx       full de costos G3: DESCRIPCIÓ TITÒL ("EG HAB UNIF BELL-LLOC"), tècnic (Eva), OFERTA
│   ├── PRESSUPOST GEOTEC.{municipi}.pdf  (creator "G3 DESENVOLUPAMENT TERRITORIAL"; 7/8 + Linyola "25·0616.pdf")
│   │                                   p.1: OBRA/CLIENT (nom, adreça, municipi, tel), codi comercial, data
│   │                                   p.2: "Tipus d'edifici: C1", "Tipus de Terreny: T1", "N assaigs DPSH", sondeig/SPT
│   ├── *.msg                           correus del client/arquitecte AMB ADJUNTS (plànols, PLAN_COST, fotos, DWG…)
│   └── (plànols del proveïdor: A.01.pdf, 2_02B_DG.pdf, IV_PLANOS.pdf 35p, 1.0.pdf, .zip de .dwg, fotos WhatsApp)
├── ACCEPTACIO/                     pressupost signat (7/8; a vegades escanejat), DADES CLIENT.txt (1/8)
├── comanda laboratori_{exp}_{MUNICIPI}.xls   petició G3 al lab: sol·licitant = G3 (NIF B25364589 → l'origen del "G3"),
│                                   OBRA ("CONSTR HABITATGE"), NÚM. D'EXPEDIENT, ADREÇA, POBLACIÓ, DATA DE PRESA, mostres
├── {NNNN}-GTL-25 {Municipi}.pdf    informe del laboratori (5/8)
├── ANNEXES/{exp}_DPSH.xls          Excel de l'Eva: un full per penetro (P-1…); columnes Prof., N20, NB, par, N.F., "Nivells" (buida)
├── ANNEXES/ALTRES/COORDENADES.txt  GPS de camp amb z (4/8)
├── PENETROS*.pdf, SONDEIG.pdf      fulls de camp manuscrits escanejats (0 text)
├── FOTOGRAFIES/                    fotos de camp; noms "WhatsApp Image 2025-10-01 …" porten la data de camp (7/8)
├── ANNEXES/*.FH11 + PDF/ANNEXES/*.pdf + tall.pdf + pl situ.pdf   ← SORTIDES DE L'EVA (no hi són en un projecte nou)
└── {exp}_informe*.doc(x), {exp}_generated.docx, PDF-V0/            ← SORTIDES DE L'EVA / nostres
```

Mida del que s'hauria de "llegir com un humà" (només fonts, sense sortides de l'Eva): **30-75 pàgines+imatges per
projecte (mitjana 46)**, 4-6 Excel, 2-5 `.msg` amb 2-11 adjunts cadascun. No és gran. Un humà ho fa en 20 minuts.

### 3.2 El mapa de veritat (extracte; complet a `docs/audit/tier-a-truth-map-2026-08-23.json`, script `scripts/tier_a_truth_map.py`)

Per a cada valor del nivell A de l'informe signat, quins documents font el contenen literalment (text de PDF vectorial,
cel·les d'Excel, cos i adjunts de `.msg`):

| Camp | Cast. | Rubí | Linyola | Bell-lloc | Alcoletge | Vilanova | Anciles | Tulipa |
|---|---|---|---|---|---|---|---|---|
| client | pressupost (MODF) ×2 | pressupost + 2 msg | fitxa + projecte + 5 msg + acceptació | **plànol A.01 + DADES CLIENT.txt** (pressupost diu l'arquitecte) | pressupost + plànol + 2 msg | pressupost + plànol 1.0 + 2 msg | fitxa + pressupost + 3 msg | **només fitxa de camp** |
| arquitecte | (sense ref.) | = client | 11 docs | 8 docs (fitxa, pressupost, A.01, msg) | = client | **0 docs de text** | = client | (sense ref.) |
| municipi | 10 docs | 7 | 16 | (apòstrof; "BELL-LLOC" a comanda/pressupost) | 7 | 6 | 13 | 8 |
| sup. parcel·la | **0** (foto del plànol / Cadastre) | 1 (dubtós) | projecte 11p + 2 msg | A.01 + fitxa + PLAN_COST + pressupost | **0** (Cadastre) | (ref. sorollosa) | (ref. sorollosa) | **0** (dins `.dwg` al zip) |
| data de camp | fitxa + GTL + comanda | GTL + comanda | fitxa + GTL + comanda | **només fitxa** (comanda = 6 oct, camp = 1 oct) | comanda | comanda | fitxa + comanda | (sense ref.) |
| cota | 0 | 0 | COORDENADES.txt | 0 | 0 | 0 | 0 | (PLAN_COST, soroll) |

Tres lliçons que cap arquitectura actual codifica:
- **Regla semàntica del client:** el "client" de l'informe és el propietari/promotor, no qui rep el pressupost. A Bell-lloc
  el pressupost va a l'arquitecte (Bosch Novell) i l'Eva posa el propietari (Ramon Mitjana S.L., que només és al caixetí
  del plànol i a `DADES CLIENT.txt`). A Linyola la fitxa diu "BUNYESC" (arquitecte) i l'Eva posa Sílvia Eroles (propietària,
  al projecte). Un humà ho sap; el concepte `client_name` del YAML ho descriu en prosa però cap regla ho aplica.
- **Conflictes legítims:** Bell-lloc té dues adreces verdaderes (parcel·la en cantonada: "entre el Carrer Antoni Bellet i el
  Carrer Mestre Ramon Ortiz"; la comanda diu "ANTONI BALLET", error tipogràfic). La data de mostra (comanda) ≠ primer dia de
  camp (fitxa, fotos). "Sempre" inclou saber que dos valors diferents poden ser tots dos correctes → candidats, no competició.
- **El que no és enlloc:** cota (0/8 en text; ve de GPS o ICGC), superfície de parcel·la a 3/8 (Cadastre o foto/DWG),
  arquitecte de Vilanova (probablement en una imatge de signatura o enlloc). Aquí el sistema ha de dir "ho he buscat a X, Y,
  Z i no hi és; proposo el Cadastre (ref. …) / deixa-ho tu", no inventar des d'una foto.

## 4. Per què les tres arquitectures fallen al mateix lloc

| | Pipeline clàssic (prod) | AI Pipeline Fases 1-5 (`experiment/ai-pipeline`, abril) | CC-Agentic T1 (abril) |
|---|---|---|---|
| Com llegeix | SmartScan per rol (nom + pàg. 1) → FileMiner per etiquetes regex → probes Groq 1 pàg. → visió per tipus sobre el fitxer "guanyador" | Inventari complet (adjunts inclosos) → conversió per pàgina → **1 crida Claude per font, totes les pàgines, amb cita** | Sonnet 4.6 llegeix els fitxers descoberts, un sol pas |
| Com tria | competició per prioritats numèriques per font (`source_priority`) | rànquing LLM en 3 passades amb `authority_principles.md` | no tria: omple |
| Resultat | 59 % (8 proj.); 77 MISMATCH d'extracció amb 5 causes, totes de *tria* | 27,66 % top-1 (Alcoletge, únic projecte), 48 conflictes; errors de *tria* (expedient = ID lab; lab = SOIL-ASSAIG) | 34,6 % |
| Llegeix bé? | sí (DPSH 85-99 %, plànols 0 % FAIL) | sí ("CC reads files well" — Finding 1) | sí |
| Per què perd | (a) etiquetes: "dies de camp" no és a la llista `["DATA","FECHA","DATA CAMP"]` de `dades_camp_excel_v1.yaml` → `field_date` cau al GTL; (b) cap noció d'autoritat per *tipus de document*: una foto WhatsApp pot guanyar `municipality`; (c) el fallback del concept_map tria per conceptes sense mirar el rol; (d) **omple amb confiança 0,95 coses falses i no ho marca** | (a) el playbook ignora les plantilles G3 i cita sortides de l'Eva com a font; (b) rànquing per concepte aïllat, sense verificació creuada; (c) mai mesurat en 7 projectes; (d) Groq no hi és — bé | sense playbook ni tria; mesurat contra càlculs |

Conclusió: **"llegir cada fitxer" és condició necessària i ja la tenim (Fase 4). La condició suficient és un playbook per
camp fet des del mapa de veritat + una política de verificació + una sortida honesta.** Cap de les tres la té.

## 5. Què vol dir, tècnicament, "entendre cada fitxer com un humà"

Descompost en el que fa un humà (l'Eva o un becari bo) amb una carpeta nova:

1. **Inventari complet.** Tot, inclosos adjunts de `.msg`, `.zip`, `.dwg`, subcarpetes amb nom de pressupost, fotos.
   *Estat:* Fase 1 ho fa (adjunts inclosos). Falta `.zip` (Tulipa) i `.dwg` (cal conversor: ODA File Converter o
   LibreDWG → DXF → text; el `PARAMETRES URBANISTICS.dwg` de Tulipa probablement porta els 564 m²). El pipeline clàssic
   deixa 117 adjunts sense rol (memòria `project_email_attachment_blindspot`).
2. **Saber què és cada document abans de buscar-hi res.** "Això és el pressupost de G3 (plantilla), això un plànol
   d'AutoCAD amb caixetí, això una foto de la màquina, això l'informe del lab." *Estat:* Fase 4 `SourceInsight`
   (document_type, author, date, purpose) ho fa per construcció; el clàssic ho fa per nom de fitxer + pàg. 1 (42,9 %
   d'encert a `architect_plan`, `PLA-VISION-EXHAUSTIVA` §SmartScan). Les plantilles de G3 es poden reconèixer
   determinísticament (creator del PDF, capçalera "PETICIÓ D'ASSAIGS", full 'fitxa', `PLAN COST | G3 DT`).
3. **Per a cada camp, anar primer on sol ser.** Això és el playbook de §6.2 — i és *per camp*, no per document. Avui
   `report_variables.yaml` té `source_priority` per *tipus de font* (`dades_camp_excel: 35`, `content_pdf: 45`) sense dir
   *quina cel·la* ni *quina regla semàntica*; `authority_principles.md` té regles per camp però sobre fonts equivocades.
4. **Verificar creuant.** Un humà que veu "BELL-LLOC" a la comanda, al pressupost i al PLAN_COST no dubta; que veu
   "Sant Quirze" en una foto i "Rubí" a tot arreu descarta la foto. *Estat:* cap arquitectura ho fa; la competició
   clàssica tria el màxim de confiança, el rànquing LLM ordena. La regla és simple: **≥ 2 fonts independents d'autoritat
   A que coincideixen → segur; 1 font d'autoritat A sense contradicció → segur amb nota; altrament candidats.**
5. **Dir d'on surt i quan no ho sap.** "Client: Ramon Mitjana S.L. (plànol A.01, caixetí). El pressupost va a Bosch Novell
   (arquitecte)." / "Plantes: no surt a cap document; el plànol A.01 només té planta baixa dibuixada — confirma." *Estat:*
   Fase 4 ja emet `quote` + `reasoning` per candidat; el wizard només mostra un badge de font i un "+N" discret.
6. **Llegir el que cal llegir amb visió, i només això.** Fulls manuscrits, plànols sense text, pressupost signat
   escanejat (Alcoletge), fotos només si cap document de text ha donat el camp. Els models ho llegeixen bé (A/B §4 del
   diagnòstic); el cost és de l'ordre de 1-3 € per projecte amb Sonnet (46 unitats × ~1,5k tokens + context; Fase 4 real:
   4,06 $ a Alcoletge incloent sortides de l'Eva i sense cache), 5-10 € amb Opus.

## 6. Alternatives

### A. Pipeline clàssic + correccions de prioritat (O5-O9 del diagnòstic) — *residual*

Tanca Q1-Q5 d'avui (G3 com a client, parcel·la, data, probes, fallback). Cost: 1-2 dies. **No respon al brief:** cada
projecte nou amb una etiqueta o un document diferent torna a fallar pel mateix mecanisme (llistes d'etiquetes). És manteniment,
no arquitectura. Només té sentit si es decideix no fer res més.

### B. Reprendre l'AI Pipeline Fases 1-5 tal com és i "arreglar la tria"

Reutilitza el 90 % del que cal (inventari, conversió, lectura per font amb cita, cache per font, traça). Però el rànquing
LLM en 3 passades sobre principis en prosa ha donat 27,66 % i és car (4,63 $ de rànquing a Alcoletge, més que la lectura).
Sense el mapa de veritat i la verificació creuada, només canviaríem el text del playbook i tornaríem a mesurar un projecte.
**Risc:** repetir abril.

### C. Agent lector (Claude amb eines: obrir, renderitzar, cercar, comparar) amb llista de comprovació per camp

És la metàfora literal del Josep ("obre cada fitxer, entén, troba, tanca"). Avantatge: adapta la cerca a la carpeta,
pot fer zoom, pot obrir un `.zip`. Inconvenients mesurats al repositori: T3 (CC com a QA) va ser net negatiu; l'agent
decideix amb el mateix (mal) criteri si no té playbook; no determinista (dos runs, dos resultats: memòria
`project_judge_noise_band`); temps 5-15 min; difícil de validar per etapes. **Bo com a eina d'Eva sota demanda** (ja existeix
en forma de calaix HITL: "ensenya'm on és i t'ho trec"), **dolent com a pipeline automàtic**.

### D. Lector per document + playbook per camp + verificació creuada + candidats — *recomanada*

```
Fase 1-3 (existents)   inventari complet (+ zip/dwg) → tipologia → artefactes per pàgina/full/cos
Fase 4 (existent)      1 crida per font: SourceInsight + candidats amb cita.  Canvi: context de plantilles G3
                        (el model sap que "PETICIÓ D'ASSAIGS" és la comanda i que "dies de camp" és la data)
Fase 4a (NOU, Python)  lectors deterministes de les 5 plantilles G3 → candidats d'autoritat A amb cel·la/pàgina exacta
Fase 5' (NOU, senzill) per camp del nivell A: playbook = [fonts en ordre, regla semàntica, regla de verificació]
                        → estat {segur, candidats[], no_trobat} + justificació. Sense passades B/C. LLM només
                        per a les regles semàntiques (client = propietari; primer dia de camp) i per a documents
                        del proveïdor (plànol, projecte).
Fase 6 (ampliar UI)    camp segur: valor + font + cita al passar el ratolí. Candidats: el camp es mostra AMB el primer
                        candidat però marcat (ambre) + popup "He trobat 2 valors: … / …" d'un clic. No trobat: text
                        "No és a cap document (he mirat pressupost, fitxa, comanda, plànol)" + botó del calaix HITL.
Fase 7                 ReportGenerator existent.
Derivats               Cadastre només amb número de carrer coincident o ref. cadastral (PDF a la carpeta); ICGC per a
                        cota quan hi ha UTM; si no, "no trobat", mai una parcel·la veïna.
```

Per què funcionarà on B i el clàssic no: el playbook surt de dades (§3.2), no d'intuïció; la decisió és majoritàriament
determinista i explicable; el model fa el que fa bé (llegir, entendre tipus de document, aplicar una regla semàntica amb el
text davant) i no el que fa malament (ordenar 23 candidats sense criteri). I la sortida té tres estats, que és l'únic que
permet "sempre": quan no ho sabem, ho diem i l'Eva tria en un clic.

**Cost per projecte:** Fase 4 amb Sonnet 1-3 € (2-4 min amb 4-8 crides en paral·lel; avui Fase 4 és seqüencial),
Fase 4a/5' < 0,1 €, derivats 0. Dins del pressupost del Josep amb marge per a Opus als documents del proveïdor si cal.
**Cost de desenvolupament:** Fase 4 cacheja per font (hash de prompt + model); una passada de lectura dels 8 projectes
(~15-25 $) serveix per a totes les iteracions del playbook i de la verificació (Python, 0 $). Les iteracions cares només
quan canvia el prompt de Fase 4.
**Esforç:** Fase 4a (5 lectors de plantilla, amb tests sobre els 8 fitxers reals): 1-2 dies. Playbook + verificació +
mètrica: 2-3 dies. UI de candidats: 1-2 dies. Zip/dwg: 0,5-1 dia. Mesura i dues rondes de hold-out: 2 dies. **~2 setmanes.**
**Què no resol:** `num_floors` i `superficie_parcela` quan el plànol no és a la carpeta (3/7 el 2026-04; T4) — aquí la
resposta correcta és "no trobat + Cadastre proposat", que és el que fa un humà. `architect_name` a Vilanova, igual.

Alternativa D és B amb tres peces petites; no és una quarta arquitectura.

## 7. Com es valida "sempre" amb 8 projectes

### 7.1 Mètrica

Per a cada projecte × camp del nivell A (15 camps × 8 = 120 cel·les), un resultat:

| Resultat | Definició | Objectiu |
|---|---|---|
| **OK** | valor segur i coincideix amb l'informe (regles CLOSE: article/adjectiu en `building_type`, format de data) | ≥ 80 % |
| **CAND** | estat "candidats" i el correcte és a la llista (≤ 3) | ≤ 20 % |
| **NT** | "no trobat" i de veritat no és a cap font (§3.2 = 0 docs) | comptat a part, no penalitza |
| **ERR** | valor *segur* i equivocat, o "no trobat" quan sí que hi era | **0 a 8/8** |

ERR és la mètrica de la ràbia de l'Eva. Avui no es mesura. El comparador `scripts/compare_prefills_vs_eva.py` dona MATCH /
CLOSE / MISMATCH; cal afegir-li l'estat de confiança del sistema per distingir CAND d'ERR (una columna).

### 7.2 Hold-out

El playbook es construeix amb 5 projectes i es mesura amb 3 que no s'han mirat; després es rota (3 particions). Els 3
difícils han d'aparèixer com a test almenys un cop: **Tulipa** (2 cases, zip/dwg, fitxa com a única font del client),
**Vilanova** (arquitecte enlloc, 18 fotos, pressupost en castellà), **Anciles** (35 pàgines de plànols, 7 habitatges, Huesca).
Si un camp passa a ERR en qualsevol partició, no es dona per fet fins que la regla que el cobreix és determinista o té
verificació creuada.

### 7.3 Runs parcials (resposta a la preocupació de cost del Josep)

| Etapa | Artefacte (`validation/`) | Cost de re-executar | Quan cal |
|---|---|---|---|
| 1-3 inventari/tipologia/conversió | `ai_inventory.json`, `ai_typology.json`, `ai_conversion.json` | 0 $ (Python) | nous fitxers |
| 4 lectura per font | `ai_analysis.json` + `ai_pipeline/analysis/{font}/_cache.json` | 1-3 $/projecte, **només les fonts el prompt de les quals canvia** | canvi de prompt o de model |
| 4a lectors plantilla G3 | (nou) `g3_templates.json` | 0 $ | sempre |
| 5' playbook + verificació | (nou) `tier_a_decisions.json` | 0 $ | cada iteració del playbook |
| mètrica | taula 120 cel·les | 0 $ | cada iteració |

Una passada de Fase 4 sobre els 8 (≈ 15-25 $) i després desenes d'iteracions de 5' a 0 $. Mai un "full pipeline" per provar
una regla.

### 7.4 Què no podem validar

Els 19 projectes reals de l'Eva. L'únic pont és Tulipa (real, 2026). Si les carpetes noves de l'Eva no porten les plantilles
G3 (improbable: són el seu procés), el playbook degrada a candidats, no a errors — que és el comportament desitjat.

## 8. Riscos i incògnites

- **Sortides de l'Eva com a font — RESOLT (Josep, 2026-08-23 nit): l'Eva dibuixa primer els annexos i després obre el
  wizard.** Per tant `PDF/ANNEXES/*_sondeig.pdf`, `tall.pdf` i `pl situ.pdf` SÍ que existeixen a la primera obertura i són
  fonts legítimes (i les millors) per a `cota_referencia` i `num_soil_levels`: són el criteri de l'Eva ja aplicat. Els
  dos camps passen de "derivat / frontera A-B" a **nivell A amb font d'autoritat A** (l'annex de sondeig). La taula de §2 s'ha
  de llegir amb aquesta correcció; el risc desapareix.
- **DWG.** Tulipa (2026) porta els plànols en `.dwg` dins d'un `.zip`. Sense conversor, superfície i plantes queden "no
  trobat". LibreDWG (`dwg2dxf`) + `ezdxf` és viable en Python; cal provar-ho amb els 3 fitxers de Tulipa.
- **Dos edificis en una carpeta** (Tulipa: CASA 1 / CASA 2, dos Excel DPSH, dos pressupostos). El nivell A es multiplica;
  el wizard no ho contempla. Mínim: detectar-ho i avisar; ideal: un informe per casa.
- **Groq.** La ruta D no el necessita. Mantenir-lo fora del camí del nivell A (503/429, memòria `groq_llama4_scout_deprecated`).
- **Temps.** Fase 4 en sèrie: 72 fonts × ~10 s. Amb 4-8 fils, 2-4 min. Si l'Eva "torna més tard" (acceptat), el wizard ja
  té SSE per mostrar primer els camps segurs de les plantilles G3 (< 10 s, Python) i després la resta.
- **Mesura inflada.** El 80 % d'OK es mesura sobre projectes amb informe signat; la redacció de `building_type` de l'Eva
  ("un habitatge unifamiliar") mai serà literal a cap font ("EG HAB UNIF") → regla CLOSE explícita o candidats amb la
  frase proposada.

## 9. Decisions per al Josep

1. **Alternativa D** (lector existent + playbook des del mapa de veritat + verificació creuada + candidats) com a línia de
   treball, o una altra de §6.
2. **On es construeix:** sobre `experiment/ai-pipeline` (té Fases 1-5 i el trace tool) o portant `automation/ai_pipeline/`
   (ja present a la branca de prod, flag off) a una branca nova des de `review/prod-audit-2026-08`. Recomano la segona: el
   codi és el mateix i evita divergir del que corre a l'Eva.
3. **Definició tancada del nivell A** (taula §2): confirmar els 15 camps i la frontera de `num_soil_levels`.
4. **Pressupost de lectura inicial:** ~25 $ per a la passada de Fase 4 sobre els 8 projectes (una vegada, cacheada).
5. ~~Pregunta per a l'Eva: annexos abans o després del wizard?~~ **Resposta (2026-08-23 nit): abans.** Vegeu §8.

**Decisions preses pel Josep (2026-08-23 nit):** alternativa D; branca nova; els 15 camps del nivell A confirmats;
25 $ de lectura inicial aprovats (OpenRouter). Pendent de decidir: si la primera lectura "d'or" dels 8 projectes la fa
Claude Code en sessió (gratuïta, agentiva, serveix d'oracle) abans de la passada per API.

---
*Fi de l'anàlisi. Lector existent + playbook fet des de les carpetes + verificació creuada + candidats honestos. El coll
d'ampolla mai ha estat llegir; ha estat saber on mirar i admetre quan no se sap.*
