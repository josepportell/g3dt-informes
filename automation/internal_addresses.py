"""
G3 internal address + provider-NIF detection.

G3 Geotecnia (the service provider) has its own office addresses and CIF
that leak into client-provided documents (lab order Excels, email
signatures, pressupost PDFs). The same happens with recurring service
providers (e.g. the drilling/lab subcontractor on every GTL report).
Those must NEVER be treated as the project's site address or the *client's*
NIF, because they identify the *provider*, not the project's client.

This module centralizes the patterns and the detection helpers so every
pipeline stage (FileMiner competition, geocode phase, adjacents phase)
applies the same guard.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

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


# ── Provider NIF/CIF blocklist (must NOT become the client's NIF) ──────────
# These NIFs identify the service provider, never the project's client.
# Verified empirically across all 7 reference projects (2026-06-23): each
# appears on the SAME document type in EVERY project — a constant that only
# the issuer/provider could be. A real client NIF varies project to project.
#   B25461443 — G3 Desenvolupament Territorial SL (Eva's own company, the
#               budget issuer): appears on every "PRESSUPOST GEOTEC.*.pdf".
#   B64803075 — drilling/lab subcontractor (TPS Perforaciones): appears on
#               every "*-GTL-*.pdf" lab report.
# To add a provider: append its NIF here (uppercase, no dots/spaces).
NON_CLIENT_NIFS: set[str] = {
    'B25461443',
    'B64803075',
}

# NIF/CIF token: optional leading letter, 7-8 digits, optional trailing letter.
# Anchored on word boundaries so it survives label prefixes like
# "N.I.F./C.I.F.: 38112117J" (the dots/colon form boundaries).
_NIF_TOKEN_RE = re.compile(r'\b[A-Z]?\d{7,8}[A-Z]?\b')


def is_non_client_nif(value: str) -> bool:
    """Return True if value contains a known provider NIF (G3 or a lab).

    Extracts NIF-shaped tokens from value and checks exact membership in
    NON_CLIENT_NIFS. A clean text-mined provider value ("B25461443") matches;
    a labelled client value ("N.I.F./C.I.F.: 38112117J") yields token
    "38112117J", which is not in the blocklist, so it is kept.
    """
    if not isinstance(value, str):
        return False
    return any(
        tok in NON_CLIENT_NIFS
        for tok in _NIF_TOKEN_RE.findall(value.upper())
    )


# ── Lab company registry (NIF → canonical name as Eva spells it) ───────────
# Maps a known lab-provider NIF to the canonical company name exactly as it
# must appear in Eva's signed reports. The GTL footer spells it WITH commas
# ("TPS, PROSPECCIÓ DEL SUBSÒL, SL"); Eva writes it WITHOUT commas — so we
# canonicalize via this registry instead of echoing the raw footer text.
# B64803075 is the same lab NIF already declared in NON_CLIENT_NIFS above
# (kept single-sourced conceptually — see that blocklist for provenance).
LAB_REGISTRY: dict[str, str] = {
    'B64803075': 'TPS PROSPECCIÓ DEL SUBSÒL SL',
}

# Lab footer band: "<name>  <NIF>  Ins. Reg. Merc. ...". Anchored on the
# mercantile-registry marker ("Ins. Reg") so it can only match the lab footer,
# never the DADES DEL CLIENT / SOL.LICITANT block (which carries G3's own NIF
# B25364589 but has no such marker). MULTILINE + line-start anchor keep the
# captured name confined to its own line (no leading label/junk from prior
# text bleeding into an unknown lab's name).
_LAB_FOOTER_RE = re.compile(
    r'^[ \t]*(?P<name>[^\n]+?)\s+(?P<nif>B\d{8})\s+Ins\.?\s*Reg',
    re.IGNORECASE | re.MULTILINE,
)


def resolve_lab_company(text: str) -> tuple[str | None, str | None]:
    """Resolve the testing-lab (name, nif) from GTL/lab report text.

    Finds the lab footer band (the line ending in the mercantile-registry
    marker "Ins. Reg") so it can never mistake the client/sol·licitant block —
    which carries G3's own NIF — for the lab. A known NIF resolves to its
    canonical spelling via LAB_REGISTRY; an unknown one returns the parsed
    name verbatim (whitespace-collapsed) and logs a warning so a recurring
    lab can be registered. Returns (None, None) when no footer is present.

    Assumes the GTL footer band is issued by the testing lab — it is the only
    line carrying the "Ins. Reg" mercantile-registry marker — and that a NIF
    present in LAB_REGISTRY is authoritative over the raw footer spelling.
    """
    if not isinstance(text, str):
        return (None, None)
    match = _LAB_FOOTER_RE.search(text)
    if not match:
        return (None, None)
    nif = match.group('nif').upper()
    if nif in LAB_REGISTRY:
        return (LAB_REGISTRY[nif], nif)
    name = re.sub(r'\s+', ' ', match.group('name')).strip()
    logger.warning(
        "Unknown lab NIF %s (%r) seen in report footer; add it to "
        "LAB_REGISTRY if it recurs.", nif, name,
    )
    return (name, nif)
