"""Regression tests for refusal-safe SPT normalization in vision_normalizer.

Rationale: the vision model emits a non-numeric blow value like "50R" when an
SPT test hits refusal (e.g. blows: [19, 32, "50R"], n_spt: null). The old
n_spt summation did `blows[1] + blows[2]` → `32 + "50R"` → TypeError. That
crash was swallowed by `except Exception: pass` in load_sondeig_merged(),
discarding the entire sondeig annex (which holds the authoritative
num_geological_levels) and forcing the wizard back to 1 geological level —
the "detects 1 level instead of 3" bug Eva reported on almost every project.

These tests pin the refusal-safe behaviour: no crash, n_spt stays None (not
fabricated), the "50R" blow is preserved for display, and the normal
all-numeric path still computes n_spt identically.
"""
from __future__ import annotations

import logging

from automation.vision_normalizer import (
    load_sondeig_merged,
    normalize_dpsh,
    normalize_sondeig,
)


def test_sondeig_refusal_blow_does_not_crash_and_preserves_levels():
    """A refusal SPT ("50R") must not crash normalize_sondeig, and the annex's
    num_geological_levels must survive (this is the root-cause regression)."""
    data = {
        "sondeig_tests": [
            {
                "test_id": "S-1",
                "num_geological_levels": 3,
                "spt_results": [
                    {
                        "test_id": "SPT-2",
                        "depth_from_m": 3.0,
                        "depth_to_m": 3.54,
                        "blows": [19, 32, "50R"],
                        "n_spt": None,
                    }
                ],
            }
        ],
    }

    result = normalize_sondeig(data)  # must NOT raise

    test = result["sondeig_tests"][0]
    assert test["num_geological_levels"] == 3
    spt = test["spt_results"][0]
    # n_spt not fabricated from a refusal — stays None
    assert spt["n_spt"] is None
    # refusal notation preserved for report display (blows array untouched)
    assert spt["blows"] == [19, 32, "50R"]


def test_dpsh_refusal_blow_does_not_crash():
    """A DPSH SPT with a refusal blow must normalize without raising and keep
    the refusal notation; n_spt stays None rather than being fabricated."""
    data = {
        "spt_in_dpsh": {
            "test_id": "SPT-1",
            "blows": [12, 25, "50R"],
            "n_spt": None,
        }
    }

    result = normalize_dpsh(data)  # must NOT raise

    spt = result["spt_in_dpsh"]
    assert spt["n_spt"] is None
    assert spt["blows"] == [12, 25, "50R"]


def test_sondeig_all_numeric_blows_still_compute_n_spt():
    """All-numeric blows must compute n_spt as blows[1]+blows[2] exactly as
    before — proves the refusal guard introduces no behaviour change."""
    data = {
        "sondeig_tests": [
            {
                "test_id": "S-1",
                "spt_results": [
                    {"test_id": "SPT-1", "blows": [6, 9, 9], "n_spt": None}
                ],
            }
        ],
    }

    result = normalize_sondeig(data)

    spt = result["sondeig_tests"][0]["spt_results"][0]
    assert spt["n_spt"] == 18


def test_dpsh_all_numeric_blows_still_compute_n_spt():
    """Same as above for the DPSH path."""
    data = {
        "spt_in_dpsh": {
            "test_id": "SPT-1",
            "blows": [6, 9, 9],
            "n_spt": None,
        }
    }

    result = normalize_dpsh(data)

    assert result["spt_in_dpsh"]["n_spt"] == 18


def test_sondeig_refusal_at_index_1_does_not_crash():
    """Refusal can land on the first counted increment (blows[1], not just the
    tail blows[2]). The guard must short-circuit on either counted increment,
    leaving n_spt None — not crash on `"R" + 40`."""
    data = {
        "sondeig_tests": [
            {
                "test_id": "S-1",
                "spt_results": [
                    {"test_id": "SPT-1", "blows": [32, "R", 40], "n_spt": None}
                ],
            }
        ],
    }

    result = normalize_sondeig(data)  # must NOT raise

    spt = result["sondeig_tests"][0]["spt_results"][0]
    assert spt["n_spt"] is None
    assert spt["blows"] == [32, "R", 40]


def test_load_sondeig_merged_malformed_json_logs_warning_not_raise(tmp_path, caplog):
    """A corrupt sondeig_extracted.json must be logged (not silently swallowed)
    and must not raise — load_sondeig_merged returns a dict regardless."""
    validation_dir = tmp_path / "validation"
    validation_dir.mkdir()
    (validation_dir / "sondeig_extracted.json").write_text(
        "{ this is not valid json ]", encoding="utf-8"
    )

    with caplog.at_level(logging.WARNING):
        result = load_sondeig_merged(validation_dir)  # must NOT raise

    assert isinstance(result, dict)
    assert any(
        "Failed to load sondeig field sheet" in rec.message
        and rec.levelno == logging.WARNING
        for rec in caplog.records
    )
