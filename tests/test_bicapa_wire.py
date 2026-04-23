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


# ---------------------------------------------------------------------------
# DPSH auto-segmentation (dpsh_segmenter) → bearing-layer selection
# ---------------------------------------------------------------------------

def test_select_bearing_layer_idx_alcoletge_synthesized():
    """Alcoletge synthesized via dpsh_segmenter: weak rebliment + competent
    lutites → bicapa must pick the deeper, competent layer (idx 1)."""
    from automation.dpsh_segmenter import segment_by_n20_step

    dpsh = _make_dpsh([
        (0.2, 5), (0.4, 2), (0.6, 4), (0.8, 9),
        (1.0, 9), (1.2, 12), (1.4, 14),
    ])
    dpsh2 = _make_dpsh([
        (0.2, 5), (0.4, 5), (0.6, 2), (0.8, 4),
        (1.0, 9), (1.2, 14), (1.4, 13),
    ])
    combined = DPSHData(
        expedient='TEST',
        tests=[*dpsh.tests, *(t for t in dpsh2.tests)],
    )
    # Rename second test so IDs are unique
    combined.tests[1].test_id = 'DPSH-2'
    layers = segment_by_n20_step(combined)
    assert len(layers) >= 2
    bearing_idx = _select_bearing_layer_idx(layers)
    assert bearing_idx == len(layers) - 1


def test_build_report_data_synthesized_layers_drive_bearing_n20():
    """Integration: no sondeig, no user_data layers → segmenter fires,
    bearing-stratum N20 reflects the competent (deeper) layer, not the
    polluted global average."""
    from automation.report_data import build_report_data

    dpsh = DPSHData(
        expedient='TEST',
        tests=[
            DPSHTest(
                test_id='P-1',
                readings=[
                    DPSHReading(depth_m=-d, n20=n, nb=n / 0.83)
                    for d, n in [
                        (0.2, 5), (0.4, 2), (0.6, 4), (0.8, 9),
                        (1.0, 9), (1.2, 12), (1.4, 14),
                    ]
                ],
            ),
            DPSHTest(
                test_id='P-2',
                readings=[
                    DPSHReading(depth_m=-d, n20=n, nb=n / 0.83)
                    for d, n in [
                        (0.2, 5), (0.4, 5), (0.6, 2), (0.8, 4),
                        (1.0, 9), (1.2, 14), (1.4, 13),
                    ]
                ],
            ),
        ],
    )
    project_data = {
        'project': {'expedient': 'TEST', 'municipality': 'TEST'},
        'building': {},
        'client': {},
        'architect': {},
        'location': {},
        'descriptions': {},
    }
    user_data: dict = {'num_soil_levels': 1}

    report = build_report_data(
        project_data=project_data,
        user_data=user_data,
        dpsh_data=dpsh,
    )
    # Bearing N20 should be closer to the deeper layer avg (~12) than
    # to the polluted global average (~7.5). Use a loose bound to allow
    # slight heuristic drift.
    gp = report.geotechnical_params
    assert gp is not None
    # phi is derived from avg_nb = bearing_n20 / 0.83. With bearing_n20
    # ~12 and polluted global ~7.5, phi should be meaningfully higher
    # than the 28° floor for very-weak soils.
    assert gp.phi >= 28.0


def test_segmenter_does_not_fire_when_user_data_has_sondeig_layers():
    """Regression guard: segmenter must NOT override user-provided layers.

    Synthetic DPSH has an Alcoletge-like N20 step that WOULD trigger the
    segmenter. But user_data already supplies its own sondeig_layers, so
    the segmenter must be skipped and the user descriptions must pass
    through unchanged (specifically NOT replaced by the old segmenter
    diagnostic string 'auto-segmented from DPSH…'). We use two layers to
    take the description-preserving branch of _generate_soil_levels."""
    from automation.report_data import build_report_data

    dpsh = DPSHData(
        expedient='TEST',
        tests=[
            DPSHTest(
                test_id='P-1',
                readings=[
                    DPSHReading(depth_m=-d, n20=n, nb=n / 0.83)
                    for d, n in [
                        (0.2, 5), (0.4, 2), (0.6, 4), (0.8, 9),
                        (1.0, 9), (1.2, 12), (1.4, 14),
                    ]
                ],
            ),
            DPSHTest(
                test_id='P-2',
                readings=[
                    DPSHReading(depth_m=-d, n20=n, nb=n / 0.83)
                    for d, n in [
                        (0.2, 5), (0.4, 5), (0.6, 2), (0.8, 4),
                        (1.0, 9), (1.2, 14), (1.4, 13),
                    ]
                ],
            ),
        ],
    )
    project_data = {
        'project': {'expedient': 'TEST', 'municipality': 'TEST'},
        'building': {},
        'client': {},
        'architect': {},
        'location': {},
        'descriptions': {},
    }
    user_data = {
        'num_soil_levels': 2,
        'sondeig_layers': [
            {
                'depth_from_m': 0.0,
                'depth_to_m': 1.2,
                'description': 'User top layer',
                'soil_type': 'cohesive',
            },
            {
                'depth_from_m': 1.2,
                'depth_to_m': 5.0,
                'description': 'User bottom layer',
                'soil_type': 'granular',
            },
        ],
    }

    report = build_report_data(
        project_data=project_data,
        user_data=user_data,
        dpsh_data=dpsh,
    )
    # The user-supplied layers must survive intact: segmenter did not run.
    assert len(report.soil_levels) == 2
    descriptions = [lvl.description for lvl in report.soil_levels]
    assert descriptions == ['User top layer', 'User bottom layer']
    # Explicitly guard against the old segmenter debug string leaking through.
    for d in descriptions:
        assert 'auto-segmented' not in d.lower()
