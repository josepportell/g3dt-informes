#!/usr/bin/env python3
"""
G3DT Auto-Extractor (Fase 0.5)

Orchestrates all available extractors to pre-fill as many user_data fields
as possible BEFORE the wizard runs. The user (Eva) then only confirms or
corrects what was found, instead of filling everything from scratch.

Three phases, each progressively more dependent:
  Phase 1: Local files only (FileScanner, DPSH Excel, field dates)
  Phase 2: PDF extraction (Lab results via PyMuPDF)
  Phase 3: HTTP APIs (ICGC geology/elevation/slope, Cadastre adjacents)

Phase 3 requires UTM coordinates — skipped if unavailable.

Usage:
    from automation.auto_extractor import auto_extract, AutoExtractionResult

    result = auto_extract('/path/to/project')
    print(result.prefills)       # Dict of pre-filled fields
    print(result.sources)        # Source of each field
    print(result.steps_completed)

    # Or from CLI:
    python -m automation.auto_extractor "reference-material/3001621 CASTELLAR DEL VALLES"

Author: Eficients.cat
Date: 2026-02-24
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

__all__ = ['auto_extract', 'AutoExtractionResult']

# ── G3 internal address patterns (must NOT become project street_address) ──
# Canonical definition lives in automation.internal_addresses so every
# pipeline stage (FileMiner competition, geocode, adjacents) uses the same
# patterns. Re-exported here under the legacy private names for backward
# compatibility with existing call sites below.
from .internal_addresses import (
    G3_ADDRESS_PATTERNS as _G3_ADDRESS_PATTERNS,
    is_g3_internal_address as _is_g3_internal_address,
)


def _best_vision_address(
    result: "AutoExtractionResult",
    min_confidence: float = 0.9,
) -> str | None:
    """Return the highest-confidence architect-plan street_address from vision.

    Projecte vision is intentionally excluded — it is OCR-noisy on scanned
    project memoria PDFs; architect_plan vision is the trustworthy source.
    Returns None if no qualifying source exists.
    """
    cmap = getattr(result, 'concept_map', None)
    if cmap is None:
        return None
    sources = getattr(cmap, 'concept_sources', {}) or {}
    candidates = sources.get('street_address', []) or []
    best: tuple[float, str] | None = None
    for src in candidates:
        method = getattr(src, 'extraction_method', '') or ''
        if not method.startswith('vision_probe:architect_plan'):
            continue
        conf = float(getattr(src, 'confidence', 0.0) or 0.0)
        if conf < min_confidence:
            continue
        preview = (getattr(src, 'signal_preview', '') or '').strip()
        if not preview:
            continue
        if best is None or conf > best[0]:
            best = (conf, preview)
    return best[1] if best else None


_ADDR_ABBREVIATIONS = [
    # (pattern, replacement_title, replacement_upper)
    # Title case for mixed-case input, upper for ALL-CAPS input
    (re.compile(r'\bC/\s*', re.IGNORECASE), 'Carrer ', 'CARRER '),
    (re.compile(r'\bAv(?:da?)?\.\s*', re.IGNORECASE), 'Avinguda ', 'AVINGUDA '),
    (re.compile(r'\bPl\.\s*', re.IGNORECASE), 'Plaça ', 'PLAÇA '),
]


def _expand_street_abbreviations(address: str) -> str:
    """Expand common street abbreviations: C/ → Carrer, Av./Avda. → Avinguda, Pl. → Plaça.

    Case-preserving: if the input is ALL-CAPS, the expansion is ALL-CAPS.
    Does NOT expand STA. → Santa (may be official cadastre name).
    Also strips 'nº' before numbers (keeps the number).
    """
    is_upper = address == address.upper()
    for pattern, repl_title, repl_upper in _ADDR_ABBREVIATIONS:
        address = pattern.sub(repl_upper if is_upper else repl_title, address)
    # Strip 'nº' but keep the number (e.g. "nº16" → "16", "nº 7" → "7")
    address = re.sub(r'nº\s*', '', address)
    return address


def _clean_street_address(address: str, municipality: str) -> str:
    """Post-process extracted street address: expand abbreviations, strip trailing municipality/postal code.

    Bell-Lloc: "C/ MESTRE RAMON ORTIZ 15 BELL-LLOC" → "Carrer MESTRE RAMON ORTIZ 15"
    """
    if not address or not municipality:
        return address

    # Expand abbreviations first (before municipality stripping)
    address = _expand_street_abbreviations(address)

    def _strip(s: str) -> str:
        return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn').upper()

    # Normalize to NFC so stripped-index == original-index (NFD has extra chars)
    address = unicodedata.normalize('NFC', address)
    addr_stripped = _strip(address)
    muni_stripped = _strip(municipality)
    # Also try common variants: "BELL-LLOC D'URGELL" → "BELL-LLOC"
    muni_words = muni_stripped.split()

    # Try full municipality name first, then first word (for "BELL-LLOC D'URGELL" → "BELL-LLOC")
    for candidate in (muni_stripped, muni_words[0] if muni_words else ''):
        if not candidate or len(candidate) < 3:
            continue
        idx = addr_stripped.rfind(candidate)
        if idx > 0:  # Must not be at the start (the street name itself)
            # Remove municipality and any preceding comma/space/postal code
            prefix = address[:idx].rstrip(' ,\t')
            # Also strip postal codes like "25220"
            prefix = re.sub(r'[\s,]+\d{5}\s*$', '', prefix)
            if len(prefix) > 3:
                logger.debug("Cleaned address: %r → %r (removed %r)", address, prefix, municipality)
                return prefix

    return address


@dataclass
class AutoExtractionResult:
    """Result of the auto-extraction process."""
    prefills: dict[str, Any] = field(default_factory=dict)
    sources: dict[str, str] = field(default_factory=dict)
    dpsh_data: Any = None           # DPSHData | None
    lab_results: Any = None         # LabResults | None
    file_mapping: Any = None        # FileMapping | None
    content_discovery: Any = None   # ContentDiscoveryResult | None
    mining_result: Any = None       # MiningResult | None (FileMiner)
    mining_alternatives: dict[str, list] = field(default_factory=dict)  # var → [Signal, ...]
    concept_map: Any = None
    steps_completed: list[str] = field(default_factory=list)
    steps_skipped: list[tuple[str, str]] = field(default_factory=list)
    duration_seconds: float = 0.0
    # Diagnostic-only: per-call usage from automation.targeted_extraction
    # (HITL drawer). Empty for runs that don't invoke targeted extraction.
    targeted_extraction_traces: list[dict] = field(default_factory=list)
    # Files promoted to roles by phase 0.46 (deep folder classify). Used by
    # phase 0.47 (re-mine) to target FileMiner at just the new files.
    # Each entry: (role_name, rel_path).
    deep_folder_promoted: list[tuple[str, str]] = field(default_factory=list)

    def summary(self) -> str:
        """Human-readable summary for the skill to display."""
        lines = []
        for step in self.steps_completed:
            lines.append(f"  {step} \u2713")
        for step, reason in self.steps_skipped:
            lines.append(f"  {step} \u2717 ({reason})")
        lines.append(f"  Temps: {self.duration_seconds:.1f}s")
        lines.append(f"  Camps pre-omplerts: {len(self.prefills)}")
        return '\n'.join(lines)


def auto_extract(
    project_path: str | Path,
    *,
    skip_phase3: bool = False,
    on_progress: Callable[[str, dict], None] | None = None,
) -> AutoExtractionResult:
    """
    Run all extraction phases on a project folder.

    Args:
        project_path: Path to the project folder
        skip_phase3: If True, skip HTTP API calls (Phase 3)

    Returns:
        AutoExtractionResult with prefills, sources, and diagnostics
    """
    t0 = time.monotonic()
    project_path = Path(project_path)
    result = AutoExtractionResult()

    def emit(event_type: str, detail: dict):
        if on_progress:
            on_progress(event_type, detail)

    # Load existing user_data.json for UTM coords (needed by Phase 3)
    existing_user_data = _load_existing_user_data(project_path)

    # --- Phase 0.1: Content discovery ---
    emit("step", {"step": "scan", "status": "active"})
    _phase1_file_scanner(project_path, result)
    if result.file_mapping and hasattr(result.file_mapping, 'roles'):
        for role_name, role_obj in result.file_mapping.roles.items():
            path = role_obj.path if hasattr(role_obj, 'path') else str(role_obj)
            emit("file", {"name": Path(path).name, "role": role_name})
    _phase01_content_discovery(project_path, result)
    _phase01_pressupost_pdf(project_path, result)
    _phase01_historia_geologica(project_path, result)
    emit("step", {"step": "scan", "status": "done", "count": len(result.file_mapping.roles) if result.file_mapping and hasattr(result.file_mapping, 'roles') else 0})

    # --- Phase 0.3: FileMiner ---
    emit("step", {"step": "mine", "status": "active"})
    emit("phase_start", {"phase": "0.3", "name": "FileMiner"})
    _phase03_fileminer(project_path, result, emit)
    fm_sigs = len(result.mining_result.signals) if result.mining_result else 0
    fm_mapped = sum(1 for s in (result.mining_result.signals if result.mining_result else []) if s.maps_to)
    emit("phase_complete", {"phase": "0.3", "name": "FileMiner", "signals": fm_sigs, "mapped": fm_mapped})
    emit("groq", {"name": "FileMiner regex", "ok": bool(result.mining_result and result.mining_result.signals)})

    # --- Phase 0.4: Groq Deep Mine (targeted gap-filling) ---
    emit("phase_start", {"phase": "0.4", "name": "Groq LLM"})
    _phase04_groq_deep_mine(project_path, result, emit)
    emit("step", {"step": "mine", "status": "done", "count": len(result.mining_result.signals) if result.mining_result else 0})

    # --- Phase 0.45: ConceptScout (after Groq enrichment, before local extractors) ---
    _phase045_concept_scout(project_path, result, emit)

    # --- Phase 0.46: Deep folder classify (uses ConceptScout probes + vision) ---
    _phase046_deep_folder_classify(project_path, result, emit)

    # --- Phase 0.47: Re-mine files newly promoted to roles ---
    _phase047_remine_promoted(project_path, result, emit)

    # --- Phase 1: Local files ---
    emit("step", {"step": "extract", "status": "active"})
    emit("phase_start", {"phase": "1", "name": "DPSH + Dates"})
    _phase1_dpsh(project_path, result)
    emit("source", {"name": "DPSH Excel", "ok": result.dpsh_data is not None and bool(getattr(result.dpsh_data, 'tests', None))})
    _phase1_field_dates(project_path, result)
    emit("source", {"name": "Dates camp", "ok": 'field_work_dates' in result.prefills})
    emit("phase_complete", {"phase": "1", "name": "DPSH + Dates"})

    # --- Phase 2: PDF extraction ---
    emit("phase_start", {"phase": "2", "name": "Lab PDF"})
    _phase2_lab_results(project_path, result)
    emit("source", {"name": "Lab PDF", "ok": result.lab_results is not None and result.lab_results.sulfate_mg_kg is not None})
    emit("phase_complete", {"phase": "2", "name": "Lab PDF"})

    # --- Phase 2.5+3: Geocode + HTTP APIs ---
    emit("phase_start", {"phase": "3", "name": "APIs HTTP"})
    if not skip_phase3:
        utm_x = existing_user_data.get('utm_x') or result.prefills.get('utm_x')
        utm_y = existing_user_data.get('utm_y') or result.prefills.get('utm_y')

        if not (utm_x and utm_y):
            utm_x, utm_y = _phase25_geocode(
                existing_user_data, result, project_path,
            )
        geocode_data = {"utm_x": utm_x, "utm_y": utm_y} if utm_x and utm_y else None
        if geocode_data:
            geocode_data["superficie_cadastral_m2"] = result.prefills.get('superficie_cadastral_m2', '')
            geocode_data["cadastral_ref"] = result.prefills.get('cadastral_ref', '')
        emit("source", {"name": "Geocode", "ok": bool(utm_x and utm_y), "data": geocode_data})

        try:
            superficie = float(
                existing_user_data.get('superficie_parcela_m2', 0)
                or result.prefills.get('superficie_parcela_m2', 0)
            )
        except (TypeError, ValueError):
            superficie = 0

        if utm_x and utm_y:
            # --- ICGC APIs use DPSH coords (regional data, ~1km resolution) ---
            emit("api_call", {"api": "ICGC WMS", "action": "geologia", "utm": f"({utm_x:.0f}, {utm_y:.0f})"})
            _phase3_geology(utm_x, utm_y, result)
            geo_ok = 'icgc_unit_code' in result.prefills
            emit("source", {
                "name": "ICGC geologia", "ok": geo_ok,
                "data": {
                    "code": result.prefills.get('icgc_unit_code', ''),
                    "description": result.prefills.get('icgc_unit_description', ''),
                    "epoch": result.prefills.get('icgc_unit_epoch', ''),
                } if geo_ok else None,
            })

            emit("api_call", {"api": "ICGC MDT", "action": "elevacio", "utm": f"({utm_x:.0f}, {utm_y:.0f})"})
            _phase3_elevation(utm_x, utm_y, result)
            elev_ok = 'cota_referencia' in result.prefills
            emit("source", {
                "name": "ICGC elevació", "ok": elev_ok,
                "data": {"cota": result.prefills.get('cota_referencia', '')} if elev_ok else None,
            })

            emit("api_call", {"api": "ICGC MDT", "action": "pendent", "utm": f"({utm_x:.0f}, {utm_y:.0f})"})
            _phase3_slope(utm_x, utm_y, result)
            slope_ok = 'is_sloped' in result.prefills
            emit("source", {
                "name": "ICGC pendent", "ok": slope_ok,
                "data": {
                    "percent": result.prefills.get('slope_percent', ''),
                    "direction": result.prefills.get('slope_direction', ''),
                    "is_sloped": result.prefills.get('is_sloped', ''),
                } if slope_ok else None,
            })

            # --- Geocode-first for parcel identification ---
            # DPSH coordinates indicate where the test MACHINE was, not the
            # project parcel. The street address (from plànol/pressupost) is
            # a more reliable indicator of the project location. Geocoded
            # coords are used for Cadastre adjacents, ortho enrichment, and
            # all parcel-specific operations. DPSH coords remain for ICGC
            # geology/elevation/slope (regional data, ~1km resolution).
            #
            # Evidence: 4/4 projects with COORDENADES.txt have DPSH on a
            # different Cadastre parcel (Bell-Lloc: 113m off, Castellar: 65m,
            # Linyola: 46m). This is normal — the DPSH truck parks on the
            # nearest accessible ground, often a neighboring parcel or road.
            parcel_x, parcel_y = utm_x, utm_y  # default: DPSH coords
            street_addr = (
                result.prefills.get('street_address')
                or (existing_user_data or {}).get('street_address', '')
            )
            site_addr = (
                result.prefills.get('site_address')
                or (existing_user_data or {}).get('site_address', '')
            )
            muni = (
                result.prefills.get('site_municipality')
                or (existing_user_data or {}).get('site_municipality', '')
            )
            province = result.prefills.get('province', '')
            for addr_candidate in (street_addr, site_addr):
                if not addr_candidate or not muni or len(addr_candidate) <= 3:
                    continue
                if _is_g3_internal_address(addr_candidate):
                    logger.warning("Geocode-first: REJECTED G3 internal address %r", addr_candidate)
                    continue
                addr_candidate = _clean_street_address(addr_candidate, muni)
                if addr_candidate and len(addr_candidate) > 3:
                    geo_res = _geocode_for_adjacents(addr_candidate, muni, province=province)
                    if geo_res:
                        parcel_x = geo_res['utm_x']
                        parcel_y = geo_res['utm_y']
                        logger.info(
                            f"Geocode-first: using ({parcel_x:.0f}, {parcel_y:.0f}) "
                            f"from '{addr_candidate}' instead of DPSH ({utm_x:.0f}, {utm_y:.0f})"
                        )
                        if geo_res.get('parcel_area') and 'superficie_cadastral_m2' not in result.prefills:
                            result.prefills['superficie_cadastral_m2'] = int(geo_res['parcel_area'])
                            result.sources['superficie_cadastral_m2'] = 'Cadastre WFS (geocode-first)'
                        break

            # --- Validate COORDENADES.txt coords when geocode-first didn't override ---
            # If municipality is unknown, try to extract from project folder name
            validate_muni = muni
            if not validate_muni:
                # Project folder name is like "4001612 BELL-LLOC" — extract municipality part
                folder_name = project_path.name
                parts = folder_name.split(' ', 1)
                if len(parts) == 2:
                    validate_muni = parts[1].strip()
                    logger.debug("Validation: municipality from folder name: %r", validate_muni)
            if parcel_x == utm_x and parcel_y == utm_y and street_addr:
                parcel_x, parcel_y, _was_corrected = _validate_coords_against_address(
                    parcel_x, parcel_y, street_addr, validate_muni, province, result,
                )

            emit("api_call", {"api": "Cadastre", "action": "adjacents", "utm": f"({parcel_x:.0f}, {parcel_y:.0f})", "superficie": superficie})
            resolved_x, resolved_y = _phase3_adjacents(parcel_x, parcel_y, superficie, result, project_path, existing_user_data)
            adj_found = {d: result.prefills.get(f'adjacent_{d}', '') for d in ('north', 'south', 'east', 'west') if result.prefills.get(f'adjacent_{d}')}
            emit("source", {
                "name": "Cadastre adj.", "ok": bool(adj_found),
                "data": {
                    "adjacents": adj_found,
                    "superficie_cadastral_m2": result.prefills.get('superficie_cadastral_m2', ''),
                    "cadastral_ref": result.prefills.get('cadastral_ref', ''),
                } if adj_found else None,
            })

            # P4a: Store resolved coordinates so downstream consumers use the
            # correct project parcel (DPSH test point may be on a neighbor).
            if (resolved_x, resolved_y) != (utm_x, utm_y):
                result.prefills['_resolved_utm_x'] = resolved_x
                result.prefills['_resolved_utm_y'] = resolved_y
                result.sources['_resolved_utm_x'] = 'geocode (address resolution)'
                result.sources['_resolved_utm_y'] = 'geocode (address resolution)'
                logger.info(f"Resolved UTM: ({resolved_x:.0f}, {resolved_y:.0f}) instead of DPSH ({utm_x:.0f}, {utm_y:.0f})")

            # Cadastral parcel area (if not already from geocode)
            if 'superficie_cadastral_m2' not in result.prefills:
                _phase3_cadastral_area(utm_x, utm_y, result)

            # Phase 2.9: Parcel resolution — detect multi-parcel sites
            planol_area = None
            for key in ('superficie_parcela_m2', 'superficie_cadastral_m2'):
                val = result.prefills.get(key) or (existing_user_data or {}).get(key)
                if val:
                    try:
                        planol_area = float(val)
                        break
                    except (ValueError, TypeError):
                        pass
            if planol_area and planol_area > 0:
                try:
                    from .parcel_resolver import resolve_parcel
                    resolved = resolve_parcel(
                        resolved_x, resolved_y,
                        planol_area_m2=planol_area,
                        municipality=result.prefills.get('site_municipality', ''),
                    )
                    if resolved and resolved.is_merged:
                        emit("source", {
                            "name": "Parcel merge", "ok": True,
                            "data": {
                                "refs": resolved.merged_refs,
                                "area": f"{resolved.area_m2:.0f} m²",
                                "method": resolved.resolution_method,
                            },
                        })
                        result.prefills['_resolved_polygon'] = resolved.polygon
                        result.prefills['_resolved_area_m2'] = resolved.area_m2
                        result.prefills['_merged_refs'] = resolved.merged_refs
                        result.sources['_resolved_polygon'] = 'parcel merge'
                        # Update superficie_cadastral with merged area
                        result.prefills['superficie_cadastral_m2'] = int(resolved.area_m2)
                        result.sources['superficie_cadastral_m2'] = f'Cadastre WFS (merge {len(resolved.merged_refs)} parcels)'
                        # Use merged centroid for downstream
                        resolved_x, resolved_y = resolved.centroid
                        logger.info(f"Parcel merge: {resolved.merged_refs} → {resolved.area_m2:.0f} m²")
                except Exception as exc:
                    logger.debug(f"Parcel resolution failed: {exc}")

            # Phase 3.5: Ortho enrichment (ICGC orthophoto + vision analysis)
            # Uses resolved coordinates (project parcel) rather than DPSH test point
            if os.environ.get('G3DT_ORTHO_ENRICHMENT', '') == '1':
                emit("api_call", {"api": "ICGC Ortho", "action": "enrichment", "utm": f"({resolved_x:.0f}, {resolved_y:.0f})"})
                _phase35_ortho_enrichment(resolved_x, resolved_y, result)
                enriched_ok = bool(result.prefills.get('site_description_enriched'))
                emit("source", {
                    "name": "ICGC ortho+visió", "ok": enriched_ok,
                    "data": {
                        "is_anthropized": result.prefills.get('is_anthropized_enriched', ''),
                        "site_description": (result.prefills['site_description_enriched'][:80] + '...') if result.prefills.get('site_description_enriched') else '',
                    } if enriched_ok else None,
                })
        else:
            emit("source", {"name": "APIs HTTP", "ok": False, "reason": "sense UTM"})
            result.steps_skipped.append(
                ("Fase 3: APIs HTTP", "sense coordenades UTM")
            )

    emit("phase_complete", {"phase": "3", "name": "APIs HTTP"})
    emit("step", {"step": "extract", "status": "done"})
    emit("step", {"step": "ready", "status": "done"})
    result.duration_seconds = time.monotonic() - t0
    return result


# ---------------------------------------------------------------------------
# Phase 0: File scanning and content discovery
# ---------------------------------------------------------------------------

def _phase1_file_scanner(project_path: Path, result: AutoExtractionResult) -> None:
    """Run FileScanner (or SmartScan if enabled) to classify project files."""
    import os
    use_smartscan = os.environ.get('G3DT_USE_SMARTSCAN', '1').strip()

    if use_smartscan == '1':
        try:
            from .smartscan import scan_project
            from .file_scanner import FileScanner, FileMapping, FileRole

            scan_result = scan_project(project_path, max_tier=3)
            fm_dict = scan_result.to_file_mapping()

            # Build FileMapping from SmartScan result (backward compat)
            mapping = FileMapping()
            for name, role_data in fm_dict.get('roles', {}).items():
                from .file_scanner import IgnoredFile, get_vision_type
                mapping.roles[name] = FileRole(
                    path=role_data['path'],
                    confidence=role_data['confidence'],
                    detection=role_data['detection'],
                    is_combined=role_data.get('is_combined', False),
                    vision_type=role_data.get('vision_type'),
                )
            from .file_scanner import IgnoredFile
            for ig in fm_dict.get('ignored', []):
                mapping.ignored.append(IgnoredFile(path=ig['path'], reason=ig['reason']))
            mapping.unassigned = fm_dict.get('unassigned', [])

            result.file_mapping = mapping
            n_roles = len(mapping.roles)
            result.steps_completed.append(f"SmartScan: {n_roles} rols detectats")

            # Also save file_mapping.json for compatibility
            scanner = FileScanner(project_path)
            scanner.save(mapping)
            return
        except Exception as exc:
            logger.warning(f"SmartScan failed, falling back to FileScanner: {exc}")

    # Default: original FileScanner
    try:
        from .file_scanner import FileScanner
        scanner = FileScanner(project_path)

        # Load existing or scan fresh
        mapping = scanner.load()
        if mapping is None:
            mapping = scanner.scan()
            scanner.save(mapping)

        result.file_mapping = mapping
        n_roles = len(mapping.roles)
        result.steps_completed.append(f"FileScanner: {n_roles} rols detectats")
    except Exception as exc:
        result.steps_skipped.append(("FileScanner", str(exc)))


def _phase03_fileminer(project_path: Path, result: AutoExtractionResult, emit=None) -> None:
    """Run FileMiner to extract data signals from all project files."""
    if not emit:
        emit = lambda *a, **kw: None
    try:
        from .fileminer import mine_project, resolve_competition

        # Convert file_mapping to dict format for FileMiner
        fm_dict = None
        if result.file_mapping:
            try:
                fm_dict = result.file_mapping.to_dict() if hasattr(result.file_mapping, 'to_dict') else None
            except Exception:
                pass

        def _mining_progress(event_type, detail):
            if event_type == 'mining_file':
                emit("file_mined", detail)

        mining = mine_project(project_path, file_mapping=fm_dict, on_progress=_mining_progress)
        result.mining_result = mining

        # Emit per-file signal summary
        from collections import Counter
        file_signal_counts = Counter(s.source_file for s in mining.signals)
        for fname, count in file_signal_counts.most_common():
            mapped = sum(1 for s in mining.signals if s.source_file == fname and s.maps_to)
            emit("file_mined_summary", {"file": fname, "signals": count, "mapped": mapped})

        if not mining.signals:
            result.steps_completed.append(
                f"FileMiner: {mining.files_mined} fitxers, cap senyal"
            )
            return

        resolved = resolve_competition(mining.signals)

        # Feed resolved values into prefills.
        # Override existing Phase 0.1 values when FileMiner has a better
        # (lower) per-concept priority for the same variable.
        from automation.schemas.loader import ConceptRegistry
        _cr = ConceptRegistry()

        n_added = 0
        _ADDRESS_VARS = {'street_address', 'site_address', 'client_address'}
        # Phase 0.1 source types that FileMiner may legitimately override
        _OVERRIDABLE_SOURCES = {
            'contingut:', 'content_discovery:', 'pressupost:',
        }
        for variable, rv in resolved.items():
            should_write = False
            if variable not in result.prefills:
                should_write = True
            else:
                # Check if FileMiner winner has better per-concept priority
                existing_src = result.sources.get(variable, '')
                if any(existing_src.startswith(pfx) for pfx in _OVERRIDABLE_SOURCES):
                    fm_pri = rv.signal.priority
                    # Infer existing source type from source string
                    existing_pri = 50  # default
                    if 'DADES' in existing_src.upper() or 'dades_camp' in existing_src:
                        existing_pri = _cr.get_priority(variable, 'dades_camp_excel')
                    elif 'PRESSUPOST' in existing_src.upper() or 'pressupost' in existing_src:
                        existing_pri = _cr.get_priority(variable, 'pressupost_pdf')
                    elif 'content_pdf' in existing_src or '.pdf' in existing_src.lower():
                        existing_pri = _cr.get_priority(variable, 'content_pdf')
                    elif 'content_excel' in existing_src or '.xls' in existing_src.lower():
                        existing_pri = _cr.get_priority(variable, 'content_excel')
                    if fm_pri < existing_pri:
                        logger.info(
                            "FileMiner: overriding %s (pri %d < %d): %r -> %r",
                            variable, fm_pri, existing_pri,
                            str(result.prefills[variable])[:50], str(rv.value)[:50],
                        )
                        should_write = True

            if should_write:
                # G3 internal address filter: reject G3 office address as project site
                value = rv.value
                if variable in _ADDRESS_VARS and _is_g3_internal_address(str(value)):
                    logger.warning("FileMiner: REJECTED G3 internal address for %s: %r", variable, value)
                    # Try alternatives
                    promoted = False
                    for alt in rv.alternatives:
                        if not _is_g3_internal_address(str(alt.value)):
                            value = alt.value
                            rv = rv.model_copy(update={'value': value, 'signal': alt})
                            logger.info("FileMiner: promoted alternative for %s: %r", variable, value)
                            promoted = True
                            break
                    if not promoted:
                        continue  # All alternatives are also G3 internal, skip entirely
                result.prefills[variable] = value
                result.sources[variable] = f"fileminer:{rv.signal.source_file}"
                n_added += 1
            # Always store alternatives for wizard display
            if rv.alternatives:
                result.mining_alternatives[variable] = [
                    {'value': alt.value, 'source': alt.source_file, 'confidence': alt.confidence}
                    for alt in rv.alternatives
                ]
            emit("signal_resolved", {
                "variable": variable,
                "winner": rv.signal.source_file,
                "value": str(rv.value)[:100],
                "alts": len(rv.alternatives),
                "method": rv.signal.extraction_method,
            })

        result.steps_completed.append(
            f"FileMiner: {len(mining.signals)} senyals, {len(resolved)} variables, {n_added} nous prefills"
        )

    except Exception as exc:
        logger.warning("FileMiner failed: %s", exc)
        result.steps_skipped.append(("FileMiner", str(exc)))


def _phase04_groq_deep_mine(project_path: Path, result: AutoExtractionResult, emit=None) -> None:
    """Phase 0.4: Use Groq LLM to extract data from files where Python miners underperformed."""
    import os

    if not emit:
        emit = lambda *a, **kw: None
    if os.environ.get('G3DT_USE_GROQ', '1').strip() != '1':
        emit("groq", {"name": "Groq (disabled)", "ok": False})
        return

    try:
        from .fileminer import mine_project_groq, resolve_competition
        from .fileminer.miners.groq_miner import TARGET_VARIABLES

        # Identify which high-value variables are still missing
        missing = [
            var for var in TARGET_VARIABLES
            if var not in result.prefills
        ]

        if not missing:
            logger.info("Phase 0.4 Groq: all target variables already filled, skipping")
            result.steps_completed.append("Groq Deep Mine: cap variable pendent")
            emit("groq", {"name": "Groq (tot cobert)", "ok": True})
            return

        emit("groq_start", {"missing": missing[:15], "count": len(missing)})
        logger.info(
            "Phase 0.4 Groq: %d missing variables: %s",
            len(missing), missing[:10],
        )

        # Get file_mapping dict
        fm_dict = None
        if result.file_mapping:
            try:
                fm_dict = result.file_mapping.to_dict() if hasattr(result.file_mapping, 'to_dict') else None
            except Exception:
                pass

        # Get existing signals from Python miners
        existing_signals = result.mining_result.signals if result.mining_result else []

        # Run Groq miner on candidate files
        groq_signals = mine_project_groq(
            project_path,
            file_mapping=fm_dict,
            missing_variables=missing,
            existing_signals=existing_signals,
        )

        if not groq_signals:
            result.steps_completed.append("Groq Deep Mine: cap senyal nou")
            emit("groq", {"name": "Groq: 0 senyals", "ok": False})
            return

        # Append Groq signals to mining_result so dev-analysis-v2 sees them
        if result.mining_result:
            result.mining_result.signals.extend(groq_signals)

        # Combine with existing signals and re-resolve competition
        all_signals = list(existing_signals) + groq_signals
        resolved = resolve_competition(all_signals)

        # Boolean string → Python bool conversion for toggle fields
        _BOOL_FIELDS = {"has_basement", "has_retaining_walls"}

        # Merge new resolved values into prefills (don't override existing)
        # Note: variable names are already wizard-compatible via maps_to remap in groq_miner
        n_new = 0
        for variable, rv in resolved.items():
            value = rv.value
            # Convert boolean string fields to Python bool
            if variable in _BOOL_FIELDS and isinstance(value, str):
                value = value.lower() in ("true", "si", "sí", "yes", "1")
            if variable not in result.prefills:
                result.prefills[variable] = value
                result.sources[variable] = f"groq_llm:{rv.signal.source_file}"
                n_new += 1
                emit("groq_found", {
                    "variable": variable,
                    "value": str(value)[:100],
                    "file": rv.signal.source_file,
                })
                logger.info(
                    "Phase 0.4 Groq: new prefill %s=%r from %s",
                    variable, value, rv.signal.source_file,
                )
            # Store alternatives for wizard display
            if rv.alternatives:
                existing_alts = result.mining_alternatives.get(variable, [])
                for alt in rv.alternatives:
                    if alt.extraction_method == "groq_llm":
                        existing_alts.append({
                            'value': alt.value,
                            'source': alt.source_file,
                            'confidence': alt.confidence,
                        })
                if existing_alts:
                    result.mining_alternatives[variable] = existing_alts

        try:
            from .fileminer.miners.groq_miner import GroqMiner
            usage = GroqMiner.get_usage_summary()
            result.steps_completed.append(
                f"Groq Deep Mine ({usage['model'].split('/')[-1]}): "
                f"{len(groq_signals)} senyals, {n_new} nous prefills, "
                f"{usage['api_calls']} calls, {usage['cache_hits']} cache hits, "
                f"{usage['total_tokens']} tokens (~${usage['estimated_cost_usd']:.4f})"
            )
        except Exception:
            result.steps_completed.append(
                f"Groq Deep Mine: {len(groq_signals)} senyals, {n_new} nous prefills"
            )
        logger.info(
            "Phase 0.4 Groq: %d new signals, %d new prefills",
            len(groq_signals), n_new,
        )
        emit("phase_complete", {"phase": "0.4", "name": "Groq LLM", "signals": len(groq_signals), "new_prefills": n_new})
        emit("groq", {"name": f"Groq: +{n_new} prefills", "ok": n_new > 0})

    except Exception as exc:
        logger.warning("Phase 0.4 Groq failed: %s", exc)
        result.steps_skipped.append(("Groq Deep Mine", str(exc)))
        emit("phase_complete", {"phase": "0.4", "name": "Groq LLM", "signals": 0, "error": str(exc)})
        emit("groq", {"name": "Groq (error)", "ok": False})


def _phase01_content_discovery(project_path: Path, result: AutoExtractionResult) -> None:
    """Run content discovery to find data in unclassified files."""
    try:
        from .content_discovery import discover_content

        discovery = discover_content(project_path, file_mapping=result.file_mapping)
        result.content_discovery = discovery

        if not discovery.items:
            result.steps_completed.append(
                f"Contingut: {discovery.files_scanned} fitxers escanejats, cap dada nova"
            )
            return

        n_items = len(discovery.items)
        categories = set(item.category for item in discovery.items)
        result.steps_completed.append(
            f"Contingut: {n_items} troballes ({', '.join(sorted(categories))})"
        )

        # Feed discovered data into prefills
        for item in discovery.items:
            if item.category == 'utm_coordinates' and item.confidence in ('high', 'medium'):
                # Use centroid of all points as project UTM
                points = item.data.get('points', {})
                if points and 'utm_x' not in result.prefills:
                    xs = [p['x'] for p in points.values()]
                    ys = [p['y'] for p in points.values()]
                    result.prefills['utm_x'] = round(sum(xs) / len(xs), 2)
                    result.prefills['utm_y'] = round(sum(ys) / len(ys), 2)
                    result.sources['utm_x'] = f"contingut:{item.source_file}"
                    result.sources['utm_y'] = f"contingut:{item.source_file}"
                    # Also store per-point data for the report
                    result.prefills['utm_points'] = item.data['points']
                    result.sources['utm_points'] = f"contingut:{item.source_file}"

            elif item.category == 'field_prep' and item.confidence in ('high', 'medium'):
                # Map field_prep keys to user_data keys
                fp = item.data
                src = f"contingut:{item.source_file}"
                if fp.get('ADREÇA OBRA') and 'site_address' not in result.prefills:
                    result.prefills['site_address'] = fp['ADREÇA OBRA']
                    result.sources['site_address'] = src
                if fp.get('CLIENT') and 'client_name' not in result.prefills:
                    result.prefills['client_name'] = fp['CLIENT']
                    result.sources['client_name'] = src
                if fp.get('PERSONA DE CONTACTE') and 'contact_name' not in result.prefills:
                    result.prefills['contact_name'] = fp['PERSONA DE CONTACTE']
                    result.sources['contact_name'] = src
                if fp.get('ACCES') and 'access_url' not in result.prefills:
                    result.prefills['access_url'] = fp['ACCES']
                    result.sources['access_url'] = src

            elif item.category == 'client_data' and item.confidence in ('high', 'medium'):
                cd = item.data
                src = f"contingut:{item.source_file}"
                if cd.get('nif') and 'client_nif' not in result.prefills:
                    result.prefills['client_nif'] = cd['nif']
                    result.sources['client_nif'] = src
                if cd.get('name') and 'client_name' not in result.prefills:
                    result.prefills['client_name'] = cd['name']
                    result.sources['client_name'] = src
                if cd.get('email') and 'client_email' not in result.prefills:
                    result.prefills['client_email'] = cd['email']
                    result.sources['client_email'] = src

    except Exception as exc:
        result.steps_skipped.append(("Contingut", str(exc)))


def _phase01_pressupost_pdf(project_path: Path, result: AutoExtractionResult) -> None:
    """Extract architect company from pressupost PDF (page 1, OBRA field)."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        result.steps_skipped.append(("Pressupost PDF", "PyMuPDF no disponible"))
        return

    # Find pressupost PDF in ACCEPTACIO/ or numbered subfolder (e.g. 25.0647/)
    candidates = []
    for subdir in (project_path / 'ACCEPTACIO', project_path):
        if subdir.is_dir():
            candidates.extend(subdir.glob('PRESSUPOST*.pdf'))
    # Also check numbered subfolders (e.g. 25.0647/)
    for child in project_path.iterdir():
        if child.is_dir() and re.match(r'^\d', child.name):
            candidates.extend(child.glob('PRESSUPOST*.pdf'))

    if not candidates:
        result.steps_skipped.append(("Pressupost PDF", "fitxer no trobat"))
        return

    # Use the first found
    pdf_path = candidates[0]
    try:
        doc = fitz.open(str(pdf_path))
        if len(doc) == 0:
            result.steps_skipped.append(("Pressupost PDF", "PDF buit"))
            return

        # Read page 1 — architect company is typically after "OBRA:" header
        text = doc[0].get_text()
        doc.close()

        if not text.strip():
            result.steps_skipped.append(("Pressupost PDF", "pàgina 1 sense text"))
            return

        # Parse: look for OBRA line followed by architect company name
        # Format typically:
        #   OBRA:
        #   ARQUITECTURA BOSCH NOVELL
        #   ESTUDI GEOTECNIC
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        architect_company = None
        for i, line in enumerate(lines):
            if re.match(r'^OBRA\s*:?\s*$', line, re.IGNORECASE):
                # Next non-empty line is the architect company
                if i + 1 < len(lines):
                    candidate = lines[i + 1]
                    # Skip if it's "ESTUDI GEOTECNIC" or similar generic text
                    if not re.match(r'^ESTUDI\s+GEO', candidate, re.IGNORECASE):
                        architect_company = candidate
                break

        if architect_company and 'architect_company' not in result.prefills:
            result.prefills['architect_company'] = architect_company
            result.sources['architect_company'] = f"pressupost:{pdf_path.name}"
            result.steps_completed.append(
                f"Pressupost PDF: empresa arquitecte = '{architect_company}'"
            )
        else:
            result.steps_skipped.append(("Pressupost PDF", "empresa arquitecte no trobada"))

    except Exception as exc:
        result.steps_skipped.append(("Pressupost PDF", str(exc)))


def _phase01_historia_geologica(project_path: Path, result: AutoExtractionResult) -> None:
    """Match project municipality to Eva's geological history templates."""
    try:
        from .folder_utils import parse_folder_name
        from .historia_geologica import lookup_municipality

        _, municipality = parse_folder_name(project_path.name)
        if not municipality:
            result.steps_skipped.append(("Historia geològica", "sense municipi al nom de carpeta"))
            return

        match = lookup_municipality(municipality)
        if match:
            result.prefills['historia_geologica_template'] = match.file_path
            result.sources['historia_geologica_template'] = (
                f"Eva template: '{match.matched_location}' (tier {match.tier})"
            )
            result.steps_completed.append(
                f"Historia geològica: '{match.matched_location}' (tier {match.tier}, score {match.score:.2f})"
            )
        else:
            result.steps_skipped.append(
                ("Historia geològica", f"cap match per '{municipality}'")
            )

    except Exception as exc:
        result.steps_skipped.append(("Historia geològica", str(exc)))


def _phase046_deep_folder_classify(
    project_path: Path, result: AutoExtractionResult, emit=None,
) -> None:
    """Phase 0.46: Classify every file ConceptScout discovered but
    FileScanner/SmartScan didn't role-assign.

    Runs AFTER ConceptScout so probe caches are hot. Covers email
    attachments + deep subdirectories (ANNEXES/ALTRES, FOTOGRAFIES/S1,
    ANEXOS/OTROS, etc.). Promotes only empty roles; always records
    provenance in `file_mapping.deep_folder_files`.
    """
    if not emit:
        emit = lambda *a, **kw: None
    try:
        from .deep_folder_classifier import classify_unclassified_files
        from .file_scanner import FileScanner

        mapping = result.file_mapping
        if mapping is None or not hasattr(mapping, 'deep_folder_files'):
            result.steps_skipped.append(
                ("Deep folder classify", "no file_mapping")
            )
            return

        # Use OpenAI vision when available; otherwise filename/probe-cache only
        vision_client = "auto" if os.environ.get('OPENAI_API_KEY') else None

        before_roles = set(mapping.roles.keys())
        prov = classify_unclassified_files(
            project_path, mapping, vision_client=vision_client,
        )
        new_role_files: list[tuple[str, str]] = [
            (v['role_assigned'], rel_path)
            for rel_path, v in prov.items()
            if v.get('role_assigned') and v['role_assigned'] not in before_roles
        ]
        # Track on the result so phase 0.47 can re-mine without re-checking
        result.deep_folder_promoted = new_role_files

        try:
            scanner = FileScanner(project_path)
            scanner.save(mapping)
        except Exception as exc:
            logger.warning("Deep folder classify: save failed: %s", exc)

        n_total = len(prov)
        n_cache = sum(1 for v in prov.values() if v['classifier_used'] == 'probe_cache')
        n_filename = sum(1 for v in prov.values() if v['classifier_used'] == 'filename')
        n_vision = sum(1 for v in prov.values() if v['classifier_used'] == 'vision')
        n_unclass = sum(1 for v in prov.values() if v['classifier_used'] == 'unclassified')

        result.steps_completed.append(
            f"Deep folder classify: {n_total} files "
            f"(probe_cache={n_cache}, filename={n_filename}, vision={n_vision}, "
            f"unclassified={n_unclass}); promoted={len(new_role_files)}"
        )
        emit("phase_complete", {
            "phase": "0.46", "name": "Deep folder classify",
            "total": n_total, "probe_cache": n_cache, "filename": n_filename,
            "vision": n_vision, "unclassified": n_unclass,
            "promoted": len(new_role_files),
        })

    except Exception as exc:
        logger.warning("Deep folder classify failed: %s", exc)
        result.steps_skipped.append(("Deep folder classify", str(exc)))


def _phase047_remine_promoted(
    project_path: Path, result: AutoExtractionResult, emit=None,
) -> None:
    """Phase 0.47: Re-mine newly-promoted files so their signals reach
    downstream extractors.

    FileMiner phase 0.3 walked the project before deep folder classify
    promoted new roles. Files in deep subfolders that FileMiner skipped
    (e.g. FOTOGRAFIES/, msg_attachments/ non-text) get their FileMiner
    signals mined here. Text-extractable files already covered by phase
    0.3 remain untouched (FileMiner is idempotent per file).
    """
    if not emit:
        emit = lambda *a, **kw: None
    promoted = getattr(result, 'deep_folder_promoted', None) or []
    if not promoted:
        return
    try:
        from .fileminer import mine_project
        from .fileminer.models import Signal

        # FileMiner's mine_project mines the full tree; we run it and
        # keep only signals for the newly-promoted files (scoped by rel_path).
        promoted_paths = {rel_path for _, rel_path in promoted}
        new_mining = mine_project(project_path)
        existing_sigs: list[Signal] = (
            result.mining_result.signals if result.mining_result else []
        )
        existing_keys: set[tuple] = {
            (s.concept_id or '', s.source_file, str(s.value), s.extraction_method)
            for s in existing_sigs
        }
        added = 0
        for sig in new_mining.signals:
            if sig.source_file not in promoted_paths:
                continue
            key = (sig.concept_id or '', sig.source_file, str(sig.value), sig.extraction_method)
            if key in existing_keys:
                continue
            existing_sigs.append(sig)
            existing_keys.add(key)
            added += 1

        result.steps_completed.append(
            f"Re-mine promoted: {len(promoted)} files, {added} new signals"
        )
        emit("phase_complete", {
            "phase": "0.47", "name": "Re-mine promoted",
            "files": len(promoted), "new_signals": added,
        })

    except Exception as exc:
        logger.warning("Re-mine promoted failed: %s", exc)
        result.steps_skipped.append(("Re-mine promoted", str(exc)))


def _phase045_concept_scout(project_path: Path, result: AutoExtractionResult, emit) -> None:
    """Phase 0.45: Build concept-to-file map from FileMiner + Groq signals + vision probe."""
    try:
        from automation.concept_scout import scout_project
        concept_map = scout_project(
            project_path,
            mining_result=result.mining_result,
            use_vision_probe=bool(os.environ.get('ANTHROPIC_API_KEY')),
            on_progress=emit,
        )
        result.concept_map = concept_map
        result.steps_completed.append(
            f"ConceptScout: {len(concept_map.concept_sources)} concepts mapped"
        )
    except Exception as exc:
        logger.warning("ConceptScout failed: %s", exc)
        result.steps_skipped.append(("ConceptScout", str(exc)))
        return

    # Merge vision-probe signals into the competition pool and re-resolve.
    # Without this, vision extractions (e.g. planol street_address) never
    # compete against text-extracted signals (e.g. G3 lab order Excel with
    # G3's own office address), and the wrong value wins.
    _merge_vision_signals_into_competition(result)


def _merge_vision_signals_into_competition(result: AutoExtractionResult) -> None:
    """Re-run FileMiner competition including ConceptScout vision-probe signals.

    Only updates prefills/sources for concepts whose winner changed. Concepts
    where no vision signal exists are untouched (the re-competition returns
    the same winner the initial competition produced).
    """
    if result.concept_map is None:
        return
    if result.mining_result is None or not result.mining_result.signals:
        return

    try:
        from .concept_scout import concept_sources_to_signals
        from .fileminer import resolve_competition
    except Exception as exc:
        logger.warning("Vision-signal merge: import failed: %s", exc)
        return

    vision_signals = concept_sources_to_signals(result.concept_map.concept_sources)
    if not vision_signals:
        return

    combined = list(result.mining_result.signals) + vision_signals
    try:
        resolved = resolve_competition(combined)
    except Exception as exc:
        logger.warning("Vision-signal merge: re-competition failed: %s", exc)
        return

    _ADDRESS_VARS = {'street_address', 'site_address', 'client_address'}
    promoted: list[str] = []
    for variable, rv in resolved.items():
        # Only consider concepts where a vision signal actually competed.
        if not any(
            s.extraction_method.startswith('vision_probe:')
            and (s.concept_id == variable or s.maps_to == variable)
            for s in vision_signals
        ):
            continue
        # Only promote when the winning signal is a vision-probe one (this is
        # the "vision actually won" signal — skip if text still beat vision).
        winning_sig = rv.signal
        if not (winning_sig.extraction_method or '').startswith('vision_probe:'):
            continue
        value = rv.value
        if not isinstance(value, str) or not value.strip():
            continue
        # Defensive: never promote a G3 internal address, even from vision.
        if variable in _ADDRESS_VARS and _is_g3_internal_address(value):
            continue

        existing = result.prefills.get(variable)
        if existing == value:
            continue
        logger.info(
            "Vision-signal merge: promoting %s winner to vision (%s): %r -> %r",
            variable, winning_sig.source_type, str(existing)[:60], str(value)[:60],
        )
        result.prefills[variable] = value
        result.sources[variable] = f"vision_probe:{winning_sig.source_file}"
        promoted.append(variable)

    if promoted:
        result.steps_completed.append(
            f"Vision-signal merge: {len(promoted)} winner(s) promoted "
            f"({', '.join(promoted[:8])})"
        )


# ---------------------------------------------------------------------------
# Phase 1: Local files
# ---------------------------------------------------------------------------

def _phase1_dpsh(project_path: Path, result: AutoExtractionResult) -> None:
    """Extract DPSH data from Excel and derive prefills."""
    try:
        from .dpsh_extractor import DPSHExtractor
        from .file_scanner import FileScanner

        # Find DPSH Excel via file_mapping or glob
        dpsh_path = _find_dpsh_excel(project_path, result.file_mapping)
        if not dpsh_path:
            result.steps_skipped.append(("DPSH Excel", "fitxer no trobat"))
            return

        extractor = DPSHExtractor(str(dpsh_path))
        dpsh_data = extractor.extract_all()
        result.dpsh_data = dpsh_data

        # Derive prefills from DPSH
        if dpsh_data and dpsh_data.tests:
            # foundation_depth_m: heuristic from refusal depth
            refusal_depths = [
                t.refusal_depth for t in dpsh_data.tests
                if t.refusal_depth is not None
            ]
            if refusal_depths:
                # Minimum refusal depth suggests where competent soil starts
                min_refusal = min(abs(d) for d in refusal_depths)
                # Foundation at 0.3m (topsoil) unless refusal is very shallow
                if min_refusal < 0.3:
                    result.prefills['foundation_depth_m'] = round(min_refusal, 1)
                    result.sources['foundation_depth_m'] = f"DPSH refús a {min_refusal:.1f}m"

            # Compute suggested Es for Schmertmann settlement
            avg_n20 = dpsh_data.overall_average_n20
            if avg_n20 > 0:
                nb = avg_n20 / 0.83
                Es_suggested = round(2.5 * nb)
                result.prefills['Es_settlement'] = Es_suggested
                result.sources['Es_settlement'] = f"2.5×Nb (Nb={nb:.1f})"

            info = (
                f"{dpsh_data.num_tests} assaigs, "
                f"prof. max {max(t.depth_reached for t in dpsh_data.tests):.1f}m"
            )
            result.steps_completed.append(f"DPSH: {info}")
        else:
            result.steps_skipped.append(("DPSH Excel", "sense dades vàlides"))

    except Exception as exc:
        result.steps_skipped.append(("DPSH Excel", str(exc)))


def _phase1_field_dates(project_path: Path, result: AutoExtractionResult) -> None:
    """Extract field work dates from PDFs."""
    try:
        from .dpsh_extractor import extract_field_dates, format_dates_catalan

        dates = extract_field_dates(project_path)
        if dates:
            result.prefills['field_work_dates'] = dates
            result.sources['field_work_dates'] = "DPSH/Lab PDF"

            dates_text = format_dates_catalan(dates)
            if dates_text:
                result.prefills['field_work_dates_text'] = dates_text
                result.sources['field_work_dates_text'] = "DPSH/Lab PDF"

            result.steps_completed.append(
                f"Dates camp: {', '.join(dates)}"
            )
        else:
            result.steps_skipped.append(("Dates camp", "cap data trobada als PDFs"))

    except Exception as exc:
        result.steps_skipped.append(("Dates camp", str(exc)))


# ---------------------------------------------------------------------------
# Phase 2: PDF extraction
# ---------------------------------------------------------------------------

def _phase2_lab_results(project_path: Path, result: AutoExtractionResult) -> None:
    """Extract lab results from PDF."""
    try:
        from .lab_extractor import extract_lab_results

        lab = extract_lab_results(project_path)
        result.lab_results = lab

        if lab.sulfate_mg_kg is not None:
            result.prefills['sulfate_mg_kg'] = lab.sulfate_mg_kg
            result.sources['sulfate_mg_kg'] = lab.source_file or "LAB PDF"
            result.steps_completed.append(
                f"Lab: sulfats = {lab.sulfate_mg_kg} mg/kg"
            )
        elif lab.source_file:
            result.steps_completed.append("Lab: PDF trobat però sense sulfats")
        else:
            result.steps_skipped.append(("Lab PDF", "fitxer no trobat"))

        if lab.tests:
            lab_tests_data = [t.to_dict() for t in lab.tests]
            result.prefills['lab_tests'] = lab_tests_data
            result.sources['lab_tests'] = lab.source_file or "LAB PDF"

        # Wire lab metadata fields to prefills
        gtl_fields = [
            'lab_location', 'lab_sample_id', 'lab_depth', 'lab_tests_text',
        ]
        constant_fields = [
            'lab_field_company', 'lab_testing_company',
            'lab_field_description', 'lab_testing_description',
        ]
        gtl_source = lab.gtl_source_file or lab.source_file or "GTL report"
        for field_name in gtl_fields:
            value = getattr(lab, field_name, '')
            if value:
                result.prefills[field_name] = value
                result.sources[field_name] = gtl_source
        for field_name in constant_fields:
            value = getattr(lab, field_name, '')
            if value:
                result.prefills[field_name] = value
                result.sources[field_name] = "constant"

    except ImportError:
        result.steps_skipped.append(("Lab PDF", "PyMuPDF no disponible"))
    except Exception as exc:
        result.steps_skipped.append(("Lab PDF", str(exc)))


# ---------------------------------------------------------------------------
# Phase 2.5: Geocode coordinates fallback
# ---------------------------------------------------------------------------

def _phase25_geocode(
    existing_user_data: dict[str, Any],
    result: AutoExtractionResult,
    project_path: Path,
) -> tuple[float | None, float | None]:
    """
    Attempt to derive UTM coordinates from the project's street address.

    Called when no COORDENADES.txt was found and no UTM coords are available.
    Uses Nominatim + Cadastre APIs to geocode the address.

    Returns:
        Tuple of (utm_x, utm_y) or (None, None) if geocoding fails.
    """
    try:
        from .geocode_coordinates import geocode_project
    except ImportError as e:
        result.steps_skipped.append(("Geocodificació", f"mòdul no disponible: {e}"))
        return None, None

    # Get address from existing data or prefills
    address = (
        existing_user_data.get('street_address')
        or existing_user_data.get('site_address')
        or result.prefills.get('site_address')
    )

    # Defensive preference: if ConceptScout extracted a high-confidence
    # architect-plan street_address, use it instead of whatever propagated
    # into prefills. This shields geocode from misrouted text signals.
    vision_addr = _best_vision_address(result)
    if vision_addr and not _is_g3_internal_address(vision_addr):
        if address and address != vision_addr:
            logger.info(
                "Geocode: using vision-extracted architect-plan address %r over prefill %r",
                vision_addr, address,
            )
        address = vision_addr

    if not address:
        result.steps_skipped.append(
            ("Geocodificació", "sense adreça disponible")
        )
        return None, None

    # Reject G3 internal address
    if _is_g3_internal_address(address):
        logger.warning("Geocodificació: REJECTED G3 internal address %r", address)
        result.steps_skipped.append(
            ("Geocodificació", f"adreça interna G3: {address[:40]}")
        )
        return None, None

    # Get municipality from folder name (e.g., "4001612 BELL-LLOC" -> "Bell-Lloc")
    municipality = _extract_municipality(project_path)
    if not municipality:
        result.steps_skipped.append(
            ("Geocodificació", "sense municipi (nom carpeta)")
        )
        return None, None

    # Strip municipality name from address (e.g., "MESTRE RAMON ORTIZ 15 BELL-LLOC" → clean)
    address = _clean_street_address(address, municipality)

    # Get point IDs from DPSH data if available
    point_ids = ['P-1']
    if result.dpsh_data and hasattr(result.dpsh_data, 'test_ids'):
        point_ids = result.dpsh_data.test_ids or ['P-1']

    logger.info(
        f"Geocodificant: '{address}', {municipality}, punts: {point_ids}"
    )

    province = result.prefills.get('province', '')

    # Always route through geocode_project: Callejero's fuzzy matcher on raw
    # addresses can silently pick neighbouring parcels (e.g. Vilanova "Urb. La
    # Serra" suffix). geocode_project runs CartoCiudad first, then reconciles
    # with Cadastre, yielding the authoritative RC. Callejero is still used
    # internally inside geocode_project's own pipeline.
    try:
        geo_result = geocode_project(
            address, municipality, point_ids, output_dir=None, province=province,
        )
    except Exception as exc:
        result.steps_skipped.append(("Geocodificació", str(exc)))
        return None, None

    if geo_result is None:
        result.steps_skipped.append(
            ("Geocodificació", "no s'han trobat coordenades")
        )
        return None, None

    # Store results in prefills
    utm_x = geo_result['utm_x']
    utm_y = geo_result['utm_y']
    source = geo_result.get('source', 'geocode')

    result.prefills['utm_x'] = round(utm_x, 2)
    result.sources['utm_x'] = source
    result.prefills['utm_y'] = round(utm_y, 2)
    result.sources['utm_y'] = source

    if geo_result.get('points'):
        result.prefills['utm_points'] = geo_result['points']
        result.sources['utm_points'] = source

    if geo_result.get('rc'):
        result.prefills['cadastral_ref'] = geo_result['rc']
        result.sources['cadastral_ref'] = source

    if geo_result.get('parcel_area'):
        result.prefills['superficie_cadastral_m2'] = int(geo_result['parcel_area'])
        result.sources['superficie_cadastral_m2'] = source

    result.steps_completed.append(
        f"Geocodificació: UTM ({utm_x:.0f}, {utm_y:.0f}) [{source}]"
    )

    return utm_x, utm_y


def _extract_municipality(project_path: Path) -> str | None:
    """
    Extract municipality name from project folder name.

    Thin wrapper around folder_utils.parse_folder_name() that adds
    Catalan accent corrections for folder names that lost diacritics.
    """
    from .folder_utils import parse_folder_name, municipality_for_report
    _, municipality = parse_folder_name(project_path.name)
    if not municipality:
        return None
    municipality = municipality_for_report(municipality)

    # Fix common articles that shouldn't be capitalized
    # (parse_folder_name handles hyphens well, but space-separated
    # folders like "CASTELLAR DEL VALLES" get .title() with uppercase articles)
    for article in (' Del ', ' De ', ' D\'', ' El ', ' La ', ' Les ', ' Els ', ' Dels '):
        municipality = municipality.replace(article, article.lower())

    # Known corrections for accent marks lost in uppercase folder names
    _ACCENT_CORRECTIONS = {
        'Valles': 'Vallès',
        'Rubi': 'Rubí',
        "D'Urgell": "d'Urgell",
    }
    for wrong, right in _ACCENT_CORRECTIONS.items():
        municipality = municipality.replace(wrong, right)

    return municipality


# ---------------------------------------------------------------------------
# Phase 3: HTTP APIs
# ---------------------------------------------------------------------------

def _phase3_geology(utm_x: float, utm_y: float, result: AutoExtractionResult) -> None:
    """Query ICGC for geological unit."""
    try:
        from .icgc_geology import get_geological_unit

        unit = get_geological_unit(utm_x, utm_y)
        result.prefills['icgc_unit_code'] = unit.code
        result.sources['icgc_unit_code'] = "ICGC WMS 1:50k"
        result.prefills['icgc_unit_description'] = unit.description
        result.sources['icgc_unit_description'] = "ICGC WMS 1:50k"
        result.prefills['icgc_unit_epoch'] = unit.epoch
        result.sources['icgc_unit_epoch'] = "ICGC WMS 1:50k"

        result.steps_completed.append(
            f"ICGC: unitat {unit.code} ({unit.epoch})"
        )
    except Exception as exc:
        result.steps_skipped.append(("ICGC geologia", str(exc)))


def _phase3_elevation(utm_x: float, utm_y: float, result: AutoExtractionResult) -> None:
    """Query ICGC MDT for elevation."""
    try:
        from .icgc_geology import get_elevation, format_cota_referencia

        elev = get_elevation(utm_x, utm_y)
        cota = format_cota_referencia(elev)
        result.prefills['cota_referencia'] = cota
        result.sources['cota_referencia'] = "ICGC MDT 2m"

        result.steps_completed.append(f"Elevació: {cota} m")
    except Exception as exc:
        result.steps_skipped.append(("ICGC elevació", str(exc)))


def _phase3_slope(utm_x: float, utm_y: float, result: AutoExtractionResult) -> None:
    """Query ICGC MDT for slope to determine is_sloped."""
    try:
        from .icgc_geology import get_slope

        slope_pct, direction = get_slope(utm_x, utm_y)
        is_sloped = slope_pct > 15.0
        result.prefills['is_sloped'] = is_sloped
        result.sources['is_sloped'] = f"ICGC MDT ({slope_pct:.0f}% {direction})"

        # Preserve numeric slope data for slope stability calculation (§4.5)
        result.prefills['slope_percent'] = round(slope_pct, 1)
        result.sources['slope_percent'] = "ICGC MDT 2m"
        result.prefills['slope_direction'] = direction
        result.sources['slope_direction'] = "ICGC MDT 2m"

        status = "pendent" if is_sloped else "pla"
        result.steps_completed.append(
            f"Pendent: {slope_pct:.0f}% {direction} → {status}"
        )
    except Exception as exc:
        result.steps_skipped.append(("ICGC pendent", str(exc)))


def _phase3_adjacents(
    utm_x: float,
    utm_y: float,
    superficie: float,
    result: AutoExtractionResult,
    project_path: Path | None = None,
    existing_user_data: dict[str, Any] | None = None,
) -> tuple[float, float]:
    """Query Cadastre API for adjacent parcels.

    For adjacents, the PROJECT PARCEL address (from planol/docs) is preferred
    over the DPSH test point coordinates (from COORDENADES.txt), because test
    points may be on a neighboring parcel.

    Returns (adj_x, adj_y) — the coordinates actually used (may differ from
    input if geocoded from street address).
    """
    try:
        from .cadastre_adjacents import get_adjacent_parcels, get_cadastral_reference

        if superficie <= 0:
            superficie = 500.0  # Conservative default

        # Prefer full municipality from user_data/prefills (has articles like "d'Urgell")
        # Fall back to folder name extraction (may lose articles)
        municipality = (
            (existing_user_data or {}).get('site_municipality')
            or result.prefills.get('site_municipality')
            or (_extract_municipality(project_path) if project_path else None)
        )

        # Prefer planol/docs street address for adjacents — geocode it to find
        # the correct project parcel (DPSH test points may be on a neighbor)
        adj_x, adj_y = utm_x, utm_y
        adj_source = "DPSH coords"
        # Try planol street_address first, then site_address from docs/pressupost
        address_candidates = []
        # Defensive preference: vision-extracted architect-plan address wins
        # even if the winning prefill is already something else (e.g. Groq
        # picked up a municipality center instead).
        vision_addr = _best_vision_address(result)
        if vision_addr and not _is_g3_internal_address(vision_addr):
            cleaned = _clean_street_address(vision_addr, municipality) if municipality else vision_addr
            if cleaned and cleaned not in address_candidates:
                address_candidates.append(cleaned)
        for key in ('street_address', 'site_address'):
            val = result.prefills.get(key) or (existing_user_data or {}).get(key)
            if val and isinstance(val, str) and len(val) > 3:
                if _is_g3_internal_address(val):
                    logger.warning("Adjacents: REJECTED G3 internal address for %s: %r", key, val)
                    continue
                if municipality:
                    val = _clean_street_address(val, municipality)
                address_candidates.append(val)

        # P1: Also try client_address as last resort (often from Groq, may have better spelling)
        # Filter: must look like a real street address (has digit, length > 10) to avoid
        # partial addresses like "LLEIDA" that would geocode to city center
        for key in ('client_address',):
            val = result.prefills.get(key) or (existing_user_data or {}).get(key)
            if val and isinstance(val, str) and len(val) > 10 and re.search(r'\d', val):
                if _is_g3_internal_address(val):
                    continue
                if val not in address_candidates:
                    address_candidates.append(val)

        province = result.prefills.get('province', '')
        if municipality and address_candidates:
            for addr in address_candidates:
                geo_res = _geocode_for_adjacents(addr, municipality, province=province)
                if geo_res:
                    adj_x, adj_y = geo_res['utm_x'], geo_res['utm_y']
                    adj_source = f"geocode({addr})"
                    # Store cadastral area if found
                    if geo_res.get('parcel_area') and 'superficie_cadastral_m2' not in result.prefills:
                        result.prefills['superficie_cadastral_m2'] = int(geo_res['parcel_area'])
                        result.sources['superficie_cadastral_m2'] = 'Cadastre WFS (geocode)'
                    logger.info(
                        f"Adjacents: using geocoded address ({adj_x:.0f}, {adj_y:.0f}) "
                        f"instead of DPSH coords ({utm_x:.0f}, {utm_y:.0f})"
                    )
                    break

        from .parcel_context import parse_rc_list
        rc_list = parse_rc_list((existing_user_data or {}).get('cadastral_refs'))
        rc14 = rc_list or result.prefills.get('cadastral_ref')
        if rc_list:
            adj_source = f"referències llegides {'+'.join(rc_list)}"
        adjacents = get_adjacent_parcels(
            adj_x, adj_y, superficie, rc14=rc14, municipality=municipality,
        )
        for direction in ('north', 'south', 'east', 'west'):
            key = f'adjacent_{direction}'
            if direction in adjacents and adjacents[direction]:
                result.prefills[key] = adjacents[direction]
                result.sources[key] = f"Cadastre API ({adj_source})"

        n = sum(1 for d in ('north', 'south', 'east', 'west') if d in adjacents)
        result.steps_completed.append(f"Cadastre: {n} adjacents detectats")
        return (adj_x, adj_y)
    except Exception as exc:
        logger.warning(f"Cadastre adjacents failed: {exc}")
        result.steps_skipped.append(("Cadastre adjacents", str(exc)))
        return (utm_x, utm_y)


def _geocode_for_adjacents(
    street_address: str,
    municipality: str,
    province: str = "",
) -> dict | None:
    """Geocode a street address to UTM for adjacents probing.

    Routes through geocode_project with progressive address variants.
    Callejero is exercised inside geocode_project's own pipeline, but not as
    a pre-empt here — its fuzzy matcher on raw addresses can silently pick
    a neighbouring parcel (e.g. Vilanova "Urb. La Serra" suffix).

    Returns full geo_result dict (utm_x, utm_y, parcel_area, rc, ...) or None.
    """
    try:
        from .geocode_coordinates import geocode_project
    except ImportError as e:
        logger.debug(f"geocode_coordinates not available: {e}")
        return None

    # Build candidate addresses: full → stripped number → bare name
    candidates = [street_address]

    # Strip house number variants: "#7", "Nº 39", "nº7", ", 16", "18A-18B-20"
    stripped = re.sub(r'[\s,]+(?:#|Nº\s*|nº\s*|n[úu]m\.?\s*)?\d[\dA-Za-z\-]*\s*$', '', street_address).strip()
    if stripped and stripped != street_address:
        candidates.append(stripped)

    # Strip street type prefix: "Carrer X" → "X", "C/ X" → "X"
    bare = re.sub(
        r'^(?:Carrer|Calle|CL|C/|Avinguda|Avenida|AV|Camí|Camino|'
        r'Passeig|Paseo|Plaça|Plaza|Travessia|Travesia|Partida|'
        r'Ronda|Passatge|Carretera)\s+',
        '', stripped or street_address, flags=re.IGNORECASE,
    ).strip()
    if bare and bare != stripped and bare != street_address:
        candidates.append(bare)

    for addr in candidates:
        try:
            geo_result = geocode_project(
                addr, municipality, ['centre'], output_dir=None, province=province,
            )
            if geo_result and geo_result.get('utm_x') and geo_result.get('utm_y'):
                logger.info(f"Geocode fallback OK: '{addr}' → ({geo_result['utm_x']:.0f}, {geo_result['utm_y']:.0f})")
                return geo_result
        except Exception as e:
            logger.debug(f"Geocode attempt '{addr}' failed: {e}")

    return None


def _phase3_cadastral_area(
    utm_x: float,
    utm_y: float,
    result: AutoExtractionResult,
) -> None:
    """Get cadastral reference from Cadastre API (area comes from project docs, not API)."""
    try:
        from .cadastre_adjacents import get_cadastral_reference

        rc, _ = get_cadastral_reference(utm_x, utm_y)
        if not rc or len(rc) < 14:
            return

        result.prefills['cadastral_ref'] = rc
        result.sources['cadastral_ref'] = "Cadastre API"
        logger.info(f"Cadastral reference: {rc[:14]}")
    except Exception as exc:
        logger.debug(f"Cadastral reference lookup failed: {exc}")


# ---------------------------------------------------------------------------
# Coordinate validation: COORDENADES.txt vs project street address
# ---------------------------------------------------------------------------

# Strip prefixes common in Catalan/Spanish addresses for fuzzy comparison
_COORD_STRIP_PREFIXES = (
    'carrer ', 'c/ ', 'c. ', 'cl ', 'calle ',
    'avinguda ', 'av. ', 'av ', 'avenida ',
    'plaça ', 'plaza ', 'pl. ',
    'passeig ', 'paseo ',
    'camí ', 'camino ',
    'partida ',
)


def _validate_coords_against_address(
    utm_x: float,
    utm_y: float,
    street_address: str,
    municipality: str,
    province: str,
    result: AutoExtractionResult,
) -> tuple[float, float, bool]:
    """Validate that UTM coords fall on the expected parcel.

    Compares the Cadastre LDT at the given coords with the project's
    street_address.  If they match, coords are good.  If they don't
    match, try geocoding the street_address as fallback.

    Returns (validated_x, validated_y, was_corrected).
    """
    from .cadastre_adjacents import _query_ref_by_coords, CadastreError

    try:
        _ref, ldt = _query_ref_by_coords(utm_x, utm_y)
    except CadastreError:
        return utm_x, utm_y, False  # Can't validate, use as-is

    if not ldt:
        return utm_x, utm_y, False

    # --- Fuzzy match: significant words from street_address vs LDT ---
    ldt_lower = ldt.lower()

    addr_clean = street_address.lower().strip()
    for prefix in _COORD_STRIP_PREFIXES:
        if addr_clean.startswith(prefix):
            addr_clean = addr_clean[len(prefix):]
            break

    # Words longer than 3 chars, excluding common type words and municipality
    _SKIP_WORDS = {'carrer', 'calle', 'avinguda', 'avenida', 'plaça', 'plaza'}
    # Also skip municipality words (they appear in ALL LDTs of the same town)
    muni_words = {w.lower() for w in municipality.split() if len(w) > 3}
    addr_words = [
        w for w in addr_clean.split()
        if len(w) > 3 and w not in _SKIP_WORDS and w not in muni_words
    ]

    if addr_words and any(w in ldt_lower for w in addr_words):
        logger.info("Coord validation: OK (LDT %r matches street_address)", ldt[:60])
        return utm_x, utm_y, False

    # --- Mismatch: coords don't point to the expected parcel ---
    logger.warning(
        "Coord validation: MISMATCH — coords point to %r "
        "but project is at %r. Attempting geocode fallback...",
        ldt[:60], street_address,
    )

    # Try geocoding the street address
    try:
        geo_res = _geocode_for_adjacents(street_address, municipality, province=province)
        if geo_res and geo_res.get('utm_x') and geo_res.get('utm_y'):
            new_x, new_y = geo_res['utm_x'], geo_res['utm_y']
            logger.info(
                "Coord validation: using geocoded coords (%.1f, %.1f) "
                "instead of COORDENADES.txt (%.1f, %.1f)",
                new_x, new_y, utm_x, utm_y,
            )
            result.steps_completed.append(
                f"Coord validation: COORDENADES.txt -> wrong parcel "
                f"({ldt[:40]}), geocoded {street_address}"
            )
            return new_x, new_y, True
    except Exception as e:
        logger.warning("Coord validation geocode fallback failed: %s", e)

    # Geocode failed too — use original coords with warning
    result.steps_completed.append(
        f"Coord validation: WARNING — coords may be on wrong parcel "
        f"(LDT: {ldt[:40]})"
    )
    return utm_x, utm_y, False


# ---------------------------------------------------------------------------
# Phase 3.5: Ortho enrichment (ICGC orthophoto + vision analysis)
# ---------------------------------------------------------------------------

def _phase35_ortho_enrichment(
    utm_x: float,
    utm_y: float,
    result: AutoExtractionResult,
) -> None:
    """Download ICGC orthophoto chips, run vision analysis, generate enriched text."""
    try:
        from .cadastre_adjacents import get_parcel_geometry_utm
        from .ortho_enrichment import download_ortho_chips
        from .ortho_vision import analyze_site
        from .site_text_generator import generate_enriched_texts

        # Get parcel polygon — fetch cadastral ref if not already available
        rc14 = result.prefills.get('cadastral_ref', '')
        if not rc14 or len(rc14) < 14:
            from .cadastre_adjacents import get_cadastral_reference
            try:
                rc14, _ = get_cadastral_reference(utm_x, utm_y)
                if rc14 and len(rc14) >= 14:
                    result.prefills['cadastral_ref'] = rc14
                    result.sources['cadastral_ref'] = 'Cadastre API (ortho)'
            except Exception as e:
                logger.debug(f"Cadastral ref lookup for ortho failed: {e}")
        if not rc14 or len(rc14) < 14:
            logger.info("Ortho enrichment: skipped (no cadastral reference)")
            result.steps_skipped.append(("Ortho enrichment", "sense ref. cadastral"))
            return

        polygon = get_parcel_geometry_utm(rc14[:14])
        if not polygon or len(polygon) < 3:
            logger.info("Ortho enrichment: skipped (no parcel polygon)")
            result.steps_skipped.append(("Ortho enrichment", "sense polígon"))
            return

        # Download orthophoto chips
        chips = download_ortho_chips(utm_x, utm_y, polygon)
        if chips.tight_chip_path is None and chips.wide_chip_path is None:
            logger.warning("Ortho enrichment: no chips downloaded")
            result.steps_skipped.append(("Ortho enrichment", "ICGC WMS error"))
            return

        # Collect existing Cadastre adjacents
        cadastre_adj = {
            d: result.prefills.get(f'adjacent_{d}', '')
            for d in ('north', 'south', 'east', 'west')
        }

        # Run vision analysis
        analysis = analyze_site(
            tight_chip_path=chips.tight_chip_path,
            wide_chip_path=chips.wide_chip_path,
            boundary_strip_paths=chips.boundary_strips,
            cadastre_adjacents=cadastre_adj,
        )
        if analysis is None:
            logger.warning("Ortho enrichment: vision analysis failed")
            result.steps_skipped.append(("Ortho enrichment", "visió fallida"))
            return

        # Generate enriched text
        enriched = generate_enriched_texts(
            analysis=analysis,
            cadastre_adjacents=cadastre_adj,
            street_address=result.prefills.get('street_address', ''),
            municipality=result.prefills.get('site_municipality', ''),
            building_type=result.prefills.get('building_type', ''),
        )

        # Store enriched values with _enriched suffix (wizard_service will merge)
        for key, value in enriched.items():
            if value is not None and value != '':
                result.prefills[f'{key}_enriched'] = value
                result.sources[f'{key}_enriched'] = 'ICGC ortho+visió'

        # Store ortho chip paths for wizard evidence panel
        if chips.tight_chip_path:
            result.prefills['_ortho_tight_chip'] = str(chips.tight_chip_path)
        if chips.wide_chip_path:
            result.prefills['_ortho_wide_chip'] = str(chips.wide_chip_path)
        for direction, path in chips.boundary_strips.items():
            result.prefills[f'_ortho_strip_{direction}'] = str(path)

        n_enriched = sum(1 for k in enriched if enriched[k])
        result.steps_completed.append(f"Ortho enrichment: {n_enriched} camps enriquits")
        logger.info(f"Ortho enrichment: {n_enriched} fields enriched")

    except Exception as exc:
        logger.warning(f"Ortho enrichment failed: {exc}")
        result.steps_skipped.append(("Ortho enrichment", str(exc)))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_existing_user_data(project_path: Path) -> dict[str, Any]:
    """Load existing user_data.json if present, for UTM coords etc."""
    ud_path = project_path / 'user_data.json'
    if not ud_path.exists():
        return {}
    try:
        return json.loads(ud_path.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError):
        return {}


def _find_dpsh_excel(project_path: Path, file_mapping: Any) -> Path | None:
    """Find DPSH Excel file via file_mapping or glob fallback."""
    # Try file_mapping first
    if file_mapping and hasattr(file_mapping, 'roles'):
        dpsh_role = file_mapping.roles.get('dpsh_excel')
        if dpsh_role:
            candidate = project_path / dpsh_role.path
            if candidate.exists():
                return candidate

    # Glob fallback
    for pattern in ('ANNEXES/*DPSH*.xls', 'ANNEXES/*dpsh*.xls', '*DPSH*.xls'):
        matches = list(project_path.glob(pattern))
        if matches:
            return matches[0]

    return None


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI entry point for testing."""
    if len(sys.argv) < 2:
        print("Ús: python -m automation.auto_extractor <project_path>")
        sys.exit(1)

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    project_path = Path(sys.argv[1])
    skip_phase3 = '--skip-phase3' in sys.argv

    print(f"Auto-extracció: {project_path}")
    print("=" * 60)

    result = auto_extract(project_path, skip_phase3=skip_phase3)

    print("\n" + result.summary())
    print("\nPrefills:")
    for key, value in sorted(result.prefills.items()):
        source = result.sources.get(key, '?')
        display = str(value)
        if len(display) > 60:
            display = display[:57] + '...'
        print(f"  {key}: {display}  [{source}]")


if __name__ == '__main__':
    main()
