"""
FileMiner -- extract data signals from project files.

Phase 0.3 in the G3DT pipeline: runs after SmartScan, before auto_extractor.
SmartScan classifies files (what IS this?); FileMiner extracts data (what's IN it?).
"""

from __future__ import annotations

import logging
import re
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
    'mine_project_groq',
    'resolve_competition',
    'MiningResult',
    'ResolvedValue',
    'Signal',
    'SignalType',
]

logger = logging.getLogger(__name__)

# Directories to skip when walking the project tree
# Note: FOTOGRAFIES removed — FileMiner walks it but naturally skips images
# (image extensions are in _SKIP_EXTENSIONS). Text files there get mined.
_SKIP_DIRS = {
    'PDF', 'PDF-V0', 'PDF_V0', 'validation',
    '.git', '__pycache__', '.venv', 'node_modules',
}

# Extensions to skip entirely (images handled by vision pipeline, not FileMiner)
# Note: .msg removed — MsgMiner now processes email files
_SKIP_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.tif',
    '.fh11', '.psd', '.ai',
    '.db', '.tmp',
}

# Our own generated outputs -- never mine these
_OUR_OUTPUTS = {
    'file_mapping.json', 'user_data.json',
}

# Reference report patterns to skip (Eva's existing reports, used for comparison only)
_SKIP_FILENAME_PATTERNS = [
    re.compile(r'^\d+_informe.*\.docx?$', re.IGNORECASE),
    re.compile(r'^\d+_portada.*\.docx?$', re.IGNORECASE),
    re.compile(r'.*_test_.*\.docx?$', re.IGNORECASE),
    re.compile(r'.*_generated.*\.docx?$', re.IGNORECASE),
    re.compile(r'.*_AUDIT_VISUAL\.docx?$', re.IGNORECASE),
]

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
    '.msg': 'content_email',
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

    # 1b. Check role_files for multi-file roles
    if file_mapping and 'role_files' in file_mapping:
        for role_name, role_entries in file_mapping['role_files'].items():
            if role_name in _ROLE_TO_SOURCE:
                for entry in role_entries:
                    if entry.get('path', '') == rel_path:
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

        # Skip reference report files
        if any(pat.match(item.name) for pat in _SKIP_FILENAME_PATTERNS):
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
                # Apply source priority and source_type to all signals from this miner
                for sig in signals:
                    sig.priority = priority
                    sig.source_type = source_type
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

    # Second pass: mine files extracted from .msg attachments
    # (validation/msg_attachments/ is inside _SKIP_DIRS so the main walk misses them)
    abs_project = project_path.resolve()
    processed_paths: set[Path] = {f.resolve() for f in files_to_mine}
    att_count = 0
    for sig in list(all_signals):
        if sig.label != 'msg_attachment':
            continue
        att_path = Path(sig.value).resolve()
        if not att_path.is_file():
            continue
        if att_path.suffix.lower() in _SKIP_EXTENSIONS:
            continue
        if att_path.suffix.lower() == '.msg':
            continue
        if att_path in processed_paths:
            continue
        if _is_our_output(att_path.name):
            continue
        processed_paths.add(att_path)

        source_type = _resolve_source_type(att_path, abs_project, file_mapping)
        priority = get_priority(source_type)
        miners = get_miners_for_file(att_path, abs_project, source_type)
        if not miners:
            continue

        try:
            rel_path = str(att_path.relative_to(abs_project))
        except ValueError:
            continue
        if on_progress:
            on_progress('mining_file', {'file': rel_path, 'source_type': source_type})

        mined_any = False
        for miner in miners:
            if not miner.can_mine(att_path):
                continue
            try:
                signals = miner.mine(att_path)
                for s in signals:
                    s.priority = priority
                    s.source_type = source_type
                all_signals.extend(signals)
                mined_any = True
            except Exception as exc:
                error_msg = f"Error mining {rel_path} with {type(miner).__name__}: {exc}"
                logger.warning(error_msg)
                result.errors.append(error_msg)

        if mined_any:
            result.files_mined += 1
            att_count += 1

    if att_count:
        logger.info("FileMiner: %d msg attachments re-processed", att_count)

    result.signals = all_signals
    result.duration_ms = int((time.monotonic() - t0) * 1000)

    logger.info(
        f"FileMiner: {len(all_signals)} signals from {result.files_mined} files "
        f"({result.duration_ms}ms)"
    )

    return result


# Source types that should never be sent to Groq (already handled by vision/dedicated extractors)
_GROQ_SKIP_SOURCES = {
    'dades_camp_excel', 'coordenades_txt',
    'dpsh_vision', 'sondeig_vision', 'planol_vision',
}


def _count_mapped_signals(
    signals: list[Signal],
    rel_path: str,
) -> int:
    """Count how many signals from a file have maps_to set."""
    return sum(
        1 for s in signals
        if s.source_file == rel_path and s.maps_to is not None
    )


def mine_project_groq(
    project_path: str | Path,
    *,
    file_mapping: dict[str, Any] | None = None,
    missing_variables: list[str] | None = None,
    existing_signals: list[Signal] | None = None,
) -> list[Signal]:
    """Run Groq LLM miner on files where Python miners underperformed.

    Identifies files with <3 mapped signals from the Python miners and sends
    them to Groq for deeper extraction, focusing on still-missing variables.

    Args:
        project_path: Path to the project directory
        file_mapping: SmartScan result as dict
        missing_variables: List of variable names still unfilled
        existing_signals: Signals from the Python mining phase

    Returns:
        List of new Signal objects from Groq extraction
    """
    import os

    project_path = Path(project_path)
    existing_signals = existing_signals or []

    if os.environ.get("G3DT_USE_GROQ", "1").strip() != "1":
        logger.debug("mine_project_groq: disabled (G3DT_USE_GROQ != 1)")
        return []
    if not os.environ.get("GROQ_API_KEY"):
        logger.debug("mine_project_groq: disabled (GROQ_API_KEY not set)")
        return []

    from .miners.groq_miner import GroqMiner

    miner = GroqMiner(
        project_path,
        source_type="groq_llm",
        missing_variables=missing_variables,
    )

    # Build set of files and their source types
    file_source_types: dict[str, str] = {}
    for item in sorted(project_path.rglob('*')):
        if not item.is_file():
            continue
        rel_parts = item.relative_to(project_path).parts
        if any(part in _SKIP_DIRS for part in rel_parts[:-1]):
            continue
        if item.suffix.lower() in _SKIP_EXTENSIONS:
            continue
        if _is_our_output(item.name):
            continue
        if any(pat.match(item.name) for pat in _SKIP_FILENAME_PATTERNS):
            continue
        rel_path = str(item.relative_to(project_path))
        source_type = _resolve_source_type(item, project_path, file_mapping)
        file_source_types[rel_path] = source_type

    # Include files extracted from .msg attachments (validation/msg_attachments/ is in _SKIP_DIRS)
    msg_att_dir = project_path / 'validation' / 'msg_attachments'
    if msg_att_dir.is_dir():
        for item in sorted(msg_att_dir.rglob('*')):
            if not item.is_file():
                continue
            if item.suffix.lower() in _SKIP_EXTENSIONS:
                continue
            if item.suffix.lower() == '.msg':
                continue
            if _is_our_output(item.name):
                continue
            if any(pat.match(item.name) for pat in _SKIP_FILENAME_PATTERNS):
                continue
            rel_path = str(item.relative_to(project_path))
            source_type = _resolve_source_type(item, project_path, file_mapping)
            file_source_types[rel_path] = source_type

    # Select candidate files
    new_signals: list[Signal] = []
    files_sent = 0

    for rel_path, source_type in file_source_types.items():
        file_path = project_path / rel_path

        # Skip files handled by dedicated extractors
        if source_type in _GROQ_SKIP_SOURCES:
            logger.debug(
                "Groq: skipping %s (source_type=%s, handled by dedicated extractor)",
                rel_path, source_type,
            )
            continue

        # Count how many mapped signals Python miners found for this file
        n_mapped = _count_mapped_signals(existing_signals, rel_path)

        # Threshold: skip files with enough signals UNLESS missing_variables
        # suggests this file type might fill important gaps.
        # Default threshold: 3 signals. But if we still have critical missing
        # variables AND this file's source_type could produce them, lower to 1.
        threshold = 3
        if missing_variables and n_mapped >= 1:
            # High-value source types that often contain unique data:
            # emails may have addresses, pressupost has architect info
            high_value_sources = {'content_email', 'pressupost_pdf', 'dades_camp_excel'}
            if source_type in high_value_sources:
                threshold = 5  # Be more generous with high-value sources

        if n_mapped >= threshold:
            logger.debug(
                "Groq: skipping %s (source_type=%s, python_signals=%d >= %d)",
                rel_path, source_type, n_mapped, threshold,
            )
            continue

        # Check if miner can handle this file type
        if not miner.can_mine(file_path):
            continue

        logger.info(
            "Groq: will mine %s (source_type=%s, python_signals=%d, missing=%s)",
            rel_path, source_type, n_mapped,
            missing_variables[:5] if missing_variables else "all",
        )

        try:
            signals = miner.mine(file_path)
            new_signals.extend(signals)
            files_sent += 1
        except Exception as exc:
            logger.warning("Groq: error mining %s: %s", rel_path, exc)

    logger.info(
        "mine_project_groq: %d new signals from %d files",
        len(new_signals), files_sent,
    )

    try:
        usage = GroqMiner.get_usage_summary()
        logger.info(
            "Groq usage: %d calls, %d cache hits, %d+%d tokens, est. $%.4f (%s)",
            usage["api_calls"], usage["cache_hits"],
            usage["input_tokens"], usage["output_tokens"],
            usage["estimated_cost_usd"], usage["model"],
        )
    except Exception:
        pass

    return new_signals
