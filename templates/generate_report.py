#!/usr/bin/env python3
"""
G3DT Geotechnical Report Template Generator
Based on template spec v1.5 - Sample 3001631 (Rubí) structure

Simple project structure:
- CTE C-0 (single-family)
- DPSH only (no Sondeig/SPT)
- Flat site (no slope analysis)
- Conclusions: 4.1 → 4.2 → 4.3 Fonamentació → END
"""

from docx import Document
from docx.shared import Pt, Cm, Inches, RGBColor, Twips
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.section import WD_ORIENT
from docx.oxml.ns import qn, nsmap
from docx.oxml import OxmlElement
from pathlib import Path
import argparse

# G3DT Brand Colors (corrected from PDF analysis 2026-01-04)
# Original assumption was #4A7C59, actual PDF uses darker greens
G3_GREEN_HEADINGS = RGBColor(0, 51, 0)     # #003300 - Section headings (H1, H2)
G3_GREEN_LINKS = RGBColor(0, 128, 0)       # #008000 - Website links (footer)
G3_GREEN_BOX = RGBColor(74, 124, 89)       # #4A7C59 - Page number box (kept for contrast)
G3_GREEN_LIGHT = RGBColor(143, 188, 143)   # #8FBC8F - Secondary/light green
TABLE_GRAY = RGBColor(245, 245, 245)       # #F5F5F5 - Alternating rows

# Main alias - use dark green for headings
G3_GREEN = G3_GREEN_HEADINGS


class G3DTReportGenerator:
    """Generate G3DT geotechnical reports in Word format."""

    def __init__(self, logo_path: str = None, cover_image_path: str = None, watermark_path: str = None):
        self.doc = Document()
        self.logo_path = logo_path
        self.cover_image_path = cover_image_path
        self.watermark_path = watermark_path
        self.document_title = ""  # Will be set when generating
        self._setup_page_layout()
        self._setup_styles()

    def _setup_page_layout(self):
        """Configure A4 page with G3DT margins."""
        section = self.doc.sections[0]

        # A4 size
        section.page_width = Cm(21.0)
        section.page_height = Cm(29.7)

        # Margins per spec
        section.top_margin = Cm(2.5)
        section.bottom_margin = Cm(2.0)
        section.left_margin = Cm(2.5)
        section.right_margin = Cm(2.5)

        # Header/footer distances
        section.header_distance = Cm(1.25)
        section.footer_distance = Cm(1.0)

        # Different first page (no header/footer on cover)
        section.different_first_page_header_footer = True

    def _add_rounded_rect_with_text(self, paragraph, text, bg_color="4A7C59"):
        """Add a rounded rectangle with text (for page numbers)."""
        # Create a simple green box effect using text with background
        run = paragraph.add_run(f" {text} ")
        run.font.color.rgb = RGBColor(255, 255, 255)
        run.font.bold = True
        run.font.size = Pt(10)
        # Add shading to run
        shading = OxmlElement('w:shd')
        shading.set(qn('w:val'), 'clear')
        shading.set(qn('w:color'), 'auto')
        shading.set(qn('w:fill'), bg_color)
        run._r.get_or_add_rPr().append(shading)

    def _add_page_number_field(self, paragraph):
        """Add a page number field to a paragraph with green box styling."""
        run = paragraph.add_run()

        # Add space before
        run.add_text(" ")

        # Create the field for page number
        fldChar1 = OxmlElement('w:fldChar')
        fldChar1.set(qn('w:fldCharType'), 'begin')

        instrText = OxmlElement('w:instrText')
        instrText.text = "PAGE"

        fldChar2 = OxmlElement('w:fldChar')
        fldChar2.set(qn('w:fldCharType'), 'separate')

        fldChar3 = OxmlElement('w:fldChar')
        fldChar3.set(qn('w:fldCharType'), 'end')

        run._r.append(fldChar1)
        run._r.append(instrText)
        run._r.append(fldChar2)
        run._r.append(fldChar3)

        # Style the run
        run.font.color.rgb = RGBColor(255, 255, 255)
        run.font.bold = True
        run.font.size = Pt(10)

        # Add green background
        shading = OxmlElement('w:shd')
        shading.set(qn('w:val'), 'clear')
        shading.set(qn('w:color'), 'auto')
        shading.set(qn('w:fill'), '4A7C59')
        run._r.get_or_add_rPr().append(shading)

        run.add_text(" ")

    def _setup_header_footer(self, section, data: dict):
        """Add header and footer to section."""
        # === HEADER ===
        header = section.header
        header.is_linked_to_previous = False

        # Create a table for header layout: Logo | Title | Page Number
        header_table = header.add_table(rows=1, cols=3, width=Cm(16))
        header_table.autofit = False
        header_table.allow_autofit = False

        # Set column widths
        header_table.columns[0].width = Cm(3)   # Logo
        header_table.columns[1].width = Cm(10)  # Title
        header_table.columns[2].width = Cm(3)   # Page number

        cells = header_table.rows[0].cells

        # Left cell: Logo
        p = cells[0].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        if self.logo_path and Path(self.logo_path).exists():
            run = p.add_run()
            run.add_picture(self.logo_path, height=Cm(1.0))

        # Center cell: Document title
        p = cells[1].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(self.document_title)
        run.font.size = Pt(9)
        run.font.color.rgb = G3_GREEN

        # Right cell: Page number in green box
        p = cells[2].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        self._add_page_number_field(p)

        # Remove table borders
        tbl = header_table._tbl
        tblPr = tbl.tblPr if tbl.tblPr is not None else OxmlElement('w:tblPr')
        tblBorders = OxmlElement('w:tblBorders')
        for border_name in ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']:
            border = OxmlElement(f'w:{border_name}')
            border.set(qn('w:val'), 'nil')
            tblBorders.append(border)
        tblPr.append(tblBorders)
        if tbl.tblPr is None:
            tbl.insert(0, tblPr)

        # === FOOTER ===
        footer = section.footer
        footer.is_linked_to_previous = False

        # Create a table for footer layout: Company | Website | Email
        footer_table = footer.add_table(rows=1, cols=3, width=Cm(16))
        footer_table.autofit = False
        footer_table.allow_autofit = False

        # Set column widths
        footer_table.columns[0].width = Cm(5.3)
        footer_table.columns[1].width = Cm(5.3)
        footer_table.columns[2].width = Cm(5.3)

        cells = footer_table.rows[0].cells

        # Left cell: Company name (black per PDF)
        p = cells[0].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        run = p.add_run("G3 DT, S.L.")
        run.font.size = Pt(9)
        # Black text per original PDF

        # Center cell: Website (green #008000 per PDF)
        p = cells[1].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run("www.g3dt.com")
        run.font.size = Pt(9)
        run.font.color.rgb = G3_GREEN_LINKS  # #008000

        # Right cell: Email (black per PDF)
        p = cells[2].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        run = p.add_run("g3@g3dt.com")
        run.font.size = Pt(9)
        # Black text per original PDF

        # Remove table borders
        tbl = footer_table._tbl
        tblPr = tbl.tblPr if tbl.tblPr is not None else OxmlElement('w:tblPr')
        tblBorders = OxmlElement('w:tblBorders')
        for border_name in ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']:
            border = OxmlElement(f'w:{border_name}')
            border.set(qn('w:val'), 'nil')
            tblBorders.append(border)
        tblPr.append(tblBorders)
        if tbl.tblPr is None:
            tbl.insert(0, tblPr)

    def _setup_styles(self):
        """Create G3DT document styles.

        Font sizes corrected from PDF analysis (2026-01-04):
        - Body: 10pt Swiss721BT-LightExtended (we use Calibri as substitute)
        - H1 (sections): 12pt dark green (#003300)
        - H2 (subsections): 11pt dark green (#003300)
        - Tables: 9pt
        """
        styles = self.doc.styles

        # === Normal (Body Text): 10pt (was 11pt) ===
        normal = styles['Normal']
        normal.font.name = 'Calibri'
        normal.font.size = Pt(10)  # Corrected from 11pt
        normal.font.color.rgb = RGBColor(0, 0, 0)
        normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        normal.paragraph_format.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
        normal.paragraph_format.line_spacing = 1.15
        normal.paragraph_format.space_after = Pt(6)

        # === Heading 1: 12pt Bold Dark Green (#003300) ===
        # NOT underlined, NOT all caps (per PDF analysis)
        h1 = styles['Heading 1']
        h1.font.name = 'Calibri'
        h1.font.size = Pt(12)  # Corrected from 14pt
        h1.font.bold = False   # PDF shows not bold, just colored
        h1.font.color.rgb = G3_GREEN_HEADINGS  # #003300
        h1.font.underline = False  # Corrected: not underlined
        h1.font.all_caps = False   # Corrected: not all caps
        h1.paragraph_format.space_before = Pt(18)
        h1.paragraph_format.space_after = Pt(12)
        h1.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT

        # === Heading 2: 11pt Dark Green (#003300) ===
        h2 = styles['Heading 2']
        h2.font.name = 'Calibri'
        h2.font.size = Pt(11)  # Corrected from 12pt
        h2.font.bold = False   # PDF shows not bold
        h2.font.color.rgb = G3_GREEN_HEADINGS  # #003300
        h2.font.underline = False
        h2.paragraph_format.space_before = Pt(12)
        h2.paragraph_format.space_after = Pt(6)
        h2.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT

        # === Heading 3: 10pt Italic Black ===
        h3 = styles['Heading 3']
        h3.font.name = 'Calibri'
        h3.font.size = Pt(10)  # Match body size
        h3.font.bold = False
        h3.font.italic = True
        h3.font.color.rgb = RGBColor(0, 0, 0)
        h3.paragraph_format.space_before = Pt(6)
        h3.paragraph_format.space_after = Pt(3)

        # === Caption: 10pt Centered ===
        if 'Caption' not in [s.name for s in styles]:
            caption = styles.add_style('Caption', WD_STYLE_TYPE.PARAGRAPH)
        else:
            caption = styles['Caption']
        caption.font.name = 'Calibri'
        caption.font.size = Pt(10)
        caption.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        caption.paragraph_format.space_before = Pt(6)
        caption.paragraph_format.space_after = Pt(12)

        # === Table Header style: 9pt (corrected from 10pt) ===
        if 'Table Header' not in [s.name for s in styles]:
            th = styles.add_style('Table Header', WD_STYLE_TYPE.PARAGRAPH)
            th.font.name = 'Calibri'
            th.font.size = Pt(9)  # Corrected from 10pt
            th.font.bold = True
            th.font.color.rgb = RGBColor(255, 255, 255)
            th.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER

    def _set_cell_shading(self, cell, color_hex):
        """Set cell background color."""
        shading = OxmlElement('w:shd')
        shading.set(qn('w:fill'), color_hex)
        cell._tc.get_or_add_tcPr().append(shading)

    def add_cover_page(self, data: dict):
        """Add cover page with G3DT branding."""
        # Top: 25 anys banner (full width, centered)
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if self.cover_image_path and Path(self.cover_image_path).exists():
            run = p.add_run()
            # Banner is horizontal, use width constraint
            run.add_picture(self.cover_image_path, width=Cm(12))
        else:
            run = p.add_run("[25 anys - Compromesos amb el teu projecte]")
            run.font.size = Pt(12)
            run.font.color.rgb = G3_GREEN

        # Spacer
        for _ in range(13):
            self.doc.add_paragraph()

        # Large G3 watermark (use image if available, otherwise text placeholder)
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        if self.watermark_path and Path(self.watermark_path).exists():
            run = p.add_run()
            run.add_picture(self.watermark_path, width=Cm(8))
        else:
            run = p.add_run("G3")
            run.font.size = Pt(144)
            run.font.color.rgb = RGBColor(200, 220, 200)  # Semi-transparent green
            run.font.bold = True

        # More spacer
        for _ in range(3):
            self.doc.add_paragraph()

        # Metadata block
        metadata_items = [
            ("CLIENT:", data.get('client', '------')),
            ("EXPEDIENT:", data.get('expedient', '')),
            ("DATA:", data.get('data', '')),
            ("OBRA:", data.get('obra', '')),
        ]

        for label, value in metadata_items:
            p = self.doc.add_paragraph()
            run_label = p.add_run(label + " ")
            run_label.font.bold = True
            run_label.font.size = Pt(11)
            run_value = p.add_run(value)
            run_value.font.size = Pt(11)
            p.paragraph_format.line_spacing = 1.5

        # Page break after cover
        self.doc.add_page_break()

    def add_index(self, sections: list):
        """Add table of contents / index page."""
        self.doc.add_heading("ÍNDEX", level=1)

        for section in sections:
            p = self.doc.add_paragraph()
            p.add_run(section)
            p.paragraph_format.space_after = Pt(3)

        self.doc.add_paragraph()
        p = self.doc.add_paragraph()
        p.add_run("ANNEXES").font.bold = True

        annexes = [
            "Base de càlcul",
            "Registre d'assaigs mecànics",
            "Esquema situació assaigs",
            "Tall de correlació",
            "Fotografies",
            "Actes d'assaig de laboratori",
        ]
        for annex in annexes:
            p = self.doc.add_paragraph()
            p.add_run(f"• {annex}")
            p.paragraph_format.left_indent = Cm(0.5)

        self.doc.add_page_break()

    def add_section_1(self, data: dict):
        """Section 1: Presentació de l'estudi."""
        self.doc.add_heading("1. PRESENTACIÓ DE L'ESTUDI", level=1)

        # 1.1 Antecedents
        self.doc.add_heading("1.1. ANTECEDENTS", level=2)

        p = self.doc.add_paragraph()
        p.add_run(f"A petició de: ").font.bold = True
        p.add_run(data.get('client', '[CLIENT]'))

        self.doc.add_paragraph(
            "G3 D T S.L. ha redactat el present informe geològic/geotècnic d'acord amb "
            "les determinacions del Codi Tècnic de l'Edificació, Document Bàsic SE-C: "
            "Seguretat Estructural Fonaments."
        )

        # Building characteristics table
        self.doc.add_paragraph()
        p = self.doc.add_paragraph()
        p.add_run("Dades principals de l'edificació:").font.bold = True

        table = self.doc.add_table(rows=1, cols=2)
        table.style = 'Table Grid'

        building_data = [
            ("Tipus d'edificació", data.get('tipus_edificacio', 'Habitatge unifamiliar aïllat')),
            ("Nombre de plantes", data.get('plantes', 'Pb + 1Pp')),
            ("Superfície construïda", data.get('superficie', '---')),
            ("Tipus de fonamentació", data.get('fonamentacio', 'Superficial')),
            ("Profunditat màxima", data.get('profunditat_max', '---')),
        ]

        for label, value in building_data:
            row = table.add_row().cells
            row[0].text = label
            row[0].paragraphs[0].runs[0].font.bold = True
            row[1].text = value

        # Remove first empty row
        table._tbl.remove(table.rows[0]._tr)

        self.doc.add_paragraph()
        p = self.doc.add_paragraph()
        p.add_run("Taula 1").font.bold = True
        p.add_run(". Dades principals de l'edificació.")
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Location figure placeholder
        self.doc.add_paragraph()
        p = self.doc.add_paragraph("[FIGURA 1: Mapes de situació - ICGC topogràfic + ortofoto]")
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.runs[0].font.color.rgb = G3_GREEN

        p = self.doc.add_paragraph()
        p.add_run("Figura 1").font.bold = True
        p.add_run(f". Situació de la zona d'estudi (Font: ICGC, modificat).")
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # 1.2 Classificació CTE
        self.doc.add_heading("1.2. CLASSIFICACIÓ DE L'OBRA SEGONS EL CTE", level=2)

        table = self.doc.add_table(rows=1, cols=2)
        table.style = 'Table Grid'

        cte_data = [
            ("Tipus d'edificació considerada", data.get('cte_edificacio', 'C-0')),
            ("Tipus de sòl considerat", data.get('cte_sol', 'T-1')),
        ]

        for label, value in cte_data:
            row = table.add_row().cells
            row[0].text = label
            row[0].paragraphs[0].runs[0].font.bold = True
            row[1].text = value

        table._tbl.remove(table.rows[0]._tr)

        self.doc.add_paragraph()
        p = self.doc.add_paragraph()
        p.add_run("Taula 2").font.bold = True
        p.add_run(". Classificació segons CTE DB SE-C.")
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # 1.3 Objectius
        self.doc.add_heading("1.3. OBJECTIUS", level=2)

        objectives = [
            "Caracterització geològica i geotècnica dels materials del subsòl.",
            "Determinació del nivell freàtic.",
            "Definició de la tipologia de fonamentació més adient.",
            "Càlcul de la tensió admissible del terreny.",
            "Estimació dels assentaments previsibles.",
            "Determinació de l'agressivitat del medi.",
            "Avaluació del risc sísmic.",
        ]

        for obj in objectives:
            p = self.doc.add_paragraph(style='List Bullet')
            p.add_run(obj)

    def add_section_2(self, data: dict):
        """Section 2: Treballs de camp."""
        self.doc.add_heading("2. TREBALLS DE CAMP", level=1)

        # 2.1 Descripció zona
        self.doc.add_heading("2.1. DESCRIPCIÓ DE LA ZONA D'ESTUDI", level=2)

        p = self.doc.add_paragraph()
        p.add_run(f"El reconeixement del terreny es va realitzar el dia ")
        p.add_run(data.get('data_camp', '[DATA]')).font.bold = True
        p.add_run(".")

        self.doc.add_heading("2.1.1. Descripció de les parcel·les adjacents", level=3)

        adjacents = data.get('adjacents', {
            'nord': '[Descripció límit nord]',
            'sud': '[Descripció límit sud]',
            'est': '[Descripció límit est]',
            'oest': '[Descripció límit oest]',
        })

        for direction, desc in adjacents.items():
            p = self.doc.add_paragraph()
            p.add_run(f"• {direction.capitalize()}: ").font.bold = True
            p.add_run(desc)

        self.doc.add_heading("2.1.2. Descripció del solar", level=3)
        self.doc.add_paragraph(data.get('descripcio_solar',
            "[Descripció del solar: dimensions, pendent, vegetació, accessos, etc.]"))

        # 2.2 Reconeixement
        self.doc.add_heading("2.2. RECONEIXEMENT DEL TERRENY", level=2)

        self.doc.add_paragraph("S'han realitzat els següents assaigs in situ:")

        tests = data.get('assaigs_insitu', ["2 assaigs de penetració dinàmica tipus DPSH"])
        for test in tests:
            p = self.doc.add_paragraph(style='List Bullet')
            p.add_run(test)

        self.doc.add_paragraph()
        p = self.doc.add_paragraph("[FIGURA 2: Emplaçament dels assaigs sobre ortofoto]")
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.runs[0].font.color.rgb = G3_GREEN

        # 2.3 Justificació CTE
        self.doc.add_heading("2.3. JUSTIFICACIÓ DE COMPLIMENT DE CTE", level=2)
        self.doc.add_paragraph(
            "El reconeixement del terreny s'ha realitzat d'acord amb les especificacions "
            "del CTE DB SE-C per a edificacions tipus C-0 sobre terrenys T-1."
        )

        # 2.4 Descripció assaigs
        self.doc.add_heading("2.4. DESCRIPCIÓ DELS ASSAIGS IN SITU", level=2)

        # 2.4.1 DPSH (always present)
        self.doc.add_heading("2.4.1. Assaigs de penetració tipus \"DPSH\"", level=3)

        self.doc.add_paragraph(
            "L'assaig de penetració dinàmica contínua DPSH (Dynamic Probing Super Heavy) "
            "consisteix en la introducció al terreny d'una punta cònica mitjançant el "
            "cop d'una maça de 63,5 kg que cau des de 76 cm d'alçada."
        )

        self.doc.add_paragraph(
            "Es registra el nombre de cops necessaris per a fer penetrar la punta 20 cm (N₂₀). "
            "L'assaig es dóna per finalitzat quan s'assoleix el rebuig (N₂₀ > 100)."
        )

        p = self.doc.add_paragraph("[FOTOGRAFIA: Equip DPSH en operació]")
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.runs[0].font.color.rgb = G3_GREEN

        # 2.4.2 Resum assaigs (for simple DPSH-only project)
        self.doc.add_heading("2.4.2. Resum dels assaigs in-situ realitzats", level=3)

        # DPSH results table
        p = self.doc.add_paragraph()
        p.add_run("Assaigs DPSH:").font.bold = True

        table = self.doc.add_table(rows=1, cols=5)
        table.style = 'Table Grid'

        # Header row
        headers = ["Assaig", "Coord. X", "Coord. Y", "Cota (m)", "Prof. (m)"]
        hdr_cells = table.rows[0].cells
        for i, header in enumerate(headers):
            hdr_cells[i].text = header
            hdr_cells[i].paragraphs[0].runs[0].font.bold = True
            self._set_cell_shading(hdr_cells[i], "4A7C59")
            hdr_cells[i].paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)

        # Sample data rows
        dpsh_data = data.get('dpsh_results', [
            ("DPSH-1", "420000.0", "4600000.0", "100.0", "4.60"),
            ("DPSH-2", "420010.0", "4600010.0", "100.5", "5.20"),
        ])

        for row_data in dpsh_data:
            row = table.add_row().cells
            for i, value in enumerate(row_data):
                row[i].text = value

        self.doc.add_paragraph()
        p = self.doc.add_paragraph()
        p.add_run("Taula 3").font.bold = True
        p.add_run(". Resum dels assaigs DPSH realitzats.")
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # 2.5 Assaigs laboratori
        self.doc.add_heading("2.5. ASSAIGS DE LABORATORI", level=2)

        self.doc.add_paragraph(
            "S'han realitzat els següents assaigs de laboratori sobre mostres "
            "representatives dels materials travessats:"
        )

        table = self.doc.add_table(rows=1, cols=3)
        table.style = 'Table Grid'

        headers = ["Assaig", "Normativa", "Mostres"]
        hdr_cells = table.rows[0].cells
        for i, header in enumerate(headers):
            hdr_cells[i].text = header
            hdr_cells[i].paragraphs[0].runs[0].font.bold = True
            self._set_cell_shading(hdr_cells[i], "4A7C59")
            hdr_cells[i].paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)

        lab_tests = data.get('lab_tests', [
            ("Granulometria", "UNE 103101/95", "2"),
            ("Límits d'Atterberg", "UNE 103103/94", "2"),
            ("Sulfats", "---", "1"),
        ])

        for row_data in lab_tests:
            row = table.add_row().cells
            for i, value in enumerate(row_data):
                row[i].text = value

        self.doc.add_paragraph()
        p = self.doc.add_paragraph()
        p.add_run("Taula 4").font.bold = True
        p.add_run(". Assaigs de laboratori realitzats.")
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    def add_section_3(self, data: dict):
        """Section 3: Descripció geològica i geotècnica."""
        self.doc.add_heading("3. DESCRIPCIÓ GEOLÒGICA I GEOTÈCNICA", level=1)

        # 3.1 Marc geològic
        self.doc.add_heading("3.1. MARC GEOLÒGIC", level=2)

        self.doc.add_paragraph(data.get('marc_geologic',
            "[Descripció del context geològic regional, formacions, era geològica, etc. "
            "Referència a mapes ICGC/IGME.]"))

        p = self.doc.add_paragraph("[FIGURA 3: Mapa geològic de la zona (ICGC)]")
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.runs[0].font.color.rgb = G3_GREEN

        # 3.2 Caracterització materials
        self.doc.add_heading("3.2. CARACTERITZACIÓ DELS MATERIALS", level=2)

        # For simple project (3001631), single level
        self.doc.add_heading("3.2.1. Nivell 1: " + data.get('nivell1_nom',
            "Graves i sorres carbonatades"), level=3)

        self.doc.add_paragraph()
        p = self.doc.add_paragraph()
        p.add_run("Descripció litològica: ").font.bold = True
        p.add_run(data.get('nivell1_litologia',
            "[Descripció detallada del material: color, textura, composició, "
            "grau de cimentació, etc.]"))

        self.doc.add_paragraph()
        p = self.doc.add_paragraph()
        p.add_run("Localització: ").font.bold = True
        p.add_run(data.get('nivell1_localitzacio',
            "[Profunditat d'aparició, gruix, continuïtat lateral.]"))

        self.doc.add_paragraph()
        p = self.doc.add_paragraph()
        p.add_run("Resistència: ").font.bold = True
        p.add_run(data.get('nivell1_resistencia',
            "[Valors N₂₀ dels DPSH, interpretació de la compacitat.]"))

        # 3.3 Hidrologia
        self.doc.add_heading("3.3. HIDROLOGIA I HIDROGEOLOGIA", level=2)

        self.doc.add_heading("3.3.1. Hidrogeologia superficial", level=3)
        self.doc.add_paragraph(data.get('hidro_superficial',
            "[Cursos d'aigua propers, xarxa de drenatge, risc d'inundació.]"))

        self.doc.add_heading("3.3.2. Hidrogeologia subterrània", level=3)
        self.doc.add_paragraph(data.get('hidro_subterrania',
            "[Nivell freàtic detectat, aqüífers, permeabilitat estimada.]"))

        self.doc.add_heading("3.3.3. Permeabilitat", level=3)

        table = self.doc.add_table(rows=1, cols=3)
        table.style = 'Table Grid'

        headers = ["Nivell", "Material", "K (m/s)"]
        hdr_cells = table.rows[0].cells
        for i, header in enumerate(headers):
            hdr_cells[i].text = header
            hdr_cells[i].paragraphs[0].runs[0].font.bold = True
            self._set_cell_shading(hdr_cells[i], "4A7C59")
            hdr_cells[i].paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)

        perm_data = data.get('permeabilitat', [
            ("Nivell 1", "Graves i sorres", "10⁻³ - 10⁻⁵"),
        ])

        for row_data in perm_data:
            row = table.add_row().cells
            for i, value in enumerate(row_data):
                row[i].text = value

        # 3.4 Agressivitat
        self.doc.add_heading("3.4. AGRESSIVITAT DEL MEDI", level=2)

        self.doc.add_paragraph(
            "S'ha analitzat el contingut en sulfats solubles del terreny per determinar "
            "l'agressivitat al formigó segons la norma EHE / CE-21:"
        )

        table = self.doc.add_table(rows=2, cols=3)
        table.style = 'Table Grid'

        headers = ["Mostra", "SO₄ (mg/kg)", "Classe exposició"]
        hdr_cells = table.rows[0].cells
        for i, header in enumerate(headers):
            hdr_cells[i].text = header
            hdr_cells[i].paragraphs[0].runs[0].font.bold = True
            self._set_cell_shading(hdr_cells[i], "4A7C59")
            hdr_cells[i].paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)

        sulfat_data = data.get('sulfats', ("M-1", "< 2000", "No agressiu"))
        row = table.rows[1].cells
        for i, value in enumerate(sulfat_data):
            row[i].text = value

        # 3.5 Excavabilitat
        self.doc.add_heading("3.5. EXCAVABILITAT", level=2)
        self.doc.add_paragraph(data.get('excavabilitat',
            "[Recomanacions sobre maquinària d'excavació, ripabilitat, "
            "presència de blocs, etc.]"))

        # 3.6 Sísmica
        self.doc.add_heading("3.6. ACCELERACIÓ SÍSMICA DE REFERÈNCIA", level=2)

        self.doc.add_paragraph(
            "Segons la norma NCSE-02, els paràmetres sísmics per a la zona d'estudi són:"
        )

        sismic_params = data.get('sismica', {
            'ab': '< 0.04 g',
            'ac': '---',
            'K': '1.0',
            'C': '1.0',
            'S': '---',
        })

        for param, value in sismic_params.items():
            p = self.doc.add_paragraph()
            p.add_run(f"• {param} = ").font.bold = True
            p.add_run(value)

        # 3.7 Radó
        self.doc.add_heading("3.7. EXPOSICIÓ AL GAS RADÓ", level=2)

        self.doc.add_paragraph(
            "Segons el CTE DB HS-6, la zona d'estudi es classifica com a:"
        )

        p = self.doc.add_paragraph()
        p.add_run(data.get('rado_zona', 'ZONA 1')).font.bold = True
        p.add_run(f" - {data.get('rado_desc', '[Descripció de les mesures requerides]')}")

    def add_section_4_simple(self, data: dict):
        """Section 4: Conclusions (simple structure - no expansivity, no slopes)."""
        self.doc.add_heading("4. CONCLUSIONS", level=1)

        # 4.1 Geologia
        self.doc.add_heading("4.1. GEOLOGIA", level=2)

        self.doc.add_paragraph(data.get('conclusio_geologia',
            "[Resum dels materials identificats, estructura geològica, "
            "correlació entre punts de reconeixement.]"))

        p = self.doc.add_paragraph("[FIGURA 4: Tall de correlació geològica]")
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.runs[0].font.color.rgb = G3_GREEN

        # Geotechnical parameters table
        self.doc.add_paragraph()
        p = self.doc.add_paragraph()
        p.add_run("Característiques geotècniques dels materials:").font.bold = True

        table = self.doc.add_table(rows=1, cols=4)
        table.style = 'Table Grid'

        headers = ["Paràmetre", "Símbol", "Unitat", "Valor"]
        hdr_cells = table.rows[0].cells
        for i, header in enumerate(headers):
            hdr_cells[i].text = header
            hdr_cells[i].paragraphs[0].runs[0].font.bold = True
            self._set_cell_shading(hdr_cells[i], "4A7C59")
            hdr_cells[i].paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)

        geotech_params = data.get('geotech_params', [
            ("Densitat aparent", "γ", "kN/m³", "20.0"),
            ("Cohesió", "c'", "kPa", "0"),
            ("Angle de fricció", "φ'", "°", "35"),
            ("Mòdul de deformació", "E", "MPa", "50"),
        ])

        for row_data in geotech_params:
            row = table.add_row().cells
            for i, value in enumerate(row_data):
                row[i].text = value

        # 4.2 Hidrogeologia
        self.doc.add_heading("4.2. HIDROGEOLOGIA I AGRESSIVITAT", level=2)

        p = self.doc.add_paragraph()
        p.add_run("Nivell freàtic: ").font.bold = True
        p.add_run(data.get('nf_conclusio', "No detectat durant els treballs de camp."))

        p = self.doc.add_paragraph()
        p.add_run("Agressivitat: ").font.bold = True
        p.add_run(data.get('agressivitat_conclusio',
            "El terreny no presenta agressivitat al formigó (SO₄ < 2000 mg/kg)."))

        # 4.3 Fonamentació (for simple projects)
        self.doc.add_heading("4.3. FONAMENTACIÓ", level=2)

        self.doc.add_paragraph(data.get('fonamentacio_intro',
            "D'acord amb les característiques geotècniques dels materials identificats, "
            "es recomana:"))

        p = self.doc.add_paragraph()
        p.add_run("Tipus de fonamentació: ").font.bold = True
        p.add_run(data.get('tipus_fonament', "Sabates aïllades o corregudes."))

        p = self.doc.add_paragraph()
        p.add_run("Profunditat mínima d'encastament: ").font.bold = True
        p.add_run(data.get('profunditat_encast', "0.60 m respecte la rasant actual."))

        p = self.doc.add_paragraph()
        p.add_run("Tensió admissible: ").font.bold = True
        p.add_run("Qa = ").font.bold = True
        p.add_run(data.get('qa', "3.50") + " kg/cm²").font.bold = True

        p = self.doc.add_paragraph()
        p.add_run("Assentaments: ").font.bold = True
        p.add_run(data.get('assentaments', "< 1.50 cm (admissible segons CTE)."))

        p = self.doc.add_paragraph()
        p.add_run("Coeficient de balast: ").font.bold = True
        p.add_run("K₃₀ = " + data.get('k30', "6.0") + " kg/cm³")

    def add_signature_page(self, data: dict):
        """Add signature page."""
        self.doc.add_page_break()

        self.doc.add_paragraph(
            "G3 D T S.L. sol·licita que si es detectessin anomalies geotècniques "
            "durant l'execució de les obres, sigui comunicat immediatament per tal "
            "de revisar les recomanacions d'aquest informe."
        )

        self.doc.add_paragraph()
        self.doc.add_paragraph()

        p = self.doc.add_paragraph()
        p.add_run("Informe geològic / geotècnic,")

        p = self.doc.add_paragraph()
        p.add_run(f"Expedient Núm.: {data.get('expedient', '[EXPEDIENT]')}")

        self.doc.add_paragraph()

        p = self.doc.add_paragraph()
        p.add_run(f"{data.get('lloc_signatura', '[LOCALITAT]')}, {data.get('data_signatura', '[DATA]')}")

        self.doc.add_paragraph()
        self.doc.add_paragraph()
        p = self.doc.add_paragraph("[SEGELL EMPRESA]")
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        self.doc.add_paragraph()

        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run(data.get('signant_nom', '[NOM SIGNANT]'))

        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run(data.get('signant_titol', 'Geòleg/a col. [XXXX]'))

        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run(data.get('signant_rol', 'G3 DT S.L.'))

    def add_annexes_placeholder(self):
        """Add annex section placeholders."""
        self.doc.add_page_break()

        annexes = [
            "ANNEX 1: BASE DE CÀLCUL",
            "ANNEX 2: REGISTRE D'ASSAIGS MECÀNICS",
            "ANNEX 3: ESQUEMA SITUACIÓ ASSAIGS",
            "ANNEX 4: TALL DE CORRELACIÓ",
            "ANNEX 5: FOTOGRAFIES",
            "ANNEX 6: ACTES D'ASSAIG DE LABORATORI",
        ]

        for annex in annexes:
            self.doc.add_heading(annex, level=1)
            p = self.doc.add_paragraph(f"[Contingut de {annex}]")
            p.runs[0].font.color.rgb = G3_GREEN
            self.doc.add_page_break()

    def generate(self, data: dict, output_path: str):
        """Generate complete report."""

        # Set document title for header
        expedient = data.get('expedient', '[EXPEDIENT]')
        lloc = data.get('obra', '').split('\n')[-1] if data.get('obra') else '[LOCALITAT]'
        self.document_title = f"{expedient}/Estudi geològic – geotècnic_{lloc}"

        # Cover page
        self.add_cover_page(data)

        # Set up header/footer for pages after cover
        section = self.doc.sections[0]
        self._setup_header_footer(section, data)

        # Index
        sections = [
            "1. Presentació de l'estudi",
            "   1.1. Antecedents",
            "   1.2. Classificació de l'obra segons el CTE",
            "   1.3. Objectius",
            "2. Treballs de camp",
            "   2.1. Descripció de la zona d'estudi",
            "   2.2. Reconeixement del terreny",
            "   2.3. Justificació de compliment de CTE",
            "   2.4. Descripció dels assaigs in situ",
            "   2.5. Assaigs de laboratori",
            "3. Descripció geològica i geotècnica",
            "   3.1. Marc geològic",
            "   3.2. Caracterització dels materials",
            "   3.3. Hidrologia i hidrogeologia",
            "   3.4. Agressivitat del medi",
            "   3.5. Excavabilitat",
            "   3.6. Acceleració sísmica de referència",
            "   3.7. Exposició al gas radó",
            "4. Conclusions",
            "   4.1. Geologia",
            "   4.2. Hidrogeologia i agressivitat",
            "   4.3. Fonamentació",
        ]
        self.add_index(sections)

        # Main sections
        self.add_section_1(data)
        self.add_section_2(data)
        self.add_section_3(data)
        self.add_section_4_simple(data)
        self.add_signature_page(data)

        # Annexes
        self.add_annexes_placeholder()

        # Save
        self.doc.save(output_path)
        print(f"Report generated: {output_path}")
        return output_path


# Sample data based on 3001631 (Rubí)
SAMPLE_DATA_RUBI = {
    # Cover
    'client': '------',
    'expedient': '3001631',
    'data': '21/11/25',
    'obra': 'ESTUDI GEOLÒGIC / GEOTÈCNIC\nPER A LA CONSTRUCCIÓ D\'UN HABITATGE UNIFAMILIAR AÏLLAT\nRUBÍ (VALLÈS OCCIDENTAL)',

    # Section 1
    'tipus_edificacio': 'Habitatge unifamiliar aïllat',
    'plantes': 'Pb + 1Pp',
    'superficie': '---',
    'fonamentacio': 'Superficial',
    'profunditat_max': '---',
    'cte_edificacio': 'C-0',
    'cte_sol': 'T-1',

    # Section 2
    'data_camp': '15/11/2025',
    'adjacents': {
        'nord': 'Solar urbanitzat',
        'sud': 'Carrer accés',
        'est': 'Habitatge unifamiliar existent',
        'oest': 'Solar en construcció',
    },
    'descripcio_solar': 'Solar de geometria rectangular amb pendent suau cap al sud. '
                        'Superfície aproximada de 500 m². Vegetació herbàcia escassa. '
                        'Accés rodat pel carrer sud.',
    'assaigs_insitu': [
        "2 assaigs de penetració dinàmica tipus DPSH"
    ],
    'dpsh_results': [
        ("DPSH-1", "420125.0", "4600230.0", "125.5", "4.60"),
        ("DPSH-2", "420135.0", "4600225.0", "125.0", "5.20"),
    ],
    'lab_tests': [
        ("Granulometria", "UNE 103101/95", "2"),
        ("Límits d'Atterberg", "UNE 103103/94", "2"),
        ("Sulfats solubles", "---", "1"),
    ],

    # Section 3
    'marc_geologic': 'La zona d\'estudi se situa en el context geològic de la Depressió '
                     'del Vallès, una fossa tectònica d\'edat neògena limitada per falles '
                     'normals. Els materials superficials corresponen a dipòsits quaternaris '
                     'de peu de mont (cons al·luvials i col·luvions) que recobreixen un '
                     'substrat miocènic de lutites i gresos.',
    'nivell1_nom': 'Graves i sorres carbonatades',
    'nivell1_litologia': 'Graves de composició carbonatada (calcàries i dolomies) amb matriu '
                         'sorrenca-llimosa de color beix-groguenc. Granulometria gruixuda a '
                         'mitjana, amb còdols subarrodonits de 2-8 cm. Grau de cimentació moderat. '
                         'Presència ocasional de nòduls carbonatats.',
    'nivell1_localitzacio': 'Des de la superfície fins a la profunditat màxima investigada '
                            '(4.60-5.20 m). Gruix mínim reconegut > 4.5 m.',
    'nivell1_resistencia': 'Els valors N₂₀ obtinguts als assaigs DPSH oscil·len entre 15 i '
                           'rebuig (N₂₀ > 100), amb un increment progressiu amb la profunditat. '
                           'Compacitat: densa a molt densa.',
    'hidro_superficial': 'No s\'observen cursos d\'aigua superficials en l\'àmbit d\'estudi. '
                         'El drenatge natural de la zona és cap al sud-est seguint el pendent '
                         'topogràfic.',
    'hidro_subterrania': 'No s\'ha detectat nivell freàtic durant l\'execució dels treballs de '
                         'camp fins a la profunditat màxima investigada (5.20 m).',
    'permeabilitat': [
        ("Nivell 1", "Graves carbonatades", "10⁻³ - 10⁻⁵"),
    ],
    'sulfats': ("M-1", "632.3", "No agressiu (< 2000)"),
    'excavabilitat': 'Els materials identificats presenten excavabilitat mitjana-alta. '
                     'Es recomana l\'ús de retroexcavadora convencional. En zones amb '
                     'major grau de cimentació pot ser necessari l\'ús de martell hidràulic.',
    'sismica': {
        'ab': '0.08 g',
        'K': '1.0',
        'C': '1.0',
        'ρ': '1.0',
    },
    'rado_zona': 'ZONA 1',
    'rado_desc': 'No es requereixen mesures especials de protecció davant el radó.',

    # Section 4
    'conclusio_geologia': 'El subsòl de la parcel·la estudiada està constituït per un únic '
                          'nivell geotècnic format per graves i sorres carbonatades de compacitat '
                          'densa a molt densa. Aquests materials presenten bones característiques '
                          'geotècniques per a la fonamentació de l\'edificació projectada.',
    'geotech_params': [
        ("Densitat aparent", "γ", "kN/m³", "21.0"),
        ("Cohesió efectiva", "c'", "kPa", "0"),
        ("Angle de fricció efectiu", "φ'", "°", "36"),
        ("Mòdul de deformació", "E", "MPa", "60"),
    ],
    'nf_conclusio': 'No detectat fins a 5.20 m de profunditat.',
    'agressivitat_conclusio': 'El terreny no presenta agressivitat al formigó (SO₄ = 632.3 mg/kg < 2000 mg/kg).',
    'fonamentacio_intro': 'Tenint en compte les característiques geotècniques dels materials '
                          'identificats i les dimensions de l\'edificació projectada, es recomana:',
    'tipus_fonament': 'Sabates aïllades o corregudes, fonamentades sobre el nivell de graves '
                      'i sorres carbonatades.',
    'profunditat_encast': '0.60 m respecte la rasant actual del terreny, superant el gruix '
                          'de terra vegetal.',
    'qa': '3.50',
    'assentaments': '< 1.50 cm, admissibles segons CTE DB SE-C.',
    'k30': '6.0',

    # Signature
    'lloc_signatura': 'Rubí',
    'data_signatura': 'novembre de 2025',
    'signant_nom': '[Nom del/la geòleg/a]',
    'signant_titol': 'Geòleg/a col. [XXXX]',
    'signant_rol': 'G3 DT S.L.',
}


def main():
    parser = argparse.ArgumentParser(description='Generate G3DT geotechnical report')
    parser.add_argument('--output', '-o', default='informe_test.docx',
                        help='Output file path (default: informe_test.docx)')
    parser.add_argument('--sample', action='store_true',
                        help='Use sample data from 3001631 (Rubí)')
    parser.add_argument('--logo', '-l', default='assets/g3-logo-circular.png',
                        help='Path to logo image (default: assets/g3-logo-circular.png)')
    parser.add_argument('--cover-image', '-c', default='assets/25-anys-banner.png',
                        help='Path to cover banner (default: assets/25-anys-banner.png)')
    parser.add_argument('--watermark', '-w', default='assets/g3-watermark.png',
                        help='Path to watermark image (default: assets/g3-watermark.png)')
    args = parser.parse_args()

    # Resolve paths relative to script directory
    script_dir = Path(__file__).parent
    logo_path = script_dir / args.logo if not Path(args.logo).is_absolute() else Path(args.logo)
    cover_image_path = script_dir / args.cover_image if not Path(args.cover_image).is_absolute() else Path(args.cover_image)
    watermark_path = script_dir / args.watermark if not Path(args.watermark).is_absolute() else Path(args.watermark)

    generator = G3DTReportGenerator(
        logo_path=str(logo_path),
        cover_image_path=str(cover_image_path),
        watermark_path=str(watermark_path)
    )

    if args.sample:
        data = SAMPLE_DATA_RUBI
    else:
        # Placeholder for data input
        data = SAMPLE_DATA_RUBI
        print("Using sample data. Implement data input for production use.")

    output_path = Path(args.output)
    generator.generate(data, str(output_path))


if __name__ == '__main__':
    main()
