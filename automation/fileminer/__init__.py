"""
FileMiner -- extract data signals from project files.

Phase 0.3 in the G3DT pipeline: runs after SmartScan, before auto_extractor.
SmartScan classifies files (what IS this?); FileMiner extracts data (what's IN it?).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .competition import resolve_competition
from .label_map import get_priority
from .miners import get_miners_for_file
from .models import MiningResult, ResolvedValue, Signal, SignalType

__all__ = [
    'mine_project',
    'resolve_competition',
    'MiningResult',
    'ResolvedValue',
    'Signal',
    'SignalType',
]

logger = logging.getLogger(__name__)

# Directories to skip when walking the project tree
_SKIP_DIRS = {
    'FOTOGRAFIES', 'PDF', 'PDF-V0', 'validation',
    '.git', '__pycache__', '.venv', 'node_modules',
}

# Extensions to skip entirely (images handled by vision pipeline, not FileMiner)
_SKIP_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.tif',
    '.fh11', '.psd', '.ai',
    '.db', '.tmp', '.msg',
}

# Our own generated outputs -- never mine these
_OUR_OUTPUTS = {
    'file_mapping.json', 'user_data.json',
}

# SmartScan role -> FileMiner source_type mapping
_ROLE_TO_SOURCE: dict[str, str] = {
    'dpsh_excel': 'dades_camp_excel',
    'lab_excel': 'comanda_lab_excel',
    'coordinates_txt': 'coordenades_txt',
    'pressupost_pdf': 'pressupost_pdf',
    'planol': 'planol_vision',
    'sondeig_field_sheet': 'sondeig_vision',
    'sondeig_annex': 'sondeig_vision',
    'penetros_pdf': 'dpsh_vision',
}

# Filename patterns -> source_type (fallback when no SmartScan role)
_FILENAME_HINTS: list[tuple[str, str]] = [
    ('DADES', 'dades_camp_excel'),
    ('PRESSUPOST', 'pressupost_pdf'),
    ('COMANDA', 'comanda_lab_excel'),
    ('COORDENADES', 'coordenades_txt'),
]

# Extension -> generic source_type fallback
_EXT_TO_SOURCE: dict[str, str] = {
    '.xls': 'content_excel',
    '.xlsx': 'content_excel',
    '.pdf': 'content_pdf',
    '.txt': 'content_text',
    '.doc': 'content_docx',
    '.docx': 'content_docx',
}


def _is_our_output(name: str) -> bool:
    """Check if a file is one of our generated outputs."""
    if name in _OUR_OUTPUTS:
        return True
    if name.endswith('_generated.docx'):
        return True
    if name.startswith('~$'):
        return True
    return False


def _resolve_source_type(
    file_path: Path,
    project_path: Path,
    file_mapping: dict[str, Any] | None,
) -> str:
    """Determine source_type for a file, using SmartScan roles + filename heuristics."""
    rel_path = str(file_path.relative_to(project_path))
    suffix = file_path.suffix.lower()

    # 1. Check SmartScan file_mapping roles
    if file_mapping and 'roles' in file_mapping:
        for role_name, role_info in file_mapping['roles'].items():
            role_path = role_info.get('path', '')
            if role_path == rel_path and role_name in _ROLE_TO_SOURCE:
                return _ROLE_TO_SOURCE[role_name]

    # 2. Filename pattern heuristics
    upper_name = file_path.stem.upper()
    for pattern, source_type in _FILENAME_HINTS:
        if pattern in upper_name:
            return source_type

    # 3. Extension-based fallback
    return _EXT_TO_SOURCE.get(suffix, 'content_text')


def mine_project(
    project_path: str | Path,
    *,
    file_mapping: dict[str, Any] | None = None,
    on_progress: Callable[[str, dict[str, Any]], None] | None = None,
) -> MiningResult:
    """Mine all project files for data signals.

    Args:
        project_path: Path to the project directory
        file_mapping: SmartScan result as dict (roles, unassigned, etc.)
        on_progress: Optional callback for progress updates

    Returns:
        MiningResult with all extracted signals
    """
    t0 = time.monotonic()
    project_path = Path(project_path)

    result = MiningResult(project_path=str(project_path))
    all_signals: list[Signal] = []

    if not project_path.is_dir():
        result.errors.append(f"Project path does not exist: {project_path}")
        result.duration_ms = int((time.monotonic() - t0) * 1000)
        return result

    # Collect files to mine
    files_to_mine: list[Path] = []
    for item in sorted(project_path.rglob('*')):
        if not item.is_file():
            continue

        # Skip files inside excluded directories
        rel_parts = item.relative_to(project_path).parts
        if any(part in _SKIP_DIRS for part in rel_parts[:-1]):
            result.files_skipped += 1
            continue

        # Skip by extension
        if item.suffix.lower() in _SKIP_EXTENSIONS:
            result.files_skipped += 1
            continue

        # Skip our own outputs
        if _is_our_output(item.name):
            result.files_skipped += 1
            continue

        files_to_mine.append(item)

    # Mine each file
    for file_path in files_to_mine:
        source_type = _resolve_source_type(file_path, project_path, file_mapping)
        priority = get_priority(source_type)

        miners = get_miners_for_file(file_path, project_path, source_type)
        if not miners:
            result.files_skipped += 1
            continue

        rel_path = str(file_path.relative_to(project_path))
        if on_progress:
            on_progress('mining_file', {'file': rel_path, 'source_type': source_type})

        mined_any = False
        for miner in miners:
            if not miner.can_mine(file_path):
                continue
            try:
                signals = miner.mine(file_path)
                # Apply source priority to all signals from this miner
                for sig in signals:
                    sig.priority = priority
                all_signals.extend(signals)
                mined_any = True
            except Exception as exc:
                error_msg = f"Error mining {rel_path} with {type(miner).__name__}: {exc}"
                logger.warning(error_msg)
                result.errors.append(error_msg)

        if mined_any:
            result.files_mined += 1
        else:
            result.files_skipped += 1

    result.signals = all_signals
    result.duration_ms = int((time.monotonic() - t0) * 1000)

    logger.info(
        f"FileMiner: {len(all_signals)} signals from {result.files_mined} files "
        f"({result.duration_ms}ms)"
    )

    return result
