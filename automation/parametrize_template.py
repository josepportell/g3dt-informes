#!/usr/bin/env python3
"""
Parametrize g3dt-jinja-template.docx - replace hardcoded data with Jinja2 variables.

Replaces hardcoded data from the Valles-Penedes reference project with Jinja2 template
variables so the template can be rendered dynamically by docxtpl for any project.

Usage:
    python3 -m automation.parametrize_template
    # or
    python3 automation/parametrize_template.py

Creates a backup at g3dt-jinja-template.docx.backup2 before modifying.

Author: Eficients.cat
Date: 2026-02-05
"""

import shutil
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "g3dt-jinja-template.docx"
BACKUP_PATH = TEMPLATE_PATH.with_suffix('.docx.backup2')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clear_and_set(paragraph, new_text):
    """Clear all runs in a paragraph and set new text on the first run.

    Preserves the paragraph-level formatting (alignment, style) and the first
    run's font properties (name, size, bold).
    """
    font_name = None
    font_size = None
    bold = None
    if paragraph.runs:
        first = paragraph.runs[0]
        font_name = first.font.name
        font_size = first.font.size
        bold = first.font.bold

    # Blank every run
    for run in paragraph.runs:
        run.text = ""

    # Write new text into the first run (or create one)
    if paragraph.runs:
        paragraph.runs[0].text = new_text
    else:
        run = paragraph.add_run(new_text)
        if font_name:
            run.font.name = font_name
        if font_size:
            run.font.size = font_size
        if bold is not None:
            run.font.bold = bold


def set_cell_text(cell, text):
    """Set cell text while keeping existing paragraph formatting."""
    p = cell.paragraphs[0]
    # Remove any extra paragraphs
    for extra in cell.paragraphs[1:]:
        extra_elem = extra._element
        extra_elem.getparent().remove(extra_elem)
    clear_and_set(p, text)


def delete_table_row(table, row_index):
    """Delete a row from a table by index (manipulates underlying XML)."""
    tbl = table._tbl
    tr = tbl.tr_lst[row_index]
    tbl.remove(tr)


def find_paragraph(paragraphs, contains, start=0):
    """Find first paragraph index whose text contains a substring, from *start*."""
    for i in range(start, len(paragraphs)):
        if contains in paragraphs[i].text:
            return i
    return None


def insert_paragraph_after(paragraph, text, style=None):
    """Insert a new paragraph after the given paragraph.

    Uses low-level XML manipulation to add a <w:p> element right after
    *paragraph* in the document body.  *style* should be a python-docx Style
    object (e.g. ``doc.styles['toc 2']``); it is applied via XML so that no
    document-part lookup is needed.

    Returns the raw ``CT_P`` element (not a full Paragraph wrapper) because
    inserted elements lack access to the document part.
    """
    new_p = OxmlElement('w:p')
    paragraph._element.addnext(new_p)

    # Apply style via XML <w:pPr><w:pStyle w:val="..."/></w:pPr>
    if style is not None:
        pPr = OxmlElement('w:pPr')
        pStyle = OxmlElement('w:pStyle')
        pStyle.set(qn('w:val'), style.style_id)
        pPr.append(pStyle)
        new_p.insert(0, pPr)

    new_run = OxmlElement('w:r')
    new_text = OxmlElement('w:t')
    new_text.text = text
    new_run.append(new_text)
    new_p.append(new_run)
    return new_p


# ---------------------------------------------------------------------------
# Table parametrisation
# ---------------------------------------------------------------------------

def parametrize_tables(doc):
    """Replace hardcoded table data with Jinja2 variables."""
    tables = doc.tables

    # --- Table 2: DPSH results (5 rows x 5 cols) ---
    # Row 0: merged header (keep)
    # Row 1: column headers (keep)
    # Rows 2-4: P-1, P-2, P-3 hardcoded -> replace row 2 with loop, delete 3 & 4
    t2 = tables[2]

    # Use 3-row pattern: {%tr for %} row, data row, {%tr endfor %} row
    # Row 2 = loop open (will be removed by docxtpl)
    set_cell_text(t2.rows[2].cells[0], '{%tr for test in dpsh_tests %}')
    for ci in range(1, 5):
        set_cell_text(t2.rows[2].cells[ci], '')

    # Row 3 = data template row (will be duplicated for each test)
    set_cell_text(t2.rows[3].cells[0], '{{ test.test_id }}')
    set_cell_text(t2.rows[3].cells[1], '{{ test.cota }}')
    set_cell_text(t2.rows[3].cells[2], '{{ test.depth }}')
    set_cell_text(t2.rows[3].cells[3], '{{ test.refusal }}')
    set_cell_text(t2.rows[3].cells[4], '{{ test.water }}')

    # Row 4 = loop close (will be removed by docxtpl)
    set_cell_text(t2.rows[4].cells[0], '{%tr endfor %}')
    for ci in range(1, 5):
        set_cell_text(t2.rows[4].cells[ci], '')

    # --- Table 3: SPT results (3 rows x 5 cols) ---
    # Row 2 data -> variables
    t3 = tables[3]
    set_cell_text(t3.rows[2].cells[0], '{{ spt_test_id }}')
    set_cell_text(t3.rows[2].cells[1], '{{ spt_location }}')
    set_cell_text(t3.rows[2].cells[2], '{{ spt_depth_range }}')
    set_cell_text(t3.rows[2].cells[3], '{{ spt_n30 }}')
    set_cell_text(t3.rows[2].cells[4], '{{ spt_lithology }}')

    # --- Table 4: Lab tests (2 rows x 3 cols) ---
    # Row 0: "Mostra: SPT-1 | Punt: P-3 | Profunditat: ..." -> variables
    t4 = tables[4]
    set_cell_text(t4.rows[0].cells[0], 'Mostra : {{ lab_sample_id }}')
    set_cell_text(t4.rows[0].cells[1], 'Punt: {{ lab_location }}')
    set_cell_text(t4.rows[0].cells[2], 'Profunditat: {{ lab_depth }}')
    # Row 1: lab test descriptions -> variable
    set_cell_text(t4.rows[1].cells[1], '{{ lab_tests_text }}')
    set_cell_text(t4.rows[1].cells[2], '{{ lab_tests_text }}')

    # --- Table 5: Soil levels (1 row x 2 cols) ---
    t5 = tables[5]
    set_cell_text(t5.rows[0].cells[0], '{{ soil_level_name }}')
    set_cell_text(t5.rows[0].cells[1], '{{ soil_level_material }}')

    # --- Table 6: Permeability (2 rows x 3 cols) ---
    t6 = tables[6]
    set_cell_text(t6.rows[1].cells[0], '{{ perm_level_name }}')
    set_cell_text(t6.rows[1].cells[1], '{{ perm_k_value }}')
    set_cell_text(t6.rows[1].cells[2], '{{ perm_material }}')

    # --- Table 7: Sulfates (2 rows x 4 cols) ---
    t7 = tables[7]
    set_cell_text(t7.rows[1].cells[0], '{{ sulfate_level_name }}')
    set_cell_text(t7.rows[1].cells[1], '{{ sulfate_value }}')
    set_cell_text(t7.rows[1].cells[2], '{{ sulfate_baumann }}')
    set_cell_text(t7.rows[1].cells[3], '{{ sulfate_classification }}')

    # --- Table 8: Seismic C (2 rows x 4 cols) ---
    t8 = tables[8]
    set_cell_text(t8.rows[1].cells[0], '{{ seismic_level_num }}')
    set_cell_text(t8.rows[1].cells[1], '{{ seismic_terrain_type }}')
    set_cell_text(t8.rows[1].cells[2], '{{ seismic_thickness }}')
    set_cell_text(t8.rows[1].cells[3], '{{ seismic_c_coeff }}')

    # --- Table 9: Geotechnical params (2 rows x 7 cols) ---
    t9 = tables[9]
    set_cell_text(t9.rows[1].cells[0], '{{ geotech_level_name }}')
    set_cell_text(t9.rows[1].cells[1], '{{ geotech_nb }}')
    set_cell_text(t9.rows[1].cells[2], '{{ geotech_n }}')
    set_cell_text(t9.rows[1].cells[3], '{{ geotech_density }}')
    set_cell_text(t9.rows[1].cells[4], '{{ geotech_cohesion }}')
    set_cell_text(t9.rows[1].cells[5], '{{ geotech_phi }}')
    set_cell_text(t9.rows[1].cells[6], '{{ geotech_E }}')


# ---------------------------------------------------------------------------
# Paragraph parametrisation
# ---------------------------------------------------------------------------

def parametrize_paragraphs(doc):
    """Replace hardcoded paragraph text with Jinja2 variables."""
    paras = doc.paragraphs

    # --- P60: Street address (remove hardcoded "carrer de la Miranda" prefix) ---
    idx = find_paragraph(paras,
                         "L\u2019habitatge que es preveu construir es situar\u00e0")
    if idx is not None:
        clear_and_set(
            paras[idx],
            "L\u2019habitatge que es preveu construir es situar\u00e0 a una "
            "parcel\u00b7la ubicada al {{ street_address }}, al terme municipal "
            "de {{ municipality }}."
        )

    # --- P101-103: Adjacent parcel descriptions ---
    idx = find_paragraph(paras, "Per la part nord,")
    if idx is not None:
        clear_and_set(paras[idx],
                      "Per la part nord, {{ adjacent_north }}.")
        # Next paragraph: south
        if idx + 1 < len(paras) and "Per la part sud" in paras[idx + 1].text:
            clear_and_set(paras[idx + 1],
                          "Per la part sud, {{ adjacent_south }}.")
        # Next: east/west
        if idx + 2 < len(paras) and "Per la part est" in paras[idx + 2].text:
            clear_and_set(
                paras[idx + 2],
                "Per la part est, {{ adjacent_east }}. "
                "Per la part oest, {{ adjacent_west }}."
            )

    # --- P107: Access description ---
    idx = find_paragraph(paras,
                         "El dia dels treballs de camp es realitza l\u2019entrada")
    if idx is not None:
        clear_and_set(
            paras[idx],
            "El dia dels treballs de camp es realitza l\u2019entrada a la zona "
            "d\u2019estudi a trav\u00e9s de {{ access_description }}."
        )

    # --- P109: Site description (full paragraph) ---
    idx = find_paragraph(paras, "El solar es localitza sense construccions")
    if idx is not None:
        clear_and_set(paras[idx], "{{ site_description }}")

    # --- P123: Number of DPSH tests ---
    idx = find_paragraph(paras,
                         "assaigs de penetraci\u00f3 din\u00e0mica tipus DPSH")
    if idx is not None:
        clear_and_set(
            paras[idx],
            "{{ num_dpsh_tests }} assaigs de penetraci\u00f3 din\u00e0mica "
            "tipus DPSH (veure annex \"Registre assaigs mec\u00e0nics\")."
        )

    # --- P124: SPT test line (with conditional sondeig) ---
    idx = find_paragraph(paras, "assaig SPT amb recuperaci\u00f3 de mostra")
    if idx is not None:
        clear_and_set(
            paras[idx],
            "{% if has_sondeig %}1 sondeig a rotaci\u00f3 amb bateria "
            "cont\u00ednua i {% endif %}1 assaig SPT amb recuperaci\u00f3 de "
            "mostra (veure annex \"Registre assaigs mec\u00e0nics\")."
        )

    # --- P205-223: Geological text (Section 3.1) ---
    # Replace the sequence of geology paragraphs with 6 template variables.
    # Find the first geology paragraph (Hoja ...)
    geo_start = find_paragraph(paras, "Hoja")
    if geo_start is not None:
        # The ICGC paragraph is the last one before the figure caption
        geo_end = find_paragraph(paras, "Concretament, i segons l\u2019ICGC")
        if geo_end is not None:
            # Clear all paragraphs between geo_start and geo_end (inclusive),
            # replacing the first 6 with geology_para_N and blanking the rest.
            geo_indices = []
            for i in range(geo_start, geo_end + 1):
                text = paras[i].text.strip()
                if text:
                    geo_indices.append(i)

            for seq, gi in enumerate(geo_indices):
                if seq < 6:
                    clear_and_set(paras[gi],
                                  "{{ " + f"geology_para_{seq + 1}" + " }}")
                else:
                    # Extra paragraphs beyond 6 - blank them
                    clear_and_set(paras[gi], "")

    # --- P244: Materials level 1 description ---
    idx = find_paragraph(paras, "El nivell 1 est\u00e0 format per graves")
    if idx is not None:
        clear_and_set(paras[idx], "{{ materials_level_1 }}")

    # --- P262: Materials depth text ---
    idx = find_paragraph(paras,
                         "A partir dels assaigs realitzats s\u2019obt\u00e9 una pot\u00e8ncia")
    if idx is not None:
        clear_and_set(paras[idx], "{{ materials_depth_text }}")

    # --- P266: Geomechanical characterization ---
    idx = find_paragraph(paras, "Des del punt de vista geomec\u00e0nic")
    if idx is not None:
        clear_and_set(paras[idx], "{{ materials_geomech_text }}")

    # --- P318: Building structure description ---
    idx = find_paragraph(paras,
                         "Segons el projecte executiu es preveu la construcci\u00f3")
    if idx is not None:
        # This text appears twice (P318 and P443). We want the first one (excavabilitat)
        clear_and_set(
            paras[idx],
            "Segons el projecte executiu es preveu la construcci\u00f3 d\u2019una "
            "estructura {{ building_structure_desc }}, i per tant, no es preveu cap "
            "excavaci\u00f3 important, \u00fanicament l\u2019excavaci\u00f3 pel "
            "sanejament, anivellaci\u00f3, i per a la implantaci\u00f3 de la "
            "fonamentaci\u00f3."
        )

    # --- P333: Seismic AB value ---
    idx = find_paragraph(paras, "AB")
    if idx is not None:
        # Find the specific "AB  =0,08" paragraph
        for i in range(len(paras)):
            if "=0,08" in paras[i].text or ("AB" in paras[i].text and "g  (essent" in paras[i].text):
                clear_and_set(
                    paras[i],
                    "AB  ={{ seismic_ab_text }} g  (essent g el valor de la gravetat)"
                )
                break

    # --- P409: Section 4.1 level description ---
    # "4.1. GEOLOGIA" appears in TOC and body. Search from 400+ for body.
    sec41 = find_paragraph(paras, "4.1. GEOLOGIA", start=400)
    if sec41 is not None:
        # The level description is 2 paragraphs after (skip the intro paragraph)
        level_idx = find_paragraph(paras, "El nivell 1 est\u00e0 format per",
                                   start=sec41)
        if level_idx is not None:
            clear_and_set(paras[level_idx], "{{ conclusions_level_1 }}")

    # --- P432: Site condition ---
    idx = find_paragraph(paras, "Es tracta d\u2019un solar")
    if idx is not None:
        clear_and_set(
            paras[idx],
            "Es tracta d\u2019un solar {{ site_condition }}, no s\u2019han "
            "detectat marques i/o indicis de processos d\u2019erosi\u00f3 "
            "relacionats amb l\u2019escolament h\u00eddric superficial, ni "
            "es preveu que apareguin. "
        )

    # --- P443: Foundation section structure description ---
    # "4.3. FONAMENTACIO" appears twice: once in the TOC (early) and once in the body.
    # Search from index 400+ to skip the TOC and find the body heading.
    sec43 = find_paragraph(paras, "4.3. FONAMENTACI\u00d3", start=400)
    if sec43 is not None:
        found = find_paragraph(
            paras, "Segons el projecte executiu es preveu", start=sec43)
        if found is not None:
            clear_and_set(
                paras[found],
                "Segons el projecte executiu es preveu la construcci\u00f3 d\u2019una "
                "estructura {{ building_structure_desc }}, per tant, no es preveu cap "
                "excavaci\u00f3 important, \u00fanicament l\u2019excavaci\u00f3 pel "
                "sanejament, anivellaci\u00f3, i per a la implantaci\u00f3 de la "
                "fonamentaci\u00f3."
            )

    # --- P449: Qa value ---
    idx = find_paragraph(paras, "Qa=")
    if idx is not None:
        # Preserve bold formatting pattern: Qa= value Kg/cm2 then normal text
        clear_and_set(
            paras[idx],
            "Qa= {{ qa_value }} Kg/cm2  amb un factor de seguretat "
            "incl\u00f2s de F=3"
        )

    # --- P451: Settlement ---
    idx = find_paragraph(paras, "assentaments m\u00e0xims previstos")
    if idx is not None:
        clear_and_set(
            paras[idx],
            "Els assentaments m\u00e0xims previstos per la c\u00e0rrega "
            "recomanada anteriorment seran iguals o inferiors a "
            "{{ settlement }} cm, immediats en el temps donat el "
            "comportament granular dels materials."
        )

    # --- P453: K30 value ---
    idx = find_paragraph(paras, "coeficient de balast")
    if idx is not None:
        clear_and_set(
            paras[idx],
            "Com a valor de coeficient de balast referit a la placa de "
            "30x30, es podr\u00e0 adoptar un valor de K30= {{ k30_value }} "
            "kg/cm3."
        )


# ---------------------------------------------------------------------------
# Conditional section 4 blocks (empentes de terres, estabilitat de vessant)
# ---------------------------------------------------------------------------

def add_conditional_section4_blocks(doc):
    """Add conditional 4.4 and 4.5 blocks using empty paragraphs after K30."""
    paras = doc.paragraphs

    # Find the K30 paragraph (anchor) and the disclaimer (end marker)
    k30_idx = find_paragraph(paras, "coeficient de balast")
    disclaimer_idx = find_paragraph(paras, "G3 D T S.L. sol\u00b7licita")
    if k30_idx is None or disclaimer_idx is None:
        print("WARNING: Could not find K30 or disclaimer paragraph for section 4 blocks")
        return

    # We expect 7 empty paragraphs between K30 and disclaimer (P455-P461).
    # We need 8 slots (4 per block), so insert one extra after the last empty.
    empty_start = k30_idx + 1
    empty_count = disclaimer_idx - empty_start
    if empty_count < 7:
        print(f"WARNING: Expected 7 empty paragraphs after K30, found {empty_count}")
        return

    # -- Empentes block (uses first 4 empty paragraphs) --
    p_emp_if = paras[empty_start]       # {%p if %}
    p_emp_h2 = paras[empty_start + 1]   # heading
    p_emp_body = paras[empty_start + 2] # body
    p_emp_endif = paras[empty_start + 3] # {%p endif %}

    clear_and_set(p_emp_if, "{%p if include_earth_pressure %}")
    clear_and_set(p_emp_h2,
                  "{{ section_empentes_num }}. EMPENTES DE TERRES")
    p_emp_h2.style = doc.styles['Heading 2']
    clear_and_set(p_emp_body, "{{ empentes_paragraph }}")
    clear_and_set(p_emp_endif, "{%p endif %}")

    # -- Estabilitat block (uses next 3 empty paragraphs + 1 inserted) --
    p_est_if = paras[empty_start + 4]   # {%p if %}
    p_est_h2 = paras[empty_start + 5]   # heading
    p_est_body = paras[empty_start + 6] # body

    clear_and_set(p_est_if, "{%p if include_slope_stability %}")
    clear_and_set(p_est_h2,
                  "{{ section_estabilitat_num }}. ESTABILITAT DE VESSANT")
    p_est_h2.style = doc.styles['Heading 2']
    clear_and_set(p_est_body, "{{ estabilitat_paragraph }}")

    # Insert a new paragraph after the body for {%p endif %}
    insert_paragraph_after(p_est_body, "{%p endif %}")

    print("  Added conditional section 4 blocks (empentes + estabilitat)")


def add_conditional_toc_entries(doc):
    """Add conditional TOC entries for sections 4.4 and 4.5 after '4.3. FONAMENTACIO'."""
    paras = doc.paragraphs

    toc43_idx = find_paragraph(paras, "4.3. FONAMENTACI\u00d3")
    if toc43_idx is None:
        print("WARNING: Could not find TOC entry for 4.3 FONAMENTACIO")
        return

    toc43 = paras[toc43_idx]
    toc2_style = doc.styles['toc 2']

    # Insert in reverse order so they end up in the right sequence:
    # After P33 we want: empentes_if, empentes_entry, empentes_endif,
    #                     estabilitat_if, estabilitat_entry, estabilitat_endif
    # Inserting after toc43 in reverse order:
    est_endif = insert_paragraph_after(toc43, "{%p endif %}")
    est_entry = insert_paragraph_after(
        toc43,
        "{{ section_estabilitat_num }}. ESTABILITAT DE VESSANT",
        style=toc2_style)
    est_if = insert_paragraph_after(
        toc43, "{%p if include_slope_stability %}")

    emp_endif = insert_paragraph_after(toc43, "{%p endif %}")
    emp_entry = insert_paragraph_after(
        toc43,
        "{{ section_empentes_num }}. EMPENTES DE TERRES",
        style=toc2_style)
    emp_if = insert_paragraph_after(
        toc43, "{%p if include_earth_pressure %}")

    print("  Added conditional TOC entries (empentes + estabilitat)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if not TEMPLATE_PATH.exists():
        print(f"ERROR: Template not found at {TEMPLATE_PATH}")
        return

    # Backup
    shutil.copy2(TEMPLATE_PATH, BACKUP_PATH)
    print(f"Backup saved to {BACKUP_PATH}")

    doc = Document(str(TEMPLATE_PATH))

    parametrize_tables(doc)
    parametrize_paragraphs(doc)
    add_conditional_section4_blocks(doc)
    add_conditional_toc_entries(doc)

    doc.save(str(TEMPLATE_PATH))
    print(f"Template updated: {TEMPLATE_PATH}")

    # Verify by listing Jinja variables found
    verify(doc)


def verify(doc):
    """Print a summary of Jinja2 variables found in the modified template."""
    import re
    variables = set()
    controls = set()

    for p in doc.paragraphs:
        text = p.text
        variables.update(re.findall(r'\{\{\s*(\w[\w.]*)\s*\}\}', text))
        controls.update(re.findall(r'\{%[p ]?\s*(for|if|endif|endfor)\b[^%]*%\}', text))

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                text = cell.text
                variables.update(re.findall(r'\{\{\s*(\w[\w.]*)\s*\}\}', text))
                controls.update(re.findall(r'\{%[ptr ]*\s*(for|if|endif|endfor)\b[^%]*%\}', text))

    print(f"\nJinja2 variables found ({len(variables)}):")
    for v in sorted(variables):
        print(f"  {{ {v} }}")

    print(f"\nJinja2 control tags found ({len(controls)}):")
    for c in sorted(controls):
        print(f"  {{% {c} %}}")


if __name__ == '__main__':
    main()
