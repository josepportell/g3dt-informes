# Pla: 3 fixes — Qa rock cap, E bracket, Schmertmann settlement

Data: 2026-02-26

## Context

The 4-project comparison matrix shows 3 systematic deviations from Eva's reference values:

| Issue | Project | Our value | Eva's value | Root cause |
|-------|---------|-----------|-------------|------------|
| Qa rock cap | Castellar | 3.0 | 5.0 | Rock gets soil cap because `cohesion=0.0` hardcoded + wrong condition |
| E bracket | Rubí | 1428 | 450 | Nb=51.8 crosses CTE D.23 bracket at N=50 |
| Settlement | Bell-Lloc/Rubí | 0.70/0.23 cm | 1.50/0.72 cm | Boussinesq elastic, not Schmertmann |

## Fix 1: Castellar Qa rock cap (3.0 → 5.0)

Two sub-issues, both must be fixed.

### 1A. Wrong cap condition — `terzaghi_calculator.py:395`

```python
# BEFORE:
qa_cap = QA_CAP_ROCK if not is_granular and self.cohesion >= 0.5 else QA_CAP_SOIL

# AFTER:
qa_cap = QA_CAP_ROCK if self.cohesion >= 0.5 else QA_CAP_SOIL
```

Rock always has cohesion >= 0.5 (from `rock_params_default()`), soils have ~0. Cohesion alone is the correct discriminator.

### 1B. Cohesion hardcoded + Terzaghi computed too early — `report_generator.py:197-218`

The Terzaghi calc runs BEFORE `build_report_data()` (line 250), using `project_data['geotechnical']` which has no cohesion. Hardcodes `cohesion=0.0` at line 204.

**Fix: Move Terzaghi after `build_report_data()`**, using the properly-computed `report_data.geotechnical_params` (which correctly detects rock → cohesion=1.0).

- Remove Terzaghi block (lines 197-220)
- Pass `terzaghi_result=None` to `build_report_data()` at line 253
- Add new block after line 255 using `self.report_data.geotechnical_params`
- Derive `is_granular` from `cohesion < 0.5` (consistent with 1A)
- Pass `soil_type` from first soil level (needed for Fix 3)

## Fix 2: Rubí E bracket (1428 → ~469)

**Root cause:** E lookup uses Nb=51.8 which crosses the CTE D.23 bracket at N=50. Within a bracket, conservative mode gives identical E for any N value (`E_min + 10% of range`). So N20 vs Nb only matters when they fall in different brackets.

N20=43 → "medios" bracket → E=469 kg/cm² (matches Eva's 450).

**Fix: Use N20 (not Nb) for `nspt_to_E_kg_cm2()`.** Nb stays correct for phi (Schmertmann CTE 4.1).

| File | Line(s) | Change |
|------|---------|--------|
| `report_data.py` | ~401, ~409 | `nspt_to_E_kg_cm2(avg_nb)` → `nspt_to_E_kg_cm2(avg_n20)` |
| `report_generator.py` | ~978, ~991 | same (avg_n20 already in scope) |
| `compare_4projects.py` | ~182 | `nspt_to_E_kg_cm2(nb)` → `nspt_to_E_kg_cm2(n20)` |

Add docstring note in `nspt_to_E_kg_cm2()` explaining callers should pass N20.

## Fix 3: Schmertmann settlement

**Current:** Boussinesq `s = q x B x (1-v²) / E`. Under-estimates 50-70%.
**Target:** Schmertmann (1978) per Eva's methodology.

### 3A. Add `nb_to_qc()` — `cte_geomech.py`

Robertson (1983) N→qc ratios:

```python
ROBERTSON_QC_RATIO = {
    "grava": 8.0, "arena": 4.5, "granular": 4.5,
    "arena_limosa": 3.5, "limo": 2.5, "cohesive": 2.5, "arcilla": 1.5,
}

def nb_to_qc(nb, soil_type="granular") -> float:
    """Nb → qc (kg/cm²) via Robertson (1983)."""
    return nb * ROBERTSON_QC_RATIO.get(soil_type, 4.5)
```

### 3B. Add `schmertmann_settlement()` — `terzaghi_calculator.py`

Module-level function. Schmertmann (1978) simplified single-layer:

```
s = C1 x Dq x Iz_integral / Es
```

- C1 = max(1 - 0.5 x sigma'v0/Dq, 0.5) — depth correction
- Iz_integral (analytical area under strain influence diagram):
  - Square: 0.525 x B_cm (depth 0→2B, peak at B/2)
  - Strip: 1.10 x B_cm (depth 0→4B, peak at B)
- Es = 2.5 x qc (square) or 3.5 x qc (strip) — Eva's methodology

### 3C. Modify `calculate_qa()` — `terzaghi_calculator.py`

- Add `soil_type: str | None = None` parameter
- Settlement logic: if nspt + soil_type available → qc → Es → Schmertmann; else → Boussinesq fallback

### 3D. Update callers

- `report_generator.py` new Terzaghi block (from Fix 1B): pass `soil_type`
- `compare_4projects.py`: add `soil_type=soil_type`

## Files to modify

| File | Fixes | Key changes |
|------|-------|-------------|
| `automation/terzaghi_calculator.py` | 1A, 3B, 3C | Cap condition, Schmertmann function, soil_type param |
| `automation/report_generator.py` | 1B, 2 | Move Terzaghi post-build, E uses N20 |
| `automation/report_data.py` | 2 | E uses N20 (2 call sites) |
| `automation/cte_geomech.py` | 3A | Add `nb_to_qc()`, E docstring note |
| `proves-fase2/compare_4projects.py` | 2, 3D | E uses N20, pass soil_type |

## Verification

Run `compare_4projects.py` and check:

| Project | Param | Before | Expected | Eva |
|---------|-------|--------|----------|-----|
| Castellar | Qa | 3.0 | **5.0** | 5.0 |
| Rubi | E | 1428 | **~469** | 450 |
| Rubi | K30 | 19.03 | **~6.25** | 6.0 |
| Bell-Lloc | settlement | 0.70 | **~1.2-1.8** | 1.50 |
| Rubi | settlement | 0.23 | **~0.5-0.9** | 0.72 |
| All others | gamma, phi | unchanged | unchanged | — |
