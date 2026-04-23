"""DPSH-based auto-segmentation of sondeig layers.

When a project has no sondeig file or the extracted sondeig has no
layers, synthesize sondeig_layers from DPSH data by detecting an N20
step-change. Used by build_report_data as a fallback so Eva's
bearing-stratum rule (skip-soft-top) still operates correctly on
projects like Alcoletge (rebliment 0-1.2m + lutites 1.2-5m) and
Linyola (handwritten field sheets without a formal log annex).

Ref: docs/PLA-ACCIO-2-BIFURCACIO-2026-04-23.md §2.1.
"""
from __future__ import annotations

import logging

from .dpsh_extractor import DPSHData

logger = logging.getLogger(__name__)


_REFUSAL_N20 = 100
_STEP_MIN_DELTA = 3.0
_STEP_BELOW_MAX_MEAN = 10.0
_STEP_WINDOW_M = 0.4
_MIN_CORROBORATING_TESTS = 2


def _non_refusal_readings(dpsh_data: DPSHData) -> list[tuple[str, float, int]]:
    """Flatten (test_id, abs_depth, n20) excluding refusal readings."""
    out: list[tuple[str, float, int]] = []
    for test in dpsh_data.tests:
        for r in test.readings:
            if r.n20 is None or r.n20 >= _REFUSAL_N20:
                continue
            out.append((test.test_id, abs(r.depth_m), int(r.n20)))
    return out


def _all_readings(dpsh_data: DPSHData) -> list[tuple[str, float, int]]:
    """Flatten (test_id, abs_depth, n20) including refusal readings."""
    out: list[tuple[str, float, int]] = []
    for test in dpsh_data.tests:
        for r in test.readings:
            if r.n20 is None:
                continue
            out.append((test.test_id, abs(r.depth_m), int(r.n20)))
    return out


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _find_boundaries(readings: list[tuple[str, float, int]]) -> list[tuple[float, float]]:
    """Return candidate boundaries as (depth, delta) sorted by depth.

    A boundary at depth d is valid if:
    - Mean N20 in [d - window, d) < _STEP_BELOW_MAX_MEAN
    - Mean N20 in [d, d + window) >= mean_below + _STEP_MIN_DELTA
    - At least _MIN_CORROBORATING_TESTS exhibit the step individually
    """
    depths = sorted({round(d, 2) for _, d, _ in readings})
    boundaries: list[tuple[float, float]] = []
    for d in depths:
        below = [n for _, dd, n in readings if d - _STEP_WINDOW_M <= dd < d]
        above = [n for _, dd, n in readings if d <= dd < d + _STEP_WINDOW_M]
        if len(below) < 2 or len(above) < 2:
            continue
        mean_below = _mean(below)
        mean_above = _mean(above)
        if mean_below >= _STEP_BELOW_MAX_MEAN:
            continue
        delta = mean_above - mean_below
        if delta < _STEP_MIN_DELTA:
            continue
        tests_with_step = 0
        test_ids = {tid for tid, _, _ in readings}
        for tid in test_ids:
            t_below = [n for ttid, dd, n in readings
                       if ttid == tid and d - _STEP_WINDOW_M <= dd < d]
            t_above = [n for ttid, dd, n in readings
                       if ttid == tid and d <= dd < d + _STEP_WINDOW_M]
            if not t_below or not t_above:
                continue
            if _mean(t_above) - _mean(t_below) >= _STEP_MIN_DELTA:
                tests_with_step += 1
        if tests_with_step < _MIN_CORROBORATING_TESTS:
            continue
        boundaries.append((d, delta))
    return boundaries


def _prune_close_boundaries(
    boundaries: list[tuple[float, float]],
    min_gap_m: float = 0.5,
) -> list[float]:
    """When two candidates are within min_gap, keep the more pronounced."""
    if not boundaries:
        return []
    by_depth = sorted(boundaries, key=lambda b: b[0])
    kept: list[tuple[float, float]] = []
    for depth, delta in by_depth:
        if kept and depth - kept[-1][0] < min_gap_m:
            if delta > kept[-1][1]:
                kept[-1] = (depth, delta)
            continue
        kept.append((depth, delta))
    return [d for d, _ in kept]


def _layer_avg_n20(
    readings_all: list[tuple[str, float, int]],
    depth_from: float,
    depth_to: float | None,
) -> float:
    vals = [n for _, d, n in readings_all
            if d >= depth_from and (depth_to is None or d < depth_to)
            and n < _REFUSAL_N20]
    return _mean(vals) if vals else 0.0


def segment_by_n20_step(dpsh_data: DPSHData) -> list[dict]:
    """Produce sondeig_layers from DPSH by detecting N20 step-change.

    Returns list of dicts with keys:
    - depth_from_m (float, positive)
    - depth_to_m (float or None for last open-ended layer)
    - n20_average (float)
    - description (str)
    - soil_type (None, let downstream detect)

    Contract:
    - Empty DPSH: returns [].
    - Too few readings or single test: returns single-layer wrap.
    - No step detected: returns single-layer wrap.
    - Step detected: returns 2+ layers split at boundary depth.
    """
    if dpsh_data is None or not dpsh_data.tests:
        return []

    readings_nr = _non_refusal_readings(dpsh_data)
    readings_all = _all_readings(dpsh_data)

    if len(dpsh_data.tests) < 2 or len(readings_nr) < 4:
        overall = _layer_avg_n20(readings_all, 0.0, None)
        logger.info(
            "dpsh_segmenter: insufficient data (tests=%d, readings=%d) "
            "→ single-layer wrap.",
            len(dpsh_data.tests), len(readings_nr),
        )
        return [{
            'depth_from_m': 0.0,
            'depth_to_m': None,
            'n20_average': overall,
            'description': '',
            'soil_type': None,
        }]

    raw_boundaries = _find_boundaries(readings_nr)
    depths = _prune_close_boundaries(raw_boundaries)

    if not depths:
        overall = _layer_avg_n20(readings_all, 0.0, None)
        logger.info(
            "dpsh_segmenter: no N20 step detected → single-layer wrap."
        )
        return [{
            'depth_from_m': 0.0,
            'depth_to_m': None,
            'n20_average': overall,
            'description': '',
            'soil_type': None,
        }]

    logger.info(
        "dpsh_segmenter: detected N20 step boundaries at %s m.",
        ", ".join(f"{d:.2f}" for d in depths),
    )
    layers: list[dict] = []
    bounds = [0.0, *depths]
    for i, start in enumerate(bounds):
        end: float | None = bounds[i + 1] if i + 1 < len(bounds) else None
        avg = _layer_avg_n20(readings_all, start, end)
        layers.append({
            'depth_from_m': float(start),
            'depth_to_m': float(end) if end is not None else None,
            'n20_average': avg,
            'description': '',
            'soil_type': None,
        })
    return layers
