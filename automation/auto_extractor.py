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
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

__all__ = ['auto_extract', 'AutoExtractionResult']


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
    steps_completed: list[str] = field(default_factory=list)
    steps_skipped: list[tuple[str, str]] = field(default_factory=list)
    duration_seconds: float = 0.0

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
    _phase03_fileminer(project_path, result)
    emit("groq", {"name": "FileMiner regex", "ok": bool(result.mining_result and result.mining_result.signals)})

    # --- Phase 0.4: Groq Deep Mine (targeted gap-filling) ---
    _phase04_groq_deep_mine(project_path, result, emit)
    emit("step", {"step": "mine", "status": "done", "count": len(result.mining_result.signals) if result.mining_result else 0})

    # --- Phase 1: Local files ---
    emit("step", {"step": "extract", "status": "active"})
    _phase1_dpsh(project_path, result)
    emit("source", {"name": "DPSH Excel", "ok": result.dpsh_data is not None and bool(getattr(result.dpsh_data, 'tests', None))})
    _phase1_field_dates(project_path, result)
    emit("source", {"name": "Dates camp", "ok": 'field_work_dates' in result.prefills})

    # --- Phase 2: PDF extraction ---
    _phase2_lab_results(project_path, result)
    emit("source", {"name": "Lab PDF", "ok": result.lab_results is not None and result.lab_results.sulfate_mg_kg is not None})

    # --- Phase 2.5: Geocode coordinates (if UTM missing) ---
    # --- Phase 3: HTTP APIs (needs UTM coords) ---
    # UTM source priority: user_data.json > content_discovery > geocode > skip
    if not skip_phase3:
        utm_x = existing_user_data.get('utm_x') or result.prefills.get('utm_x')
        utm_y = existing_user_data.get('utm_y') or result.prefills.get('utm_y')

        if not (utm_x and utm_y):
            utm_x, utm_y = _phase25_geocode(
                existing_user_data, result, project_path,
            )
        emit("source", {"name": "Geocode", "ok": bool(utm_x and utm_y)})

        superficie = (
            existing_user_data.get('superficie_parcela_m2', 0)
            or result.prefills.get('superficie_parcela_m2', 0)
        )

        if utm_x and utm_y:
            _phase3_geology(utm_x, utm_y, result)
            emit("source", {"name": "ICGC geologia", "ok": 'icgc_unit_code' in result.prefills})
            _phase3_elevation(utm_x, utm_y, result)
            emit("source", {"name": "ICGC elevació", "ok": 'cota_referencia' in result.prefills})
            _phase3_slope(utm_x, utm_y, result)
            emit("source", {"name": "ICGC pendent", "ok": 'is_sloped' in result.prefills})
            _phase3_adjacents(utm_x, utm_y, superficie, result, project_path, existing_user_data)
            emit("source", {"name": "Cadastre adj.", "ok": any(f'adjacent_{d}' in result.prefills for d in ('north', 'south', 'east', 'west'))})
            # Cadastral parcel area (if not already from geocode)
            if 'superficie_cadastral_m2' not in result.prefills:
                _phase3_cadastral_area(utm_x, utm_y, result)
        else:
            emit("source", {"name": "APIs HTTP", "ok": False, "reason": "sense UTM"})
            result.steps_skipped.append(
                ("Fase 3: APIs HTTP", "sense coordenades UTM")
            )

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
    use_smartscan = os.environ.get('G3DT_USE_SMARTSCAN', '').strip()

    if use_smartscan == '1':
        try:
            from .smartscan import scan_project
            from .file_scanner import FileScanner, FileMapping, FileRole

            scan_result = scan_project(project_path, max_tier=2)
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


def _phase03_fileminer(project_path: Path, result: AutoExtractionResult) -> None:
    """Run FileMiner to extract data signals from all project files."""
    try:
        from .fileminer import mine_project, resolve_competition

        # Convert file_mapping to dict format for FileMiner
        fm_dict = None
        if result.file_mapping:
            try:
                fm_dict = result.file_mapping.to_dict() if hasattr(result.file_mapping, 'to_dict') else None
            except Exception:
                pass

        mining = mine_project(project_path, file_mapping=fm_dict)
        result.mining_result = mining

        if not mining.signals:
            result.steps_completed.append(
                f"FileMiner: {mining.files_mined} fitxers, cap senyal"
            )
            return

        resolved = resolve_competition(mining.signals)

        # Feed resolved values into prefills (don't override existing prefills
        # from dedicated extractors which are more precise)
        n_added = 0
        for variable, rv in resolved.items():
            if variable not in result.prefills:
                result.prefills[variable] = rv.value
                result.sources[variable] = f"fileminer:{rv.signal.source_file}"
                n_added += 1
            # Always store alternatives for wizard display
            if rv.alternatives:
                result.mining_alternatives[variable] = [
                    {'value': alt.value, 'source': alt.source_file, 'confidence': alt.confidence}
                    for alt in rv.alternatives
                ]

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
    if os.environ.get('G3DT_USE_GROQ', '').strip() != '1':
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
        emit("groq", {"name": f"Groq: +{n_new} prefills", "ok": n_new > 0})

    except Exception as exc:
        logger.warning("Phase 0.4 Groq failed: %s", exc)
        result.steps_skipped.append(("Groq Deep Mine", str(exc)))
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
    if not address:
        result.steps_skipped.append(
            ("Geocodificació", "sense adreça disponible")
        )
        return None, None

    # Get municipality from folder name (e.g., "4001612 BELL-LLOC" -> "Bell-Lloc")
    municipality = _extract_municipality(project_path)
    if not municipality:
        result.steps_skipped.append(
            ("Geocodificació", "sense municipi (nom carpeta)")
        )
        return None, None

    # Get point IDs from DPSH data if available
    point_ids = ['P-1']
    if result.dpsh_data and hasattr(result.dpsh_data, 'test_ids'):
        point_ids = result.dpsh_data.test_ids or ['P-1']

    logger.info(
        f"Geocodificant: '{address}', {municipality}, punts: {point_ids}"
    )

    province = result.prefills.get('province', '')

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
) -> None:
    """Query Cadastre API for adjacent parcels.

    For adjacents, the PROJECT PARCEL address (from planol/docs) is preferred
    over the DPSH test point coordinates (from COORDENADES.txt), because test
    points may be on a neighboring parcel.
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
        for key in ('street_address', 'site_address'):
            val = result.prefills.get(key) or (existing_user_data or {}).get(key)
            if val and isinstance(val, str) and len(val) > 3:
                address_candidates.append(val)

        province = result.prefills.get('province', '')
        if municipality and address_candidates:
            for addr in address_candidates:
                geocoded = _geocode_for_adjacents(addr, municipality, province=province)
                if geocoded:
                    adj_x, adj_y = geocoded
                    adj_source = f"geocode({addr})"
                    logger.info(
                        f"Adjacents: using geocoded address ({adj_x:.0f}, {adj_y:.0f}) "
                        f"instead of DPSH coords ({utm_x:.0f}, {utm_y:.0f})"
                    )
                    break

        rc14 = result.prefills.get('cadastral_ref')
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
    except Exception as exc:
        logger.warning(f"Cadastre adjacents failed: {exc}")
        result.steps_skipped.append(("Cadastre adjacents", str(exc)))


def _geocode_for_adjacents(
    street_address: str,
    municipality: str,
    province: str = "",
) -> tuple[float, float] | None:
    """Geocode a street address to UTM for adjacents probing.

    Tries the full address first, then strips the street type prefix
    (Nominatim often fails on "Carrer X" but succeeds on bare "X"
    for small Catalan towns).

    Returns (utm_x, utm_y) or None if geocoding fails.
    """
    try:
        from .geocode_coordinates import geocode_project
    except ImportError as e:
        logger.debug(f"geocode_coordinates not available: {e}")
        return None

    # Build candidate addresses: full → stripped number → bare name
    candidates = [street_address]

    # Strip house number variants: "Nº 39", ", 16", "18A-18B-20"
    import re
    stripped = re.sub(r'[\s,]+(?:Nº\s*|nº\s*|n[úu]m\.?\s*)?\d[\dA-Za-z\-]*\s*$', '', street_address).strip()
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
                logger.info(f"Geocode for adjacents OK: '{addr}' → ({geo_result['utm_x']:.0f}, {geo_result['utm_y']:.0f})")
                return geo_result['utm_x'], geo_result['utm_y']
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
