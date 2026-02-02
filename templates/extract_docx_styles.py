#!/usr/bin/env python3
"""
Extract and document all styles from a G3DT Word document.
Outputs a comprehensive style guide for template creation.

Usage:
    python extract_docx_styles.py <document.docx>
    python extract_docx_styles.py <document.docx> --detailed
"""

import argparse
import json
from pathlib import Path
from collections import defaultdict
from docx import Document
from docx.shared import Pt, Cm, Inches, RGBColor
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH


def rgb_to_hex(rgb):
    """Convert RGBColor to hex string."""
    if rgb is None:
        return None
    # RGBColor is stored as an integer, convert to hex string
    try:
        # If it's already a hex-like integer
        if isinstance(rgb, int):
            return f"#{rgb:06X}"
        # If it's an RGBColor object, convert to string and parse
        rgb_str = str(rgb)
        if len(rgb_str) == 6:
            return f"#{rgb_str.upper()}"
        return f"#{rgb_str}"
    except Exception:
        return str(rgb)


def extract_styles(doc_path: str, detailed: bool = False) -> dict:
    """Extract all relevant styles from a docx file."""
    doc = Document(doc_path)

    result = {
        'file': str(doc_path),
        'page_setup': {},
        'document_stats': {},
        'paragraph_styles': {},
        'fonts_used': defaultdict(int),
        'colors_used': defaultdict(int),
        'font_sizes': defaultdict(int),
        'tables': [],
        'sections': [],
        'headers_footers': {},
        'images': [],
    }

    # =========================================================================
    # DOCUMENT STATISTICS
    # =========================================================================
    result['document_stats'] = {
        'paragraph_count': len(doc.paragraphs),
        'table_count': len(doc.tables),
        'section_count': len(doc.sections),
    }

    # =========================================================================
    # PAGE SETUP (from first section)
    # =========================================================================
    if doc.sections:
        section = doc.sections[0]
        result['page_setup'] = {
            'page_width_cm': round(section.page_width.cm, 2),
            'page_height_cm': round(section.page_height.cm, 2),
            'top_margin_cm': round(section.top_margin.cm, 2),
            'bottom_margin_cm': round(section.bottom_margin.cm, 2),
            'left_margin_cm': round(section.left_margin.cm, 2),
            'right_margin_cm': round(section.right_margin.cm, 2),
            'header_distance_cm': round(section.header_distance.cm, 2),
            'footer_distance_cm': round(section.footer_distance.cm, 2),
            'orientation': 'portrait' if section.page_width < section.page_height else 'landscape',
        }

    # =========================================================================
    # PARAGRAPH STYLES
    # =========================================================================
    for i, para in enumerate(doc.paragraphs):
        style_name = para.style.name if para.style else 'None'

        if style_name not in result['paragraph_styles']:
            result['paragraph_styles'][style_name] = {
                'count': 0,
                'fonts': set(),
                'colors': set(),
                'sizes': set(),
                'samples': [],
            }

        result['paragraph_styles'][style_name]['count'] += 1

        # Collect sample text (first 3 occurrences)
        if para.text.strip() and len(result['paragraph_styles'][style_name]['samples']) < 3:
            result['paragraph_styles'][style_name]['samples'].append({
                'para_index': i,
                'text': para.text[:100] + ('...' if len(para.text) > 100 else ''),
            })

        # Analyze runs for fonts, colors, sizes
        for run in para.runs:
            if run.font.name:
                result['paragraph_styles'][style_name]['fonts'].add(run.font.name)
                result['fonts_used'][run.font.name] += 1

            if run.font.size:
                size_pt = round(run.font.size.pt, 1)
                result['paragraph_styles'][style_name]['sizes'].add(size_pt)
                result['font_sizes'][size_pt] += 1

            if run.font.color and run.font.color.rgb:
                color_hex = rgb_to_hex(run.font.color.rgb)
                result['paragraph_styles'][style_name]['colors'].add(color_hex)
                result['colors_used'][color_hex] += 1

    # Convert sets to lists for JSON serialization
    for style in result['paragraph_styles'].values():
        style['fonts'] = sorted(list(style['fonts']))
        style['colors'] = sorted(list(style['colors']))
        style['sizes'] = sorted(list(style['sizes']))

    result['fonts_used'] = dict(sorted(result['fonts_used'].items(), key=lambda x: -x[1]))
    result['colors_used'] = dict(sorted(result['colors_used'].items(), key=lambda x: -x[1]))
    result['font_sizes'] = dict(sorted(result['font_sizes'].items(), key=lambda x: -x[1]))

    # =========================================================================
    # TABLES
    # =========================================================================
    for i, table in enumerate(doc.tables):
        table_info = {
            'index': i,
            'rows': len(table.rows),
            'cols': len(table.columns),
            'first_row_text': [],
            'has_header_row': False,
        }

        # Get first row content (likely headers)
        if table.rows:
            for cell in table.rows[0].cells:
                table_info['first_row_text'].append(cell.text[:50])

        # Check if first row has different formatting (header)
        if table.rows and len(table.rows) > 1:
            first_row = table.rows[0]
            # Check for shading in first row
            for cell in first_row.cells:
                tc = cell._tc
                shading = tc.find(qn('w:shd'))
                if shading is not None:
                    fill = shading.get(qn('w:fill'))
                    if fill:
                        table_info['has_header_row'] = True
                        table_info['header_fill_color'] = f"#{fill}" if not fill.startswith('#') else fill
                        break

        result['tables'].append(table_info)

    # =========================================================================
    # SECTIONS (for multi-section documents)
    # =========================================================================
    for i, section in enumerate(doc.sections):
        section_info = {
            'index': i,
            'start_type': str(section.start_type) if section.start_type else 'continuous',
            'page_width_cm': round(section.page_width.cm, 2),
            'page_height_cm': round(section.page_height.cm, 2),
            'has_different_first_page_header': section.different_first_page_header_footer,
        }
        result['sections'].append(section_info)

    # =========================================================================
    # HEADERS AND FOOTERS
    # =========================================================================
    if doc.sections:
        section = doc.sections[0]

        # Header
        header = section.header
        if header and header.paragraphs:
            header_text = ' | '.join([p.text for p in header.paragraphs if p.text.strip()])
            result['headers_footers']['header'] = {
                'text': header_text[:200] if header_text else '(images/tables only)',
                'paragraph_count': len(header.paragraphs),
            }

        # Footer
        footer = section.footer
        if footer and footer.paragraphs:
            footer_text = ' | '.join([p.text for p in footer.paragraphs if p.text.strip()])
            result['headers_footers']['footer'] = {
                'text': footer_text[:200] if footer_text else '(images/tables only)',
                'paragraph_count': len(footer.paragraphs),
            }

    # =========================================================================
    # IMAGES (via relationships)
    # =========================================================================
    try:
        for rel in doc.part.rels.values():
            if "image" in rel.reltype:
                result['images'].append({
                    'rId': rel.rId,
                    'target': str(rel.target_ref) if hasattr(rel, 'target_ref') else 'embedded',
                })
    except Exception:
        pass

    result['document_stats']['image_count'] = len(result['images'])

    return result


def print_summary(result: dict):
    """Print a human-readable summary."""
    print("\n" + "=" * 60)
    print(f"STYLE ANALYSIS: {Path(result['file']).name}")
    print("=" * 60)

    print(f"\n📄 DOCUMENT STATS:")
    stats = result['document_stats']
    print(f"   Paragraphs: {stats['paragraph_count']}")
    print(f"   Tables: {stats['table_count']}")
    print(f"   Sections: {stats['section_count']}")
    print(f"   Images: {stats.get('image_count', 0)}")

    print(f"\n📐 PAGE SETUP:")
    ps = result['page_setup']
    print(f"   Size: {ps['page_width_cm']} x {ps['page_height_cm']} cm ({ps['orientation']})")
    print(f"   Margins: T={ps['top_margin_cm']} B={ps['bottom_margin_cm']} L={ps['left_margin_cm']} R={ps['right_margin_cm']} cm")
    print(f"   Header/Footer: {ps['header_distance_cm']} / {ps['footer_distance_cm']} cm")

    print(f"\n🔤 FONTS USED (top 5):")
    for font, count in list(result['fonts_used'].items())[:5]:
        print(f"   {font}: {count} occurrences")

    print(f"\n🎨 COLORS USED:")
    for color, count in list(result['colors_used'].items())[:10]:
        print(f"   {color}: {count} occurrences")

    print(f"\n📏 FONT SIZES (top 5):")
    for size, count in list(result['font_sizes'].items())[:5]:
        print(f"   {size}pt: {count} occurrences")

    print(f"\n📝 PARAGRAPH STYLES (by frequency):")
    sorted_styles = sorted(
        result['paragraph_styles'].items(),
        key=lambda x: -x[1]['count']
    )
    for style_name, info in sorted_styles[:10]:
        fonts_str = ', '.join(info['fonts'][:2]) if info['fonts'] else '-'
        colors_str = ', '.join(info['colors'][:2]) if info['colors'] else '-'
        print(f"   {style_name}: {info['count']}x | Fonts: {fonts_str} | Colors: {colors_str}")

    print(f"\n📊 TABLES ({len(result['tables'])}):")
    for t in result['tables'][:5]:
        header_info = f" [header: {t.get('header_fill_color', 'none')}]" if t.get('has_header_row') else ""
        print(f"   Table {t['index']}: {t['rows']}x{t['cols']}{header_info}")
        if t['first_row_text']:
            print(f"      Headers: {' | '.join(t['first_row_text'][:3])}")

    if result['headers_footers']:
        print(f"\n📌 HEADERS/FOOTERS:")
        if 'header' in result['headers_footers']:
            h = result['headers_footers']['header']
            print(f"   Header: {h['text'][:80]}...")
        if 'footer' in result['headers_footers']:
            f = result['headers_footers']['footer']
            print(f"   Footer: {f['text'][:80]}...")


def main():
    parser = argparse.ArgumentParser(description='Extract styles from Word document')
    parser.add_argument('document', help='Path to .docx file')
    parser.add_argument('--detailed', '-d', action='store_true', help='Include detailed output')
    parser.add_argument('--json', '-j', action='store_true', help='Output JSON only')
    args = parser.parse_args()

    doc_path = Path(args.document)
    if not doc_path.exists():
        print(f"Error: File not found: {doc_path}")
        return 1

    result = extract_styles(str(doc_path), detailed=args.detailed)

    # Save JSON
    output_path = doc_path.with_suffix('.styles.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    else:
        print_summary(result)
        print(f"\n✅ Full analysis saved to: {output_path}")

    return 0


if __name__ == '__main__':
    exit(main())
