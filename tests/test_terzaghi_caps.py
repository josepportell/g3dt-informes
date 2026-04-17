"""Regression tests for Qa cap classification in TerzaghiCalculator.

Eva's professional-practice caps vary by soil category (verified against 7
reference reports):
    - Rock (c ≥ 0.5):                             cap 3.0 kg/cm²
    - Dense granular (soil_type=granular, Nb≥25): cap 3.5 kg/cm²
    - Soft / cohesive / unknown:                  cap 3.0 kg/cm²

The cohesive-aware restriction on dense-granular (2026-04-17) prevents
cohesive soils with low cohesion (e.g. Linyola llims: c=0.05, Nb>25)
from falsely triggering the 3.5 cap.
"""
from __future__ import annotations

import pytest

from automation.terzaghi_calculator import (
    FootingShape,
    TerzaghiCalculator,
)


def _calc(phi: float, cohesion: float, gamma: float, nspt: float,
          soil_type: str | None, *, B: float = 1.0, Df: float = 0.8):
    c = TerzaghiCalculator(phi=phi, cohesion=cohesion, gamma=gamma)
    return c.calculate_qa(
        B=B, Df=Df, shape=FootingShape.SQUARE,
        nspt=nspt, is_granular=(cohesion < 0.5),
        soil_type=soil_type,
    )


def test_rock_cap_is_3_regardless_of_nspt() -> None:
    """c ≥ 0.5 classifies as rock → cap 3.0, even with very high Nb."""
    r = _calc(phi=35, cohesion=1.0, gamma=2.2, nspt=60, soil_type='rock')
    assert r.Qa == pytest.approx(3.0), f"expected cap=3.0, got {r.Qa}"
    # Uncapped should be well above the cap for rock params
    assert r.Qa_uncapped > 5.0


def test_dense_granular_cap_fires_on_granular_with_nb_ge_25() -> None:
    """soil_type=granular + c<0.5 + Nb≥25 → dense-granular cap 3.5."""
    r = _calc(phi=38, cohesion=0.0, gamma=2.0, nspt=47, soil_type='granular')
    # Rubí-like: dense gravel. Uncapped Qa is typically ~5, dense cap clips to 3.5.
    assert r.Qa == pytest.approx(3.5), f"expected dense cap 3.5, got {r.Qa}"


def test_cohesive_does_not_trigger_dense_cap_even_with_nb_ge_25() -> None:
    """Regression: cohesive soil (e.g. Linyola llims) with c=0.05 + Nb>25
    must NOT get the 3.5 ceiling — cap stays at 3.0."""
    r = _calc(phi=32, cohesion=0.05, gamma=1.9, nspt=35, soil_type='cohesive')
    # With cap 3.0, Qa is min(uncapped, 3.0) or formula if below cap.
    assert r.Qa <= 3.0, f"cohesive cap must be 3.0, got {r.Qa}"


def test_soft_granular_nb_below_25_uses_soft_cap() -> None:
    """Nb<25 on granular → soft cap 3.0."""
    r = _calc(phi=30, cohesion=0.0, gamma=2.0, nspt=15, soil_type='granular')
    assert r.Qa <= 3.0
    # Formula result is typically well below 3.0 for low Nb → cap doesn't fire
    # but behaviour must not exceed 3.0.


def test_unknown_soil_type_defaults_to_soft_cap() -> None:
    """When soil_type is None / unknown, cap falls to soil default 3.0 —
    we do NOT assume granular by default to avoid silently applying 3.5."""
    r = _calc(phi=38, cohesion=0.0, gamma=2.0, nspt=40, soil_type=None)
    assert r.Qa <= 3.0, f"unknown soil_type must not fire dense cap, got {r.Qa}"
