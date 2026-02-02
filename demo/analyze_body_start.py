#!/usr/bin/env python3
"""
Analyze the beginning of the document body to find cover elements.
"""

from docx import Document
from pathlib import Path
import re

def analyze_body_start(docx_path: str):
    """Analyze first part of body for cover elements."""
    doc = Document(docx_path)

    print(f"\n{'='*60}")
    print("BODY START ANALYSIS")
    print(f"{'='*60}")

    # Check first 5 paragraphs in detail
    print("\n## FIRST 5 PARAGRAPHS (detailed XML):")
    for i, para in enumerate(doc.paragraphs[:5]):
        print(f"\n--- Paragraph {i} ---")
        print(f"  Style: {para.style.name}")
        print(f"  Text: '{para.text}'")
        print(f"  Runs: {len(para.runs)}")

        # Check for embedded content
        xml = para._element.xml
        has_drawing = '<w:drawing' in xml
        has_pict = '<w:pict' in xml
        has_break = '<w:br' in xml

        print(f"  Has drawing: {has_drawing}")
        print(f"  Has picture: {has_pict}")
        print(f"  Has break: {has_break}")

        # Check for specific elements
        if '<a:blip' in xml:
            print("  ✓ Contains image reference (a:blip)")
            refs = re.findall(r'r:embed="(rId\d+)"', xml)
            print(f"    Image refs: {refs}")

    # Look for tables at the start
    print("\n## TABLES IN FIRST 50 ELEMENTS:")
    body = doc.element.body
    table_count = 0
    for i, child in enumerate(body[:50]):
        tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        if tag == 'tbl':
            table_count += 1
            print(f"  Table found at position {i}")

    # Check document part for cover-related images
    print("\n## IMAGE PARTS:")
    for rel_id, rel in doc.part.rels.items():
        if 'image' in rel.reltype.lower():
            print(f"  {rel_id}: {rel.target_ref}")

if __name__ == "__main__":
    sample = "/home/josep/projects/claudecode-job/clients/g3dt/samples/3001631_informe.docx"
    analyze_body_start(sample)
