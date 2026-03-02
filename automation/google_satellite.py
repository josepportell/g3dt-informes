#!/usr/bin/env python3
"""
Google Maps Static API Satellite Imagery Module

Downloads satellite imagery from Google Maps Static API with parcel polygon
overlay. This is the preferred source for "Foto Emplacament" (Figure 2) in
geotechnical reports, providing higher resolution and more up-to-date imagery
than the ICGC orthophoto fallback.

Google draws the polygon server-side via the path parameter, so no Pillow
dependency is needed.

Usage:
    from google_satellite import get_google_satellite_with_parcel

    path = get_google_satellite_with_parcel(
        utm_x=314508.67,
        utm_y=4611192.86,
        polygon_utm=[(314490, 4611170), (314530, 4611170), ...],
        output_path="emplacament.png",
    )

Author: Eficients.cat
Date: 2026-03-02
"""

from __future__ import annotations

import logging
import math
import os
import socket
import urllib.request
import urllib.error
from pathlib import Path

logger = logging.getLogger(__name__)

__all__ = [
    'utm_to_latlon',
    'get_google_satellite_with_parcel',
    'GoogleSatelliteError',
    'GoogleSatelliteNoAPIKeyError',
    'GoogleSatelliteConnectionError',
]


# === Load .env from project root ===

def _load_env() -> None:
    """Read .env file from project root into os.environ (no dependencies)."""
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if key and key not in os.environ:  # don't override explicit env vars
                os.environ[key] = value

_load_env()


# === Configuration ===

REQUEST_TIMEOUT_SECONDS = 10
USER_AGENT = "G3DT-Automation/1.0 (Eficients.cat; geotechnical report generation)"
GOOGLE_STATIC_MAPS_URL = "https://maps.googleapis.com/maps/api/staticmap"


# === Exception Hierarchy ===

class GoogleSatelliteError(Exception):
    """Base exception for Google satellite imagery errors."""
    pass


class GoogleSatelliteNoAPIKeyError(GoogleSatelliteError):
    """GOOGLE_MAPS_API_KEY environment variable is not set."""
    pass


class GoogleSatelliteConnectionError(GoogleSatelliteError):
    """Failed to connect to Google Maps Static API."""
    pass


# === UTM to WGS84 Conversion ===

def utm_to_latlon(
    easting: float,
    northing: float,
    zone: int = 31,
    northern: bool = True,
) -> tuple[float, float]:
    """
    Convert UTM coordinates to WGS84 latitude/longitude.

    Uses the standard geodetic series expansion with the WGS84 ellipsoid.
    Only UTM zone 31N is needed for Catalunya.

    Args:
        easting: UTM easting in meters
        northing: UTM northing in meters
        zone: UTM zone number (default 31 for Catalunya)
        northern: True for northern hemisphere

    Returns:
        (latitude, longitude) tuple in decimal degrees
    """
    # WGS84 ellipsoid parameters
    a = 6378137.0
    f = 1 / 298.257223563
    b = a * (1 - f)
    e2 = 1 - (b / a) ** 2
    e_prime2 = e2 / (1 - e2)

    # UTM parameters
    k0 = 0.9996
    x = easting - 500000.0
    y = northing if northern else northing - 10000000.0

    # Footpoint latitude
    M = y / k0
    mu = M / (a * (1 - e2 / 4 - 3 * e2**2 / 64 - 5 * e2**3 / 256))

    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    phi1 = (
        mu
        + (3 * e1 / 2 - 27 * e1**3 / 32) * math.sin(2 * mu)
        + (21 * e1**2 / 16 - 55 * e1**4 / 32) * math.sin(4 * mu)
        + (151 * e1**3 / 96) * math.sin(6 * mu)
        + (1097 * e1**4 / 512) * math.sin(8 * mu)
    )

    sin_phi1 = math.sin(phi1)
    cos_phi1 = math.cos(phi1)
    tan_phi1 = math.tan(phi1)

    N1 = a / math.sqrt(1 - e2 * sin_phi1**2)
    T1 = tan_phi1**2
    C1 = e_prime2 * cos_phi1**2
    R1 = a * (1 - e2) / (1 - e2 * sin_phi1**2) ** 1.5
    D = x / (N1 * k0)

    lat_rad = phi1 - (N1 * tan_phi1 / R1) * (
        D**2 / 2
        - (5 + 3 * T1 + 10 * C1 - 4 * C1**2 - 9 * e_prime2) * D**4 / 24
        + (61 + 90 * T1 + 298 * C1 + 45 * T1**2 - 252 * e_prime2 - 3 * C1**2)
        * D**6 / 720
    )

    lon_rad = (
        D
        - (1 + 2 * T1 + C1) * D**3 / 6
        + (5 - 2 * C1 + 28 * T1 - 3 * C1**2 + 8 * e_prime2 + 24 * T1**2)
        * D**5 / 120
    ) / cos_phi1

    lat = math.degrees(lat_rad)
    lon = math.degrees(lon_rad) + (zone * 6 - 183)

    return (lat, lon)


# === Helpers ===

def _compute_zoom(buffer_m: float, lat: float, width: int) -> int:
    """
    Compute Google Maps zoom level to show buffer_m around center.

    Args:
        buffer_m: Buffer in meters around center to show
        lat: Latitude of center (affects meters/pixel at equator)
        width: Image width in pixels

    Returns:
        Integer zoom level (max 21)
    """
    meters_per_pixel_needed = (2 * buffer_m) / width
    if meters_per_pixel_needed <= 0:
        return 21
    zoom = math.log2(
        156543.03392 * math.cos(math.radians(lat)) / meters_per_pixel_needed
    )
    zoom = int(zoom)
    return min(max(zoom, 0), 21)


def _simplify_polygon(
    vertices: list[tuple[float, float]],
    max_vertices: int = 50,
) -> list[tuple[float, float]]:
    """
    Downsample polygon to max_vertices evenly spaced points.

    Keeps the URL length manageable (~16K char limit for Google Static Maps).

    Args:
        vertices: List of (x, y) coordinate tuples
        max_vertices: Maximum number of vertices to keep

    Returns:
        Simplified list of vertices
    """
    if len(vertices) <= max_vertices:
        return vertices

    step = len(vertices) / max_vertices
    return [vertices[int(i * step)] for i in range(max_vertices)]


# === Main Function ===

def get_google_satellite_with_parcel(
    utm_x: float,
    utm_y: float,
    polygon_utm: list[tuple[float, float]],
    output_path: str | Path,
    buffer_m: float = 200.0,
    width: int = 640,
    height: int = 480,
) -> Path:
    """
    Download Google Maps satellite image with parcel polygon overlay.

    The polygon is rendered server-side by Google as a red outline with
    semi-transparent red fill. No image processing libraries needed.

    Args:
        utm_x: UTM X coordinate (EPSG:25831) for centering
        utm_y: UTM Y coordinate
        polygon_utm: List of (x, y) UTM coordinate tuples forming the parcel polygon
        output_path: Where to save the PNG image
        buffer_m: Buffer around center point in meters (default 200m)
        width: Image width in pixels (max 640 for free tier)
        height: Image height in pixels (max 640 for free tier)

    Returns:
        Path to saved PNG image

    Raises:
        GoogleSatelliteNoAPIKeyError: If GOOGLE_MAPS_API_KEY env var is not set
        GoogleSatelliteConnectionError: If download fails
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise GoogleSatelliteNoAPIKeyError(
            "GOOGLE_MAPS_API_KEY environment variable is not set. "
            "Set it to use Google satellite imagery, or fall back to ICGC orthophoto."
        )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert center UTM to lat/lon
    center_lat, center_lon = utm_to_latlon(utm_x, utm_y)
    logger.debug(f"Center: UTM ({utm_x}, {utm_y}) -> WGS84 ({center_lat:.6f}, {center_lon:.6f})")

    # Convert polygon vertices UTM to lat/lon
    polygon_latlon = [utm_to_latlon(vx, vy) for vx, vy in polygon_utm]

    # Simplify polygon if too many vertices
    polygon_latlon = _simplify_polygon(polygon_latlon)

    # Compute zoom level
    zoom = _compute_zoom(buffer_m, center_lat, width)
    logger.debug(f"Computed zoom level: {zoom} (buffer={buffer_m}m, width={width}px)")

    # Build path parameter: red outline + semi-transparent red fill
    # color format: 0xRRGGBBAA, fillcolor format: 0xRRGGBBAA
    path_vertices = "|".join(f"{lat:.6f},{lon:.6f}" for lat, lon in polygon_latlon)
    path_param = f"color:0xff0000ff|fillcolor:0xff000028|weight:2|{path_vertices}"

    # Build full URL
    url = (
        f"{GOOGLE_STATIC_MAPS_URL}"
        f"?center={center_lat:.6f},{center_lon:.6f}"
        f"&zoom={zoom}"
        f"&size={width}x{height}"
        f"&maptype=satellite"
        f"&format=png"
        f"&path={path_param}"
        f"&key={api_key}"
    )

    logger.debug(f"Google Static Maps URL length: {len(url)} chars")

    # Download image
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
            data = resp.read()
    except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as e:
        raise GoogleSatelliteConnectionError(
            f"Failed to download Google satellite image: {e}"
        )

    # Validate response is PNG
    if data[:4] != b'\x89PNG':
        # Try to extract error message from response
        try:
            error_text = data[:500].decode('utf-8', errors='replace')
        except Exception:
            error_text = "(binary response)"
        raise GoogleSatelliteConnectionError(
            f"Google Maps API returned non-PNG response: {error_text}"
        )

    # Save image
    with open(output_path, 'wb') as f:
        f.write(data)

    logger.info(f"Google satellite image with parcel outline saved to {output_path}")
    return output_path


# === CLI for Testing ===

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    print("=" * 60)
    print("Google Satellite Imagery - Test")
    print("=" * 60)

    # Test UTM conversion
    lat, lon = utm_to_latlon(314508.67, 4611192.86)
    print(f"\nUTM (314508.67, 4611192.86) -> WGS84 ({lat:.6f}, {lon:.6f})")
    print(f"  Expected: approximately (41.631, 0.773)")
    assert abs(lat - 41.631) < 0.01, f"Latitude deviation too large: {lat}"
    assert abs(lon - 0.773) < 0.02, f"Longitude deviation too large: {lon}"
    print("  UTM conversion OK")

    # Fetch real cadastral polygon (shared for both Google and ICGC)
    print("\nFetching real cadastral polygon...")
    polygon = None
    try:
        from automation.cadastre_adjacents import get_cadastral_reference, get_parcel_geometry_utm
        rc14_full, _ldt = get_cadastral_reference(314508.67, 4611192.86)
        if rc14_full and len(rc14_full) >= 14:
            polygon = get_parcel_geometry_utm(rc14_full[:14])
            print(f"  Parcel {rc14_full[:14]}: {len(polygon)} vertices")
        else:
            print("  Could not get cadastral reference")
    except Exception as e:
        print(f"  Cadastre lookup failed: {e}")

    # Test Google satellite if API key is set
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if api_key and polygon:
        print("\nGenerating Google satellite image...")
        google_path = get_google_satellite_with_parcel(
            utm_x=314508.67,
            utm_y=4611192.86,
            polygon_utm=polygon,
            output_path="/tmp/bell_lloc_google_satellite.png",
        )
        print(f"  Google satellite: {google_path}")
    elif not api_key:
        print("\nGOOGLE_MAPS_API_KEY not set, skipping Google satellite test")

    # Generate ICGC version for comparison
    if polygon:
        print("\nGenerating ICGC orthophoto for comparison...")
        try:
            from automation.icgc_geology import get_orthophoto_with_parcel
            icgc_path = get_orthophoto_with_parcel(
                utm_x=314508.67,
                utm_y=4611192.86,
                polygon_utm=polygon,
                output_path="/tmp/bell_lloc_icgc_ortho.png",
            )
            print(f"  ICGC orthophoto: {icgc_path}")
        except Exception as e:
            print(f"  ICGC comparison skipped: {e}")

    print("\nDone.")
