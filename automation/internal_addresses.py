"""
G3 internal address detection.

G3 Geotecnia (the service provider) has its own office addresses that
leak into client-provided documents (lab order Excels, email signatures,
pressupost PDFs). Those must NEVER be treated as the project's site
address, because they are the *provider's* address, not the project's.

This module centralizes the patterns and the detection helper so every
pipeline stage (FileMiner competition, geocode phase, adjacents phase)
applies the same guard.
"""

from __future__ import annotations

# ── G3 internal address patterns (must NOT become project street_address) ──
# G3 Desenvolupament Territorial SL office: C/ Vallbona, 22 — Rubi
# Each tuple is (street_fragment, house_number) — BOTH must match to avoid
# false positives on legitimate "Vallbona" addresses in other municipalities.
G3_ADDRESS_PATTERNS: list[tuple[str, str]] = [
    ('VALLBONA', '22'),  # G3 office: C/ Vallbona, 22 — Rubi
]


def is_g3_internal_address(value: str) -> bool:
    """Return True if value looks like G3's own office address, not a project site.

    The match is deliberately loose on municipality context: we accept false
    positives like "Vallbona d'Anoia 22" because the cost of polluting a
    project's street_address with G3's office is far higher than the cost of
    dropping a single legitimate address that shares the same fragment.
    """
    if not isinstance(value, str):
        return False
    upper = value.upper().strip()
    return any(
        street in upper and number in upper
        for street, number in G3_ADDRESS_PATTERNS
    )
