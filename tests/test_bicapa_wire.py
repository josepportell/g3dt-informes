"""Regression tests for G.5-wire: bicapa helpers integrated into the pipeline.

Verifies that `_bearing_stratum_n20` + `_select_bearing_layer_idx`
correctly apply Eva's skip-soft-top rule in `automation/report_data.py`,
and that `build_report_data` wires the bearing-layer description/soil
type into the geotechnical params path.

Key fixture: Alcoletge-style profile (1st = rebliment, 2nd = lutites),
where the bearing layer must be index 1 per Eva's informe."""
from __future__ import annotations

from automation.dpsh_extractor import DPSHData, DPSHReading, DPSHTest
from automation.report_data import (
    _bearing_stratum_n20,
    _select_bearing_layer_idx,
)


def _make_dpsh(readings_by_depth: list[tuple[float, float]]) -> DPSHData:
    """Build a minimal DPSHData from (depth_m, n20) pairs. Depths negative."""
    readings = [
        DPSHReading(depth_m=-d, n20=int(n), nb=n / 0.83)
        for d, n in readings_by_depth
    ]
    test = DPSHTest(test_id='DPSH-1', readings=readings)
    return DPSHData(expedient='TEST', tests=[test])


# ---------------------------------------------------------------------------
# _select_bearing_layer_idx — Eva's skip-soft-top rule on dict layers
# ---------------------------------------------------------------------------

def test_select_bearing_layer_idx_alcoletge_profile():
    """Alcoletge: rebliment (1.3m) + lutites → picks lutites (idx 1)."""
    sondeig_layers = [
        {
            'depth_from_m': 0.0, 'depth_to_m': 1.3,
            'description': 'Sorres argiloses de rebliment',
            'n20_average': 0.0,
        },
        {
            'depth_from_m': 1.3, 'depth_to_m': 5.0,
            'description': 'Lutites i sorrenques alterades',
            'n20_average': 20.0,
        },
    ]
    assert _select_bearing_layer_idx(sondeig_layers) == 1


def test_select_bearing_layer_idx_single_layer():
    """Single-layer profile returns 0."""
    layers = [{
        'depth_from_m': 0.0, 'depth_to_m': 5.0,
        'description': 'Graves sorrenques', 'n20_average': 25.0,
    }]
    assert _select_bearing_layer_idx(layers) == 0


def test_select_bearing_layer_idx_empty():
    assert _select_bearing_layer_idx([]) == 0


def test_select_bearing_layer_idx_homogeneous_profile_picks_deepest():
    """Two competent layers → deepest competent is layer 1 (bearing stratum)."""
    layers = [
        {'depth_from_m': 0.0, 'depth_to_m': 2.0,
         'description': 'Graves compactes', 'n20_average': 30.0},
        {'depth_from_m': 2.0, 'depth_to_m': 5.0,
         'description': 'Bretxes carbonatades', 'n20_average': 50.0},
    ]
    # Both layers competent → pick deepest (bearing stratum under footing).
    assert _select_bearing_layer_idx(layers) == 1


# ---------------------------------------------------------------------------
# _bearing_stratum_n20 — N20 averaged inside the chosen bearing layer only
# ---------------------------------------------------------------------------

def test_bearing_stratum_n20_filters_to_bearing_layer():
    """Rebliment depth 0-1.3m has low N; lutites depth 1.3-5m has high N.
    Average should reflect only the bearing (lutites) zone."""
    dpsh = _make_dpsh([
        (0.2, 2),   # in rebliment
        (0.6, 3),   # in rebliment
        (1.0, 4),   # in rebliment
        (1.6, 20),  # in lutites
        (2.2, 22),  # in lutites
        (3.0, 25),  # in lutites
    ])
    sondeig = [
        {'depth_from_m': 0.0, 'depth_to_m': 1.3,
         'description': 'Rebliment', 'n20_average': 3.0},
        {'depth_from_m': 1.3, 'depth_to_m': 5.0,
         'description': 'Lutites alterades', 'n20_average': 22.3},
    ]
    result = _bearing_stratum_n20(dpsh, sondeig)
    # Only bearing-layer readings: (20+22+25)/3 ≈ 22.33
    assert abs(result - 22.33) < 0.1


def test_bearing_stratum_n20_falls_back_to_global_if_no_readings_in_bearing():
    """DPSH stopped in rebliment — bearing layer has no readings →
    fall back to global average rather than returning 0."""
    dpsh = _make_dpsh([(0.2, 2), (0.6, 3)])
    sondeig = [
        {'depth_from_m': 0.0, 'depth_to_m': 1.3,
         'description': 'Rebliment'},
        {'depth_from_m': 1.3, 'depth_to_m': 5.0,
         'description': 'Lutites alterades', 'n20_average': 22.0},
    ]
    result = _bearing_stratum_n20(dpsh, sondeig)
    # No readings in [1.3, 5.0] → global (2+3)/2 = 2.5
    assert abs(result - 2.5) < 0.01


def test_bearing_stratum_n20_single_layer_returns_global():
    dpsh = _make_dpsh([(0.2, 10), (1.0, 20), (2.0, 30)])
    sondeig = [{'depth_from_m': 0.0, 'depth_to_m': 5.0,
                'description': 'Graves', 'n20_average': 20.0}]
    result = _bearing_stratum_n20(dpsh, sondeig)
    assert abs(result - 20.0) < 0.01


# ---------------------------------------------------------------------------
# Regression: Bell-Lloc-shape profile (all-competent multi-layer) must pick
# the DEEPEST competent layer, not the shallowest. Previously the helper
# delegated to bicapa.select_bearing_layer which returns the first competent
# layer — wrong for Eva's convention on flagship reference projects.
# ---------------------------------------------------------------------------

def test_select_bearing_layer_idx_bell_lloc_shape_picks_deepest():
    """Bell-Lloc shape: 2 granular layers (0-1.6m, 1.6-1.8m), both competent.
    Eva computes Qa on the DEEPEST layer (bearing stratum). Helper MUST
    return idx=1, not idx=0."""
    layers = [
        {
            'depth_from_m': 0.0, 'depth_to_m': 1.6,
            'description': 'Graves en matriu sorrenca',
            'n20_average': 20.0,
        },
        {
            'depth_from_m': 1.6, 'depth_to_m': 1.8,
            'description': 'Graves carbonatades',
            'n20_average': 50.0,
        },
    ]
    assert _select_bearing_layer_idx(layers) == 1
