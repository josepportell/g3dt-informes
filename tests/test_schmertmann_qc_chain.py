"""Tests for the Schmertmann N→qc→E chain decoded from Eva's informe text.

Source text (every Eva informe contains this verbatim):
    "E = mòdul de deformació definit per Schmertmann, que s'obté de
     multiplicar 2.5 en el cas de sabates aïllades i 3.5 en el cas de
     corregudes, pel colpeig del penetròmetre estàtic. Aquest colpeig
     s'obté de la relació entre N (Nspt), amb uns factors de conversió
     establerts per cada un dels diferents tipus de material."

Decoded chain:
    qc = n_factor × N
    E  = shape_factor × qc       (2.5 isolated, 3.5 strip)
"""
from __future__ import annotations

import pytest

from automation.cte_geomech import (
    SCHMERTMANN_E_ISOLATED_FACTOR,
    SCHMERTMANN_E_STRIP_FACTOR,
    nspt_to_qc,
    schmertmann_E_from_nspt,
    schmertmann_E_from_qc,
    schmertmann_n_phi,                     # deprecated alias
    phi_from_nspt_silty_empirical,          # its real successor
)


# ---------------------------------------------------------------------------
# nspt_to_qc — grain-size conversion per Eva's three classes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("nspt, n, expected_qc", [
    # Slightly silty sands — Eva's n = 2.5
    (10, 2.5, 25.0),
    (20, 2.5, 50.0),
    # Silty sands — n = 2.0
    (10, 2.0, 20.0),
    (20, 2.0, 40.0),
    # Sandy silts (llims sorrencs) — n = 1.25
    (18.8, 1.25, 23.5),                  # Linyola-like (rounds to 23.5)
    (22.6, 1.25, 28.25),
])
def test_nspt_to_qc_anchor_points(nspt: float, n: float, expected_qc: float) -> None:
    assert nspt_to_qc(nspt, n) == pytest.approx(expected_qc)


def test_nspt_to_qc_handles_negative_input() -> None:
    """Negative N clamps to 0 — fails closed, no negative qc."""
    assert nspt_to_qc(-5, 2.5) == 0.0


def test_nspt_to_qc_intermediate_n_factors() -> None:
    """n-factor is a scalar multiplier; intermediate values work linearly."""
    assert nspt_to_qc(20, 1.75) == pytest.approx(35.0)


# ---------------------------------------------------------------------------
# schmertmann_E_from_qc — shape-factor dispatch
# ---------------------------------------------------------------------------

def test_shape_factor_constants() -> None:
    assert SCHMERTMANN_E_ISOLATED_FACTOR == 2.5
    assert SCHMERTMANN_E_STRIP_FACTOR == 3.5


@pytest.mark.parametrize("shape_label", [
    "isolated", "aillada", "aïllada", "aislada", "square", "circular", "ISOLATED",
])
def test_isolated_shape_uses_2_5_factor(shape_label: str) -> None:
    assert schmertmann_E_from_qc(10.0, shape_label) == pytest.approx(25.0)


@pytest.mark.parametrize("shape_label", [
    "strip", "corregudes", "corrida", "continuous", "STRIP",
])
def test_strip_shape_uses_3_5_factor(shape_label: str) -> None:
    assert schmertmann_E_from_qc(10.0, shape_label) == pytest.approx(35.0)


def test_unknown_shape_falls_back_to_isolated() -> None:
    """Unknown shape label logs a warning + returns the isolated-factor result.
    Defensive: never crash, never silently skip."""
    assert schmertmann_E_from_qc(10.0, "blueprint_typo") == pytest.approx(25.0)


def test_E_from_qc_clamps_negative_qc_to_zero() -> None:
    assert schmertmann_E_from_qc(-5.0, "isolated") == 0.0


# ---------------------------------------------------------------------------
# Full chain: N → qc → E
# ---------------------------------------------------------------------------

def test_full_chain_square_footing_linyola() -> None:
    """Linyola (N=18.8, llim argilós, n=1.25, square footing):
        qc = 1.25 × 18.8 = 23.5
        E  = 2.5  × 23.5 = 58.75 kg/cm²
    (Eva's observed E for llims argilosos ≈ 100 — pipeline will still be
    low, but this is the method Eva's reports describe. The gap between
    58.75 and 100 is Eva's professional adjustment, not an algorithmic
    error in our chain.)"""
    E = schmertmann_E_from_nspt(18.8, 1.25, "isolated")
    assert E == pytest.approx(58.75)


def test_full_chain_strip_footing_uses_3_5() -> None:
    E = schmertmann_E_from_nspt(20, 2.0, "strip")
    assert E == pytest.approx(140.0)   # 3.5 × 2.0 × 20


# ---------------------------------------------------------------------------
# Deprecation alias: schmertmann_n_phi → phi_from_nspt_silty_empirical
# ---------------------------------------------------------------------------

def test_schmertmann_n_phi_alias_forwards() -> None:
    """Old name keeps working during migration; returns the new name's value."""
    assert schmertmann_n_phi(22.6, 1.25) == pytest.approx(
        phi_from_nspt_silty_empirical(22.6, 1.25)
    )


def test_phi_helper_linyola_empirical_calibration() -> None:
    """The empirical φ helper still hits Linyola's 28° at n=1.25 — that
    calibration hasn't changed, only the name + docstring."""
    assert abs(phi_from_nspt_silty_empirical(22.6, 1.25) - 28.0) <= 1.0
