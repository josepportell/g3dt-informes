#!/usr/bin/env python3
"""
Intelligent Audit: Template-aware comparison of generated vs reference reports.

Prepares structured data for Claude Code to evaluate semantically.
Unlike highlight_report.py (SequenceMatcher), this understands which
Jinja template variables produced each paragraph.

Usage:
    python3 -m automation.intelligent_audit \
        reference-material/4001612-bell-lloc/4001612_generated.docx \
        reference-material/4001612-bell-lloc/4001612_informe.docx

    # Or with explicit project path and user data:
    python3 -m automation.intelligent_audit \
        path/to/generated.docx path/to/reference.docx \
        --project-path reference-material/4001612-bell-lloc \
        --user-data reference-material/4001612-bell-lloc/user_data.json

Output:
    {project_path}/validation/audit_intelligent.json

Author: Eficients.cat
Date: 2026-02-08
"""

import json
import logging
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Jinja2 patterns in template text
JINJA_VAR_RE = re.compile(r'\{\{[-\s]*(\w[\w.]*)\s*(?:\|[^}]*)?\s*\}\}')
JINJA_BLOCK_RE = re.compile(r'\{%[-\s]*(if|elif|else|endif|for|endfor)\s*(.*?)\s*%\}')
JINJA_ANY_RE = re.compile(r'\{\{.*?\}\}|\{%.*?%\}')


@dataclass
class TableCoords:
    """Structured coordinates for a paragraph inside a table cell."""
    table_idx: int
    row_idx: int
    col_idx: int
    para_idx_in_cell: int       # 0 for first paragraph in cell
    is_merged_duplicate: bool   # True if cell is a repeated merged cell ref


def _build_table_coords_map(doc) -> dict[int, TableCoords]:
    """Build a mapping from flat paragraph index to TableCoords.

    Iterates tables in the same order as extract_docx_paragraphs() —
    table → row → cell → paragraph — so flat indices match.
    Uses id(cell._tc) to detect merged cell duplicates within each row.
    """
    body_count = len(doc.paragraphs)
    coords_map: dict[int, TableCoords] = {}
    flat_idx = body_count

    for table_idx, table in enumerate(doc.tables):
        for row_idx, row in enumerate(table.rows):
            seen_in_row: set[int] = set()
            for col_idx, cell in enumerate(row.cells):
                tc_id = id(cell._tc)
                is_dup = tc_id in seen_in_row
                seen_in_row.add(tc_id)
                for p_local, _p in enumerate(cell.paragraphs):
                    coords_map[flat_idx] = TableCoords(
                        table_idx=table_idx,
                        row_idx=row_idx,
                        col_idx=col_idx,
                        para_idx_in_cell=p_local,
                        is_merged_duplicate=is_dup,
                    )
                    flat_idx += 1

    return coords_map


def _flat_idx_to_elem_id(idx: int, body_count: int,
                         table_coords_map: dict[int, TableCoords]) -> str:
    """Convert a flat paragraph index to a stable elem_id string.

    Body paragraphs: p{idx:03d}
    Table cells: t{table}_r{row}_c{col}  (+ _p{n} if multi-paragraph cell)
    """
    if idx < body_count:
        return f"p{idx:03d}"

    coords = table_coords_map.get(idx)
    if coords is None:
        return f"p{idx:03d}"

    base = f"t{coords.table_idx}_r{coords.row_idx}_c{coords.col_idx}"
    if coords.para_idx_in_cell > 0:
        base += f"_p{coords.para_idx_in_cell}"
    return base


JINJA_TR_FOR_RE = re.compile(r'\{%[-\s]*tr\s+for\s+', re.IGNORECASE)
JINJA_TR_ENDFOR_RE = re.compile(r'\{%[-\s]*tr\s+endfor', re.IGNORECASE)


def _build_loop_column_map(
    template_paras: list,  # list[TemplateParagraph]
    tmpl_body_count: int,
    tmpl_table_coords: dict[int, 'TableCoords'],
) -> dict[tuple[int, int], 'TemplateParagraph']:
    """Build a map of (table_idx, col_idx) → TemplateParagraph for loop variables.

    Scans template table cells for {%tr for %} blocks. For each loop,
    finds the data row with {{ variable }} tags and maps each column
    to its TemplateParagraph. This allows generated cells inside expanded
    loops to be matched to the correct template variables even though
    positional alignment is off.
    """
    loop_map: dict[tuple[int, int], TemplateParagraph] = {}

    # Group template table cells by (table_idx, row_idx)
    rows_by_table: dict[int, dict[int, list[tuple[int, int, TemplateParagraph]]]] = {}
    for flat_idx, coords in tmpl_table_coords.items():
        if flat_idx >= len(template_paras):
            continue
        tp = template_paras[flat_idx]
        t = coords.table_idx
        r = coords.row_idx
        if t not in rows_by_table:
            rows_by_table[t] = {}
        if r not in rows_by_table[t]:
            rows_by_table[t][r] = []
        rows_by_table[t][r].append((coords.col_idx, flat_idx, tp))

    # For each table, find {%tr for%} rows and the variable row after them
    for table_idx, rows in rows_by_table.items():
        sorted_rows = sorted(rows.keys())
        for i, row_idx in enumerate(sorted_rows):
            cells = rows[row_idx]
            # Check if any cell in this row has {%tr for %}
            has_tr_for = any(
                JINJA_TR_FOR_RE.search(tp.text) for _, _, tp in cells
            )
            if not has_tr_for:
                continue
            # Find the next row(s) that have {{ variable }} tags
            for j in range(i + 1, len(sorted_rows)):
                next_row_idx = sorted_rows[j]
                next_cells = rows[next_row_idx]
                # Check if any cell has Jinja variables
                has_vars = any(
                    tp.variables for _, _, tp in next_cells
                )
                if has_vars:
                    # Map (table_idx, col_idx) → TemplateParagraph
                    for col_idx, flat_idx, tp in next_cells:
                        if tp.variables or not tp.is_static:
                            loop_map[(table_idx, col_idx)] = tp
                    break
                # Check if this is {%tr endfor %} — stop searching
                has_endfor = any(
                    JINJA_TR_ENDFOR_RE.search(tp.text) for _, _, tp in next_cells
                )
                if has_endfor:
                    break

    return loop_map


@dataclass
class TemplateParagraph:
    """A paragraph from the template with its Jinja metadata."""
    idx: int
    text: str
    variables: list[str] = field(default_factory=list)
    has_conditionals: bool = False
    is_static: bool = True  # No Jinja tags at all


@dataclass
class AuditParagraph:
    """A paragraph comparison triple for audit."""
    idx: int
    template_text: str
    template_variables: list[str]
    variable_values: dict[str, str]
    generated_text: str
    reference_text: str
    classification: str  # static_match, likely_correct, needs_review, missing, extra
    match_ratio: float = 0.0
    notes: str = ""


@dataclass
class AuditResult:
    """Complete audit result."""
    generated_file: str
    reference_file: str
    template_file: str
    audit_date: str
    static_paragraphs: list[dict] = field(default_factory=list)
    dynamic_paragraphs: list[dict] = field(default_factory=list)
    missing_in_generated: list[dict] = field(default_factory=list)
    extra_in_generated: list[dict] = field(default_factory=list)
    statistics: dict = field(default_factory=dict)


def extract_docx_paragraphs(docx_path: Path) -> tuple[list[str], int]:
    """Extract all paragraph texts from a .docx file (body + tables).

    Returns (paragraphs, body_count) where body_count is len(doc.paragraphs).
    Table paragraphs start at index body_count.
    """
    from docx import Document
    doc = Document(str(docx_path))
    paragraphs = []

    for p in doc.paragraphs:
        text = p.text.strip()
        paragraphs.append(text)

    body_count = len(paragraphs)

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    text = p.text.strip()
                    paragraphs.append(text)

    return paragraphs, body_count


def extract_template_paragraphs(template_path: Path) -> tuple[list[TemplateParagraph], int]:
    """
    Extract paragraphs from a Jinja-enabled .docx template.

    Finds {{ variable }} and {% if/for %} blocks in each paragraph.
    Note: docxtpl templates store Jinja tags in the raw XML, so we read
    the raw XML to find them, then map back to paragraph text.
    """
    from docx import Document
    import zipfile

    # First, get the rendered paragraph texts (what docx shows)
    doc = Document(str(template_path))
    result = []

    # Also read raw XML to find Jinja tags that may be split across runs
    raw_xml = ""
    with zipfile.ZipFile(str(template_path), 'r') as z:
        if 'word/document.xml' in z.namelist():
            raw_xml = z.read('word/document.xml').decode('utf-8')

    # Extract all paragraphs from the document body
    for i, p in enumerate(doc.paragraphs):
        text = p.text.strip()
        # Find Jinja variables in this paragraph's text
        variables = JINJA_VAR_RE.findall(text)
        has_conditionals = bool(JINJA_BLOCK_RE.search(text))
        has_any_jinja = bool(JINJA_ANY_RE.search(text))

        result.append(TemplateParagraph(
            idx=i,
            text=text,
            variables=variables,
            has_conditionals=has_conditionals,
            is_static=not has_any_jinja and not variables and not has_conditionals,
        ))

    body_count = len(result)

    # Also check table cells
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    text = p.text.strip()
                    variables = JINJA_VAR_RE.findall(text)
                    has_conditionals = bool(JINJA_BLOCK_RE.search(text))
                    has_any_jinja = bool(JINJA_ANY_RE.search(text))
                    idx = len(result)
                    result.append(TemplateParagraph(
                        idx=idx,
                        text=text,
                        variables=variables,
                        has_conditionals=has_conditionals,
                        is_static=not has_any_jinja and not variables and not has_conditionals,
                    ))

    return result, body_count


def normalize_text(text: str) -> str:
    """Normalize text for comparison: lowercase, collapse whitespace, normalize quotes."""
    text = text.strip().lower()
    text = re.sub(r'\s+', ' ', text)
    text = text.replace('\u2018', "'").replace('\u2019', "'")
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    return text


def text_similarity(a: str, b: str) -> float:
    """Calculate similarity ratio between two texts. Uses autojunk=False to avoid the Catalan text bug."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    na = normalize_text(a)
    nb = normalize_text(b)
    if na == nb:
        return 1.0
    return SequenceMatcher(None, na, nb, autojunk=False).ratio()


def find_best_match(text: str, candidates: list[str], threshold: float = 0.3) -> tuple[int, float]:
    """
    Find the best matching candidate for a text.

    Returns (index, similarity_ratio). Returns (-1, 0.0) if no match above threshold.
    """
    if not text.strip():
        return -1, 0.0

    best_idx = -1
    best_ratio = 0.0
    norm = normalize_text(text)

    for i, candidate in enumerate(candidates):
        if not candidate.strip():
            continue
        cn = normalize_text(candidate)

        # Quick length filter
        if len(norm) > 0 and len(cn) > 0:
            ratio = len(norm) / len(cn)
            if ratio > 5.0 or ratio < 0.2:
                continue

        sim = SequenceMatcher(None, norm, cn, autojunk=False).ratio()
        if sim > best_ratio:
            best_ratio = sim
            best_idx = i
        if sim >= 0.98:
            break

    if best_ratio >= threshold:
        return best_idx, best_ratio
    return -1, 0.0


def get_template_context(project_path: Path, user_data_path: Path | None = None) -> dict[str, Any]:
    """
    Build the template context by reusing ReportGenerator._build_template_context().

    Returns dict of all template variable names -> rendered values.
    """
    try:
        from .report_generator import ReportGenerator

        user_data = str(user_data_path) if user_data_path else None
        gen = ReportGenerator(
            project_path=str(project_path),
            user_data=user_data,
        )
        gen.extract_project_data()
        gen.build_report_data()
        sections = gen.generate_sections()
        context = gen._build_template_context(sections)

        # Flatten context: convert non-string values to string representations
        flat = {}
        for k, v in context.items():
            if isinstance(v, str):
                flat[k] = v
            elif isinstance(v, (int, float)):
                flat[k] = str(v)
            elif isinstance(v, bool):
                flat[k] = str(v)
            elif isinstance(v, list):
                flat[k] = json.dumps(v, ensure_ascii=False)
            elif isinstance(v, dict):
                flat[k] = json.dumps(v, ensure_ascii=False)
            elif v is None:
                flat[k] = ''
            else:
                flat[k] = str(v)
        return flat
    except Exception as e:
        logger.warning("Could not build template context: %s", e)
        return {}


def render_template_text(template_text: str, context: dict[str, str]) -> str:
    """
    Simple rendering of a template paragraph by replacing {{ var }} with values.

    This is a rough approximation (not full Jinja2) for comparison purposes.
    """
    def replace_var(match):
        var_name = match.group(1).strip()
        # Handle dotted access (e.g., project.client_name)
        return context.get(var_name, match.group(0))

    rendered = JINJA_VAR_RE.sub(replace_var, template_text)
    # Remove conditional blocks for comparison (they'd be evaluated)
    rendered = JINJA_BLOCK_RE.sub('', rendered)
    rendered = re.sub(r'\s+', ' ', rendered).strip()
    return rendered


def build_template_manifest(template_path: Path) -> dict:
    """Build a manifest decomposing each template paragraph into sub-elements.

    For each paragraph (body + table), splits text on Jinja tags to produce
    typed segments (static, variable, conditional) with stable sub-element IDs.

    Returns a dict suitable for JSON serialization.
    """
    from docx import Document

    doc = Document(str(template_path))
    body_count = len(doc.paragraphs)

    # Build table coords for the template itself
    tmpl_table_coords = _build_table_coords_map(doc)

    paragraphs_manifest: dict[str, dict] = {}

    def _decompose_paragraph(text: str, elem_id: str, idx: int,
                             location: str, coords: TableCoords | None):
        """Decompose a single paragraph into sub-element segments."""
        variables = JINJA_VAR_RE.findall(text)
        has_any_jinja = bool(JINJA_ANY_RE.search(text))
        is_static = not has_any_jinja and not variables

        # Split on Jinja tags, keeping the delimiters
        segments = re.split(r'(\{\{.*?\}\}|\{%.*?%\})', text)
        elements = []
        seg_counter = 0
        for seg in segments:
            seg_stripped = seg.strip()
            if not seg_stripped:
                continue
            var_match = JINJA_VAR_RE.match(seg_stripped)
            block_match = JINJA_BLOCK_RE.match(seg_stripped)
            if var_match:
                var_name = var_match.group(1).strip()
                elements.append({
                    'id': f"{elem_id}_v{seg_counter}",
                    'type': 'variable',
                    'var': var_name,
                })
            elif block_match:
                elements.append({
                    'id': f"{elem_id}_b{seg_counter}",
                    'type': 'conditional',
                    'text': seg_stripped,
                })
            else:
                elements.append({
                    'id': f"{elem_id}_s{seg_counter}",
                    'type': 'static',
                    'text': seg,
                })
            seg_counter += 1

        entry: dict = {
            'idx': idx,
            'location': location,
            'is_static': is_static,
            'variables': variables,
            'elements': elements,
        }
        if coords is not None:
            entry['table'] = coords.table_idx
            entry['row'] = coords.row_idx
            entry['col'] = coords.col_idx

        paragraphs_manifest[elem_id] = entry

    # Process body paragraphs
    for i, p in enumerate(doc.paragraphs):
        text = p.text.strip()
        elem_id = f"p{i:03d}"
        _decompose_paragraph(text, elem_id, i, 'body', None)

    # Process table paragraphs
    flat_idx = body_count
    for table_idx, table in enumerate(doc.tables):
        for row_idx, row in enumerate(table.rows):
            seen_in_row: set[int] = set()
            for col_idx, cell in enumerate(row.cells):
                tc_id = id(cell._tc)
                is_dup = tc_id in seen_in_row
                seen_in_row.add(tc_id)
                for p_local, p in enumerate(cell.paragraphs):
                    coords = TableCoords(
                        table_idx=table_idx, row_idx=row_idx,
                        col_idx=col_idx, para_idx_in_cell=p_local,
                        is_merged_duplicate=is_dup,
                    )
                    elem_id = _flat_idx_to_elem_id(flat_idx, body_count,
                                                   {flat_idx: coords})
                    text = p.text.strip()
                    _decompose_paragraph(text, elem_id, flat_idx, 'table', coords)
                    flat_idx += 1

    return {
        'template_file': template_path.name,
        'body_count': body_count,
        'total_paragraphs': flat_idx,
        'paragraphs': paragraphs_manifest,
    }


def classify_paragraph(
    template_para: TemplateParagraph,
    generated_text: str,
    reference_text: str,
    context: dict[str, str],
) -> tuple[str, float, float, str]:
    """
    Classify a paragraph alignment.

    Returns (classification, match_ratio, ref_match_ratio, notes).
    ref_match_ratio is the generated<->reference similarity, used for coloring.
    """
    # Empty paragraphs
    if not template_para.text and not generated_text:
        return 'static_match', 1.0, 1.0, 'Both empty'

    # Static template text (no Jinja variables)
    if template_para.is_static:
        gen_sim = text_similarity(template_para.text, generated_text)
        ref_sim = text_similarity(generated_text, reference_text)

        if gen_sim >= 0.95:
            return 'static_match', gen_sim, ref_sim, 'Static template text matches'
        elif ref_sim >= 0.90:
            return 'static_match', ref_sim, ref_sim, 'Matches reference'
        elif gen_sim >= 0.70:
            return 'likely_correct', gen_sim, ref_sim, f'Static text partial match ({gen_sim:.0%})'
        else:
            return 'needs_review', gen_sim, ref_sim, f'Static text diverges from template ({gen_sim:.0%})'

    # Dynamic template text (has Jinja variables)
    # Try to render the template with known values
    expected_text = render_template_text(template_para.text, context)

    # Compare generated vs expected
    gen_expected_sim = text_similarity(generated_text, expected_text)

    # Compare generated vs reference
    gen_ref_sim = text_similarity(generated_text, reference_text)

    # All variable values present in generated text?
    all_values_present = True
    missing_values = []
    for var in template_para.variables:
        value = context.get(var, '')
        if value and value not in generated_text:
            all_values_present = False
            missing_values.append(f'{var}={value!r}')

    if gen_expected_sim >= 0.90 and gen_ref_sim >= 0.90:
        return 'likely_correct', gen_ref_sim, gen_ref_sim, 'Matches both expected and reference'
    elif gen_expected_sim >= 0.90:
        if gen_ref_sim >= 0.60:
            return 'likely_correct', gen_expected_sim, gen_ref_sim, 'Matches expected, reference similar'
        else:
            return 'needs_review', gen_expected_sim, gen_ref_sim, (
                f'Matches expected rendering but differs from reference ({gen_ref_sim:.0%}). '
                f'Possible: input data differs from reference project.'
            )
    elif gen_ref_sim >= 0.90:
        return 'likely_correct', gen_ref_sim, gen_ref_sim, 'Matches reference closely'
    elif all_values_present and gen_ref_sim >= 0.60:
        return 'likely_correct', gen_ref_sim, gen_ref_sim, 'Variable values present, reasonable reference match'
    elif gen_ref_sim >= 0.60 or gen_expected_sim >= 0.60:
        return 'needs_review', max(gen_ref_sim, gen_expected_sim), gen_ref_sim, (
            f'Partial match (gen<->ref: {gen_ref_sim:.0%}, gen<->expected: {gen_expected_sim:.0%})'
        )
    else:
        notes_parts = [f'Low match (gen<->ref: {gen_ref_sim:.0%}, gen<->expected: {gen_expected_sim:.0%})']
        if missing_values:
            notes_parts.append(f'Missing values: {", ".join(missing_values)}')
        return 'needs_review', max(gen_ref_sim, gen_expected_sim), gen_ref_sim, '. '.join(notes_parts)


def align_paragraphs(
    template_paras: list[TemplateParagraph],
    generated_paras: list[str],
    reference_paras: list[str],
    context: dict[str, str],
    gen_body_count: int = 0,
    ref_body_count: int = 0,
    tmpl_body_count: int = 0,
    gen_table_coords: dict[int, TableCoords] | None = None,
    loop_column_map: dict[tuple[int, int], TemplateParagraph] | None = None,
    tmpl_cell_map: dict[tuple[int, int, int], TemplateParagraph] | None = None,
) -> AuditResult:
    """
    Align template, generated, and reference paragraphs and classify each.

    Strategy:
    1. Walk through generated paragraphs sequentially
    2. For body paragraphs: find best match by text similarity (full search)
    3. For table paragraphs (idx >= gen_body_count): SCOPED similarity search
       restricted to only table cells of the other document. This prevents
       short values like "598" or "C-1" from false-matching body text.
    4. Classify each triple
    """
    result = AuditResult(
        generated_file='',
        reference_file='',
        template_file='',
        audit_date=datetime.now().isoformat(),
    )

    # Build template texts for matching (strip Jinja tags for comparison)
    template_clean = []
    template_rendered = []
    for tp in template_paras:
        clean = JINJA_ANY_RE.sub('', tp.text).strip()
        clean = re.sub(r'\s+', ' ', clean)
        template_clean.append(clean)
        # Build rendered version: substitute {{ var }} with context values
        rendered = tp.text
        for var in tp.variables:
            val = str(context.get(var, ''))
            rendered = re.sub(r'\{\{\s*' + re.escape(var) + r'\s*\}\}', val, rendered)
        rendered = JINJA_ANY_RE.sub('', rendered).strip()
        rendered = re.sub(r'\s+', ' ', rendered)
        template_rendered.append(rendered)

    # Track which reference paragraphs have been matched
    ref_matched = set()

    for gen_idx, gen_text in enumerate(generated_paras):
        if not gen_text:
            continue

        is_table = gen_body_count > 0 and gen_idx >= gen_body_count

        if is_table:
            # Match generated table cells to template cells using coordinates.
            # Priority: 1) coordinate-based, 2) loop column map, 3) flat offset
            template_para = TemplateParagraph(
                idx=-1, text='', variables=[], has_conditionals=False, is_static=True
            )

            # 1st: Try coordinate-based lookup (table_idx, row_idx, col_idx)
            if tmpl_cell_map and gen_table_coords:
                coords = gen_table_coords.get(gen_idx)
                if coords:
                    tp = tmpl_cell_map.get((coords.table_idx, coords.row_idx, coords.col_idx))
                    if tp:
                        template_para = tp

            # 2nd: If coord lookup gave empty/static, try loop column map
            if (template_para.is_static and not template_para.text.strip()
                    and loop_column_map and gen_table_coords):
                coords = gen_table_coords.get(gen_idx)
                if coords:
                    loop_tp = loop_column_map.get(
                        (coords.table_idx, coords.col_idx)
                    )
                    if loop_tp:
                        template_para = loop_tp

            # 3rd: Fallback to flat offset if nothing else matched
            if template_para.idx == -1 and not template_para.text:
                table_rel_idx = gen_idx - gen_body_count
                tmpl_table_idx = tmpl_body_count + table_rel_idx
                if tmpl_table_idx < len(template_paras):
                    template_para = template_paras[tmpl_table_idx]

            # Reference: scoped similarity (ref may have different table structure)
            ref_table_slice = reference_paras[ref_body_count:]
            ref_rel_idx, ref_sim = find_best_match(gen_text, ref_table_slice, threshold=0.25)
            if ref_rel_idx >= 0:
                ref_abs_idx = ref_body_count + ref_rel_idx
                ref_text = reference_paras[ref_abs_idx]
                ref_matched.add(ref_abs_idx)
            else:
                ref_text = ''
        else:
            # SIMILARITY matching for body paragraphs
            tmpl_idx, tmpl_sim = find_best_match(gen_text, template_clean, threshold=0.25)
            # Fallback: try rendered template text for pure-variable paragraphs
            if tmpl_sim < 0.7:
                rend_idx, rend_sim = find_best_match(gen_text, template_rendered, threshold=0.25)
                if rend_sim > tmpl_sim:
                    tmpl_idx, tmpl_sim = rend_idx, rend_sim
            template_para = template_paras[tmpl_idx] if tmpl_idx >= 0 else TemplateParagraph(
                idx=-1, text='', variables=[], has_conditionals=False, is_static=True
            )

            ref_idx, ref_sim = find_best_match(gen_text, reference_paras, threshold=0.25)
            ref_text = reference_paras[ref_idx] if ref_idx >= 0 else ''
            if ref_idx >= 0:
                ref_matched.add(ref_idx)

        # Get variable values for this template paragraph
        var_values = {}
        for var in template_para.variables:
            var_values[var] = context.get(var, '')

        # Classify
        classification, match_ratio, ref_match_ratio, notes = classify_paragraph(
            template_para, gen_text, ref_text, context
        )

        elem_id = _flat_idx_to_elem_id(
            gen_idx, gen_body_count, gen_table_coords or {}
        )

        para_dict = {
            'idx': gen_idx,
            'elem_id': elem_id,
            'template_text': template_para.text,
            'template_variables': template_para.variables,
            'variable_values': var_values,
            'generated_text': gen_text,
            'reference_text': ref_text,
            'classification': classification,
            'match_ratio': round(match_ratio, 3),
            'ref_match_ratio': round(ref_match_ratio, 3),
            'notes': notes,
        }

        if classification == 'static_match':
            result.static_paragraphs.append(para_dict)
        elif classification in ('likely_correct', 'needs_review'):
            result.dynamic_paragraphs.append(para_dict)

    # Find reference paragraphs not matched by any generated paragraph
    # Secondary sweep: check for false positives where the reference text
    # IS present in the generated doc but wasn't claimed by the 1:1 alignment
    for ref_idx, ref_text in enumerate(reference_paras):
        if ref_idx not in ref_matched and ref_text.strip():
            ref_norm = normalize_text(ref_text)

            # Check 1: Is ref_text a high-similarity match to any generated paragraph?
            found = False
            for gen_text in generated_paras:
                if not gen_text.strip():
                    continue
                gen_norm = normalize_text(gen_text)

                # Exact or near-exact containment (ref is substring of gen)
                if ref_norm in gen_norm:
                    found = True
                    break

                # High similarity (>= 70%) with relaxed length filter
                if len(ref_norm) > 10 and len(gen_norm) > 10:
                    sim = SequenceMatcher(None, ref_norm, gen_norm, autojunk=False).ratio()
                    if sim >= 0.70:
                        found = True
                        break

            if not found:
                result.missing_in_generated.append({
                    'ref_idx': ref_idx,
                    'elem_id': f"ref_{ref_idx:03d}",
                    'reference_text': ref_text,
                    'notes': 'Present in reference but not found in generated report',
                })

    # Statistics
    total = len([p for p in generated_paras if p.strip()])
    static_count = len(result.static_paragraphs)
    likely_count = len([p for p in result.dynamic_paragraphs if p['classification'] == 'likely_correct'])
    review_count = len([p for p in result.dynamic_paragraphs if p['classification'] == 'needs_review'])
    missing_count = len(result.missing_in_generated)

    result.statistics = {
        'total_generated': total,
        'static_match': static_count,
        'likely_correct': likely_count,
        'needs_review': review_count,
        'missing_in_generated': missing_count,
        'auto_resolved_pct': round((static_count + likely_count) / max(total, 1) * 100, 1),
    }

    return result


# ============================================================================
# Highlighted .docx generation
# ============================================================================

# Color scheme (hex RGB for w:shd fill, no # prefix):
#   Green   = static template text (boilerplate, not modified per project)
#   Cyan    = perfect match with reference (dynamic content, correct)
#   Yellow  = match >= 90% with reference
#   Purple  = match funcional >= 70% (user called it "light-orange")
#   Lilac   = templates regionals / geologia
#   Pink    = pendent Eva (data discrepancy: gen correct per variables but differs from ref)
#   Red     = error or missing content

COLOR_HEX = {
    'green':  '92D050',  # Bright green
    'cyan':   '00B0F0',  # Cyan / light blue
    'yellow': 'FFFF00',  # Yellow
    'purple': '602A80',  # User-provided hex for >70% match
    'lilac':  'A56CB9',  # User-provided hex for regional templates
    'pink':   'FF00FF',  # Magenta / pink
    'red':    'FF0000',  # Red
}

# After LLM review, these override the color
LLM_CLASSIFICATION_COLORS = {
    'CORRECTE': 'cyan',
    'FORMAT_DIFF': 'yellow',
    'DADES_ERRÒNIES': 'pink',
    'TEMPLATE_ERROR': 'red',
    'INCERT': 'purple',
}

LEGEND_ITEMS_AUDIT = [
    ('green',  "VERD — Text fix de plantilla (boilerplate, no modificat per projecte)."),
    ('cyan',   "CIAN — Match perfecte: contingut dinàmic correcte, coincideix amb referència."),
    ('yellow', "GROC — Match >= 90%: contingut correcte amb diferències mínimes."),
    ('purple', "PORPRA — Match funcional >= 70%: contingut similar amb diferències notables."),
    ('lilac',  "LILA — Templates regionals / descripcions geològiques (depenen de la zona)."),
    ('pink',   "ROSA — Discrepància de dades: el generat és correcte segons les nostres variables, però difereix de la referència. VERIFICAR."),
    ('red',    "VERMELL — Error, contingut absent, o línia que falta al generat."),
]


def _get_color_category(info: dict) -> str:
    """
    Determine the color category for a paragraph based on audit info.

    Returns one of: green, cyan, yellow, purple, lilac, pink, red
    """
    # LLM classification overrides everything
    llm_class = info.get('llm_classification', '')
    if llm_class and llm_class in LLM_CLASSIFICATION_COLORS:
        return LLM_CLASSIFICATION_COLORS[llm_class]

    classification = info.get('classification', '')
    match_ratio = info.get('match_ratio', 0.0)
    # ref_match_ratio is the gen<->ref similarity, more useful for coloring
    ref_mr = info.get('ref_match_ratio', match_ratio)
    ref_text = info.get('reference_text', '')
    gen_text = info.get('generated_text', '')

    # Static template text → green
    if classification == 'static_match':
        return 'green'

    # Dynamic content: use ref_match_ratio for color decisions
    # (match_ratio may be inflated by gen<->expected similarity)
    if classification == 'likely_correct':
        if ref_mr >= 0.95:
            return 'cyan'   # Perfect match with reference
        if ref_mr >= 0.90:
            return 'yellow'  # Very good match
        if ref_mr >= 0.70:
            return 'yellow'  # Reasonable match
        # Gen matches expected but ref differs → data discrepancy
        if ref_text and gen_text:
            return 'pink'
        return 'yellow'

    if classification == 'needs_review':
        if ref_mr >= 0.90:
            return 'yellow'
        if ref_mr >= 0.70:
            return 'purple'
        if ref_mr >= 0.40:
            return 'purple'
        return 'red'

    return 'red'


def _insert_marker_run(paragraph, marker_text: str):
    """Prepend a grey 7pt marker run like [p054] at the start of a paragraph."""
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    r = OxmlElement("w:r")
    rPr = OxmlElement("w:rPr")
    # 7pt font size
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), "14")  # half-points
    szCs = OxmlElement("w:szCs")
    szCs.set(qn("w:val"), "14")
    rPr.append(sz)
    rPr.append(szCs)
    # Grey color
    color_elem = OxmlElement("w:color")
    color_elem.set(qn("w:val"), "888888")
    rPr.append(color_elem)
    r.append(rPr)

    t_elem = OxmlElement("w:t")
    t_elem.text = f"[{marker_text}] "
    t_elem.set(qn("xml:space"), "preserve")
    r.append(t_elem)

    # Insert at the beginning of the paragraph (before existing runs)
    first_run = paragraph._element.find(qn("w:r"))
    if first_run is not None:
        first_run.addprevious(r)
    else:
        paragraph._element.append(r)


def generate_highlighted_docx(
    generated_path: Path,
    audit_data: dict,
    output_path: Path,
) -> Path:
    """
    Generate a color-coded .docx from audit results.

    Colors each paragraph using w:shd (shading) for custom hex colors.
    Adds annotations for non-green paragraphs. Inserts legend and statistics.
    Inserts RED notes for missing paragraphs from the reference.
    """
    from docx import Document
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    from docx.shared import Pt

    doc = Document(str(generated_path))

    # Save original body count BEFORE legend/annotations inflate doc.paragraphs
    original_body_count = len(doc.paragraphs)

    # Build lookup: paragraph_idx → full audit info
    para_lookup: dict[int, dict] = {}

    for p in audit_data.get('static_paragraphs', []):
        para_lookup[p['idx']] = p

    for p in audit_data.get('dynamic_paragraphs', []):
        para_lookup[p['idx']] = p

    # Build list of missing paragraphs for insertion
    missing_paras = audit_data.get('missing_in_generated', [])

    # Stats counters
    stats = {k: 0 for k in COLOR_HEX}
    stats['none'] = 0

    def _shd_all_runs(paragraph, hex_color: str):
        """Apply shading (background color) to all runs in a paragraph."""
        all_r = paragraph._element.findall(".//" + qn("w:r"))
        for r_elem in all_r:
            rPr = r_elem.find(qn("w:rPr"))
            if rPr is None:
                rPr = OxmlElement("w:rPr")
                r_elem.insert(0, rPr)
            # Remove existing shading
            old_shd = rPr.find(qn("w:shd"))
            if old_shd is not None:
                rPr.remove(old_shd)
            shd = OxmlElement("w:shd")
            shd.set(qn("w:val"), "clear")
            shd.set(qn("w:color"), "auto")
            shd.set(qn("w:fill"), hex_color)
            rPr.append(shd)

    def _insert_annotation(paragraph, text: str):
        """Insert a small red italic annotation after the paragraph."""
        new_p = OxmlElement("w:p")
        pPr = OxmlElement("w:pPr")
        spacing = OxmlElement("w:spacing")
        spacing.set(qn("w:before"), "0")
        spacing.set(qn("w:after"), "40")
        pPr.append(spacing)
        new_p.append(pPr)

        r = OxmlElement("w:r")
        rPr = OxmlElement("w:rPr")
        rPr.append(OxmlElement("w:i"))
        sz = OxmlElement("w:sz")
        sz.set(qn("w:val"), "16")
        szCs = OxmlElement("w:szCs")
        szCs.set(qn("w:val"), "16")
        rPr.append(sz)
        rPr.append(szCs)
        color_elem = OxmlElement("w:color")
        color_elem.set(qn("w:val"), "FF0000")
        rPr.append(color_elem)
        r.append(rPr)

        t_elem = OxmlElement("w:t")
        t_elem.text = text
        t_elem.set(qn("xml:space"), "preserve")
        r.append(t_elem)
        new_p.append(r)
        paragraph._element.addnext(new_p)

    def _insert_missing_note(paragraph, ref_text: str):
        """Insert a red-background note for a missing paragraph from the reference."""
        new_p = OxmlElement("w:p")
        pPr = OxmlElement("w:pPr")
        spacing = OxmlElement("w:spacing")
        spacing.set(qn("w:before"), "60")
        spacing.set(qn("w:after"), "60")
        pPr.append(spacing)
        # Paragraph-level red shading
        pShd = OxmlElement("w:shd")
        pShd.set(qn("w:val"), "clear")
        pShd.set(qn("w:color"), "auto")
        pShd.set(qn("w:fill"), "FF0000")
        pPr.append(pShd)
        new_p.append(pPr)

        r = OxmlElement("w:r")
        rPr = OxmlElement("w:rPr")
        rPr.append(OxmlElement("w:b"))
        sz = OxmlElement("w:sz")
        sz.set(qn("w:val"), "18")
        szCs = OxmlElement("w:szCs")
        szCs.set(qn("w:val"), "18")
        rPr.append(sz)
        rPr.append(szCs)
        fc = OxmlElement("w:color")
        fc.set(qn("w:val"), "FFFFFF")
        rPr.append(fc)
        # Run-level shading too
        rShd = OxmlElement("w:shd")
        rShd.set(qn("w:val"), "clear")
        rShd.set(qn("w:color"), "auto")
        rShd.set(qn("w:fill"), "FF0000")
        rPr.append(rShd)
        r.append(rPr)

        truncated = ref_text[:200] + ('...' if len(ref_text) > 200 else '')
        t_elem = OxmlElement("w:t")
        t_elem.text = f"[FALTA A L'INFORME GENERAT] Referència: \"{truncated}\""
        t_elem.set(qn("xml:space"), "preserve")
        r.append(t_elem)
        new_p.append(r)
        paragraph._element.addnext(new_p)

    def _make_legend_element(text: str, fill_hex: str = None,
                             bold: bool = False, size_pt: int = None):
        """Create a w:p element for the legend."""
        p = OxmlElement("w:p")
        r = OxmlElement("w:r")
        rPr = OxmlElement("w:rPr")
        if bold:
            rPr.append(OxmlElement("w:b"))
        if size_pt:
            sz = OxmlElement("w:sz")
            sz.set(qn("w:val"), str(size_pt * 2))
            szCs = OxmlElement("w:szCs")
            szCs.set(qn("w:val"), str(size_pt * 2))
            rPr.append(sz)
            rPr.append(szCs)
        if fill_hex:
            shd = OxmlElement("w:shd")
            shd.set(qn("w:val"), "clear")
            shd.set(qn("w:color"), "auto")
            shd.set(qn("w:fill"), fill_hex)
            rPr.append(shd)
        r.append(rPr)
        t_elem = OxmlElement("w:t")
        t_elem.text = text
        t_elem.set(qn("xml:space"), "preserve")
        r.append(t_elem)
        p.append(r)
        return p

    # ---- Process body paragraphs ----
    annotations_to_insert = []  # (paragraph, annotation_text)
    missing_to_insert = []      # (paragraph, ref_text) — for missing notes

    # Track the last processed paragraph for inserting missing notes nearby
    last_para_by_idx = {}
    for idx, para in enumerate(doc.paragraphs):
        last_para_by_idx[idx] = para
        text = para.text.strip()
        if not text:
            continue

        # Insert marker BEFORE coloring so marker run gets the background too
        _insert_marker_run(para, f"p{idx:03d}")

        info = para_lookup.get(idx)
        if info is None:
            stats['none'] += 1
            continue

        color_cat = _get_color_category(info)
        hex_color = COLOR_HEX.get(color_cat, COLOR_HEX['red'])
        stats[color_cat] = stats.get(color_cat, 0) + 1
        _shd_all_runs(para, hex_color)

        # Add annotation for anything that's not green or cyan
        if color_cat not in ('green', 'cyan'):
            annotation_parts = []
            if info.get('notes'):
                annotation_parts.append(info['notes'])
            if info.get('llm_explanation'):
                annotation_parts.append(info['llm_explanation'])
            # Show reference text for discrepancies (pink)
            if color_cat == 'pink' and info.get('reference_text'):
                ref_preview = info['reference_text'][:100]
                annotation_parts.append(f'Ref: "{ref_preview}"')
            if info.get('variable_values'):
                vars_str = ', '.join(f'{k}={v!r}' for k, v in info['variable_values'].items() if v)
                if vars_str:
                    annotation_parts.append(f'Vars: {vars_str}')
            if annotation_parts:
                annotations_to_insert.append((para, ' | '.join(annotation_parts)))

    # Insert annotations in reverse order
    for para, annotation_text in reversed(annotations_to_insert):
        _insert_annotation(para, f'[AUDIT] {annotation_text}')

    # ---- Insert MISSING paragraph notes ----
    # Try to insert each missing note near where it would appear.
    # Use the ref_idx to find the nearest generated paragraph.
    if missing_paras:
        doc_para_count = original_body_count
        for mp in reversed(missing_paras):  # reverse to preserve positions
            ref_idx = mp.get('ref_idx', -1)
            ref_text = mp.get('reference_text', '')
            if not ref_text.strip():
                continue
            # Find the nearest document paragraph to insert after
            # Use a heuristic: insert near the proportional position
            if doc_para_count > 0 and ref_idx >= 0:
                # Map reference index to generated document position proportionally
                ref_total = audit_data.get('statistics', {}).get('total_generated', doc_para_count)
                approx_pos = min(int(ref_idx / max(ref_total, 1) * doc_para_count), doc_para_count - 1)
                target_para = last_para_by_idx.get(approx_pos)
                if target_para is None:
                    # Fallback: use last paragraph
                    target_para = last_para_by_idx.get(doc_para_count - 1)
                if target_para is not None:
                    _insert_missing_note(target_para, ref_text)

    # ---- Process table cells ----
    # Must iterate without deduplication to match extract_docx_paragraphs(),
    # which visits merged cells multiple times (python-docx returns duplicate
    # cell references for merged cells).
    table_offset = original_body_count
    for table_idx_h, table_h in enumerate(doc.tables):
        for row_idx_h, row_h in enumerate(table_h.rows):
            seen_in_row: set[int] = set()
            for col_idx_h, cell_h in enumerate(row_h.cells):
                cell_tc_id = id(cell_h._tc)
                is_first = cell_tc_id not in seen_in_row
                seen_in_row.add(cell_tc_id)
                for p_local, para in enumerate(cell_h.paragraphs):
                    text = para.text.strip()
                    # Insert marker on first non-merged paragraph of each cell
                    if is_first and p_local == 0 and text:
                        _insert_marker_run(
                            para, f"t{table_idx_h}_r{row_idx_h}_c{col_idx_h}"
                        )
                    info = para_lookup.get(table_offset)
                    if info and text:
                        color_cat = _get_color_category(info)
                        hex_color = COLOR_HEX.get(color_cat, COLOR_HEX['red'])
                        stats[color_cat] = stats.get(color_cat, 0) + 1
                        _shd_all_runs(para, hex_color)
                    table_offset += 1

    # ---- Append statistics and legend at the end ----
    audit_stats = audit_data.get('statistics', {})
    doc.add_paragraph()
    p = doc.add_paragraph()
    run = p.add_run("=" * 70)
    run.font.size = Pt(8)

    p = doc.add_paragraph()
    run = p.add_run("RESUM — AUDIT INTEL·LIGENT")
    run.bold = True
    run.font.size = Pt(12)

    doc.add_paragraph()
    total = audit_stats.get('total_generated', 0)
    missing_count = audit_stats.get('missing_in_generated', 0)

    def _add_stat(label, count, fill_hex=None):
        p = doc.add_paragraph()
        pct = f"{count / total * 100:.1f}%" if total > 0 else "0%"
        run = p.add_run(f"  {label}: {count}  ({pct})")
        run.font.size = Pt(10)
        if fill_hex:
            # Apply shading to the run
            rPr = run._element.find(qn("w:rPr"))
            if rPr is None:
                rPr = OxmlElement("w:rPr")
                run._element.insert(0, rPr)
            shd = OxmlElement("w:shd")
            shd.set(qn("w:val"), "clear")
            shd.set(qn("w:color"), "auto")
            shd.set(qn("w:fill"), fill_hex)
            rPr.append(shd)

    _add_stat("Verd (static template)", audit_stats.get('static_match', 0), COLOR_HEX['green'])
    _add_stat("Cian (match perfecte)", audit_stats.get('likely_correct', 0), COLOR_HEX['cyan'])
    _add_stat("Groc (match >= 90%)", 0, COLOR_HEX['yellow'])  # counted in needs_review
    _add_stat("Porpra (match >= 70%)", 0, COLOR_HEX['purple'])
    _add_stat("Rosa (discrepància dades)", 0, COLOR_HEX['pink'])
    _add_stat("Cian needs review", audit_stats.get('needs_review', 0), COLOR_HEX['purple'])
    _add_stat("Vermell (error/absent)", missing_count, COLOR_HEX['red'])

    doc.add_paragraph()
    auto_pct = audit_stats.get('auto_resolved_pct', 0)
    p = doc.add_paragraph()
    run = p.add_run(f"Qualitat auto-resolta: {auto_pct}% (verd + cian)")
    run.bold = True
    run.font.size = Pt(11)

    if missing_count > 0:
        p = doc.add_paragraph()
        run = p.add_run(
            f"ATENCIÓ: {missing_count} paràgrafs de la referència NO trobats al generat. "
            f"Busca les notes vermelles [FALTA A L'INFORME GENERAT] al document."
        )
        run.bold = True
        run.font.size = Pt(10)
        # Red shading on the warning
        rPr = run._element.find(qn("w:rPr"))
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), COLOR_HEX['red'])
        rPr.append(shd)
        fc = OxmlElement("w:color")
        fc.set(qn("w:val"), "FFFFFF")
        rPr.append(fc)

    # ---- Append legend ----
    doc.add_paragraph()
    p = doc.add_paragraph()
    run = p.add_run("LLEGENDA DE COLORS — AUDIT INTEL·LIGENT")
    run.bold = True
    run.font.size = Pt(14)

    doc.add_paragraph()
    for color_key, description in LEGEND_ITEMS_AUDIT:
        p = doc.add_paragraph()
        run = p.add_run(f"  {description}")
        run.font.size = Pt(9)
        rPr = run._element.find(qn("w:rPr"))
        if rPr is None:
            rPr = OxmlElement("w:rPr")
            run._element.insert(0, rPr)
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), COLOR_HEX[color_key])
        rPr.append(shd)

    doc.add_paragraph()
    p = doc.add_paragraph()
    run = p.add_run(
        "MARCADORS: [p054] = Paràgraf 54 | [t0_r1_c1] = Taula 0, fila 1, columna 1"
    )
    run.font.size = Pt(9)

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    return output_path


def run_audit(
    generated_path: Path,
    reference_path: Path,
    project_path: Path | None = None,
    user_data_path: Path | None = None,
    template_path: Path | None = None,
    output_path: Path | None = None,
    highlight: bool = True,
) -> dict:
    """
    Run the full intelligent audit pipeline.

    Args:
        generated_path: Path to generated .docx
        reference_path: Path to reference .docx
        project_path: Path to project folder (for template context). Defaults to generated_path.parent
        user_data_path: Path to user_data.json. Defaults to {project_path}/user_data.json
        template_path: Path to Jinja template .docx. Auto-detected if None.
        output_path: Where to save JSON. Defaults to {project_path}/validation/audit_intelligent.json
        highlight: Whether to generate a highlighted .docx (default True)

    Returns:
        The audit result as a dict
    """
    # Resolve paths
    if project_path is None:
        project_path = generated_path.parent

    if user_data_path is None:
        candidate = project_path / 'user_data.json'
        if candidate.exists():
            user_data_path = candidate

    if template_path is None:
        # Search standard locations
        for candidate in [
            project_path / 'templates' / 'g3dt-jinja-template.docx',
            project_path.parent / 'templates' / 'g3dt-jinja-template.docx',
            Path(__file__).parent.parent / 'templates' / 'g3dt-jinja-template.docx',
        ]:
            if candidate.exists():
                template_path = candidate
                break

    if output_path is None:
        output_path = project_path / 'validation' / 'audit_intelligent.json'

    # Validate inputs
    for path, name in [(generated_path, 'generated'), (reference_path, 'reference')]:
        if not path.exists():
            raise FileNotFoundError(f"{name} file not found: {path}")

    print(f"Intelligent Audit")
    print(f"{'=' * 60}")
    print(f"Generated: {generated_path}")
    print(f"Reference: {reference_path}")
    print(f"Template:  {template_path or '(not found)'}")
    print(f"Project:   {project_path}")
    print()

    # Step 1: Extract template paragraphs
    template_paras = []
    tmpl_body_count = 0
    if template_path and template_path.exists():
        print("Extracting template paragraphs...")
        template_paras, tmpl_body_count = extract_template_paragraphs(template_path)
        jinja_count = sum(1 for p in template_paras if not p.is_static)
        print(f"  Total: {len(template_paras)}, with Jinja: {jinja_count}, body: {tmpl_body_count}")
    else:
        print("WARNING: No template found, audit will be limited to gen<->ref comparison")

    # Step 2: Extract generated and reference paragraphs
    print("Extracting generated paragraphs...")
    generated_paras, gen_body_count = extract_docx_paragraphs(generated_path)
    gen_nonempty = sum(1 for p in generated_paras if p.strip())
    print(f"  Total: {len(generated_paras)}, non-empty: {gen_nonempty}, body: {gen_body_count}")

    print("Extracting reference paragraphs...")
    reference_paras, ref_body_count = extract_docx_paragraphs(reference_path)
    ref_nonempty = sum(1 for p in reference_paras if p.strip())
    print(f"  Total: {len(reference_paras)}, non-empty: {ref_nonempty}, body: {ref_body_count}")

    # Step 2b: Build table coordinates map for generated docx
    from docx import Document as _Document
    gen_doc = _Document(str(generated_path))
    gen_table_coords = _build_table_coords_map(gen_doc)
    print(f"  Table coordinates mapped: {len(gen_table_coords)} cells")

    # Step 2c: Build loop column map and cell map from template
    loop_column_map: dict[tuple[int, int], TemplateParagraph] = {}
    tmpl_cell_map: dict[tuple[int, int, int], TemplateParagraph] = {}
    if template_path and template_path.exists() and template_paras:
        tmpl_doc = _Document(str(template_path))
        tmpl_table_coords = _build_table_coords_map(tmpl_doc)
        loop_column_map = _build_loop_column_map(
            template_paras, tmpl_body_count, tmpl_table_coords
        )
        if loop_column_map:
            print(f"  Loop column variables: {len(loop_column_map)} columns")

        # Build tmpl_cell_map: (table_idx, row_idx, col_idx) -> TemplateParagraph
        for flat_idx, coords in tmpl_table_coords.items():
            if flat_idx < len(template_paras):
                tmpl_cell_map[(coords.table_idx, coords.row_idx, coords.col_idx)] = template_paras[flat_idx]
        if tmpl_cell_map:
            print(f"  Template cell map: {len(tmpl_cell_map)} cells")

    # Step 3: Build template context
    print("Building template context...")
    context = get_template_context(project_path, user_data_path)
    print(f"  Variables loaded: {len(context)}")

    # Step 4: Align and classify
    print("Aligning and classifying paragraphs...")
    audit = align_paragraphs(
        template_paras, generated_paras, reference_paras, context,
        gen_body_count=gen_body_count,
        ref_body_count=ref_body_count,
        tmpl_body_count=tmpl_body_count,
        gen_table_coords=gen_table_coords,
        loop_column_map=loop_column_map,
        tmpl_cell_map=tmpl_cell_map,
    )
    audit.generated_file = str(generated_path)
    audit.reference_file = str(reference_path)
    audit.template_file = str(template_path) if template_path else ''

    # Step 5: Save JSON
    output_path.parent.mkdir(parents=True, exist_ok=True)

    result_dict = {
        'generated_file': audit.generated_file,
        'reference_file': audit.reference_file,
        'template_file': audit.template_file,
        'audit_date': audit.audit_date,
        'static_paragraphs': audit.static_paragraphs,
        'dynamic_paragraphs': audit.dynamic_paragraphs,
        'missing_in_generated': audit.missing_in_generated,
        'extra_in_generated': audit.extra_in_generated,
        'statistics': audit.statistics,
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result_dict, f, ensure_ascii=False, indent=2)

    # Step 5b: Build and save template manifest
    if template_path and template_path.exists():
        manifest = build_template_manifest(template_path)
        manifest_path = output_path.parent / 'template_manifest.json'
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        print(f"  Template manifest: {manifest_path}")

    # Step 6: Generate highlighted .docx
    if highlight:
        highlight_path = output_path.parent / (generated_path.stem + '_AUDIT_VISUAL.docx')
        print("Generating highlighted .docx...")
        generate_highlighted_docx(generated_path, result_dict, highlight_path)
        result_dict['highlight_file'] = str(highlight_path)
        print(f"  Highlighted: {highlight_path}")

    # Print summary
    stats = audit.statistics
    print()
    print(f"{'=' * 60}")
    print(f"AUDIT SUMMARY")
    print(f"{'=' * 60}")
    print(f"Total generated (non-empty):  {stats['total_generated']}")
    print(f"  Static match:               {stats['static_match']}")
    print(f"  Likely correct:             {stats['likely_correct']}")
    print(f"  Needs LLM review:           {stats['needs_review']}")
    print(f"  Missing in generated:       {stats['missing_in_generated']}")
    print(f"  Auto-resolved:              {stats['auto_resolved_pct']}%")
    print()
    print(f"Output JSON: {output_path}")
    if highlight:
        print(f"Output DOCX: {result_dict.get('highlight_file', '')}")

    return result_dict


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Intelligent audit: template-aware comparison of generated vs reference reports',
    )
    parser.add_argument('generated', help='Path to generated .docx')
    parser.add_argument('reference', help='Path to reference .docx')
    parser.add_argument('--project-path', '-p', help='Project folder path')
    parser.add_argument('--user-data', '-u', help='Path to user_data.json')
    parser.add_argument('--template', '-t', help='Path to Jinja template .docx')
    parser.add_argument('--output', '-o', help='Output JSON path')
    parser.add_argument('--no-highlight', action='store_true',
                        help='Skip generating highlighted .docx')

    args = parser.parse_args()

    run_audit(
        generated_path=Path(args.generated),
        reference_path=Path(args.reference),
        project_path=Path(args.project_path) if args.project_path else None,
        user_data_path=Path(args.user_data) if args.user_data else None,
        template_path=Path(args.template) if args.template else None,
        output_path=Path(args.output) if args.output else None,
        highlight=not args.no_highlight,
    )


if __name__ == '__main__':
    main()
