"""
Parcel Resolver Module

Resolves the correct parcel polygon for a project, detecting and handling
multi-parcel sites by merging adjacent cadastral parcels when the plan area
doesn't match a single parcel.

Usage:
    from automation.parcel_resolver import resolve_parcel

    result = resolve_parcel(314503.0, 4611178.0, planol_area_m2=995)
    if result and result.is_merged:
        print(f"Merged {len(result.merged_refs)} parcels: {result.merged_refs}")

Author: Eficients.cat
Date: 2026-03-29
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from shapely.geometry import Polygon as ShapelyPolygon
from shapely.ops import unary_union

from .cadastre_adjacents import (
    get_cadastral_reference,
    get_parcel_geometry_utm,
    _classify_edges_by_direction,
    _query_ref_by_coords,
)

logger = logging.getLogger(__name__)

__all__ = ["ResolvedParcel", "resolve_parcel"]

# Area mismatch thresholds
_SINGLE_PARCEL_TOLERANCE = 0.30  # Accept single parcel if within 30%
_MERGE_ACCEPT_THRESHOLD = 0.20   # Accept merge if within 20%
_HIGH_CONFIDENCE_THRESHOLD = 0.10  # "high" confidence if within 10%
_SINGLE_HIGH_THRESHOLD = 0.15    # "high" for single if within 15%
_PROBE_DISTANCE_M = 5.0          # How far outside edge to probe for neighbors


@dataclass
class ResolvedParcel:
    """Result of parcel resolution, possibly with merged neighbors."""

    rc14: str
    polygon: list[tuple[float, float]]
    centroid: tuple[float, float]
    area_m2: float
    is_merged: bool
    merged_refs: list[str] = field(default_factory=list)
    resolution_method: str = "single"
    confidence: str = "high"


def resolve_parcel(
    utm_x: float,
    utm_y: float,
    planol_area_m2: float | None = None,
    municipality: str = "",
) -> ResolvedParcel | None:
    """Resolve the correct parcel polygon, merging neighbors if needed.

    Args:
        utm_x: UTM X coordinate (EPSG:25831).
        utm_y: UTM Y coordinate (EPSG:25831).
        planol_area_m2: Expected area from architect's plan. When provided and
            the primary parcel area differs significantly, the resolver
            attempts to merge adjacent parcels.
        municipality: Municipality name (unused currently, reserved for
            future Cadastre query refinements).

    Returns:
        ResolvedParcel with the polygon (single or merged), or None if
        the primary parcel cannot be resolved at all.
    """
    # --- Step 1: Get primary parcel ---
    try:
        rc_full, _ = get_cadastral_reference(utm_x, utm_y)
    except Exception:
        logger.warning("Cadastre reference lookup failed for (%.2f, %.2f)", utm_x, utm_y)
        return None

    if not rc_full:
        logger.warning("No cadastral reference at (%.2f, %.2f)", utm_x, utm_y)
        return None

    rc14 = rc_full[:14]

    try:
        polygon = get_parcel_geometry_utm(rc14)
    except Exception:
        logger.warning("Parcel geometry lookup failed for %s", rc14)
        return None

    if not polygon or len(polygon) < 3:
        logger.warning("Invalid polygon for %s (%d points)", rc14, len(polygon) if polygon else 0)
        return None

    # --- Step 2: Compute primary area ---
    primary = ShapelyPolygon(polygon)
    primary_area = primary.area
    cx, cy = primary.centroid.x, primary.centroid.y

    logger.info(
        "Primary parcel %s: %.1f m2 (centroid %.2f, %.2f)",
        rc14, primary_area, cx, cy,
    )

    # --- Step 3: Check if merge is needed ---
    if planol_area_m2 is None or planol_area_m2 <= 0:
        return ResolvedParcel(
            rc14=rc14,
            polygon=polygon,
            centroid=(cx, cy),
            area_m2=primary_area,
            is_merged=False,
            merged_refs=[rc14],
            resolution_method="single",
            confidence="high",
        )

    ratio = abs(planol_area_m2 - primary_area) / primary_area if primary_area > 0 else float("inf")

    if ratio < _SINGLE_PARCEL_TOLERANCE:
        logger.info(
            "Single parcel matches plan area (ratio=%.2f, threshold=%.2f)",
            ratio, _SINGLE_PARCEL_TOLERANCE,
        )
        return ResolvedParcel(
            rc14=rc14,
            polygon=polygon,
            centroid=(cx, cy),
            area_m2=primary_area,
            is_merged=False,
            merged_refs=[rc14],
            resolution_method="single",
            confidence="high",
        )

    logger.info(
        "Area mismatch: primary=%.1f m2, plan=%.1f m2, ratio=%.2f — attempting merge",
        primary_area, planol_area_m2, ratio,
    )

    # --- Step 4: Find neighbor parcel refs ---
    neighbor_refs = _find_neighbor_refs(polygon, rc14)

    if not neighbor_refs:
        logger.warning(
            "No neighbor parcels found for %s despite area mismatch (%.1f vs %.1f)",
            rc14, primary_area, planol_area_m2,
        )
        return ResolvedParcel(
            rc14=rc14,
            polygon=polygon,
            centroid=(cx, cy),
            area_m2=primary_area,
            is_merged=False,
            merged_refs=[rc14],
            resolution_method="single",
            confidence="low",
        )

    logger.info("Found %d neighbor parcels: %s", len(neighbor_refs), neighbor_refs)

    # --- Step 5: Try merging ---
    best_merge = _find_best_merge(primary, rc14, neighbor_refs, planol_area_m2)

    # --- Step 6: Return result ---
    if best_merge is not None:
        merged_poly, refs, merged_area, best_diff = best_merge
        merged_coords = list(merged_poly.exterior.coords)
        mcx, mcy = merged_poly.centroid.x, merged_poly.centroid.y

        logger.info(
            "Merge accepted: refs=%s, area=%.1f m2, diff=%.2f",
            refs, merged_area, best_diff,
        )

        return ResolvedParcel(
            rc14=rc14,
            polygon=merged_coords,
            centroid=(mcx, mcy),
            area_m2=merged_area,
            is_merged=True,
            merged_refs=refs,
            resolution_method="merged",
            confidence="high" if best_diff < _HIGH_CONFIDENCE_THRESHOLD else "medium",
        )

    # No good merge found
    logger.warning(
        "No acceptable merge found for %s (plan=%.1f m2, primary=%.1f m2)",
        rc14, planol_area_m2, primary_area,
    )
    return ResolvedParcel(
        rc14=rc14,
        polygon=polygon,
        centroid=(cx, cy),
        area_m2=primary_area,
        is_merged=False,
        merged_refs=[rc14],
        resolution_method="single",
        confidence="low" if ratio >= _SINGLE_HIGH_THRESHOLD else "high",
    )


# === Internal helpers ===


def _find_neighbor_refs(
    polygon: list[tuple[float, float]],
    our_rc14: str,
) -> set[str]:
    """Probe outward from each edge to discover neighboring parcel refs."""
    edge_info = _classify_edges_by_direction(polygon)
    neighbor_refs: set[str] = set()

    for direction, (midpoint, normal) in edge_info.items():
        probe_x = midpoint[0] + normal[0] * _PROBE_DISTANCE_M
        probe_y = midpoint[1] + normal[1] * _PROBE_DISTANCE_M

        logger.debug(
            "Probing %s: midpoint=(%.2f, %.2f) → probe=(%.2f, %.2f)",
            direction, midpoint[0], midpoint[1], probe_x, probe_y,
        )

        try:
            ref, _ = _query_ref_by_coords(probe_x, probe_y)
            if ref and ref[:14] != our_rc14:
                neighbor_refs.add(ref[:14])
                logger.debug("Found neighbor %s to the %s", ref[:14], direction)
        except Exception:
            logger.debug("Probe %s failed", direction)

    return neighbor_refs


def _get_neighbor_polygon(ref: str) -> ShapelyPolygon | None:
    """Fetch and validate a neighbor's polygon geometry."""
    try:
        npoly = get_parcel_geometry_utm(ref)
    except Exception:
        return None

    if not npoly or len(npoly) < 3:
        return None

    return ShapelyPolygon(npoly)


def _try_merge(
    primary: ShapelyPolygon,
    neighbors: list[ShapelyPolygon],
    planol_area_m2: float,
) -> tuple[ShapelyPolygon, float, float] | None:
    """Attempt to merge primary with a set of neighbor polygons.

    Returns (merged_polygon, merged_area, relative_diff) or None if the
    result is not a single contiguous Polygon.
    """
    merged = unary_union([primary, *neighbors])
    if merged.geom_type != "Polygon":
        return None
    merged_area = merged.area
    diff = abs(planol_area_m2 - merged_area) / planol_area_m2 if planol_area_m2 > 0 else float("inf")
    return merged, merged_area, diff


def _find_best_merge(
    primary: ShapelyPolygon,
    rc14: str,
    neighbor_refs: set[str],
    planol_area_m2: float,
) -> tuple[ShapelyPolygon, list[str], float, float] | None:
    """Try single-neighbor and two-neighbor merges, return the best one.

    Returns (merged_polygon, all_refs, merged_area, diff) or None.
    """
    best_diff = float("inf")
    best_result: tuple[ShapelyPolygon, list[str], float, float] | None = None

    # Pre-fetch neighbor polygons
    neighbor_polys: dict[str, ShapelyPolygon] = {}
    for nref in neighbor_refs:
        npoly = _get_neighbor_polygon(nref)
        if npoly is not None:
            neighbor_polys[nref] = npoly

    # Single-neighbor merges
    for nref, npoly in neighbor_polys.items():
        result = _try_merge(primary, [npoly], planol_area_m2)
        if result is None:
            continue
        merged, merged_area, diff = result
        if diff < best_diff:
            best_diff = diff
            best_result = (merged, [rc14, nref], merged_area, diff)

    # Two-neighbor merges (only if single merge not close enough)
    if best_diff > _SINGLE_HIGH_THRESHOLD:
        neighbor_list = list(neighbor_polys.keys())
        for i in range(len(neighbor_list)):
            for j in range(i + 1, len(neighbor_list)):
                ref_i, ref_j = neighbor_list[i], neighbor_list[j]
                result = _try_merge(
                    primary,
                    [neighbor_polys[ref_i], neighbor_polys[ref_j]],
                    planol_area_m2,
                )
                if result is None:
                    continue
                merged, merged_area, diff = result
                if diff < best_diff:
                    best_diff = diff
                    best_result = (merged, [rc14, ref_i, ref_j], merged_area, diff)

    # Only accept if within threshold
    if best_result is not None and best_diff < _MERGE_ACCEPT_THRESHOLD:
        return best_result

    return None
