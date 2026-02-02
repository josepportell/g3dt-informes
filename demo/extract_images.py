#!/usr/bin/env python3
"""
Extract images from G3DT sample documents.

DOCX files are ZIP archives containing images in word/media/ folder.
This script extracts all images and creates a mapping for later use.
"""

import json
import zipfile
from pathlib import Path
from collections import defaultdict


def extract_images(docx_path: str, output_dir: str = None) -> dict:
    """Extract images from a DOCX file.

    Args:
        docx_path: Path to the DOCX file
        output_dir: Where to save extracted images (default: same folder as docx)

    Returns:
        Dictionary mapping image names to their extracted paths
    """
    docx_path = Path(docx_path)
    if not docx_path.exists():
        raise FileNotFoundError(f"Document not found: {docx_path}")

    # Output directory
    if output_dir:
        out_dir = Path(output_dir)
    else:
        out_dir = docx_path.parent / "extracted-images" / docx_path.stem

    out_dir.mkdir(parents=True, exist_ok=True)

    extracted = {}

    with zipfile.ZipFile(docx_path, 'r') as zf:
        # List all files in the archive
        all_files = zf.namelist()

        # Find images in word/media/
        media_files = [f for f in all_files if f.startswith('word/media/')]

        print(f"\n{'='*60}")
        print(f"Extracting images from: {docx_path.name}")
        print(f"Found {len(media_files)} media files")
        print(f"{'='*60}")

        for media_path in media_files:
            # Extract image name
            image_name = Path(media_path).name
            output_path = out_dir / image_name

            # Extract the file
            with zf.open(media_path) as src:
                data = src.read()
                output_path.write_bytes(data)

            extracted[image_name] = str(output_path)
            print(f"  Extracted: {image_name} ({len(data):,} bytes)")

    # Save mapping
    mapping_file = out_dir / "image_mapping.json"
    with open(mapping_file, 'w', encoding='utf-8') as f:
        json.dump(extracted, f, indent=2, ensure_ascii=False)

    print(f"\nMapping saved to: {mapping_file}")
    print(f"Total images extracted: {len(extracted)}")

    return extracted


def analyze_image_usage(docx_path: str) -> dict:
    """Analyze how images are referenced in the document.

    This helps understand which images correspond to which figures.
    """
    import re
    from docx import Document

    doc = Document(docx_path)

    # Find all image references in document XML
    image_refs = defaultdict(list)

    # Check paragraphs for captions near images
    captions = []
    for i, para in enumerate(doc.paragraphs):
        text = para.text.strip()
        if text.startswith(('Figura', 'Fotografia', 'Imatge', 'Mapa')):
            captions.append((i, text))
            # Check XML for nearby image
            xml = para._element.xml
            refs = re.findall(r'r:embed="(rId\d+)"', xml)
            if refs:
                image_refs[text].extend(refs)

    # Check document relationships
    print(f"\n{'='*60}")
    print("IMAGE USAGE ANALYSIS")
    print(f"{'='*60}")

    print(f"\nFound {len(captions)} figure/photo captions:")
    for i, caption in captions:
        print(f"  [{i}] {caption[:60]}...")

    return {"captions": captions, "refs": dict(image_refs)}


def extract_all_samples():
    """Extract images from all sample documents."""
    samples_dir = Path(__file__).parent.parent / "samples"
    output_base = Path(__file__).parent / "extracted-images"

    if not samples_dir.exists():
        print(f"Samples directory not found: {samples_dir}")
        return

    all_extracted = {}

    for docx in samples_dir.glob("*.docx"):
        try:
            out_dir = output_base / docx.stem
            extracted = extract_images(str(docx), str(out_dir))
            all_extracted[docx.name] = extracted
        except Exception as e:
            print(f"Error processing {docx.name}: {e}")

    # Save combined mapping
    combined_mapping = output_base / "all_images_mapping.json"
    with open(combined_mapping, 'w', encoding='utf-8') as f:
        json.dump(all_extracted, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"EXTRACTION COMPLETE")
    print(f"Total documents processed: {len(all_extracted)}")
    print(f"Combined mapping: {combined_mapping}")
    print(f"{'='*60}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # Extract from specific file
        docx_file = sys.argv[1]
        extract_images(docx_file)
    else:
        # Extract from all samples
        extract_all_samples()
