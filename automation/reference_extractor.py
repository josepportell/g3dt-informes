#!/usr/bin/env python3
"""
Reference Extractor: Extract structured variable values from Eva's real
geotechnical reports (.docx/.doc) using template-guided alignment.

Reads the Jinja template to know WHERE each variable lives, then finds
the matching paragraph/cell in the reference report and extracts the value.

Usage:
    python3 -m automation.reference_extractor "reference-material/4001612 BELL-LLOC"

    # Or a specific .doc/.docx file:
    python3 -m automation.reference_extractor path/to/4001612_informe.doc

Output:
    {project_path}/validation/eva_reference_values.json

Author: Eficients.cat
Date: 2026-04-05
"""

import json
import logging
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field, asdict
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from .intelligent_audit import (
    extract_docx_paragraphs,
    extract_template_paragraphs,
    _build_table_coords_map,
    _flat_idx_to_elem_id,
    text_similarity,
    normalize_text,
    TemplateParagraph,
    TableCoords,
    JINJA_VAR_RE,
    JINJA_ANY_RE,
)

logger = logging.getLogger(__name__)

VERSION = "1.0"

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_TEMPLATE = BASE_DIR / "templates" / "g3dt-jinja-template.docx"
REFERENCE_DIR = BASE_DIR / "reference-material"

KNOWN_REPORTS = {
    "4001612 BELL-LLOC": "4001612_informe.doc",
    "3001631 RUBI": "3001631_informe.doc",
    "4001607 LINYOLA": "4001607_informe.doc",
    "3001621 CASTELLAR DEL VALLES": "3001621_informe_v0.doc",
    "4001670 ALCOLETGE": "4001670_informe.doc",
    "4001671 VILANOVA DE SEGRIA": "4001671_informe.docx",
    "4001679 ANCILES": "4001679_informe_V0.doc",
}

SKIP_PREFIXES = (
    "fig_", "photo_", "section_", "taula_",
)

# Phrases that indicate a row is a column-header (used by _is_table_header_row).
# Broad set: includes single-letter column names like "n", "e", "nb" because we
# only flag a ROW as header when MULTIPLE cells match these phrases.
_HEADER_ROW_PHRASES = frozenset({
    "nº assaig", "n° assaig", "n. assaig", "nº  assaig",
    "nº ensayo", "n° ensayo", "n.º ensayo", "punto", "prof. extracción (m)", "prof. extraccion (m)", "litología",   # ES (bloc 3)
    "punt",
    "prof. extracció (m)", "prof. extraccio (m)",
    "prof. extracció", "prof. extraccio",
    "n30", "n20", "n",
    "litologia",
    "cota", "depth", "test_id",
    "refús", "refus", "refusal",
    "nivell freàtic", "nivell freatic", "water", "spt_ma",
    "nb", "phi", "e", "cohesion", "density",
    "name", "material", "k_value",
    "thickness", "terrain_type", "c_coeff", "num",
})

# Strict header-cell phrases (used during flatten, where one bad cell shouldn't
# poison the whole row). Narrower; avoids matching on legitimate single-letter
# values like "N" / "E" that may appear as data in some columns.
_HEADER_CELL_PHRASES = frozenset({
    "nº assaig", "n° assaig", "n. assaig", "nº  assaig",
    "prof. extracció (m)", "prof. extraccio (m)",
    "prof. extracció", "prof. extraccio",
    "litologia",
    "nº ensayo", "n° ensayo", "n.º ensayo", "prof. extracción (m)", "litología",   # ES (bloc 3)
})

# Backwards-compat alias retained for any external imports/tests.
_TABLE_HEADER_VALUES = _HEADER_ROW_PHRASES


def _is_table_header_value(s: Any) -> bool:
    """Return True when a cell value looks like a column header phrase.

    Catalan-aware (handles `Nº`, `°`, `extracció`). Uses the broad
    `_HEADER_ROW_PHRASES` set because callers (row-level header detection)
    need maximum recall.
    """
    if not isinstance(s, str):
        return False
    return s.strip().lower() in _HEADER_ROW_PHRASES


def _is_strict_header_cell(s: Any) -> bool:
    """Return True only for definitely-not-data header phrases.

    Used during table flatten where a single false-positive (e.g. a cell value
    of "N" or "E") would poison a whole row. Narrower than
    `_is_table_header_value`.
    """
    if not isinstance(s, str):
        return False
    return s.strip().lower() in _HEADER_CELL_PHRASES


def _is_table_header_row(row: dict) -> bool:
    """Return True when a loop-table row looks like a header row.

    Heuristics:
    1. `test_id` matches a known header phrase (e.g. "Nº assaig").
    2. All non-empty values look like header phrases.
    A real test_id like "P-1", "S-2", "SPT-1" passes through (digit + dash).

    Assumption (W4): all real test_ids in our reports follow the
    `LETTERS[-]DIGITS` pattern (P-1, S2, SPT-1). If a future format uses
    purely numeric or purely alphabetic ids, this guard needs updating.
    """
    if not isinstance(row, dict):
        return False
    test_id = row.get("test_id")
    if isinstance(test_id, str):
        tid = test_id.strip()
        # Real test ids: letters + dash + digits (e.g. P-1, S-2, SPT-1).
        if re.match(r"^[A-Za-z]+-?\d+", tid):
            return False
        if _is_table_header_value(tid):
            return True
    non_empty = [v for v in row.values() if isinstance(v, str) and v.strip()]
    if non_empty and all(_is_table_header_value(v) for v in non_empty):
        return True
    return False

SKIP_SUFFIXES = (
    "_image", "_num",
)

LOOP_TABLES = {
    4: {
        "name": "dpsh_tests",
        "cols": ["test_id", "cota", "depth", "refusal", "water"],
        "header_rows": 2,
    },
    5: {
        "name": "sondeig_tests",
        "cols": ["test_id", "cota", "depth", "spt_ma", "water"],
        "header_rows": 2,
    },
    # Bloc 3 (2026-09-07): la taula SPT/MA és un bucle des de la Fase 8b (2026-08-26); sense aquesta entrada les cel·les
    # `{{ test.* }}` es saltaven (punt al nom) i `spt_*` queien a None a la re-extracció.
    6: {
        "name": "spt_ma_tests",
        "cols": ["test_id", "location", "depth_range", "n30", "lithology"],
        "header_rows": 2,
    },
    8: {
        "name": "soil_level_rows",
        "cols": ["name", "material"],
        "header_rows": 1,
    },
    9: {
        "name": "perm_rows",
        "cols": ["name", "k_value", "material"],
        "header_rows": 1,
    },
    11: {
        "name": "seismic_rows",
        "cols": ["num", "terrain_type", "thickness", "c_coeff"],
        "header_rows": 2,
    },
    12: {
        "name": "geotech_rows",
        "cols": ["name", "nb", "n", "density", "cohesion", "phi", "E"],
        "header_rows": 2,
    },
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ExtractedVariable:
    value: Any
    position: str
    position_description: str
    confidence: float
    extraction_method: str
    template_text: str = ""
    reference_text: str = ""


@dataclass
class ExtractionResult:
    project: str
    source_file: str
    extraction_date: str
    template_file: str
    variables: dict[str, ExtractedVariable] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    statistics: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _should_skip_variable(var_name: str) -> bool:
    """Return True if the variable should be skipped (images, numbering)."""
    for prefix in SKIP_PREFIXES:
        if var_name.startswith(prefix):
            return True
    for suffix in SKIP_SUFFIXES:
        if var_name.endswith(suffix):
            return True
    if "." in var_name:
        return True
    return False


def _table_fingerprint(table) -> str:
    """Build a fingerprint from the first non-Jinja-block row's cell texts.

    Strips Jinja tags so template tables with {%tr for%} can still match
    reference tables by their header content.
    """
    if not table.rows:
        return ""
    for row in table.rows:
        cells = []
        has_content = False
        for cell in row.cells:
            text = JINJA_ANY_RE.sub('', cell.text).strip()
            cells.append(normalize_text(text))
            if text:
                has_content = True
        if has_content:
            return " | ".join(cells)
    return ""


def _get_table_cell_text(table, row_idx: int, col_idx: int) -> str | None:
    """Safely read a table cell's text."""
    try:
        if row_idx >= len(table.rows):
            return None
        row = table.rows[row_idx]
        if col_idx >= len(row.cells):
            return None
        return row.cells[col_idx].text.strip()
    except (IndexError, AttributeError):
        return None


#: Forats que l'Eva pot ometre del tot: si el prefix fix no hi és, val més cap valor que un paràgraf equivocat.
_ABSENT_IF_PREFIX_MISSING = frozenset({"location_sentence"})


def _ap_lower(text: str) -> str:
    """Minúscules amb apòstrofs i cometes tipogràfiques normalitzades, mateixa longitud que l'original."""
    return (text.replace('\u2019', "'").replace('\u2018', "'")
                .replace('\u201c', '"').replace('\u201d', '"').lower())


def _extract_single_var(template_text: str, var_name: str,
                        ref_text: str) -> tuple[str | None, float]:
    """Extract a single variable value from a reference paragraph.

    Splits the template text on the {{ var }} placeholder to get prefix/suffix,
    then slices the reference text accordingly.

    Returns (value, confidence).
    """
    pattern = re.compile(
        r'\{\{[-\s]*' + re.escape(var_name) + r'\s*(?:\|[^}]*)?\s*\}\}'
    )
    parts = pattern.split(template_text, maxsplit=1)
    if len(parts) != 2:
        return None, 0.0

    prefix_tmpl = JINJA_ANY_RE.sub('', parts[0]).strip()
    suffix_tmpl = JINJA_ANY_RE.sub('', parts[1]).strip()

    value = ref_text
    if prefix_tmpl:
        # Apòstrofs tipogràfics (’ al signat, ' a la plantilla): comparació 1:1 en minúscules, tall sobre l'original
        idx = _ap_lower(ref_text).find(_ap_lower(prefix_tmpl))
        if idx >= 0:
            value = value[idx + len(prefix_tmpl):]
        else:
            # Prefix absent: la veritat és el paràgraf sencer amb confiança 0,3 (capçalera diferent, variant de
            # l'Eva, castellà…). Excepció: les variables on l'Eva OMET la frase sencera (`location_sentence`, 6/7
            # signats): sense prefix ni sufix no trivial, absent, no un paràgraf equivocat («…presentarà les
            # següents característiques:»).
            if var_name in _ABSENT_IF_PREFIX_MISSING and not (
                len(suffix_tmpl) > 2 and _ap_lower(suffix_tmpl) in _ap_lower(ref_text)
            ):
                return None, 0.0
            return value.strip() or None, 0.3

    if suffix_tmpl:
        # Sufix curt («.»): la PRIMERA ocurrència després del prefix (abans, l'última: en un paràgraf de cinc frases
        # el forat s'enduia les quatre frases següents). Sufix llarg: l'última, com sempre.
        hay, needle = _ap_lower(value), _ap_lower(suffix_tmpl)
        idx = hay.find(needle) if len(suffix_tmpl) <= 2 else hay.rfind(needle)
        if idx >= 0:
            value = value[:idx]

    value = value.strip()
    if not value:
        return None, 0.0

    confidence = 0.9 if prefix_tmpl or suffix_tmpl else 0.7
    return value, confidence


def _extract_multi_vars(template_text: str, var_names: list[str],
                        ref_text: str) -> dict[str, tuple[str | None, float]]:
    """Extract multiple variables from a single paragraph using regex groups.

    Builds a regex from the static parts between {{ var }} placeholders.
    """
    results: dict[str, tuple[str | None, float]] = {}

    skeleton = JINJA_ANY_RE.sub('', template_text).strip()
    if not skeleton:
        for v in var_names:
            results[v] = (None, 0.0)
        return results

    cleaned = template_text
    for tag in JINJA_ANY_RE.findall(template_text):
        if not JINJA_VAR_RE.search(tag):
            cleaned = cleaned.replace(tag, '', 1)

    ordered_vars = []
    remaining = cleaned
    while True:
        m = JINJA_VAR_RE.search(remaining)
        if not m:
            break
        ordered_vars.append(m.group(1))
        remaining = remaining[m.end():]

    if not ordered_vars:
        for v in var_names:
            results[v] = (None, 0.0)
        return results

    pattern_parts = []
    pos = 0
    for var in ordered_vars:
        var_pattern = re.compile(
            r'\{\{[-\s]*' + re.escape(var) + r'\s*(?:\|[^}]*)?\s*\}\}'
        )
        m = var_pattern.search(cleaned, pos)
        if m is None:
            continue
        static_before = cleaned[pos:m.start()]
        static_clean = JINJA_ANY_RE.sub('', static_before).strip()
        if static_clean:
            pattern_parts.append(re.escape(static_clean))
        pattern_parts.append('(.+?)')
        pos = m.end()

    trailing = JINJA_ANY_RE.sub('', cleaned[pos:]).strip()
    if trailing:
        pattern_parts.append(re.escape(trailing))
    else:
        if pattern_parts and pattern_parts[-1] == '(.+?)':
            pattern_parts[-1] = '(.+)'

    if not pattern_parts:
        for v in var_names:
            results[v] = (None, 0.0)
        return results

    regex_str = r'\s*'.join(pattern_parts)
    try:
        match = re.search(regex_str, ref_text, re.IGNORECASE | re.DOTALL)
    except re.error:
        for v in var_names:
            results[v] = (None, 0.0)
        return results

    if match:
        for i, var in enumerate(ordered_vars):
            if i < len(match.groups()):
                val = match.group(i + 1).strip()
                results[var] = (val if val else None, 0.75)
            else:
                results[var] = (None, 0.0)
    else:
        for var in ordered_vars:
            results[var] = (None, 0.3)

    for v in var_names:
        if v not in results:
            results[v] = (None, 0.0)

    return results


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def find_reference_report(project_path: Path) -> Path | None:
    """Find the reference report file in a project directory.

    Tries known filenames first, then common patterns.
    """
    project_path = Path(project_path)
    folder_name = project_path.name

    if folder_name in KNOWN_REPORTS:
        candidate = project_path / KNOWN_REPORTS[folder_name]
        if candidate.exists():
            return candidate

    expedient = folder_name.split()[0] if ' ' in folder_name else folder_name
    patterns = [
        f"{expedient}_informe.docx",
        f"{expedient}_informe.doc",
        f"{expedient}_informe_v0.doc",
        f"{expedient}_informe_V0.doc",
        f"{expedient}_informe_DETALLAT.doc",
    ]
    for pat in patterns:
        candidate = project_path / pat
        if candidate.exists():
            return candidate

    return None


def convert_doc_to_docx(doc_path: Path) -> Path:
    """Convert a .doc file to .docx using LibreOffice headless mode.

    Returns the path to the converted .docx file in a temp directory.
    """
    doc_path = Path(doc_path)
    if doc_path.suffix.lower() == '.docx':
        return doc_path

    tmpdir = tempfile.mkdtemp(prefix="g3dt_ref_")
    result = subprocess.run(
        [
            "libreoffice", "--headless", "--convert-to", "docx",
            "--outdir", tmpdir, str(doc_path),
        ],
        check=True,
        capture_output=True,
        timeout=60,
    )
    converted = Path(tmpdir) / doc_path.with_suffix('.docx').name
    if not converted.exists():
        raise FileNotFoundError(
            f"LibreOffice conversion produced no output: {converted}\n"
            f"stdout: {result.stdout.decode()}\nstderr: {result.stderr.decode()}"
        )
    return converted


def _table_label_fingerprint(table) -> str:
    """Primera cel·la (l'ETIQUETA) de les tres primeres files amb contingut, sense Jinja (bloc 3, 2026-09-07).

    La fila sencera barreja etiqueta i VALOR: a Anciles «n.º de plantas previstas | 5 viviendas con pb + 1pp + bc …»
    s'assemblava menys a «nº de plantes per habitatge | » que la taula CTE («tipo de edificación considerada: | c-1»),
    i `superficie_parcela` valia «T-1» i `plantes` «C-1». Les etiquetes soles («n.º de plantas previstas | superficie
    de la parcela (m2) | superficie construida total (m2)») s'assemblen a les de la plantilla en qualsevol idioma.
    """
    labels = []
    for row in table.rows:
        if not row.cells:
            continue
        text = JINJA_ANY_RE.sub('', row.cells[0].text).strip()
        if text:
            labels.append(normalize_text(text))
        if len(labels) == 3:
            break
    return " | ".join(labels)


def match_tables(template_doc, ref_doc) -> dict[int, int]:
    """Match template tables to reference tables by header fingerprint similarity.

    Puntuació = màxim entre la primera fila sencera (com sempre) i les etiquetes de la primera columna
    (`_table_label_fingerprint`, bloc 3). Returns {template_table_idx: reference_table_idx}.
    """
    tmpl_fps = [(_table_fingerprint(t), _table_label_fingerprint(t)) for t in template_doc.tables]
    ref_fps = [(_table_fingerprint(t), _table_label_fingerprint(t)) for t in ref_doc.tables]
    # Assignació GLOBAL per puntuació descendent (bloc 3, 2026-09-07), no cobdiciosa en ordre de plantilla: abans t5
    # (sondeig) s'enduia la taula SPT dels projectes sense sondeig (Rubí, Linyola, Alcoletge: 0,33) i t6 quedava sense o
    # agafava la de signatures; a Vilanova t5 prenia la geotècnica. Llindar 0,4 (era 0,3): els aparellaments bons
    # puntuen ≥ 0,66; els dolents ≤ 0,38.
    pairs = []
    for ti, (tfp, tlab) in enumerate(tmpl_fps):
        if not tfp:
            continue
        for ri, (rfp, rlab) in enumerate(ref_fps):
            if not rfp:
                continue
            score = text_similarity(tfp, rfp)
            if tlab and rlab:
                score = max(score, text_similarity(tlab, rlab))
            pairs.append((score, ti, ri))
    mapping: dict[int, int] = {}
    used_ref: set[int] = set()
    for score, ti, ri in sorted(pairs, key=lambda p: (-p[0], p[1], p[2])):
        if score < 0.4:
            break
        if ti in mapping or ri in used_ref:
            continue
        mapping[ti] = ri
        used_ref.add(ri)
        logger.debug("Table match: tmpl t%d → ref t%d (score=%.2f)", ti, ri, score)
    return mapping


def _single_var_prefix(template_text: str, active_vars: list[str]) -> str:
    """Text fix (≥ 3 paraules) davant de l'únic forat del paràgraf; '' si no n'hi ha."""
    if len(active_vars) != 1:
        return ""
    pattern = re.compile(
        r'\{\{[-\s]*' + re.escape(active_vars[0]) + r'\s*(?:\|[^}]*)?\s*\}\}'
    )
    parts = pattern.split(template_text, maxsplit=1)
    if len(parts) != 2:
        return ""
    prefix = JINJA_ANY_RE.sub('', parts[0]).strip()
    return prefix if len(prefix.split()) >= 3 else ""


def _anchor_paragraph(tp: TemplateParagraph, tmpl_paras: list[TemplateParagraph], ref_body: list[str],
                      tmpl_body_count: int) -> int | None:
    """Índex a `ref_body` del paràgraf que segueix l'àncora (el paràgraf fix anterior de la plantilla, ≥ 3 paraules,
    trobat al signat amb similitud ≥ 0,6 i, en empat, el més proper en posició relativa). None si no hi ha àncora."""
    anchor_text = ""
    for prev in reversed(tmpl_paras[:tp.idx]):
        if prev.idx >= tmpl_body_count:
            continue
        if not prev.text.strip():
            continue                       # blancs entremig: d'acord
        txt = JINJA_ANY_RE.sub('', prev.text).strip()
        # Bloc 3 (2026-09-07): l'àncora pot ser un paràgraf AMB forat si el seu esquelet té ≥ 3 paraules («Qa=
        # {{ qa_value }} Kg/cm2 amb un factor de seguretat inclòs de F=3» precedeix «{{ settlement_sentence }}»,
        # que queia a None). L'esquelet es localitza al signat per similitud com un paràgraf fix.
        if prev.is_static and len(txt.split()) >= 3:
            anchor_text = txt
        elif len(txt.split()) >= 6 and not _looks_like_heading(txt):
            anchor_text = txt              # («{{ section_empentes_num }}. EMPENTES DE TERRES» NO és àncora)
        break                              # el primer paràgraf no buit ha de ser l'àncora; si no, no n'hi ha
    if not anchor_text:
        return None
    pos_t = tp.idx / max(1, tmpl_body_count)
    scored = [(text_similarity(anchor_text, rt), -abs(ri / max(1, len(ref_body)) - pos_t), ri)
              for ri, rt in enumerate(ref_body) if rt]
    if not scored:
        return None
    score, _, ri = max(scored)
    if score < 0.6:
        return None
    for nxt in range(ri + 1, min(ri + 6, len(ref_body))):
        txt = (ref_body[nxt] or "").strip()
        if not txt:
            continue
        # el següent paràgraf ha de ser una FRASE, no una capçalera («2.1. DESCRIPCIÓ…», «4.1. GEOLOGIA»)
        return None if _looks_like_heading(txt) else nxt
    return None


_HEADING_RE = re.compile(r"^\d+(\.\d+)*\.?\s+\S")


def _looks_like_heading(text: str) -> bool:
    t = text.strip()
    if len(t.split()) < 4:
        return True
    if _HEADING_RE.match(t) and len(t.split()) <= 8:
        return True
    letters = [c for c in t if c.isalpha()]
    return bool(letters) and sum(c.isupper() for c in letters) / len(letters) > 0.8


def extract_body_variables(
    tmpl_paras: list[TemplateParagraph],
    ref_paras: list[str],
    tmpl_body_count: int,
    ref_body_count: int,
    ref_coords_map: dict[int, TableCoords],
) -> tuple[dict[str, ExtractedVariable], list[str]]:
    """Extract variable values from body paragraphs by matching template to reference.

    Returns (variables_dict, warnings_list).
    """
    variables: dict[str, ExtractedVariable] = {}
    warnings: list[str] = []

    ref_body = ref_paras[:ref_body_count]

    for tp in tmpl_paras:
        if tp.idx >= tmpl_body_count:
            break
        if tp.is_static or not tp.variables:
            continue

        active_vars = [v for v in tp.variables if not _should_skip_variable(v)]
        if not active_vars:
            continue

        skeleton = JINJA_ANY_RE.sub('', tp.text).strip()
        pos_t = tp.idx / max(1, tmpl_body_count)
        by_anchor = False
        best_score = 0.0
        best_ref_idx = -1
        best_ref_text = ""
        if skeleton:
            # Prefix primer (2026-09-06, `docs/ANALISI-NARRATIVA-2026-09-06.md` §2.2): si el paràgraf de la plantilla té
            # un sol forat amb text fix al davant, el paràgraf del signat que CONTÉ aquest prefix mana sobre la similitud
            # de l'esquelet; si n'hi ha més d'un (la frase de l'estructura surt a 3.5 i a 4.3), el més proper en POSICIÓ
            # relativa dins del document. Abans, «L'edificació que es preveu construir es situarà {{ location_sentence }}.»
            # s'alineava amb «…presentarà les següents característiques:» (7/7 projectes) amb confiança 0,2.
            candidates = list(range(len(ref_body)))
            prefix_tmpl = _single_var_prefix(tp.text, active_vars)
            by_prefix = False
            if prefix_tmpl:
                with_prefix = [ri for ri, rt in enumerate(ref_body)
                               if rt and normalize_text(prefix_tmpl) in normalize_text(rt)]
                if not with_prefix and len(prefix_tmpl.split()) > 5:
                    head = " ".join(prefix_tmpl.split()[:5])     # «Segons el projecte executiu es preveu» (d'estructures)
                    with_prefix = [ri for ri, rt in enumerate(ref_body)
                                   if rt and normalize_text(head) in normalize_text(rt)]
                if with_prefix:
                    by_prefix = True
                    # primer els paràgrafs que COMENCEN pel prefix (o pel seu cap), després el més proper en posició
                    _needle = normalize_text(prefix_tmpl if any(
                        normalize_text(prefix_tmpl) in normalize_text(ref_body[ri]) for ri in with_prefix)
                        else " ".join(prefix_tmpl.split()[:5]))
                    candidates = [min(with_prefix, key=lambda ri: (
                        0 if normalize_text(ref_body[ri]).startswith(_needle) else 1,
                        abs(ri / max(1, len(ref_body)) - pos_t)))]
            for ri in candidates:
                rt = ref_body[ri]
                if not rt:
                    continue
                score = text_similarity(skeleton, rt)
                if score > best_score:
                    best_score = score
                    best_ref_idx = ri
                    best_ref_text = rt
            if by_prefix and best_ref_idx >= 0:
                # el prefix hi és: el paràgraf pot ser molt més llarg que l'esquelet (bloc de la descripció del solar)
                best_score = max(best_score, 0.5)

        if best_score < 0.5 and len(active_vars) == 1:
            # Sense esquelet («{{ site_condition }}», «{{ radon_sentence }}», «{{ settlement_sentence }}») o sense cap
            # paràgraf prou semblant: ÀNCORA = el paràgraf fix anterior de la plantilla, localitzat al signat; la
            # veritat és el paràgraf no buit que el segueix (2026-09-06).
            anchored = _anchor_paragraph(tp, tmpl_paras, ref_body, tmpl_body_count)
            if anchored is not None:
                best_ref_idx, best_ref_text, best_score = anchored, ref_body[anchored], max(best_score, 0.5)
                by_anchor = True

        if best_score < 0.5:
            for v in active_vars:
                if v not in variables:
                    warnings.append(
                        f"p{tp.idx:03d}: No match for '{v}' "
                        f"(best_score={best_score:.2f}, skeleton='{skeleton[:60]}...')"
                    )
            continue

        elem_id = f"p{tp.idx:03d}"

        if len(active_vars) == 1:
            var_name = active_vars[0]
            value, confidence = _extract_single_var(tp.text, var_name, best_ref_text)
            if value is not None and var_name not in variables:
                variables[var_name] = ExtractedVariable(
                    value=value,
                    position=elem_id,
                    position_description=f"Body paragraph {tp.idx}",
                    confidence=confidence * best_score,
                    extraction_method="paragraph_anchor" if by_anchor else "paragraph_single",
                    template_text=tp.text[:200],
                    reference_text=best_ref_text[:200],
                )
        else:
            multi = _extract_multi_vars(tp.text, active_vars, best_ref_text)
            for var_name, (value, conf) in multi.items():
                if value is not None and var_name not in variables:
                    variables[var_name] = ExtractedVariable(
                        value=value,
                        position=elem_id,
                        position_description=f"Body paragraph {tp.idx}",
                        confidence=conf * best_score,
                        extraction_method="paragraph_multi",
                        template_text=tp.text[:200],
                        reference_text=best_ref_text[:200],
                    )

    return variables, warnings


def extract_table_variables(
    tmpl_doc,
    ref_doc,
    table_map: dict[int, int],
    tmpl_paras: list[TemplateParagraph],
    tmpl_body_count: int,
    tmpl_coords_map: dict[int, TableCoords],
) -> tuple[dict[str, ExtractedVariable], list[str]]:
    """Extract single-variable table cells (non-loop) from reference tables.

    Returns (variables_dict, warnings_list).
    """
    variables: dict[str, ExtractedVariable] = {}
    warnings: list[str] = []

    loop_table_indices = set(LOOP_TABLES.keys())

    for flat_idx, coords in tmpl_coords_map.items():
        if flat_idx >= len(tmpl_paras):
            continue
        tp = tmpl_paras[flat_idx]
        if tp.is_static or not tp.variables:
            continue
        if coords.is_merged_duplicate:
            continue
        if coords.table_idx in loop_table_indices:
            continue

        active_vars = [v for v in tp.variables if not _should_skip_variable(v)]
        if not active_vars:
            continue

        ref_table_idx = table_map.get(coords.table_idx)
        if ref_table_idx is None:
            for v in active_vars:
                warnings.append(
                    f"t{coords.table_idx}_r{coords.row_idx}_c{coords.col_idx}: "
                    f"No matching ref table for '{v}'"
                )
            continue

        ref_table = ref_doc.tables[ref_table_idx]
        ref_text = _get_table_cell_text(ref_table, coords.row_idx, coords.col_idx)
        if ref_text is None:
            for v in active_vars:
                warnings.append(
                    f"t{coords.table_idx}_r{coords.row_idx}_c{coords.col_idx}: "
                    f"Cell out of range in ref table for '{v}'"
                )
            continue

        elem_id = _flat_idx_to_elem_id(flat_idx, tmpl_body_count, tmpl_coords_map)

        if len(active_vars) == 1:
            var_name = active_vars[0]
            value = ref_text.strip()
            if value and var_name not in variables:
                variables[var_name] = ExtractedVariable(
                    value=value,
                    position=elem_id,
                    position_description=(
                        f"Table {coords.table_idx}, "
                        f"row {coords.row_idx}, col {coords.col_idx}"
                    ),
                    confidence=0.95,
                    extraction_method="table_cell",
                    template_text=tp.text[:200],
                    reference_text=ref_text[:200],
                )
        else:
            for var_name in active_vars:
                if var_name not in variables:
                    variables[var_name] = ExtractedVariable(
                        value=ref_text.strip() if ref_text.strip() else None,
                        position=elem_id,
                        position_description=(
                            f"Table {coords.table_idx}, "
                            f"row {coords.row_idx}, col {coords.col_idx} (multi-var cell)"
                        ),
                        confidence=0.5,
                        extraction_method="table_cell_multi",
                        template_text=tp.text[:200],
                        reference_text=ref_text[:200],
                    )
                    warnings.append(
                        f"{elem_id}: Multi-var cell, raw text assigned to '{var_name}'"
                    )

    return variables, warnings


def _detect_header_rows(ref_table, col_names: list[str]) -> int:
    """Auto-detect the number of header rows in a reference table.

    Scans from the LAST row backward: data rows have numeric values or
    test IDs. Returns the index of the first data row (= number of header rows).
    """
    num_cols = len(col_names)
    total = len(ref_table.rows)
    if total <= 1:
        return 0

    first_data_row = total
    for row_idx in range(total - 1, -1, -1):
        cells = []
        for ci in range(min(num_cols, len(ref_table.rows[row_idx].cells))):
            text = (_get_table_cell_text(ref_table, row_idx, ci) or "").strip()
            cells.append(text)
        if not any(cells):
            continue
        # Notacions de les taules de l'Eva que SÓN dades (bloc 3, 2026-09-07): «15-R», «38º», «>350», «--». Abans, la fila
        # «2do nivel | 15-R | -- | 2.00 | 0.00 | 38º | >350» d'Anciles comptava 2/7 numèrics (< 30 %) i l'escaneig
        # s'aturava: capçalera = 2 files i la taula geotècnica es quedava amb una sola fila (la del 1er nivell fora).
        numeric_count = sum(
            1 for c in cells
            if c and (re.match(r'^[<>]?[+-]?\d[\d.,/\-\s]*(?:-?R|º|°)?$', c) or c in ("--", "-", "R"))
        )
        id_like = sum(
            1 for c in cells
            if c and re.match(r'^(?:P|S|SPT|MA|TP|MI)-?\d+$', c)   # «N30» de la capçalera NO és un id (bloc 3)
        )
        has_parenthetical = sum(
            1 for c in cells
            if c and re.search(r'\(.*\)', c)
        )
        all_same = len(set(cells)) == 1 and len(cells) > 1

        if all_same or has_parenthetical >= num_cols * 0.3:
            break
        if numeric_count >= num_cols * 0.3 or id_like >= 1:
            first_data_row = row_idx
        else:
            break

    return max(first_data_row, 1) if first_data_row < total else max(total - 1, 1)


def extract_loop_tables(
    ref_doc,
    table_map: dict[int, int],
) -> tuple[dict[str, ExtractedVariable], list[str]]:
    """Extract data from loop tables ({% tr for %} tables).

    Auto-detects header rows in the reference table rather than relying
    on a fixed count, since .doc conversion may produce different row counts.

    Returns (variables_dict, warnings_list).
    """
    variables: dict[str, ExtractedVariable] = {}
    warnings: list[str] = []

    for tmpl_table_idx, loop_def in LOOP_TABLES.items():
        ref_table_idx = table_map.get(tmpl_table_idx)
        if ref_table_idx is None:
            warnings.append(
                f"Loop table t{tmpl_table_idx} ({loop_def['name']}): "
                f"no matching reference table"
            )
            continue

        ref_table = ref_doc.tables[ref_table_idx]
        col_names = loop_def["cols"]
        var_name = loop_def["name"]

        header_rows = _detect_header_rows(ref_table, col_names)

        rows_data: list[dict[str, str]] = []
        for row_idx in range(header_rows, len(ref_table.rows)):
            row = ref_table.rows[row_idx]
            row_dict: dict[str, str] = {}
            all_empty = True
            for ci, col_name in enumerate(col_names):
                text = _get_table_cell_text(ref_table, row_idx, ci)
                val = text.strip() if text else ""
                row_dict[col_name] = val
                if val:
                    all_empty = False
            if all_empty:
                continue
            # Drop rows that are actually column headers (header-detection
            # may underestimate when LibreOffice merges header rows).
            if _is_table_header_row(row_dict):
                logger.debug(
                    "Dropping header-row contamination from %s row %d: %s",
                    var_name, row_idx, row_dict,
                )
                continue
            rows_data.append(row_dict)

        if rows_data:
            variables[var_name] = ExtractedVariable(
                value=rows_data,
                position=f"t{tmpl_table_idx}",
                position_description=f"Loop table {tmpl_table_idx} ({var_name})",
                confidence=0.85,
                extraction_method="loop_table",
                template_text=f"Loop: {col_names}",
                reference_text=f"{len(rows_data)} data rows",
            )
        else:
            warnings.append(
                f"Loop table t{tmpl_table_idx} ({var_name}): "
                f"no data rows found (ref table has {len(ref_table.rows)} rows, "
                f"detected header_rows={header_rows})"
            )

    return variables, warnings


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def extract_reference_values(
    reference_path: Path,
    template_path: Path | None = None,
    project_name: str = "",
) -> ExtractionResult:
    """Extract all variable values from a reference report.

    Args:
        reference_path: Path to the reference .doc/.docx file.
        template_path: Path to the Jinja template. Defaults to the project template.
        project_name: Project name for the output. Derived from path if empty.

    Returns:
        ExtractionResult with all extracted variables.
    """
    from docx import Document

    reference_path = Path(reference_path)
    if template_path is None:
        template_path = DEFAULT_TEMPLATE
    template_path = Path(template_path)

    if not project_name:
        project_name = reference_path.parent.name

    result = ExtractionResult(
        project=project_name,
        source_file=reference_path.name,
        extraction_date=datetime.now().isoformat(),
        template_file=template_path.name,
    )

    # 1. Convert .doc if needed
    if reference_path.suffix.lower() == '.doc':
        try:
            docx_path = convert_doc_to_docx(reference_path)
            result.warnings.append(f"Converted {reference_path.name} -> .docx")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            result.warnings.append(f"Conversion failed: {e}")
            return result
    else:
        docx_path = reference_path

    # 2. Load template and reference
    tmpl_paras, tmpl_body_count = extract_template_paragraphs(template_path)
    ref_paras, ref_body_count = extract_docx_paragraphs(docx_path)

    tmpl_doc = Document(str(template_path))
    ref_doc = Document(str(docx_path))

    # 3. Build coords maps
    tmpl_coords_map = _build_table_coords_map(tmpl_doc)
    ref_coords_map = _build_table_coords_map(ref_doc)

    # 4. Match tables
    table_map = match_tables(tmpl_doc, ref_doc)
    result.warnings.append(
        f"Table matching: {len(table_map)}/{len(tmpl_doc.tables)} template tables matched"
    )

    # 5. Extract body variables
    body_vars, body_warns = extract_body_variables(
        tmpl_paras, ref_paras, tmpl_body_count, ref_body_count, ref_coords_map,
    )
    result.variables.update(body_vars)
    result.warnings.extend(body_warns)

    # 6. Extract table cell variables
    table_vars, table_warns = extract_table_variables(
        tmpl_doc, ref_doc, table_map,
        tmpl_paras, tmpl_body_count, tmpl_coords_map,
    )
    result.variables.update(table_vars)
    result.warnings.extend(table_warns)

    # 7. Extract loop table variables
    loop_vars, loop_warns = extract_loop_tables(ref_doc, table_map)
    result.variables.update(loop_vars)
    result.warnings.extend(loop_warns)

    # 8. Statistics
    total_tmpl_vars = set()
    for tp in tmpl_paras:
        for v in tp.variables:
            if not _should_skip_variable(v):
                total_tmpl_vars.add(v)

    extracted_count = len(result.variables)
    result.statistics = {
        "total_template_variables": len(total_tmpl_vars),
        "total_extracted": extracted_count,
        "extraction_rate": (
            round(extracted_count / len(total_tmpl_vars) * 100, 1)
            if total_tmpl_vars else 0
        ),
        "by_method": {},
        "body_paragraphs": {"template": tmpl_body_count, "reference": ref_body_count},
        "tables": {
            "template": len(tmpl_doc.tables),
            "reference": len(ref_doc.tables),
            "matched": len(table_map),
        },
    }
    for ev in result.variables.values():
        method = ev.extraction_method
        result.statistics["by_method"][method] = (
            result.statistics["by_method"].get(method, 0) + 1
        )

    # 8.5. Flatten nested loop-table rows to top-level concept_ids
    # (e.g. geotech_rows[0].E -> geomech_E). Positional extraction wins;
    # this only fills gaps. Must run BEFORE statistics so by_method counts.
    _flatten_loop_table_concepts(result, ref_paras)

    # Re-tally statistics so flatten contributions are reflected.
    extracted_count = len(result.variables)
    result.statistics["total_extracted"] = extracted_count
    result.statistics["extraction_rate"] = (
        round(extracted_count / result.statistics["total_template_variables"] * 100, 1)
        if result.statistics["total_template_variables"] else 0
    )
    result.statistics["by_method"] = {}
    for ev in result.variables.values():
        method = ev.extraction_method
        result.statistics["by_method"][method] = (
            result.statistics["by_method"].get(method, 0) + 1
        )

    # 9. Architect-vs-client conflation guard (post-processing)
    _guard_architect_client_conflation(result)

    return result


# ---------------------------------------------------------------------------
# Flatten nested loop-table rows to flat concept_ids
# ---------------------------------------------------------------------------

# Mapping: flat concept_id -> (loop_table_var, row index, source column)
# Eva's geotechnical column names differ from our concept names in one case:
# the table column is "density" (densitat) but the canonical concept is
# "geomech_gamma" (γ, peso específico). They are synonyms in geotechnics.
_GEOTECH_FLATTEN: tuple[tuple[str, str], ...] = (
    ("geomech_E", "E"),
    ("geomech_phi", "phi"),
    ("geomech_cohesion", "cohesion"),
    ("geomech_gamma", "density"),
)


def _clean_phi_value(val: Any) -> Any:
    """Strip the trailing degree symbol from a phi value (e.g. `38º` -> `38`).

    Preserves the original type if non-string.
    """
    if not isinstance(val, str):
        return val
    cleaned = val.strip().rstrip("º°").strip()
    return cleaned if cleaned else val


def _flatten_loop_table_concepts(result: ExtractionResult, ref_paras: list[str] | None = None) -> None:
    """Derive flat concept_ids from the bearing row of nested loop tables.

    Adds (when not already present):
    - geomech_E, geomech_phi, geomech_cohesion, geomech_gamma
      from `geotech_rows[-1]` (bearing stratum — last row in Eva's tables;
      see docs/INVESTIGACIO-GEOMECH-STRATUM.md)
    - cota_referencia from `dpsh_tests[0].cota` (project reference cota)

    Existing flat keys are preserved (positional extraction wins; this is
    a fallback). Header-like values are skipped defensively.
    """
    variables = result.variables

    # 1. Flatten geotech_rows[-1] (bearing stratum). Eva always reports
    #    geomech_* parameters from the bearing layer (the level the
    #    foundation rests on), which by her shallowest-to-deepest convention
    #    is the LAST row. For single-layer profiles row[-1] == row[0].
    geotech_ev = variables.get("geotech_rows")
    if geotech_ev is not None and isinstance(geotech_ev.value, list) and geotech_ev.value:
        n_rows = len(geotech_ev.value)
        # Bloc 3 (2026-09-07): la fila portant és la que el signat DECLARA a la frase de la tensió («…recolzada sobre
        # els materials del segon nivell sanejat, es podrà adoptar una tensió de treball de:»); abans, l'última fila
        # (Vilanova recolza al 2n de 2: bé; però la regla no ho SABIA) o la primera (veritats d'abril: Alcoletge X).
        rule_idx = bearing_row_from_text(ref_paras or [], n_rows)
        bearing_idx = rule_idx if rule_idx is not None else n_rows - 1
        if rule_idx is not None and "bearing_layer_idx" not in variables:
            variables["bearing_layer_idx"] = ExtractedVariable(
                value=rule_idx,
                position=f"{geotech_ev.position}.row{rule_idx}",
                position_description="Nivell portant declarat a la frase de la tensió admissible/de treball del signat",
                confidence=0.9,
                extraction_method="bearing_rule",
                template_text="",
                reference_text=_bearing_sentence(ref_paras or [])[:200],
            )
        bearing_row = geotech_ev.value[bearing_idx]
        if isinstance(bearing_row, dict) and not _is_table_header_row(bearing_row):
            for flat_concept, src_col in _GEOTECH_FLATTEN:
                if flat_concept in variables:
                    continue
                raw = bearing_row.get(src_col)
                if raw is None:
                    continue
                if isinstance(raw, str) and (
                    not raw.strip() or _is_strict_header_cell(raw)
                ):
                    continue
                # Values stay as strings to round-trip prefixed sentinels like
                # ">500" / ">350" without information loss.
                cleaned = _clean_phi_value(raw) if flat_concept == "geomech_phi" else raw
                variables[flat_concept] = ExtractedVariable(
                    value=cleaned,
                    position=f"{geotech_ev.position}.row{bearing_idx}.{src_col}",
                    position_description=(
                        f"Flattened from geotech_rows[{bearing_idx}] "
                        f"(bearing stratum).{src_col}"
                    ),
                    confidence=0.95,
                    extraction_method="table_flatten",
                    template_text="",
                    reference_text=str(raw),
                )

    # 2. Flatten dpsh_tests[0].cota -> cota_referencia.
    dpsh_ev = variables.get("dpsh_tests")
    if (
        dpsh_ev is not None
        and isinstance(dpsh_ev.value, list)
        and dpsh_ev.value
        and "cota_referencia" not in variables
    ):
        first_dpsh = dpsh_ev.value[0]
        if isinstance(first_dpsh, dict) and not _is_table_header_row(first_dpsh):
            cota = first_dpsh.get("cota")
            if (
                isinstance(cota, str)
                and cota.strip()
                and not _is_strict_header_cell(cota)
            ):
                variables["cota_referencia"] = ExtractedVariable(
                    value=cota.strip(),
                    position=f"{dpsh_ev.position}.row0.cota",
                    position_description=(
                        "Flattened from first DPSH test elevation"
                    ),
                    confidence=0.9,
                    extraction_method="table_flatten",
                    template_text="",
                    reference_text=str(cota),
                )

    # 3. Bloc 3 (2026-09-07): `spt_ma_tests[0]` → `spt_test_id`, `spt_location`, `spt_depth_range`, `spt_n30`,
    #    `spt_lithology` (la fila que el generador imprimeix com a escalars; abans eren cel·les soles de la plantilla).
    spt_ev = variables.get("spt_ma_tests")
    if spt_ev is not None and isinstance(spt_ev.value, list) and spt_ev.value:
        first_spt = spt_ev.value[0]
        if isinstance(first_spt, dict) and not _is_table_header_row(first_spt):
            for col in ("test_id", "location", "depth_range", "n30", "lithology"):
                key = f"spt_{col}"
                raw = first_spt.get(col)
                if key in variables or not isinstance(raw, str) or not raw.strip() or _is_strict_header_cell(raw):
                    continue
                variables[key] = ExtractedVariable(
                    value=raw.strip(),
                    position=f"{spt_ev.position}.row0.{col}",
                    position_description="Flattened from first SPT/MA row",
                    confidence=0.9,
                    extraction_method="table_flatten",
                    template_text="",
                    reference_text=raw,
                )


_TENSION_RE = re.compile(r"tensi[oó]n?\s+(?:de\s+treball|admissible|de\s+trabajo|admisible)\s+de\s*:", re.I)
_ORDINAL_LEVEL_RE = re.compile(
    r"\b(primer|1er|1r|segon|2on|2n|segundo|2do|2º|tercer|3er|3r|tercero|quart|4t|cuarto|4to)\s+nivell?\b", re.I)
_ORDINALS = {"primer": 1, "1er": 1, "1r": 1, "segon": 2, "2on": 2, "2n": 2, "segundo": 2, "2do": 2, "2º": 2,
             "tercer": 3, "3er": 3, "3r": 3, "tercero": 3, "quart": 4, "4t": 4, "cuarto": 4, "4to": 4}


def _bearing_sentence(ref_paras: list[str]) -> str:
    """El paràgraf del signat que acaba amb «…tensió de treball/admissible de:» (7/7 signats en porten un)."""
    for p in ref_paras:
        if p and _TENSION_RE.search(p):
            return p
    return ""


def bearing_row_from_text(ref_paras: list[str], n_rows: int) -> int | None:
    """Índex (0-based) de la fila de la taula geotècnica on recolza la fonamentació segons el signat, o None.

    Regla (bloc 3, 2026-09-07; verificada als 7 signats): a la frase de la tensió, l'ÚLTIM ordinal de nivell mana
    («un cop superats els materials del primer nivell … recolzada sobre els materials del segon nivell sanejat» → 2);
    sense ordinal, «substrat/sustrato» = l'última fila (Castellar: «encastada … en els materials de substrat»).
    Fora de rang (ordinal > files) → None (mai s'inventa una fila).
    """
    sent = _bearing_sentence(ref_paras)
    if not sent or n_rows <= 0:
        return None
    ords = [_ORDINALS[m.group(1).lower()] for m in _ORDINAL_LEVEL_RE.finditer(sent)]
    if ords:
        idx = ords[-1] - 1
        return idx if 0 <= idx < n_rows else None
    if re.search(r"substrat|sustrato", sent, re.I):
        return n_rows - 1
    return None


# ---------------------------------------------------------------------------
# Post-processing guards
# ---------------------------------------------------------------------------

# Pattern matching the body sentence "Sr. X en nom propi..." that the report
# template tucks into the architect slot when the project is owner-built. The
# real architect_name lives on the plànol caixetí, NOT in this body sentence.
_BODY_SR_PATTERN = re.compile(r"^(?:Sr|Sra|D|Dna)\.\s+\S+", re.IGNORECASE)


def _guard_architect_client_conflation(result: ExtractionResult) -> None:
    """Flag suspicious architect_name values that look like client/sol·licitant.

    Two heuristics:
    1. architect_name == client_name (case-insensitive, trimmed): likely an
       owner-built project. We keep the value but emit a warning so a reviewer
       verifies against the plànol caixetí.
    2. architect_name matches the body-sentence pattern ("Sr. X ...") or
       contains "en nom propi": the extractor picked up the sol·licitant
       sentence rather than the caixetí. Set confidence to 0 to signal low
       trust, but keep the raw value for inspection.
    """
    def _norm(v: Any) -> str:
        return str(v).strip().lower() if v is not None else ""

    client_val = _norm(
        result.variables["client_name"].value
        if "client_name" in result.variables else ""
    )

    for arch_key in ("architect_name", "architect_name_upper"):
        if arch_key not in result.variables:
            continue
        ev = result.variables[arch_key]
        arch_val = _norm(ev.value)
        if not arch_val:
            continue

        # Heuristic 1: equality with client.
        if client_val and arch_val == client_val:
            warning = (
                f"{arch_key} == client_name; likely owner-built project — "
                "verify caixetí of plànol manually"
            )
            if warning not in result.warnings:
                result.warnings.append(warning)

        # Heuristic 2: body-sentence pattern.
        raw_val = str(ev.value or "").strip()
        looks_like_body_sentence = (
            bool(_BODY_SR_PATTERN.match(raw_val))
            or "en nom propi" in arch_val
        )
        if looks_like_body_sentence:
            warning = (
                f"{arch_key} matches body-sentence pattern ('Sr. X' / 'en nom "
                "propi'); likely sol·licitant, not architect — confidence "
                "lowered, verify caixetí of plànol"
            )
            if warning not in result.warnings:
                result.warnings.append(warning)
            ev.confidence = 0.0


# ---------------------------------------------------------------------------
# Merge with prior reference JSON (preserve external-method entries)
# ---------------------------------------------------------------------------

# Methods produced by THIS extractor — authoritative for their own keys. If a
# prior entry uses one of these and the current run no longer emits the key,
# the prior entry is dropped (we deliberately stopped emitting it).
_OWN_EXTRACTION_METHODS = frozenset({
    "paragraph_single",
    "paragraph_anchor", "paragraph_multi",
    "table_cell", "table_cell_multi",
    "loop_table", "table_flatten", "bearing_rule",
})

# Methods produced by external tools we don't control (e.g. a one-off LLM pass
# that filled in concepts the positional extractor can't recover: free-text
# paragraphs, formatted lists, narrative summaries). These entries MUST be
# preserved on re-extraction — otherwise they vanish silently.
_EXTERNAL_EXTRACTION_METHODS = frozenset({
    "intelligent_analysis",
})


def _merge_with_prior(new_result: ExtractionResult, prior_path: Path) -> None:
    """Preserve prior entries with an external extraction_method.

    Re-extraction is otherwise destructive for concepts our positional
    extractor can't recover (free-text paragraphs like `conclusions_*`,
    `site_description`, `materials_intro`). Those entries are produced by an
    external `intelligent_analysis` pass and must round-trip across runs.

    Rules:
    - If the new run emitted the same key, NEW WINS (fresher positional data) — except when the new entry comes
      from the anchor fallback (`paragraph_anchor`, 2026-09-06) and the prior is external: the anchor is a weaker
      signal than an `intelligent_analysis` value, so the prior wins.
    - If the new run did NOT emit the key AND prior method is external,
      preserve verbatim.
    - If the new run did NOT emit the key AND prior method is one of OUR own
      methods, drop it (the new code path is authoritative; absence is
      deliberate).
    - If the new run did NOT emit the key AND prior method is unknown,
      preserve it (safe default — protect against future external sources).

    The merge is IDEMPOTENT: a second call with the same prior file produces
    the same result as the first.
    """
    if not prior_path.is_file():
        return
    try:
        prior = json.loads(prior_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(
            "Could not load prior reference values for merge (%s): %s",
            prior_path, exc,
        )
        return

    prior_vars = prior.get("variables", {})
    if not isinstance(prior_vars, dict):
        return

    preserved_keys: list[str] = []
    for k, entry in prior_vars.items():
        if k in new_result.variables:
            new_method = new_result.variables[k].extraction_method
            prior_method = entry.get("extraction_method") if isinstance(entry, dict) else None
            if new_method != "paragraph_anchor" or prior_method not in _EXTERNAL_EXTRACTION_METHODS:
                continue
            # àncora contra extern: l'extern mana (cau al bloc de preservació de sota)
        if not isinstance(entry, dict):
            continue
        method = entry.get("extraction_method", "")
        # Drop entries produced by our own (now-superseded) code path.
        if method in _OWN_EXTRACTION_METHODS:
            continue

        # Preserve external entries (and unknown methods, defensively).
        try:
            new_result.variables[k] = ExtractedVariable(
                value=entry.get("value"),
                position=entry.get("position", ""),
                position_description=entry.get("position_description", ""),
                confidence=float(entry.get("confidence", 0.0) or 0.0),
                extraction_method=method or "intelligent_analysis",
                template_text=entry.get("template_text", "") or "",
                reference_text=entry.get("reference_text", "") or "",
            )
            preserved_keys.append(k)
        except (TypeError, ValueError) as exc:
            logger.warning(
                "Could not preserve prior entry %s (%s); skipping",
                k, exc,
            )

    if preserved_keys:
        new_result.warnings.append(
            f"Merged {len(preserved_keys)} prior external-method entries: "
            + ", ".join(sorted(preserved_keys)[:8])
            + ("..." if len(preserved_keys) > 8 else "")
        )


def _recompute_statistics(result: ExtractionResult) -> None:
    """Recompute total_extracted / extraction_rate / by_method after a merge."""
    extracted_count = len(result.variables)
    result.statistics["total_extracted"] = extracted_count
    total_tmpl = result.statistics.get("total_template_variables", 0) or 0
    result.statistics["extraction_rate"] = (
        round(extracted_count / total_tmpl * 100, 1) if total_tmpl else 0
    )
    by_method: dict[str, int] = {}
    for ev in result.variables.values():
        m = ev.extraction_method
        by_method[m] = by_method.get(m, 0) + 1
    result.statistics["by_method"] = by_method


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def _result_to_dict(result: ExtractionResult) -> dict:
    """Convert ExtractionResult to a JSON-serializable dict."""
    out = {
        "project": result.project,
        "source_file": result.source_file,
        "extraction_date": result.extraction_date,
        "template_file": result.template_file,
        "extractor_version": VERSION,
        "statistics": result.statistics,
        "variables": {},
        "warnings": result.warnings,
    }
    for k, ev in sorted(result.variables.items()):
        out["variables"][k] = {
            "value": ev.value,
            "position": ev.position,
            "position_description": ev.position_description,
            "confidence": round(ev.confidence, 3),
            "extraction_method": ev.extraction_method,
            "template_text": ev.template_text,
            "reference_text": ev.reference_text,
        }
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _process_project(project_path: Path, template_path: Path | None = None) -> ExtractionResult | None:
    """Process a single project: find report, extract, save JSON."""
    ref_file = find_reference_report(project_path)
    if ref_file is None:
        logger.warning("No reference report found in %s", project_path)
        return None

    logger.info("Processing %s -> %s", project_path.name, ref_file.name)
    result = extract_reference_values(
        ref_file,
        template_path=template_path,
        project_name=project_path.name,
    )

    out_dir = project_path / "validation"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / "eva_reference_values.json"

    # Merge any prior external-method entries (e.g. intelligent_analysis from
    # one-off LLM extractions) BEFORE writing. Preserves Eva ground-truth that
    # our positional extractor can't recover.
    _merge_with_prior(result, out_file)
    _recompute_statistics(result)

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(_result_to_dict(result), f, ensure_ascii=False, indent=2)

    logger.info(
        "  -> %d variables extracted (%.1f%%), saved to %s",
        len(result.variables),
        result.statistics.get("extraction_rate", 0),
        out_file,
    )
    return result


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    if len(sys.argv) > 1:
        target = Path(sys.argv[1])
        if target.is_dir():
            result = _process_project(target)
        elif target.is_file():
            project_path = target.parent
            result = extract_reference_values(
                target, project_name=project_path.name
            )
            if result:
                out_dir = project_path / "validation"
                out_dir.mkdir(exist_ok=True)
                out_file = out_dir / "eva_reference_values.json"
                _merge_with_prior(result, out_file)
                _recompute_statistics(result)
                with open(out_file, "w", encoding="utf-8") as f:
                    json.dump(_result_to_dict(result), f, ensure_ascii=False, indent=2)
                logger.info(
                    "Extracted %d variables -> %s",
                    len(result.variables), out_file,
                )
        else:
            logger.error("Path not found: %s", target)
            sys.exit(1)
    else:
        logger.info("Processing all known projects in %s", REFERENCE_DIR)
        for folder_name in sorted(KNOWN_REPORTS.keys()):
            project_path = REFERENCE_DIR / folder_name
            if project_path.is_dir():
                _process_project(project_path)
            else:
                logger.warning("Directory not found: %s", project_path)


if __name__ == "__main__":
    main()
