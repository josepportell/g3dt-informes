#!/usr/bin/env python3
"""
Analyze G3DT document content to identify variable fields for Jinja2 placeholders.
Outputs a mapping of text locations -> suggested placeholders.

Usage:
    python analyze_content.py <document.docx>
    python analyze_content.py <document.docx> --tables
"""

import argparse
import re
from pathlib import Path
from docx import Document


# Known variable patterns in G3DT reports
VARIABLE_PATTERNS = {
    # Expedition/client info
    r'\d{7}': 'expedient',  # 7-digit expedition number
    r'\d{2}/\d{2}/\d{2}': 'data',  # Date format DD/MM/YY
    r'RUBÍ|LINYOLA|CASTELLAR|BELL-LLOC': 'location',

    # Coordinates
    r'UTM X\s*[=:]\s*[\d.]+': 'utm_x',
    r'UTM Y\s*[=:]\s*[\d.]+': 'utm_y',

    # Test results
    r'P-\d+': 'punt_assaig',
    r'\d+\.\d+\s*m': 'profunditat',

    # Geotechnical values
    r'Qa\s*=\s*[\d.,]+\s*kg/cm': 'qa',
    r'N20\s*=\s*[\d]+': 'n20',
}


def extract_paragraphs(doc_path: str) -> list:
    """Extract all paragraphs with their indices and context."""
    doc = Document(doc_path)
    paragraphs = []

    for i, para in enumerate(doc.paragraphs):
        text = para.text.strip()
        if text:
            paragraphs.append({
                'index': i,
                'style': para.style.name if para.style else 'None',
                'text': text,
                'length': len(text),
            })

    return paragraphs


def extract_tables(doc_path: str) -> list:
    """Extract all tables with their content."""
    doc = Document(doc_path)
    tables = []

    for i, table in enumerate(doc.tables):
        table_data = {
            'index': i,
            'rows': len(table.rows),
            'cols': len(table.columns),
            'cells': [],
        }

        for row_idx, row in enumerate(table.rows):
            row_data = []
            for cell_idx, cell in enumerate(row.cells):
                cell_text = cell.text.strip()
                if cell_text:
                    row_data.append({
                        'row': row_idx,
                        'col': cell_idx,
                        'text': cell_text[:100],
                    })
            if row_data:
                table_data['cells'].append(row_data)

        tables.append(table_data)

    return tables


def find_variable_candidates(paragraphs: list) -> list:
    """Find paragraphs that likely contain variable content."""
    candidates = []

    # Keywords that suggest variable content
    variable_keywords = [
        'expedient', 'client', 'obra', 'data', 'localitat',
        'utm', 'coordenades', 'parcela', 'referència',
        'superfície', 'plantes', 'tipus',
        'profunditat', 'cota', 'nivell freàtic',
        'qa', 'n20', 'assentament', 'fonamentació',
    ]

    for para in paragraphs:
        text_lower = para['text'].lower()

        # Check for keywords
        for keyword in variable_keywords:
            if keyword in text_lower:
                candidates.append({
                    **para,
                    'reason': f'Contains keyword: {keyword}',
                })
                break

        # Check for numeric patterns that likely vary
        if re.search(r'\d{7}', para['text']):  # Expedition number
            candidates.append({
                **para,
                'reason': 'Contains 7-digit number (likely expedient)',
            })
        elif re.search(r'\d{2}/\d{2}/\d{2}', para['text']):  # Date
            candidates.append({
                **para,
                'reason': 'Contains date pattern',
            })

    # Remove duplicates
    seen = set()
    unique = []
    for c in candidates:
        if c['index'] not in seen:
            seen.add(c['index'])
            unique.append(c)

    return unique


def identify_sections(paragraphs: list) -> list:
    """Identify main section headings."""
    sections = []

    section_patterns = [
        r'^1\.\s+PRESENTACIÓ',
        r'^2\.\s+TREBALLS',
        r'^3\.\s+DESCRIPCIÓ',
        r'^4\.\s+CONCLUSIONS',
        r'^\d+\.\d+\.?\s+',  # Subsection numbers
    ]

    for para in paragraphs:
        for pattern in section_patterns:
            if re.match(pattern, para['text'], re.IGNORECASE):
                sections.append(para)
                break

    return sections


def print_analysis(paragraphs: list, tables: list, show_tables: bool = False):
    """Print analysis results."""

    print("\n" + "=" * 70)
    print("DOCUMENT CONTENT ANALYSIS")
    print("=" * 70)

    # Sections
    sections = identify_sections(paragraphs)
    print(f"\n📑 SECTIONS FOUND ({len(sections)}):")
    for s in sections[:20]:
        print(f"   [{s['index']:3d}] {s['text'][:70]}")

    # Variable candidates
    candidates = find_variable_candidates(paragraphs)
    print(f"\n🔄 VARIABLE CANDIDATES ({len(candidates)}):")
    for c in candidates[:30]:
        print(f"   [{c['index']:3d}] {c['text'][:60]}")
        print(f"         Reason: {c['reason']}")

    # Tables
    if show_tables:
        print(f"\n📊 TABLES ({len(tables)}):")
        for t in tables:
            print(f"\n   Table {t['index']} ({t['rows']}x{t['cols']}):")
            for row in t['cells'][:5]:
                row_text = ' | '.join([c['text'][:30] for c in row[:4]])
                print(f"      {row_text}")

    # First 50 paragraphs (for context)
    print(f"\n📝 FIRST 50 NON-EMPTY PARAGRAPHS:")
    for para in paragraphs[:50]:
        style_short = para['style'][:15] if para['style'] else 'None'
        print(f"   [{para['index']:3d}] ({style_short:15}) {para['text'][:60]}")


def main():
    parser = argparse.ArgumentParser(description='Analyze document content')
    parser.add_argument('document', help='Path to .docx file')
    parser.add_argument('--tables', '-t', action='store_true', help='Show table contents')
    args = parser.parse_args()

    doc_path = Path(args.document)
    if not doc_path.exists():
        print(f"Error: File not found: {doc_path}")
        return 1

    paragraphs = extract_paragraphs(str(doc_path))
    tables = extract_tables(str(doc_path))

    print_analysis(paragraphs, tables, show_tables=args.tables)

    print(f"\n✅ Total paragraphs with text: {len(paragraphs)}")
    print(f"✅ Total tables: {len(tables)}")

    return 0


if __name__ == '__main__':
    exit(main())
