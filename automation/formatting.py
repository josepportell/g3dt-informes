#!/usr/bin/env python3
"""
G3DT Formatting Utilities

Shared text formatting functions used across report generation modules.

Bloc 2 (2026-09-07): les funcions d'aquí són la «forma impresa» d'un valor LLEGIT o desat al wizard. El wizard
conserva el text tal com s'ha llegit (l'Eva el veu sencer); el generador hi aplica aquestes funcions abans
d'omplir la plantilla. Totes són idempotents (un valor ja formatat surt igual) i no inventen res: un text que no
es reconeix surt tal qual.
"""

import re

_PAREN_RE = re.compile(r"\([^)]*\)")
_NUM_WORDS = {"un": 1, "una": 1, "uno": 1, "dos": 2, "dues": 2, "tres": 3, "quatre": 4, "cuatro": 4,
              "cinc": 5, "cinco": 5}
_FLOOR_SPLIT_RE = re.compile(r"\+|,|/|\s+(?:i|y|amb|con|més|más)\s+", re.I)
_BASEMENT_RE = re.compile(r"(semi)?s[oò]t[aà]n|soterran|sótano|sotano")


def format_floor_notation(value: str) -> str:
    """Convert architect-style floor notation (or the free text the reader gives) to Eva's style.

    Eva's convention (7/7 signats): «Pb», «Pb+1Pp», «Ps+Pb+2Pp», «PB + Porxo». Lowercase except the first
    letter, explicit count before Pp, basement first, porch last.

    Examples (notació d'arquitecte, com abans):
        "PB+PP" -> "Pb+1Pp"
        "PB+P1" -> "Pb+1Pp"
        "Ps+PB+2Pp" -> "Ps+Pb+2Pp"
        "Ps+PB+P1+P2" -> "Ps+Pb+2Pp"
        "PB" -> "Pb"
    Examples (text llegit, bloc 2 2026-09-07):
        "PB+1" -> "Pb+1Pp"                                   (Castellar: número sol després de PB = plantes pis)
        "PB (planta baixa, 1 nivell)" -> "Pb"                (Linyola; la glossa entre parèntesis no compta)
        "PB (planta baixa) + porxada, sense pis superior" -> "Pb+Porxo"   (Rubí; «sense …» és negació)
        "PB+1PP amb dos semisòtans" -> "2Ps+Pb+1Pp"          (Anciles)
        "SÓTANO, PLANTA BAJA y PLANTA 1" -> "Ps+Pb+1Pp"
    Un text sense cap component reconegut surt tal qual («3», «1 (PB)»).
    """
    if not value or not str(value).strip():
        return value

    raw = str(value).strip()
    raw = re.sub(r"[''´\"]+$", '', raw)
    text = _PAREN_RE.sub(" ", raw)
    parts = [p.strip() for p in _FLOOR_SPLIT_RE.split(text) if p and p.strip()]
    pb = False
    porxo = False
    ps_count = 0
    pp_count = 0
    unknown: list[str] = []
    recognised = False

    for idx, part in enumerate(parts):
        low = part.lower()
        compact = re.sub(r"\s+", "", low)
        if low.startswith(("sense ", "sin ")):          # «sense pis superior»: no compta res
            recognised = True
            continue
        if compact == "pb" or "plantabaixa" in compact or "plantabaja" in compact:
            pb = True
            recognised = True
            continue
        m = re.fullmatch(r"(\d*)ps", compact)
        if m or _BASEMENT_RE.search(compact):
            n = int(m.group(1)) if (m and m.group(1)) else None
            if n is None:
                m2 = re.match(r"(\d+)", compact)
                n = int(m2.group(1)) if m2 else _NUM_WORDS.get(low.split()[0], 1)
            ps_count += n
            recognised = True
            continue
        if re.fullmatch(r"p\d+", compact) or re.fullmatch(r"planta\d+", compact):   # P1, P2, «planta 1»
            pp_count += 1
            recognised = True
            continue
        m = re.fullmatch(r"(\d*)pp", compact)                                       # PP, 1Pp, 2PP
        if m:
            pp_count += int(m.group(1)) if m.group(1) else 1
            recognised = True
            continue
        if compact in ("pis", "plantapis", "plantaprimera", "plantasegona", "plantaprimer", "primerpis", "plantapiso"):
            pp_count += 1
            recognised = True
            continue
        if re.fullmatch(r"\d+", compact) and idx > 0 and pb:                        # «PB+1»: plantes pis
            pp_count += int(compact)
            recognised = True
            continue
        if re.search(r"porx|porche", compact):
            porxo = True
            recognised = True
            continue
        unknown.append(part)

    if not recognised:
        return raw

    out: list[str] = []
    if ps_count:
        out.append(f"{ps_count}Ps" if ps_count > 1 else "Ps")
    if pb:
        out.append("Pb")
    if pp_count:
        out.append(f"{pp_count}Pp")
    if porxo:
        out.append("Porxo")
    out.extend(unknown)
    formatted = "+".join(out)
    return formatted if formatted else raw


_THOUSANDS_RE = re.compile(r"[+-]?\d{1,3}(?:\.\d{3})+(?:,\d+)?")


def format_area(value) -> str:
    """Superfície (m²) com l'escriu l'Eva a la Taula 1: milers amb punt, decimals amb coma.

    «1284.0» → «1.284» (Castellar signat «1.284»), «951.0» → «951», «250.91» → «250,91», «1655.01» → «1.655,01».
    Un valor ja formatat («1.284», «1.655,01») o no numèric («280+86», «120 m2») surt tal qual; buit → «».
    """
    if value is None:
        return ""
    s = str(value).strip()
    if not s:
        return ""
    if _THOUSANDS_RE.fullmatch(s):
        return s
    if not re.fullmatch(r"[+-]?\d+(?:[.,]\d+)?", s):
        return s
    num = float(s.replace(",", "."))
    if num.is_integer():
        return f"{int(num):,}".replace(",", ".")
    return f"{num:,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def format_cota(value) -> str:
    """Cota de referència com la imprimeix l'Eva: signe, punt decimal, dos decimals («+188.20», «-4.00»).

    Del text llegit: «+188,20 msnm» → «+188.20»; «199,50 m» → «+199.50»; «+245 msnm segons plànol topogràfic del
    ICGC (-0,15m carrer)» → «+245.00» (el primer número és la cota; el de dins del parèntesi és una nota);
    «-4,0 m (respecte el carrer)» → «-4.00». Ja formatat → igual; sense número → tal qual; buit → «».
    """
    s = str(value or "").strip()
    if not s:
        return ""
    m = re.search(r"([+-]?)\s*(\d+(?:[.,]\d+)?)", s.replace("−", "-"))
    if not m:
        return s
    num = float(m.group(2).replace(",", "."))
    if m.group(1) == "-":
        num = -num
    return f"{num:+.2f}"


def format_spt_id(value) -> str:
    """Identificador d'un assaig SPT/MA com a la taula de l'Eva: «SPT-1», «MA-1» (4/4 signats amb SPT).

    «SPT1 S1» / «SPT1 P3» / «SPT1» / «spt-1» → «SPT-1» (el punt/sondeig té la seva columna); «MA1 S1» → «MA-1».
    Un text que no comença per SPT/MA/MI/TP + número surt tal qual.
    """
    s = str(value or "").strip()
    m = re.match(r"^(SPT|MA|MI|TP)\s*-?\s*(\d+)\b", s, re.I)
    if not m:
        return s
    return f"{m.group(1).upper()}-{int(m.group(2))}"
