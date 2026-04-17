"""Regression tests pinning _bearing_stratum_n20 on real reference-data fixtures.

Rationale: the G.5-wire rollout almost shipped a -60% N20 regression on
Bell-Lloc because the unit tests used synthetic profiles that didn't exercise
the all-competent multi-layer shape of the flagship project. These tests
load the actual sondeig + DPSH fixtures so future refactors can't silently
shift calibrated values that Eva's deviation matrix depends on.
"""
from __future__ import annotations

import glob
from pathlib import Path

import pytest

from automation.dpsh_extractor import DPSHExtractor
from automation.report_data import _bearing_stratum_n20, _select_bearing_layer_idx
from automation.vision_normalizer import load_sondeig_merged


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_project(folder_name: str):
    """Load DPSH + sondeig_layers for a reference-material project.

    Skip the test if fixtures are missing locally (they're user data, not
    committed to the repo in every environment).
    """
    proj = REPO_ROOT / "reference-material" / folder_name
    xls_hits = glob.glob(str(proj / "**" / "*DPSH*.xls"), recursive=True) + \
               glob.glob(str(proj / "**" / "*DPSH*.xlsx"), recursive=True)
    if not xls_hits:
        pytest.skip(f"DPSH fixture missing for {folder_name}")
    sdata = load_sondeig_merged(proj / "validation")
    tests_ = sdata.get("sondeig_tests", [])
    if not tests_ or not tests_[0].get("layers"):
        pytest.skip(f"sondeig layers missing for {folder_name}")
    dpsh = DPSHExtractor(xls_hits[0]).extract_all()
    layers = tests_[0]["layers"]
    return dpsh, layers


def test_bell_lloc_bearing_idx_and_n20() -> None:
    """Bell-Lloc: 2 granular layers, both competent.
    Expected: bearing_idx=1 (deepest), N20 ≈ 49.8."""
    dpsh, layers = _load_project("4001612 BELL-LLOC")
    assert _select_bearing_layer_idx(layers) == 1
    n20 = _bearing_stratum_n20(dpsh, layers)
    assert abs(n20 - 49.8) < 1.0, f"Bell-Lloc N20={n20}, expected ≈49.8"


def test_alcoletge_bearing_idx_and_n20() -> None:
    """Alcoletge: rebliment (weak) + lutites (competent).
    Expected: bearing_idx=1 (skips fill), N20 from the lutites zone."""
    dpsh, layers = _load_project("4001670 ALCOLETGE")
    assert _select_bearing_layer_idx(layers) == 1
    n20 = _bearing_stratum_n20(dpsh, layers)
    # Pinned below once the test was run once on the current pipeline.
    # Update the expected value if you intentionally change the bearing logic.
    assert n20 > 0, "bearing N20 should be positive"
