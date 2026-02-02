#!/usr/bin/env python3
"""
PDF Style Analyzer for G3DT Reports
Extracts detailed formatting metadata: font, size, color, position per text span.

Uses PyMuPDF (fitz) for granular extraction.
"""

import fitz  # PyMuPDF
import json
import argparse
from pathlib import Path
from collections import defaultdict


def rgb_to_hex(color):
    """Convert fitz color (int) to hex string."""
    if isinstance(color, int):
        # Color is stored as integer
        r = (color >> 16) & 0xFF
        g = (color >> 8) & 0xFF
        b = color & 0xFF
        return f"#{r:02X}{g:02X}{b:02X}"
    return str(color)


def analyze_page(page, page_num):
    """Analyze a single page and extract text styling."""
    # Get text as dictionary with full details
    blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

    page_data = {
        "page": page_num + 1,
        "width": page.rect.width,
        "height": page.rect.height,
        "blocks": []
    }

    for block in blocks.get("blocks", []):
        if block.get("type") == 0:  # Text block
            block_data = {
                "bbox": block.get("bbox"),
                "lines": []
            }

            for line in block.get("lines", []):
                line_data = {
                    "bbox": line.get("bbox"),
                    "spans": []
                }

                for span in line.get("spans", []):
                    span_data = {
                        "text": span.get("text", ""),
                        "font": span.get("font", ""),
                        "size": round(span.get("size", 0), 1),
                        "color": rgb_to_hex(span.get("color", 0)),
                        "flags": span.get("flags", 0),
                        "bold": bool(span.get("flags", 0) & 2**4),  # bit 4 = bold
                        "italic": bool(span.get("flags", 0) & 2**1),  # bit 1 = italic
                        "bbox": span.get("bbox"),
                    }

                    # Only include non-empty spans
                    if span_data["text"].strip():
                        line_data["spans"].append(span_data)

                if line_data["spans"]:
                    block_data["lines"].append(line_data)

            if block_data["lines"]:
                page_data["blocks"].append(block_data)

    return page_data


def summarize_styles(pages_data):
    """Create summary of all unique styles found."""
    styles = defaultdict(lambda: {"count": 0, "examples": []})

    for page in pages_data:
        for block in page.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    # Create style key
                    key = (
                        span["font"],
                        span["size"],
                        span["color"],
                        span["bold"],
                        span["italic"]
                    )

                    styles[key]["count"] += 1
                    if len(styles[key]["examples"]) < 3:
                        text = span["text"][:50] + "..." if len(span["text"]) > 50 else span["text"]
                        styles[key]["examples"].append({
                            "text": text,
                            "page": page["page"]
                        })

    # Convert to list and sort by count
    style_list = []
    for (font, size, color, bold, italic), data in styles.items():
        style_list.append({
            "font": font,
            "size": size,
            "color": color,
            "bold": bold,
            "italic": italic,
            "count": data["count"],
            "examples": data["examples"]
        })

    return sorted(style_list, key=lambda x: -x["count"])


def analyze_pdf(pdf_path, output_format="summary", pages=None):
    """
    Analyze PDF and extract style information.

    Args:
        pdf_path: Path to PDF file
        output_format: "summary", "detailed", or "json"
        pages: List of page numbers to analyze (1-indexed), or None for all
    """
    doc = fitz.open(pdf_path)

    print(f"Analyzing: {pdf_path}")
    print(f"Pages: {doc.page_count}")
    print(f"Metadata: {doc.metadata}")
    print("-" * 60)

    pages_data = []

    page_range = range(doc.page_count)
    if pages:
        page_range = [p - 1 for p in pages if 0 < p <= doc.page_count]

    for page_num in page_range:
        page = doc[page_num]
        page_data = analyze_page(page, page_num)
        pages_data.append(page_data)

    doc.close()

    if output_format == "json":
        return json.dumps(pages_data, indent=2, ensure_ascii=False)

    elif output_format == "detailed":
        output = []
        for page in pages_data:
            output.append(f"\n{'='*60}")
            output.append(f"PAGE {page['page']} ({page['width']:.0f} x {page['height']:.0f})")
            output.append("="*60)

            for block in page["blocks"]:
                for line in block["lines"]:
                    for span in line["spans"]:
                        bold_mark = "B" if span["bold"] else "-"
                        ital_mark = "I" if span["italic"] else "-"
                        output.append(
                            f"[{bold_mark}{ital_mark}] {span['font']:30} "
                            f"{span['size']:5.1f}pt {span['color']} | "
                            f"{span['text'][:60]}"
                        )
        return "\n".join(output)

    else:  # summary
        styles = summarize_styles(pages_data)

        output = ["\nSTYLE SUMMARY", "=" * 60]
        output.append(f"{'Font':<35} {'Size':>6} {'Color':>9} {'B':>2} {'I':>2} {'Count':>6}")
        output.append("-" * 60)

        for style in styles[:30]:  # Top 30 styles
            bold_mark = "Y" if style["bold"] else "-"
            ital_mark = "Y" if style["italic"] else "-"
            output.append(
                f"{style['font'][:35]:<35} {style['size']:>6.1f} "
                f"{style['color']:>9} {bold_mark:>2} {ital_mark:>2} {style['count']:>6}"
            )
            for ex in style["examples"][:1]:
                output.append(f"    Example (p{ex['page']}): {ex['text']}")

        return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(description='Analyze PDF text styles')
    parser.add_argument('pdf', help='Path to PDF file')
    parser.add_argument('--format', '-f', choices=['summary', 'detailed', 'json'],
                        default='summary', help='Output format')
    parser.add_argument('--pages', '-p', type=int, nargs='+',
                        help='Specific pages to analyze (1-indexed)')
    parser.add_argument('--output', '-o', help='Output file (default: stdout)')

    args = parser.parse_args()

    result = analyze_pdf(args.pdf, args.format, args.pages)

    if args.output:
        Path(args.output).write_text(result, encoding='utf-8')
        print(f"Output written to: {args.output}")
    else:
        print(result)


if __name__ == '__main__':
    main()
