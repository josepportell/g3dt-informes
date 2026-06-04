"""
Tests for ImageManager defensive image handling (debug/tulipa-render-error).

Covers the three production-bug fixes:
1. discover_photos() filters non-image files out of role-based discovery, so a
   'fotografies' PDF mis-classified into a photo role never reaches InlineImage.
2. _safe_inline_image() returns None for a non-embeddable file and a real
   InlineImage for a valid raster image.
3. _find_photos_dir() recognizes a singular 'FOTOGRAFIA' directory.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from automation.image_manager import ImageManager  # noqa: E402

# A real raster image bundled with the project, used for the valid-image case.
VALID_IMAGE = PROJECT_ROOT / 'templates' / 'images' / 'cullera_spt.jpg'


def _make_manager(project_path: Path, tpl=None) -> ImageManager:
    """Build an ImageManager with minimal stand-ins.

    report_data is unused by the methods under test; tpl is only needed when a
    valid InlineImage is actually constructed.
    """
    return ImageManager(project_path, report_data=object(), tpl=tpl)


# ============================================================
# Fix 1 — non-image excluded from role-based photo discovery
# ============================================================

def test_discover_photos_excludes_pdf_in_photo_role(tmp_path):
    """A .pdf assigned to a photo role must NOT land in result['site']."""
    # Create the offending photo-album PDF that SmartScan mis-classified.
    pdf_path = tmp_path / '3001706_fotografies_CASA 1.pdf'
    pdf_path.write_bytes(b'%PDF-1.4\n%not an image\n')

    file_mapping = {
        'roles': {
            'field_photo': {'path': pdf_path.name},
        }
    }
    (tmp_path / 'file_mapping.json').write_text(
        json.dumps(file_mapping), encoding='utf-8'
    )

    mgr = _make_manager(tmp_path)
    result = mgr.discover_photos()

    assert pdf_path not in result['site']
    assert all(p.suffix.lower() in {'.jpg', '.jpeg', '.png'} for p in result['site'])


def test_discover_photos_keeps_image_in_photo_role(tmp_path):
    """A real .jpg assigned to a photo role IS kept in result['site']."""
    jpg_path = tmp_path / 'vista.jpg'
    jpg_path.write_bytes(b'\xff\xd8\xff\xe0fake-jpeg-bytes')

    file_mapping = {
        'roles': {
            'field_photo': {'path': jpg_path.name},
        }
    }
    (tmp_path / 'file_mapping.json').write_text(
        json.dumps(file_mapping), encoding='utf-8'
    )

    mgr = _make_manager(tmp_path)
    result = mgr.discover_photos()

    assert jpg_path in result['site']


def test_discover_photos_excludes_pdf_in_role_files(tmp_path):
    """Priority 1b (role_files): a .pdf in a photo role's file list is excluded,
    while a real image in the same list is kept."""
    pdf_path = tmp_path / '3001706_fotografies_CASA 2.pdf'
    pdf_path.write_bytes(b'%PDF-1.4\n%not an image\n')
    jpg_path = tmp_path / 'vista_general.jpg'
    jpg_path.write_bytes(b'\xff\xd8\xff\xe0fake-jpeg-bytes')

    file_mapping = {
        'role_files': {
            'field_photo': [
                {'path': pdf_path.name, 'confidence': 90},
                {'path': jpg_path.name, 'confidence': 80},
            ],
        }
    }
    (tmp_path / 'file_mapping.json').write_text(
        json.dumps(file_mapping), encoding='utf-8'
    )

    mgr = _make_manager(tmp_path)
    result = mgr.discover_photos()

    assert pdf_path not in result['site']
    assert jpg_path in result['site']


# ============================================================
# Fix 2 — _safe_inline_image validation
# ============================================================

def test_safe_inline_image_returns_none_for_non_image(tmp_path):
    """A non-raster file (PDF stub) must yield None, not crash."""
    pdf_path = tmp_path / 'album.pdf'
    pdf_path.write_bytes(b'%PDF-1.4\n%not an image\n')

    mgr = _make_manager(tmp_path, tpl=None)
    assert mgr._safe_inline_image(str(pdf_path)) is None


@pytest.mark.skipif(not VALID_IMAGE.exists(), reason="bundled cullera_spt.jpg missing")
def test_safe_inline_image_returns_inline_for_valid_image(tmp_path):
    """A valid raster image must yield a real InlineImage."""
    docxtpl = pytest.importorskip("docxtpl")
    from docx.shared import Mm

    template = PROJECT_ROOT / 'templates' / 'g3dt-jinja-template.docx'
    tpl = docxtpl.DocxTemplate(str(template))

    mgr = _make_manager(tmp_path, tpl=tpl)
    result = mgr._safe_inline_image(str(VALID_IMAGE), width=Mm(120))

    assert isinstance(result, docxtpl.InlineImage)


# ============================================================
# Fix 4 — recognize singular FOTOGRAFIA directory
# ============================================================

def test_find_photos_dir_recognizes_fotografia_singular(tmp_path):
    """A directory named 'FOTOGRAFIA' (singular) must be found."""
    foto_dir = tmp_path / 'FOTOGRAFIA'
    foto_dir.mkdir()

    mgr = _make_manager(tmp_path)
    assert mgr._find_photos_dir() == foto_dir
