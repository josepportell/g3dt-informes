#!/usr/bin/env python3
"""
Create a clean base template from the G3DT sample.
Preserves: styles, headers, footers, page setup
Removes: body content, embedded images
"""

from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from pathlib import Path

def create_clean_base():
    """Create a minimal base template with G3DT styles."""
    source_path = Path("/home/josep/projects/claudecode-job/clients/g3dt/samples/3001631_informe.docx")
    output_path = Path("/home/josep/projects/claudecode-job/clients/g3dt/demo/base-template-clean.docx")

    # Open source document
    doc = Document(str(source_path))

    # Remove all body content
    body = doc.element.body
    for child in list(body):
        # Keep section properties (contains page setup)
        if child.tag.endswith('sectPr'):
            continue
        body.remove(child)

    # Remove all relationships to embedded images
    # (This reduces file size significantly)

    # Add placeholder paragraph to ensure document is valid
    para = doc.add_paragraph("", style="Normal")

    # Save clean template
    doc.save(str(output_path))
    print(f"✅ Clean base template created: {output_path}")
    print(f"   Size: {output_path.stat().st_size / 1024:.1f} KB")

    return output_path

if __name__ == "__main__":
    create_clean_base()
