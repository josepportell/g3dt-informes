#!/usr/bin/env python3
"""
Fix two issues:
1. Remove duplicate fig_main_plan_image paragraph from template (para 129)
2. Change IMAGE_WIDTH_SPT_CULLERA from 100 to 150 in image_manager.py
"""

from pathlib import Path
from docx import Document

def fix_duplicate_paragraph():
    """Remove duplicate {{ fig_main_plan_image }} paragraph from template."""
    template_path = Path(__file__).parent.parent / 'templates' / 'g3dt-jinja-template.docx'
    print(f"Opening template: {template_path}")

    doc = Document(template_path)
    body = doc.element.body

    # Find and remove the FIRST occurrence of {{ fig_main_plan_image }}
    removed = False
    para_count = 0
    for i, para in enumerate(doc.paragraphs):
        text = para.text.strip()
        if text == '{{ fig_main_plan_image }}' and not removed:
            # Remove first occurrence only
            body.remove(para._element)
            removed = True
            print(f'✓ Removed duplicate para {i} (style: {para.style.name}): "{text}"')
            break
        if '{{ fig_main_plan_image }}' in text:
            para_count += 1

    if not removed:
        print(f"⚠ No duplicate found. Total paragraphs with fig_main_plan_image: {para_count}")
        return False

    # Save the fixed template
    doc.save(template_path)
    print(f"✓ Template saved: {template_path}")

    # Verify only one occurrence remains
    doc_verify = Document(template_path)
    count = sum(1 for p in doc_verify.paragraphs if '{{ fig_main_plan_image }}' in p.text)
    print(f"✓ Verification: {count} occurrence(s) of {{ fig_main_plan_image }} remain")
    return True

def fix_image_width():
    """Change IMAGE_WIDTH_SPT_CULLERA from 100 to 150."""
    image_manager_path = Path(__file__).parent / 'image_manager.py'
    print(f"\nOpening image_manager.py: {image_manager_path}")

    content = image_manager_path.read_text(encoding="utf-8")

    # Find and replace the constant
    old_line = 'IMAGE_WIDTH_SPT_CULLERA = 100  # SPT spoon diagram (smaller, technical)'
    new_line = 'IMAGE_WIDTH_SPT_CULLERA = 150  # SPT spoon diagram (full-width, same as other figures)'

    if old_line in content:
        content = content.replace(old_line, new_line)
        image_manager_path.write_text(content, encoding="utf-8")
        print(f"✓ Changed IMAGE_WIDTH_SPT_CULLERA: 100 → 150")
        return True
    else:
        print(f"⚠ Old line not found. Searching for any IMAGE_WIDTH_SPT_CULLERA...")
        import re
        match = re.search(r'IMAGE_WIDTH_SPT_CULLERA\s*=\s*(\d+)', content)
        if match:
            current_value = match.group(1)
            print(f"  Current value: {current_value}")
            if current_value == '150':
                print(f"  ✓ Already set to 150, no change needed")
                return True
            else:
                print(f"  ⚠ Unexpected value, manual check needed")
                return False
        else:
            print(f"  ⚠ Constant not found, manual check needed")
            return False

if __name__ == '__main__':
    print("=" * 60)
    print("FIX 1: Remove duplicate {{ fig_main_plan_image }} paragraph")
    print("=" * 60)
    success1 = fix_duplicate_paragraph()

    print("\n" + "=" * 60)
    print("FIX 2: Change IMAGE_WIDTH_SPT_CULLERA from 100 to 150")
    print("=" * 60)
    success2 = fix_image_width()

    print("\n" + "=" * 60)
    if success1 and success2:
        print("✓✓ BOTH FIXES COMPLETE")
    elif success1 or success2:
        print("⚠ PARTIAL SUCCESS - review output above")
    else:
        print("✗ BOTH FIXES FAILED - manual intervention needed")
    print("=" * 60)
