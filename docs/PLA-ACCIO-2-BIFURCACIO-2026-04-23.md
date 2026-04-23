# Bifurcació d'Acció 2 — Plans deterministic + LLM reasoner

**Data:** 2026-04-23
**Estat:** Pla — pendent d'execució
**Branch de referència:** `experiment/cc-only-extraction`

---

## 1. Context i motivació

### 1.1 Com hem arribat aquí

Acció 2 del pla post-sweep 2026-04-22 es descrivia com un "CTE threshold off-by-one bug" — arreglar 3 variables (`cte_sol`, `cte_edificacio`, `qa_value`) que mostraven un patró coherent de discrepància a 4 projectes. La investigació profunda d'avui (2026-04-23) ha revelat que el framing original era incorrecte.

**Descobertes clau:**

1. **Skip-top-layer ja està implementat i cablejat** (`automation/bicapa.py` + `automation/report_data.py:954`). El mòdul conté TOTES les cases de Rodríguez Ortiz Cap. 2 §6.1 + §6.2 com a primitives (Fig. 2.9, Vesic Cuadro 2.4, Brown & Meyerhof, Tcheng). El test `tests/test_bicapa_wire.py` passa amb fixtures tipus Alcoletge.

2. **A la pràctica, la lògica no dispara correctament.** El `calc_trace` del sweep 2026-04-22 mostra discrepàncies no uniformes:

   | Projecte | Eva qa | Pipe qa | bearing_idx | sondeig file? | cap_reason | Causa arrel |
   |---|---|---|---|---|---|---|
   | Alcoletge | 3.50 | 1.00 | 0 | **NO** | soil | No sondeig → fallback single-layer |
   | Rubí | 3.50 | 3.00 | 1 ✓ | yes | **rock** ✗ | "Gresos" classificat com a rock; Eva ho tracta com dense_granular |
   | Linyola | 3.00 | 2.00 | 0 | yes | soil | Sondeig extret buit (`sondeig_tests=[]`) → fallback |
   | Castellar | 3.00 | 2.00 | 1 ✓ | yes | soil | Detecció de soil_type inconsistent amb el bearing layer (L2 "bretxes" hauria de ser rock) |
   | Vilanova | 2.50 | 2.50 | 0 | yes | soil | **Fals positiu** — valors iguals, Eva afegeix "...F=3" al text |

3. **No és un sol bug, són quatre causes diferents** amb regression surface diferent a cada una.

4. **`docs/METODOLOGIA-EVA.md` (2026-04-17)** documenta citat textualment les fonts d'Eva (Crespo Villalaz, Rodríguez Ortiz, Schmertmann, Terzaghi-Peck). Ortiz Cap. 2 està arxivat com a PDF a `docs/research/books/`. Confiança en la metodologia: 99.99% (Eva cita textualment als seus informes signats).

5. **El codi actual acumula regles hand-tuned** (llistes de keywords, llindars numèrics, detecció de soil_type) que encerten alguns casos i fallen en altres per raons subtils de judici professional. Exemple paradigmàtic:
   - Rubí L2: `"Gresos amb intercalacions de lutites i conglomerats"` — tècnicament roca, Eva ho tracta com a dens granular (c=0.05, cap 3.5).
   - Castellar L2: `"Substrat rocós. Bretxes amb lutites i gresos vermells"` — Eva ho tracta com a roca (c=1.0, cap 3.0).
   - Bell-Lloc L2: `"Graves en matriu sorrenca carbonatades"` — Eva ho tracta com a dens granular (c=0.05, cap 3.5).
   - Linyola L2 (per Eva): `"Lutites i sorrenques"` amb c=1.0 — roca.

   Les distincions són de judici professional basat en N20 + descripció + context del projecte. Cap llista de keywords tancada capta la regla real.

### 1.2 El problema estructural

**La pipeline actual codifica regles; Eva aplica judici.** Per moure el match+close headline del 64% a cotes més altes necessitem o (a) refinar les regles fins al límit del que és expressable en codi, o (b) incorporar un component que raoni com Eva ho fa.

Aquest document descriu les dues vies i un experiment puntual per decidir entre elles.

---

## 2. Plan 1 — Continuació deterministic

**Objectiu:** tancar les causes identificades amb regles expressables en codi. Mantenir la pipeline 100% determinista i auditable.

**Branch:** `feature/action-2-deterministic` a partir de `experiment/cc-only-extraction`.

### 2.1 Fase 1a — DPSH auto-segmentation (Fix α)

**Problema que resol:** Alcoletge + Linyola arriben al càlcul sense estructura de capes utilitzable (Alcoletge no té sondeig; Linyola té `sondeig_tests=[]` perquè l'extractor no va produir capes estructurades). El fallback single-layer contamina el N20 mitjà amb lectures febles superficials.

**Implementació:**
- Nou mòdul `automation/dpsh_segmenter.py` amb funció `segment_by_n20_step(dpsh_data) -> list[dict]`.
- Heurística: detectar salt de N20 ≥ 3 blow counts entre lectures consecutives, present a ≥ 2 tests DPSH del projecte, per identificar frontera de capa.
- Sortida: llista de dicts compatibles amb `sondeig_layers` (`depth_from_m`, `depth_to_m`, `n20_average`, `description="auto-segmented from DPSH"`).
- Gate a `report_data.py`: `if not sondeig_layers and dpsh_data: sondeig_layers = segment_by_n20_step(dpsh_data)`.

**Dades que ho confirmen:** Alcoletge mostra salt consistent a ~1.2m (N20 passa de 5-9 a 12-14 a 3 tests independents). Sub-A investigation ho ha validat.

**Regression guard:** gating estricte — només dispara si `sondeig_layers` està buit. Projectes amb sondeig real (Bell-Lloc, Castellar, Rubí, Vilanova, Anciles) no es toquen mai.

**Esforç:** 1-2 dies.
**Risc:** Baix (gating perfecte).
**Impacte esperat:** Alcoletge qa 1.00→3.5 (+6pp headline), Linyola qa 2.00→3.0 (+3pp headline).

**Tests:**
- `tests/test_dpsh_segmenter.py` — unit tests de la heurística (saltes clars, saltes ambigus, DPSH sense salt → una sola capa).
- `tests/test_bicapa_wire.py` — afegir fixtures Alcoletge + Linyola.
- Cap regressió als 5 projectes amb sondeig real.

### 2.2 Fase 1b — Email Eva (Question #5)

**Problema que resol:** Fix β requereix confirmació metodològica d'Eva sobre rock vs dense_granular.

**Pregunta a afegir a `docs/CORREU-EVA-PREGUNTES-CALCULS-v4.md`:**

> *"Per materials descrits com «gresos alterats», «lutites parcialment alterades» o «conglomerat amb matriu granular» amb N20 moderat (40-70, no refús):*
> - *Els tractes com a roca (c=1.0 kg/cm², cap Qa=3.0)?*
> - *O com a dens granular (c=0.05 kg/cm², cap Qa=3.5)?*
> *Com decideixes el límit? Exemples concrets que recordis: Rubí té gresos + N20=40-63 → vas donar Qa=3.50 (implica dens granular). Castellar té bretxes + refús → vas donar Qa=3.0 (roca). Quin criteri diferencia aquests dos casos per al futur?"*

Bloqueja Fase 1c fins a resposta.

**Esforç:** 15 min (redactar la pregunta).

### 2.3 Fase 1c — Refinament rock classification (Fix β)

**Problema que resol:** Rubí qa 3.00→3.50, Bell-Lloc cap tier upgrade a dense_granular (actualment `cap_reason=soil` tot i matxejar per coincidència al 3.0).

**Implementació (pendent de resposta d'Eva):**
- Dividir `is_rock()` en `is_hard_rock()` + `is_indurated_granular()` a `automation/cte_geomech.py`.
- Criteri tentatiu (a confirmar amb Eva):
  - `is_hard_rock`: descripció conté {`'bretx'`, `'substrat rocós'`, `'pissarra'`, `'roca compacta'`} **AND** N20 ≥ 80 (proper a refús).
  - `is_indurated_granular`: descripció conté {`'gresos'`, `'lutites alterades'`, `'conglomerat'`, `'graves carbonatades'`} **AND** N20 ∈ [25, 79].
- `soil_type_to_cohesion` mapping nou: `indurated_granular` → c=0.05, phi=35°.
- `calculate_qa` cap_tier:
  - hard_rock → QA_CAP_ROCK = 3.0 (o 4.5 per roca clara segons Eva)
  - indurated_granular → QA_CAP_DENSE_GRANULAR = 3.5
  - dense_granular existent → 3.5
  - soil → 3.0

**Regression matrix (obligatòria abans de merge):**

| Projecte | Bearing layer desc | N20 | Eva qa | Classificació esperada |
|---|---|---|---|---|
| Rubí | Gresos amb lutites | 40-63 | 3.50 | indurated_granular ✓ |
| Bell-Lloc | Graves carbonatades | 42 | 3.50 | dense_granular ✓ |
| Castellar | Bretxes, lutites, gresos | refús | 3.00 | hard_rock ✓ |
| Linyola L2 | Lutites i sorrenques | 31-R | 3.00 | hard_rock (Eva dóna c=1.0) ✓ |
| Alcoletge L2 | Lutites alterades | R | 3.50 | indurated_granular ✓ |
| Vilanova | — | — | 2.50 | soil (sense canvi) ✓ |
| Anciles | — | — | ? | (pendent dades netes) |

**Esforç:** 2-3 dies post-Eva.
**Risc:** Mitjà (surface tocada és detecció de soil_type; tests obligatoris).
**Impacte esperat:** Rubí +1 MATCH a qa_value, Bell-Lloc cap tier auditat, eventualment +1-2pp headline.

### 2.4 Fase 1d — Re-sweep mesurant impacte

Després de Fix α (i opcionalment Fix β, si Eva respon ràpid), córrer sweep complet 7 projectes.

**Procediment:** seguir `docs/_FOR-NEW-YOU-20260423.md` §"Re-sweep operational checklist" — netejar caches de concept_map + CartoCiudad + geocode, executar `scripts/diagnostic_trace.py --save --components --ne-trace`, verificar no hi ha DNS contamination, comparar variables a nivell de MISMATCH→MATCH flips contra snapshot 2026-04-22.

**Projecció:** Plan 1 (tot inclòs) arriba al 77-80% match+close per acció pura deterministic. Aquest és el sostre del plantejament basat en regles.

### 2.5 Sostre i risc de Plan 1

**Sostre:** ~77-80% match+close. Més enllà cal entrar al territori on la pipeline encerta numèricament però la comparació text-to-text del judge falla (narratives Eva, identity synthesis, adjacents observats), o on les regles han d'incorporar nuances de judici professional.

**Risc:** Baix-mitjà. Cada fix és scoped, gated, testat amb golden cases, i roda-ble en isolació. Cap cost arquitectural.

---

## 3. Plan 2 — LLM decision layer (Eva-like reasoning)

**Objectiu:** afegir una capa al pipeline que raoni com Eva ho fa — decidint quin mètode aplicar, quina capa usar, quin cap tier, quin idioma del output — delegant el raonament de judici professional a un LLM amb accés a la metodologia d'Eva.

**Branch:** `feature/llm-geotech-reasoner` a partir de `experiment/cc-only-extraction`.

### 3.1 Arquitectura

```
Phase 0.3  → FileMiner                        (unchanged)
Phase 0.45 → ConceptScout                     (unchanged)
Phase 0.5  → auto_extract                     (unchanged)
Phase 1    → Claude vision (plànol/sondeig)   (unchanged)
      ↓
Phase 1.5  → GeotechReasoner (NOU — LLM layer)

  Inputs:
    - sondeig_layers extretes (o buides)
    - dpsh_data (lectures crues)
    - eva_reference_values.json (si existeix, per ground truth)
    - METODOLOGIA-EVA.md (fragment, contextualitzat)
    - Ortiz Cap. 2 §6.2 (resum de regles bicapa)
    - CTE DB SE-C brackets (T-1..T-4, C-0..C-2)
    - Formulae: Schmertmann shape factors (2.5/3.5), Terzaghi-Peck boundary (1.20m)
    - Eva's typical values table

  Eines disponibles (tool_use):
    - decide_geotech_strategy: schema estricta Pydantic

  Output (tool-use, 100% schema compliant):
    {
      "bearing_strategy": "single_layer" | "skip_top" | "bicapa_fig29" |
                          "clay_over_clay_soft_over_stiff" |
                          "clay_over_clay_stiff_over_soft" |
                          "sand_over_clay",
      "bearing_layer_index": int,
      "soil_classification": "hard_rock" | "indurated_granular" |
                             "dense_granular" | "medium_granular" |
                             "soft_granular" | "cohesive_stiff" |
                             "cohesive_soft" | "weak_fill",
      "cap_tier": "rock_3.0" | "rock_4.5" | "dense_granular_3.5" | "soil_3.0",
      "n20_source": "sondeig_layer_avg" | "dpsh_filtered_to_layer" |
                    "dpsh_global_avg" | "eva_override",
      "cte_sol": "T-1" | "T-2" | "T-3" | "T-4",
      "cte_edificacio": "C-0" | "C-1" | "C-2",
      "schmertmann_shape_factor": 2.5 | 3.5,
      "settlement_language": "ca" | "es",
      "rationale": str,
      "eva_methodology_citations": [str, ...],
      "confidence": "high" | "medium" | "low",
      "flags": list[str]  # e.g. ["novel_case", "fallback_to_rules", ...]
    }
      ↓
Phase 2   → Wizard prefills populated from LLM decisions + computed values
Phase 3   → ReportGenerator (unchanged)
```

### 3.2 Principis de disseny

1. **LLM decideix meta-lògica; codi executa càlcul.** L'LLM no produeix `qa=3.50` — produeix `{bearing_layer_index: 1, cap_tier: "dense_granular_3.5"}`. El codi fa després `calculate_qa(bearing_layer=layers[1], cap_tier="dense_granular_3.5")`. La matemàtica queda auditable i determinista.

2. **Tool-use amb schema Pydantic strict.** 100% garantia de format JSON. Retry loop amb feedback al prompt si la validació falla (convergència ~100% a 3 intents).

3. **Temperature = 0, model pinat.** `claude-opus-4-7` (el model més capaç, Eva és l'únic usuari per MEMORY.md `feedback_no_volume_reasoning`). Versió del model fixada a config.

4. **Prompt = metodologia + inputs.** L'LLM no necessita "saber geotècnia" — llegeix `METODOLOGIA-EVA.md` + fragment d'Ortiz + els inputs del projecte i aplica la metodologia d'Eva. Prompt construït amb context injection.

5. **Cache per projecte** per hash d'inputs. Una crida API per projecte per canvi d'inputs. Cost menyspreable.

6. **Fallback deterministic.** Si l'output de l'LLM falla validació o contradiu dades crítiques (ex. Eva té user_data explícit), fer fallback a regles existents + log WARN.

7. **Rationale capturat per auditar.** El camp `rationale` i `eva_methodology_citations` permeten entendre per què l'LLM ha decidit X. Commit de decisions a golden test fixtures.

### 3.3 Estratègia de regressió

- **Golden test suite obligatòria**: 7 projectes × tots els camps de decisió → snapshots a `tests/fixtures/llm_decisions/{project}_expected.json`.
- **LLM output fixat** a commit time. Diff alert si canvia per a qualsevol projecte entre commits.
- **Re-snapshot només** quan Eva confirma un canvi metodològic (commit = evidence trail a la Git history).
- **Bench mínim**: `pytest tests/test_llm_reasoner_regression.py` verifica que tots els 7 projectes produeixen l'output golden.

### 3.4 Riscos

| Risc | Mitigació |
|---|---|
| Drift entre versions del model API | Pin model version; golden tests detecten qualsevol canvi |
| Projectes novells (fora dels 7 de mostra) | Eva-in-the-loop al wizard queda; fallback a regles si confidence=low |
| Latència extra 5-10s per projecte | Acceptable (wizard UX async); cache elimina re-calls |
| Cost API | Negligible (Eva = únic usuari, ~1 call per informe) |
| Debuggabilitat en errors | Rationale + citations + regression diff |
| LLM confia amb resposta incorrecta | Golden tests + confidence field + Eva review |

### 3.5 Rollout phased

1. **Fase 2a — Build + standalone test.** Construir reasoner + pydantic schema + prompt. Sense cablejar. Executar sobre els 7 projectes usant dades ja extretes. Produir golden decisions inicials.
2. **Fase 2b — Wire darrere env flag.** `G3DT_USE_LLM_REASONER=true` (default OFF). Pipeline roda amb LLM si flag, fallback a regles si no.
3. **Fase 2c — Side-by-side sweep.** Córrer sweep amb flag ON vs OFF. Comparar headline + variable-level flips. Criteri: ≥3pp millora headline + zero regressions sobre variables MATCH actuals.
4. **Fase 2d — Flip default.** Si 2c passa, flip default a ON. Deixar fallback code path viu per 2 sweeps més. Després remove dead rule code.

**Esforç total:** ~2 setmanes (si tot passa a primer intent).
**Risc:** Mitjà-alt (superfície nova). Mitigat per rollout phased + golden tests.
**Sostre potencial:** > 85% si l'LLM resol també casos d'identitat (client/arquitecte) i adjacents narratius.

---

## 4. El spike experiment — decidir Plan 2 abans d'invertir-hi

### 4.1 Per què un spike primer

**Problema identificat per l'usuari (2026-04-23):**
- Plan 2 és un canvi arquitectural gran.
- Executar Plan 1 i Plan 2 en paral·lel (proposta inicial) introdueix risc de context-switching entre branques llargues a sessions múltiples → merge conflicts + estat oblidat.
- Alternativa millor: **isolar el canvi arquitectural al mínim testable, validar amb dades reals, decidir go/no-go amb 2-3 dies d'esforç.**

Aquesta és enginyeria spike clàssica. Si l'spike funciona, invertim en Plan 2 complet amb confiança alta. Si no funciona, descartem i continuem amb Plan 1 sense haver contaminat la pipeline.

### 4.2 Scope de l'spike

**Target:** `cap_tier` classification per al bearing layer (rock_3.0 / rock_4.5 / dense_granular_3.5 / soil_3.0).

**Per què aquesta decisió concreta:**
- És el nucli del problema identificat avui — Rubí vs Bell-Lloc vs Castellar vs Linyola presenten exactament el tipus de nuance que regles tancades no resolen.
- És una decisió **discreta** (4 valors possibles), amb ground truth inequívoc a `eva_reference_values.json` (la cohesion d'Eva implica el cap).
- Mètrica clara: "LLM cap_tier == Eva cap_tier" per projecte. 7/7 = èxit; <5/7 = dismiss.
- Requereix que l'LLM llegeixi metodologia + descripció + N20 + context → exercici perfecte de raonament.
- Si l'LLM encerta aquí, és senyal fort que pot gestionar els altres camps de decisió.

### 4.3 Implementació de l'spike

**Branch:** `experiment/llm-spike-cap-tier` off `experiment/cc-only-extraction`.

**Fitxers nous (tots opcional — no toquen pipeline viva):**

```
automation/experimental/
  __init__.py
  cap_tier_reasoner.py       # LLM wrapper + pydantic schema + prompt
  cap_tier_calculator.py     # Clone de calculate_qa adaptat a rebre cap_tier
                             # com a input explícit (en lloc de derivar-lo)
tests/experimental/
  test_cap_tier_spike.py     # Test sobre 7 projectes
scripts/
  run_cap_tier_spike.py      # Entry point per córrer l'experiment
docs/experimental/
  cap-tier-spike-results.md  # Registre de resultats per projecte
```

**Pipeline de l'spike (sobre dades ja existents, sense re-executar Phase 0/1):**

1. Per cada projecte a `reference-material/*`:
   - Llegir `sondeig_annex_extracted.json` (si existeix), `dpsh_extracted.json`, `eva_reference_values.json`.
   - Construir prompt amb: descripció del bearing layer (deepest layer o el picat per `_select_bearing_layer_idx`), N20 distribution, METODOLOGIA-EVA.md fragment, exemples dels 4 cap tiers.
   - Cridar Claude API amb tool-use (`claude-opus-4-7`, temperature=0).
   - Extreure `cap_tier` del tool call.
   - Córrer `cap_tier_calculator.calculate_qa_with_explicit_cap_tier(...)` passant el cap_tier de l'LLM.
   - Comparar qa_value resultant vs Eva's qa_value.

2. Produir taula de resultats:

   ```
   Project      | Bearing desc (truncated)        | N20 | LLM cap_tier         | Eva qa | Pipe qa (spike) | Match?
   -------------|---------------------------------|-----|----------------------|--------|-----------------|-------
   Bell-Lloc    | Graves carbonatades             | 42  | dense_granular_3.5   | 3.50   | 3.50            | ✓
   Castellar    | Substrat rocós, bretxes         | R   | rock_3.0             | 3.00   | 3.00            | ✓
   Rubí         | Gresos amb lutites              | 55  | dense_granular_3.5   | 3.50   | 3.50            | ✓
   Linyola      | Lutites i sorrenques            | 31R | rock_3.0             | 3.00   | 3.00            | ✓
   Alcoletge    | Lutites alterades               | R   | dense_granular_3.5   | 3.50   | 3.50            | ✓
   Vilanova     | (bearing desc)                  | ..  | soil_3.0             | 2.50   | 2.50            | ✓
   Anciles      | (bearing desc)                  | ..  | ?                    | ?      | ?               | ?
   ```

3. Capturar rationale per cada cas a `docs/experimental/cap-tier-spike-results.md`.

### 4.4 Criteri d'èxit

**Adoptar Plan 2:** 6/7 projectes correctament classificats, amb rationale coherent i confidence alta als 6. Rubí és el test crític — si l'LLM llegeix "Gresos" però aplica `dense_granular_3.5` citant el N20 moderat, és l'evidència principal que el model raona com Eva.

**Dismiss Plan 2:** < 5/7 correctament classificats, o rationale inconsistents entre projectes similars, o confidence baixa generalitzada. En aquest cas, continuar amb Plan 1 només.

**Ambigu (5/7):** discussió amb Eva, potencialment iterar el prompt 1-2 voltes abans de decidir.

### 4.5 Timeline

- **Dia 1 AM**: Construir `cap_tier_reasoner.py` + pydantic schema + prompt base (carregant fragments de METODOLOGIA-EVA.md).
- **Dia 1 PM**: Construir `cap_tier_calculator.py` (clone minimal de `calculate_qa`) + `run_cap_tier_spike.py`.
- **Dia 2 AM**: Executar contra 1 projecte (Rubí, el cas més crític). Iterar prompt fins a correct + confident.
- **Dia 2 PM**: Executar contra els 7 projectes. Recollir resultats.
- **Dia 3 AM**: Anàlisi + doc de resultats + decisió.

**Total:** 2-3 dies.

### 4.6 Què produeix independentment del veredicte

- **Prompt + schema reutilitzables** per Plan 2 complet si adoptem.
- **Dades empíriques** sobre capacitat del LLM en aquest domini.
- **Golden cases** de cap_tier per project (útils per Plan 1 testing també).
- **Registre de rationale** que pot informar el disseny de regles deterministic a Plan 1 (l'LLM ens pot ensenyar les regles que hauríem de codificar).

---

## 5. Seqüència proposada

1. **Fase 1a (Plan 1)** — DPSH auto-segmentation, merge independent, sense bloquejar. Baix risc, alt impacte (+9pp esperat). 1-2 dies.
2. **Re-sweep post-1a** — medir impacte real. Commit STATUS.md checkpoint.
3. **Spike LLM (§4)** — 2-3 dies. Veredicte go/no-go per Plan 2.
4. **Fase 1b (email Eva)** — en paral·lel amb spike (no blocking).
5. **Si spike OK → Plan 2 Fase 2a** (build full reasoner amb tots els camps de decisió). Paral·lel amb Fase 1c (Fix β) si Eva ja ha respost.
6. **Si spike KO → Plan 1 Fase 1c** directament, amb l'evidència de l'spike informant-ne el disseny.
7. **Re-sweep final** després de tot, documentar nou headline.

---

## 6. Git i sessió strategy

### 6.1 Branques

```
main ────────────────────────────────────────
 │
 └─ experiment/cc-only-extraction (stable baseline, current HEAD)
      │
      ├─ feature/action-2-deterministic (Plan 1 phases 1a, 1c)
      │     └─ sub-branch per cada fix si cal
      │
      └─ experiment/llm-spike-cap-tier (spike §4)
            │ si èxit →
            └─ feature/llm-geotech-reasoner (Plan 2 full)
                  └─ phase-specific sub-branches
```

### 6.2 Regles de commit

- Commit per cada milestone (no commits "WIP"). STATUS.md checkpoint a cada merge.
- Missatge segueix convenció existent: `docs(g3dt):`, `feat(g3dt):`, `fix(g3dt):`, `test(g3dt):`.
- Cada branch feature viu fins a merge final. Després esborrar.
- **No merge cap a `main`** fins que Plan complet (1 o 2) sigui validat amb re-sweep estable.

### 6.3 Session continuity

- Cada sessió comença llegint `STATUS.md` + aquest doc + `MEMORY.md` + `docs/_FOR-NEW-YOU-{YYYYMMDD}.md` més recent.
- Tasques in_progress queden explicitades a la TaskList del CLI.
- Branch actual visible a `git branch --show-current`.
- Si una sessió acaba amb treball incomplet, crear handoff doc `docs/_FOR-NEW-YOU-{YYYYMMDD}.md` amb el pointer exacte al punt on es reprèn.

### 6.4 Rollback plan

- Cada fix passa per tests (660 pass baseline) abans de merge.
- Cada merge → commit de tag opcional `checkpoint-{fix-name}` per facilitar rollback.
- `git revert` sobre el merge commit és el path de rollback (no `git reset --hard`, no force push).

---

## 7. Open questions

- **Eva mètode rock vs dense_granular** — pendent de resposta.
- **Anciles dades netes** — sweep 2026-04-22 DNS-contaminat; cal re-run individual per tenir dades fiables.
- **Spike model choice final** — claude-opus-4-7 assumit; fallback a sonnet-4.6 si volum de tokens massa alt o latència problemàtica (improbable per a aquest domini).

---

## 8. Referències

- `docs/METODOLOGIA-EVA.md` — metodologia Eva, cites textuals dels informes.
- `docs/RESPOSTA-EVA-PREGUNTES-CALCULS.md` — respostes Eva 2026-02-26.
- `docs/PLA-PROXIMES-ACCIONS-POST-SWEEP-2026-04-22.md` — pla original (Acció 2 com a "CTE threshold bug" — ara re-framed en aquest doc).
- `docs/_FOR-NEW-YOU-20260423.md` — handoff doc de la sessió actual.
- `docs/diagnostics/2026-04-22_CROSS_351d13.json` — snapshot sweep baseline.
- `automation/bicapa.py` — primitives de bicapa ja implementades.
- `automation/report_data.py:954` — `_select_bearing_layer_idx` cablejat.
- `docs/research/books/Rodriguez-Ortiz-Curso-aplicado-de-cimentaciones.pdf` — font metodològica.
- `tests/test_bicapa_wire.py` — tests existents de bearing-layer selection.

---

*Fi del pla. Proper pas: inici de Phase 1a sobre branch `feature/action-2-deterministic`.*
