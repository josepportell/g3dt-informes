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

# Sources that indicate high-priority extraction data (trusted over LLM synthesis).
# Phase B update (2026-04-19): added `computed` so narrative fields that
# report_generator populates via template rendering (site_condition with
# "computed (slope X%)" / "computed (ES template)" sources) aren't clobbered
# by `llm_synthesis_with_observations`. Before this, the sweep regressed 4.7pp
# because Phase B's synthesis overrode correctly-rendered computed values.
# NOTE: `plantilla generada` is intentionally NOT trusted — it's a generic
# filler (e.g. "parcel·la de forma rectangular amb superfície de 571 m2")
# that synthesis can legitimately improve for site_description prose.
_TRUSTED_SOURCE_PATTERNS = (
    'planol', 'sondeig', 'vision', 'ICGC', 'Cadastre', 'DPSH',
    'contingut:', 'fileminer:', 'groq_llm:',
    'computed',
)

# Minimum ConceptScout visual observations required to enable LLM-driven
# per-direction adjacent_*_fmt synthesis. Below this threshold, the cadastre
# template (format_all_adjacents) output is used as-is.
_MIN_VISUALS_FOR_ADJACENT_SYNTHESIS = 2

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


def _observe_terrain_photos(project_path: Path, file_mapping_roles: dict) -> str:
    """Observe field photos and return a brief terrain description.

    Uses OpenAI vision (gpt-4.1-mini) to describe terrain surface, vegetation,
    slopes, and nearby structures. The text helps Eva decide is_anthropized
    but does NOT make the decision itself.

    Returns empty string on any failure (missing photos, no API key, API error).
    """
    import re

    try:
        import httpx
    except ImportError:
        return ''

    api_key = config.OPENAI_API_KEY
    if not api_key:
        return ''

    # Find photos directory
    photos_dir = None
    fm_photos = file_mapping_roles.get('photos_dir', {})
    if isinstance(fm_photos, dict) and fm_photos.get('path'):
        candidate = project_path / fm_photos['path']
        if candidate.is_dir():
            photos_dir = candidate

    if not photos_dir:
        for dirname in ('FOTOGRAFIES', 'FOTOS DE CAMP', 'Fotografies', 'fotos'):
            candidate = project_path / dirname
            if candidate.is_dir():
                photos_dir = candidate
                break

    if not photos_dir:
        return ''

    # Collect all image files recursively
    image_exts = {'.jpg', '.jpeg', '.png'}
    all_images: list[Path] = []
    for ext in image_exts:
        all_images.extend(photos_dir.rglob(f'*{ext}'))
        all_images.extend(photos_dir.rglob(f'*{ext.upper()}'))
    # Deduplicate (rglob .jpg and .JPG may overlap on case-insensitive FS)
    all_images = list({p.resolve(): p for p in all_images}.values())

    # Filter out document-like images (field data sheets, croquis)
    skip_keywords = ('penetrometre', 'full de camp', 'croquis', 'fitxa', 'acta')
    filtered: list[Path] = []
    for img in all_images:
        name_lower = img.stem.lower()
        if any(kw in name_lower for kw in skip_keywords):
            continue
        filtered.append(img)

    if not filtered:
        return ''

    # Prioritize selection: vista/general photos first, then P1-P4, then rest
    priority_keywords = ('vista', 'general', 'des de', 'des del', 'interior', 'zona', 'empl')
    tier1: list[Path] = []  # panoramic/overview
    tier2: list[Path] = []  # P1-P4 numbered photos
    tier3: list[Path] = []  # everything else (WhatsApp, etc.)

    for img in filtered:
        name_lower = img.stem.lower()
        if any(kw in name_lower for kw in priority_keywords):
            tier1.append(img)
        elif re.match(r'^p\d', name_lower):
            tier2.append(img)
        else:
            tier3.append(img)

    selected = (tier1 + tier2 + tier3)[:5]
    if not selected:
        return ''

    # Encode images to base64
    from web.vision_groq import _file_to_images
    b64_images: list[str] = []
    for img_path in selected:
        try:
            imgs = _file_to_images(img_path, dpi=150, max_pages=1)
            if imgs:
                b64_images.append(imgs[0])
        except Exception:
            continue

    if not b64_images:
        return ''

    # Build vision request
    prompt = (
        "Descriu breument el que observes del terreny i l'entorn visible en "
        "aquestes fotografies de camp d'un estudi geotecnic. Centra't en: "
        "superficie del sol (natural, remogut, pavimentat, runa), vegetacio, "
        "pendents, i presencia d'edificacions o infraestructures adjacents. "
        "Dues o tres frases curtes."
    )

    content: list[dict] = [{"type": "text", "text": prompt}]
    for b64_img in b64_images:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"},
        })

    payload = {
        "model": config.VISION_MODEL_OPENAI,
        "messages": [
            {"role": "system", "content": "Ets un observador de camp geotecnic. Respon en catala."},
            {"role": "user", "content": content},
        ],
        "temperature": 0.0,
        "max_tokens": 300,
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
        if resp.status_code != 200:
            logger.warning("Terrain observation vision call failed: HTTP %d", resp.status_code)
            return ''

        data = resp.json()
        text = data.get('choices', [{}])[0].get('message', {}).get('content', '')
        return text.strip()

    except Exception as e:
        logger.warning("Terrain observation failed: %s", e)
        return ''


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
                if not is_anthro or is_anthro.lower() in ('none', ''):
                    # No decision made — use slope only
                    if slope_val > 10:
                        qualifier = "Tot i no ser un solar pla"
                    else:
                        qualifier = "Com que es tracta d'un solar pla"
                else:
                    anthro = str(is_anthro).lower() not in ('false', '0')
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

    # Pull bearing-stratum N20 from sondeig_extracted (Eva's skip-soft-top rule).
    # Falls back to overall_average_n20 for single-layer profiles.
    sondeig_layers: list[dict] = []
    soil_types_list: list[str] = []
    try:
        from automation.vision_normalizer import load_sondeig_merged
        sdata = load_sondeig_merged(project_path / 'validation')
        tests = sdata.get('sondeig_tests', [])
        if tests and tests[0].get('layers'):
            sondeig_layers = tests[0]['layers']
    except Exception:
        pass

    # Fallback: no sondeig file or empty extraction → synthesize layers from
    # DPSH N20 step-change (mirrors build_report_data's Fix α fallback so the
    # wizard prefill path and the report-generation path stay aligned).
    if not sondeig_layers and getattr(dpsh, 'tests', None):
        try:
            from automation.dpsh_segmenter import segment_by_n20_step
            sondeig_layers = segment_by_n20_step(dpsh)
            if sondeig_layers and len(sondeig_layers) > 1:
                logger.info(
                    "dpsh_segmenter synthesized %d sondeig_layers from DPSH "
                    "in wizard_service prefill (no sondeig file or empty).",
                    len(sondeig_layers),
                )
        except Exception as exc:
            logger.warning("dpsh_segmenter fallback failed: %s", exc)
            sondeig_layers = []

    # Determine bearing-level soil type from merged prefills.
    # num_levels reflects the highest-indexed level key; soil_type/desc use it.
    num_levels = 1
    nle = merged.get('num_geological_levels') or merged.get('num_soil_levels')
    if nle:
        nle_val = nle['value'] if isinstance(nle, dict) else nle
        try:
            num_levels = int(nle_val)
        except (ValueError, TypeError):
            pass

    # Build per-level soil types from merged prefills (needed by bicapa).
    n_types = max(num_levels, len(sondeig_layers))
    for i in range(1, n_types + 1):
        _e = merged.get(f'soil_type_level_{i}')
        _v = (_e['value'] if isinstance(_e, dict) else _e) or ''
        soil_types_list.append(str(_v).lower())

    try:
        from automation.report_data import _bearing_stratum_n20
        if sondeig_layers:
            avg_n20 = _bearing_stratum_n20(dpsh, sondeig_layers, soil_types_list)
        else:
            avg_n20 = getattr(dpsh, 'overall_average_n20', None)
    except Exception:
        avg_n20 = getattr(dpsh, 'overall_average_n20', None)
    if not avg_n20 or avg_n20 <= 0:
        return

    nb = avg_n20 / 0.83

    # Pick bearing layer index (skip-soft-top rule) and use it to resolve
    # the soil_type/description keys that belong to the bearing stratum.
    # This keeps avg_n20 and soil_type/description aligned even when the
    # bicapa picks a middle layer or num_levels was user-merged.
    try:
        from automation.report_data import _select_bearing_layer_idx
        bearing_idx = _select_bearing_layer_idx(sondeig_layers, soil_types_list) if sondeig_layers else 0
    except Exception:
        bearing_idx = max(0, len(sondeig_layers) - 1) if sondeig_layers else 0

    if sondeig_layers and (num_levels - 1) != bearing_idx:
        logger.warning(
            "Bearing stratum divergence: num_levels=%d (1-based %d) but bearing_idx=%d. "
            "Using bearing_idx for soil_type/description lookups.",
            num_levels, num_levels, bearing_idx,
        )

    bearing_level_1based = bearing_idx + 1 if sondeig_layers else num_levels

    soil_type_key = f'soil_type_level_{bearing_level_1based}'
    st_entry = merged.get(soil_type_key) or merged.get('soil_type_level_1')
    soil_type = (st_entry['value'] if isinstance(st_entry, dict) else st_entry) if st_entry else 'granular'
    if not soil_type:
        soil_type = 'granular'
    soil_type = soil_type.lower()

    # Get bearing-level description for rock detection
    desc_key = f'sondeig_layer_desc_{bearing_level_1based}'
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

    # Diagnostic-only stamps (underscore prefix => filtered out of variable
    # comparison loop in scripts/diagnostic_trace.py:363). Used by
    # _format_calc_trace to surface the bicapa pick + Crespo fines branch
    # that drove the qa_value computation.
    _set('_calc_bearing_idx', bearing_idx, 'system')
    # Stash bearing-filtered N20 so _compute_lookup_prefills (cte_sol) can
    # consume it without re-deriving. Underscore prefix keeps it out of the
    # diagnostic variable comparison loop.
    _set('_bearing_avg_n20', avg_n20, 'system')
    # Map soil_type -> Crespo fine_fraction label that crespo_phi_granular
    # would receive if invoked. "transitional" matches Eva's anchor at 28°
    # for llim argilós / sorres argiloses (Finding #10).
    # diagnostic-display only; never pass directly to crespo_phi_granular (which accepts only clean/normal/transitional)
    _FINE_FRACTION_BY_SOIL = {
        'granular': 'normal', 'grava': 'normal', 'arena': 'normal',
        'arena_limosa': 'transitional', 'limo': 'transitional',
        'cohesive': 'transitional', 'arcilla': 'transitional',
        'rock': 'n/a',
    }
    _set('_calc_fine_fraction', _FINE_FRACTION_BY_SOIL.get(soil_type, 'normal'), 'system')

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
            nspt=nb, is_granular=is_granular, soil_type=soil_type,
            E=E, Es_override=Es_override,
        )

        _set('qa_value', f"{tr.Qa:.2f}", 'Terzaghi-Peck')
        if tr.qa_cap_reason is not None:
            _set('qa_cap_reason', tr.qa_cap_reason, 'Terzaghi-Peck')
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

    # CTE soil classification — prefer the bearing-stratum-filtered N20 that
    # _compute_geotech_prefills stashed in merged['_bearing_avg_n20']. That
    # value reflects the competent bearing layer (skip-soft-top rule) rather
    # than the whole-profile mean, which can be polluted by shallow fill.
    # Falls back to overall_average_n20 when the stash is absent (e.g. no
    # DPSH, or geotech prefills short-circuited earlier).
    dpsh = auto_result.dpsh_data if hasattr(auto_result, 'dpsh_data') else None
    bearing_entry = merged.get('_bearing_avg_n20')
    avg_n20 = None
    if isinstance(bearing_entry, dict):
        try:
            avg_n20 = float(bearing_entry.get('value')) if bearing_entry.get('value') is not None else None
        except (TypeError, ValueError):
            avg_n20 = None
    if avg_n20 is None:
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


_VISUAL_CONCEPT_IDS = (
    'site_vegetation_visual',
    'site_slope_visual',
    'is_anthropized_visual',
    'building_to_demolish_visual',
    'access_road_visual',
    'surrounding_context_visual',
)


def _gather_visual_observations(project_path: Path) -> dict[str, list[dict]]:
    """Return {concept_id: [{file, preview, confidence}, ...]} from concept_map.

    Reads `validation/concept_map.json` (written by ConceptScout) and
    extracts every entry under `concept_sources` whose concept_id is one
    of the 6 visual observation concepts. Used as input to narrative
    synthesis (site_description, site_condition, is_anthropized).

    Returns an empty dict if the file is missing, unreadable, or has no
    visual observations.
    """
    cm_path = project_path / 'validation' / 'concept_map.json'
    if not cm_path.is_file():
        return {}
    try:
        cm = json.loads(cm_path.read_text(encoding='utf-8'))
    except Exception:
        return {}

    sources_map = cm.get('concept_sources') or {}
    if not isinstance(sources_map, dict):
        return {}

    out: dict[str, list[dict]] = {}
    for cid in _VISUAL_CONCEPT_IDS:
        sources = sources_map.get(cid) or []
        if not sources:
            continue
        clean: list[dict] = []
        for src in sources:
            if not isinstance(src, dict):
                continue
            preview = (src.get('signal_preview') or '').strip()
            if not preview:
                continue
            clean.append({
                'file': src.get('file', ''),
                'preview': preview,
                'confidence': float(src.get('confidence', 0.5)),
            })
        if clean:
            out[cid] = clean
    return out


def _format_visual_observations_for_prompt(
    observations: dict[str, list[dict]],
) -> str:
    """Render visual observations as a compact bulleted block for the prompt."""
    if not observations:
        return "(no visual observations found — leave narrative fields empty if no other grounding)"
    lines: list[str] = []
    for cid in _VISUAL_CONCEPT_IDS:
        entries = observations.get(cid) or []
        if not entries:
            continue
        # Deduplicate previews (same tag often appears on multiple photos)
        seen: set[str] = set()
        previews: list[str] = []
        for e in entries:
            pv = e['preview']
            norm = pv.lower().strip()
            if norm not in seen:
                seen.add(norm)
                previews.append(pv)
        short_cid = cid.replace('_visual', '')
        joined = '; '.join(previews[:5])
        lines.append(f"- {short_cid}: {joined}")
    return '\n'.join(lines) if lines else "(no visual observations found)"


def _synthesize_with_llm(merged: dict[str, Any], project_path: Path) -> None:
    """Use Claude API to synthesize narrative fields from all pre-extracted sources.

    One API call per project. Covers three field families:

    - Identity: building_type, architect_name, client_name, location_sentence.
    - Narrative: site_description, site_condition, is_anthropized,
      building_structure_desc (grounded in ConceptScout visual observations
      when available).
    - Adjacents (conditional): adjacent_north_fmt / south / east / west,
      refining the cadastre-template sentences with visual context. Only
      requested when ≥`_MIN_VISUALS_FOR_ADJACENT_SYNTHESIS` visual
      observations are present AND at least one cadastre-fmt sentence is
      non-empty — see the gate below.

    User edits (source='user') are never overwritten for any field.
    """

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

    # Check if ALL synthesis fields already have user edits — skip the API call.
    # Expanded Phase B (2026-04-19): now 8 fields, including 4 narrative outputs
    # (site_description, site_condition, is_anthropized, building_structure_desc).
    # NOTE: adjacent_*_fmt fields are intentionally EXCLUDED from this check.
    # They are conditionally added to the request (gated on ≥2 visual
    # observations AND at least one non-empty cadastre-fmt sentence). The
    # per-field `_get_source(field) == 'user'` guard in the adjacent apply
    # loop still prevents overwriting Eva's edits; treating them as part of
    # the always-requested set would suppress legitimate synthesis of the
    # 8 narrative/identity fields when only the 4 adjacents are user-edited.
    _SYNTHESIS_FIELDS = (
        'building_type', 'architect_name', 'client_name', 'location_sentence',
        'site_description', 'site_condition', 'is_anthropized',
        'building_structure_desc',
    )
    user_fields = [k for k in _SYNTHESIS_FIELDS if _get_source(k) == 'user']
    if len(user_fields) == len(_SYNTHESIS_FIELDS):
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

    # Projecte arquitecte data (multi-page project doc, lower priority than planol)
    projecte_architect = ''
    projecte_company = ''
    projecte_promotor = ''
    projecte_path = project_path / 'validation' / 'projecte_extracted.json'
    if projecte_path.exists():
        try:
            projecte_data = json.loads(projecte_path.read_text(encoding='utf-8'))
            parch = projecte_data.get('architect_data', {})
            projecte_architect = parch.get('architect', '') or ''
            projecte_company = parch.get('architect_company', '') or ''
            projecte_promotor = parch.get('promotor', '') or parch.get('client_name', '') or ''
            # Fill planol fields if they are empty (projecte as fallback)
            if not planol_architect and projecte_architect:
                planol_architect = projecte_architect
            if not planol_company and projecte_company:
                planol_company = projecte_company
            if not planol_promotor and projecte_promotor:
                planol_promotor = projecte_promotor
            if not project_title:
                project_title = parch.get('project_name', '') or ''
        except Exception:
            pass

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

    # Narrative-input data (for site_description + site_condition synthesis)
    icgc_slope_class = _get_val('site_slope_class')
    is_anthropized_current = _get_val('is_anthropized')
    building_height_current = _get_val('building_height_m')
    num_floors_current = _get_val('num_floors')
    has_basement_current = _get_val('has_basement')

    # Visual observations from ConceptScout's probe cache (Phase B)
    visual_observations = _gather_visual_observations(project_path)

    # Language
    lang = _get_project_language(merged)
    lang_name = 'Spanish' if lang == 'es' else 'Catalan'

    # Adjacent synthesis gate (Phase B, 2026-04-19): only ask the LLM to
    # rewrite the 4 adjacent_*_fmt sentences when there is enough visual
    # grounding (≥2 observations). Below that, the existing cadastre-template
    # fallback at `format_all_adjacents` keeps producing the output.
    synthesize_adjacents = len(visual_observations) >= _MIN_VISUALS_FOR_ADJACENT_SYNTHESIS
    adjacent_current_fmt = {
        d: _get_val(f'adjacent_{d}_fmt')
        for d in ('north', 'south', 'east', 'west')
    }
    # Edge case: gate fires but ALL cadastre-template fmt values are empty
    # (e.g. cadastre probe returned nothing). Asking the LLM to "refine"
    # four empty strings produces hallucinated prose. Skip the adjacent
    # block in that case — the cadastre template will produce the same
    # empty output either way, so no regression.
    if synthesize_adjacents and not any(
        (v or '').strip() for v in adjacent_current_fmt.values()
    ):
        logger.info(
            "Adjacent synthesis skipped: all cadastre fmt values are empty",
        )
        synthesize_adjacents = False

    # --- Build prompt ---

    # Adjacent synthesis block — only appended when the ≥2 visuals gate passes.
    # Direction labels and the JSON output keys match the language cue.
    if synthesize_adjacents:
        if lang == 'es':
            adj_dir_labels = 'norte/sur/este/oeste'
        else:
            adj_dir_labels = 'nord/sud/est/oest'
        adjacent_rules_block = f"""

### adjacent_north_fmt / adjacent_south_fmt / adjacent_east_fmt / adjacent_west_fmt
- For each adjacent direction ({adj_dir_labels}), rewrite the cadastre-given facts in Eva's voice.
- You MAY add visual context that clarifies what's on that side (e.g., 'parcel·la buida' → 'parcel·la buida amb vegetació rasa' only if the visual observation confirms it).
- You MUST NOT invent adjacent characteristics not present in the cadastre data or visual observations.
- Keep each description to one short sentence.
- Match the project's reference language ({lang_name}).
- If the cadastre data for a direction is empty and no visual grounding exists, return an empty string "" for that direction."""
        adjacent_sources_block = f"""

**Adjacent (formatted by cadastre template) — starting point you can refine:**
- adjacent_north_fmt (current): "{adjacent_current_fmt['north']}"
- adjacent_south_fmt (current): "{adjacent_current_fmt['south']}"
- adjacent_east_fmt (current): "{adjacent_current_fmt['east']}"
- adjacent_west_fmt (current): "{adjacent_current_fmt['west']}"
"""
        adjacent_output_keys = (
            ',\n  "adjacent_north_fmt": "..."'
            ',\n  "adjacent_south_fmt": "..."'
            ',\n  "adjacent_east_fmt": "..."'
            ',\n  "adjacent_west_fmt": "..."'
        )
        _adj_count = 4
    else:
        adjacent_rules_block = ''
        adjacent_sources_block = ''
        adjacent_output_keys = ''
        _adj_count = 0
    field_count_label = f'{len(_SYNTHESIS_FIELDS) + _adj_count} fields'

    prompt = f"""You are a geotechnical report assistant. Given data extracted from multiple sources about a construction project, synthesize the final values for {field_count_label}.

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

### site_description (narrative paragraph)
- Compose Eva's opening paragraph for the "Descripció del solar" section, in {lang_name}
- Typical opening: "El dia dels treballs de camp es realitza l'entrada a la parcel·la pel Carrer X. La parcel·la es presenta [terreny/vegetació/construccions], presentant un terreny [pendent/pla]..."
- Weave in the visual observations below. Only state facts grounded in the observations OR in the location/adjacents data. DO NOT invent details.
- If fewer than 2 visual observations exist AND no strong grounding, return an empty string "" rather than fabricating.
- Keep it to 1-3 sentences. Match Eva's register (factual, technical, first person plural implicit).

### site_condition (short qualifier)
- One short phrase describing the state of the plot, in {lang_name}
- Patterns: "pla", "antropitzat", "no antropitzat", "pendent moderat cap a sud", etc.
- Inputs: slope class ({icgc_slope_class}), anthropization ({is_anthropized_current}), visual observations
- Output format: lowercase, no article, 1-4 words

### is_anthropized (boolean as "si" or "no")
- TRUE if visual observations show human modification (existing construction, fill, leveling, retaining walls)
- FALSE if site looks natural/undisturbed
- Use is_anthropized_visual observations as primary signal; site_slope_visual ("pla") is a weak secondary signal
- Return "si" or "no" (lowercase)
- If there is no evidence either way, use "no"

### building_structure_desc (short structural phrase)
- Short phrase describing the planned structure for geotechnical context, in {lang_name}
- Examples: "en planta baixa", "amb soterrani", "sense soterrani", "2 plantes sobre rasant amb soterrani", "PB+1Pp"
- Inputs: num_floors ({num_floors_current}), has_basement ({has_basement_current}), building_height_m ({building_height_current})
- Keep it concise (2-6 words){adjacent_rules_block}

## Eva's Reference Examples — identity + location

1. Bell-Lloc (CA): building_type="un habitatge unifamiliar", architect="JORDI BOSCH NOVELL", client="RAMON MITJANA S.L", location="entre el Carrer Antoni Bellet i el Carrer Mestre Ramon Ortiz de Bell-Lloc d'Urgell"
2. Castellar (CA): building_type="3 habitatges unifamiliars d'estructura lleugera, fusta", client="WOOD COMFORT PROMOCIONS SLU", location="en el Carrer dels Arbrells, 18 de Castellar del Valles"
3. Rubi (CA): building_type="un habitatge unifamiliar aillat modular", architect="JOANA MARTINEZ", client="SRA. JOANA MARTINEZ", location="a una parcella ubicada al carrer de la Miranda n 39, (PARC. 6-105) Rubi, Barcelona"
4. Linyola (CA): building_type="un nou habitatge unifamiliar", architect="SILVIA EROLES BALAGUERO", client="SRA. SILVIA EROLES BALAGUERO", location="al Carrer Clot de la Llacuna n16 de Linyola"
5. Alcoletge (CA): building_type="l'ampliacio d'un edifici en planta baixa", architect="ALBERT SANS BONVEHI", client="SR. ALBERT SANS BONVEHI", location="a una parcella ubicada al Carrer Girasols n7, Urbanitzacio El Roser d'Alcoletge"
6. Vilanova (ES): building_type="una vivienda unifamiliar aislada", architect="JUAN JOSE TORRES POVEDANO", client="GRUPO CUENCA GUERRERO, S.L", location="en la Calle STA. GEMMA n 4, URB. LA SERRA del municipio de VILANOVA DE SEGRIA"
7. Anciles (ES): building_type="7 viviendas unifamiliares adosadas", architect="ALBA MARIA BARRAU CASTAN", client="SRA. ALBA MARIA BARRAU CASTAN", location="en la calle Gral Ferraz n20 en el municipio de Anciles, Benasque"

## Eva's Reference Examples — narrative fields

1. Bell-Lloc (CA):
   site_description="El dia dels treballs de camp es realitza l'entrada a la parcel·la pel Carrer Antoni Bellet. La parcel·la es presenta totalment buida, lliure de construccions i vegetació, presentant un terreny lleugerament inclinat cap al sud."
   site_condition="pla"
   is_anthropized="no"
   building_structure_desc="en planta baixa"

2. Castellar (CA):
   site_description="La parcel·la es troba al Carrer dels Arbrells. Es tracta d'un solar antropitzat amb vegetació rasa i presenta un pendent moderat cap al sud."
   site_condition="antropitzat"
   is_anthropized="si"
   building_structure_desc="en planta baixa"

3. Alcoletge (CA):
   site_description="El dia dels treballs de camp s'accedeix a la parcel·la pel Carrer Girasols. Existeix una edificació de planta baixa que es manté, i l'ampliació ocupa la zona est del solar."
   site_condition="antropitzat"
   is_anthropized="si"
   building_structure_desc="ampliació en planta baixa"

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
{adjacent_sources_block}
**Site observations (visual, from ConceptScout probes):**
{_format_visual_observations_for_prompt(visual_observations)}

**Structural sources:**
- num_floors: "{num_floors_current}"
- has_basement: "{has_basement_current}"
- building_height_m: "{building_height_current}"
- is_anthropized (current): "{is_anthropized_current}"
- ICGC slope class: "{icgc_slope_class}"

## Output

Return ONLY a JSON object with exactly these keys:
```json
{{
  "building_type": "...",
  "architect_name": "...",
  "client_name": "...",
  "location_sentence": "...",
  "site_description": "...",
  "site_condition": "...",
  "is_anthropized": "...",
  "building_structure_desc": "..."{adjacent_output_keys}
}}
```

If you cannot determine a value with reasonable confidence, use an empty string "".
For `site_description` specifically: prefer empty over fabricating prose from thin air."""

    # --- Call Claude API (routed via llm_client factory, supports OpenRouter) ---
    try:
        import re as _re

        from automation.llm_client import get_anthropic_client, get_cc_model
        client = get_anthropic_client()
        response = client.messages.create(
            model=get_cc_model(),
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

        # Apply synthesized values.
        # The 4 narrative fields (site_description, site_condition,
        # is_anthropized, building_structure_desc) are tagged with a distinct
        # source so the diagnostic can attribute them to visual_synthesis.
        _IDENTITY_FIELDS = (
            'building_type', 'architect_name', 'client_name', 'location_sentence',
        )
        _NARRATIVE_FIELDS = (
            'site_description', 'site_condition', 'is_anthropized',
            'building_structure_desc',
        )
        for field in _IDENTITY_FIELDS:
            value = result.get(field, '')
            if not isinstance(value, str):
                value = str(value)
            if value and _get_source(field) != 'user':
                _set(field, value)
        for field in _NARRATIVE_FIELDS:
            raw = result.get(field, '')
            if isinstance(raw, bool):
                value = 'si' if raw else 'no'
            elif raw is None:
                value = ''
            else:
                value = str(raw).strip()
            # Normalize is_anthropized to canonical "si"/"no"
            if field == 'is_anthropized':
                low = value.lower()
                if low in ('true', 'yes', 'sí', 'si', '1'):
                    value = 'si'
                elif low in ('false', 'no', '0'):
                    value = 'no'
                elif not low:
                    value = ''
                else:
                    value = low  # leave as-is, _set will check
            if value and value.lower() not in ('null', 'none', 'unknown', ''):
                if _get_source(field) != 'user':
                    _set(field, value, source='llm_synthesis_with_observations')

        # Adjacent_*_fmt — only when the gate opened the request. We bypass
        # _set() here because the existing cadastre source tag ("formatted
        # from Cadastre") matches the trusted "Cadastre" pattern; for these
        # four fields we WANT LLM synthesis to win over the template. User
        # edits are still preserved.
        _ADJACENT_FMT_FIELDS = (
            'adjacent_north_fmt', 'adjacent_south_fmt',
            'adjacent_east_fmt', 'adjacent_west_fmt',
        )
        adjacents_updated = 0
        if synthesize_adjacents:
            for field in _ADJACENT_FMT_FIELDS:
                raw = result.get(field, '')
                if raw is None:
                    value = ''
                else:
                    value = str(raw).strip()
                if not value or value.lower() in ('null', 'none', 'unknown'):
                    # LLM produced no value for this direction: leave cadastre
                    # template output untouched (fallback remains the winner).
                    continue
                if _get_source(field) == 'user':
                    continue
                merged[field] = {
                    'value': value,
                    'source': 'llm_synthesis_with_observations',
                }
                adjacents_updated += 1

        logger.info(
            "LLM synthesis: %d identity + %d narrative + %d adjacent fields updated for %s",
            sum(1 for f in _IDENTITY_FIELDS if result.get(f)),
            sum(1 for f in _NARRATIVE_FIELDS if result.get(f)),
            adjacents_updated,
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

    # --- 4.4  Merge projecte_extracted.json (lower priority than planol) ---
    # Multi-page architect project documents contain surfaces, height, floors
    # that SmartScan misses on single-page plans. Only fill missing values.
    projecte_path = project_path / 'validation' / 'projecte_extracted.json'
    if projecte_path.exists():
        try:
            projecte_data = json.loads(projecte_path.read_text(encoding='utf-8'))
            p_arch = projecte_data.get('architect_data', {})
            p_dims = projecte_data.get('dimensions', {})

            def _proj_dim_val(key: str):
                """Extract numeric value from projecte dimensions entry."""
                entry = p_dims.get(key, {})
                if isinstance(entry, dict):
                    return entry.get('value')
                return entry

            # building_type
            if not _get_val('building_type') and p_arch.get('building_type'):
                _set('building_type', p_arch['building_type'], 'projecte_arquitecte vision')

            # Eva's convention: when promotor and architect are different non-empty
            # entities, the architect_name in the report is often the promotor (who
            # acts as project director), NOT the document's literal "architect"
            # field. See _synthesize_with_llm few-shot example #4 (Linyola: SILVIA
            # EROLES = promotor, JOSEP BUNYESC = literal architect; Eva uses Sílvia).
            # Skip writing architect_name and client_name here; let the LLM
            # synthesis make the call using its few-shot rule. Bell-Lloc-style
            # cases (single architect, no separate promotor) still write through.
            promotor_val = (p_arch.get('promotor') or '').strip()
            architect_val = (p_arch.get('architect') or '').strip()
            distinct_promotor_architect = (
                promotor_val and architect_val
                and promotor_val.lower() != architect_val.lower()
            )

            # client_name
            if not _get_val('client_name') and not distinct_promotor_architect:
                cli = p_arch.get('client_name') or p_arch.get('promotor')
                if cli:
                    _set('client_name', cli, 'projecte_arquitecte vision')

            # architect_name
            if (
                not _get_val('architect_name')
                and p_arch.get('architect')
                and not distinct_promotor_architect
            ):
                _set('architect_name', p_arch['architect'], 'projecte_arquitecte vision')

            # municipality
            if not _get_val('site_municipality') and p_arch.get('municipality'):
                _set('site_municipality', p_arch['municipality'], 'projecte_arquitecte vision')

            # street_address
            if not _get_val('street_address') and p_arch.get('street_address'):
                _set('street_address', p_arch['street_address'], 'projecte_arquitecte vision')

            # num_floors
            if not _get_val('num_floors'):
                floors_val = _proj_dim_val('num_floors')
                if floors_val is not None:
                    from automation.formatting import format_floor_notation
                    _set('num_floors', format_floor_notation(str(floors_val)), 'projecte_arquitecte vision')

            # building_height_m
            if not _get_val('building_height_m'):
                height = _proj_dim_val('max_height_m')
                if height is not None:
                    _set('building_height_m', str(height), 'projecte_arquitecte vision')

            # superficie_construida_m2
            if not _get_val('superficie_construida_m2'):
                footprint = _proj_dim_val('building_footprint_m2')
                if footprint is not None:
                    _set('superficie_construida_m2', str(footprint), 'projecte_arquitecte vision')

            # superficie_parcela_m2
            if not _get_val('superficie_parcela_m2'):
                parcel = _proj_dim_val('parcel_area_m2')
                if parcel is not None:
                    _set('superficie_parcela_m2', str(parcel), 'projecte_arquitecte vision')

        except Exception as e:
            logger.warning("projecte_extracted merge failed: %s", e)


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

    vision_types = {'planol': 'planol_extracted.json', 'dpsh': 'dpsh_extracted.json', 'sondeig': 'sondeig_extracted.json', 'sondeig_annex': 'sondeig_annex_extracted.json', 'docs': 'docs_extracted.json', 'projecte_arquitecte': 'projecte_extracted.json'}
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

    # Terrain observation from field photos (for is_anthropized decision)
    if not merged.get('terrain_observation'):
        fm_path = project_path / 'file_mapping.json'
        fm_roles = {}
        if fm_path.exists():
            try:
                fm_roles = json.loads(fm_path.read_text()).get('roles', {})
            except Exception:
                pass
        obs = _observe_terrain_photos(project_path, fm_roles)
        if obs:
            merged['terrain_observation'] = {
                'value': obs,
                'source': 'vision (fotos camp)',
            }

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

    # Enrich with per-field confidence/missing_reason/expected_source_label
    # and build the top-level _missing_summary used by the HITL wizard drawer.
    _enrich_prefills_with_missing_summary(merged)

    _prefill_cache[project_name] = merged
    _auto_result_cache[project_name] = auto_result
    return merged


def _enrich_prefills_with_missing_summary(merged: dict[str, Any]) -> None:
    """Mutate `merged` in place:

    - For each concept entry: attach `confidence`, `missing_reason`,
      `expected_source_label` alongside the existing `value` and `source`.
    - Add a top-level `_missing_summary` key with fields grouped by expected
      source, used by the "Missing info" drawer in the wizard.

    Keys starting with `_` are system metadata and are skipped.
    """
    from web.expected_sources import CONFIDENCE_THRESHOLD, expected_source_for

    concept_map_entry = merged.get('_concept_map')
    concept_sources: dict[str, list[dict]] = {}
    if isinstance(concept_map_entry, dict):
        cm_val = concept_map_entry.get('value')
        if isinstance(cm_val, dict):
            concept_sources = cm_val

    groups: dict[str, dict[str, Any]] = {}

    for concept_id, entry in list(merged.items()):
        if concept_id.startswith('_'):
            continue
        if not isinstance(entry, dict):
            continue

        value = entry.get('value')
        has_value = value not in (None, '', [], {})

        # Confidence: max across concept_map sources for this concept (if any).
        cm_entries = concept_sources.get(concept_id) or []
        max_conf: float | None = None
        for src in cm_entries:
            if isinstance(src, dict):
                c = src.get('confidence')
                if isinstance(c, (int, float)):
                    c = max(0.0, min(1.0, float(c)))
                    if max_conf is None or c > max_conf:
                        max_conf = c
        entry['confidence'] = max_conf

        # Missing-reason classification.
        missing_reason: str | None = None
        if not has_value:
            missing_reason = 'file_had_no_match' if cm_entries else 'no_source_file'
        elif max_conf is not None and max_conf < CONFIDENCE_THRESHOLD:
            missing_reason = 'extracted_low_confidence'
        entry['missing_reason'] = missing_reason

        # Expected-source label (None if concept not in our curated map).
        hint = expected_source_for(concept_id)
        entry['expected_source_label'] = hint[0] if hint else None

        # Aggregate into groups if this is an incomplete/low-confidence field.
        if missing_reason is None:
            continue
        group_label = hint[0] if hint else 'Altres'
        role_hints = hint[1] if hint else []
        g = groups.setdefault(group_label, {
            'label': group_label,
            'role_hints': list(role_hints),
            'concept_ids': [],
            'reasons': {},
        })
        g['concept_ids'].append(concept_id)
        g['reasons'][concept_id] = missing_reason

    merged['_missing_summary'] = {
        'value': {
            'groups': list(groups.values()),
            'total_missing': sum(len(g['concept_ids']) for g in groups.values()),
            'total_groups': len(groups),
        },
        'source': 'system',
    }


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
        'projecte_arquitecte': 'projecte_extracted.json',
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
