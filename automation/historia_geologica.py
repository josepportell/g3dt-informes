#!/usr/bin/env python3
"""
G3DT Historia Geològica - Template Lookup & Extraction

Matches a municipality name to Eva's 238 regional geological history templates
(stored as .docx files under templates/historia-geologica/) and extracts
paragraph text for use in Section 3.1 MARC GEOLÒGIC.

Public API:
    lookup_municipality(name) -> HistoriaLookupResult | None
    extract_paragraphs(file_path) -> list[str]

Author: Eficients.cat
Date: 2026-03-01
"""

from __future__ import annotations

import json
import logging
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ['lookup_municipality', 'extract_paragraphs', 'HistoriaLookupResult']

# Root of the historia-geologica templates
_TEMPLATES_ROOT = Path(__file__).parent.parent / "templates" / "historia-geologica"
_INDEX_PATH = _TEMPLATES_ROOT / "index.json"

# Comarca data file
_COMARQUES_PATH = Path(__file__).parent / "data" / "comarques.json"

# Module-level caches
_INDEX_CACHE: list[dict[str, Any]] | None = None
_MUNICIPI_COMARCA_CACHE: dict[str, str] | None = None  # normalized name → comarca

# Matching thresholds
_MATCH_THRESHOLD = 0.75
_CANDIDATE_THRESHOLD = 0.75

# Comarca → best template location in index.json
# Tier 2 (comarca/zone specific)
# Tier 3 (regional / broader geographic area)
_COMARCA_TEMPLATE: dict[str, str] = {
    # --- Tier 2: comarca-specific templates ---
    'Bages': 'Bages General',
    'Moianes': 'Bages General',
    'Baix Llobregat': 'Baix llobregat general',
    'Valles Occidental': 'vallès',
    'Valles Oriental': 'Valles oriental',
    'Alt Penedes': 'Penedès',
    'Anoia': 'igualada',
    'Maresme': 'maresme',
    'Tarragones': 'Tarragona',
    'Baix Penedes': 'vendrell',
    # --- Tier 3: regional templates ---
    'Barcelones': 'Barcelona',
    'Garraf': 'Vilanova',
    'Bergueda': 'Bergueda',
    'Cerdanya': 'Cerdanya',
    'Solsones': 'Prelitoral',
    'Osona': 'Prelitoral',
    'Ripolles': 'Ripoll_Vallfogona',
    'Girones': 'Girona',
    'Selva': 'Fossa de la Selva',
    'Alt Emporda': 'Empordà',
    'Baix Emporda': 'Empordà',
    'Pla de l\'Estany': 'Banyoles',
    'Alt Camp': 'Fossa del Camp',
    'Baix Camp': 'reus-valls',
    'Priorat': 'Priorat',
    'Conca de Barbera': 'Montblanc',
    'Ribera d\'Ebre': 'historia depresio ebre',
    'Terra Alta': 'Gandesa',
    'Baix Ebre': 'DELTA EBRE',
    'Montsia': 'DELTA EBRE',
    'Segria': 'Lleida',
    'Pla d\'Urgell': 'Lleida',
    'Noguera': 'Lleida',
    'Urgell': 'Lleida',
    'Garrigues': 'Lleida',
    'Segarra': 'Lleida',
    'Pallars Jussa': 'Pallars',
    'Pallars Sobira': 'Pallars',
    'Alta Ribagorca': 'Ribagorça',
    'Alt Urgell': 'PREPIRINEUS',
    'Val d\'Aran': 'Vall d\'Aran',
}


@dataclass
class HistoriaLookupResult:
    """Result of a municipality lookup against the template index."""
    matched_location: str   # "Castellar del Vallès"
    file_path: str          # absolute path to .docx
    tier: int               # 1=municipality, 2=comarca, 3=regional
    score: float            # fuzzy match 0.0-1.0
    candidates: list[dict] = field(default_factory=list)  # other matches


def _load_index() -> list[dict[str, Any]]:
    """Load and cache the template index."""
    global _INDEX_CACHE
    if _INDEX_CACHE is not None:
        return _INDEX_CACHE

    if not _INDEX_PATH.exists():
        logger.warning("Historia geologica index not found: %s", _INDEX_PATH)
        _INDEX_CACHE = []
        return _INDEX_CACHE

    try:
        data = json.loads(_INDEX_PATH.read_text(encoding='utf-8'))
        _INDEX_CACHE = data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Error loading historia geologica index: %s", e)
        _INDEX_CACHE = []

    return _INDEX_CACHE


def _normalize(name: str) -> str:
    """
    Normalize a municipality name for fuzzy matching.

    Steps:
    1. Lowercase + strip accents (NFD decomposition)
    2. st. → sant, sta. → santa
    3. Strip ' i rodalies' suffix
    4. Strip leading articles (el, la, l', els, les)
    5. Collapse whitespace
    """
    # Lowercase
    s = name.lower().strip()

    # Strip accents via NFD decomposition
    s = ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
    )

    # Abbreviation expansions
    s = s.replace('st.', 'sant').replace('sta.', 'santa')

    # Strip ' i rodalies' suffix
    if s.endswith(' i rodalies'):
        s = s[:-len(' i rodalies')]

    # Strip leading articles
    for prefix in ('els ', 'les ', 'el ', 'la ', "l'"):
        if s.startswith(prefix):
            s = s[len(prefix):]
            break

    # Collapse whitespace
    return ' '.join(s.split())


def _load_comarca_mapping() -> dict[str, str]:
    """Load and cache the normalized municipality → comarca reverse lookup."""
    global _MUNICIPI_COMARCA_CACHE
    if _MUNICIPI_COMARCA_CACHE is not None:
        return _MUNICIPI_COMARCA_CACHE

    _MUNICIPI_COMARCA_CACHE = {}
    if not _COMARQUES_PATH.exists():
        logger.warning("Comarques data not found: %s", _COMARQUES_PATH)
        return _MUNICIPI_COMARCA_CACHE

    try:
        data = json.loads(_COMARQUES_PATH.read_text(encoding='utf-8'))
        for comarca, municipis in data.items():
            if comarca.startswith('_'):
                continue
            norm_comarca = _normalize(comarca)
            for m in municipis:
                norm_m = _normalize(m)
                if norm_m:
                    _MUNICIPI_COMARCA_CACHE[norm_m] = norm_comarca
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Error loading comarques data: %s", e)

    return _MUNICIPI_COMARCA_CACHE


def _find_in_index(location_query: str) -> dict | None:
    """Find the best matching entry in index.json for a given location string."""
    index = _load_index()
    norm_query = _normalize(location_query)
    if not norm_query:
        return None

    best: dict | None = None
    best_score = 0.0

    for entry in index:
        if entry.get('tier', 99) >= 4:
            continue
        location = entry.get('location', '')
        norm_loc = _normalize(location)
        if not norm_loc:
            continue

        score = SequenceMatcher(None, norm_query, norm_loc).ratio()
        if score >= _CANDIDATE_THRESHOLD and score > best_score:
            # Prefer Catalan
            if best and best.get('lang') == 'ca' and entry.get('lang') != 'ca' and score - best_score < 0.1:
                continue
            best = {
                'location': location,
                'file': entry['file'],
                'tier': entry.get('tier', 1),
                'lang': entry.get('lang', 'ca'),
                'score': round(score, 3),
            }
            best_score = score

    return best


def lookup_municipality(municipality: str) -> HistoriaLookupResult | None:
    """
    Find the best matching geological history template for a municipality.

    Hierarchical lookup:
    1. Fuzzy match municipality name → tier 1 templates (exact/near match)
    2. If no match: look up comarca → find tier 2/3 template for that comarca
    3. If no comarca match: return None (falls back to hardcoded templates)

    Args:
        municipality: Municipality name (e.g., "Rubí", "Bell-Lloc")

    Returns:
        HistoriaLookupResult if a match found, None otherwise
    """
    index = _load_index()
    if not index:
        return None

    norm_query = _normalize(municipality)
    if not norm_query:
        return None

    # --- Step 1: Direct fuzzy match against all index entries ---
    matches: list[dict] = []

    for entry in index:
        if entry.get('tier', 99) >= 4:
            continue

        location = entry.get('location', '')
        norm_loc = _normalize(location)
        if not norm_loc:
            continue

        score = SequenceMatcher(None, norm_query, norm_loc).ratio()

        if score >= _CANDIDATE_THRESHOLD:
            matches.append({
                'location': location,
                'file': entry['file'],
                'tier': entry.get('tier', 1),
                'lang': entry.get('lang', 'ca'),
                'score': round(score, 3),
            })

    if matches:
        # Sort: prefer Catalan, lowest tier, highest score, shortest name
        matches.sort(key=lambda m: (
            0 if m['lang'] == 'ca' else 1,
            m['tier'],
            -m['score'],
            len(m['location']),
        ))

        best = matches[0]

        # Guard against false positives for short names:
        # "valls" → "vallès" (0.91) or "ripoll" → "ripollet" (0.86) are wrong.
        # If score < 0.95 and query is short, prefer comarca fallback.
        if best['score'] >= 0.95 or len(norm_query) >= 8:
            file_path = _resolve_file_path(best['file'])
            candidates = [m for m in matches[1:] if m['score'] >= _CANDIDATE_THRESHOLD]
            return HistoriaLookupResult(
                matched_location=best['location'],
                file_path=str(file_path),
                tier=best['tier'],
                score=best['score'],
                candidates=candidates,
            )
        # For ambiguous short-name matches, fall through to comarca lookup

    # --- Step 2: Comarca fallback ---
    comarca_map = _load_comarca_mapping()
    comarca = comarca_map.get(norm_query)
    if not comarca:
        # Try prefix matching: "bell-lloc" matches "bell-lloc d'urgell"
        # Prefer shortest match (closest to query) to avoid "sant cugat" → "sant cugat sesgarrigues"
        prefix_matches = []
        for norm_m, com in comarca_map.items():
            if norm_m.startswith(norm_query) and len(norm_query) >= 4:
                prefix_matches.append((norm_m, com))
        if prefix_matches:
            prefix_matches.sort(key=lambda x: len(x[0]))
            comarca = prefix_matches[0][1]
    if not comarca:
        # Try fuzzy matching against comarca municipality list
        best_score = 0.0
        for norm_m, com in comarca_map.items():
            score = SequenceMatcher(None, norm_query, norm_m).ratio()
            if score >= 0.85 and score > best_score:
                comarca = com
                best_score = score

    if not comarca:
        return None

    # Find the template location for this comarca
    template_location = _COMARCA_TEMPLATE.get(comarca)
    if not template_location:
        # Try normalized comarca name against _COMARCA_TEMPLATE keys
        for key, loc in _COMARCA_TEMPLATE.items():
            if _normalize(key) == comarca:
                template_location = loc
                break

    if not template_location:
        logger.debug("No template mapping for comarca '%s'", comarca)
        return None

    # Find the template in the index
    match = _find_in_index(template_location)
    if not match:
        logger.debug("Template '%s' not found in index for comarca '%s'", template_location, comarca)
        return None

    file_path = _resolve_file_path(match['file'])

    return HistoriaLookupResult(
        matched_location=f"{match['location']} (via comarca)",
        file_path=str(file_path),
        tier=match['tier'],
        score=match['score'],
        candidates=[],
    )


def _resolve_file_path(relative_path: str) -> Path:
    """Resolve a relative path from index.json to an absolute path."""
    # The index paths are relative to HISTORIA GEOLÒGICA subfolder
    return _TEMPLATES_ROOT / "HISTORIA GEOLÒGICA" / relative_path


def extract_paragraphs(file_path: str) -> list[str]:
    """
    Extract non-empty paragraphs from a .docx template file.

    Args:
        file_path: Absolute or relative path to the .docx file

    Returns:
        List of non-empty paragraph strings
    """
    path = Path(file_path)
    if not path.exists():
        logger.warning("Historia geologica file not found: %s", path)
        return []

    try:
        from docx import Document
        doc = Document(str(path))
        paragraphs = [
            p.text.strip()
            for p in doc.paragraphs
            if p.text.strip()
        ]
        return paragraphs
    except ImportError:
        logger.error("python-docx not installed, cannot extract historia geologica")
        return []
    except Exception as e:
        logger.warning("Error extracting paragraphs from %s: %s", path, e)
        return []


# ---------------------------------------------------------------------------
# CLI for testing
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import sys

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    if len(sys.argv) < 2:
        print("Ús: python3 -m automation.historia_geologica <municipality>")
        print("Exemple: python3 -m automation.historia_geologica Rubí")
        sys.exit(1)

    name = ' '.join(sys.argv[1:])
    print(f"Cercant: '{name}'")
    print("=" * 50)

    result = lookup_municipality(name)
    if result:
        print(f"Match: {result.matched_location} (tier {result.tier}, score {result.score:.2f})")
        print(f"File: {result.file_path}")
        if result.candidates:
            print(f"Candidates: {len(result.candidates)}")
            for c in result.candidates[:3]:
                print(f"  - {c['location']} (tier {c['tier']}, score {c['score']:.2f})")

        paras = extract_paragraphs(result.file_path)
        print(f"\nParagraphs: {len(paras)}")
        for i, p in enumerate(paras[:3]):
            print(f"  [{i+1}] {p[:80]}...")
    else:
        print("NO MATCH (falls back to hardcoded templates)")
