#!/usr/bin/env python3
"""
G3DT Report Generator - Template-Based Approach

Uses python-docx-template (docxtpl) to fill G3DT's Word template with data.
This approach preserves 100% of the original styling because we're replacing
content within existing styled elements, not reconstructing styles.

Usage:
    python generate_from_template.py --template g3dt-template.docx --data project.json --output report.docx
    python generate_from_template.py --sample  # Use built-in sample data
"""

import argparse
import json
from pathlib import Path
from datetime import datetime

from docxtpl import DocxTemplate, InlineImage
from docx.shared import Mm, Cm


# =============================================================================
# DATA SCHEMA
# =============================================================================

# Sample data matching 3001631 (Rubí) - simple single-family home
# Updated to match g3dt-jinja-template.docx placeholders
SAMPLE_DATA_RUBI = {
    # =========================================================================
    # CORE FIELDS (required by template)
    # =========================================================================
    "client": "SRA. JOANA MARTINEZ",
    "expedient": "3001631",
    "location": "RUBÍ",

    # Dates - text format for Catalan
    "data_camp_text": "14 de novembre de 2025",
    "data_signatura_text": "17 de desembre de 2025",

    # =========================================================================
    # SECTION 1: PRESENTACIÓ - Building data table
    # =========================================================================
    "plantes": "PB + Porxo",
    "superficie_parcela": "951",
    "superficie_construida": "92",

    # CTE Classification table
    "cte_edificacio": "C-0",
    "cte_sol": "T-1",

    # Additional section 1 fields (for future expansion)
    "tipus_edificacio": "Habitatge unifamiliar aïllat modular",
    "obra": "ESTUDI GEOLÒGIC / GEOTÈCNIC\nPER A LA CONSTRUCCIÓ D'UN HABITATGE\nUNIFAMILIAR MODULAR AÏLLAT",

    # =========================================================================
    # SECTION 2: TREBALLS DE CAMP
    # =========================================================================

    # DPSH test results
    "dpsh_results": [
        {"name": "P-1", "x": "420823", "y": "4594126", "cota": "212.5", "depth": "5.40"},
        {"name": "P-2", "x": "420831", "y": "4594132", "cota": "212.3", "depth": "3.40"},
        {"name": "P-3", "x": "420838", "y": "4594125", "cota": "212.4", "depth": "3.80"},
    ],
    "num_dpsh": "3",

    # Lab tests (optional)
    "lab_tests": [],
    "has_lab_tests": False,

    # =========================================================================
    # SECTION 3: DESCRIPCIÓ GEOLÒGICA I GEOTÈCNICA
    # =========================================================================
    "marc_geologic": (
        "La zona d'estudi es situa geològicament a la Depressió del Vallès, "
        "una fossa tectònica que separa la Serralada Prelitoral de la Serralada Litoral. "
        "Els materials que afloren a la zona corresponen principalment a dipòsits quaternaris "
        "de naturalesa al·luvial i col·luvial, disposats sobre un substrat miocè."
    ),

    # Geotechnical unit
    "nivell1_nom": "Graves i sorres amb matriu llimosa",
    "nivell1_litologia": (
        "Material granular de coloració marró, format per graves i sorres amb matriu llimosa. "
        "Presenta una compacitat densa a molt densa segons els valors de N₂₀ obtinguts."
    ),
    "nivell1_uscs": "GP-GM",

    # Geotechnical parameters
    "geotech_params": [
        {"param": "Classificació USCS", "symbol": "", "unit": "", "value": "GP-GM"},
        {"param": "Densitat aparent", "symbol": "γ", "unit": "kN/m³", "value": "20"},
        {"param": "Angle de fricció interna", "symbol": "φ'", "unit": "°", "value": "32-35"},
        {"param": "Cohesió efectiva", "symbol": "c'", "unit": "kPa", "value": "0"},
    ],

    # Phreatic level
    "nf_detectat": False,
    "nf_profunditat": "",
    "nf_conclusio": (
        "Durant la realització dels treballs de camp no s'ha detectat la presència "
        "de nivell freàtic dins de les cotes assolides pels assaigs de penetració."
    ),

    # Aggressivity
    "agressivitat_conclusio": (
        "No s'han realitzat assaigs per determinar l'agressivitat química del terreny. "
        "Es recomana considerar una classe d'exposició IIa segons l'EHE-08 per defecte."
    ),

    # Seismicity
    "sismica_ab": "0.04g",
    "sismica_zona": "baixa",

    # Radon
    "rado_zona": "Zona 1",
    "rado_desc": "potencial baix",

    # =========================================================================
    # SECTION 4: CONCLUSIONS
    # =========================================================================
    "tipus_fonament": "sabates aïllades o corregudes",
    "profunditat_encast": "-0.80 m",
    "qa": "3.50",
    "qa_kpa": "350",
    "assentaments": "< 25 mm",
    "k30": "6.0",

    # =========================================================================
    # SIGNATURE
    # =========================================================================
    "lloc_signatura": "Els Omells de Na Gaia",
    "data_signatura": "novembre del 2025",
    "signant_nom": "[Nom del/la geòleg/a]",
    "signant_titol": "Geòleg/a col. [XXXX]",
    "signant_rol": "G3 DT S.L.",

    # =========================================================================
    # CONDITIONAL SECTIONS (for complex projects)
    # =========================================================================
    "has_expansivity": False,
    "has_slope_stability": False,
    "has_earth_pressure": False,
    "has_spt": False,
    "has_sondeig": False,
}


# =============================================================================
# GENERATOR CLASS
# =============================================================================

class G3DTTemplateGenerator:
    """Generate G3DT reports using template-based approach."""

    def __init__(self, template_path: str):
        """Initialize with path to G3DT Word template."""
        self.template_path = Path(template_path)
        if not self.template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")

    def generate(self, data: dict, output_path: str) -> Path:
        """Generate report from template with given data."""
        # Load template
        doc = DocxTemplate(self.template_path)

        # Preprocess data (add computed fields)
        context = self._prepare_context(data)

        # Render template
        doc.render(context)

        # Save output
        output = Path(output_path)
        doc.save(output)
        print(f"Report generated: {output}")
        return output

    def _prepare_context(self, data: dict) -> dict:
        """Prepare template context with computed fields."""
        context = data.copy()

        # Add header title (expedient + location)
        context['header_title'] = (
            f"{data.get('expedient', '')}/Estudi geològic – geotècnic_{data.get('location', '')}"
        )

        # Format obra for multiline
        obra = data.get('obra', '')
        context['obra_lines'] = obra.split('\n') if obra else []

        # Count tests
        context['num_dpsh'] = len(data.get('dpsh_results', []))
        context['num_lab_tests'] = len(data.get('lab_tests', []))

        # Boolean flags for conditional sections
        context['has_dpsh'] = len(data.get('dpsh_results', [])) > 0
        context['has_lab_tests'] = len(data.get('lab_tests', [])) > 0

        # Generation timestamp
        context['generated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M")

        return context


# =============================================================================
# CLI
# =============================================================================

def load_data(path: str) -> dict:
    """Load data from JSON file."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(
        description='Generate G3DT geotechnical report from template',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Generate with sample data
    python generate_from_template.py --template g3dt-template.docx --sample

    # Generate from JSON data file
    python generate_from_template.py --template g3dt-template.docx --data project.json

    # Specify output file
    python generate_from_template.py --template g3dt-template.docx --sample --output report.docx
"""
    )
    parser.add_argument(
        '--template', '-t',
        default='g3dt-jinja-template.docx',
        help='Path to G3DT Word template (default: g3dt-jinja-template.docx)'
    )
    parser.add_argument(
        '--data', '-d',
        help='Path to JSON data file'
    )
    parser.add_argument(
        '--sample', '-s',
        action='store_true',
        help='Use built-in sample data (3001631 Rubí)'
    )
    parser.add_argument(
        '--output', '-o',
        default='generated_report.docx',
        help='Output file path (default: generated_report.docx)'
    )
    parser.add_argument(
        '--export-schema',
        action='store_true',
        help='Export data schema to JSON and exit'
    )

    args = parser.parse_args()

    # Export schema if requested
    if args.export_schema:
        schema_path = Path(__file__).parent / 'data_schema.json'
        with open(schema_path, 'w', encoding='utf-8') as f:
            json.dump(SAMPLE_DATA_RUBI, f, indent=2, ensure_ascii=False)
        print(f"Schema exported to: {schema_path}")
        return

    # Template has default value, check if it exists
    template_path = Path(args.template)
    if not template_path.exists():
        print(f"Error: Template not found: {args.template}")
        print("Create the template first using create_template_v2.py")
        return 1

    # Load data
    if args.sample:
        data = SAMPLE_DATA_RUBI
        print("Using sample data (3001631 Rubí)")
    elif args.data:
        data = load_data(args.data)
        print(f"Loaded data from: {args.data}")
    else:
        print("Error: Either --sample or --data is required")
        return 1

    # Generate report
    generator = G3DTTemplateGenerator(args.template)
    generator.generate(data, args.output)


if __name__ == '__main__':
    main()
