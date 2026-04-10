# Resum consolidat — Sessió 2026-04-10

## Progressió d'accuracy

```
  37.7%  ████████░░░░░░░░░░░░  Baseline (matí, string matching)
  57.0%  ███████████░░░░░░░░░  + LLM judge + synthesis priority + probes
  57.5%  ███████████░░░░░░░░░  + coord validation + OBRA fix
  58.9%  ████████████░░░░░░░░  + Qa cap Nb≥25 + rounding professional
```

| Mètrica | Baseline | Final | Canvi |
|---|---|---|---|
| **Match+Close** | 37.7% | **58.9%** | **+21.2pp** |
| MATCH | 58 | 90 | +32 (+55%) |
| CLOSE | 20 | 32 | +12 (+60%) |
| MISMATCH | 129 | 85 | -44 (-34%) |
| Not extracted | 74 | 74 | = |

---

## Fixes implementats avui (10 commits)

| # | Fix | Commit | Impacte |
|---|---|---|---|
| F1 | LLM judge a diagnostic_trace.py (`--llm-judge`) | 8156319 | -40 MISMATCH (falsos positius) |
| F2 | Synthesis respecta source priority (`_TRUSTED_SOURCE_PATTERNS`) | 8156319 | Traçabilitat vision preservada |
| F3 | Probe adjacents amb bounding box | 8156319 | Millora per parcelles amb polygon |
| F4 | "OBRA" eliminat de pressupost_pdf_v1.yaml | 47f140f | Menys senyals dolentes building_type |
| F5 | spt_depth_range signe negatiu | 47f140f | +2 MATCH (Castellar, Anciles) |
| F6 | Validació coordenades COORDENADES.txt | fca8023 + a0ad246 | Bell-Lloc detecta parcel·la incorrecta |
| F7 | SmartScan Tier 3 multi-pàgina | 7973c21 | Classifica millor PDFs multipàgina |
| F8 | Diagnostic fixes (scorecard, lab regex, diff) | 89c5c4f | Diagnostic més precís |
| F9 | Qa cap variable (Nb≥25 → 3.5) | b61d3f0 + 6e2f40e | 6/7 projectes MATCH per Qa |
| F10 | Arrodoniment professional (0.5, enter, 0.1) | b61d3f0 | Valors com els d'Eva |

---

## Troballes clau (verificades)

### Criteris de càlcul d'Eva (doc complet: `docs/CRITERIS-CALCUL-EVA.md`)
- **Qa:** `round_0.5(min(max(T-P, Full_Terzaghi), cap))` — 6/7 MATCH
- **Cap variable:** Rock (c≥0.5) = 3.0, Dense (Nb≥25) = 3.5, Soft = 3.0
- **K30:** E/75 granular, E/60 rock → 2/2 MATCH exacte
- **Arrodoniment:** Pràctica professional estàndard (confirmat per recerca Exa)
- **Arrodoniment intermedi:** phi arrodonit al bracket CTE ABANS de Terzaghi

### Pipeline
- **Vision plànol:** Funciona bé (7/7), però LLM synthesis sobreescrivia → FIX F2
- **FileMiner:** "OBRA" capturava adreces → FIX F4
- **Coordenades:** Bell-Lloc COORDENADES.txt apunta a parcel·la equivocada → FIX F6
- **74% conceptes sense format mapping** — però ~30 no ho necessiten
- **lab_extractor:** Funciona per 3 projectes amb GTL, però no propaga als prefills

---

## 85 MISMATCH restants — Per causa arrel

| Causa arrel | Count | Accionable? | Fix previst |
|---|---|---|---|
| **Text narratiu** (site_desc 7, building_struct 5, lab_tests 4, location 2) | 18 | Parcial | LLM judge ja millora. Post-processadors |
| **Càlculs frases** (settlement 6, qa 5, k30 2) | 13 | **SÍ** | Parsejar frases Eva al diagnostic |
| **Adjacents** (N/S/E/W fmt: 14 total) | 14 | Parcial | P05 orientació, geometria WFS |
| **Extracció text** (CTE 4, seismic 4, table_dpsh 4, architect 4, altres 10) | 26 | **SÍ** | Completar frases, millorar extraction |
| **Edge cases** (spt 2, sulfate 2, superficie 2, radon 2, altres 6) | 14 | Parcial | Revisar individualment |

## 74 NOT_EXTRACTED restants — Reclassificats

| Causa arrel | Count | Nova classificació |
|---|---|---|
| **Lab sense GTL** (Alcoletge, Vilanova, Anciles) | ~18 | → **PASS** (font no existeix) |
| **Lab AMB GTL** (Castellar, Rubí, Linyola) — no propagades | ~18 | → **FIX** (bug propagació) |
| **SPT sense sondeig** | ~6 | → **PASS** |
| **site_condition** | 7 | → Investigar vision (fotos camp, G.Earth) |
| **access_street** | 6 | → Cadastre/ICGC (explorar) |
| **Adjacents Vilanova** (geocoding falla) | 4 | → Fix geocoding |
| **superficie_*, dates, altres** | 15 | → Millorar vision/extracció |

### Impacte potencial amb tots els fixes
- ~24 NE → PASS (neteja diagnostic)
- ~18 NE → MATCH (fix propagació lab)
- ~27 MISMATCH → MATCH/CLOSE
- **Estimació: 58.9% → ~75-80%** d'accuracy mesurada

---

## Metodologia establerta

### Traçabilitat completa (3 variables traçades avui)
1. **building_type** → `docs/taller/traca-building-type/`
2. **adjacent_*_fmt** → `docs/taller/traca-adjacents/`
3. **qa_value / settlement / k30** → `docs/taller/traca-qa-settlement/`

### Registre de verificacions: `docs/taller/REGISTRE-VERIFICACIONS.md`
- 16 troballes verificades (V01-V16)
- 5 hipòtesis pendents (P01-P05)
- 10 accions (F1-F10 fetes + F4-F10 pendents)

### Bateria de tests Qa: `scripts/qa_hypothesis_tester.py`
- Test sistemàtic de 11 hipòtesis × 7 projectes
- Paràmetres reals extrets via PyMuPDF de PDFs signats

---

## Tasques pendents

| # | Tasca | Prioritat |
|---|---|---|
| 7 | Implementar PASS al diagnostic | ALTA (en curs) |
| 8 | Fix lab_* propagació als prefills (18 NE) | ALTA |
| 9 | Explorar site_condition via fotos camp | MITJA |
| — | Fix diagnostic: parsejar frases settlement/K30 | ALTA (-8 MISMATCH) |
| — | Completar frase seismic_ab_text | ALTA (-4 MISMATCH) |
| — | Fix geocoding Vilanova | MITJA (-4 NE) |
| — | Adjacents: investigar orientació P05 | MITJA (-5 a -14 MISMATCH) |
