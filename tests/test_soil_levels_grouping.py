"""Tests for geological-level grouping in _generate_soil_levels.

Covers the bug #2 fix (docs/BUG-NIVELLS-GEOLOGICS-ANALISI.md): the report
must produce one SoilLevel per *geological level* (grouping sondeig_layers by
their 'geological_level' field) instead of collapsing to 1 whenever
num_levels < len(sondeig_layers).

Design: Option A — geological_level is ground-truth for the count;
num_soil_levels only acts as a downward override.
"""
from __future__ import annotations

from automation.dpsh_extractor import DPSHData, DPSHReading, DPSHTest
from automation.report_data import (
    _generate_soil_levels,
    _group_layers_by_geological_level,
)


def _make_dpsh(readings: list[tuple[float, int]]) -> DPSHData:
    """Build a single-test DPSHData from (depth_m, n20) pairs. Depths negative."""
    drs = [DPSHReading(depth_m=-d, n20=int(n), nb=n / 0.83) for d, n in readings]
    return DPSHData(expedient='TEST', tests=[DPSHTest(test_id='P-1', readings=drs)])


# ---------------------------------------------------------------------------
# _group_layers_by_geological_level
# ---------------------------------------------------------------------------

def test_group_consecutive_runs():
    layers = [{'geological_level': gl} for gl in (1, 1, 2, 3, 3)]
    assert _group_layers_by_geological_level(layers) == [[0, 1], [2], [3, 4]]


def test_group_all_same_level():
    layers = [{'geological_level': 1}, {'geological_level': 1}]
    assert _group_layers_by_geological_level(layers) == [[0, 1]]


def test_group_returns_none_when_value_is_none():
    layers = [{'geological_level': 1}, {'geological_level': None}]
    assert _group_layers_by_geological_level(layers) is None


def test_group_returns_none_when_field_missing():
    layers = [{'geological_level': 1}, {'description': 'graves'}]
    assert _group_layers_by_geological_level(layers) is None


# ---------------------------------------------------------------------------
# _generate_soil_levels — Tulipa-style (5 materials, gl [1,1,2,3,3] -> 3 levels)
# ---------------------------------------------------------------------------

def _tulipa_layers() -> list[dict]:
    return [
        {'depth_from_m': 0.0, 'depth_to_m': 1.0, 'description': 'sorres llimoses A', 'geological_level': 1},
        {'depth_from_m': 1.0, 'depth_to_m': 2.0, 'description': 'sorres llimoses B', 'geological_level': 1},
        {'depth_from_m': 2.0, 'depth_to_m': 3.5, 'description': 'llims argilosos', 'geological_level': 2},
        {'depth_from_m': 3.5, 'depth_to_m': 4.5, 'description': 'substrat alterat A', 'geological_level': 3},
        {'depth_from_m': 4.5, 'depth_to_m': 5.5, 'description': 'substrat alterat B', 'geological_level': 3},
    ]


def test_generate_three_geological_levels():
    dpsh = _make_dpsh([(d / 10, 10 + d) for d in range(2, 62, 2)])  # 0.2..6.0m
    layers = _tulipa_layers()
    result = _generate_soil_levels(dpsh, num_levels=3, sondeig_layers=layers)

    assert len(result) == 3
    # Each level's description/depths come from its group's deepest (bearing) layer.
    assert result[0].description == 'sorres llimoses B'   # idx 1
    assert result[1].description == 'llims argilosos'     # idx 2
    assert result[2].description == 'substrat alterat B'  # idx 4
    # Group depth spans: from first layer's top to last layer's bottom.
    assert result[0].depth_from_m == 0.0
    assert result[0].depth_to_m == 2.0
    assert result[1].depth_from_m == 2.0
    assert result[1].depth_to_m == 3.5
    assert result[2].depth_from_m == 3.5
    assert result[2].depth_to_m == 5.5
    assert [lvl.level_number for lvl in result] == [1, 2, 3]


# ---------------------------------------------------------------------------
# _generate_soil_levels — Bell-Lloc-style (2 materials both gl=1 -> 1 level)
# ---------------------------------------------------------------------------

def test_generate_single_level_when_one_group():
    dpsh = _make_dpsh([(d / 10, 30 + d) for d in range(2, 42, 2)])  # 0.2..4.0m
    layers = [
        {'depth_from_m': 0.0, 'depth_to_m': 1.0, 'description': 'graves sorrenca', 'geological_level': 1},
        {'depth_from_m': 1.0, 'depth_to_m': 4.0, 'description': 'graves carbonatades', 'geological_level': 1},
    ]
    result = _generate_soil_levels(dpsh, num_levels=1, sondeig_layers=layers)

    assert len(result) == 1
    assert result[0].level_number == 1
    # Collapse uses the deepest layer's description (bearing material).
    assert result[0].description == 'graves carbonatades'


# ---------------------------------------------------------------------------
# _generate_soil_levels — downward override (3 groups but num_levels=1 -> 1)
# ---------------------------------------------------------------------------

def test_generate_override_collapses_to_one():
    dpsh = _make_dpsh([(d / 10, 10 + d) for d in range(2, 62, 2)])
    layers = _tulipa_layers()
    result = _generate_soil_levels(dpsh, num_levels=1, sondeig_layers=layers)

    assert len(result) == 1
    assert result[0].level_number == 1
    assert result[0].description == 'substrat alterat B'  # deepest layer overall


# ---------------------------------------------------------------------------
# _generate_soil_levels — defensive guard: non-last group with depth_to_m=None
# ---------------------------------------------------------------------------

def test_generate_handles_none_depth_to_in_non_last_group():
    """A non-last group whose deepest layer has depth_to_m=None must NOT crash.

    Before the guard, `abs(r.depth_m) <= None` raised TypeError in the N20
    comprehension. The upper bound is simply dropped (treated as unbounded),
    same as the last group, and grouping still yields one level per group.
    """
    dpsh = _make_dpsh([(d / 10, 10 + d) for d in range(2, 62, 2)])  # 0.2..6.0m
    layers = [
        # group 1 (non-last): deepest layer has no lower bound -> depth_to_m=None
        {'depth_from_m': 0.0, 'depth_to_m': 1.0, 'description': 'sorres A', 'geological_level': 1},
        {'depth_from_m': 1.0, 'depth_to_m': None, 'description': 'sorres B', 'geological_level': 1},
        # group 2 (last)
        {'depth_from_m': 2.0, 'depth_to_m': 4.0, 'description': 'substrat', 'geological_level': 2},
    ]
    result = _generate_soil_levels(dpsh, num_levels=2, sondeig_layers=layers)

    assert len(result) == 2
    assert [lvl.level_number for lvl in result] == [1, 2]
    # depth_to_m=None on the bearing layer -> level reports None upper bound + no thickness
    assert result[0].depth_to_m is None
    assert result[0].thickness_m is None
    assert result[1].description == 'substrat'
