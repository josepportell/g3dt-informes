#!/usr/bin/env python3
"""
G3DT Full Report Generator - With Cover, Index, and All Sections

This generator creates complete G3DT reports with:
- Cover page (preserved from base template's first page header)
- Index/Table of Contents
- All 4 main sections
- Proper styling throughout
- Updated header with expedient/location

Usage:
    python generate_full_report.py --scenario balaguer --output report.docx
"""

import argparse
import re
from pathlib import Path
from datetime import datetime
from docx import Document
from docx.shared import Pt, Cm, Inches, RGBColor, Twips
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

# Path to base template and images
BASE_TEMPLATE = Path(__file__).parent / "base-template.docx"
IMAGES_DIR = Path(__file__).parent / "images"

# Standard image mapping for figures
STANDARD_IMAGES = {
    "figura_1": "location_map.png",       # Situació de la zona d'estudi
    "figura_2": "site_plan.png",          # Situació assaigs realitzats
    "figura_4": "geological_map.png",     # Mapa geològic
    "foto_1": "site_photo_1.jpeg",        # Vista general zona
    "foto_2": "dpsh_photo.jpeg",          # Màquina DPSH
    "foto_3": "material_detail.jpeg",     # Detall materials
}


class G3DTFullReportGenerator:
    """Generate complete G3DT reports with cover, index, and all sections."""

    def __init__(self, base_template: str = None):
        self.base_path = Path(base_template) if base_template else BASE_TEMPLATE
        if not self.base_path.exists():
            raise FileNotFoundError(f"Base template not found: {self.base_path}")

    def create_report(self, scenario: dict, output_path: str) -> Path:
        """Create a full report from scenario data."""
        doc = Document(str(self.base_path))

        # Clear body content but keep headers/footers (preserves cover design)
        self._clear_body_content(doc)

        # Update header2 (regular pages) with new expedient/location
        self._update_regular_header(doc, scenario)

        # Build report content
        self._add_cover_content(doc, scenario)
        self._add_index(doc, scenario)
        self._add_section_1_presentacio(doc, scenario)
        self._add_section_2_treballs_camp(doc, scenario)
        self._add_section_3_descripcio(doc, scenario)
        self._add_section_4_conclusions(doc, scenario)
        self._add_signature(doc, scenario)

        # Save
        output = Path(output_path)
        doc.save(output)
        print(f"✅ Full report generated: {output}")
        return output

    def _clear_body_content(self, doc: Document):
        """Clear body content, preserving headers/footers."""
        for para in list(doc.paragraphs):
            para._element.getparent().remove(para._element)
        for table in list(doc.tables):
            table._element.getparent().remove(table._element)

    def _update_regular_header(self, doc: Document, scenario: dict):
        """Update the regular header (header2) with new expedient info."""
        expedient = scenario.get("expedient", "")
        location = scenario.get("ubicacio", "")

        if doc.sections:
            section = doc.sections[0]
            # The regular header (not first page) contains the expedient text
            header = section.header
            for para in header.paragraphs:
                # Look for the expedient pattern and update it
                if "Estudi" in para.text or para.text.strip().isdigit():
                    # Clear and rebuild
                    for run in para.runs:
                        if "Estudi" in run.text or run.text.strip().isdigit():
                            run.text = ""
                # Update with new info (we'll set it in a specific way)
            # Actually, let's just update the text directly via XML for reliability
            self._update_header_text(header, expedient, location)

    def _update_header_text(self, header, expedient: str, location: str):
        """Update header text via direct text replacement."""
        header_xml = header._element.xml
        # Replace patterns like "3001631" with new expedient
        # And "RUBI" with new location
        for para in header.paragraphs:
            for run in para.runs:
                text = run.text
                # Replace old expedient pattern
                if re.match(r'^\d{7}$', text.strip()):
                    run.text = expedient
                # Replace location (uppercase)
                elif text.strip().isupper() and len(text.strip()) > 2:
                    run.text = location.upper()

    def _add_cover_content(self, doc: Document, scenario: dict):
        """Add cover page content (body portion - header has the design)."""
        # The cover design is in the first page header (preserved from base template)
        # We just add an empty heading and page break to trigger the first page
        doc.add_paragraph("", style="Heading 1")
        doc.add_page_break()

    def _add_index(self, doc: Document, scenario: dict):
        """Add Table of Contents (Index)."""
        # Title
        para = doc.add_paragraph("Índex", style="Normal")
        para.runs[0].bold = True
        para.runs[0].font.size = Pt(14)
        doc.add_paragraph()

        # TOC entries - using proper toc styles (including toc 3 for third-level)
        toc_entries = [
            ("toc 1", "1 . PRESENTACIÓ DE L'ESTUDI", "2"),
            ("toc 2", "1.1. ANTECEDENTS", "2"),
            ("toc 2", "1.2. CLASSIFICACIÓ DE L'OBRA SEGONS EL CTE", "3"),
            ("toc 2", "1.3. OBJECTIUS", "3"),
            ("toc 1", "2. TREBALLS DE CAMP", "4"),
            ("toc 2", "2.1. DESCRIPCIÓ DE LA ZONA D'ESTUDI", "4"),
            ("toc 3", "2.1.1. Descripció de les parcel·les adjacents", "4"),
            ("toc 3", "2.1.2. Descripció del solar", "4"),
            ("toc 2", "2.2. RECONEIXEMENT DEL TERRENY", "5"),
            ("toc 2", "2.3. JUSTIFICACIÓ DE COMPLIMENT DE CTE", "6"),
            ("toc 2", "2.4. DESCRIPCIÓ DELS ASSAIGS IN SITU", "7"),
            ("toc 3", "2.4.1. Assaigs de penetració tipus \"DPSH\"", "7"),
            ("toc 3", "2.4.2. Assaig tipus S.P.T.", "8"),
            ("toc 3", "2.4.3. Resum dels assaigs in-situ realitzats", "8"),
            ("toc 2", "2.5. ASSAIGS DE LABORATORI", "9"),
            ("toc 1", "3. DESCRIPCIÓ GEOLÒGICA I GEOTÈCNICA", "10"),
            ("toc 2", "3.1. MARC GEOLÒGIC", "10"),
            ("toc 2", "3.2. CARACTERITZACIÓ DELS MATERIALS", "11"),
            ("toc 3", "3.2.1. Nivell 1", "11"),
            ("toc 2", "3.3. HIDROLOGIA I HIDROGEOLOGIA", "13"),
            ("toc 3", "3.3.1. Hidrogeologia superficial", "13"),
            ("toc 3", "3.3.2. Hidrogeologia subterrània", "13"),
            ("toc 3", "3.3.3. Permeabilitat dels materials", "14"),
            ("toc 2", "3.4. AGRESSIVITAT DEL MEDI", "14"),
            ("toc 2", "3.5. EXCAVABILITAT", "14"),
            ("toc 2", "3.6. ACCELERACIÓ SISMICA DE REFERÈNCIA", "15"),
            ("toc 2", "3.7. EXPOSICIÓ AL GAS RADÓ", "16"),
            ("toc 1", "4. CONCLUSIONS", "18"),
            ("toc 2", "4.1. GEOLOGIA", "18"),
            ("toc 2", "4.2. HIDROGEOLOGIA I AGRESSIVITAT", "19"),
            ("toc 2", "4.3. FONAMENTACIÓ", "19"),
        ]

        for style, text, page in toc_entries:
            para = doc.add_paragraph(style=style)
            # Add text with tab and page number
            para.add_run(text)
            para.add_run("\t")
            para.add_run(page)
            # Set tab stop for right-aligned page numbers
            self._set_toc_tab_stop(para)

        doc.add_page_break()

    def _set_toc_tab_stop(self, para):
        """Set right-aligned tab stop with dot leader for TOC."""
        tab_stops = para.paragraph_format.tab_stops
        tab_stops.add_tab_stop(Cm(15), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)

    def _add_section_1_presentacio(self, doc: Document, scenario: dict):
        """Add Section 1: Presentació de l'Estudi."""
        doc.add_paragraph("1 . PRESENTACIÓ DE L'ESTUDI", style="Heading 1")

        doc.add_paragraph("A petició de:", style="Normal")
        para = doc.add_paragraph(scenario.get("client", "CLIENT"), style="Normal")
        para.runs[0].bold = True

        doc.add_paragraph(
            "G3 DT, S.L. ha realitzat el següent informe geotècnic segons les instruccions "
            "del DB SE-C Cimientos fetes pel \"Código Técnico de la Edificación\" CTE, "
            "que entrà en vigor el 29 de març del 2006.",
            style="Normal"
        )

        # 1.1 Antecedents
        doc.add_paragraph("1.1. ANTECEDENTS", style="Heading 2")
        doc.add_paragraph(
            f"Segons ens indica el sol·licitant, {scenario.get('client', 'el client')}, "
            f"es vol valorar les característiques geològiques i geotècniques d'una zona "
            f"on es preveu la construcció d'un {scenario.get('tipus_obra', 'habitatge unifamiliar aïllat')}.",
            style="Normal"
        )
        doc.add_paragraph(
            "L'edificació que es preveu construir presentarà les següents característiques:",
            style="Normal"
        )

        # Table 1
        self._add_table(doc,
            headers=["Característica", "Valor"],
            rows=[
                ["Tipus edificació", scenario.get("tipus_obra", "Habitatge unifamiliar")],
                ["Nombre de plantes", scenario.get("plantes", "PB + 1")],
                ["Superfície parcel·la", scenario.get("superficie_parcela", "600 m²")],
                ["Superfície construïda", scenario.get("superficie_construida", "180 m²")],
            ],
            caption="Taula 1. Resum de les principals dades de l'edificació a construir."
        )

        doc.add_paragraph(
            f"L'edificació es situarà a {scenario.get('adreca', 'una parcel·la')}, "
            f"{scenario.get('ubicacio', 'localitat')}, {scenario.get('provincia', 'Lleida')}.",
            style="Normal"
        )
        self._add_figure(doc, "figura_1", "Figura 1. Situació de la zona d'estudi (ICGC 2026).")

        # 1.2 Classificació CTE
        doc.add_paragraph("1.2. CLASSIFICACIÓ DE L'OBRA SEGONS EL CTE", style="Heading 2")
        doc.add_paragraph(
            "A partir de les dades exposades pel client, tant tipus d'edificació com "
            "localització de l'obra, un tècnic qualificat en la realització de l'estudi "
            "realitza la següent classificació, segons els criteris que marca el DB SE-C del citat CTE:",
            style="Normal"
        )
        self._add_table(doc,
            headers=["Paràmetre", "Classificació"],
            rows=[
                ["Tipus edificació", scenario.get("cte_edificacio", "C-0")],
                ["Tipus terreny", scenario.get("cte_sol", "T-1")],
            ],
            caption="Taula 2. Classificació de la construcció segons DB-SE-C del CTE."
        )

        # 1.3 Objectius
        doc.add_paragraph("1.3. OBJECTIUS", style="Heading 2")
        doc.add_paragraph(
            "Per la realització del present estudi, s'ha dut a terme una campanya de camp "
            "tenint en compte que els objectius de l'estudi són:",
            style="Normal"
        )
        objectives = [
            "Estudi de l'entorn geològic de l'obra.",
            "Reconeixement, caracterització i potència dels materials del subsòl de la zona, "
            "des del punt de vista geològic i geotècnic, i tenint en compte les recomanacions del CTE.",
            "Cota del nivell freàtic, quan es detecti dins de les cotes assajades.",
            "Determinació de les càrregues admissibles dels materials sota diferents solucions de fonamentació.",
            "Estimació dels assentaments per a les càrregues admissibles exposades.",
            "Recomanacions sobre condicionants geològics i geotècnics que puguin afectar a l'obra.",
        ]
        for obj in objectives:
            doc.add_paragraph(obj, style="List Bullet")

        doc.add_page_break()

    def _add_section_2_treballs_camp(self, doc: Document, scenario: dict):
        """Add Section 2: Treballs de Camp."""
        doc.add_paragraph("2. TREBALLS DE CAMP", style="Heading 1")

        data_camp = scenario.get("data_camp", datetime.now().strftime("%d de gener de 2026"))
        doc.add_paragraph(
            f"El dia {data_camp}, es va visitar l'obra per tal de:",
            style="Normal"
        )
        tasks = [
            "Realitzar una inspecció geològica de la zona, reconeixent el tipus de terreny.",
            "Dissenyar la campanya de camp.",
            "Comprovar l'accessibilitat de maquinària a l'interior del solar.",
            "Localitzar els punts on es realitzaran els assaigs.",
        ]
        for task in tasks:
            doc.add_paragraph(task, style="List Bullet")

        # 2.1 Descripció zona
        doc.add_paragraph("2.1. DESCRIPCIÓ DE LA ZONA D'ESTUDI", style="Heading 2")

        self._add_heading3(doc, "2.1.1. Descripció de les parcel·les adjacents")
        doc.add_paragraph(
            f"La parcel·la objecte d'estudi es situa al municipi de {scenario.get('ubicacio', 'la localitat')}, "
            "pren una morfologia rectangular, i limita:",
            style="Normal"
        )
        limits = [
            "Per la part nord, amb parcel·les amb edificacions residencials.",
            "Per la part sud, amb el vial d'accés.",
            "Per la part est i oest, amb construccions de característiques similars.",
        ]
        for limit in limits:
            doc.add_paragraph(limit, style="List Bullet")

        self._add_heading3(doc, "2.1.2. Descripció del solar")
        doc.add_paragraph(
            "El dia dels treballs de camp es realitza l'entrada a la zona d'estudi. "
            "El solar es localitza sense construccions i pavimentacions. "
            "Topogràficament, es mostra pràcticament pla.",
            style="Normal"
        )
        self._add_figure(doc, "foto_1", "Fotografia 1. Vista general de la zona d'estudi.")

        # 2.2 Reconeixement
        doc.add_paragraph("2.2. RECONEIXEMENT DEL TERRENY", style="Heading 2")
        doc.add_paragraph(
            f"La campanya de camp, que s'ha realitzat el dia {data_camp}, "
            "ha consistit en la realització de:",
            style="Normal"
        )
        tests = [
            "3 assaigs de penetració dinàmica tipus DPSH (veure annex \"Registre assaigs mecànics\").",
            "1 assaig SPT amb recuperació de mostra (veure annex \"Registre assaigs mecànics\").",
            "Observacions de camp realitzades pel tècnic de l'empresa desplaçat a l'obra.",
            "Reportatge fotogràfic (veure annex \"Fotografies\").",
        ]
        for test in tests:
            doc.add_paragraph(test, style="List Bullet")

        doc.add_paragraph(
            "Els assaigs in situ han estat realitzats per TPS PROSPECCIÓ DEL SUBSÒL SL, "
            "laboratori d'assaigs per al control de qualitat de l'edificació.",
            style="Normal"
        )
        self._add_figure(doc, "figura_2", "Figura 2. Situació de l'estructura projectada i els assaigs realitzats.")

        # 2.3 Justificació CTE
        doc.add_paragraph("2.3. JUSTIFICACIÓ DE COMPLIMENT DE CTE", style="Heading 2")
        doc.add_paragraph(
            "A partir de la campanya realitzada i la classificació de l'obra que s'obté "
            "segons l'apartat 1.2 del present estudi, es compleixen els mínims establerts "
            "pel DB SE-C del Código Técnico de la Edificación pel que fa referència al "
            "nombre de punts d'investigació realitzats, així com a les profunditats assolides.",
            style="Normal"
        )

        # 2.4 Descripció assaigs
        doc.add_paragraph("2.4. DESCRIPCIÓ DELS ASSAIGS IN SITU", style="Heading 2")

        self._add_heading3(doc, "2.4.1. Assaigs de penetració tipus \"DPSH\"")
        doc.add_paragraph(
            "L'assaig consisteix a clavar en el terreny una barnilla de secció circular "
            "mitjançant la caiguda d'una massa, per penetrar en intervals de 20 cm. "
            "El comptatge del número de cops ens donarà un valor que anomenarem N₂₀.",
            style="Normal"
        )
        doc.add_paragraph("Característiques de l'assaig:", style="Normal")
        specs = [
            "Alçada de caiguda del Pes: 75 cm",
            "Diàmetre de la punta de penetració: 51 mm",
            "Interval de penetració: 20 cm",
            "Pes: 63.5 Kg",
        ]
        for spec in specs:
            doc.add_paragraph(spec, style="List Bullet")

        self._add_figure(doc, "foto_2", "Fotografia 2. Vista de la màquina utilitzada en l'assaig DPSH.")

        self._add_heading3(doc, "2.4.2. Assaig tipus S.P.T. (\"Standard Penetration Test\")")
        doc.add_paragraph(
            "L'assaig SPT consisteix en clavar un mostrador de secció cilíndrica "
            "de paret gruixuda mitjançant la caiguda d'una maça. Es comptabilitza "
            "el nombre de cops per penetrar 3 intervals de 15 cm cadascun.",
            style="Normal"
        )

        self._add_heading3(doc, "2.4.3. Resum dels assaigs in-situ realitzats")
        self._add_table(doc,
            headers=["Assaig", "Coord. X", "Coord. Y", "Cota (m)", "Prof. (m)"],
            rows=[
                ["P-1", "[REVISAR]", "[REVISAR]", "245.0", "4.80"],
                ["P-2", "[REVISAR]", "[REVISAR]", "245.1", "3.60"],
                ["P-3", "[REVISAR]", "[REVISAR]", "244.9", "4.20"],
                ["SPT-1", "[REVISAR]", "[REVISAR]", "245.0", "5.00"],
            ],
            caption="Taula 3. Coordenades i profunditats dels assaigs realitzats."
        )

        # 2.5 Assaigs laboratori
        doc.add_paragraph("2.5. ASSAIGS DE LABORATORI", style="Heading 2")
        doc.add_paragraph(
            "De les mostres recuperades en els assaigs SPT s'han realitzat els següents "
            "assaigs de laboratori:",
            style="Normal"
        )
        lab_tests = [
            "Anàlisi granulomètrica per tamisat (UNE 103101).",
            "Límits d'Atterberg (UNE 103103/104).",
            "Contingut en sulfats solubles (UNE 83963).",
        ]
        for test in lab_tests:
            doc.add_paragraph(test, style="List Bullet")

        doc.add_page_break()

    def _add_section_3_descripcio(self, doc: Document, scenario: dict):
        """Add Section 3: Descripció Geològica i Geotècnica."""
        doc.add_paragraph("3. DESCRIPCIÓ GEOLÒGICA I GEOTÈCNICA", style="Heading 1")

        # 3.1 Marc geològic
        doc.add_paragraph("3.1. MARC GEOLÒGIC", style="Heading 2")
        doc.add_paragraph(
            "En primer lloc, s'ha procedit a la consulta de les diferents cartografies "
            "geològiques existents sobre la zona:",
            style="Normal"
        )

        ubicacio = scenario.get("ubicacio", "la zona")
        comarca = scenario.get("comarca", "la comarca")

        # Adapt geological description based on location
        if "BALAGUER" in ubicacio.upper():
            geologia = (
                "Els estudis s'han realitzat sobre materials d'edat Oligocè-Miocè que formen "
                "part de la Depressió de l'Ebre, en el seu sector oriental corresponent a la "
                "Conca del Segre. Geològicament, la zona de Balaguer es caracteritza per la "
                "presència de materials terciaris de caràcter continental, principalment gresos, "
                "lutites i conglomerats de tons rogencs i ocres."
            )
        elif "TÀRREGA" in ubicacio.upper() or "TARREGA" in ubicacio.upper():
            geologia = (
                "Els estudis s'han realitzat sobre materials d'edat Oligocè que formen part "
                "de la Depressió Central Catalana. La zona de Tàrrega es caracteritza per la "
                "presència de materials terciaris de caràcter continental amb alternança de "
                "gresos, margues i calcàries lacustres."
            )
        else:
            geologia = (
                "Els estudis s'han realitzat sobre materials terciaris de la Depressió de l'Ebre. "
                "La zona es caracteritza per la presència de dipòsits al·luvials quaternaris "
                "disposats sobre un substrat oligocè-miocè format per gresos, lutites i conglomerats."
            )

        doc.add_paragraph(geologia, style="Normal")
        self._add_figure(doc, "figura_4", "Figura 4. Mapa geològic de la zona en estudi (Font: ICGC, modificat).")

        # 3.2 Caracterització materials
        doc.add_paragraph("3.2. CARACTERITZACIÓ DELS MATERIALS", style="Heading 2")
        doc.add_paragraph(
            "A partir dels assaigs in situ realitzats, s'ha establert un nivell de materials "
            "des del punt de vista geològic-geotècnic:",
            style="Normal"
        )

        self._add_heading3(doc, "3.2.1. Nivell 1")
        doc.add_paragraph("Descripció litològica", style="Normal")
        doc.add_paragraph(
            "El nivell 1 està format per graves i sorres amb matriu llimosa, de coloracions "
            "marró clar a ocre. Superficialment es detecta un tram de sòls vegetals entre 30-50 cm. "
            "Aquests materials han estat caracteritzats a partir de la interpretació de les dades "
            "dels assaigs de penetració dinàmica i la correlació amb l'estudi de la geologia regional.",
            style="Normal"
        )
        self._add_figure(doc, "foto_3", "Fotografia 3. Detall dels materials del primer nivell.")

        doc.add_paragraph("Localització", style="Normal")
        doc.add_paragraph(
            "A partir dels assaigs realitzats s'obté una potència màxima estudiada de 4.80 metres, "
            "tot i que a partir de l'estudi de la geologia regional de la zona se li podria atribuir "
            "potències superiors.",
            style="Normal"
        )

        doc.add_paragraph("Resistència", style="Normal")
        doc.add_paragraph(
            "Des del punt de vista geomecànic es tracta d'uns materials de caràcter generalment "
            "granulars, amb una densitat i una capacitat portant mitja-alta. Dels assaigs de "
            "penetració dinàmica DPSH s'obté un valor de N₂₀ mig de 45-55.",
            style="Normal"
        )

        # 3.3 Hidrologia
        doc.add_paragraph("3.3. HIDROLOGIA I HIDROGEOLOGIA", style="Heading 2")

        self._add_heading3(doc, "3.3.1. Hidrogeologia superficial")
        doc.add_paragraph(
            "Al solar, no s'han detectat marques i/o indicis de processos d'erosió relacionats "
            "amb l'escolament hídric superficial, ni es preveu que apareguin. "
            "Per altra banda, no s'ha localitzat cap curs d'aigua i/o torrent que pugui afectar al solar.",
            style="Normal"
        )

        self._add_heading3(doc, "3.3.2. Hidrogeologia subterrània")
        doc.add_paragraph(
            "En data de la realització dels treballs de camp, i fins la cota estudiada, "
            "no es va detectar presència de nivell freàtic en cap dels punts estudiats.",
            style="Normal"
        )

        self._add_heading3(doc, "3.3.3. Permeabilitat dels materials")
        doc.add_paragraph(
            "A continuació s'exposen els valors del coeficient de permeabilitat (K) associats "
            "als materials detectats al subsòl del solar:",
            style="Normal"
        )
        self._add_table(doc,
            headers=["Nivell", "Material", "K (m/s)"],
            rows=[
                ["1", "Graves i sorres", "10⁻⁴ - 10⁻⁵"],
            ],
            caption="Taula 6. Resum del coeficient de permeabilitat dels materials."
        )

        # 3.4 Agressivitat
        doc.add_paragraph("3.4. AGRESSIVITAT DEL MEDI", style="Heading 2")
        doc.add_paragraph(
            "D'una mostra dels materials del subsòl, on es preveu armar la fonamentació, "
            "s'ha realitzat els pertinents assaigs de laboratori per tal de determinar "
            "la seva agressivitat al formigó (segons CE-21).",
            style="Normal"
        )
        self._add_table(doc,
            headers=["Paràmetre", "Valor", "Límit", "Classificació"],
            rows=[
                ["SO₄²⁻ (mg/kg)", "< 2000", "3000", "No agressiu"],
            ],
            caption="Taula 7. Valors obtinguts dels assaigs d'agressivitat."
        )

        # 3.5 Excavabilitat
        doc.add_paragraph("3.5. EXCAVABILITAT", style="Heading 2")
        doc.add_paragraph(
            "Els materials del primer nivell no presentaran problemes des del punt de vista "
            "de la seva ripabilitat, podent-se realitzar les excavacions amb maquinària convencional. "
            "En profunditat, en arribar als materials més consolidats, el rendiment de la màquina "
            "disminuirà, essent necessària la utilització de maquinària més contundent.",
            style="Normal"
        )

        # 3.6 Sísmica
        doc.add_paragraph("3.6. ACCELERACIÓ SÍSMICA DE REFERÈNCIA", style="Heading 2")
        doc.add_paragraph(
            "A efectes d'aplicació de la Norma de Construcción Sismoresistente NCSE-02, "
            f"l'acceleració sísmica bàsica per a la zona de {ubicacio} és de ab = 0.04g, "
            "corresponent a una zona de sismicitat baixa.",
            style="Normal"
        )
        self._add_table(doc,
            headers=["Paràmetre", "Valor"],
            rows=[
                ["Acceleració sísmica bàsica (ab)", "0.04g"],
                ["Coeficient del sòl (C)", "1.6"],
                ["Coeficient de contribució (K)", "1.0"],
            ],
            caption="Taula 8. Paràmetres sísmics de la zona."
        )

        # 3.7 Radó
        doc.add_paragraph("3.7. EXPOSICIÓ AL GAS RADÓ", style="Heading 2")
        doc.add_paragraph(
            f"Segons el mapa de zones d'exposició al radó del CTE HS-6, el municipi de {ubicacio} "
            "es troba en Zona 1, corresponent a un potencial d'exposició baix.",
            style="Normal"
        )

        doc.add_page_break()

    def _add_section_4_conclusions(self, doc: Document, scenario: dict):
        """Add Section 4: Conclusions."""
        doc.add_paragraph("4. CONCLUSIONS", style="Heading 1")
        doc.add_paragraph(
            "Les recomanacions es donen en funció dels resultats obtinguts de la campanya "
            "de camp realitzada, així com les observacions realitzades pel tècnic de l'empresa "
            "desplaçat a l'obra.",
            style="Normal"
        )

        # 4.1 Geologia
        doc.add_paragraph("4.1. GEOLOGIA", style="Heading 2")
        doc.add_paragraph(
            "Es detecta un nivell de materials des del punt de vista geològic/geotècnic "
            "en el subsòl del solar en estudi.",
            style="Normal"
        )
        doc.add_paragraph(
            "El nivell 1 està format per graves i sorres amb matriu llimosa, de coloracions "
            "marró clar a ocre. Superficialment es detecta un tram de sòls vegetals entre 30-50 cm. "
            "Des del punt de vista geomecànic es tracta d'uns materials de caràcter generalment "
            "granulars, amb una densitat i una capacitat portant mitja-alta.",
            style="Normal"
        )
        self._add_caption(doc, "Figura 5. Detall del tall de correlació que s'adjunta als annexes.")

        self._add_table(doc,
            headers=["Paràmetre", "Símbol", "Unitat", "Valor"],
            rows=[
                ["Classificació USCS", "-", "-", "SM-GP"],
                ["Densitat aparent", "γ", "kN/m³", "20"],
                ["Angle de fricció interna", "φ'", "°", "32-35"],
                ["Cohesió efectiva", "c'", "kPa", "0"],
                ["Mòdul de deformació", "E", "MPa", "25-35"],
            ],
            caption="Taula 9. Característiques geològiques i geotècniques dels materials."
        )

        # 4.2 Hidrogeologia
        doc.add_paragraph("4.2. HIDROGEOLOGIA I AGRESSIVITAT", style="Heading 2")
        doc.add_paragraph(
            "Es tracta d'un solar no antropitzat. No s'han detectat marques i/o indicis "
            "de processos d'erosió relacionats amb l'escolament hídric superficial.",
            style="Normal"
        )
        doc.add_paragraph(
            "En data de la realització dels treballs de camp, i fins la cota estudiada, "
            "no es va detectar presència de nivell freàtic en cap dels punts estudiats.",
            style="Normal"
        )
        doc.add_paragraph(
            "A partir dels resultats dels assaigs de laboratori realitzats, els materials "
            "del subsòl on es preveu armar la fonamentació, es presenten NO AGRESSIUS al formigó.",
            style="Normal"
        )

        # 4.3 Fonamentació
        doc.add_paragraph("4.3. FONAMENTACIÓ", style="Heading 2")
        tipus_obra = scenario.get("tipus_obra", "habitatge unifamiliar")
        plantes = scenario.get("plantes", "PB + 1")

        doc.add_paragraph(
            f"Segons el projecte executiu es preveu la construcció d'una estructura de {plantes}. "
            "Un cop realitzat el sanejament i anivellació, afloraran superficialment els materials "
            "del primer nivell descrit.",
            style="Normal"
        )
        doc.add_paragraph(
            "Donades les propietats geomecàniques dels materials del primer nivell, es realitza "
            "una valoració per a la realització d'una fonamentació superficial mitjançant sabates, "
            "aïllades i/o corregudes, o bé llosa.",
            style="Normal"
        )
        doc.add_paragraph(
            "Per una fonamentació mitjançant sabates, encastada entre 40-60 cm en els materials "
            "del primer nivell sanejat, es podrà adoptar una tensió admissible de:",
            style="Normal"
        )

        # Destacar valor Qa
        para = doc.add_paragraph("Qa = 3.50 kg/cm²", style="Normal")
        para.runs[0].bold = True
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_paragraph("amb un factor de seguretat inclòs de F=3", style="Normal")

        doc.add_paragraph(
            "Els assentaments màxims previstos per la càrrega recomanada anteriorment seran "
            "iguals o inferiors a 2.0 cm, immediats en el temps donat el comportament granular "
            "dels materials.",
            style="Normal"
        )
        doc.add_paragraph(
            "Com a valor de coeficient de balast referit a la placa de 30x30, es podrà adoptar "
            "un valor de K₃₀ = 6.0 kg/cm³.",
            style="Normal"
        )

    def _add_signature(self, doc: Document, scenario: dict):
        """Add signature block."""
        doc.add_paragraph()
        doc.add_paragraph(
            "G3 D T S.L. sol·licita que si es detectessin anomalies respecte les dades que s'exposen, "
            "durant l'execució de la obra, agrairíem que ens avisessin, i igualment restem a la seva "
            "disposició per qualsevol consulta i/o dubte que vulguin realitzar, en el telèfon 973 33 12 12.",
            style="Normal"
        )
        doc.add_paragraph()

        doc.add_paragraph("Informe geològic / geotècnic", style="Normal")

        expedient = scenario.get("expedient", "[EXPEDIENT]")
        doc.add_paragraph(f"Expedient Núm.: {expedient}", style="Normal")

        lloc = scenario.get("lloc_signatura", "Els Omells de Na Gaia")
        data = scenario.get("data_signatura", datetime.now().strftime("%d de gener de 2026"))
        doc.add_paragraph(f"{lloc}, {data}", style="Normal")

    def _add_table(self, doc: Document, headers: list, rows: list, caption: str = ""):
        """Add a styled table."""
        num_cols = len(headers) if headers else len(rows[0]) if rows else 0
        num_rows = (1 if headers else 0) + len(rows)

        if num_cols == 0:
            return

        table = doc.add_table(rows=num_rows, cols=num_cols)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER

        try:
            table.style = "Table Grid"
        except:
            pass

        # Add headers
        row_idx = 0
        if headers:
            for i, text in enumerate(headers):
                cell = table.rows[0].cells[i]
                cell.text = str(text)
                for para in cell.paragraphs:
                    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    for run in para.runs:
                        run.bold = True
                        run.font.color.rgb = RGBColor(255, 255, 255)
                self._shade_cell(cell, "4A7C59")
            row_idx = 1

        # Add data
        for row_data in rows:
            for i, text in enumerate(row_data):
                if i < len(table.rows[row_idx].cells):
                    table.rows[row_idx].cells[i].text = str(text)
            row_idx += 1

        if caption:
            cap = doc.add_paragraph(caption, style="Caption")
            cap.alignment = WD_ALIGN_PARAGRAPH.CENTER

    def _shade_cell(self, cell, color: str):
        """Add background shading to a cell."""
        shading = OxmlElement("w:shd")
        shading.set(qn("w:fill"), color)
        cell._tc.get_or_add_tcPr().append(shading)

    def _add_caption(self, doc: Document, text: str):
        """Add a centered caption."""
        para = doc.add_paragraph(text, style="Caption")
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER

    def _add_heading3(self, doc: Document, text: str):
        """Add a Heading 3 paragraph with forced left alignment."""
        para = doc.add_paragraph(text, style="Heading 3")
        para.alignment = WD_ALIGN_PARAGRAPH.LEFT
        return para

    def _add_image(self, doc: Document, image_key: str, width_cm: float = 14.0):
        """Add an image from the standard images folder.

        Args:
            doc: The document
            image_key: Key from STANDARD_IMAGES (e.g., 'figura_1', 'foto_1')
            width_cm: Width of the image in centimeters
        """
        if image_key not in STANDARD_IMAGES:
            return None

        image_file = IMAGES_DIR / STANDARD_IMAGES[image_key]
        if not image_file.exists():
            return None

        para = doc.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = para.add_run()
        run.add_picture(str(image_file), width=Cm(width_cm))
        return para

    def _add_figure(self, doc: Document, image_key: str, caption: str, width_cm: float = 14.0):
        """Add an image with caption below it.

        Args:
            doc: The document
            image_key: Key from STANDARD_IMAGES
            caption: Caption text (e.g., "Figura 1. Situació...")
            width_cm: Width of the image in centimeters
        """
        # Add image
        img_para = self._add_image(doc, image_key, width_cm)

        # Add caption
        self._add_caption(doc, caption)

        return img_para


def main():
    parser = argparse.ArgumentParser(description="Generate full G3DT report")
    parser.add_argument("--scenario", choices=["balaguer", "tarrega", "mollerussa"], default="balaguer")
    parser.add_argument("--output", "-o", default="full-report.docx")
    args = parser.parse_args()

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
            "data_camp": "10 de gener de 2026",
            "data_signatura": "16 de gener de 2026",
            "lloc_signatura": "Els Omells de Na Gaia",
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
            "data_camp": "8 de gener de 2026",
            "data_signatura": "15 de gener de 2026",
            "lloc_signatura": "Els Omells de Na Gaia",
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
            "data_camp": "9 de gener de 2026",
            "data_signatura": "16 de gener de 2026",
            "lloc_signatura": "Els Omells de Na Gaia",
        },
    }

    generator = G3DTFullReportGenerator()
    generator.create_report(scenarios[args.scenario], args.output)


if __name__ == "__main__":
    main()
