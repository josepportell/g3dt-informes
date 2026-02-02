#!/usr/bin/env python3
"""
G3DT Report Generator - Using Base Template Styles

This generator:
1. Opens the base template (preserves all G3DT styles)
2. Clears content but keeps styles, headers, footers
3. Adds new content with proper style references

Usage:
    python generate_styled_report.py --content content.json --output report.docx
"""

import argparse
import json
from pathlib import Path
from datetime import datetime
from copy import deepcopy

from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

# Path to base template (has all G3DT styles defined)
BASE_TEMPLATE = Path(__file__).parent / "base-template.docx"

class G3DTStyledGenerator:
    """Generate G3DT reports using proper styles from base template."""

    def __init__(self, base_template: str = None):
        """Initialize with base template path."""
        self.base_path = Path(base_template) if base_template else BASE_TEMPLATE
        if not self.base_path.exists():
            raise FileNotFoundError(f"Base template not found: {self.base_path}")

    def create_report(self, content: dict, output_path: str) -> Path:
        """
        Create a new report from content dictionary.

        content structure:
        {
            "metadata": {
                "client": "...",
                "expedient": "...",
                "location": "...",
                ...
            },
            "sections": [
                {
                    "type": "heading1",
                    "text": "1. PRESENTACIÓ DE L'ESTUDI"
                },
                {
                    "type": "paragraph",
                    "text": "A petició de: ..."
                },
                {
                    "type": "table",
                    "headers": ["Col1", "Col2"],
                    "rows": [["val1", "val2"], ...]
                },
                ...
            ]
        }
        """
        # Open base template
        doc = Document(str(self.base_path))

        # Clear all content (paragraphs and tables) but keep styles
        self._clear_content(doc)

        # Add new content with proper styles
        metadata = content.get("metadata", {})
        sections = content.get("sections", [])

        for section in sections:
            self._add_section(doc, section, metadata)

        # Update header with expedient info
        self._update_header(doc, metadata)

        # Save
        output = Path(output_path)
        doc.save(output)
        print(f"✅ Report generated: {output}")
        return output

    def _clear_content(self, doc: Document):
        """Clear all body content but preserve styles and headers/footers."""
        # Remove all paragraphs from body
        for para in list(doc.paragraphs):
            p = para._element
            p.getparent().remove(p)

        # Remove all tables from body
        for table in list(doc.tables):
            t = table._element
            t.getparent().remove(t)

    def _add_section(self, doc: Document, section: dict, metadata: dict):
        """Add a section with proper styling."""
        section_type = section.get("type", "paragraph")

        if section_type == "heading1":
            para = doc.add_paragraph(section.get("text", ""), style="Heading 1")

        elif section_type == "heading2":
            para = doc.add_paragraph(section.get("text", ""), style="Heading 2")

        elif section_type == "heading3":
            para = doc.add_paragraph(section.get("text", ""), style="Heading 3")

        elif section_type == "paragraph":
            para = doc.add_paragraph(section.get("text", ""), style="Normal")

        elif section_type == "body_text":
            para = doc.add_paragraph(section.get("text", ""), style="Body Text 3")

        elif section_type == "caption":
            para = doc.add_paragraph(section.get("text", ""), style="Caption")
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER

        elif section_type == "bullet_list":
            for item in section.get("items", []):
                para = doc.add_paragraph(item, style="List Bullet")

        elif section_type == "table":
            self._add_table(doc, section)

        elif section_type == "signature":
            self._add_signature(doc, section, metadata)

        elif section_type == "page_break":
            doc.add_page_break()

    def _add_table(self, doc: Document, section: dict):
        """Add a table with G3DT styling."""
        headers = section.get("headers", [])
        rows = section.get("rows", [])
        caption = section.get("caption", "")

        if not headers and not rows:
            return

        # Determine table dimensions
        num_cols = len(headers) if headers else len(rows[0]) if rows else 0
        num_rows = (1 if headers else 0) + len(rows)

        if num_cols == 0:
            return

        # Create table
        table = doc.add_table(rows=num_rows, cols=num_cols)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER

        # Apply table style (use built-in or custom)
        try:
            table.style = "Table Grid"
        except:
            pass  # Style might not exist

        # Add headers
        row_idx = 0
        if headers:
            header_row = table.rows[0]
            for i, header_text in enumerate(headers):
                cell = header_row.cells[i]
                cell.text = str(header_text)
                # Style header cells
                for para in cell.paragraphs:
                    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    for run in para.runs:
                        run.bold = True
                # Add shading to header
                self._shade_cell(cell, "4A7C59")  # G3DT green
            row_idx = 1

        # Add data rows
        for row_data in rows:
            row = table.rows[row_idx]
            for i, cell_text in enumerate(row_data):
                if i < len(row.cells):
                    row.cells[i].text = str(cell_text)
            row_idx += 1

        # Add caption below table
        if caption:
            caption_para = doc.add_paragraph(caption, style="Caption")
            caption_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

    def _shade_cell(self, cell, color: str):
        """Add background shading to a table cell."""
        shading = OxmlElement("w:shd")
        shading.set(qn("w:fill"), color)
        cell._tc.get_or_add_tcPr().append(shading)

    def _add_signature(self, doc: Document, section: dict, metadata: dict):
        """Add signature block."""
        doc.add_paragraph()  # Space
        doc.add_paragraph("G3 D T S.L. sol·licita que si es detectessin anomalies respecte les dades que s'exposen, durant l'execució de la obra, agrairíem que ens avisessin, i igualment restem a la seva disposició per qualsevol consulta i/o dubte que vulguin realitzar, en el telèfon 973 33 12 12.", style="Normal")
        doc.add_paragraph()

        # Signature info
        para = doc.add_paragraph("Informe geològic / geotècnic", style="Normal")
        para.alignment = WD_ALIGN_PARAGRAPH.LEFT

        expedient = metadata.get("expedient", "[EXPEDIENT]")
        para = doc.add_paragraph(f"Expedient Núm.: {expedient}", style="Normal")

        lloc = metadata.get("lloc_signatura", "Els Omells de Na Gaia")
        data = metadata.get("data_signatura", datetime.now().strftime("%d de %B de %Y"))
        para = doc.add_paragraph(f"{lloc}, {data}", style="Normal")

    def _update_header(self, doc: Document, metadata: dict):
        """Update document header with project info."""
        expedient = metadata.get("expedient", "")
        location = metadata.get("location", "")

        if doc.sections:
            header = doc.sections[0].header
            if header.paragraphs:
                # Update first paragraph with expedient info
                header_text = f"{expedient}/Estudi geològic – geotècnic_{location}"
                # Find and update the right paragraph
                for para in header.paragraphs:
                    if "Estudi" in para.text or "expedient" in para.text.lower():
                        para.text = header_text
                        break


def create_demo_content(scenario: dict) -> dict:
    """Create content structure from a demo scenario."""
    return {
        "metadata": {
            "client": scenario.get("client", "CLIENT DEMO"),
            "expedient": scenario.get("expedient", "4001700"),
            "location": scenario.get("ubicacio", "BALAGUER"),
            "lloc_signatura": "Els Omells de Na Gaia",
            "data_signatura": datetime.now().strftime("%d de gener de 2026"),
        },
        "sections": [
            # Section 1: Presentació
            {"type": "heading1", "text": "1. PRESENTACIÓ DE L'ESTUDI"},
            {"type": "paragraph", "text": f"A petició de:"},
            {"type": "paragraph", "text": f"{scenario.get('client', 'CLIENT')}"},
            {"type": "paragraph", "text": "G3 DT, S.L. ha realitzat el següent informe geotècnic segons les instruccions del DB SE-C Cimientos fetes pel \"Código Técnico de la Edificación\" CTE, que entrà en vigor el 29 de març del 2006."},

            {"type": "heading2", "text": "1.1. ANTECEDENTS"},
            {"type": "paragraph", "text": f"Segons ens indica el sol·licitant, {scenario.get('client', 'el client')}, es vol valorar les característiques geològiques i geotècniques d'una zona on es preveu la construcció d'un {scenario.get('tipus_obra', 'habitatge unifamiliar aïllat')}."},
            {"type": "paragraph", "text": "L'edificació que es preveu construir presentarà les següents característiques:"},
            {
                "type": "table",
                "headers": ["Característica", "Valor"],
                "rows": [
                    ["Tipus edificació", scenario.get("tipus_obra", "Habitatge unifamiliar")],
                    ["Nombre de plantes", scenario.get("plantes", "PB + 1")],
                    ["Superfície parcel·la", scenario.get("superficie_parcela", "600 m²")],
                    ["Superfície construïda", scenario.get("superficie_construida", "180 m²")],
                ],
                "caption": "Taula 1. Resum de les principals dades de l'edificació a construir."
            },
            {"type": "paragraph", "text": f"L'edificació es situarà a {scenario.get('adreca', 'una parcel·la')}, {scenario.get('ubicacio', 'localitat')}, {scenario.get('provincia', 'Lleida')}."},
            {"type": "caption", "text": "Figura 1. Situació de la zona d'estudi (ICGC 2026)."},

            {"type": "heading2", "text": "1.2. CLASSIFICACIÓ DE L'OBRA SEGONS EL CTE"},
            {"type": "paragraph", "text": "A partir de les dades exposades pel client, un tècnic qualificat realitza la següent classificació segons el DB SE-C del CTE:"},
            {
                "type": "table",
                "headers": ["Paràmetre", "Classificació"],
                "rows": [
                    ["Tipus edificació", scenario.get("cte_edificacio", "C-0")],
                    ["Tipus terreny", scenario.get("cte_sol", "T-1")],
                ],
                "caption": "Taula 2. Classificació segons DB-SE-C del CTE."
            },

            {"type": "heading2", "text": "1.3. OBJECTIUS"},
            {"type": "paragraph", "text": "Els objectius de l'estudi són:"},
            {"type": "bullet_list", "items": [
                "Estudi de l'entorn geològic de l'obra.",
                "Reconeixement i caracterització dels materials del subsòl.",
                "Cota del nivell freàtic.",
                "Determinació de les càrregues admissibles.",
                "Estimació dels assentaments.",
                "Recomanacions sobre condicionants geològics i geotècnics.",
            ]},

            {"type": "page_break"},

            # Section 2: Treballs de Camp
            {"type": "heading1", "text": "2. TREBALLS DE CAMP"},
            {"type": "paragraph", "text": f"El dia {datetime.now().strftime('%d de gener de 2026')}, es va visitar l'obra per realitzar una inspecció geològica de la zona."},

            {"type": "heading2", "text": "2.1. DESCRIPCIÓ DE LA ZONA D'ESTUDI"},
            {"type": "paragraph", "text": f"La parcel·la objecte d'estudi es situa al municipi de {scenario.get('ubicacio', 'la localitat')}."},

            {"type": "heading2", "text": "2.2. RECONEIXEMENT DEL TERRENY"},
            {"type": "paragraph", "text": "La campanya de camp ha consistit en la realització de:"},
            {"type": "bullet_list", "items": [
                "3 assaigs de penetració dinàmica tipus DPSH.",
                "1 assaig SPT amb recuperació de mostra.",
                "Observacions de camp.",
                "Reportatge fotogràfic.",
            ]},
            {
                "type": "table",
                "headers": ["Assaig", "Coord. X", "Coord. Y", "Cota (m)", "Prof. (m)"],
                "rows": [
                    ["P-1", "[REVISAR]", "[REVISAR]", "245.0", "4.80"],
                    ["P-2", "[REVISAR]", "[REVISAR]", "245.1", "3.60"],
                    ["P-3", "[REVISAR]", "[REVISAR]", "244.9", "4.20"],
                ],
                "caption": "Taula 3. Coordenades i profunditats dels assaigs."
            },

            {"type": "page_break"},

            # Section 4: Conclusions (skip section 3 for brevity)
            {"type": "heading1", "text": "4. CONCLUSIONS"},
            {"type": "paragraph", "text": "Les recomanacions es donen en funció dels resultats obtinguts de la campanya de camp realitzada."},

            {"type": "heading2", "text": "4.1. GEOLOGIA"},
            {"type": "paragraph", "text": "Es detecta un nivell de materials des del punt de vista geològic/geotècnic en el subsòl del solar en estudi."},
            {
                "type": "table",
                "headers": ["Paràmetre", "Valor"],
                "rows": [
                    ["Classificació USCS", "SM-GP"],
                    ["Densitat aparent", "20 kN/m³"],
                    ["Angle de fricció", "32-35°"],
                    ["Cohesió efectiva", "0 kPa"],
                ],
                "caption": "Taula 9. Característiques geotècniques dels materials."
            },

            {"type": "heading2", "text": "4.2. HIDROGEOLOGIA I AGRESSIVITAT"},
            {"type": "paragraph", "text": "No es va detectar presència de nivell freàtic. Els materials es presenten NO AGRESSIUS al formigó."},

            {"type": "heading2", "text": "4.3. FONAMENTACIÓ"},
            {"type": "paragraph", "text": "Es recomana una fonamentació superficial mitjançant sabates:"},
            {"type": "paragraph", "text": "Qa = 3.50 kg/cm² amb factor de seguretat F=3"},
            {"type": "paragraph", "text": "Assentaments màxims previstos: ≤ 2.0 cm"},
            {"type": "paragraph", "text": "Coeficient de balast: K30 = 6.0 kg/cm³"},

            # Signature
            {"type": "signature"},
        ]
    }


def main():
    parser = argparse.ArgumentParser(description="Generate G3DT styled report")
    parser.add_argument("--scenario", choices=["balaguer", "tarrega", "mollerussa"], default="balaguer")
    parser.add_argument("--output", "-o", default="demo-report.docx")
    parser.add_argument("--template", "-t", help="Custom base template path")
    args = parser.parse_args()

    # Demo scenarios
    scenarios = {
        "balaguer": {
            "client": "PROMOTORA PONENT SL",
            "expedient": "4001700",
            "ubicacio": "BALAGUER",
            "comarca": "Noguera",
            "provincia": "Lleida",
            "adreca": "Carrer Major, 45",
            "tipus_obra": "habitatge unifamiliar aïllat",
            "plantes": "PB + 1",
            "superficie_parcela": "600 m²",
            "superficie_construida": "180 m²",
            "cte_edificacio": "C-0",
            "cte_sol": "T-1",
        },
        "tarrega": {
            "client": "CONSTRUCCIONS XYZ SL",
            "expedient": "4001701",
            "ubicacio": "TÀRREGA",
            "comarca": "Urgell",
            "provincia": "Lleida",
            "adreca": "Polígon Industrial El Segre, Parcel·la 15",
            "tipus_obra": "nau industrial",
            "plantes": "PB",
            "superficie_parcela": "2500 m²",
            "superficie_construida": "1800 m²",
            "cte_edificacio": "C-1",
            "cte_sol": "T-1",
        },
        "mollerussa": {
            "client": "AJUNTAMENT DE MOLLERUSSA",
            "expedient": "4001702",
            "ubicacio": "MOLLERUSSA",
            "comarca": "Pla d'Urgell",
            "provincia": "Lleida",
            "adreca": "Plaça de l'Ajuntament, s/n",
            "tipus_obra": "equipament públic",
            "plantes": "PB + 2",
            "superficie_parcela": "1200 m²",
            "superficie_construida": "800 m²",
            "cte_edificacio": "C-1",
            "cte_sol": "T-2",
        },
    }

    scenario = scenarios[args.scenario]
    content = create_demo_content(scenario)

    generator = G3DTStyledGenerator(args.template)
    generator.create_report(content, args.output)


if __name__ == "__main__":
    main()
