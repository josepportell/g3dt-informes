#!/usr/bin/env python3
"""
Orthophoto Enrichment Module

Downloads ICGC orthophoto chips and crops boundary strips for a cadastral parcel.
Tries ICGC Local WMS (10cm) first, falls back to Territorial WMS (25cm).

Usage:
    from automation.ortho_enrichment import download_ortho_chips

    chips = download_ortho_chips(314508.67, 4611192.86, polygon_coords)
    print(chips.tight_chip_path)   # ~/.g3dt/cache/ortho_enrichment/{hash}/tight_chip.png
    print(chips.boundary_strips)   # {'north': Path(...), 'south': Path(...), ...}

Author: Eficients.cat
Date: 2026-03-28
"""

from __future__ import annotations

import hashlib
import logging
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .cadastre_adjacents import _classify_edges_by_direction
from .icgc_geology import ICGCConnectionError, ICGCCoordinateError, _validate_coordinates

logger = logging.getLogger(__name__)


# === WMS Configuration ===

ICGC_LOCAL_WMS_URL = "https://geoserveis.icgc.cat/servei/catalunya/orto-local/wms"
ICGC_LOCAL_LAYER = "ortofoto_color_serie_local_vigent"

ICGC_TERRITORIAL_WMS_URL = "https://geoserveis.icgc.cat/servei/catalunya/orto-territorial/wms"
ICGC_TERRITORIAL_LAYER = "ortofoto_color_vigent"

DEFAULT_CACHE_DIR = Path.home() / ".g3dt" / "cache" / "ortho_enrichment"

TIGHT_BUFFER_M = 40.0
WIDE_BUFFER_M = 100.0
STRIP_NORMAL_M = 25.0
STRIP_TANGENT_PAD_M = 10.0


@dataclass
class OrthoChips:
    tight_chip_path: Path | None
    wide_chip_path: Path | None
    boundary_strips: dict[str, Path]
    parcel_polygon: list[tuple[float, float]]
    bbox_tight: tuple[float, float, float, float]
    resolution_source: str


def download_ortho_chips(
    utm_x: float,
    utm_y: float,
    polygon_utm: list[tuple[float, float]],
    cache_dir: Path | None = None,
) -> OrthoChips:
    """Download orthophoto chips and crop boundary strips for a parcel.

    Downloads a tight chip (parcel bbox + 40m buffer) and a wide chip
    (centroid + 100m), then crops 4 boundary strips from the tight chip.

    Never raises — returns OrthoChips with None paths on failure.
    """
    if cache_dir is None:
        cache_dir = DEFAULT_CACHE_DIR

    poly_str = "|".join(f"{x:.1f},{y:.1f}" for x, y in polygon_utm)
    cache_key = hashlib.sha256(f"{utm_x:.0f}_{utm_y:.0f}_{poly_str}".encode()).hexdigest()
    chip_dir = cache_dir / cache_key
    tight_path = chip_dir / "tight_chip.png"

    # Return cached result if available
    if tight_path.exists():
        logger.info(f"Ortho chips cache hit: {chip_dir}")
        return _load_cached(chip_dir, polygon_utm)

    chip_dir.mkdir(parents=True, exist_ok=True)

    try:
        _validate_coordinates(utm_x, utm_y)
    except ICGCCoordinateError as e:
        logger.warning(f"Coordinates outside Catalunya: {e}")
        return _empty_result(polygon_utm)

    # Compute tight bbox from polygon
    xs = [p[0] for p in polygon_utm]
    ys = [p[1] for p in polygon_utm]
    poly_xmin, poly_xmax = min(xs), max(xs)
    poly_ymin, poly_ymax = min(ys), max(ys)

    bbox_tight = (
        poly_xmin - TIGHT_BUFFER_M,
        poly_ymin - TIGHT_BUFFER_M,
        poly_xmax + TIGHT_BUFFER_M,
        poly_ymax + TIGHT_BUFFER_M,
    )

    # --- Tight chip ---
    resolution_source = "local_10cm"
    tight_raw = chip_dir / "tight_raw.jpg"
    try:
        _download_wms(ICGC_LOCAL_WMS_URL, ICGC_LOCAL_LAYER, bbox_tight, 800, 800, tight_raw)
    except (ICGCConnectionError, OSError):
        logger.info("Local WMS failed, falling back to territorial")
        resolution_source = "territorial_25cm"
        try:
            _download_wms(ICGC_TERRITORIAL_WMS_URL, ICGC_TERRITORIAL_LAYER, bbox_tight, 800, 800, tight_raw)
        except (ICGCConnectionError, OSError) as e:
            logger.warning(f"Both WMS sources failed for tight chip: {e}")
            return _empty_result(polygon_utm)

    # Draw parcel overlay and save as PNG
    try:
        _draw_parcel_overlay(tight_raw, tight_path, polygon_utm, bbox_tight, 800, 800)
    except Exception as e:
        logger.warning(f"Failed to draw parcel overlay: {e}")
        return _empty_result(polygon_utm)
    finally:
        tight_raw.unlink(missing_ok=True)

    # --- Wide chip ---
    centroid_x = sum(xs) / len(xs)
    centroid_y = sum(ys) / len(ys)
    aspect = 800 / 600
    bbox_wide = (
        centroid_x - WIDE_BUFFER_M * aspect,
        centroid_y - WIDE_BUFFER_M,
        centroid_x + WIDE_BUFFER_M * aspect,
        centroid_y + WIDE_BUFFER_M,
    )
    wide_path = chip_dir / "wide_chip.jpg"
    try:
        _download_wms(ICGC_TERRITORIAL_WMS_URL, ICGC_TERRITORIAL_LAYER, bbox_wide, 800, 600, wide_path)
    except (ICGCConnectionError, OSError) as e:
        logger.warning(f"Wide chip download failed: {e}")
        wide_path = None

    # --- Boundary strips ---
    strips = _crop_boundary_strips(tight_path, polygon_utm, bbox_tight, 800, 800, chip_dir)

    return OrthoChips(
        tight_chip_path=tight_path,
        wide_chip_path=wide_path,
        boundary_strips=strips,
        parcel_polygon=polygon_utm,
        bbox_tight=bbox_tight,
        resolution_source=resolution_source,
    )


def _download_wms(
    wms_url: str,
    layer: str,
    bbox: tuple[float, float, float, float],
    width: int,
    height: int,
    output_path: Path,
) -> None:
    x_min, y_min, x_max, y_max = bbox
    url = (
        f"{wms_url}"
        f"?SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap"
        f"&LAYERS={layer}"
        f"&STYLES=&SRS=EPSG:25831"
        f"&BBOX={x_min},{y_min},{x_max},{y_max}"
        f"&WIDTH={width}&HEIGHT={height}"
        f"&FORMAT=image/jpeg"
    )
    logger.debug(f"WMS request: {url}")

    try:
        urllib.request.urlretrieve(url, str(output_path))
    except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as e:
        output_path.unlink(missing_ok=True)
        raise ICGCConnectionError(f"WMS download failed: {e}")

    with open(output_path, 'rb') as f:
        header = f.read(4)
    if header[:2] != b'\xff\xd8':
        output_path.unlink(missing_ok=True)
        raise ICGCConnectionError("WMS response is not JPEG (likely error XML)")


def _draw_parcel_overlay(
    input_jpg: Path,
    output_png: Path,
    polygon_utm: list[tuple[float, float]],
    bbox: tuple[float, float, float, float],
    img_w: int,
    img_h: int,
) -> None:
    from PIL import Image, ImageDraw

    x_min, y_min, x_max, y_max = bbox

    img = Image.open(str(input_jpg)).convert("RGBA")
    actual_w, actual_h = img.size

    pixel_coords = []
    for vx, vy in polygon_utm:
        px = (vx - x_min) / (x_max - x_min) * actual_w
        py = actual_h - (vy - y_min) / (y_max - y_min) * actual_h
        pixel_coords.append((px, py))

    if len(pixel_coords) >= 3:
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw_overlay = ImageDraw.Draw(overlay)
        draw_overlay.polygon(pixel_coords, fill=(255, 0, 0, 40))
        img = Image.alpha_composite(img, overlay)

        draw = ImageDraw.Draw(img)
        draw.polygon(pixel_coords, outline='red')
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            shifted = [(x + dx, y + dy) for x, y in pixel_coords]
            draw.polygon(shifted, outline='red')

    img.convert("RGB").save(str(output_png), "PNG")
    logger.info(f"Tight chip with parcel overlay saved: {output_png}")


def _crop_boundary_strips(
    tight_chip_path: Path,
    polygon_utm: list[tuple[float, float]],
    bbox: tuple[float, float, float, float],
    img_w: int,
    img_h: int,
    output_dir: Path,
) -> dict[str, Path]:
    from PIL import Image

    try:
        edge_info = _classify_edges_by_direction(polygon_utm)
    except Exception as e:
        logger.warning(f"Edge classification failed: {e}")
        return {}

    if not edge_info:
        return {}

    try:
        img = Image.open(str(tight_chip_path))
    except Exception as e:
        logger.warning(f"Failed to open tight chip for cropping: {e}")
        return {}

    actual_w, actual_h = img.size
    x_min, y_min, x_max, y_max = bbox
    edge_lengths = _compute_edge_lengths(polygon_utm, edge_info)

    strips: dict[str, Path] = {}
    for direction, (midpoint, normal) in edge_info.items():
        mx, my = midpoint
        nx, ny = normal
        edge_len = edge_lengths.get(direction, 30.0)

        # Tangent is perpendicular to outward normal
        tx, ty = -ny, nx
        half_tangent = edge_len / 2.0 + STRIP_TANGENT_PAD_M

        # Four corners of the strip rectangle in UTM
        corners_utm = [
            (mx + tx * half_tangent + nx * STRIP_NORMAL_M,
             my + ty * half_tangent + ny * STRIP_NORMAL_M),
            (mx - tx * half_tangent + nx * STRIP_NORMAL_M,
             my - ty * half_tangent + ny * STRIP_NORMAL_M),
            (mx - tx * half_tangent - nx * STRIP_NORMAL_M,
             my - ty * half_tangent - ny * STRIP_NORMAL_M),
            (mx + tx * half_tangent - nx * STRIP_NORMAL_M,
             my + ty * half_tangent - ny * STRIP_NORMAL_M),
        ]

        # Convert to pixel coordinates
        pxs = []
        pys = []
        for vx, vy in corners_utm:
            px = (vx - x_min) / (x_max - x_min) * actual_w
            py = actual_h - (vy - y_min) / (y_max - y_min) * actual_h
            pxs.append(px)
            pys.append(py)

        # Axis-aligned bounding box of the rotated strip, clamped to image
        crop_left = max(0, int(min(pxs)))
        crop_upper = max(0, int(min(pys)))
        crop_right = min(actual_w, int(max(pxs)) + 1)
        crop_lower = min(actual_h, int(max(pys)) + 1)

        if crop_right <= crop_left or crop_lower <= crop_upper:
            logger.warning(f"Strip {direction} falls outside image bounds, skipping")
            continue

        strip_path = output_dir / f"strip_{direction}.jpg"
        try:
            cropped = img.crop((crop_left, crop_upper, crop_right, crop_lower))
            cropped.save(str(strip_path), "JPEG", quality=90)
            strips[direction] = strip_path
            logger.info(f"Boundary strip {direction} saved: {strip_path}")
        except Exception as e:
            logger.warning(f"Failed to crop strip {direction}: {e}")

    return strips


def _compute_edge_lengths(
    polygon_utm: list[tuple[float, float]],
    edge_info: dict[str, tuple[tuple[float, float], tuple[float, float]]],
) -> dict[str, float]:
    """Find the actual edge length for each classified direction."""
    import math

    n = len(polygon_utm)
    closed = n > 1 and polygon_utm[0] == polygon_utm[-1]
    num_edges = (n - 1) if closed else n

    # Map direction midpoints to expected edge lengths
    result: dict[str, float] = {}
    for direction, (midpoint, _normal) in edge_info.items():
        mid_x, mid_y = midpoint
        best_dist = float('inf')
        best_len = 30.0

        for i in range(num_edges):
            j = (i + 1) % n
            x1, y1 = polygon_utm[i]
            x2, y2 = polygon_utm[j]
            emx = (x1 + x2) / 2.0
            emy = (y1 + y2) / 2.0
            dist = math.hypot(emx - mid_x, emy - mid_y)
            if dist < best_dist:
                best_dist = dist
                best_len = math.hypot(x2 - x1, y2 - y1)

        result[direction] = best_len

    return result


def _load_cached(chip_dir: Path, polygon_utm: list[tuple[float, float]]) -> OrthoChips:
    tight_path = chip_dir / "tight_chip.png"
    wide_path = chip_dir / "wide_chip.jpg"
    if not wide_path.exists():
        wide_path = None

    strips: dict[str, Path] = {}
    for direction in ("north", "south", "east", "west"):
        strip_path = chip_dir / f"strip_{direction}.jpg"
        if strip_path.exists():
            strips[direction] = strip_path

    # Reconstruct bbox from polygon
    xs = [p[0] for p in polygon_utm]
    ys = [p[1] for p in polygon_utm]
    bbox_tight = (
        min(xs) - TIGHT_BUFFER_M,
        min(ys) - TIGHT_BUFFER_M,
        max(xs) + TIGHT_BUFFER_M,
        max(ys) + TIGHT_BUFFER_M,
    )

    return OrthoChips(
        tight_chip_path=tight_path,
        wide_chip_path=wide_path,
        boundary_strips=strips,
        parcel_polygon=polygon_utm,
        bbox_tight=bbox_tight,
        resolution_source="cached",
    )


def _empty_result(polygon_utm: list[tuple[float, float]]) -> OrthoChips:
    return OrthoChips(
        tight_chip_path=None,
        wide_chip_path=None,
        boundary_strips={},
        parcel_polygon=polygon_utm,
        bbox_tight=(0.0, 0.0, 0.0, 0.0),
        resolution_source="none",
    )
