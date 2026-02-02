#!/usr/bin/env python3
"""
Test the G3DT Jinja2 template with sample data.

Usage:
    python test_template.py
    python test_template.py --output test_output.docx
"""

import argparse
from pathlib import Path
from docxtpl import DocxTemplate


# Sample data matching 3001631 (Rubí) - simple single-family home
SAMPLE_DATA = {
    # Cover page / General info
    'client': 'SRA. MARIA GARCIA',
    'expedient': '3001632',
    'data': '15/01/26',
    'data_camp_text': '10 de gener de 2026',
    'location': 'LLEIDA',

    # Building characteristics (Table 0)
    'plantes': 'PB + 1',
    'superficie_parcela': '500',
    'superficie_construida': '150',

    # CTE Classification (Table 1)
    'cte_edificacio': 'C-1',
    'cte_sol': 'T-2',

    # Additional fields for future expansion
    'obra': 'ESTUDI GEOLÒGIC / GEOTÈCNIC\nPER A LA CONSTRUCCIÓ D\'UN HABITATGE\nUNIFAMILIAR AÏLLAT',
    'tipus_edificacio': 'Habitatge unifamiliar aïllat',
    'data_signatura_text': '15 de gener de 2026',
}


def test_template(template_path: str, output_path: str) -> bool:
    """Test template rendering with sample data."""
    print(f"Loading template: {template_path}")

    try:
        doc = DocxTemplate(template_path)
        print(f"✅ Template loaded successfully")

        # Get template variables
        variables = doc.get_undeclared_template_variables()
        print(f"\n📋 Template variables found: {len(variables)}")
        for var in sorted(variables):
            value = SAMPLE_DATA.get(var, '???')
            status = '✅' if var in SAMPLE_DATA else '❌'
            print(f"   {status} {var}: {value}")

        # Check for missing variables
        missing = [v for v in variables if v not in SAMPLE_DATA]
        if missing:
            print(f"\n⚠️  Missing variables in sample data: {missing}")

        # Render template
        print(f"\n🔄 Rendering template...")
        doc.render(SAMPLE_DATA)
        print(f"✅ Template rendered successfully")

        # Save output
        doc.save(output_path)
        print(f"✅ Output saved to: {output_path}")

        # File size check
        output_size = Path(output_path).stat().st_size
        template_size = Path(template_path).stat().st_size
        print(f"\n📊 File sizes:")
        print(f"   Template: {template_size:,} bytes")
        print(f"   Output: {output_size:,} bytes")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description='Test G3DT template')
    parser.add_argument('--template', '-t', default='g3dt-jinja-template.docx',
                        help='Template file path')
    parser.add_argument('--output', '-o', default='test_output.docx',
                        help='Output file path')
    args = parser.parse_args()

    success = test_template(args.template, args.output)
    return 0 if success else 1


if __name__ == '__main__':
    exit(main())
