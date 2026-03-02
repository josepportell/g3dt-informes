"""
Service layer bridging automation modules to the web API.

All business logic lives here; api.py is a thin HTTP wrapper.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Base dir for reference-material/ (relative to g3dt project root)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_REF_DIR = _PROJECT_ROOT / 'reference-material'

# In-memory prefill cache: project_name -> prefills dict
_prefill_cache: dict[str, dict[str, Any]] = {}


def _resolve_project(project_name: str) -> Path:
    """Resolve a project name to its folder path. Raises ValueError if not found."""
    candidate = _REF_DIR / project_name
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


def get_prefills(project_name: str, *, force_refresh: bool = False) -> dict[str, Any]:
    """Run auto_extract + wizard prefill chain for a project.

    Returns a dict of {field: {value, source, confidence?}} entries.
    Results are cached per project_name; pass force_refresh=True to re-run.
    """
    if not force_refresh and project_name in _prefill_cache:
        return _prefill_cache[project_name]

    project_path = _resolve_project(project_name)

    # Phase 1: auto_extract (DPSH, lab, ICGC, cadastre)
    from automation.auto_extractor import auto_extract
    auto_result = auto_extract(project_path)

    # Phase 2: wizard prefill chain (defaults, sondeig, planol, adjacents_visor, user_data)
    from automation.wizard import UserDataWizard
    wizard = UserDataWizard(str(project_path))
    wizard.load_prefills()

    # Merge: wizard prefills take priority, auto_extract fills gaps
    merged: dict[str, Any] = {}

    # Add auto_extract prefills as {value, source}
    for key, value in auto_result.prefills.items():
        source = auto_result.sources.get(key, 'auto')
        merged[key] = {'value': value, 'source': source}

    # Overlay wizard prefills (higher priority)
    for key, entry in wizard.prefills.items():
        merged[key] = entry

    _prefill_cache[project_name] = merged
    return merged


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

    from automation.wizard import save_wizard_data
    result = save_wizard_data(project_path, wizard_fields, expert_overrides)
    _prefill_cache.pop(project_name, None)
    return result


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

    # Get municipality from folder name
    from automation.folder_utils import parse_folder_name
    _, municipality = parse_folder_name(project_path.name)
    if not municipality:
        raise ValueError("No s'ha pogut extreure el municipi del nom de carpeta")

    # Resolve address: parameter > user_data > adjacent_south
    if not address:
        ud = load_user_data(project_name)
        address = (
            ud.get('street_address')
            or ud.get('site_address')
            or ud.get('adjacent_south')
        )
    if not address:
        raise ValueError(
            "Cal una adreça per geocodificar. "
            "Introdueix-la al camp 'adjacent_south' o passa-la com a paràmetre."
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

    # Run geocoding
    from automation.geocode_coordinates import geocode_project, GeocodeError
    try:
        result = geocode_project(address, municipality, point_ids, output_dir=project_path)
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
