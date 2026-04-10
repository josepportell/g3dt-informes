"""
Service layer bridging automation modules to the web API.

All business logic lives here; api.py is a thin HTTP wrapper.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import subprocess
import threading
from pathlib import Path
from typing import Any

from automation import config

logger = logging.getLogger(__name__)

# Base dir for reference-material/ (relative to g3dt project root)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_REF_DIR = Path(config.G3DT_PROJECTS_DIR)

# Production path where Eva keeps signed reference reports
_INFORMES_DIR = Path('/mnt/c/claude/g3dt/4-informes')

# Sources that indicate high-priority extraction data (trusted over LLM synthesis)
_TRUSTED_SOURCE_PATTERNS = (
    'planol', 'sondeig', 'vision', 'ICGC', 'Cadastre', 'DPSH',
    'contingut:', 'fileminer:', 'groq_llm:',
)

# In-memory prefill cache: project_name -> prefills dict
_prefill_cache: dict[str, dict[str, Any]] = {}
# Cache raw AutoExtractionResult for dev-analysis-v2 (signal trace)
_auto_result_cache: dict[str, Any] = {}  # project_name -> AutoExtractionResult

# Vision subprocess tracking: project_name -> Popen
_vision_processes: dict[str, subprocess.Popen] = {}
# Vision last result: project_name -> returncode (persists after cleanup)
_vision_last_rc: dict[str, int] = {}
_vision_lock = threading.Lock()


def _resolve_project(project_name: str) -> Path:
    """Resolve a project name to its folder path. Raises ValueError if not found."""
    candidate = _REF_DIR / project_name
    try:
        candidate.resolve().relative_to(_REF_DIR.resolve())
    except ValueError:
        raise ValueError(f"Projecte no trobat: {project_name}")
    if candidate.is_dir():
        return candidate
    raise ValueError(f"Projecte no trobat: {project_name}")


def list_projects() -> list[dict[str, str]]:
    """List available projects from reference-material/."""
    if not _REF_DIR.is_dir():
        return []
    projects = []
    for d in sorted(_REF_DIR.iterdir()):
        if d.is_dir() and not d.name.startswith('.'):
            from automation.folder_utils import parse_folder_name
            expedient, municipality = parse_folder_name(d.name)
            projects.append({
                'folder': d.name,
                'expedient': expedient,
                'municipality': municipality,
            })
    return projects


def _fill_missing_adjacents(merged: dict[str, Any], project_path: Path) -> None:
    """Run adjacents detection from planol address when auto_extract skipped it.

    Only fires when ALL adjacents are empty (Phase 3 was skipped due to
    missing UTM coords) AND a street address + municipality are available
    from vision/wizard data. This avoids re-running for projects that
    already have adjacents from DPSH coordinates.
    """
    def _get_val(key: str) -> str:
        entry = merged.get(key)
        if entry is None:
            return ''
        if isinstance(entry, dict):
            return str(entry.get('value', ''))
        return str(entry)

    # Only run if ALL adjacents are empty
    has_any_adjacent = any(
        _get_val(f'adjacent_{d}')
        for d in ('north', 'south', 'east', 'west')
    )
    if has_any_adjacent:
        return

    street_address = _get_val('street_address')
    municipality = _get_val('site_municipality')
    if not street_address or not municipality:
        # P1: Try client_address as fallback if street_address is empty
        client_addr = _get_val('client_address')
        if client_addr and len(client_addr) > 10 and any(c.isdigit() for c in client_addr) and municipality:
            street_address = client_addr
        else:
            return

    logger.info(
        f"No adjacents from auto_extract — geocoding from planol: "
        f"'{street_address}', {municipality}"
    )

    try:
        from automation.auto_extractor import _geocode_for_adjacents, _extract_municipality
        from automation.cadastre_adjacents import get_adjacent_parcels

        province = _get_val('province')
        geo_result = _geocode_for_adjacents(street_address, municipality, province=province)
        if not geo_result:
            logger.info("Geocode for missing adjacents failed")
            return

        utm_x, utm_y = geo_result['utm_x'], geo_result['utm_y']

        # Save UTM coords to prefills if not already set
        if 'utm_x' not in merged or not _get_val('utm_x'):
            merged['utm_x'] = {'value': round(utm_x, 2), 'source': 'geocode:adjacents_fallback'}
            merged['utm_y'] = {'value': round(utm_y, 2), 'source': 'geocode:adjacents_fallback'}

        # Save cadastral area if available
        if geo_result.get('parcel_area') and not _get_val('superficie_cadastral_m2'):
            merged['superficie_cadastral_m2'] = {
                'value': int(geo_result['parcel_area']),
                'source': 'Cadastre WFS (geocode)',
            }

        superficie = float(_get_val('superficie_parcela_m2') or _get_val('superficie_cadastral_m2') or 500)
        muni_clean = _extract_municipality(project_path) or municipality

        adjacents = get_adjacent_parcels(
            utm_x, utm_y, superficie, municipality=muni_clean,
        )
        for direction in ('north', 'south', 'east', 'west'):
            val = adjacents.get(direction)
            if val:
                merged[f'adjacent_{direction}'] = {
                    'value': val,
                    'source': f"Cadastre API (geocode post-visió)",
                }
        logger.info(f"Filled {sum(1 for d in adjacents.values() if d)} adjacents from planol address")

    except Exception as e:
        logger.warning(f"Failed to fill missing adjacents: {e}")


def _crossref_lab_from_sondeig(merged: dict[str, Any], project_path: Path) -> None:
    """Deduce lab_location and lab_sample_id by cross-referencing sondeig SPT depths.

    When the lab PDF lacks explicit location/sample info (e.g. Castellar's GTL
    says "Tipus de mostra: Alterada" without SPT/location), we can match lab_depth
    against sondeig SPT depth ranges to infer which test point the sample came from.
    """
    import re

    def _get_val(key: str) -> str:
        entry = merged.get(key)
        if entry is None:
            return ''
        if isinstance(entry, dict):
            return str(entry.get('value', '') or '')
        return str(entry)

    # Only run if lab_location is missing and we have a lab_depth to match
    if _get_val('lab_location') or not _get_val('lab_depth'):
        return

    lab_depth_str = _get_val('lab_depth')  # e.g. "-1.00 a -1.20 m"

    # Parse lab depth: extract the two numeric values
    depth_nums = re.findall(r'(\d+[.,]\d+)', lab_depth_str)
    if len(depth_nums) < 2:
        return
    lab_from = float(depth_nums[0].replace(',', '.'))
    lab_to = float(depth_nums[1].replace(',', '.'))

    # Load merged sondeig data (annex + field sheet)
    try:
        from automation.vision_normalizer import load_sondeig_merged
        sondeig = load_sondeig_merged(project_path / 'validation')
    except Exception as exc:
        logger.debug("Lab cross-ref: could not load sondeig: %s", exc)
        return

    if not sondeig:
        return

    for test in sondeig.get('sondeig_tests', []):
        test_id = test.get('test_id', '')  # e.g. "S-1"
        for spt in test.get('spt_results', []):
            spt_id = spt.get('test_id', '')  # e.g. "SPT-1"
            spt_from = spt.get('depth_from_m')
            spt_to = spt.get('depth_to_m')
            if spt_from is None or spt_to is None:
                continue

            # Match if depths overlap within 0.1m tolerance
            if abs(float(spt_from) - lab_from) <= 0.1 and abs(float(spt_to) - lab_to) <= 0.1:
                source = f'cross-ref: sondeig {test_id} SPT depth matches lab'
                if not _get_val('lab_location') and test_id:
                    merged['lab_location'] = {'value': test_id, 'source': source}
                if not _get_val('lab_sample_id') and spt_id:
                    merged['lab_sample_id'] = {'value': spt_id, 'source': source}
                logger.info(
                    "Lab cross-ref: deduced location=%s sample=%s from SPT depth %.1f-%.1f",
                    test_id, spt_id, spt_from, spt_to,
                )
                return  # First match wins

    logger.debug("Lab cross-ref: no SPT depth match for lab_depth='%s'", lab_depth_str)


def _generate_template_prefills_from_merged(merged: dict[str, Any]) -> None:
    """Generate site/access descriptions from merged prefill data.

    Runs after auto_extract + wizard prefills are merged, so adjacents
    data is available for access_description generation.
    """
    def _get_val(key: str) -> str:
        entry = merged.get(key)
        if entry is None:
            return ''
        if isinstance(entry, dict):
            return str(entry.get('value', '') or '')
        return str(entry)

    # Phase 3.5 enriched values: override template-generated and auto-extracted,
    # but NOT user edits (source='user')
    _ENRICHED_FIELDS = (
        'adjacent_north', 'adjacent_south', 'adjacent_east', 'adjacent_west',
        'site_description', 'access_description', 'location_sentence',
    )
    for field_name in _ENRICHED_FIELDS:
        enriched_key = f'{field_name}_enriched'
        enriched_entry = merged.get(enriched_key)
        enriched_val = ''
        if isinstance(enriched_entry, dict):
            enriched_val = str(enriched_entry.get('value', '') or '')
        elif enriched_entry is not None:
            enriched_val = str(enriched_entry)
        if enriched_val:
            # Only skip if user manually edited this field
            existing = merged.get(field_name)
            existing_source = ''
            if isinstance(existing, dict):
                existing_source = str(existing.get('source', '') or '')
            if existing_source == 'user':
                continue  # User edits always win
            merged[field_name] = {
                'value': enriched_val,
                'source': 'ICGC ortho+visió',
            }

    # is_anthropized from enrichment (overrides default, not user edits)
    enriched_anthro = merged.get('is_anthropized_enriched')
    if enriched_anthro is not None:
        existing = merged.get('is_anthropized')
        existing_source = ''
        if isinstance(existing, dict):
            existing_source = str(existing.get('source', '') or '')
        if existing_source != 'user':
            val = enriched_anthro
            if isinstance(val, dict):
                val = val.get('value', True)
            merged['is_anthropized'] = {
            'value': val,
            'source': 'ICGC ortho+visió',
        }

    # Access description: pick first street-facing direction (full sentence)
    if not _get_val('access_description'):
        import re as _re
        _ACCESS_PREFIX = (
            "El dia dels treballs de camp es realitza l\u2019entrada a la zona "
            "d\u2019estudi a trav\u00e9s "
        )
        STREET_PREPOSITIONS = {
            'carrer': 'del', 'avinguda': "de l'", 'camí': 'del',
            'passatge': 'del', 'passeig': 'del', 'plaça': 'de la',
            'ronda': 'de la', 'partida': 'de la', 'carretera': 'de la',
            'travessia': 'de la',
        }
        _muni_val = _get_val('site_municipality')
        for direction, direction_cat in [
            ('south', 'sud'), ('north', 'nord'),
            ('east', 'est'), ('west', 'oest'),
        ]:
            val = _get_val(f'adjacent_{direction}')
            if not val:
                continue
            # Strip trailing municipality from street name (Fix B, upstream)
            if _muni_val:
                cleaned = _re.sub(r'\s+' + _re.escape(_muni_val) + r'\s*$', '', val, flags=_re.IGNORECASE).strip()
                if cleaned and cleaned != val:
                    val = cleaned
            val_lower = val.lower()
            for kw, prep in STREET_PREPOSITIONS.items():
                if kw in val_lower:
                    sep = '' if prep.endswith("'") else ' '
                    merged['access_description'] = {
                        'value': f"{_ACCESS_PREFIX}{prep}{sep}{val} existent al {direction_cat}.",
                        'source': 'plantilla generada',
                    }
                    break
            if _get_val('access_description'):
                break

    # Site description: generate from shape, area, anthropized state
    if not _get_val('site_description'):
        parts = []
        shape = _get_val('parcel_shape') or 'rectangular'
        area = _get_val('superficie_parcela_m2') or _get_val('superficie_cadastral_m2')
        if area:
            try:
                parts.append(
                    f"parcel\u00b7la de forma {shape} amb superf\u00edcie de {int(float(area))} m2"
                )
            except (ValueError, TypeError):
                parts.append(f"parcel\u00b7la de forma {shape}")

        is_anthropized = _get_val('is_anthropized')
        if is_anthropized and is_anthropized.lower() not in ('false', '0', ''):
            parts.append("El terreny es presenta antropitzat")

        if parts:
            merged['site_description'] = {
                'value': '. '.join(parts),
                'source': 'plantilla generada',
            }

    # Site condition: erosion observation sentence
    # Uses slope (ICGC) + adjacents (Cadastre) to determine qualifier.
    # "Antropitzat" = the LAND itself is modified (paving, rubble, earthworks)
    # — requires visual observation, NOT deducible from adjacents alone.
    # "No pla" = significant slope (>10%).
    # "Pla" = default when flat and no special condition observed.
    # Spanish projects get a simpler fixed sentence.
    if not _get_val('site_condition'):
        lang = _get_project_language(merged)
        if lang == 'es':
            site_cond = (
                "En la zona de estudio no se han detectado marcas de inicios "
                "de procesos de erosión relacionados con la escorrentía "
                "hídrica superficial."
            )
            source = 'computed (ES template)'
        else:
            slope_pct = _get_val('slope_percent')
            try:
                slope_val = float(slope_pct) if slope_pct else 0.0
            except (ValueError, TypeError):
                slope_val = 0.0

            is_anthro_entry = merged.get('is_anthropized', {})
            anthro_source = is_anthro_entry.get('source', '') if isinstance(is_anthro_entry, dict) else ''

            # Only trust is_anthropized if it comes from a REAL source (not default)
            if 'default' in anthro_source:
                # Don't use default — determine from slope only
                if slope_val > 10:
                    qualifier = "Tot i no ser un solar pla"
                else:
                    qualifier = "Com que es tracta d'un solar pla"
            else:
                # We have real anthropization data (from ortho, user, etc.)
                is_anthro = _get_val('is_anthropized')
                anthro = is_anthro and str(is_anthro).lower() not in ('false', '0', '')
                if slope_val > 10 and not anthro:
                    qualifier = "Es tracta d'un solar no antropitzat"
                elif slope_val > 10:
                    qualifier = "Tot i no ser un solar pla"
                elif anthro:
                    qualifier = "Degut a que es tracta d'un solar antropitzat"
                else:
                    qualifier = "Com que es tracta d'un solar pla"

            site_cond = (
                f"{qualifier}, no s'han detectat marques i/o indicis de processos "
                f"d'erosió relacionats amb l'escolament hídric superficial, "
                f"ni es preveu que apareguin."
            )
            source = f'computed (slope {slope_val:.0f}%)'
        merged['site_condition'] = {
            'value': site_cond,
            'source': source,
        }


def _clear_stale_user_data(project_path: Path) -> None:
    """Back up stale user_data.json before a fresh pipeline run.

    Prevents outdated fields (e.g. soil_types, num_soil_levels) from a
    previous run from overriding correct auto-extracted values.  The
    backup is kept as _user_data_prev.json for safety.
    """
    user_data_path = project_path / 'user_data.json'
    if user_data_path.exists():
        backup_path = project_path / '_user_data_prev.json'
        user_data_path.rename(backup_path)
        logger.info("Backed up stale user_data.json -> _user_data_prev.json")


def _compute_geotech_prefills(merged: dict, project_path: Path, auto_result: Any) -> None:
    """Add geotech params + calc transparency notes to wizard prefills.

    Replicates the computation from ReportGenerator.build_context_preview()
    so the wizard can display geomech values and Tier C calc notes without
    running the full report pipeline.

    Skips any key where merged already has source="user" (Eva's edits win).
    """
    from automation.cte_geomech import (
        nspt_to_phi, nspt_to_E_kg_cm2, nspt_to_gamma_g_cm3,
        is_rock, rock_params_default, soil_type_to_cohesion,
    )
    from automation.report_generator import _TYPICAL_RANGES
    from automation.terzaghi_calculator import TerzaghiCalculator, FootingShape

    dpsh = auto_result.dpsh_data if hasattr(auto_result, 'dpsh_data') else None
    if not dpsh:
        return
    avg_n20 = getattr(dpsh, 'overall_average_n20', None)
    if not avg_n20 or avg_n20 <= 0:
        return

    nb = avg_n20 / 0.83

    # Determine deepest-level soil type from merged prefills
    num_levels = 1
    nle = merged.get('num_geological_levels') or merged.get('num_soil_levels')
    if nle:
        nle_val = nle['value'] if isinstance(nle, dict) else nle
        try:
            num_levels = int(nle_val)
        except (ValueError, TypeError):
            pass

    soil_type_key = f'soil_type_level_{num_levels}'
    st_entry = merged.get(soil_type_key) or merged.get('soil_type_level_1')
    soil_type = (st_entry['value'] if isinstance(st_entry, dict) else st_entry) if st_entry else 'granular'
    if not soil_type:
        soil_type = 'granular'
    soil_type = soil_type.lower()

    # Get deepest-level description for rock detection
    desc_key = f'sondeig_layer_desc_{num_levels}'
    desc_entry = merged.get(desc_key, merged.get('sondeig_layer_desc_1'))
    description = (desc_entry['value'] if isinstance(desc_entry, dict) else (desc_entry or '')) if desc_entry else ''

    # Compute geomech params (same logic as report_generator)
    if soil_type == 'rock' or is_rock(avg_n20, description):
        rock = rock_params_default()
        gamma, phi, E, cohesion = rock['gamma'], rock['phi'], rock['E'], rock['cohesion']
    else:
        gamma = nspt_to_gamma_g_cm3(avg_n20, soil_type)
        phi = nspt_to_phi(nb, soil_type)
        E = nspt_to_E_kg_cm2(avg_n20)
        cohesion = soil_type_to_cohesion(soil_type)

    is_granular = cohesion < 0.5
    soil_cat = 'rock' if cohesion >= 0.5 else ('cohesive' if soil_type == 'cohesive' else 'granular')
    ranges = _TYPICAL_RANGES.get(soil_cat, _TYPICAL_RANGES['granular'])

    def _set(key: str, value: Any, source: str) -> None:
        """Set merged[key] only if not already a user edit."""
        existing = merged.get(key)
        if isinstance(existing, dict) and existing.get('source') == 'user':
            return
        merged[key] = {'value': value, 'source': source}

    # Geomech prefills (populate expert override fields)
    _set('geomech_gamma', gamma, f'CTE D.27 ({soil_type})')
    _set('geomech_cohesion', cohesion, f'soil_type={soil_type}')
    _set('geomech_phi', round(phi, 1), f'Schmertmann Nb={nb:.0f}')
    _set('geomech_E', round(E), f'CTE D.23 N20={avg_n20:.0f}')

    # Calc transparency notes
    n20_src = f"N20={avg_n20:.0f}"
    _set('_calc_gamma', f"CTE D.27 {soil_type} | Rang Eva: {ranges['gamma']}", 'system')
    _set('_calc_phi', f"Schmertmann Nb={nb:.0f} | Rang Eva: {ranges['phi']}", 'system')
    _set('_calc_E', f"CTE D.23 {n20_src} | Rang Eva: {ranges['E']}", 'system')
    _set('_calc_cohesion', f"Rang Eva: {ranges['c']}", 'system')

    # Run Terzaghi for Qa + settlement
    try:
        B_entry = merged.get('footing_width_m')
        B = float((B_entry['value'] if isinstance(B_entry, dict) else B_entry) or 1.0)
        if B <= 0:
            B = 1.0
        Df_entry = merged.get('foundation_depth_m')
        Df = float((Df_entry['value'] if isinstance(Df_entry, dict) else Df_entry) or 0.8)
        if Df <= 0:
            Df = 0.8

        # Check for wizard Es override
        Es_entry = merged.get('Es_settlement')
        Es_override = None
        if Es_entry:
            es_val = Es_entry['value'] if isinstance(Es_entry, dict) else Es_entry
            if es_val:
                try:
                    Es_override = float(es_val)
                except (ValueError, TypeError):
                    pass

        calc = TerzaghiCalculator(phi=phi, cohesion=cohesion, gamma=gamma)
        tr = calc.calculate_qa(
            B=B, Df=Df, shape=FootingShape.SQUARE,
            nspt=nb, is_granular=is_granular,
            E=E, Es_override=Es_override,
        )

        _set('qa_value', f"{tr.Qa:.2f}", 'Terzaghi-Peck')
        if tr.settlement_cm is not None:
            _set('settlement', f"{tr.settlement_cm:.2f}", 'Schmertmann')

        # K30 ballast coefficient
        if cohesion and cohesion > 0:
            k30 = E / 60
            k30_formula = f"E/60 = {E:.0f}/60 (roca, c={cohesion})"
        else:
            k30 = E / 75
            k30_formula = f"E/75 = {E:.0f}/75 (granular)"
        _set('k30_value', f"{k30:.1f}", 'Winkler')
        _set('_calc_k30', k30_formula, 'system')

        # Qa transparency
        if nb:
            formula = f"Nb/12={nb:.0f}/12={nb/12:.2f}"
            if tr.Fw is not None:
                formula += f" / Fw={tr.Fw:.2f}"
            if tr.Fd_tp is not None:
                formula += f" x Fd={tr.Fd_tp:.2f}"
            if tr.Qa_uncapped is not None:
                _set('_calc_qa', f"{formula} = {tr.Qa_uncapped:.2f} | Cap: {tr.Qa:.2f} ({ranges['Qa_cap']})", 'system')
            else:
                _set('_calc_qa', f"{formula} = {tr.Qa:.2f} | Rang Eva: {ranges['Qa_cap']}", 'system')

        # Settlement transparency with sensitivity
        if tr.settlement_cm and tr.Es_used:
            Es = tr.Es_used
            base = tr.settlement_cm
            Es_low = Es * 0.75
            Es_high = Es * 1.25
            s_low = base * Es / Es_high
            s_high = base * Es / Es_low
            _set('_calc_settlement',
                 f"Schmertmann Es={Es:.0f}, B={B}m \u2192 {base:.2f} cm"
                 f" | Si Es={Es_low:.0f}: {s_high:.2f} cm"
                 f" | Si Es={Es_high:.0f}: {s_low:.2f} cm",
                 'system')
            _set('_calc_Es', f"Es={Es:.0f} (2.5\u00d7Nb) | \u00b125%: {Es_low:.0f}-{Es_high:.0f}", 'system')

    except Exception as exc:
        logger.warning("Geotech prefill calc failed: %s", exc)


# Aragonese municipalities served by G3DT (Spanish, not Catalan)
_ES_MUNICIPALITIES = frozenset({
    'anciles', 'benasque', 'castejón de sos', 'campo', 'graus',
    'barbastro', 'monzón', 'binéfar', 'tamarite de litera',
    'vilanova de segrià', 'vilanova de segria',  # Eva writes these in Spanish
})

# Spanish-language markers (words that don't appear in Catalan texts)
_ES_MARKERS = ('vivienda', 'ensayo', 'calle ', 'sótano', 'planta baja')


def _get_project_language(prefills: dict[str, Any]) -> str:
    """Detect project language from municipality and prefill text.

    Returns 'ca' (Catalan, default) or 'es' (Spanish).
    """
    def _val(key: str) -> str:
        entry = prefills.get(key)
        if entry is None:
            return ''
        if isinstance(entry, dict):
            return str(entry.get('value', '') or '')
        return str(entry)

    # Check municipality against known ES list
    muni = _val('site_municipality').lower().strip()
    if muni in _ES_MUNICIPALITIES:
        return 'es'

    # Check prefill text for Spanish markers
    sample = ' '.join(
        _val(k) for k in ('building_type', 'street_address', 'site_description')
    ).lower()
    if any(marker in sample for marker in _ES_MARKERS):
        return 'es'

    return 'ca'


def _compute_narrative_prefills(
    merged: dict[str, Any],
    auto_result: Any,
    project_path: Path,
) -> None:
    """Compute narrative template variables from existing data.

    Sets num_dpsh_tests, table_dpsh_range, and building_structure_desc.
    Respects user edits (source='user').
    """

    def _set(key: str, value: Any, source: str) -> None:
        existing = merged.get(key)
        if isinstance(existing, dict) and existing.get('source') == 'user':
            return
        merged[key] = {'value': value, 'source': source}

    def _get_val(key: str) -> str:
        entry = merged.get(key)
        if entry is None:
            return ''
        if isinstance(entry, dict):
            return str(entry.get('value', '') or '')
        return str(entry)

    lang = _get_project_language(merged)

    # --- num_dpsh_tests + table_dpsh_range ---
    dpsh = auto_result.dpsh_data if hasattr(auto_result, 'dpsh_data') else None
    num_tests = dpsh.num_tests if dpsh else 0

    # Fallback: count tests in dpsh_extracted.json (vision result)
    if num_tests == 0:
        dpsh_json_path = project_path / 'validation' / 'dpsh_extracted.json'
        if dpsh_json_path.exists():
            try:
                dpsh_json = json.loads(dpsh_json_path.read_text(encoding='utf-8'))
                num_tests = len(dpsh_json.get('dpsh_tests', []))
            except (json.JSONDecodeError, KeyError):
                pass

    if num_tests > 0:
        if lang == 'es':
            _set(
                'num_dpsh_tests',
                f'{num_tests} ensayos de penetración dinámica DPSH '
                f'(ver registro de los ensayos mecánicos).',
                'computed',
            )
        else:
            _set(
                'num_dpsh_tests',
                f'{num_tests} assaigs de penetració dinàmica tipus DPSH '
                f'(veure annex "Registre assaigs mecànics").',
                'computed',
            )

        # table_dpsh_range: table numbering depends on test count
        if num_tests <= 2:
            range_str = '3 y 4' if lang == 'es' else '3 i 4'
        else:
            range_str = '3, 4 y 5' if lang == 'es' else '3, 4 i 5'

        _set('table_dpsh_range', range_str, 'computed')

    # --- building_structure_desc ---
    num_floors = _get_val('num_floors').strip()
    has_basement_entry = merged.get('has_basement')
    has_basement = False
    if has_basement_entry is not None:
        bval = has_basement_entry.get('value') if isinstance(has_basement_entry, dict) else has_basement_entry
        has_basement = str(bval).lower() in ('true', '1', 'yes', 'sí', 'si')

    # Detect basement from num_floors notation (Ps / PS = planta soterrani)
    import re
    if num_floors:
        if re.search(r'\bP[Ss]\b', num_floors):
            has_basement = True
        # Ground-floor only: "Pb" or "PB" with no upper floors (no "Pp")
        is_ground_only = bool(
            re.search(r'\bP[Bb]\b', num_floors)
        ) and not re.search(r'\bP[Pp]\b', num_floors) and not re.search(r'\d+\s*P[Pp]', num_floors, re.IGNORECASE)

        if has_basement:
            desc = 'con nivel de sótano' if lang == 'es' else 'amb nivell de soterrani'
        elif is_ground_only:
            desc = 'en planta baja' if lang == 'es' else 'en planta baixa'
        else:
            desc = 'sin nivel de sótano' if lang == 'es' else 'sense nivell de soterrani'

        _set('building_structure_desc', desc, 'computed')


def _compute_lookup_prefills(merged: dict[str, Any], auto_result: Any) -> None:
    """Set CTE, seismic, and radon prefills from municipality lookups.

    Uses existing modules (cte_classifier, municipal_data) via the
    municipal_lookups facade. Respects user edits (source='user').
    """
    from automation.municipal_lookups import (
        lookup_cte_edificacio,
        lookup_cte_sol,
        lookup_seismic_ab,
        lookup_radon_zone,
        format_seismic_ab_text,
    )

    def _get_val(key: str) -> str:
        entry = merged.get(key)
        if entry is None:
            return ''
        if isinstance(entry, dict):
            return str(entry.get('value', '') or '')
        return str(entry)

    def _set(key: str, value: Any, source: str) -> None:
        existing = merged.get(key)
        if isinstance(existing, dict) and existing.get('source') == 'user':
            return
        merged[key] = {'value': value, 'source': source}

    # CTE building classification
    building_type = _get_val('building_type')
    num_floors = _get_val('num_floors')
    if building_type or num_floors:
        cte_edif = lookup_cte_edificacio(building_type or 'habitatge', num_floors or '1')
        _set('cte_edificacio', cte_edif, f'CTE DB SE-C ({building_type or "default"})')

    # CTE soil classification
    dpsh = auto_result.dpsh_data if hasattr(auto_result, 'dpsh_data') else None
    avg_n20 = getattr(dpsh, 'overall_average_n20', None) if dpsh else None
    cte_sol = lookup_cte_sol(average_n20=avg_n20)
    _set('cte_sol', cte_sol, 'CTE DB SE-C' + (f' (N20={avg_n20:.0f})' if avg_n20 else ''))

    # Seismic acceleration
    municipality = _get_val('site_municipality')
    if municipality:
        ab = lookup_seismic_ab(municipality)
        ab_text = format_seismic_ab_text(ab)
        _set('seismic_ab_text', ab_text, f'NCSE-02 ({municipality})')

    # Radon zone
    if municipality:
        zone = lookup_radon_zone(municipality)
        _set('radon_zone', str(zone), f'CTE DB HS6 ({municipality})')


def _extract_comanda_building_info(project_path: Path) -> str:
    """Extract building info from comanda_lab Excel file.

    Looks for patterns like "CONSTR 3 HAB UNIF", "CONSTR GRUPO DE VIVIENDAS" etc.
    Returns the raw text found, or empty string.
    """
    import re

    # Find comanda file via file_mapping.json
    mapping_path = project_path / 'file_mapping.json'
    comanda_path = None

    if mapping_path.exists():
        try:
            data = json.loads(mapping_path.read_text(encoding='utf-8'))
            for role_name in ('lab_order', 'lab_excel', 'comanda_lab'):
                role = data.get('roles', {}).get(role_name)
                if role:
                    candidate = project_path / role['path']
                    if candidate.exists():
                        comanda_path = candidate
                        break
        except Exception:
            pass

    # Fallback: glob for comanda*.xls
    if not comanda_path:
        matches = (
            list(project_path.glob('comanda*laboratori*.xls'))
            + list(project_path.glob('comanda*laboratori*.xlsx'))
        )
        if matches:
            comanda_path = matches[0]

    if not comanda_path:
        return ''

    try:
        import xlrd
        wb = xlrd.open_workbook(str(comanda_path))
        text_parts = []
        for sheet in wb.sheets():
            for row_idx in range(min(sheet.nrows, 20)):  # First 20 rows only
                for col_idx in range(sheet.ncols):
                    cell = sheet.cell(row_idx, col_idx)
                    if cell.ctype == xlrd.XL_CELL_TEXT and cell.value:
                        text_parts.append(cell.value.strip())

        full_text = ' '.join(text_parts)

        # Look for construction/building patterns
        patterns = [
            r'(?i)(CONSTR(?:UCCI[OÓ]N?)?\s+\d+\s+HAB\w*(?:\s+\w+)*)',
            r'(?i)(CONSTR(?:UCCI[OÓ]N?)?\s+(?:GRUP(?:O|E)\s+DE\s+)?(?:VIVIEND|HABITA)\w*(?:\s+\w+)*)',
            r'(?i)(CONSTR(?:UCCI[OÓ]N?)?\s+(?:NAU|EDIFIC|AMPLIA)\w*(?:\s+\w+)*)',
            r'(?i)(\d+\s+(?:HABITATGES?|VIVIENDAS?)\s+\w+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, full_text)
            if match:
                return match.group(1).strip()

        return ''

    except ImportError:
        logger.info("xlrd not available, cannot read comanda_lab")
        return ''
    except Exception as e:
        logger.debug("Failed to read comanda_lab %s: %s", comanda_path, e)
        return ''


def _synthesize_with_llm(merged: dict[str, Any], project_path: Path) -> None:
    """Use Claude API to synthesize building_type, architect/client, location_sentence
    from all pre-extracted sources. One API call per project."""

    def _get_val(key: str) -> str:
        entry = merged.get(key)
        if entry is None:
            return ''
        if isinstance(entry, dict):
            return str(entry.get('value', '') or '')
        return str(entry)

    def _get_source(key: str) -> str:
        entry = merged.get(key)
        if isinstance(entry, dict):
            return entry.get('source', '')
        return ''

    def _set(key: str, value: str, source: str = 'llm_synthesis') -> None:
        existing = merged.get(key)
        if not isinstance(existing, dict):
            # No existing structured value — synthesis can set freely
            if value:
                merged[key] = {'value': value, 'source': source}
            return

        existing_source = existing.get('source', '')
        existing_value = str(existing.get('value', '') or '')

        # User edits always win
        if existing_source == 'user':
            return

        # If existing source is trusted and has a value, protect it
        if existing_value and any(p in existing_source for p in _TRUSTED_SOURCE_PATTERNS):
            # Allow refinement: synthesis adds article/prefix but core content same
            existing_lower = existing_value.lower().strip()
            value_lower = (value or '').lower().strip()
            if value_lower and existing_lower in value_lower:
                # Synthesis refines (e.g. adds article) — update value, keep source
                merged[key] = {'value': value, 'source': existing_source}
            # else: don't overwrite — trusted source takes precedence
            return

        # Low-priority or unknown source — synthesis can overwrite
        if value:
            merged[key] = {'value': value, 'source': source}

    # Skip if no API key available
    try:
        import anthropic
    except ImportError:
        logger.info("anthropic package not available, skipping LLM synthesis")
        return

    if not config.ANTHROPIC_API_KEY:
        logger.info("No ANTHROPIC_API_KEY, skipping LLM synthesis")
        return

    # Check if ALL fields already have user edits -- skip synthesis if so
    user_fields = [
        k for k in ('building_type', 'architect_name', 'client_name', 'location_sentence')
        if _get_source(k) == 'user'
    ]
    if len(user_fields) == 4:
        logger.info("All synthesis fields have user edits, skipping LLM synthesis")
        return

    # --- Gather all source data ---

    # Building type sources
    building_type_current = _get_val('building_type')
    building_type_source = _get_source('building_type')

    # Project title from planol
    planol_path = project_path / 'validation' / 'planol_extracted.json'
    project_title = ''
    planol_data = {}
    if planol_path.exists():
        try:
            planol_data = json.loads(planol_path.read_text(encoding='utf-8'))
            arch = planol_data.get('architect_data', {})
            project_title = (
                arch.get('project_name', '')
                or arch.get('project_title', '')
                or ''
            )
        except Exception:
            pass

    # Comanda lab building info
    comanda_building_info = _extract_comanda_building_info(project_path)

    # Architect/client from all sources
    architect_current = _get_val('architect_name')
    architect_source = _get_source('architect_name')
    client_current = _get_val('client_name')
    client_source = _get_source('client_name')

    # Planol architect data
    planol_architect = ''
    planol_company = ''
    planol_promotor = ''
    if planol_data:
        arch = planol_data.get('architect_data', {})
        planol_architect = arch.get('architect', '') or ''
        planol_company = arch.get('architect_company', '') or ''
        planol_promotor = arch.get('promotor', '') or arch.get('client_name', '') or ''

    # Docs extracted data
    docs_path = project_path / 'validation' / 'docs_extracted.json'
    docs_architect = ''
    docs_client = ''
    if docs_path.exists():
        try:
            docs_data = json.loads(docs_path.read_text(encoding='utf-8'))
            raw_arch = docs_data.get('architect_name')
            docs_architect = (
                raw_arch.get('value', '') if isinstance(raw_arch, dict)
                else (raw_arch or '')
            )
            raw_cli = docs_data.get('client_name')
            docs_client = (
                raw_cli.get('value', '') if isinstance(raw_cli, dict)
                else (raw_cli or '')
            )
        except Exception:
            pass

    # Location data
    street_address = _get_val('street_address')
    municipality = _get_val('site_municipality')
    adjacent_north = _get_val('adjacent_north_formatted') or _get_val('adjacent_north')
    adjacent_south = _get_val('adjacent_south_formatted') or _get_val('adjacent_south')
    adjacent_east = _get_val('adjacent_east_formatted') or _get_val('adjacent_east')
    adjacent_west = _get_val('adjacent_west_formatted') or _get_val('adjacent_west')

    # Language
    lang = _get_project_language(merged)
    lang_name = 'Spanish' if lang == 'es' else 'Catalan'

    # --- Build prompt ---

    prompt = f"""You are a geotechnical report assistant. Given data extracted from multiple sources about a construction project, synthesize the final values for 4 fields.

## Rules

### building_type
- Output in {lang_name}
- Include the article (un/una/l'/los/las)
- Include quantity if more than 1 (e.g., "3 habitatges unifamiliars")
- Include relevant descriptors from the project title or comanda (e.g., "modular", "d'estructura lleugera, fusta", "adosadas")
- If the project title mentions "ampliacio", "tancament", "reforma" -> the building_type should reflect this (e.g., "l'ampliacio d'un edifici en planta baixa")
- Keep it concise (3-10 words)

### architect_name
- Look at all sources and determine who the correct architect/technical director is
- Sometimes it is the plan-signing architect (e.g., Bell-Lloc: BOSCH NOVELL)
- Sometimes it is the promotor/client who also acts as project director (e.g., Linyola: EROLES)
- Use the few-shot examples below as guidance for each case
- Use UPPERCASE for names
- Do NOT include honorifics (Sr./Sra.)

### client_name
- Add honorific: "SR." for male, "SRA." for female names. For companies, no honorific.
- If the client is clearly a company (S.L, S.L.U, etc.), use the company name without honorific
- Use UPPERCASE

### location_sentence
- Compose a location description from the available address and municipality data
- In {lang_name}
- Format examples:
  - "al Carrer X nY de Z" (simple address)
  - "entre el Carrer X i el Carrer Y de Z" (between two streets -- use when adjacent streets are available on 2+ sides)
  - "a una parcella ubicada al Carrer X nY, Z" (with parcel reference)
  - "en la calle X nY en el municipio de Z" (Spanish)
- If you don't have enough data for a specific part, omit it rather than guessing

## Eva's Reference Examples

1. Bell-Lloc (CA): building_type="un habitatge unifamiliar", architect="JORDI BOSCH NOVELL", client="RAMON MITJANA S.L", location="entre el Carrer Antoni Bellet i el Carrer Mestre Ramon Ortiz de Bell-Lloc d'Urgell"
2. Castellar (CA): building_type="3 habitatges unifamiliars d'estructura lleugera, fusta", client="WOOD COMFORT PROMOCIONS SLU", location="en el Carrer dels Arbrells, 18 de Castellar del Valles"
3. Rubi (CA): building_type="un habitatge unifamiliar aillat modular", architect="JOANA MARTINEZ", client="SRA. JOANA MARTINEZ", location="a una parcella ubicada al carrer de la Miranda n 39, (PARC. 6-105) Rubi, Barcelona"
4. Linyola (CA): building_type="un nou habitatge unifamiliar", architect="SILVIA EROLES BALAGUERO", client="SRA. SILVIA EROLES BALAGUERO", location="al Carrer Clot de la Llacuna n16 de Linyola"
5. Alcoletge (CA): building_type="l'ampliacio d'un edifici en planta baixa", architect="ALBERT SANS BONVEHI", client="SR. ALBERT SANS BONVEHI", location="a una parcella ubicada al Carrer Girasols n7, Urbanitzacio El Roser d'Alcoletge"
6. Vilanova (ES): building_type="una vivienda unifamiliar aislada", architect="JUAN JOSE TORRES POVEDANO", client="GRUPO CUENCA GUERRERO, S.L", location="en la Calle STA. GEMMA n 4, URB. LA SERRA del municipio de VILANOVA DE SEGRIA"
7. Anciles (ES): building_type="7 viviendas unifamiliares adosadas", architect="ALBA MARIA BARRAU CASTAN", client="SRA. ALBA MARIA BARRAU CASTAN", location="en la calle Gral Ferraz n20 en el municipio de Anciles, Benasque"

## Current Project Data

**Language:** {lang_name}
**Municipality:** {municipality}

**Building type sources:**
- Vision extraction (from architectural plan): "{building_type_current}" (source: {building_type_source})
- Project title (from plan header): "{project_title}"
- Comanda lab (lab order form): "{comanda_building_info}"

**Architect/client sources:**
- Current pipeline architect: "{architect_current}" (source: {architect_source})
- Current pipeline client: "{client_current}" (source: {client_source})
- Planol architect (plan signer): "{planol_architect}"
- Planol company: "{planol_company}"
- Planol promotor: "{planol_promotor}"
- Docs extracted architect: "{docs_architect}"
- Docs extracted client: "{docs_client}"

**Location sources:**
- Street address: "{street_address}"
- Municipality: "{municipality}"
- Adjacent north: "{adjacent_north}"
- Adjacent south: "{adjacent_south}"
- Adjacent east: "{adjacent_east}"
- Adjacent west: "{adjacent_west}"

## Output

Return ONLY a JSON object with exactly these 4 keys:
```json
{{
  "building_type": "...",
  "architect_name": "...",
  "client_name": "...",
  "location_sentence": "..."
}}
```

If you cannot determine a value with reasonable confidence, use an empty string ""."""

    # --- Call Claude API ---
    try:
        import re as _re

        client = anthropic.Anthropic()
        response = client.messages.create(
            model=config.TEXT_MODEL_ANTHROPIC,
            max_tokens=500,
            messages=[{'role': 'user', 'content': prompt}],
        )
        response_text = response.content[0].text

        # Parse JSON from response
        json_match = _re.search(
            r'```(?:json)?\s*\n(.*?)\n```', response_text, _re.DOTALL,
        )
        if json_match:
            result = json.loads(json_match.group(1))
        else:
            start = response_text.find('{')
            end = response_text.rfind('}')
            if start >= 0 and end > start:
                result = json.loads(response_text[start:end + 1])
            else:
                logger.warning("LLM synthesis: no JSON in response")
                return

        # Apply synthesized values
        for field in ('building_type', 'architect_name', 'client_name', 'location_sentence'):
            value = result.get(field, '')
            if value and _get_source(field) != 'user':
                _set(field, value)

        logger.info(
            "LLM synthesis: %d fields updated for %s",
            sum(
                1 for f in ('building_type', 'architect_name', 'client_name', 'location_sentence')
                if result.get(f)
            ),
            project_path.name,
        )

    except Exception as e:
        logger.warning("LLM synthesis failed: %s", e)


def _compute_mapping_prefills(
    merged: dict[str, Any],
    auto_result: Any,
    project_path: Path,
) -> None:
    """Map existing extracted data to prefill variables (Block 4).

    Wires SPT data from sondeig_extracted.json and derives sulfate
    classification from sulfate_mg_kg. Skips keys where merged already
    has source='user' (Eva's edits win).
    """

    def _set(key: str, value: Any, source: str) -> None:
        existing = merged.get(key)
        if isinstance(existing, dict) and existing.get('source') == 'user':
            return
        merged[key] = {'value': value, 'source': source}

    def _get_val(key: str) -> str:
        entry = merged.get(key)
        if entry is None:
            return ''
        if isinstance(entry, dict):
            return str(entry.get('value', ''))
        return str(entry)

    # --- 4.1  SPT data from sondeig (annex preferred over field sheet) ---
    try:
        from automation.vision_normalizer import load_sondeig_merged
        sondeig_data = load_sondeig_merged(project_path / 'validation')
        if sondeig_data:
            tests = sondeig_data.get('sondeig_tests', [])
            if tests:
                test = tests[0]
                spt_list = test.get('spt_results', [])
                if spt_list:
                    spt = spt_list[0]
                    _set('spt_test_id', spt.get('test_id', 'SPT-1'), 'sondeig vision')

                    # N30: standard SPT = blows[1]+blows[2] (middle two 15cm intervals)
                    blows = spt.get('blows', [])
                    if len(blows) >= 3:
                        n30 = blows[1] + blows[2]
                    elif spt.get('n_spt'):
                        n30 = spt['n_spt']
                    else:
                        n30 = None
                    if n30 is not None:
                        _set('spt_n30', str(n30), 'sondeig vision')

                    # Depth range: absolute values, formatted as "-1.00 a -1.60"
                    depth_from = spt.get('depth_from_m')
                    depth_to = spt.get('depth_to_m')
                    if depth_from is not None and depth_to is not None:
                        df = abs(float(depth_from))
                        dt = abs(float(depth_to))
                        _set('spt_depth_range', f"-{df:.2f} a -{dt:.2f}", 'sondeig vision')

                    # Lithology: find the sondeig layer at SPT depth
                    lithology = ''
                    spt_depth = abs(float(depth_from)) if depth_from is not None else 0
                    for layer in test.get('layers', []):
                        lf = abs(float(layer.get('depth_from_m', 0)))
                        lt = abs(float(layer.get('depth_to_m', 99)))
                        if lf <= spt_depth < lt:
                            lithology = layer.get('description', '')
                            break
                    if lithology:
                        _set('spt_lithology', lithology, 'sondeig vision')

                    # Location: sondeig test id (e.g. "S-1")
                    _set('spt_location', test.get('test_id', 'S-1'), 'sondeig vision')
    except Exception as e:
        logger.warning("SPT mapping from sondeig failed: %s", e)

    # --- 4.2  Sulfate classification from sulfate_mg_kg (RD 470/2021) ---
    sulfate_raw = _get_val('sulfate_mg_kg')
    if sulfate_raw:
        try:
            sulfate = float(sulfate_raw)
            if sulfate < 2000:
                classification = 'No Agressius'
                baumann = '---'
            elif sulfate < 3000:
                classification = 'Dèbilment agressius'
                baumann = ''
            elif sulfate < 12000:
                classification = 'Moderadament agressius'
                baumann = ''
            elif sulfate < 24000:
                classification = 'Altament agressius'
                baumann = ''
            else:
                classification = 'Molt altament agressius'
                baumann = ''

            _set('sulfate_classification', classification, 'RD 470/2021')
            _set('sulfate_baumann', baumann, 'RD 470/2021')
        except (ValueError, TypeError):
            pass

    # Sulfate level name: default to first geological level
    if sulfate_raw:
        _set('sulfate_level_name', '1er nivell', 'default')

    # --- 4.3  num_floors from planol_extracted.json (safety net) ---
    # Already wired through wizard._load_planol(), but catch edge cases
    # where planol_extracted exists but wizard didn't process dimensions.
    if not _get_val('num_floors'):
        planol_path = project_path / 'validation' / 'planol_extracted.json'
        if planol_path.exists():
            try:
                with open(planol_path, 'r', encoding='utf-8') as f:
                    planol_data = json.load(f)
                arch = planol_data.get('architect_data', {})
                dims = arch.get('dimensions', {})
                floors = dims.get('num_floors', {})
                floors_val = floors.get('pdf_value') if isinstance(floors, dict) else floors
                if floors_val:
                    from automation.formatting import format_floor_notation
                    _set('num_floors', format_floor_notation(str(floors_val)), 'planol vision (fallback)')
            except Exception as e:
                logger.warning("num_floors fallback mapping failed: %s", e)


def get_prefills(project_name: str, *, force_refresh: bool = False) -> dict[str, Any]:
    """Run auto_extract + vision + wizard prefill chain for a project.

    Returns a dict of {field: {value, source, confidence?}} entries.
    Results are cached per project_name; pass force_refresh=True to re-run.
    """
    if not force_refresh and project_name in _prefill_cache and os.environ.get("G3DT_NO_CACHE") != "1":
        return _prefill_cache[project_name]

    project_path = _resolve_project(project_name)
    _clear_stale_user_data(project_path)

    # Phase 0-3: auto_extract (DPSH, lab, ICGC, cadastre — Python only, ~3-5s)
    from automation.auto_extractor import auto_extract
    auto_result = auto_extract(project_path)

    return _merge_prefills(project_name, project_path, auto_result)


def _merge_prefills(project_name: str, project_path: Path, auto_result: Any) -> dict[str, Any]:
    """Merge auto_extract result with vision + wizard prefills. Shared by sync and streaming paths."""
    _run_vision_phase(project_path, force_refresh=False)

    from automation.wizard import UserDataWizard
    wizard = UserDataWizard(str(project_path))
    wizard.load_prefills()

    merged: dict[str, Any] = {}

    for key, value in auto_result.prefills.items():
        source = auto_result.sources.get(key, 'auto')
        merged[key] = {'value': value, 'source': source}

    for key, entry in wizard.prefills.items():
        # Don't let wizard defaults overwrite real extracted data
        source = entry.get('source', '') if isinstance(entry, dict) else ''
        if source == 'default estandard' and key in merged:
            continue
        merged[key] = entry

    if 'street_address' not in merged and 'street_address' in wizard._user_data_full:
        merged['street_address'] = {'value': wizard._user_data_full['street_address'], 'source': 'planol vision'}

    # Use site_address from auto_extract (pressupost/docs intel) to fill or improve
    # street_address and site_municipality.  site_address typically contains the
    # street + number + city (e.g. "C/MESTRE RAMON ORTIZ 15, BELL-LLOC") and is
    # more complete than planol vision which may omit the street number.
    site_addr_entry = merged.get('site_address')
    if site_addr_entry:
        import re
        site_addr_val = site_addr_entry['value'] if isinstance(site_addr_entry, dict) else site_addr_entry
        site_addr_source = (site_addr_entry.get('source', 'auto') if isinstance(site_addr_entry, dict) else 'auto')
        if site_addr_val and isinstance(site_addr_val, str):
            from automation.wizard import _split_address
            sa_street, sa_municipality = _split_address(site_addr_val)
            # Fill street_address if missing, or upgrade if current one lacks a number
            cur_street = merged.get('street_address')
            cur_street_val = (cur_street['value'] if isinstance(cur_street, dict) else cur_street) if cur_street else ''
            has_number = bool(re.search(r'\d', str(cur_street_val)))
            sa_has_number = bool(re.search(r'\d', sa_street))
            if not cur_street_val or (not has_number and sa_has_number):
                merged['street_address'] = {'value': sa_street, 'source': site_addr_source}
            # Fill municipality if missing or is just folder name default
            cur_muni = merged.get('site_municipality')
            cur_muni_source = (cur_muni.get('source', '') if isinstance(cur_muni, dict) else '') if cur_muni else ''
            if sa_municipality and (not cur_muni or cur_muni_source == 'nom carpeta'):
                merged['site_municipality'] = {'value': sa_municipality, 'source': site_addr_source}

    # Override cota_referencia with sondeig elevation_z (field-measured)
    # if the current value is NOT a manual Eva edit.
    # Sondeig field measurement (e.g. +199.50) is more accurate than ICGC DTM (e.g. +199.00).
    cota_entry = merged.get('cota_referencia')
    cota_source = (cota_entry.get('source', '') if isinstance(cota_entry, dict) else '') if cota_entry else ''
    if cota_source != 'user':
        try:
            from automation.vision_normalizer import load_sondeig_merged
            sondeig_data = load_sondeig_merged(project_path / 'validation')
            elev_z = sondeig_data.get('elevation_z')
            if elev_z is not None:
                cota_val = float(elev_z)
                merged['cota_referencia'] = {'value': f"+{cota_val:.2f}", 'source': 'sondeig elevation_z'}
        except Exception:
            pass

    vision_types = {'planol': 'planol_extracted.json', 'dpsh': 'dpsh_extracted.json', 'sondeig': 'sondeig_extracted.json', 'sondeig_annex': 'sondeig_annex_extracted.json', 'docs': 'docs_extracted.json'}
    vision_status = {}
    for vt, filename in vision_types.items():
        vision_status[vt] = (project_path / 'validation' / filename).exists()
    merged['_vision_status'] = {'value': vision_status, 'source': 'system'}

    # Load concept_map if available
    concept_map_path = project_path / 'validation' / 'concept_map.json'
    if concept_map_path.exists():
        try:
            cm_data = json.loads(concept_map_path.read_text(encoding='utf-8'))
            merged['_concept_map'] = {'value': cm_data.get('concept_sources', {}), 'source': 'concept_scout'}
        except Exception:
            logger.warning("Failed to load concept_map.json for %s", project_name)

    if auto_result.file_mapping:
        fm = auto_result.file_mapping
        fm_serialized = {}
        for role_name, role_obj in fm.roles.items():
            fm_serialized[role_name] = {
                'path': role_obj.path if hasattr(role_obj, 'path') else str(role_obj),
                'confidence': getattr(role_obj, 'confidence', None),
            }
        merged['_file_mapping'] = {'value': fm_serialized, 'source': 'system'}

    merged['_projects_base'] = {'value': str(_REF_DIR), 'source': 'system'}

    # FileMiner alternatives — enables +N badges in wizard UI
    if hasattr(auto_result, 'mining_alternatives') and auto_result.mining_alternatives:
        merged['_alternatives'] = {
            'value': auto_result.mining_alternatives,
            'source': 'fileminer',
        }

    # If auto_extract skipped adjacents (no UTM coords), try geocoding from
    # planol address now that vision data is available in the merged prefills.
    _fill_missing_adjacents(merged, project_path)

    # Generate formatted adjacent sentences for diagnostic comparison
    def _get_merged_val(key: str) -> str:
        entry = merged.get(key)
        if entry is None:
            return ''
        if isinstance(entry, dict):
            return str(entry.get('value', ''))
        return str(entry)

    from automation.adjacent_formatter import format_all_adjacents
    adj_raw = {d: _get_merged_val(f'adjacent_{d}') for d in ('north', 'south', 'east', 'west')}
    municipality_for_fmt = _get_merged_val('site_municipality')
    if any(adj_raw.values()):
        adj_fmt = format_all_adjacents(adj_raw, municipality_for_fmt or None)
        for key, val in adj_fmt.items():
            merged[key] = {'value': val, 'source': 'formatted from Cadastre'}

    # Cross-source: deduce lab_location/lab_sample_id from sondeig SPT depths
    _crossref_lab_from_sondeig(merged, project_path)

    # Generate template prefills (access/site description) AFTER merge,
    # because they depend on adjacents data from auto_extract.
    _generate_template_prefills_from_merged(merged)

    # Compute geotech params + calc transparency notes for wizard display
    _compute_geotech_prefills(merged, project_path, auto_result)

    # Map existing extracted data (SPT, sulfate classification) to prefill keys
    _compute_mapping_prefills(merged, auto_result, project_path)

    # Narrative template variables (num_dpsh_tests, table_dpsh_range, building_structure_desc)
    _compute_narrative_prefills(merged, auto_result, project_path)

    # CTE, seismic, radon lookups from municipality + building data
    _compute_lookup_prefills(merged, auto_result)

    # LLM synthesis for building_type, architect/client, location_sentence
    _synthesize_with_llm(merged, project_path)

    # -- Format learning detection ---
    # Check if any mined files have unrecognized formats
    if auto_result.mining_result:
        from automation.format_learner import FormatLearner
        learner = FormatLearner()
        detections = []

        # Get file_mapping for role lookups
        fm_path = project_path / "file_mapping.json"
        file_mapping = None
        if fm_path.exists():
            file_mapping = json.loads(fm_path.read_text())

        if file_mapping and "roles" in file_mapping:
            for role_name, role_info in file_mapping["roles"].items():
                role_path = role_info.get("path", "")
                file_path = project_path / role_path
                if not file_path.exists():
                    continue
                # Get signals for this file
                file_signals = [
                    s for s in auto_result.mining_result.signals
                    if s.source_file == role_path
                ]
                detection = learner.detect_format(
                    file_path, role_name, file_signals,
                    file_mapping=file_mapping,
                )
                if detection.is_new:
                    detections.append(detection.model_dump())

        if detections:
            merged["_format_learning"] = {
                "value": {
                    "active": True,
                    "detections": detections,
                },
                "source": "system",
            }

    _prefill_cache[project_name] = merged
    _auto_result_cache[project_name] = auto_result
    return merged


def get_prefills_streaming(project_name: str):
    """Generator yielding SSE events during auto_extract, then final prefills."""
    project_path = _resolve_project(project_name)
    _clear_stale_user_data(project_path)

    event_queue: queue.Queue = queue.Queue()
    auto_result_holder: list = []
    error_holder: list = []

    def progress_callback(event_type: str, detail: dict):
        event_queue.put((event_type, detail))

    def run_extract():
        try:
            from automation.auto_extractor import auto_extract
            result = auto_extract(project_path, on_progress=progress_callback)
            auto_result_holder.append(result)
        except Exception as e:
            error_holder.append(e)
        finally:
            event_queue.put(None)  # Sentinel

    thread = threading.Thread(target=run_extract, daemon=True)
    thread.start()

    # Yield SSE events as they arrive
    while True:
        item = event_queue.get()
        if item is None:
            break
        event_type, detail = item
        yield f"event: {event_type}\ndata: {json.dumps(detail, ensure_ascii=False)}\n\n"

    thread.join()

    if error_holder:
        yield f"event: error_event\ndata: {json.dumps({'message': str(error_holder[0])})}\n\n"
        return

    if not auto_result_holder:
        yield f"event: error_event\ndata: {json.dumps({'message': 'Extraction ended without result'})}\n\n"
        return

    # --- Vision phase (after auto_extract, before merge) ---
    if auto_result_holder:
        from .vision_groq import groq_available
        if groq_available():
            yield f"event: step\ndata: {json.dumps({'step': 'vision', 'status': 'active'})}\n\n"

            vision_queue: queue.Queue = queue.Queue()

            def run_vision():
                try:
                    def vision_cb(event_type, detail):
                        vision_queue.put((event_type, detail))
                    _run_vision_phase(project_path, force_refresh=False, on_progress=vision_cb)
                except Exception as e:
                    logger.warning("Vision phase error: %s", e)
                finally:
                    vision_queue.put(None)

            vision_thread = threading.Thread(target=run_vision, daemon=True)
            vision_thread.start()

            while True:
                item = vision_queue.get()
                if item is None:
                    break
                event_type, detail = item
                yield f"event: {event_type}\ndata: {json.dumps(detail, ensure_ascii=False)}\n\n"

            vision_thread.join()
            yield f"event: step\ndata: {json.dumps({'step': 'vision', 'status': 'done'})}\n\n"

    try:
        auto_result = auto_result_holder[0]
        merged = _merge_prefills(project_name, project_path, auto_result)
        yield f"event: prefills\ndata: {json.dumps(merged, ensure_ascii=False)}\n\n"
    except Exception as e:
        logger.exception("Error merging prefills for streaming")
        yield f"event: error_event\ndata: {json.dumps({'message': str(e)})}\n\n"


def get_vision_status(project_name: str) -> dict[str, Any]:
    """Check which vision extraction JSONs exist and their mtime."""
    project_path = _resolve_project(project_name)
    vision_files = {
        'planol': 'planol_extracted.json',
        'dpsh': 'dpsh_extracted.json',
        'sondeig': 'sondeig_extracted.json',
        'sondeig_annex': 'sondeig_annex_extracted.json',
        'docs': 'docs_extracted.json',
    }
    status = {}
    for key, filename in vision_files.items():
        path = project_path / 'validation' / filename
        if path.exists():
            status[key] = {"exists": True, "mtime": path.stat().st_mtime}
        else:
            status[key] = {"exists": False, "mtime": None}

    # If any vision file is newly available, refresh the cached prefills
    cached = _prefill_cache.get(project_name)
    if cached:
        cached_vision = cached.get('_vision_status', {}).get('value', {})
        newly_available = any(
            status[k]['exists'] and not cached_vision.get(k, False)
            for k in vision_files
        )
        if newly_available:
            logger.info("New vision files detected for %s, refreshing prefills", project_name)
            # Update vision status in cache
            cached['_vision_status'] = {'value': {k: v['exists'] for k, v in status.items()}, 'source': 'system'}
            # Re-run wizard prefill loading to pick up new vision data
            try:
                from automation.wizard import UserDataWizard
                wizard = UserDataWizard(str(project_path))
                wizard.load_prefills()
                for key, entry in wizard.prefills.items():
                    cached[key] = entry
                # Override cota_referencia with sondeig elevation_z if not user-set
                cota_entry = cached.get('cota_referencia')
                cota_source = (cota_entry.get('source', '') if isinstance(cota_entry, dict) else '') if cota_entry else ''
                if cota_source != 'user':
                    try:
                        from automation.vision_normalizer import load_sondeig_merged
                        sdata = load_sondeig_merged(project_path / 'validation')
                        ez = sdata.get('elevation_z')
                        if ez is not None:
                            cached['cota_referencia'] = {'value': f"+{float(ez):.2f}", 'source': 'sondeig elevation_z'}
                    except Exception:
                        pass
            except Exception as e:
                logger.warning("Failed to refresh wizard prefills: %s", e)

    return status


def start_vision_cli(project_name: str, force: bool = False) -> dict[str, Any]:
    """Start Claude CLI vision extraction as a background subprocess.

    Returns immediately with status: 'started', 'already_running', or 'error'.
    The subprocess creates validation/*_extracted.json files that the frontend
    detects via polling /api/vision-status/.
    """
    project_path = _resolve_project(project_name)
    claude_path = os.getenv('G3DT_CLAUDE_PATH', 'claude')

    with _vision_lock:
        existing = _vision_processes.get(project_name)
        if existing and existing.poll() is None:
            return {"status": "already_running"}

        force_flag = " --force" if force else ""
        prompt = f"/g3dt-visio-projecte {project_path}{force_flag}"
        # Clear last result so polling knows a new run started
        _vision_last_rc.pop(project_name, None)

        # Log stdout/stderr to temp file for timing diagnosis
        log_path = Path('/tmp') / f'claude-vision-{project_name.replace("/","_")}.log'
        logger.info("Vision CLI log: %s", log_path)

        # Replicate exactly the manual command that works:
        #   claude -p "..." --permission-mode bypassPermissions < /dev/null > log 2>&1
        # Using shell=True to match the bash invocation behavior.
        import shlex
        shell_cmd = (
            f'{shlex.quote(claude_path)} -p {shlex.quote(prompt)}'
            f' --permission-mode bypassPermissions'
            f' < /dev/null > {shlex.quote(str(log_path))} 2>&1'
        )
        logger.info("Vision CLI cmd: %s", shell_cmd)

        try:
            proc = subprocess.Popen(
                shell_cmd,
                shell=True,
                cwd=str(_PROJECT_ROOT),
                start_new_session=True,
            )
        except FileNotFoundError:
            return {
                "status": "error",
                "message": f"claude CLI no trobat al PATH (buscat: '{claude_path}'). "
                           "Verifica que Claude Code esta instal·lat.",
            }

        _vision_processes[project_name] = proc

    def _wait_and_cleanup():
        timeout = int(os.getenv('G3DT_VISION_TIMEOUT', '600'))
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            import signal
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, OSError):
                proc.kill()
            proc.wait()
            logger.warning("Vision CLI timed out after %ds for %s", timeout, project_name)
            with _vision_lock:
                _vision_last_rc[project_name] = -1
                if _vision_processes.get(project_name) is proc:
                    del _vision_processes[project_name]
            return
        rc = proc.returncode
        if rc != 0:
            logger.warning("Vision CLI ended rc=%d for %s (see %s)", rc, project_name, log_path)
        else:
            logger.info("Vision CLI completed successfully for %s (see %s)", project_name, log_path)
        with _vision_lock:
            _vision_last_rc[project_name] = rc
            if _vision_processes.get(project_name) is proc:
                del _vision_processes[project_name]

    threading.Thread(target=_wait_and_cleanup, daemon=True).start()
    return {"status": "started"}


def get_vision_process_status(project_name: str) -> dict[str, Any]:
    """Check if a vision subprocess is running for this project."""
    with _vision_lock:
        proc = _vision_processes.get(project_name)
        if proc is not None:
            rc = proc.poll()
            if rc is None:
                return {"running": True, "returncode": None}
            return {"running": False, "returncode": rc}
        # Process already cleaned up — check last result
        last_rc = _vision_last_rc.get(project_name)
        if last_rc is not None:
            return {"running": False, "returncode": last_rc}
        return {"running": False, "returncode": None}


def _run_vision_phase(project_path: Path, force_refresh: bool, on_progress=None) -> None:
    """Run vision extraction (Claude preferred, Groq fallback). Non-fatal on failure."""
    try:
        from .vision_groq import groq_available, run_vision_groq_sync
        if groq_available():
            logger.info("Vision phase: running extraction for %s", project_path.name)
            run_vision_groq_sync(project_path, force_refresh=force_refresh, on_progress=on_progress)
            return
    except Exception as e:
        logger.warning("Vision extraction failed: %s", e)

    logger.info("Vision phase: no vision API available, skipping")


def load_user_data(project_name: str) -> dict[str, Any]:
    """Read existing user_data.json for a project, or empty dict."""
    project_path = _resolve_project(project_name)
    ud_path = project_path / 'user_data.json'
    if not ud_path.exists():
        return {}
    try:
        return json.loads(ud_path.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError):
        return {}


def save_wizard(
    project_name: str,
    wizard_fields: dict[str, Any],
    expert_overrides: dict[str, Any] | None = None,
) -> Path:
    """Save wizard data to user_data.json."""
    project_path = _resolve_project(project_name)

    # Collect current sources from prefill cache so they survive save/reload.
    # Mark fields Eva changed as 'user' so badges turn green on reload.
    current_sources = {}
    cached = _prefill_cache.get(project_name, {})
    for k, v in cached.items():
        if isinstance(v, dict) and 'source' in v and not k.startswith('_'):
            current_sources[k] = v['source']
    def _prefill_val(key):
        pf = cached.get(key)
        return pf['value'] if isinstance(pf, dict) and 'value' in pf else None

    def _is_changed(key, new_val):
        old = _prefill_val(key)
        if old is None:
            # No prefill existed — only mark as user if Eva typed something
            return bool(new_val) and str(new_val).strip() != ''
        return str(new_val) != str(old)

    # Detect changes: compare wizard_fields against prefill values
    for field, new_val in wizard_fields.items():
        if _is_changed(field, new_val):
            current_sources[field] = 'user'
    # Detect expert override changes
    if expert_overrides:
        for field, new_val in expert_overrides.items():
            if field == 'geomech_params' and isinstance(new_val, dict):
                for param, val in new_val.items():
                    if _is_changed(f'geomech_{param}', val):
                        current_sources[f'geomech_{param}'] = 'user'
            elif _is_changed(field, new_val):
                current_sources[field] = 'user'

    from automation.wizard import save_wizard_data
    result = save_wizard_data(project_path, wizard_fields, expert_overrides, sources=current_sources)

    # -- Format learning: save confirmed format if learning was active ---
    if cached.get("_format_learning"):
        fl = cached["_format_learning"]
        if isinstance(fl, dict) and fl.get("value", {}).get("active"):
            _save_learned_formats(project_path, wizard_fields, fl["value"].get("detections", []))

    _prefill_cache.pop(project_name, None)
    _auto_result_cache.pop(project_name, None)
    return result


def _save_learned_formats(
    project_path: Path,
    wizard_fields: dict[str, Any],
    detections: list[dict],
) -> None:
    """Save format schemas from Eva's confirmed wizard edits."""
    from automation.format_learner import FormatLearner
    learner = FormatLearner()

    for det in detections:
        role = det.get("role", "")
        source_file = det.get("file_path", "")
        missing_fields = det.get("missing_fields", [])

        # Build confirmed mappings from wizard_fields that fill missing fields
        confirmed = []
        for field_name in missing_fields:
            val = wizard_fields.get(field_name)
            if val and str(val).strip():
                # Eva provided a value for this missing field
                confirmed.append({
                    "label": field_name.upper().replace("_", " "),
                    "concept_id": field_name,
                })

        if confirmed:
            try:
                learner.confirm_mappings(
                    role=role,
                    source_file=source_file,
                    confirmed_mappings=confirmed,
                )
            except Exception:
                logger.warning("Failed to save learned format for %s", source_file, exc_info=True)


def geocode_coords(
    project_name: str,
    address: str | None = None,
) -> dict[str, Any]:
    """Run geocoding pipeline to derive UTM coordinates from address.

    Args:
        project_name: Project folder name.
        address: Street address override. If None, derived from project data.

    Returns:
        Dict with utm_x, utm_y, rc, source keys.

    Raises:
        ValueError: If project not found or no address available.
    """
    project_path = _resolve_project(project_name)

    # Get municipality: site_municipality (wizard) > folder name
    from automation.folder_utils import parse_folder_name
    ud = load_user_data(project_name)
    municipality = ud.get('site_municipality') or ''
    if not municipality:
        _, municipality = parse_folder_name(project_path.name)
    if not municipality:
        raise ValueError("No s'ha pogut extreure el municipi del nom de carpeta")

    # Resolve address: parameter > user_data > adjacent_south
    if not address:
        address = (
            ud.get('street_address')
            or ud.get('site_address')
            or ud.get('adjacent_south')
        )
    if not address:
        raise ValueError(
            "Cal una adreça per geocodificar. "
            "Introdueix-la al camp 'Adreca del solar' o passa-la com a paràmetre."
        )

    # Get point IDs from DPSH if available
    point_ids = ['P-1']
    dpsh_path = project_path / 'validation' / 'dpsh_extracted.json'
    if dpsh_path.exists():
        try:
            dpsh_data = json.loads(dpsh_path.read_text(encoding='utf-8'))
            ids = [t.get('test_id') for t in dpsh_data.get('dpsh_tests', []) if t.get('test_id')]
            if ids:
                point_ids = ids
        except (json.JSONDecodeError, KeyError):
            pass

    # Get province from prefills or user_data
    province = ud.get('province', '')
    if not province and project_name in _prefill_cache:
        prov_entry = _prefill_cache[project_name].get('province')
        province = (prov_entry['value'] if isinstance(prov_entry, dict) else prov_entry) if prov_entry else ''

    # Run geocoding
    from automation.geocode_coordinates import geocode_project, GeocodeError
    try:
        result = geocode_project(address, municipality, point_ids, output_dir=project_path, province=province)
    except GeocodeError as e:
        raise ValueError(f"Error de geocodificació: {e}")

    if result is None:
        raise ValueError(
            f"No s'han trobat coordenades per '{address}, {municipality}'. "
            "Verifica l'adreça o introdueix les coordenades UTM manualment."
        )

    # Save utm_x/utm_y to user_data.json
    from automation.wizard import save_wizard_data
    save_wizard_data(project_path, {
        'utm_x': round(result['utm_x'], 2),
        'utm_y': round(result['utm_y'], 2),
    })

    # Invalidate prefill cache so Phase 3 re-runs
    _prefill_cache.pop(project_name, None)
    _auto_result_cache.pop(project_name, None)

    return result


def generate_report(project_name: str) -> dict[str, Any]:
    """Run ReportGenerator and return result info."""
    project_path = _resolve_project(project_name)

    from automation.folder_utils import parse_folder_name
    expedient, _ = parse_folder_name(project_path.name)
    output_name = f'{expedient}_generated.docx'
    output_path = project_path / output_name

    from automation.report_generator import ReportGenerator
    generator = ReportGenerator(project_path=str(project_path))
    result = generator.generate(str(output_path))

    return {
        'success': result.success,
        'output_path': str(output_path) if result.success else None,
        'output_name': output_name if result.success else None,
        'errors': result.errors,
        'warnings': result.warnings,
    }


def find_report(project_name: str) -> Path | None:
    """Locate the generated .docx for a project."""
    project_path = _resolve_project(project_name)
    matches = list(project_path.glob('*_generated.docx'))
    if matches:
        # Return most recently modified
        return max(matches, key=lambda p: p.stat().st_mtime)
    return None


def _find_reference_report(project_path: Path) -> Path | None:
    """Find the reference .docx for a project.

    Search order:
    1. /mnt/c/claude/g3dt/4-informes/{folder_name}/*_informe*.docx
    2. project_path/*_informe*.docx
    If only .doc found, convert via soffice.
    """
    folder_name = project_path.name

    for search_dir in [_INFORMES_DIR / folder_name, project_path]:
        if not search_dir.is_dir():
            continue

        # Try .docx first
        docx_matches = list(search_dir.glob('*_informe*.docx'))
        if docx_matches:
            return max(docx_matches, key=lambda p: p.stat().st_mtime)

        # Fallback: .doc → convert
        doc_matches = [p for p in search_dir.glob('*_informe*.doc') if not p.name.startswith('~')]
        if doc_matches:
            doc_path = max(doc_matches, key=lambda p: p.stat().st_mtime)
            try:
                subprocess.run(
                    ['soffice', '--headless', '--convert-to', 'docx',
                     '--outdir', str(search_dir), str(doc_path)],
                    capture_output=True, timeout=30,
                )
                converted = doc_path.with_suffix('.docx')
                if converted.exists():
                    return converted
            except (subprocess.TimeoutExpired, FileNotFoundError):
                logger.warning("soffice conversion failed for %s", doc_path)

    return None


def run_audit_visual(project_name: str) -> dict[str, Any]:
    """Run intelligent audit comparing generated vs reference report."""
    project_path = _resolve_project(project_name)

    # Find generated report
    generated = find_report(project_name)
    if not generated:
        return {
            'success': False,
            'output_name': None,
            'errors': ["No s'ha trobat l'informe generat. Genera'l primer."],
            'warnings': [],
        }

    # Find reference report
    reference = _find_reference_report(project_path)
    if not reference:
        return {
            'success': False,
            'output_name': None,
            'errors': ["No s'ha trobat l'informe de referència (signat per Eva)."],
            'warnings': [],
        }

    try:
        from automation.intelligent_audit import run_audit
        result = run_audit(generated, reference, project_path=project_path)
        stats = result.get('statistics', {})
        highlight_file = result.get('highlight_file')
        output_name = Path(highlight_file).name if highlight_file else None
        return {
            'success': True,
            'output_name': output_name,
            'auto_resolved_pct': stats.get('auto_resolved_pct', 0),
            'needs_review': stats.get('needs_review', 0),
            'missing': stats.get('missing_in_generated', 0),
            'errors': [],
            'warnings': [],
        }
    except Exception as e:
        logger.exception("Audit failed for %s", project_name)
        return {
            'success': False,
            'output_name': None,
            'errors': [str(e)],
            'warnings': [],
        }


def get_auto_result(project_name: str) -> Any | None:
    """Get cached AutoExtractionResult for dev-analysis-v2. Returns None if not cached."""
    return _auto_result_cache.get(project_name)


def find_audit_report(project_name: str) -> Path | None:
    """Locate the most recent AUDIT_VISUAL .docx for a project."""
    project_path = _resolve_project(project_name)
    validation_dir = project_path / 'validation'
    if not validation_dir.is_dir():
        return None
    matches = list(validation_dir.glob('*_AUDIT_VISUAL.docx'))
    if matches:
        return max(matches, key=lambda p: p.stat().st_mtime)
    return None
