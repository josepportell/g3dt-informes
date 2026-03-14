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

logger = logging.getLogger(__name__)

# Base dir for reference-material/ (relative to g3dt project root)
# Override with G3DT_PROJECTS_DIR env var or .env file
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

def _load_env() -> None:
    """Load .env from project root if it exists (no external dependencies)."""
    env_path = _PROJECT_ROOT / '.env'
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' in line:
            key, _, value = line.partition('=')
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)

_load_env()
_REF_DIR = Path(os.getenv('G3DT_PROJECTS_DIR', str(_PROJECT_ROOT / 'reference-material')))

# Production path where Eva keeps signed reference reports
_INFORMES_DIR = Path('/mnt/c/claude/g3dt/4-informes')

# In-memory prefill cache: project_name -> prefills dict
_prefill_cache: dict[str, dict[str, Any]] = {}

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


def get_prefills(project_name: str, *, force_refresh: bool = False) -> dict[str, Any]:
    """Run auto_extract + vision + wizard prefill chain for a project.

    Returns a dict of {field: {value, source, confidence?}} entries.
    Results are cached per project_name; pass force_refresh=True to re-run.
    """
    if not force_refresh and project_name in _prefill_cache:
        return _prefill_cache[project_name]

    project_path = _resolve_project(project_name)

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

    vision_types = {'planol': 'planol_extracted.json', 'dpsh': 'dpsh_extracted.json', 'sondeig': 'sondeig_extracted.json', 'docs': 'docs_extracted.json'}
    vision_status = {}
    for vt, filename in vision_types.items():
        vision_status[vt] = (project_path / 'validation' / filename).exists()
    merged['_vision_status'] = {'value': vision_status, 'source': 'system'}

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

    _prefill_cache[project_name] = merged
    return merged


def get_prefills_streaming(project_name: str):
    """Generator yielding SSE events during auto_extract, then final prefills."""
    project_path = _resolve_project(project_name)

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


def _run_vision_phase(project_path: Path, force_refresh: bool) -> None:
    """Run Claude vision extraction (Phase 1) via Anthropic SDK. Non-fatal on failure.

    In the native Claude Code path, vision JSONs are pre-created by
    /g3dt-visio-projecte. This function only fills in missing JSONs via the SDK
    (if available). It should NEVER be called with force_refresh=True from the
    web wizard — that would hang without an API key.

    NOTE: SDK path disabled until G3DT provides their own API key.
    Vision runs exclusively via Claude Code CLI (/g3dt-visio-projecte).
    """
    # TODO: re-enable when G3DT has their own Anthropic API key
    # try:
    #     from automation.vision_extractor import run_vision_extraction
    #     run_vision_extraction(project_path, force_refresh=force_refresh)
    # except ImportError:
    #     logger.warning("Vision extraction not available (anthropic not installed)")
    # except Exception as e:
    #     logger.warning("Vision extraction failed (SDK): %s", e)
    pass


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
