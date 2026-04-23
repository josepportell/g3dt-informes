"""Tests for automation.dpsh_segmenter.segment_by_n20_step.

Covers Alcoletge-style step profiles, uniform profiles, single-test
edge cases, empty input, and two-close-boundaries tiebreaker.

Ref: docs/PLA-ACCIO-2-BIFURCACIO-2026-04-23.md §2.1.
"""
from __future__ import annotations

from automation.dpsh_extractor import DPSHData, DPSHReading, DPSHTest
from automation.dpsh_segmenter import segment_by_n20_step


def _make_dpsh(
    tests_readings: list[list[tuple[float, int]]],
) -> DPSHData:
    tests = []
    for i, readings in enumerate(tests_readings, start=1):
        drs = [
            DPSHReading(depth_m=-d, n20=int(n), nb=n / 0.83)
            for d, n in readings
        ]
        tests.append(DPSHTest(test_id=f'P-{i}', readings=drs))
    return DPSHData(expedient='TEST', tests=tests)


def test_empty_dpsh_returns_empty():
    dpsh = DPSHData(expedient='TEST', tests=[])
    assert segment_by_n20_step(dpsh) == []


def test_single_test_returns_single_wrap():
    dpsh = _make_dpsh([[(0.2, 5), (0.4, 6), (0.6, 5), (1.4, 30)]])
    layers = segment_by_n20_step(dpsh)
    assert len(layers) == 1
    assert layers[0]['depth_from_m'] == 0.0
    assert layers[0]['depth_to_m'] is None
    assert 'single layer' in layers[0]['description'].lower()


def test_too_few_readings_returns_single_wrap():
    dpsh = _make_dpsh([[(0.2, 5)], [(0.2, 4)]])
    layers = segment_by_n20_step(dpsh)
    assert len(layers) == 1


def test_uniform_high_n20_no_step():
    dpsh = _make_dpsh([
        [(0.2, 30), (0.4, 32), (0.6, 31), (0.8, 33), (1.0, 32), (1.2, 30)],
        [(0.2, 28), (0.4, 30), (0.6, 29), (0.8, 31), (1.0, 30), (1.2, 29)],
    ])
    layers = segment_by_n20_step(dpsh)
    assert len(layers) == 1
    assert 'no step' in layers[0]['description'].lower()


def test_alcoletge_clear_step():
    """Alcoletge real shape: soft top ~2-5, then jump to ~12-14.

    Uses simplified synthetic values matching the real Alcoletge
    P-2/P-3 DPSH data. Boundary is expected in the step zone
    between 1.0 m and 1.3 m.
    """
    dpsh = _make_dpsh([
        [(0.2, 5), (0.4, 2), (0.6, 4), (0.8, 9), (1.0, 9), (1.2, 12), (1.4, 14)],
        [(0.2, 5), (0.4, 5), (0.6, 2), (0.8, 4), (1.0, 9), (1.2, 14), (1.4, 13)],
    ])
    layers = segment_by_n20_step(dpsh)
    assert len(layers) >= 2
    assert layers[0]['depth_from_m'] == 0.0
    assert 0.7 <= layers[0]['depth_to_m'] <= 1.3
    last = layers[-1]
    assert last['depth_to_m'] is None
    assert layers[0]['n20_average'] < last['n20_average']


def test_refusal_readings_ignored_for_step_detection():
    """100 blow counts are refusal, not step evidence."""
    dpsh = _make_dpsh([
        [(0.2, 3), (0.4, 4), (0.6, 3), (0.8, 100)],
        [(0.2, 4), (0.4, 3), (0.6, 2), (0.8, 100)],
    ])
    layers = segment_by_n20_step(dpsh)
    assert len(layers) == 1


def test_single_test_step_not_corroborated():
    """One test has step, other is uniform soft → no step (needs 2+ tests)."""
    dpsh = _make_dpsh([
        [(0.2, 3), (0.4, 4), (0.6, 5), (0.8, 25), (1.0, 28), (1.2, 30)],
        [(0.2, 3), (0.4, 4), (0.6, 3), (0.8, 4), (1.0, 3), (1.2, 4)],
    ])
    layers = segment_by_n20_step(dpsh)
    assert len(layers) == 1


def test_two_close_boundaries_pick_more_pronounced():
    """Candidates at 1.0m (delta 5) and 1.2m (delta 12) within 0.5m → pick 1.2."""
    dpsh = _make_dpsh([
        [(0.2, 2), (0.4, 3), (0.6, 3), (0.8, 4), (1.0, 8), (1.2, 20), (1.4, 22)],
        [(0.2, 3), (0.4, 2), (0.6, 4), (0.8, 3), (1.0, 7), (1.2, 19), (1.4, 21)],
    ])
    layers = segment_by_n20_step(dpsh)
    assert len(layers) == 2
    assert abs(layers[0]['depth_to_m'] - 1.2) < 0.05


def test_layer_avg_excludes_refusal_but_averages_remainder():
    dpsh = _make_dpsh([
        [(0.2, 3), (0.4, 4), (0.6, 3), (0.8, 4), (1.2, 20), (1.4, 22), (1.6, 100)],
        [(0.2, 4), (0.4, 3), (0.6, 4), (0.8, 3), (1.2, 21), (1.4, 23), (1.6, 100)],
    ])
    layers = segment_by_n20_step(dpsh)
    assert len(layers) == 2
    assert layers[1]['n20_average'] < 50


def test_output_schema_matches_sondeig_layers():
    dpsh = _make_dpsh([
        [(0.2, 3), (0.4, 4), (0.6, 3), (0.8, 4), (1.2, 20), (1.4, 22)],
        [(0.2, 3), (0.4, 4), (0.6, 3), (0.8, 4), (1.2, 20), (1.4, 22)],
    ])
    layers = segment_by_n20_step(dpsh)
    for layer in layers:
        assert set(layer.keys()) == {
            'depth_from_m', 'depth_to_m', 'n20_average',
            'description', 'soil_type',
        }
        assert isinstance(layer['depth_from_m'], float)
        assert layer['depth_to_m'] is None or isinstance(layer['depth_to_m'], float)
        assert isinstance(layer['n20_average'], float)
        assert isinstance(layer['description'], str)
        assert layer['soil_type'] is None
