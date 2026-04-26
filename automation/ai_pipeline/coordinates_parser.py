"""Deterministic parser for ANNEXES/COORDENADES.txt — Eva's structured UTM file.

Observed format across reference projects:

    Coordenades UTM (X);(Y);(Z);
    P-1
    308781,86 ; 4613950.63 ; 198.9
    P-2 (optional)
    308782,11 ; 4613951.04 ; 198.7

This file is too small / too structured for an LLM call to be cost-effective —
a few lines of regex/split logic extract it perfectly. Stage 2 marks the file
`coordinates_text, useful=True, conversion_strategy="parse_deterministically"`
so Stage 3/4 can short-circuit the usual conversion + LLM pipeline.

Public API:
    parse_coordenades_txt(path) → list[dict] | None
    candidates_from_coordenades(rows, source_path) → list[Candidate]
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from automation.ai_pipeline.analysis import Candidate

logger = logging.getLogger(__name__)


_HEADER_TOKENS = ("COORDENADES UTM", "COORDINATES")
_TEST_ID_RE = re.compile(r"^[A-Za-z]+\s*-?\s*\d+[A-Za-z]?$")


def _looks_like_test_id(line: str) -> bool:
    """True when the line is a short label like 'P-1', 'S-2', 'P 3'."""
    s = line.strip()
    if not s or len(s) > 20:
        return False
    return bool(_TEST_ID_RE.match(s))


def _parse_coord_line(line: str) -> tuple[float, float, float | None] | None:
    """Parse a single 'x ; y [ ; z ]' line. Comma-decimals are normalized.

    Returns None if the line has fewer than two parsable numbers.
    """
    parts = [p.strip().replace(",", ".") for p in line.split(";") if p.strip()]
    if len(parts) < 2:
        return None
    try:
        x = float(parts[0])
        y = float(parts[1])
    except ValueError:
        return None
    z: float | None = None
    if len(parts) >= 3:
        try:
            z = float(parts[2])
        except ValueError:
            z = None
    return (x, y, z)


def parse_coordenades_txt(path: Path) -> list[dict] | None:
    """Parse ANNEXES/COORDENADES.txt — header + (test_id) + (x;y;z[;extra]) per row.

    Returns: list of dicts, one per test point, with keys:
        test_point_id (str), utm_x (float), utm_y (float), utm_z (float | None)

    Returns None if the file is unreadable or unparseable. Returns [] if the
    file matches the expected shape (header) but has no valid coordinate rows.
    """
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as e:
        logger.debug("coordinates_parser: cannot read %s: %s", path, e)
        return None

    raw_lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not raw_lines:
        return None

    # Skip header line(s).
    lines: list[str] = []
    saw_header = False
    for ln in raw_lines:
        ln_upper = ln.upper()
        if any(tok in ln_upper for tok in _HEADER_TOKENS):
            saw_header = True
            continue
        lines.append(ln)

    if not saw_header and not any(";" in ln for ln in lines):
        # No header AND no semicolon-delimited rows → not our format.
        return None

    rows: list[dict] = []
    pending_id: str | None = None
    auto_index = 0

    for ln in lines:
        if _looks_like_test_id(ln):
            pending_id = ln.replace(" ", "")
            continue
        coord = _parse_coord_line(ln)
        if coord is None:
            continue
        if pending_id is None:
            auto_index += 1
            pending_id = f"P-{auto_index}"
        x, y, z = coord
        rows.append({
            "test_point_id": pending_id,
            "utm_x": x,
            "utm_y": y,
            "utm_z": z,
        })
        pending_id = None

    return rows


# ─── Candidate synthesis ───────────────────────────────────────────────


# concept_id mapping for the project-level UTM coordinates.
_PROJECT_LEVEL_CONCEPT_BY_FIELD: dict[str, str] = {
    "utm_x": "utm_x",
    "utm_y": "utm_y",
    "utm_z": "utm_z",
}


def candidates_from_coordenades(rows: list[dict], source_path: str) -> list["Candidate"]:
    """Build Stage 4 Candidate objects from parsed coord rows.

    Project-level concepts (utm_x / utm_y / utm_z) take the FIRST row, by
    Eva's convention that P-1 is the reference point. Returns an empty list
    when `rows` is empty.
    """
    from automation.ai_pipeline.analysis import Candidate  # local import: avoid cycle

    if not rows:
        return []

    out: list[Candidate] = []
    first = rows[0]
    for field, concept_id in _PROJECT_LEVEL_CONCEPT_BY_FIELD.items():
        value = first.get(field)
        if value is None:
            continue
        out.append(
            Candidate(
                concept_id=concept_id,
                value=value,
                confidence=1.0,
                quote=f"{first.get('test_point_id', '')}: {value}",
                source_path=source_path,
                extractor="coordinates_parser",
                reasoning=(
                    f"Deterministic parse of COORDENADES.txt — value taken "
                    f"from row {first.get('test_point_id', '?')}."
                ),
            )
        )
    return out
