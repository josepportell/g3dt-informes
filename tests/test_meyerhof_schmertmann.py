"""Pin the Meyerhof 1957 curves digitized from image119 + Schmertmann-n
proxy behaviour.

These helpers are NOT wired into the pipeline yet. Tests exist to lock the
published values in place so a future change is intentional.
"""
from __future__ import annotations

import pytest

from automation.cte_geomech import (
    meyerhof_phi_clean_sand,
    meyerhof_phi_silty_sand,
    peck_hanson_thornburn_phi,
    schmertmann_n_phi,
)


# ---------------------------------------------------------------------------
# Peck-Hanson-Thornburn baseline (from image119)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("n, expected_phi", [
    (5,  28.5), (10, 30.5), (15, 32.0), (20, 33.5),
    (25, 35.0), (30, 36.0), (40, 38.0), (50, 40.0), (60, 41.5),
])
def test_peck_hanson_thornburn_anchor_points(n: float, expected_phi: float) -> None:
    assert peck_hanson_thornburn_phi(n) == pytest.approx(expected_phi)


# ---------------------------------------------------------------------------
# Meyerhof clean sand (<5% fines) — maps to Schmertmann n=2.5
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("n, expected_phi", [
    (5,  29.5), (10, 32.5), (15, 34.5), (20, 36.0),
    (25, 37.5), (30, 39.0), (40, 41.0), (50, 42.5), (60, 44.0),
])
def test_meyerhof_clean_sand_anchor_points(n: float, expected_phi: float) -> None:
    assert meyerhof_phi_clean_sand(n) == pytest.approx(expected_phi)


def test_meyerhof_clean_sand_interpolates_between_anchors() -> None:
    # Halfway between N=20 (36°) and N=25 (37.5°) → 36.75°
    assert meyerhof_phi_clean_sand(22.5) == pytest.approx(36.75)


# ---------------------------------------------------------------------------
# Meyerhof silty sand (>5% fines) — maps to Schmertmann n=2.0
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("n, expected_phi", [
    (5,  26.5), (10, 29.0), (15, 30.0), (20, 31.0),
    (25, 32.0), (30, 33.0), (40, 35.0), (50, 37.0), (60, 38.0),
])
def test_meyerhof_silty_sand_anchor_points(n: float, expected_phi: float) -> None:
    assert meyerhof_phi_silty_sand(n) == pytest.approx(expected_phi)


def test_table_edges_clamp() -> None:
    """N below the lowest anchor or above the highest clamps to the endpoint."""
    assert meyerhof_phi_clean_sand(0) == 29.5        # clamped to N=5 value
    assert meyerhof_phi_clean_sand(200) == 44.0      # clamped to N=60 value


# ---------------------------------------------------------------------------
# Schmertmann-n dispatch: ordering + key values
# ---------------------------------------------------------------------------

def test_schmertmann_n25_matches_meyerhof_clean() -> None:
    for n in (5, 10, 20, 30, 50):
        assert schmertmann_n_phi(n, 2.5) == pytest.approx(meyerhof_phi_clean_sand(n))


def test_schmertmann_n20_matches_meyerhof_silty() -> None:
    for n in (5, 10, 20, 30, 50):
        assert schmertmann_n_phi(n, 2.0) == pytest.approx(meyerhof_phi_silty_sand(n))


def test_schmertmann_n125_is_silty_minus_3() -> None:
    """The n=1.25 case is deliberately set 3° below the Meyerhof >5% curve.
    This is the extrapolation calibrated to Linyola (Nb=22.6 → 28°)."""
    for n in (10, 20, 30):
        expected = meyerhof_phi_silty_sand(n) - 3.0
        assert schmertmann_n_phi(n, 1.25) == pytest.approx(expected)


def test_schmertmann_monotonic_in_n() -> None:
    """For any fixed N, φ must increase monotonically with n (coarser → stiffer)."""
    N = 22.6   # Linyola-like
    phis = [schmertmann_n_phi(N, n) for n in (1.25, 1.5, 1.75, 2.0, 2.25, 2.5)]
    for a, b in zip(phis, phis[1:]):
        assert a <= b, f"monotonicity violated: {phis}"


def test_linyola_regression_value() -> None:
    """Linyola Nb=22.6, Eva φ=28°. With n=1.25 (sandy silt) the helper should
    reach Eva's value within ±1°. This is the single data point the
    extrapolation was calibrated to — if this breaks, Eva's answer on n
    has come in and the calibration should be revisited.

    ±1° tolerance acknowledges the chart-read precision on the underlying
    Meyerhof 1957 curves; tightening this further would imply precision the
    source material doesn't have."""
    phi = schmertmann_n_phi(22.6, 1.25)
    assert abs(phi - 28.0) <= 1.0, f"Linyola target drift: {phi}"


def test_n_clamps_out_of_range() -> None:
    """n<1.0 or n>3.0 should still return a number (not crash)."""
    # Very silty (clay-like) → should return low φ but non-negative
    assert schmertmann_n_phi(20, 0.5) >= 0.0
    # Very granular → should not exceed clean-sand value by much
    assert schmertmann_n_phi(20, 5.0) == pytest.approx(meyerhof_phi_clean_sand(20))
