"""Shared detection functions for text-based miners.

Ports regex patterns from content_discovery.py into Signal-producing functions.
All text-based miners (text, pdf_text, docx) import from here.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from ..label_map import LABEL_TO_VARIABLE
from ..models import Signal, SignalType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns (ported from content_discovery.py)
# ---------------------------------------------------------------------------

# UTM ranges for Catalonia
_UTM_X_MIN, _UTM_X_MAX = 250_000, 550_000
_UTM_Y_MIN, _UTM_Y_MAX = 4_450_000, 4_750_000

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

_POINT_ID_RE = re.compile(
    r'((?:P|S|DPSH|SPT)\s*-?\s*\d+)',
    re.IGNORECASE,
)

# NIF (personal): 8 digits + letter
_NIF_RE = re.compile(r'\b(\d{8}\s*[A-Z])\b')
# CIF (company): letter + 7 digits + alphanumeric
_CIF_RE = re.compile(r'\b([A-Z]\d{7}[A-Z0-9])\b')

# Phone patterns: 6XX XXX XXX or 9XX XXX XXX
_PHONE_RE = re.compile(r'\b([69]\d{2}[\s.\-]?\d{3}[\s.\-]?\d{3})\b')

# Email pattern
_EMAIL_RE = re.compile(
    r'\b([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})\b'
)

# URL pattern (Google Maps links, etc.)
_URL_RE = re.compile(
    r'(https?://[^\s<>"\']+)',
    re.IGNORECASE,
)

# Billing keywords (ported from content_discovery.py)
_BILLING_RE_AMOUNT = re.compile(
    r'(?:IMPORT\s+DE|TOTAL|BASE\s+IMPONIBLE|SUBTOTAL)\s*[:\s]*'
    r'(\d[\d.,]*)\s*(?:\u20ac|EUR)?',
    re.IGNORECASE,
)
_BILLING_KEYWORDS = re.compile(
    r'\b(?:VCT|DTO|FACTUR|PRESSUPOST|IMPORT\s+DE)\b',
    re.IGNORECASE,
)

# Known internal NIFs/CIFs to exclude
_KNOWN_INTERNAL_NIFS = {'B25364589'}  # G3 Desenvolupament Territorial SL

# Label-value line patterns
_LABEL_VALUE_COLON_RE = re.compile(r'^([^:]{2,40}):\s*(.+)$')
_LABEL_VALUE_TAB_RE = re.compile(r'^([^\t]{2,40})\t+(.+)$')


# ---------------------------------------------------------------------------
# Detection functions -- each returns list[Signal]
# ---------------------------------------------------------------------------

def detect_utm_points(
    text: str,
    source_file: str,
    confidence: float = 0.95,
) -> list[Signal]:
    """Detect UTM coordinate points in text. Each point becomes a Signal."""
    signals: list[Signal] = []
    lines = text.splitlines()

    seen_points: dict[str, dict[str, float]] = {}

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

            z: float | None = None
            if m.group(3):
                try:
                    z = float(m.group(3).replace(',', '.'))
                except ValueError:
                    pass

            # Find point ID on same line or previous line
            point_id: str | None = None
            for search_line in (line, lines[i - 1] if i > 0 else ''):
                id_match = _POINT_ID_RE.search(search_line)
                if id_match:
                    point_id = id_match.group(1).upper().replace(' ', '')
                    break

            if point_id is None:
                point_id = f'PT-{len(seen_points) + 1}'

            point_value: dict[str, float | str] = {
                'point_id': point_id,
                'x': x,
                'y': y,
            }
            if z is not None:
                point_value['z'] = z

            if point_id in seen_points:
                continue
            seen_points[point_id] = point_value

            signals.append(Signal(
                type=SignalType.COORDS,
                label=f'UTM {point_id}',
                value=point_value,
                raw_value=line.strip(),
                maps_to='utm_coordinates',
                source_file=source_file,
                source_location=f'line {i + 1}',
                extraction_method='regex',
                confidence=confidence,
            ))

    return signals


def detect_nif_cif(
    text: str,
    source_file: str,
    confidence: float = 0.85,
) -> list[Signal]:
    """Detect NIF/CIF identifiers and surrounding client data."""
    signals: list[Signal] = []

    nif_matches = [m.group(1).replace(' ', '') for m in _NIF_RE.finditer(text)]
    cif_matches = [m.group(1) for m in _CIF_RE.finditer(text)]
    all_ids = [n for n in nif_matches + cif_matches if n not in _KNOWN_INTERNAL_NIFS]

    if not all_ids:
        return signals

    # Emit signal for each unique NIF/CIF found
    seen_ids: set[str] = set()
    for nif_value in all_ids:
        if nif_value in seen_ids:
            continue
        seen_ids.add(nif_value)
        signals.append(Signal(
            type=SignalType.TEXT,
            label='NIF/CIF',
            value=nif_value,
            raw_value=nif_value,
            maps_to='client_nif',
            source_file=source_file,
            extraction_method='regex',
            confidence=confidence,
        ))

    # Look for client name near the NIF
    lines = text.splitlines()
    for line in lines:
        upper = line.upper().strip()
        if any(kw in upper for kw in ('CLIENT', 'NOM', 'PROMOTOR', 'PROPIETARI')):
            parts = re.split(r'[:\t]', line, maxsplit=1)
            if len(parts) > 1 and parts[1].strip():
                candidate = parts[1].strip()
                alpha_ratio = sum(
                    c.isalpha() or c == ' ' for c in candidate
                ) / max(len(candidate), 1)
                if alpha_ratio > 0.6 and len(candidate) > 2:
                    signals.append(Signal(
                        type=SignalType.TEXT,
                        label='Client name',
                        value=candidate,
                        raw_value=candidate,
                        maps_to='client_name',
                        source_file=source_file,
                        extraction_method='regex',
                        confidence=confidence,
                    ))
                    break

    # Look for address near the NIF
    for line in lines:
        upper = line.upper().strip()
        if any(kw in upper for kw in ('ADRE\u00c7A', 'DIRECCI\u00d3', 'DOMICILI', 'DIRECCION')):
            parts = re.split(r'[:\t]', line, maxsplit=1)
            if len(parts) > 1 and parts[1].strip():
                candidate = parts[1].strip()
                alpha_ratio = sum(
                    c.isalpha() or c == ' ' for c in candidate
                ) / max(len(candidate), 1)
                if alpha_ratio > 0.4 and len(candidate) > 3:
                    signals.append(Signal(
                        type=SignalType.TEXT,
                        label='Street address',
                        value=candidate,
                        raw_value=candidate,
                        maps_to='street_address',
                        source_file=source_file,
                        extraction_method='regex',
                        confidence=confidence,
                    ))
                    break

    return signals


def detect_phones(
    text: str,
    source_file: str,
    confidence: float = 0.80,
) -> list[Signal]:
    """Detect phone numbers."""
    signals: list[Signal] = []
    seen: set[str] = set()

    for m in _PHONE_RE.finditer(text):
        raw = m.group(1)
        clean = raw.replace(' ', '').replace('.', '').replace('-', '')
        if clean in seen:
            continue
        seen.add(clean)

        signals.append(Signal(
            type=SignalType.TEXT,
            label='Phone',
            value=clean,
            raw_value=raw,
            maps_to='client_phone',
            source_file=source_file,
            extraction_method='regex',
            confidence=confidence,
        ))

    return signals


def detect_emails(
    text: str,
    source_file: str,
    confidence: float = 0.80,
) -> list[Signal]:
    """Detect email addresses."""
    signals: list[Signal] = []
    seen: set[str] = set()

    for m in _EMAIL_RE.finditer(text):
        email = m.group(1).lower()
        if email in seen:
            continue
        seen.add(email)

        signals.append(Signal(
            type=SignalType.TEXT,
            label='Email',
            value=email,
            raw_value=m.group(1),
            maps_to='client_email',
            source_file=source_file,
            extraction_method='regex',
            confidence=confidence,
        ))

    return signals


def detect_urls(
    text: str,
    source_file: str,
    confidence: float = 0.80,
) -> list[Signal]:
    """Detect URLs (Google Maps links, etc.)."""
    signals: list[Signal] = []
    seen: set[str] = set()

    for m in _URL_RE.finditer(text):
        url = m.group(1).rstrip('.,;)')
        if url in seen:
            continue
        seen.add(url)

        maps_to = 'access_url' if 'maps' in url.lower() or 'google' in url.lower() else None

        signals.append(Signal(
            type=SignalType.URL,
            label='URL',
            value=url,
            raw_value=url,
            maps_to=maps_to,
            source_file=source_file,
            extraction_method='regex',
            confidence=confidence,
        ))

    return signals


def detect_label_values(
    text: str,
    source_file: str,
    confidence: float = 0.85,
) -> list[Signal]:
    """Detect LABEL: VALUE or LABEL\\tVALUE patterns matching LABEL_TO_VARIABLE."""
    signals: list[Signal] = []
    seen_variables: set[str] = set()

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or len(stripped) < 3:
            continue

        label: str | None = None
        value: str | None = None

        # Try colon separator first
        m = _LABEL_VALUE_COLON_RE.match(stripped)
        if m:
            label = m.group(1).strip()
            value = m.group(2).strip()
        else:
            # Try tab separator
            m = _LABEL_VALUE_TAB_RE.match(stripped)
            if m:
                label = m.group(1).strip()
                value = m.group(2).strip()

        if not label or not value:
            continue

        # Lookup in LABEL_TO_VARIABLE
        variable = LABEL_TO_VARIABLE.get(label.upper())
        if variable is None:
            continue

        # Only keep first match per variable (highest in file = most prominent)
        if variable in seen_variables:
            continue
        seen_variables.add(variable)

        sig_type = SignalType.TEXT
        if variable == 'utm_coordinates':
            sig_type = SignalType.COORDS

        signals.append(Signal(
            type=sig_type,
            label=label,
            value=value,
            raw_value=stripped,
            maps_to=variable,
            source_file=source_file,
            extraction_method='label_value',
            confidence=confidence,
        ))

    return signals


def detect_billing(
    text: str,
    source_file: str,
    confidence: float = 0.80,
) -> list[Signal]:
    """Detect billing/invoice/budget data."""
    if not _BILLING_KEYWORDS.search(text):
        return []

    signals: list[Signal] = []

    amount_match = _BILLING_RE_AMOUNT.search(text)
    if amount_match:
        raw_amount = amount_match.group(1).replace(' ', '')
        signals.append(Signal(
            type=SignalType.NUMERIC,
            label='Billing amount',
            value=raw_amount,
            raw_value=amount_match.group(0).strip(),
            maps_to=None,
            source_file=source_file,
            extraction_method='regex',
            confidence=confidence,
        ))

    return signals


def run_all_detectors(
    text: str,
    source_file: str,
    confidence_offset: float = 0.0,
    *,
    include_billing: bool = False,
) -> list[Signal]:
    """Run all detection functions on a text blob.

    Args:
        text: The text content to analyze
        source_file: Relative path for signal provenance
        confidence_offset: Added to base confidence (use -0.05 for noisier sources)
        include_billing: Whether to run billing detection (PDF only)

    Returns:
        Combined list of all detected signals
    """
    if not text or not text.strip():
        return []

    def adj(base: float) -> float:
        return max(0.0, min(1.0, base + confidence_offset))

    signals: list[Signal] = []
    signals.extend(detect_utm_points(text, source_file, confidence=adj(0.95)))
    signals.extend(detect_nif_cif(text, source_file, confidence=adj(0.85)))
    signals.extend(detect_phones(text, source_file, confidence=adj(0.80)))
    signals.extend(detect_emails(text, source_file, confidence=adj(0.80)))
    signals.extend(detect_urls(text, source_file, confidence=adj(0.80)))
    signals.extend(detect_label_values(text, source_file, confidence=adj(0.85)))

    if include_billing:
        signals.extend(detect_billing(text, source_file, confidence=adj(0.80)))

    return signals
