#!/usr/bin/env python3
"""
Tests for automation/geocode_coordinates.py

Offline tests run without network access.
Online integration tests require --online flag.

Usage:
    # Offline only (default)
    uv run python3 tests/test_geocode.py

    # Include online integration tests
    uv run python3 tests/test_geocode.py --online

Author: Eficients.cat
Date: 2026-02-27
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from automation.geocode_coordinates import (
    _wgs84_to_utm31n,
    _parse_address,
    distribute_points,
    generate_coordenades_txt,
)
from automation.auto_extractor import _extract_municipality


# === Test Counters ===

_passed = 0
_failed = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"  PASS  {name}")
    else:
        _failed += 1
        msg = f"  FAIL  {name}"
        if detail:
            msg += f" — {detail}"
        print(msg)


# === Offline Tests ===

def test_wgs84_to_utm31n() -> None:
    """Test WGS84 → UTM zone 31N conversion against known coordinates."""
    print("\n--- _wgs84_to_utm31n ---")

    # Bell-Lloc d'Urgell: GPS (41.6303, 0.7733) → known UTM ~(314509, 4611193)
    x, y = _wgs84_to_utm31n(41.6303, 0.7733)
    check("Bell-Lloc X in range", 314400 < x < 314600, f"got {x:.1f}")
    check("Bell-Lloc Y in range", 4611100 < y < 4611300, f"got {y:.1f}")

    # Barcelona: ~(41.3874, 2.1686) → known UTM ~(431000, 4581000)
    x, y = _wgs84_to_utm31n(41.3874, 2.1686)
    check("Barcelona X in range", 430000 < x < 432000, f"got {x:.1f}")
    check("Barcelona Y in range", 4580000 < y < 4583000, f"got {y:.1f}")

    # Lleida: ~(41.6176, 0.6260) → known UTM ~(301500, 4609700)
    x, y = _wgs84_to_utm31n(41.6176, 0.6260)
    check("Lleida X in range", 300500 < x < 302500, f"got {x:.1f}")
    check("Lleida Y in range", 4608700 < y < 4610700, f"got {y:.1f}")


def test_distribute_points() -> None:
    """Test point distribution within a polygon."""
    print("\n--- distribute_points ---")

    # Simple square polygon (20m × 20m)
    square = [
        (100.0, 100.0), (120.0, 100.0),
        (120.0, 120.0), (100.0, 120.0),
    ]

    # Single point → centroid
    result = distribute_points(square, ["P-1"])
    check("1 point at centroid X", abs(result["P-1"]["x"] - 110.0) < 0.1)
    check("1 point at centroid Y", abs(result["P-1"]["y"] - 110.0) < 0.1)

    # Two points → spread along major axis
    result = distribute_points(square, ["P-1", "P-2"])
    check("2 points different X or Y",
          result["P-1"]["x"] != result["P-2"]["x"] or
          result["P-1"]["y"] != result["P-2"]["y"])

    # Check spacing between 7-12m
    import math
    dx = result["P-1"]["x"] - result["P-2"]["x"]
    dy = result["P-1"]["y"] - result["P-2"]["y"]
    dist = math.sqrt(dx**2 + dy**2)
    check("2 points spacing 7-12m", 7.0 <= dist <= 12.0, f"got {dist:.1f}m")

    # Three points → all within polygon bbox
    result = distribute_points(square, ["P-1", "P-2", "S-1"])
    for pid, pt in result.items():
        check(f"3 pts: {pid} within bbox X",
              100.0 <= pt["x"] <= 120.0, f"x={pt['x']:.1f}")
        check(f"3 pts: {pid} within bbox Y",
              100.0 <= pt["y"] <= 120.0, f"y={pt['y']:.1f}")

    # Empty inputs
    check("empty polygon", distribute_points([], ["P-1"]) == {})
    check("empty point_ids", distribute_points(square, []) == {})

    # Elongated polygon (50m × 5m)
    narrow = [
        (100.0, 100.0), (150.0, 100.0),
        (150.0, 105.0), (100.0, 105.0),
    ]
    result = distribute_points(narrow, ["P-1", "P-2", "P-3"])
    # Points should spread along X axis (major axis)
    xs = [result[p]["x"] for p in ["P-1", "P-2", "P-3"]]
    check("narrow: points spread on major axis",
          max(xs) - min(xs) > 10.0, f"spread={max(xs)-min(xs):.1f}m")


def test_generate_coordenades_txt() -> None:
    """Test COORDENADES.txt file format."""
    print("\n--- generate_coordenades_txt ---")

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = Path(tmpdir) / "COORDENADES.txt"
        points = {
            "S-1": {"x": 314507.0, "y": 4611159.0},
            "P-1": {"x": 314487.0, "y": 4611157.0},
            "P-2": {"x": 314497.0, "y": 4611158.0},
        }
        elevations = {"P-1": 199.2, "P-2": 199.3, "S-1": 199.3}

        generate_coordenades_txt(points, elevations, out_path)
        content = out_path.read_text()
        lines = content.splitlines()

        check("header line", lines[0] == "Coordenades UTM (X);(Y);(Z);")
        check("P-1 before P-2 (sorted)", lines[1] == "P-1")
        check("P-1 coords format", "314487.0 ; 4611157.0 ; 199.2" in lines[2])
        check("blank line separator", lines[3] == "")
        check("P-2 after P-1", lines[4] == "P-2")
        check("S-1 last (sorted)", "S-1" in content.split("P-2")[1])

    # Missing elevation defaults to 0.0
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = Path(tmpdir) / "COORDENADES.txt"
        generate_coordenades_txt({"P-1": {"x": 1.0, "y": 2.0}}, {}, out_path)
        content = out_path.read_text()
        check("missing elevation → 0.0", "0.0" in content)


def test_extract_municipality() -> None:
    """Test municipality name extraction from folder names."""
    print("\n--- _extract_municipality ---")

    cases = [
        ("4001612 BELL-LLOC", "Bell-Lloc"),
        ("3001621 CASTELLAR DEL VALLES", "Castellar del Vallès"),
        ("3001631 RUBI", "Rubí"),
        ("4001607 LINYOLA", "Linyola"),
    ]

    for folder, expected in cases:
        result = _extract_municipality(Path(folder))
        check(f"'{folder}'", result == expected,
              f"expected '{expected}', got '{result}'")

    # Edge cases
    check("no number prefix", _extract_municipality(Path("BELL-LLOC")) is None)
    check("just numbers", _extract_municipality(Path("4001612")) is None)


def test_parse_address() -> None:
    """Test address parsing for Cadastre Callejero API."""
    print("\n--- _parse_address ---")

    # Basic Catalan street types
    sigla, calle, num = _parse_address("Carrer Mestre Ramon Ortiz, 5")
    check("carrer sigla", sigla == "CL")
    check("carrer calle", calle == "Mestre Ramon Ortiz")
    check("carrer numero", num == "5")

    sigla, calle, num = _parse_address("Av. Catalunya, 12")
    check("avinguda sigla", sigla == "AV")
    check("avinguda calle", calle == "Catalunya")
    check("avinguda numero", num == "12")

    # Number with letter suffix
    sigla, calle, num = _parse_address("Carrer Major, 5A")
    check("letter suffix sigla", sigla == "CL")
    check("letter suffix calle", calle == "Major")
    check("letter suffix numero", num == "5A")

    # No number
    sigla, calle, num = _parse_address("Partida Fontanals")
    check("no number sigla", sigla == "PD")
    check("no number calle", calle == "Fontanals")
    check("no number numero", num == "")

    # Plaça
    sigla, calle, num = _parse_address("Plaça Major, 1")
    check("plaça sigla", sigla == "PZ")
    check("plaça calle", calle == "Major")

    # Spanish variant
    sigla, calle, num = _parse_address("Calle Mayor, 10")
    check("calle sigla", sigla == "CL")
    check("calle name", calle == "Mayor")

    # Number without comma (trailing space + digits)
    sigla, calle, num = _parse_address("Carrer Major 3")
    check("no comma numero", num == "3")

    # Edge: empty string
    sigla, calle, num = _parse_address("")
    check("empty string", sigla == "" and calle == "" and num == "")


# === Online Integration Tests ===

def test_cadastre_address_lookup() -> None:
    """Test Cadastre Callejero address lookup (requires network)."""
    print("\n--- cadastre_address_lookup (ONLINE) ---")
    from automation.geocode_coordinates import cadastre_address_lookup, cadastre_rc_to_utm

    # Bell-Lloc: known address with house number 13 (5 doesn't exist in Cadastre)
    result = cadastre_address_lookup(
        "Carrer Mestre Ramon Ortiz, 13", "Bell-Lloc d'Urgell"
    )
    check("DNPLOC returns result", result is not None)
    if result:
        check("has RC", bool(result.get("rc")))
        check("RC starts with expected", result["rc"].startswith("4613"))
        print(f"  INFO  RC={result['rc']}")

        # Test CPMRC with the RC
        utm = cadastre_rc_to_utm(result["rc"])
        check("CPMRC returns UTM", utm is not None)
        if utm:
            x, y = utm
            check("UTM X plausible", 314000 < x < 315000, f"x={x:.1f}")
            check("UTM Y plausible", 4611000 < y < 4612000, f"y={y:.1f}")
            print(f"  INFO  UTM=({x:.1f}, {y:.1f})")

    # Test with non-existent number (should retry without number)
    result2 = cadastre_address_lookup(
        "Carrer Mestre Ramon Ortiz, 5", "Bell-Lloc d'Urgell"
    )
    check("non-existent number still returns", result2 is not None)
    if result2:
        print(f"  INFO  fallback RC={result2['rc']}")


def test_nominatim_geocode() -> None:
    """Test Nominatim geocoding (requires network)."""
    print("\n--- nominatim_geocode (ONLINE) ---")
    from automation.geocode_coordinates import nominatim_geocode

    result = nominatim_geocode("Carrer Mestre Ramon Ortiz, 5", "Bell-Lloc d'Urgell")
    check("returns tuple", result is not None and len(result) == 2)
    if result:
        lat, lon = result
        check("lat in range", 41.5 < lat < 41.7, f"got {lat:.4f}")
        check("lon in range", 0.7 < lon < 0.9, f"got {lon:.4f}")


def test_geocode_project_bell_lloc() -> None:
    """Test full geocoding pipeline against known Bell-Lloc GPS coords."""
    print("\n--- geocode_project Bell-Lloc (ONLINE) ---")
    from automation.geocode_coordinates import geocode_project

    result = geocode_project(
        "Carrer Mestre Ramon Ortiz, 5",
        "Bell-Lloc d'Urgell",
        ["P-1", "P-2", "S-1"],
        None,
    )

    check("result not None", result is not None)
    if result is None:
        return

    # Known GPS centroid: (314508.67, 4611192.86)
    utm_x, utm_y = result["utm_x"], result["utm_y"]
    dx = abs(utm_x - 314508.67)
    dy = abs(utm_y - 4611192.86)
    total = (dx**2 + dy**2) ** 0.5

    check("UTM X within 50m of GPS", dx < 50, f"delta={dx:.1f}m")
    check("UTM Y within 100m of GPS", dy < 100, f"delta={dy:.1f}m")
    check("total distance < 100m", total < 100, f"total={total:.1f}m")
    check("has cadastral ref", result.get("rc") is not None)
    check("has 3 points", len(result.get("points", {})) == 3)
    check("source tag", result.get("source", "").startswith("geocode:"),
          f"got '{result.get('source')}'")
    print(f"  INFO  source={result.get('source')}")

    # Check point elevations are reasonable (~199m for Bell-Lloc)
    for pid, pt in result.get("points", {}).items():
        z = pt.get("z", 0)
        check(f"{pid} elevation ~199m", 190 < z < 210, f"got {z:.1f}m")


def test_auto_extract_with_geocode() -> None:
    """Test auto_extract triggers geocoding when no COORDENADES.txt."""
    print("\n--- auto_extract geocode fallback (ONLINE) ---")

    # Create a minimal project folder with just an address
    with tempfile.TemporaryDirectory() as tmpdir:
        project = Path(tmpdir) / "9999999 TEST-GEOCODE"
        project.mkdir()

        # Write minimal user_data.json with street_address
        import json
        ud = {"street_address": "Plaça Major, 1"}
        (project / "user_data.json").write_text(json.dumps(ud))

        from automation.auto_extractor import auto_extract
        result = auto_extract(str(project))

        # Municipality extraction from "TEST-GEOCODE" won't produce a real
        # municipality, so geocoding should skip with "no results" rather than crash
        geocode_skipped = any("Geocod" in s for s, _ in result.steps_skipped)
        geocode_done = any("Geocod" in s for s in result.steps_completed)
        check("geocode attempted (skipped or done)", geocode_skipped or geocode_done)
        check("no crash", True)  # If we got here, no exception


# === Main ===

def main() -> None:
    online = '--online' in sys.argv

    print("=" * 60)
    print("G3DT Geocoding Tests")
    print("=" * 60)

    # Offline tests (always run)
    test_wgs84_to_utm31n()
    test_distribute_points()
    test_generate_coordenades_txt()
    test_extract_municipality()
    test_parse_address()

    # Online tests (only with --online flag)
    if online:
        print("\n" + "=" * 60)
        print("ONLINE INTEGRATION TESTS")
        print("=" * 60)
        test_cadastre_address_lookup()
        test_nominatim_geocode()
        test_geocode_project_bell_lloc()
        test_auto_extract_with_geocode()
    else:
        print("\n  (Skip online tests — run with --online to include)")

    # Summary
    print("\n" + "=" * 60)
    total = _passed + _failed
    print(f"Results: {_passed}/{total} passed, {_failed} failed")
    if _failed > 0:
        print("SOME TESTS FAILED")
        sys.exit(1)
    else:
        print("ALL TESTS PASSED")
    print("=" * 60)


if __name__ == '__main__':
    main()
