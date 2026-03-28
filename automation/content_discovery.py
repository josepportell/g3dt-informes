#!/usr/bin/env python3
"""
Content Discovery for G3DT Report Generation (Fase 0.1)

Scans ALL unclassified files in a project folder by CONTENT (not filename)
to discover "hidden" data in unexpectedly-named files. G3DT naming is
inconsistent across projects, so we open files and check what's inside.

Scans:
  - All .txt files at any depth
  - All .xlsx/.xls not already classified as dpsh_excel
  - Files in the numeric subdirectory (XX.XXXX/ pattern)

Content classifiers (regex/pattern, no AI):
  - utm_coordinates: UTM X/Y/Z points
  - client_data: NIF/CIF + name/address
  - contact_info: phones, emails
  - field_prep: "DADES PER ANAR A CAMP" style Excel sheets
  - billing: invoice/budget amounts

Usage:
    from automation.content_discovery import discover_content

    result = discover_content('/path/to/project')
    print(result.summary())

    # Or from CLI:
    python -m automation.content_discovery "reference-material/4001612 BELL-LLOC"

Author: Eficients.cat
Date: 2026-02-25
"""

from __future__ import annotations

import json
import logging
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ['discover_content', 'ContentDiscoveryResult', 'DiscoveredItem']

# Files we never open (binary or system)
SKIP_EXTENSIONS = {
    '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff',
    '.fh11', '.doc', '.psd', '.ai',
    '.db', '.tmp',
}

# Our own outputs -- skip by exact name or pattern
OUR_OUTPUT_NAMES = {
    'file_mapping.json', 'user_data.json',
}

OUR_OUTPUT_PATTERNS = [
    re.compile(r'.*_generated\.docx$'),
    re.compile(r'^~\$'),
    re.compile(r'^Thumbs\.db$'),
]

# Numeric subdirectory pattern (e.g., "25.0647")
NUMERIC_SUBDIR_RE = re.compile(r'^\d+\.\d+$')

# Encoding fallback chain for text files
TEXT_ENCODINGS = ('utf-8', 'latin-1', 'cp1252')


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class DiscoveredItem:
    category: str       # utm_coordinates, client_data, contact_info, field_prep, billing
    source_file: str    # relative path from project root
    confidence: str     # high, medium, low
    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            'category': self.category,
            'source_file': self.source_file,
            'confidence': self.confidence,
            'data': self.data,
        }


@dataclass
class ContentDiscoveryResult:
    items: list[DiscoveredItem] = field(default_factory=list)
    files_scanned: int = 0
    files_skipped: int = 0
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """For JSON serialization into file_mapping.json."""
        return {
            'content_discovery': {
                'items': [item.to_dict() for item in self.items],
                'files_scanned': self.files_scanned,
                'files_skipped': self.files_skipped,
                'duration_seconds': round(self.duration_seconds, 2),
            },
        }

    def summary(self) -> str:
        """Human-readable summary in Catalan."""
        conf_map = {'high': 'alta', 'medium': 'mitjana', 'low': 'baixa'}
        lines = [
            '=' * 60,
            'Fase 0.1: Descoberta de contingut',
            '=' * 60,
        ]

        if not self.items:
            lines.append('  Cap contingut addicional descobert.')
        else:
            by_cat: dict[str, list[DiscoveredItem]] = {}
            for item in self.items:
                by_cat.setdefault(item.category, []).append(item)

            for cat, cat_items in by_cat.items():
                lines.append(f'  {cat} ({len(cat_items)}):')
                for item in cat_items:
                    conf = conf_map.get(item.confidence, item.confidence)
                    lines.append(
                        f'    - {item.source_file} ({conf} confianca)'
                    )

        lines.append('')
        lines.append(
            f'Fitxers escanejats: {self.files_scanned}, '
            f'omesos: {self.files_skipped}'
        )
        lines.append(f'Temps: {self.duration_seconds:.2f}s')
        lines.append('=' * 60)
        return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Content classifiers
# ---------------------------------------------------------------------------

# UTM ranges for Catalonia
_UTM_X_MIN, _UTM_X_MAX = 250_000, 550_000
_UTM_Y_MIN, _UTM_Y_MAX = 4_450_000, 4_750_000

# Pattern: numbers separated by ; or whitespace, optionally with labels
_UTM_LINE_RE = re.compile(
    r'(?:^|[;\s])\s*'
    r'(?:X\s*[:=]?\s*)?'
    r'(\d{5,6}(?:[.,]\d+)?)'
    r'\s*[;\s]+\s*'
    r'(?:Y\s*[:=]?\s*)?'
    r'(\d{6,7}(?:[.,]\d+)?)'
    r'(?:\s*[;\s]+\s*(?:Z\s*[:=]?\s*)?(\d{1,4}(?:[.,]\d+)?))?',
    re.IGNORECASE,
)

# Point ID pattern: P-1, S-1, P1, S1, DPSH-1, etc.
_POINT_ID_RE = re.compile(
    r'((?:P|S|DPSH|SPT)\s*-?\s*\d+)',
    re.IGNORECASE,
)

# NIF (personal): 8 digits + letter
_NIF_RE = re.compile(r'\b(\d{8}\s*[A-Z])\b')
# CIF (company): letter + 7 digits + alphanumeric
_CIF_RE = re.compile(r'\b([A-Z]\d{7}[A-Z0-9])\b')

# Phone patterns: 6XX XXX XXX or 9XX XXX XXX (with optional separators)
_PHONE_RE = re.compile(
    r'\b([69]\d{2}[\s.\-]?\d{3}[\s.\-]?\d{3})\b'
)

# Email pattern
_EMAIL_RE = re.compile(
    r'\b([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})\b'
)

# Field prep keywords: split into STRONG (distinctive) and WEAK (generic).
# Require at least 2 strong OR 1 strong + 2 weak to classify as field_prep.
_FIELD_PREP_STRONG = [
    'ADREÇA OBRA', 'PREVISIÓ DE TREBALL', 'TREBALL DE CAMP',
    'TRABAJO DE CAMPO', 'PERSONA DE CONTACTE', 'EDIFICACIÓ',
    'EDIFICACION', 'DESNIVELL', 'DESNIVEL', 'VEGETACIÓ', 'VEGETACION',
    'DADES PER ANAR A CAMP',
]
_FIELD_PREP_WEAK = [
    'CLIENT', 'CONTACTE', 'CONTACTO',
    'ADREÇA', 'DIRECCIÓ', 'DIRECCION',
    'ACCES', 'ACCÉS', 'ACCESO',
]
_FIELD_PREP_KEYWORDS = _FIELD_PREP_STRONG + _FIELD_PREP_WEAK

# Billing keywords
_BILLING_RE_AMOUNT = re.compile(
    r'(?:IMPORT\s+DE|TOTAL|BASE\s+IMPONIBLE|SUBTOTAL)\s*[:\s]*'
    r'(\d[\d.,]*)\s*(?:€|EUR)?',
    re.IGNORECASE,
)
_BILLING_KEYWORDS = re.compile(
    r'\b(?:VCT|DTO|FACTUR|PRESSUPOST|IMPORT\s+DE)\b',
    re.IGNORECASE,
)


def _classify_utm(text: str) -> dict[str, Any] | None:
    """Look for UTM coordinate pairs in text content."""
    points: dict[str, dict[str, float]] = {}
    lines = text.splitlines()

    for i, line in enumerate(lines):
        matches = list(_UTM_LINE_RE.finditer(line))
        for m in matches:
            raw_x = m.group(1).replace(',', '.')
            raw_y = m.group(2).replace(',', '.')
            try:
                x = float(raw_x)
                y = float(raw_y)
            except ValueError:
                continue

            if not (_UTM_X_MIN <= x <= _UTM_X_MAX and _UTM_Y_MIN <= y <= _UTM_Y_MAX):
                continue

            z = None
            if m.group(3):
                try:
                    z = float(m.group(3).replace(',', '.'))
                except ValueError:
                    pass

            # Try to find a point ID on the same line or previous line
            point_id = None
            for search_line in (line, lines[i - 1] if i > 0 else ''):
                id_match = _POINT_ID_RE.search(search_line)
                if id_match:
                    point_id = id_match.group(1).upper().replace(' ', '')
                    break

            if point_id is None:
                point_id = f'PT-{len(points) + 1}'

            point: dict[str, float] = {'x': x, 'y': y}
            if z is not None:
                point['z'] = z
            points[point_id] = point

    if not points:
        return None

    return {'points': points}


# Known NIFs/CIFs to exclude (G3DT's own company, subcontractors)
_KNOWN_INTERNAL_NIFS = {'B25364589'}  # G3 Desenvolupament Territorial SL


def _classify_client_data(text: str) -> dict[str, Any] | None:
    """Look for NIF/CIF and associated client info."""
    # Collect all NIF/CIF matches and filter out known internals
    nif_matches = [m.group(1).replace(' ', '') for m in _NIF_RE.finditer(text)]
    cif_matches = [m.group(1) for m in _CIF_RE.finditer(text)]
    all_ids = [n for n in nif_matches + cif_matches if n not in _KNOWN_INTERNAL_NIFS]

    if not all_ids:
        return None

    result: dict[str, Any] = {}
    result['nif'] = all_ids[0]

    # Look for name/address near the NIF/CIF
    # Simple heuristic: lines containing "CLIENT", "NOM", "PROMOTOR"
    lines = text.splitlines()
    for line in lines:
        upper = line.upper().strip()
        if any(kw in upper for kw in ('CLIENT', 'NOM', 'PROMOTOR', 'PROPIETARI')):
            # Value is typically after : or in next column
            parts = re.split(r'[:\t]', line, maxsplit=1)
            if len(parts) > 1 and parts[1].strip():
                candidate = parts[1].strip()
                # Sanity: name should look like a name (mostly letters/spaces),
                # not random cell values like "1.0\t1.6\tX\tNOMÉS SULFATS"
                alpha_ratio = sum(c.isalpha() or c == ' ' for c in candidate) / max(len(candidate), 1)
                if alpha_ratio > 0.6 and len(candidate) > 2:
                    result['name'] = candidate

        if any(kw in upper for kw in ('ADREÇA', 'DIRECCIÓ', 'DOMICILI', 'DIRECCION')):
            parts = re.split(r'[:\t]', line, maxsplit=1)
            if len(parts) > 1 and parts[1].strip():
                candidate = parts[1].strip()
                # Address should have some alphabetic content
                alpha_ratio = sum(c.isalpha() or c == ' ' for c in candidate) / max(len(candidate), 1)
                if alpha_ratio > 0.4 and len(candidate) > 3:
                    result['address'] = candidate

    # Check for phone/email near NIF
    phone = _PHONE_RE.search(text)
    if phone:
        result['phone'] = phone.group(1).replace(' ', '').replace('.', '').replace('-', '')

    email = _EMAIL_RE.search(text)
    if email:
        result['email'] = email.group(1)

    return result


def _classify_contact_info(text: str) -> dict[str, Any] | None:
    """Look for phone numbers and email addresses."""
    phones = list(set(_PHONE_RE.findall(text)))
    emails = list(set(_EMAIL_RE.findall(text)))

    if not phones and not emails:
        return None

    contacts: list[dict[str, str]] = []

    for phone in phones:
        clean = phone.replace(' ', '').replace('.', '').replace('-', '')
        contact: dict[str, str] = {'phone': clean}

        # Try to find a name near this phone number
        for line in text.splitlines():
            if phone in line:
                # Check for "CONTACTE:" or "PERSONA:" type labels
                for kw in ('CONTACTE', 'PERSONA', 'RESPONSABLE', 'TEL'):
                    if kw in line.upper():
                        parts = re.split(r'[:\t]', line, maxsplit=1)
                        if len(parts) > 1:
                            name_part = parts[1].strip()
                            # Remove the phone and tab-separated noise
                            name_part = name_part.replace(phone, '')
                            # Clean tabs and known noise words
                            name_part = re.sub(r'\t.*', '', name_part)
                            name_part = re.sub(
                                r'\b(?:TEL\.?|TELEFON|MAIL|WHATS)\b',
                                '', name_part, flags=re.IGNORECASE,
                            ).strip(' .-:,')
                            if name_part and len(name_part) > 2:
                                contact['name'] = name_part
                        break
        contacts.append(contact)

    for email in emails:
        # Only add if not already associated with a phone contact
        if not any(c.get('email') == email for c in contacts):
            contacts.append({'email': email})

    return {'contacts': contacts}


def _classify_field_prep_text(text: str) -> dict[str, Any] | None:
    """Detect field prep data in plain text."""
    upper = text.upper()
    result: dict[str, str] = {}
    n_strong = 0
    n_weak = 0

    for kw in _FIELD_PREP_KEYWORDS:
        if kw in upper:
            if kw in _FIELD_PREP_STRONG:
                n_strong += 1
            else:
                n_weak += 1
            # Try to extract value after the keyword
            for line in text.splitlines():
                if kw in line.upper():
                    parts = re.split(r'[:\t]', line, maxsplit=1)
                    if len(parts) > 1 and parts[1].strip():
                        result[kw] = parts[1].strip()
                    break

    # Need 2+ strong, or 1 strong + 2 weak
    if n_strong < 2 and not (n_strong >= 1 and n_weak >= 2):
        return None

    return result


def _classify_billing(text: str) -> dict[str, Any] | None:
    """Detect billing/invoice/budget data."""
    if not _BILLING_KEYWORDS.search(text):
        return None

    result: dict[str, str] = {}

    amount_match = _BILLING_RE_AMOUNT.search(text)
    if amount_match:
        result['amount'] = amount_match.group(1).replace(' ', '')
        result['currency'] = 'EUR'

    # Look for dates near billing keywords
    date_re = re.compile(r'\b(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})\b')
    dates = date_re.findall(text)
    if dates:
        result['date'] = dates[0]
        if len(dates) > 1:
            result['due_date'] = dates[-1]

    if not result:
        return None

    return result


# ---------------------------------------------------------------------------
# Excel content reading
# ---------------------------------------------------------------------------

def _read_excel_cells(file_path: Path) -> list[tuple[str, list[list[str]]]]:
    """
    Read all sheets from an Excel file, returning cell values as strings.

    Returns list of (sheet_name, rows) where rows is list of list of str.
    Each cell value is stripped and converted to str.
    """
    suffix = file_path.suffix.lower()
    sheets: list[tuple[str, list[list[str]]]] = []

    try:
        if suffix == '.xlsx':
            import openpyxl
            wb = openpyxl.load_workbook(str(file_path), read_only=True, data_only=True)
            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                rows: list[list[str]] = []
                for row in ws.iter_rows(values_only=True):
                    rows.append([
                        str(cell).strip() if cell is not None else ''
                        for cell in row
                    ])
                sheets.append((sheet_name, rows))
            wb.close()

        elif suffix == '.xls':
            import xlrd
            wb = xlrd.open_workbook(str(file_path))
            for sheet_idx in range(wb.nsheets):
                ws = wb.sheet_by_index(sheet_idx)
                rows = []
                for row_idx in range(ws.nrows):
                    rows.append([
                        str(ws.cell_value(row_idx, col_idx)).strip()
                        for col_idx in range(ws.ncols)
                    ])
                sheets.append((ws.name, rows))

    except Exception as exc:
        logger.debug(f"Could not read Excel {file_path}: {exc}")

    return sheets


def _excel_to_text(sheets: list[tuple[str, list[list[str]]]]) -> str:
    """Flatten Excel sheets into a single text string for text-based classifiers."""
    lines: list[str] = []
    for sheet_name, rows in sheets:
        lines.append(f'--- {sheet_name} ---')
        for row in rows:
            non_empty = [c for c in row if c]
            if non_empty:
                lines.append('\t'.join(non_empty))
    return '\n'.join(lines)


def _classify_field_prep_excel(
    sheets: list[tuple[str, list[list[str]]]],
) -> dict[str, Any] | None:
    """
    Detect field prep data in Excel by looking for keyword cells.

    Returns dict mapping found keywords to their adjacent cell values.
    """
    found: dict[str, str] = {}
    n_strong = 0
    n_weak = 0

    for _sheet_name, rows in sheets:
        for row in rows:
            for col_idx, cell in enumerate(row):
                cell_upper = cell.upper()
                for kw in _FIELD_PREP_KEYWORDS:
                    if kw in cell_upper:
                        if kw in _FIELD_PREP_STRONG:
                            n_strong += 1
                        else:
                            n_weak += 1
                        # Value is in the next non-empty cell in the same row
                        value = ''
                        for next_col in range(col_idx + 1, len(row)):
                            if row[next_col]:
                                value = row[next_col]
                                break
                        # Keep first occurrence — later sheets may have
                        # static lookup tables (e.g. "CLIENT" → "INTECSON")
                        if kw not in found:
                            found[kw] = value
                        break

    # Need 2+ strong, or 1 strong + 2 weak
    if n_strong < 2 and not (n_strong >= 1 and n_weak >= 2):
        return None

    return found


# ---------------------------------------------------------------------------
# File collection
# ---------------------------------------------------------------------------

def _is_our_output(name: str) -> bool:
    """Check if a file is one of our generated outputs."""
    if name in OUR_OUTPUT_NAMES:
        return True
    return any(p.match(name) for p in OUR_OUTPUT_PATTERNS)


def _get_classified_paths(file_mapping: Any) -> set[str]:
    """Extract all paths already classified by FileScanner."""
    paths: set[str] = set()
    if file_mapping is None:
        return paths

    if hasattr(file_mapping, 'roles'):
        for role in file_mapping.roles.values():
            paths.add(role.path)

    if hasattr(file_mapping, 'ignored'):
        for ignored in file_mapping.ignored:
            # ignored.path may have trailing / for directories
            paths.add(ignored.path.rstrip('/'))

    return paths


def _collect_files(
    project_path: Path,
    classified_paths: set[str],
) -> tuple[list[Path], int]:
    """
    Collect files to scan, returning (files_to_scan, files_skipped).

    Collects:
      - All .txt files at any depth
      - All .xlsx/.xls not classified as dpsh_excel
      - Files in numeric subdirectories (XX.XXXX/)
    """
    to_scan: list[Path] = []
    skipped = 0

    if not project_path.exists():
        return to_scan, skipped

    for file_path in sorted(project_path.rglob('*')):
        if not file_path.is_file():
            continue

        name = file_path.name
        suffix = file_path.suffix.lower()

        # Skip our outputs
        if _is_our_output(name):
            skipped += 1
            continue

        # Skip binary/unsupported
        if suffix in SKIP_EXTENSIONS:
            skipped += 1
            continue

        # Skip .msg (Outlook emails)
        if suffix == '.msg':
            skipped += 1
            continue

        # Relative path from project root
        try:
            rel_path = str(file_path.relative_to(project_path))
        except ValueError:
            skipped += 1
            continue

        # Skip already classified by FileScanner
        if rel_path in classified_paths:
            skipped += 1
            continue

        # Determine if this file qualifies for scanning
        should_scan = False

        # Rule 1: All .txt files
        if suffix == '.txt':
            should_scan = True

        # Rule 2: .xlsx/.xls not classified as dpsh_excel
        elif suffix in ('.xlsx', '.xls'):
            should_scan = True

        # Rule 3: Files in numeric subdirectory
        elif _is_in_numeric_subdir(rel_path):
            # Accept readable file types in numeric subdirs
            if suffix in ('.txt', '.xlsx', '.xls', '.csv'):
                should_scan = True

        if should_scan:
            to_scan.append(file_path)
        else:
            skipped += 1

    return to_scan, skipped


def _is_in_numeric_subdir(rel_path: str) -> bool:
    """Check if the file is inside a numeric subdirectory at the root level."""
    parts = rel_path.split('/')
    if len(parts) >= 2:
        return bool(NUMERIC_SUBDIR_RE.match(parts[0]))
    return False


# ---------------------------------------------------------------------------
# Text file reading
# ---------------------------------------------------------------------------

def _read_text_file(file_path: Path) -> str | None:
    """Read a text file with encoding fallbacks."""
    for enc in TEXT_ENCODINGS:
        try:
            return file_path.read_text(encoding=enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
        except OSError as exc:
            logger.debug(f"Could not read {file_path}: {exc}")
            return None
    return None


# ---------------------------------------------------------------------------
# Main classification dispatch
# ---------------------------------------------------------------------------

def _classify_text_content(
    text: str,
    rel_path: str,
) -> list[DiscoveredItem]:
    """Run all text-based classifiers on a text string."""
    items: list[DiscoveredItem] = []

    # UTM coordinates
    try:
        utm = _classify_utm(text)
        if utm:
            n_points = len(utm['points'])
            items.append(DiscoveredItem(
                category='utm_coordinates',
                source_file=rel_path,
                confidence='high' if n_points >= 1 else 'medium',
                data=utm,
            ))
    except Exception as exc:
        logger.debug(f"UTM classifier error on {rel_path}: {exc}")

    # Client data
    try:
        client = _classify_client_data(text)
        if client:
            has_nif = 'nif' in client
            has_name = 'name' in client
            conf = 'high' if (has_nif and has_name) else 'medium' if has_nif else 'low'
            items.append(DiscoveredItem(
                category='client_data',
                source_file=rel_path,
                confidence=conf,
                data=client,
            ))
    except Exception as exc:
        logger.debug(f"Client data classifier error on {rel_path}: {exc}")

    # Contact info
    try:
        contact = _classify_contact_info(text)
        if contact:
            items.append(DiscoveredItem(
                category='contact_info',
                source_file=rel_path,
                confidence='medium',
                data=contact,
            ))
    except Exception as exc:
        logger.debug(f"Contact info classifier error on {rel_path}: {exc}")

    # Field prep (text version)
    try:
        field_prep = _classify_field_prep_text(text)
        if field_prep:
            n_keys = len(field_prep)
            conf = 'high' if n_keys >= 5 else 'medium'
            items.append(DiscoveredItem(
                category='field_prep',
                source_file=rel_path,
                confidence=conf,
                data=field_prep,
            ))
    except Exception as exc:
        logger.debug(f"Field prep classifier error on {rel_path}: {exc}")

    # Billing
    try:
        billing = _classify_billing(text)
        if billing:
            has_amount = 'amount' in billing
            items.append(DiscoveredItem(
                category='billing',
                source_file=rel_path,
                confidence='high' if has_amount else 'low',
                data=billing,
            ))
    except Exception as exc:
        logger.debug(f"Billing classifier error on {rel_path}: {exc}")

    return items


def _classify_excel_file(
    file_path: Path,
    rel_path: str,
) -> list[DiscoveredItem]:
    """Run classifiers on an Excel file."""
    items: list[DiscoveredItem] = []

    sheets = _read_excel_cells(file_path)
    if not sheets:
        return items

    # Field prep (Excel-specific classifier)
    try:
        field_prep = _classify_field_prep_excel(sheets)
        if field_prep:
            n_keys = len(field_prep)
            conf = 'high' if n_keys >= 5 else 'medium'
            items.append(DiscoveredItem(
                category='field_prep',
                source_file=rel_path,
                confidence=conf,
                data=field_prep,
            ))
    except Exception as exc:
        logger.debug(f"Field prep Excel classifier error on {rel_path}: {exc}")

    # Also run text-based classifiers on flattened Excel content
    text = _excel_to_text(sheets)
    if text:
        text_items = _classify_text_content(text, rel_path)
        # Avoid duplicate field_prep if Excel classifier already found it
        has_field_prep = any(i.category == 'field_prep' for i in items)
        for item in text_items:
            if item.category == 'field_prep' and has_field_prep:
                continue
            items.append(item)

    return items


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def discover_content(
    project_path: str | Path,
    file_mapping: Any = None,
) -> ContentDiscoveryResult:
    """
    Scan unclassified files in a project folder by content.

    Args:
        project_path: Path to the project folder
        file_mapping: FileMapping from FileScanner, to skip classified files.
                      Accepts the FileMapping dataclass or None.

    Returns:
        ContentDiscoveryResult with discovered items and scan stats
    """
    t0 = time.monotonic()
    project_path = Path(project_path)
    result = ContentDiscoveryResult()

    classified_paths = _get_classified_paths(file_mapping)
    files, skipped = _collect_files(project_path, classified_paths)
    result.files_skipped = skipped

    for file_path in files:
        try:
            rel_path = str(file_path.relative_to(project_path))
        except ValueError:
            result.files_skipped += 1
            continue

        suffix = file_path.suffix.lower()
        result.files_scanned += 1

        try:
            if suffix in ('.xlsx', '.xls'):
                items = _classify_excel_file(file_path, rel_path)
            elif suffix == '.csv':
                text = _read_text_file(file_path)
                if text:
                    items = _classify_text_content(text, rel_path)
                else:
                    items = []
            else:
                # .txt and other text files
                text = _read_text_file(file_path)
                if text:
                    items = _classify_text_content(text, rel_path)
                else:
                    items = []

            result.items.extend(items)

        except Exception as exc:
            logger.warning(f"Error scanning {rel_path}: {exc}")

    result.duration_seconds = time.monotonic() - t0

    logger.info(
        f"Content discovery: {len(result.items)} items found in "
        f"{result.files_scanned} files ({result.duration_seconds:.2f}s)"
    )

    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI entry point for testing."""
    if len(sys.argv) < 2:
        print("Us: python -m automation.content_discovery <project_path>")
        sys.exit(1)

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    project_path = Path(sys.argv[1])

    # Optionally load FileMapping to skip classified files
    file_mapping = None
    try:
        from .file_scanner import FileScanner
        scanner = FileScanner(project_path)
        file_mapping = scanner.load()
        if file_mapping:
            print(f"FileMapping carregat: {len(file_mapping.roles)} rols")
    except Exception:
        pass

    print(f"Descoberta de contingut: {project_path}")
    print('=' * 60)

    result = discover_content(project_path, file_mapping=file_mapping)

    print('\n' + result.summary())

    if result.items:
        print('\nDetalls:')
        for item in result.items:
            print(f'\n  [{item.category}] {item.source_file} ({item.confidence})')
            data_str = json.dumps(item.data, indent=4, ensure_ascii=False)
            for line in data_str.splitlines():
                print(f'    {line}')


if __name__ == '__main__':
    main()
