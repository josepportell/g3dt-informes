#!/usr/bin/env python3
"""
G3DT Formatting Utilities

Shared text formatting functions used across report generation modules.
"""

import re


def format_floor_notation(value: str) -> str:
    """Convert architect-style floor notation to Eva's preferred style.

    Eva's convention: lowercase except first letter, explicit count before Pp.

    Examples:
        "PB+PP" -> "Pb+1Pp"
        "PB+P1" -> "Pb+1Pp"
        "Ps+PB+2Pp" -> "Ps+Pb+2Pp"
        "Ps+PB+P1+P2" -> "Ps+Pb+2Pp"
        "PB" -> "Pb"
    """
    if not value or not value.strip():
        return value

    raw = value.strip()
    raw = re.sub(r"[''´\"]+$", '', raw)
    parts = [p.strip() for p in raw.split('+')]
    result = []
    pp_count = 0

    for part in parts:
        upper = part.upper()
        if upper == 'PB':
            result.append(('pb', None))
        elif upper == 'PS':
            result.append(('ps', None))
        elif re.match(r'^P\d+$', upper):
            # Individual upper floor like P1, P2
            pp_count += 1
        elif re.match(r'^\d+\s*PP$', upper):
            # Already counted like "2Pp" or "2PP"
            m = re.match(r'^(\d+)', part)
            pp_count += int(m.group(1))
        elif upper == 'PP':
            pp_count += 1
        else:
            # Unknown component -- keep as-is
            result.append(('unknown', part))

    # Build output
    output_parts = []
    for kind, orig in result:
        if kind == 'pb':
            output_parts.append('Pb')
        elif kind == 'ps':
            output_parts.append('Ps')
        else:
            output_parts.append(orig)

    if pp_count > 0:
        output_parts.append(f'{pp_count}Pp')

    formatted = '+'.join(output_parts)
    return formatted if formatted else raw
