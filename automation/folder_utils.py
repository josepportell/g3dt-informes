"""Shared utilities for parsing G3DT project folder names.

G3DT project folders on their network use the format "4001612 BELL-LLOC"
(code + space + municipality in uppercase). Test folders may use
"4001612-bell-lloc" (hyphens, lowercase). This module handles both.
"""

import re


def parse_folder_name(folder_name: str) -> tuple[str, str]:
    """Extract expedient code and municipality from a project folder name.

    Supports:
        "4001612 BELL-LLOC"           -> ("4001612", "Bell-Lloc")
        "3001621 CASTELLAR DEL VALLES" -> ("3001621", "Castellar Del Valles")
        "4001612-bell-lloc"           -> ("4001612", "Bell-Lloc")
        "4001612-bell-lloc-d-urgell"  -> ("4001612", "Bell-Lloc d'Urgell")
        "4001612"                     -> ("4001612", "")
    """
    # Normalize Catalan punt volat (·) to hyphen: "BELL·LLOC" -> "BELL-LLOC"
    folder_name = folder_name.replace('\u00b7', '-')

    # Space-separated: "4001612 BELL-LLOC" or "3001621 CASTELLAR DEL VALLES"
    if ' ' in folder_name:
        parts = folder_name.split(maxsplit=1)
        expedient = parts[0]
        municipality = parts[1].title() if len(parts) > 1 else ""
        return expedient, municipality

    # Hyphen-separated: "4001612-bell-lloc" or "4001612-bell-lloc-d-urgell"
    match = re.match(r'^(\d+)-(.+)$', folder_name)
    if match:
        expedient = match.group(1)
        raw_municipality = match.group(2)
        municipality = _format_catalan_municipality(raw_municipality)
        return expedient, municipality

    # Bare code: "4001612"
    return folder_name, ""


def municipality_for_report(name: str) -> str:
    """Strip trailing digits from a municipality name for use in report text.

    Folder names like "BELL-LLOC4" include a version suffix that should not
    appear in the report prose.  "Bell-Lloc4" -> "Bell-Lloc".
    """
    return re.sub(r'\d+$', '', name)


def _format_catalan_municipality(raw: str) -> str:
    """Format a hyphen-separated municipality name with Catalan conventions.

    Handles apostrophe contractions (d', l') and lowercase prepositions.
    Regular name parts are rejoined with hyphens (e.g. Bell-Lloc),
    while prepositions/articles get spaces (e.g. Castellar del Valles).
    """
    words = raw.split('-')
    contractions = {"d", "l"}
    lowercase_words = {"de", "del", "la", "el", "les", "els"}

    tokens: list[str] = []
    prev_type = None  # "regular", "lowercase", "apostrophe"
    for w in words:
        wl = w.lower()
        if wl in contractions:
            if tokens:
                tokens.append(' ')
            tokens.append(wl + "'")
            prev_type = "apostrophe"
        elif wl in lowercase_words:
            if tokens:
                tokens.append(' ')
            tokens.append(wl)
            prev_type = "lowercase"
        else:
            if tokens:
                if prev_type == "apostrophe":
                    pass  # glue directly after apostrophe
                elif prev_type == "lowercase":
                    tokens.append(' ')
                else:
                    tokens.append('-')
            tokens.append(w.capitalize())
            prev_type = "regular"

    return ''.join(tokens)
