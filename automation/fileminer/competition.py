"""
Signal competition: when multiple signals target the same variable, pick the winner.

Default: deterministic resolution by priority (lower wins), then confidence (higher wins).
For report_date: among same-priority signals, prefer the most recent date.
Designed to be replaceable with an LLM-based resolver in Phase G.
"""

from __future__ import annotations

import re
from datetime import datetime

from .models import Signal, ResolvedValue


# Month name → number mapping (Spanish/Catalan)
_MONTH_MAP = {
    "enero": 1, "gener": 1, "january": 1,
    "febrero": 2, "febrer": 2, "february": 2,
    "marzo": 3, "març": 3, "march": 3,
    "abril": 4, "april": 4,
    "mayo": 5, "maig": 5, "may": 5,
    "junio": 6, "juny": 6, "june": 6,
    "julio": 7, "juliol": 7, "july": 7,
    "agosto": 8, "agost": 8, "august": 8,
    "septiembre": 9, "setembre": 9, "september": 9,
    "octubre": 10, "october": 10,
    "noviembre": 11, "novembre": 11, "november": 11,
    "diciembre": 12, "desembre": 12, "december": 12,
}


def _parse_date_value(value: str) -> float:
    """Try to parse a date string and return a timestamp (higher = more recent).

    Handles: "MARZO 2024", "Febrero 2026", "18/11/24", "2024-03-15", etc.
    Returns 0.0 if unparseable.
    """
    v = value.strip()

    # Try "MONTH YEAR" pattern (e.g. "MARZO 2024", "Octubre 2025")
    m = re.match(r'^(\w+)\s+(\d{4})$', v, re.IGNORECASE)
    if m:
        month_name = m.group(1).lower()
        year = int(m.group(2))
        month = _MONTH_MAP.get(month_name)
        if month:
            try:
                return datetime(year, month, 1).timestamp()
            except ValueError:
                pass

    # Try standard date formats
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(v, fmt).timestamp()
        except ValueError:
            continue

    return 0.0


def resolve_competition(
    signals: list[Signal],
) -> dict[str, ResolvedValue]:
    """Resolve competing signals into one winner per report variable.

    Groups signals by maps_to, then for each variable picks the best signal.
    Signals with maps_to=None are skipped (unmapped data).

    For report_date: among same-priority signals, prefer the most recent date.

    Args:
        signals: All signals from all miners

    Returns:
        Dict of variable_name -> ResolvedValue (winner + alternatives)
    """
    grouped: dict[str, list[Signal]] = {}
    for s in signals:
        if s.maps_to is not None:
            grouped.setdefault(s.maps_to, []).append(s)

    resolved: dict[str, ResolvedValue] = {}
    for variable, candidates in grouped.items():
        if variable == "report_date":
            # For dates: priority first (lower wins), then most recent date
            ranked = sorted(
                candidates,
                key=lambda s: (s.priority, -_parse_date_value(s.value), -s.confidence),
            )
        else:
            ranked = sorted(candidates, key=lambda s: (s.priority, -s.confidence))
        winner = ranked[0]
        alternatives = ranked[1:]
        resolved[variable] = ResolvedValue(
            variable=variable,
            value=winner.value,
            source=winner.source_file,
            confidence=winner.confidence,
            signal=winner,
            alternatives=alternatives,
        )

    return resolved
