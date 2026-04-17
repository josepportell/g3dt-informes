"""Tests for Crespo Villalaz Tabla 11.2 — granular SPT→φ lookup.

Source: Crespo Villalaz (2004), "Mecánica de suelos y cimentaciones", 5a ed.,
Ch.11, p.175, Tabla 11.2 "En arenas".

Context: This is the sub-table behind Eva's recurring φ=28° for transitional
materials (llim argilós, sorres argiloses) — the "muy floja" bottom row.
"""
from __future__ import annotations

import pytest

from automation.cte_geomech import (
    CRESPO_C_CEMENTED_GRAVEL_KGCM2,
    CRESPO_PHI_ESTIMATES_NO_LAB,
    crespo_density_label,
    crespo_phi_granular,
    crespo_phi_granular_range,
)


# ---------------------------------------------------------------------------
# Tabla 11.2 band midpoints
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("nspt, expected_phi", [
    (0,  28.0),   # muy floja — single anchor
    (4,  28.0),   # still muy floja
    (5,  29.0),   # floja: (28+30)/2
    (10, 29.0),   # floja upper end
    (11, 33.0),   # media: (30+36)/2
    (30, 33.0),   # media upper end
    (31, 38.5),   # densa: (36+41)/2
    (50, 38.5),   # densa upper end
    (51, 43.0),   # muy densa: (41+45)/2
    (80, 43.0),   # muy densa
])
def test_crespo_phi_granular_band_midpoints(nspt: float, expected_phi: float) -> None:
    assert crespo_phi_granular(nspt) == pytest.approx(expected_phi)


def test_crespo_phi_granular_transitional_clamps_to_28() -> None:
    """Eva's rule for llim argilós / sorres argiloses: clamp to 28°
    regardless of N. This matches her informes (Alcoletge, Linyola, Rubí)."""
    assert crespo_phi_granular(5, "transitional") == 28.0
    assert crespo_phi_granular(30, "transitional") == 28.0
    assert crespo_phi_granular(0, "transitional") == 28.0


def test_crespo_phi_granular_clean_bonus_plus_5() -> None:
    """Crespo p.174: if <5% fines, add 5° to tabulated φ."""
    base = crespo_phi_granular(20, "normal")  # media = 33°
    clean = crespo_phi_granular(20, "clean")
    assert clean == pytest.approx(base + 5.0)


def test_crespo_phi_granular_range_returns_tuple() -> None:
    phi_lo, phi_hi = crespo_phi_granular_range(20)
    assert phi_lo == 30.0
    assert phi_hi == 36.0


def test_crespo_phi_granular_negative_clamps_to_muy_floja() -> None:
    """Negative N is safer handled as muy floja (28°)."""
    assert crespo_phi_granular(-5) == 28.0


# ---------------------------------------------------------------------------
# Density labels
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("nspt, lang, expected", [
    (3,   "key", "muy_floja"),
    (7,   "key", "floja"),
    (20,  "key", "media"),
    (40,  "key", "densa"),
    (60,  "key", "muy_densa"),
    (3,   "es",  "muy floja"),
    (3,   "ca",  "molt fluixa"),
    (20,  "es",  "media"),
    (20,  "ca",  "mitjana"),
])
def test_crespo_density_label(nspt: float, lang: str, expected: str) -> None:
    assert crespo_density_label(nspt, lang) == expected


# ---------------------------------------------------------------------------
# Preliminary estimates without lab data (Crespo p.175 footnote)
# ---------------------------------------------------------------------------

def test_preliminary_estimates_match_crespo_footnote() -> None:
    """p.175 bottom paragraph: 'el limo un φ=20°', 'arena húmeda 10-15°',
    'arena seca 30-34°', 'grava/arena cementadas 34° c=0.25'."""
    assert CRESPO_PHI_ESTIMATES_NO_LAB["limo"] == 20.0
    assert CRESPO_PHI_ESTIMATES_NO_LAB["arena_seca"] == pytest.approx(32.0)
    assert CRESPO_PHI_ESTIMATES_NO_LAB["grava_cementada"] == 34.0
    assert CRESPO_C_CEMENTED_GRAVEL_KGCM2 == 0.25


def test_transitional_anchor_matches_muy_floja() -> None:
    """Eva's 28° anchor is the same value as Tabla 11.2's muy-floja row —
    this is intentional (she treats transitional materials as muy floja)."""
    assert CRESPO_PHI_ESTIMATES_NO_LAB["transicional"] == crespo_phi_granular(0)


# ---------------------------------------------------------------------------
# Alcoletge-style regression
# ---------------------------------------------------------------------------

def test_alcoletge_layer_1_matches_eva() -> None:
    """Alcoletge informe layer 1 (Sorres argiloses de rebliment, Nb=5-0):
    Eva's value is φ=28° exactly. Our lookup must agree."""
    # Nb≈3 → muy floja → 28°. Also clamped via "transitional" path.
    assert crespo_phi_granular(3) == 28.0
    assert crespo_phi_granular(3, "transitional") == 28.0


def test_linyola_style_transitional_still_28() -> None:
    """Linyola (Nb=22.6) hits the 'media' band (30-36°), but Eva uses 28°.
    The override for transitional materials reproduces this."""
    assert crespo_phi_granular(22.6, "transitional") == 28.0
    # Confirm that without the override we'd get the media midpoint
    assert crespo_phi_granular(22.6, "normal") == pytest.approx(33.0)


# ---------------------------------------------------------------------------
# Input validation / safety
# ---------------------------------------------------------------------------

def test_crespo_phi_granular_rejects_unknown_fine_fraction() -> None:
    with pytest.raises(ValueError, match="fine_fraction must be"):
        crespo_phi_granular(20, "transitonal")  # typo
    with pytest.raises(ValueError):
        crespo_phi_granular(20, "Clean")  # case mismatch


def test_crespo_phi_granular_clean_caps_at_45() -> None:
    """N=60 (muy densa, base φ=43°) + clean bonus would otherwise be 48° — cap at 45°."""
    assert crespo_phi_granular(60, "clean") == 45.0
