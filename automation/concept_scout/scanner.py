"""Enumerate ALL files in a project tree for concept discovery."""

from __future__ import annotations

import logging
from pathlib import Path

from .models import FileEntry

logger = logging.getLogger(__name__)

# Directories to skip
_SKIP_DIRS = {'.git', '__pycache__', 'validation', 'node_modules', '.venv'}

# Our generated outputs — never scan these
_OUR_OUTPUTS = {'file_mapping.json', 'user_data.json'}

# Extensions to skip entirely (unreadable binary design files)
_SKIP_EXTENSIONS = {'.fh11', '.psd', '.ai'}

# Windows cache files
_WINDOWS_CACHE = {'Thumbs.db'}

# Image extensions
_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif'}


def _is_our_output(name: str) -> bool:
    """Check if a file is one of our generated outputs."""
    if name in _OUR_OUTPUTS:
        return True
    if name.endswith('_generated.docx'):
        return True
    if name.startswith('~$'):
        return True
    return False


def _classify_pdf(file_path: Path) -> str:
    """Classify a PDF as vector or scanned using PyMuPDF text extraction."""
    try:
        import fitz
        doc = fitz.open(str(file_path))
        if doc.page_count > 0:
            text = doc[0].get_text().strip()
            doc.close()
            return "pdf_vector" if len(text) > 50 else "pdf_scanned"
        doc.close()
    except Exception:
        pass
    return "pdf_scanned"


def enumerate_project_files(project_path: Path) -> list[FileEntry]:
    """Walk the project tree and return a FileEntry for every relevant file.

    Unlike FileMiner (which skips PDF/, FOTOGRAFIES, images), ConceptScout
    scans everything to build a complete inventory.
    """
    entries: list[FileEntry] = []

    for item in sorted(project_path.rglob('*')):
        if not item.is_file():
            continue

        # Skip files inside excluded directories
        # Exception: validation/msg_attachments/ — contains .msg extracted files
        rel_parts = item.relative_to(project_path).parts
        if any(part in _SKIP_DIRS for part in rel_parts[:-1]):
            if not (len(rel_parts) >= 3 and rel_parts[0] == 'validation' and rel_parts[1] == 'msg_attachments'):
                continue

        name = item.name
        suffix = item.suffix.lower()

        # Skip unreadable binary design files
        if suffix in _SKIP_EXTENSIONS:
            continue

        # Skip our generated outputs
        if _is_our_output(name):
            continue

        # Skip Windows cache and temp files
        if name in _WINDOWS_CACHE or suffix == '.tmp':
            continue

        rel_path = str(item.relative_to(project_path))
        size_kb = item.stat().st_size // 1024

        # Classify file type
        if suffix == '.pdf':
            file_type = _classify_pdf(item)
            text_extractable = file_type == "pdf_vector"
        elif suffix in ('.xls', '.xlsx'):
            file_type = "excel"
            text_extractable = True
        elif suffix in _IMAGE_EXTENSIONS:
            file_type = "image"
            text_extractable = False
        elif suffix in ('.txt', '.csv'):
            file_type = "text"
            text_extractable = True
        elif suffix == '.msg':
            file_type = "email"
            text_extractable = True
        elif suffix in ('.doc', '.docx'):
            file_type = "docx"
            text_extractable = True
        else:
            file_type = "other"
            text_extractable = True

        entries.append(FileEntry(
            path=rel_path,
            type=file_type,
            size_kb=size_kb,
            text_extractable=text_extractable,
        ))

    logger.info("ConceptScout scanner: %d files in %s", len(entries), project_path.name)
    return entries
