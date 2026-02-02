#!/usr/bin/env python3
"""
Extract sections from G3DT sample DOCX for demo purposes.
Outputs markdown files to demo-sections/ folder.
"""

from docx import Document
from pathlib import Path
import json
import re

def extract_text_with_structure(docx_path: str) -> list:
    """Extract paragraphs with their heading level."""
    doc = Document(docx_path)
    paragraphs = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        style_name = para.style.name if para.style else ""

        # Determine heading level
        level = 0
        if "Heading 1" in style_name or "Títol 1" in style_name:
            level = 1
        elif "Heading 2" in style_name or "Títol 2" in style_name:
            level = 2
        elif "Heading 3" in style_name or "Títol 3" in style_name:
            level = 3
        elif "Title" in style_name:
            level = 0  # Title

        paragraphs.append({
            "text": text,
            "level": level,
            "style": style_name
        })

    return paragraphs

def find_section_boundaries(paragraphs: list) -> dict:
    """Find where each major section starts and ends."""
    sections = {}
    current_section = None
    current_content = []

    for i, para in enumerate(paragraphs):
        # Check for main section headers (level 1)
        if para["level"] == 1:
            # Save previous section
            if current_section:
                sections[current_section] = current_content

            # Start new section
            current_section = para["text"]
            current_content = [para]
        elif current_section:
            current_content.append(para)

    # Save last section
    if current_section:
        sections[current_section] = current_content

    return sections

def paragraphs_to_markdown(paragraphs: list) -> str:
    """Convert paragraph list to markdown."""
    lines = []
    for para in paragraphs:
        text = para["text"]
        level = para["level"]

        if level == 1:
            lines.append(f"# {text}\n")
        elif level == 2:
            lines.append(f"## {text}\n")
        elif level == 3:
            lines.append(f"### {text}\n")
        else:
            lines.append(f"{text}\n")

    return "\n".join(lines)

def main():
    # Paths
    sample_path = Path("/home/josep/projects/claudecode-job/clients/g3dt/samples/3001631_informe.docx")
    output_dir = Path("/home/josep/projects/claudecode-job/clients/g3dt/demo-sections")
    output_dir.mkdir(exist_ok=True)

    print(f"Reading: {sample_path}")

    # Extract paragraphs
    paragraphs = extract_text_with_structure(str(sample_path))
    print(f"Found {len(paragraphs)} paragraphs")

    # Find sections
    sections = find_section_boundaries(paragraphs)
    print(f"Found {len(sections)} main sections:")
    for name in sections.keys():
        print(f"  - {name[:50]}...")

    # Map sections to output files
    section_mapping = {
        "1": ("01-antecedents.md", "PRESENTACIÓ"),
        "2": ("02-treballs-camp.md", "TREBALLS DE CAMP"),
        "3": ("03-descripcio.md", "DESCRIPCIÓ"),
        "4": ("04-conclusions.md", "CONCLUSIONS"),
    }

    # Write each section
    for section_name, content in sections.items():
        # Determine output file based on section number
        section_num = section_name.split(".")[0].strip() if "." in section_name else section_name[0]

        if section_num in section_mapping:
            filename, _ = section_mapping[section_num]
        else:
            # Create filename from section name
            slug = re.sub(r'[^a-z0-9]+', '-', section_name.lower())[:30]
            filename = f"section-{slug}.md"

        output_path = output_dir / filename
        markdown = paragraphs_to_markdown(content)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown)

        print(f"Wrote: {output_path.name} ({len(content)} paragraphs)")

    # Write all content to a single file for reference
    all_md = output_dir / "ALL-SECTIONS-RAW.md"
    full_markdown = paragraphs_to_markdown(paragraphs)
    with open(all_md, 'w', encoding='utf-8') as f:
        f.write(full_markdown)
    print(f"Wrote complete document: {all_md.name}")

if __name__ == "__main__":
    main()
