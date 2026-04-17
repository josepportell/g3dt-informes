"""Pin the Crespo Villalaz + Hunt cohesive-soil correlation tables.

Source: Carlos Crespo Villalaz, "Mecánica de suelos y cimentaciones",
Limusa 5ª ed. (2004). Full research notes + cross-checks:
docs/RECERCA-PRACTICA-GEOTECNICA-ESPANYA.md § 9.

These helpers are NOT yet wired into the pipeline (see task G.2c). The tests
exist to pin the exact table values so any future change is intentional
rather than accidental.
"""
from __future__ import annotations

import pytest

from automation.cte_geomech import (
    CONSISTENCY_LABELS,
    consistency_label,
    crespo_consistency,
    crespo_phi_cohesive,
    crespo_phi_range,
    hunt_cohesion_from_nspt,
    hunt_cohesion_from_qu,
)


# ---------------------------------------------------------------------------
# Crespo φ table — row-by-row boundary pinning
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("nspt, expected_class, expected_phi_range", [
    # Lower boundary samples (inside each band)
    (0,   "muy_blanda", (0.0,  0.0)),
    (1.5, "muy_blanda", (0.0,  0.0)),
    (2,   "blanda",     (0.0,  5.0)),
    (3,   "blanda",     (0.0,  5.0)),
    (4,   "media",      (5.0,  10.0)),
    (7,   "media",      (5.0,  10.0)),
    (8,   "firme",      (10.0, 15.0)),
    (14,  "firme",      (10.0, 15.0)),
    (15,  "muy_firme",  (15.0, 20.0)),
    (22,  "muy_firme",  (15.0, 20.0)),   # Linyola-like N
    (30,  "dura",       (20.0, 25.0)),
    (60,  "dura",       (20.0, 25.0)),
])
def test_crespo_bands(nspt: float, expected_class: str, expected_phi_range: tuple[float, float]) -> None:
    assert crespo_consistency(nspt) == expected_class
    assert crespo_phi_range(nspt) == expected_phi_range
    # Midpoint φ
    lo, hi = expected_phi_range
    assert crespo_phi_cohesive(nspt) == pytest.approx((lo + hi) / 2.0)


def test_crespo_negative_nspt_fails_closed() -> None:
    """Negative/garbage N clamps to muy_blanda (safest-cohesion assumption)."""
    assert crespo_consistency(-5) == "muy_blanda"
    assert crespo_phi_cohesive(-5) == 0.0


# ---------------------------------------------------------------------------
# Consistency label localisation (Spanish + Catalan)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key, expected_es, expected_ca", [
    ("muy_blanda", "muy blanda", "molt tova"),
    ("blanda",     "blanda",     "tova"),
    ("media",      "media",      "mitjana"),
    ("plastico",   "plástico",   "plàstica"),
    ("firme",      "firme",      "ferma"),
    ("muy_firme",  "muy firme",  "molt ferma"),
    ("dura",       "dura",       "dura"),
])
def test_consistency_labels_both_languages(key: str, expected_es: str, expected_ca: str) -> None:
    assert consistency_label(key, "es") == expected_es
    assert consistency_label(key, "ca") == expected_ca
    assert CONSISTENCY_LABELS[key] == (expected_es, expected_ca)


def test_consistency_label_defaults_to_catalan() -> None:
    """Catalan is G3DT's primary UI language; no explicit lang arg → Catalan."""
    assert consistency_label("muy_firme") == "molt ferma"


def test_consistency_label_unknown_key_roundtrips() -> None:
    """Unknown keys echo back unchanged (defensive)."""
    assert consistency_label("made_up_band", "ca") == "made_up_band"


def test_crespo_consistency_lang_switch() -> None:
    """crespo_consistency supports key / es / ca return modes."""
    # Linyola-like N
    assert crespo_consistency(22) == "muy_firme"            # default = key
    assert crespo_consistency(22, "es") == "muy firme"
    assert crespo_consistency(22, "ca") == "molt ferma"


# ---------------------------------------------------------------------------
# Hunt cohesion from N (via Crespo rows)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("nspt, expected_c_kgcm2", [
    (1,   0.0625),   # muy_blanda: c range (0, 0.125) → mid 0.0625
    (3,   0.1875),   # blanda: (0.125, 0.25) → 0.1875
    (6,   0.375),    # media: (0.25, 0.50) → 0.375
    (10,  0.75),     # firme: (0.50, 1.00) → 0.75
    (22,  1.5),      # muy_firme: (1.00, 2.00) → 1.5
    (50,  2.5),      # dura: (2.0, ∞) → capped at 2.5
])
def test_hunt_cohesion_from_nspt(nspt: float, expected_c_kgcm2: float) -> None:
    assert hunt_cohesion_from_nspt(nspt) == pytest.approx(expected_c_kgcm2)


# ---------------------------------------------------------------------------
# Hunt cohesion from qu (standalone table)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("qu_kgcm2, expected_c_kgcm2", [
    (0.1,  0.0625),   # muy_blanda band
    (0.40, 0.1875),   # blanda
    (0.75, 0.375),    # plástico
    (1.50, 0.75),     # firme
    (3.00, 1.5),      # muy_firme
    (5.00, 2.5),      # dura (capped)
])
def test_hunt_cohesion_from_qu(qu_kgcm2: float, expected_c_kgcm2: float) -> None:
    assert hunt_cohesion_from_qu(qu_kgcm2) == pytest.approx(expected_c_kgcm2)


# ---------------------------------------------------------------------------
# Sanity: the helpers are NOT wired into the current pipeline
# ---------------------------------------------------------------------------

def test_helpers_not_wired_into_pipeline_yet() -> None:
    """G.2a ships helpers only. nspt_to_phi (used by the pipeline) must still
    return its CTE 4.1 result, not the Crespo reduction. Remove this test
    when G.2c wires the new correlations in."""
    from automation.cte_geomech import nspt_to_phi
    # For a cohesive soil at Nb=22 (Linyola-like):
    # - CTE 4.1 (current): ~35° (over-reports)
    # - Crespo (new helper): 17.5° (pure clay), still too low for llims
    # Until G.2c, the pipeline must keep returning the CTE value (>20°).
    assert nspt_to_phi(22, "cohesive") > 20.0, \
        "Pipeline phi changed unexpectedly — G.2c may have landed; remove this test."
