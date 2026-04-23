"""Regression tests for CTE building classification (Fix #1, Action 2).

Per CTE DB SE-C, the C-0/C-1 boundary is floor count only. Parcel area is
NOT a discriminator. Rubí (1 floor, 951 m2 parcel) must be C-0, per Eva's
signed report.
"""

from automation.cte_classifier import classify_building


def test_rubi_single_floor_large_parcel_is_c0():
    # Rubí regression: 1 floor, 951 m2 parcel must be C-0 (was C-1 bug).
    assert classify_building(floors=1, area_m2=951) == "C-0"


def test_single_floor_small_parcel_is_c0():
    assert classify_building(floors=1, area_m2=50) == "C-0"


def test_two_floors_small_parcel_is_c1():
    assert classify_building(floors=2, area_m2=50) == "C-1"


def test_two_floors_large_parcel_is_c1():
    assert classify_building(floors=2, area_m2=951) == "C-1"


def test_eleven_floors_is_c2():
    assert classify_building(floors=11, area_m2=500) == "C-2"


def test_single_floor_area_100_no_longer_promotes():
    # Explicit: area=100 used to trigger C-1 promotion; no longer.
    assert classify_building(floors=1, area_m2=100) == "C-0"
