#!/usr/bin/env python3
"""
Highlight comparison: auto-generated report vs reference.
Produces a color-coded audit .docx for Eva.

Colors (matching Eva's DETALLAT document conventions):
  GREEN       - Fixed template text (boilerplate, methodology, norms) -- Eva's green = "done, don't touch"
  YELLOW      - Auto-generated text matching reference >= 90% -- Eva's yellow = "needs modification each time"
  TURQUOISE   - Functional match: content correct, minor format diffs (>= 70%)
  DARK_YELLOW - Regional/geology templates needing expansion
  PINK        - Values pending Eva's confirmation
  RED         - Errors or missing content

Non-matching paragraphs (turquoise, orange, pink, red) include a small red
annotation explaining the reason for the classification.

IMPORTANT mapping note (legacy naming):
  CAT_GREEN  = "green"  -> maps to WD_COLOR_INDEX.YELLOW      (groc = dynamic match)
  CAT_YELLOW = "yellow" -> maps to WD_COLOR_INDEX.BRIGHT_GREEN (verd = template)
  This swap was done to match Eva's color conventions where green = template
  and yellow = dynamic fields.

Usage:
  python3 automation/highlight_report.py

  REFERENCE must be a .docx file. If only the .doc exists, convert it first:
    libreoffice --headless --convert-to docx reference-material/4001612-bell-lloc/4001612_informe.doc
"""

import re
from difflib import SequenceMatcher
from pathlib import Path

from docx import Document
from docx.enum.text import WD_COLOR_INDEX
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Pt

# ---------------------------------------------------------------------------
# Paths (configurable)
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

GENERATED = BASE_DIR / "reference-material/4001612 BELL-LLOC/4001612_generated.docx"
REFERENCE = BASE_DIR / "reference-material/4001612 BELL-LLOC/4001612_informe.docx"
OUTPUT = BASE_DIR / "reference-material/4001612 BELL-LLOC/4001612_AUDIT_VISUAL.docx"

# ---------------------------------------------------------------------------
# Classification constants
# ---------------------------------------------------------------------------

# Project-specific strings: if text contains any of these it is dynamic, not
# pure template boilerplate.
PROJECT_SPECIFIC = [
    "RAMON MITJANA", "Bell-Lloc", "bell-lloc", "Jordi Bosch",
    "4001612", "Antoni Bellet", "Mestre Ramon Ortiz",
    "octubre de 2025", "199.50", "598", "297", "296",
    "Qvpu", "89.8", "3.18", "MITJANA", "BOSCH NOVELL",
    "Jordi bosch", "ramon mitjana",
]

# Patterns that signal Eva-dependent values (PINK).
EVA_PATTERNS = [
    "3.18", "3,18",        # Qa differs from reference 3.0
    "188", "345",          # E values divergent from reference 650
    "0.72", "0,72",        # settlement value
    "3.7", "3,7",          # K30 value
]

# Broader Eva keywords -- if a paragraph contains BOTH a number AND one of
# these words, it is likely an Eva-dependent geotechnical parameter.
EVA_KEYWORDS = [
    "permeabilitat", "coeficient de balast",
]

# Known dynamic value patterns: short strings rendered from Jinja template
# variables that should be classified as dynamic (groc), not template (verd).
DYNAMIC_VALUE_RES = [
    re.compile(r"^[CT]-\d$"),       # CTE classifications: C-0, C-1, T-1, T-2
    re.compile(r"^\d{7}$"),         # Project numbers: 4001612
]

# Template-expansion patterns (geology regional descriptions).
TEMPLATE_EXPANSION_PATTERNS = [
    "Qvpu", "Quaternari", "Pleistoce", "al\u00b7luvial",
    "diposits", "terrassa fluvial", "dip\u00f2sits",
    "Pleistoc\u00e8",
]

# Broader geology keywords: paragraphs dominated by geology content that
# differs from the reference are regional template text, not errors.
GEOLOGY_KEYWORDS = [
    "conca", "orogen", "pirinenc", "pirineus", "serralad",
    "litosfer", "tect\u00f2nic", "sediment", "eoc\u00e8", "oligoc\u00e8",
    "depressi\u00f3", "morfoestruct", "endorreic", "continental",
    "encavalcant", "subducci\u00f3", "erosi\u00f3", "aflor",
    "gresos", "lutites", "margues", "conglomerat",
    "terrassa fluvial", "al\u00b7luvial", "fluvial",
    "granuom\u00e8tr", "pl\u00e0stic", "no pl\u00e0stic",
    "grava con arenas", "grava amb sorr",
    "coloracions clar", "marr\u00f3 clar",
    "NMgo", "P8G", "unitat",
    "cartografi", "geol\u00f2gi",
]

# Section headers and TOC entries are always template text.
SECTION_HEADER_RE = re.compile(
    r"^\s*\d+(\.\d+)*\.?\s+[A-Z\u00c0\u00c1\u00c8\u00c9\u00cd\u00d2\u00d3\u00da\u00cf\u00dc\s\'\-\.\,\(\)]+$"
)
TOC_RE = re.compile(r"^\s*\d+(\.\d+)*\.?\s+.*\t\d+\s*$")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize(text: str) -> str:
    """Lowercase, collapse whitespace, strip, normalize quotes."""
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    # Normalize smart quotes / curly quotes to ASCII
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u00b7", ".")  # interpunct
    return text


def is_empty(text: str) -> bool:
    return not text or not text.strip()


def contains_any(text: str, patterns: list[str], case_sensitive: bool = False) -> bool:
    if case_sensitive:
        return any(p in text for p in patterns)
    low = text.lower()
    return any(p.lower() in low for p in patterns)


def contains_project_specific(text: str) -> bool:
    return contains_any(text, PROJECT_SPECIFIC)


def is_eva_dependent(text: str) -> bool:
    """Check if text contains Eva-dependent values."""
    # Direct pattern match
    if contains_any(text, EVA_PATTERNS, case_sensitive=True):
        return True
    # Keyword + number combination
    low = text.lower()
    if any(kw in low for kw in EVA_KEYWORDS) and re.search(r"\d", text):
        return True
    return False


def is_dynamic_value(text: str) -> bool:
    """Check if text matches a known dynamic value pattern (Jinja variables)."""
    stripped = text.strip()
    return any(pat.match(stripped) for pat in DYNAMIC_VALUE_RES)


def is_template_expansion(text: str) -> bool:
    """Check if text is a geology/regional description needing templates."""
    return contains_any(text, TEMPLATE_EXPANSION_PATTERNS)


def is_geology_content(text: str) -> bool:
    """Check if text is dominated by geology terminology."""
    low = text.lower()
    hits = sum(1 for kw in GEOLOGY_KEYWORDS if kw.lower() in low)
    # At least 2 geology keywords for longer text, or 1 for short
    if len(text) > 80:
        return hits >= 2
    return hits >= 1 and len(text) > 30


def is_section_header_or_toc(text: str) -> bool:
    """Check if text is a section header or TOC line."""
    stripped = text.strip()
    if not stripped:
        return False
    if TOC_RE.match(stripped):
        return True
    if SECTION_HEADER_RE.match(stripped):
        return True
    return False


def best_match(text: str, reference_pool: list[str], threshold: float = 0.4):
    """Find best matching reference text. Returns (ratio, matched_ref)."""
    norm = normalize(text)
    if not norm:
        return 0.0, ""
    best_ratio = 0.0
    best_ref = ""
    for ref in reference_pool:
        ref_norm = normalize(ref)
        if not ref_norm:
            continue
        # Quick length filter: if lengths differ by > 5x, skip
        len_ratio = len(norm) / max(len(ref_norm), 1)
        if len_ratio > 5.0 or len_ratio < 0.2:
            continue
        ratio = SequenceMatcher(None, norm, ref_norm).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_ref = ref
        if ratio >= 0.98:
            break  # good enough
    return best_ratio, best_ref


# ---------------------------------------------------------------------------
# Highlight application
# ---------------------------------------------------------------------------

def highlight_paragraph(paragraph, color):
    """Apply highlight color to all runs in a paragraph, including nested ones."""
    if isinstance(color, str):
        # Raw XML color string (e.g. "darkGreen") — skip high-level API
        xml_color = color
    else:
        xml_color = COLOR_TO_XML.get(color, "yellow")
        # Use high-level API for direct runs (only works with WD_COLOR_INDEX)
        for run in paragraph.runs:
            run.font.highlight_color = color

    # Also handle runs inside hyperlinks, fldSimple, and other wrappers
    # that python-docx's paragraph.runs doesn't cover.
    all_r_elements = paragraph._element.findall(".//" + qn("w:r"))
    for r_elem in all_r_elements:
        rPr = r_elem.find(qn("w:rPr"))
        if rPr is None:
            rPr = OxmlElement("w:rPr")
            r_elem.insert(0, rPr)
        hl = rPr.find(qn("w:highlight"))
        if hl is None:
            hl = OxmlElement("w:highlight")
            rPr.append(hl)
        hl.set(qn("w:val"), xml_color)


# Mapping from WD_COLOR_INDEX to XML w:highlight val attribute
COLOR_TO_XML = {
    WD_COLOR_INDEX.BRIGHT_GREEN: "green",
    WD_COLOR_INDEX.YELLOW: "yellow",
    WD_COLOR_INDEX.TURQUOISE: "cyan",
    WD_COLOR_INDEX.DARK_YELLOW: "darkYellow",
    WD_COLOR_INDEX.PINK: "magenta",
    WD_COLOR_INDEX.RED: "red",
}

def insert_annotation_after(paragraph, text):
    """Insert a small red italic annotation paragraph after the given paragraph."""
    new_p = OxmlElement("w:p")

    # Paragraph properties - tight spacing
    pPr = OxmlElement("w:pPr")
    spacing = OxmlElement("w:spacing")
    spacing.set(qn("w:before"), "0")
    spacing.set(qn("w:after"), "40")
    pPr.append(spacing)
    new_p.append(pPr)

    # Run with red font color, italic, small font
    r = OxmlElement("w:r")
    rPr = OxmlElement("w:rPr")

    # Italic
    i = OxmlElement("w:i")
    rPr.append(i)

    # Small font (8pt = 16 half-points)
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), "16")
    szCs = OxmlElement("w:szCs")
    szCs.set(qn("w:val"), "16")
    rPr.append(sz)
    rPr.append(szCs)

    # Red font color
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "FF0000")
    rPr.append(color)

    r.append(rPr)
    t_elem = OxmlElement("w:t")
    t_elem.text = text
    t_elem.set(qn("xml:space"), "preserve")
    r.append(t_elem)
    new_p.append(r)

    # Insert after the paragraph
    paragraph._element.addnext(new_p)


# ---------------------------------------------------------------------------
# Classification logic
# ---------------------------------------------------------------------------

# Category constants
CAT_GREEN = "green"
CAT_YELLOW = "yellow"
CAT_TURQUOISE = "turquoise"
CAT_ORANGE = "orange"
CAT_PINK = "pink"
CAT_RED = "red"
CAT_YELLOW_IMPERFECT = "yellow_imperfect"
CAT_EMPTY = "empty"

CAT_TO_COLOR = {
    CAT_GREEN: WD_COLOR_INDEX.YELLOW,         # dynamic match now yellow (Eva's yellow = modify)
    CAT_YELLOW: WD_COLOR_INDEX.BRIGHT_GREEN,  # template now green (Eva's green = don't touch)
    CAT_YELLOW_IMPERFECT: "darkGreen",        # raw XML color, not WD_COLOR_INDEX
    CAT_TURQUOISE: WD_COLOR_INDEX.TURQUOISE,
    CAT_ORANGE: WD_COLOR_INDEX.DARK_YELLOW,
    CAT_PINK: WD_COLOR_INDEX.PINK,
    CAT_RED: WD_COLOR_INDEX.RED,
}

CAT_LABELS = {
    CAT_GREEN: "Groc (match >= 90%)",
    CAT_YELLOW: "Verd (text fix plantilla)",
    CAT_YELLOW_IMPERFECT: "Verd clar (plantilla < 100%)",
    CAT_TURQUOISE: "Cian (match funcional >= 70%)",
    CAT_ORANGE: "Taronja (templates regionals)",
    CAT_PINK: "Rosa (pendent Eva)",
    CAT_RED: "Vermell (error/absent)",
    CAT_EMPTY: "Sense color (buit)",
}


def classify_text(text: str, reference_pool: list[str]) -> tuple[str, str, float]:
    """Classify a text fragment into one of the 6 categories.

    Returns (category, reason, match_ratio).
    reason is a non-empty string only for categories that need annotation
    (turquoise, orange, pink, red).
    """
    if is_empty(text):
        return CAT_EMPTY, "", 0.0

    stripped = text.strip()

    # 1) Eva-dependent values take priority
    if is_eva_dependent(stripped):
        return CAT_PINK, "[NOTA: Valor pendent confirmacio Eva]", 0.0

    # 2) Template expansion (geology regional)
    #    But only for longer descriptive paragraphs, not short mentions
    if is_template_expansion(stripped) and len(stripped) > 60:
        return CAT_ORANGE, "[NOTA: Template geologic regional -- cal ampliar per altres municipis]", 0.0

    # 3) Compare against reference pool
    ratio, matched = best_match(stripped, reference_pool)

    # 4) Section headers and TOC lines are template
    if is_section_header_or_toc(stripped):
        if ratio >= 0.995 or ratio < 0.40:
            # Perfect match OR no match at all (new section, still template)
            return CAT_YELLOW, "", ratio
        else:
            return CAT_YELLOW_IMPERFECT, f"[PLANTILLA: capcalera match {ratio*100:.0f}%]", ratio

    # 5) Very high match
    if ratio >= 0.90:
        # Distinguish pure template (no project data) vs dynamic match
        if not contains_project_specific(stripped) and not is_dynamic_value(stripped) and ratio >= 0.95:
            if ratio >= 0.995:
                return CAT_YELLOW, "", ratio
            else:
                return CAT_YELLOW_IMPERFECT, f"[PLANTILLA: match {ratio*100:.1f}%]", ratio
        return CAT_GREEN, "", ratio

    # 5b) Functional match
    if ratio >= 0.70:
        return CAT_TURQUOISE, f"[NOTA: Match {ratio*100:.0f}% -- difereix lleugerament de la referencia]", ratio

    # 5c) Moderate match -- be lenient for short text (table cells etc)
    if ratio >= 0.55 and len(stripped) < 50:
        return CAT_TURQUOISE, f"[NOTA: Match {ratio*100:.0f}%]", ratio

    # 6) Template expansion for shorter geo mentions
    if is_template_expansion(stripped):
        return CAT_ORANGE, "[NOTA: Template geologic regional]", ratio

    # 6b) Broader geology content detection -- these are regional template
    #     descriptions that differ from the reference but are not errors.
    if is_geology_content(stripped):
        return CAT_ORANGE, "[NOTA: Descripcio geologica regional -- depen de la zona]", ratio

    # 7) Very short text (single words, numbers) that are likely labels
    if len(stripped) < 15:
        # Check if it's a dynamic value pattern first
        if is_dynamic_value(stripped):
            return CAT_GREEN, "", ratio
        return CAT_YELLOW, "", ratio

    # 8) Figure / table captions (structural, usually close enough)
    if re.match(r"^(Figura|Taula|Gr\u00e0fic|Foto)\s+\d+", stripped):
        return CAT_TURQUOISE, f"[NOTA: Caption -- match {ratio*100:.0f}%]", ratio

    # 9) Fallback: check if it could be methodology/legal boilerplate
    #    (text with no project-specific data and some match)
    if ratio >= 0.45 and not contains_project_specific(stripped):
        return CAT_TURQUOISE, f"[NOTA: Match {ratio*100:.0f}%]", ratio

    # 10) Moderate match with project-specific data (still partially correct)
    if ratio >= 0.40:
        return CAT_TURQUOISE, f"[NOTA: Match {ratio*100:.0f}%]", ratio

    # 11) Otherwise: RED
    return CAT_RED, f"[NOTA: No coincideix amb la referencia -- match {ratio*100:.0f}%]", ratio


# ---------------------------------------------------------------------------
# Reference pool extraction
# ---------------------------------------------------------------------------

def extract_text_pool(doc: Document) -> list[str]:
    """Extract all non-empty text fragments from a document."""
    pool = []
    for p in doc.paragraphs:
        t = p.text.strip()
        if t:
            pool.append(t)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    t = p.text.strip()
                    if t:
                        pool.append(t)
    return pool


# ---------------------------------------------------------------------------
# Legend insertion
# ---------------------------------------------------------------------------

LEGEND_ITEMS = [
    ("green", "VERD -- Text fix de plantilla (boilerplate, metodologia, normativa). Coincideix amb el VERD del document DETALLAT d'Eva."),
    ("darkGreen", "VERD CLAR -- Plantilla amb diferencies menors (< 100% match). Indica text de plantilla que necessita revisio."),
    ("yellow", "GROC -- Match >= 90%: text auto-generat correctament que coincideix amb la referencia. Coincideix amb el GROC del document DETALLAT d'Eva (camps a modificar cada vegada)."),
    ("cyan", "CIAN -- Match funcional: contingut correcte amb diferencies menors (>= 70%)"),
    ("darkYellow", "TARONJA -- Templates regionals/geologics a ampliar per a altres municipis"),
    ("magenta", "ROSA -- Depen de confirmacio Eva (K, gamma, E, criteri nivells)"),
    ("red", "VERMELL -- Error o contingut absent a la referencia"),
]


def make_paragraph_element(text: str, highlight_color: str = None,
                           bold: bool = False, size_pt: int = None) -> "Element":
    """Create a w:p element with a single run."""
    p = OxmlElement("w:p")
    r = OxmlElement("w:r")
    rPr = OxmlElement("w:rPr")

    if bold:
        b = OxmlElement("w:b")
        rPr.append(b)

    if size_pt:
        sz = OxmlElement("w:sz")
        sz.set(qn("w:val"), str(size_pt * 2))  # half-points
        szCs = OxmlElement("w:szCs")
        szCs.set(qn("w:val"), str(size_pt * 2))
        rPr.append(sz)
        rPr.append(szCs)

    if highlight_color:
        hl = OxmlElement("w:highlight")
        hl.set(qn("w:val"), highlight_color)
        rPr.append(hl)

    r.append(rPr)
    t_elem = OxmlElement("w:t")
    t_elem.text = text
    t_elem.set(qn("xml:space"), "preserve")
    r.append(t_elem)
    p.append(r)
    return p


def append_legend(doc: Document):
    """Append a color legend at the end of the document."""
    doc.add_paragraph()  # blank line

    p = doc.add_paragraph()
    run = p.add_run("=" * 70)
    run.font.size = Pt(8)

    p = doc.add_paragraph()
    run = p.add_run("LLEGENDA DE COLORS \u2014 AUDIT VISUAL")
    run.bold = True
    run.font.size = Pt(14)

    p = doc.add_paragraph()
    run = p.add_run("=" * 70)
    run.font.size = Pt(8)

    doc.add_paragraph()  # blank line

    for color_xml, description in LEGEND_ITEMS:
        body = doc.element.body
        body.append(make_paragraph_element(
            f"  {description}",
            highlight_color=color_xml,
            size_pt=9
        ))


# ---------------------------------------------------------------------------
# Statistics summary
# ---------------------------------------------------------------------------

def append_statistics(doc: Document, stats: dict):
    """Append split statistics: template quality + content quality."""
    total_content = sum(v for k, v in stats.items() if k != CAT_EMPTY)

    doc.add_paragraph()  # blank line
    p = doc.add_paragraph()
    run = p.add_run("=" * 70)
    run.font.size = Pt(8)

    p = doc.add_paragraph()
    run = p.add_run("RESUM ESTADISTIC \u2014 AUDIT VISUAL")
    run.bold = True
    run.font.size = Pt(12)

    p = doc.add_paragraph()
    run = p.add_run("=" * 70)
    run.font.size = Pt(8)

    doc.add_paragraph()

    p = doc.add_paragraph()
    run = p.add_run(f"Total paragrafs/cel\u00b7les amb contingut: {total_content}")
    run.font.size = Pt(10)
    run.bold = True

    doc.add_paragraph()

    # --- TEMPLATE QUALITY ---
    tpl_perfect = stats.get(CAT_YELLOW, 0)
    tpl_imperfect = stats.get(CAT_YELLOW_IMPERFECT, 0)
    tpl_total = tpl_perfect + tpl_imperfect
    tpl_quality = tpl_perfect / tpl_total * 100 if tpl_total > 0 else 100.0

    p = doc.add_paragraph()
    run = p.add_run(f"QUALITAT PLANTILLA: {tpl_quality:.1f}%")
    run.bold = True
    run.font.size = Pt(11)

    def add_stat_line(label, count, color=None):
        p = doc.add_paragraph()
        pct = f"{count / total_content * 100:.1f}%" if total_content > 0 else "0%"
        run = p.add_run(f"  {label}: {count:>6}  ({pct})")
        run.font.size = Pt(10)
        if color and not isinstance(color, str):
            run.font.highlight_color = color

    add_stat_line(CAT_LABELS[CAT_YELLOW], tpl_perfect, CAT_TO_COLOR[CAT_YELLOW])
    add_stat_line(CAT_LABELS[CAT_YELLOW_IMPERFECT], tpl_imperfect)

    p = doc.add_paragraph()
    run = p.add_run(f"  Total plantilla: {tpl_total}")
    run.font.size = Pt(10)

    doc.add_paragraph()

    # --- CONTENT QUALITY ---
    content_good = stats.get(CAT_GREEN, 0) + stats.get(CAT_TURQUOISE, 0)
    content_bad = stats.get(CAT_ORANGE, 0) + stats.get(CAT_PINK, 0) + stats.get(CAT_RED, 0)
    content_total = content_good + content_bad
    content_quality = content_good / content_total * 100 if content_total > 0 else 100.0

    p = doc.add_paragraph()
    run = p.add_run(f"QUALITAT CONTINGUT: {content_quality:.1f}%")
    run.bold = True
    run.font.size = Pt(11)

    add_stat_line(CAT_LABELS[CAT_GREEN], stats.get(CAT_GREEN, 0), CAT_TO_COLOR[CAT_GREEN])
    add_stat_line(CAT_LABELS[CAT_TURQUOISE], stats.get(CAT_TURQUOISE, 0), CAT_TO_COLOR[CAT_TURQUOISE])
    add_stat_line(CAT_LABELS[CAT_ORANGE], stats.get(CAT_ORANGE, 0), CAT_TO_COLOR[CAT_ORANGE])
    add_stat_line(CAT_LABELS[CAT_PINK], stats.get(CAT_PINK, 0), CAT_TO_COLOR[CAT_PINK])
    add_stat_line(CAT_LABELS[CAT_RED], stats.get(CAT_RED, 0), CAT_TO_COLOR[CAT_RED])

    p = doc.add_paragraph()
    run = p.add_run(f"  Total contingut: {content_total}")
    run.font.size = Pt(10)

    doc.add_paragraph()

    p = doc.add_paragraph()
    run = p.add_run(f"  {CAT_LABELS[CAT_EMPTY]}: {stats.get(CAT_EMPTY, 0):>6}")
    run.font.size = Pt(10)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # Validate paths
    if not GENERATED.exists():
        print(f"ERROR: Generated report not found: {GENERATED}")
        return
    if not REFERENCE.exists():
        # Check if the .doc version exists and suggest conversion
        doc_path = REFERENCE.with_suffix(".doc")
        if doc_path.exists():
            print(f"ERROR: Reference .docx not found: {REFERENCE}")
            print(f"  The .doc version exists at: {doc_path}")
            print(f"  Convert it with: libreoffice --headless --convert-to docx \"{doc_path}\" --outdir \"{REFERENCE.parent}\"")
        else:
            print(f"ERROR: Reference report not found: {REFERENCE}")
        return

    print(f"Loading generated report: {GENERATED}")
    doc = Document(str(GENERATED))

    print(f"Loading reference report: {REFERENCE}")
    ref_doc = Document(str(REFERENCE))

    print("Building reference text pool...")
    ref_pool = extract_text_pool(ref_doc)
    print(f"  Reference pool size: {len(ref_pool)} text fragments")

    # Statistics counter
    stats = {
        CAT_GREEN: 0, CAT_YELLOW: 0, CAT_YELLOW_IMPERFECT: 0, CAT_TURQUOISE: 0,
        CAT_ORANGE: 0, CAT_PINK: 0, CAT_RED: 0, CAT_EMPTY: 0,
    }

    # Categories that get a red annotation
    ANNOTATED_CATS = {CAT_TURQUOISE, CAT_ORANGE, CAT_PINK, CAT_RED, CAT_YELLOW_IMPERFECT}

    def process_paragraph(paragraph):
        """Classify and highlight a single paragraph.

        Returns (paragraph, reason) if an annotation is needed, else None.
        """
        text = paragraph.text
        if is_empty(text):
            stats[CAT_EMPTY] += 1
            return None

        try:
            cat, reason, ratio = classify_text(text, ref_pool)
            stats[cat] += 1
            if cat != CAT_EMPTY:
                color = CAT_TO_COLOR[cat]
                highlight_paragraph(paragraph, color)
            if cat in ANNOTATED_CATS and reason:
                return (paragraph, reason)
        except Exception as e:
            print(f"  WARNING: Failed to process paragraph: {text[:60]}... -> {e}")
            stats[CAT_RED] += 1
        return None

    # Process body paragraphs
    print("Processing body paragraphs...")
    body_annotations = []
    for para in doc.paragraphs:
        result = process_paragraph(para)
        if result:
            body_annotations.append(result)

    # Insert body annotations (reverse order to preserve positions)
    for para, reason in reversed(body_annotations):
        insert_annotation_after(para, reason)

    # Process table cells.
    # Deduplicate merged cells: python-docx returns the same _tc element
    # for cells that are vertically merged. We track seen tc elements,
    # but must keep references alive to prevent id() reuse.
    print("Processing table cells...")
    seen_tc_elements = []  # keep references alive to prevent id reuse
    seen_tc_ids = set()
    for ti, table in enumerate(doc.tables):
        for row in table.rows:
            for cell in row.cells:
                tc_elem = cell._element
                tc_id = id(tc_elem)
                if tc_id in seen_tc_ids:
                    continue
                seen_tc_ids.add(tc_id)
                seen_tc_elements.append(tc_elem)  # prevent GC
                cell_annotations = []
                for para in cell.paragraphs:
                    result = process_paragraph(para)
                    if result:
                        cell_annotations.append(result)
                for para, reason in reversed(cell_annotations):
                    insert_annotation_after(para, reason)

    # Append legend at end (preserves cover page)
    print("Appending legend...")
    append_legend(doc)

    # Append statistics
    print("Appending statistics...")
    append_statistics(doc, stats)

    # Save
    print(f"Saving to: {OUTPUT}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(OUTPUT))

    # Print summary
    total_content = sum(v for k, v in stats.items() if k != CAT_EMPTY)
    print(f"\n{'='*50}")
    print(f"AUDIT VISUAL COMPLETE")
    print(f"{'='*50}")
    print(f"Total with content: {total_content}")

    # Template quality
    tpl_perfect = stats[CAT_YELLOW]
    tpl_imperfect = stats[CAT_YELLOW_IMPERFECT]
    tpl_total = tpl_perfect + tpl_imperfect
    tpl_pct = tpl_perfect / tpl_total * 100 if tpl_total > 0 else 100.0
    print(f"\nQUALITAT PLANTILLA: {tpl_pct:.1f}%")
    print(f"  {CAT_LABELS[CAT_YELLOW]}: {tpl_perfect}")
    print(f"  {CAT_LABELS[CAT_YELLOW_IMPERFECT]}: {tpl_imperfect}")

    # Content quality
    content_good = stats[CAT_GREEN] + stats[CAT_TURQUOISE]
    content_bad = stats[CAT_ORANGE] + stats[CAT_PINK] + stats[CAT_RED]
    content_total = content_good + content_bad
    content_pct = content_good / content_total * 100 if content_total > 0 else 100.0
    print(f"\nQUALITAT CONTINGUT: {content_pct:.1f}%")
    for cat in [CAT_GREEN, CAT_TURQUOISE, CAT_ORANGE, CAT_PINK, CAT_RED]:
        count = stats[cat]
        pct = count / total_content * 100 if total_content > 0 else 0
        print(f"  {CAT_LABELS[cat]}: {count} ({pct:.1f}%)")

    print(f"\n  {CAT_LABELS[CAT_EMPTY]}: {stats[CAT_EMPTY]}")
    print(f"Output: {OUTPUT}")


if __name__ == "__main__":
    main()
