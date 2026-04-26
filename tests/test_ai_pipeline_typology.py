"""Tests for AI pipeline Stage 2 — typology."""

from __future__ import annotations

import sys
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from automation.ai_pipeline.typology import (
    DEV_ONLY_TOPLEVEL_DIRS,
    LOGO_PHASH_THRESHOLD,
    FileClass,
    FolderClass,
    ProjectTypology,
    _load_logo_references,
    _reset_logo_reference_cache,
    classify_project,
    load_typology,
    save_typology,
)


# ---------------------------------------------------------------------------
# Project fixtures
# ---------------------------------------------------------------------------


def _noisy_png_bytes(size: int = 256) -> bytes:
    """Random-noise PNG that won't compress below the 5KB threshold."""
    import random
    from PIL import Image

    random.seed(42)
    img = Image.new("RGB", (size, size))
    pixels = [(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
              for _ in range(size * size)]
    img.putdata(pixels)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_min_pdf_bytes(with_text: bool = True, with_image: bool = False) -> bytes:
    """Create a minimal PDF using PyMuPDF. Optionally embed text + a noisy image."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    if with_text:
        page.insert_text((72, 72), "Hello world. " * 20)
    if with_image:
        page.insert_image(fitz.Rect(100, 100, 356, 356), stream=_noisy_png_bytes(256))
    data = doc.tobytes()
    doc.close()
    return data


def _make_scanned_pdf_bytes() -> bytes:
    """PDF with no text — only a large noisy image."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_image(fitz.Rect(50, 50, 500, 500), stream=_noisy_png_bytes(400))
    data = doc.tobytes()
    doc.close()
    return data


def _make_xlsx_bytes(with_image: bool = False) -> bytes:
    """Create a minimal xlsx, optionally with an embedded image."""
    import openpyxl
    from openpyxl.drawing.image import Image as XLImage
    from PIL import Image as PILImage

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Data"
    ws["A1"] = "header"
    ws["A2"] = 123
    wb.create_sheet("Summary")

    if with_image:
        img_buf = BytesIO(_noisy_png_bytes(200))
        img_buf.seek(0)
        xl_img = XLImage(img_buf)
        xl_img.width = 200
        xl_img.height = 200
        ws.add_image(xl_img, "C3")

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _make_docx_with_media(with_media: bool) -> bytes:
    """Minimal DOCX zip with optional embedded media."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", "<document><p>hi</p></document>")
        if with_media:
            zf.writestr("word/media/image1.png", _noisy_png_bytes(200))
    return buf.getvalue()


def _make_project(tmp_path: Path) -> Path:
    project = tmp_path / "demo"
    (project / "ANNEXES").mkdir(parents=True)
    (project / "FOTOGRAFIES").mkdir()
    (project / "PDF").mkdir()               # dev-only dir
    (project / "PDF V0").mkdir()            # dev-only dir
    (project / "ACCEPTACIO").mkdir()        # NOT dev-only
    (project / "validation" / "msg_attachments" / "email-1").mkdir(parents=True)

    # Useful files
    (project / "PENETROS.pdf").write_bytes(_make_min_pdf_bytes(with_text=True, with_image=False))
    (project / "SONDEIG_scanned.pdf").write_bytes(_make_scanned_pdf_bytes())
    (project / "PLAN_with_image.pdf").write_bytes(_make_min_pdf_bytes(with_text=True, with_image=True))
    (project / "DPSH.xlsx").write_bytes(_make_xlsx_bytes(with_image=False))
    (project / "BUDGET.xlsx").write_bytes(_make_xlsx_bytes(with_image=True))
    # Larger text body (>150 bytes) so it doesn't trip Rule B's text_stub guard
    (project / "notes.txt").write_text("some notes — " + ("padding " * 30))
    (project / "ANNEXES" / "sondeig.pdf").write_bytes(_make_min_pdf_bytes(with_text=True))
    (project / "FOTOGRAFIES" / "foto1.jpg").write_bytes(b"\xff\xd8\xff" + b"d" * 6000)
    (project / "ACCEPTACIO" / "signed.pdf").write_bytes(_make_min_pdf_bytes(with_text=True))
    (project / "letter.docx").write_bytes(_make_docx_with_media(with_media=True))

    # Dev-only files
    (project / "PDF" / "4001670_informe.pdf").write_bytes(_make_min_pdf_bytes(with_text=True))
    (project / "PDF V0" / "4001670_informe_v0.pdf").write_bytes(_make_min_pdf_bytes(with_text=True))

    # Attachment from email
    (project / "validation" / "msg_attachments" / "email-1" / "attached.pdf").write_bytes(
        _make_min_pdf_bytes(with_text=True, with_image=True)
    )

    return project


# ---------------------------------------------------------------------------
# Category assignment
# ---------------------------------------------------------------------------


def _find(typ: ProjectTypology, path: str) -> FileClass:
    for f in typ.files:
        if f.path == path:
            return f
    pytest.fail(f"File not in typology: {path}")


def test_pdf_with_text_no_images_is_pdf_text(tmp_path):
    project = _make_project(tmp_path)
    typ = classify_project(project, extract_images=False)
    f = _find(typ, "PENETROS.pdf")
    assert f.category == "pdf_text"
    assert f.has_text
    assert not f.has_images
    assert f.conversion_strategy == "pdf_to_markdown"
    assert f.useful


def test_pdf_without_text_is_pdf_scanned(tmp_path):
    project = _make_project(tmp_path)
    typ = classify_project(project, extract_images=False)
    f = _find(typ, "SONDEIG_scanned.pdf")
    assert f.category == "pdf_scanned"
    assert f.conversion_strategy == "pdf_pages_to_images"


def test_pdf_with_text_and_images_is_pdf_mixed(tmp_path):
    project = _make_project(tmp_path)
    typ = classify_project(project, extract_images=False)
    f = _find(typ, "PLAN_with_image.pdf")
    assert f.category == "pdf_mixed"
    assert f.conversion_strategy == "pdf_to_markdown_plus_images"
    assert f.image_count >= 1


def test_xlsx_without_images_is_spreadsheet(tmp_path):
    project = _make_project(tmp_path)
    typ = classify_project(project, extract_images=False)
    f = _find(typ, "DPSH.xlsx")
    assert f.category == "spreadsheet"
    assert f.conversion_strategy == "excel_per_sheet_to_csv"
    assert f.sheet_count == 2
    assert "Data" in f.sheet_names


def test_xlsx_with_images_is_spreadsheet_mixed(tmp_path):
    project = _make_project(tmp_path)
    typ = classify_project(project, extract_images=False)
    f = _find(typ, "BUDGET.xlsx")
    assert f.category == "spreadsheet_mixed"
    assert f.conversion_strategy == "excel_per_sheet_to_csv_plus_images"


def test_docx_classification(tmp_path):
    project = _make_project(tmp_path)
    typ = classify_project(project, extract_images=False)
    f = _find(typ, "letter.docx")
    assert f.category == "docx"
    assert f.conversion_strategy == "docx_to_markdown_plus_media"


def test_text_file_is_text_category(tmp_path):
    project = _make_project(tmp_path)
    typ = classify_project(project, extract_images=False)
    f = _find(typ, "notes.txt")
    assert f.category == "text"


def test_image_file_is_image_category(tmp_path):
    project = _make_project(tmp_path)
    typ = classify_project(project, extract_images=False)
    f = _find(typ, "FOTOGRAFIES/foto1.jpg")
    assert f.category == "image"
    assert f.useful


# ---------------------------------------------------------------------------
# Dev-only detection
# ---------------------------------------------------------------------------


def test_pdf_folder_is_dev_only(tmp_path):
    project = _make_project(tmp_path)
    typ = classify_project(project, extract_images=False)
    f = _find(typ, "PDF/4001670_informe.pdf")
    assert f.category == "reference_output"
    assert not f.useful
    assert "PDF/" in f.reason
    assert f.conversion_strategy == "skip"


def test_pdf_v0_is_dev_only(tmp_path):
    project = _make_project(tmp_path)
    typ = classify_project(project, extract_images=False)
    f = _find(typ, "PDF V0/4001670_informe_v0.pdf")
    assert f.category == "reference_output"
    assert not f.useful


def test_acceptacio_is_not_dev_only(tmp_path):
    """ACCEPTACIO is client invoice signing — NOT dev-only."""
    project = _make_project(tmp_path)
    typ = classify_project(project, extract_images=False)
    f = _find(typ, "ACCEPTACIO/signed.pdf")
    assert f.category == "pdf_text"
    assert f.useful


def test_dev_only_dirs_constant():
    assert "PDF" in DEV_ONLY_TOPLEVEL_DIRS
    assert "PDF V0" in DEV_ONLY_TOPLEVEL_DIRS
    assert "PDF-V0" in DEV_ONLY_TOPLEVEL_DIRS
    assert "ACCEPTACIO" not in DEV_ONLY_TOPLEVEL_DIRS


def _make_project_with_eva_outputs(tmp_path: Path) -> Path:
    """Minimal project with Eva's prior-output filenames at root (D17)."""
    project = tmp_path / "demo_eva_outputs"
    project.mkdir()
    # Loose dev-only files Eva leaves at project root across projects
    (project / "4001670_informe.doc").write_bytes(_make_min_pdf_bytes(with_text=True))
    (project / "4001670_informe_v2.doc").write_bytes(_make_min_pdf_bytes(with_text=True))
    (project / "4001670_informe.pdf").write_bytes(_make_min_pdf_bytes(with_text=True))
    (project / "4001670_generated (1).docx").write_bytes(_make_docx_with_media(with_media=False))
    (project / "4001670_generated_utms.docx").write_bytes(_make_docx_with_media(with_media=False))
    (project / "4001670_portada.doc").write_bytes(_make_min_pdf_bytes(with_text=True))
    (project / "4001670_AUDIT_VISUAL.docx").write_bytes(_make_docx_with_media(with_media=False))
    # One legitimate input that must NOT be flagged
    (project / "PENETROS.pdf").write_bytes(_make_min_pdf_bytes(with_text=True))
    return project


def test_loose_informe_doc_is_dev_only(tmp_path):
    """*_informe*.doc at root should be dev-only, not treated as input."""
    project = _make_project_with_eva_outputs(tmp_path)
    typ = classify_project(project, extract_images=False)
    f = _find(typ, "4001670_informe.doc")
    assert f.category == "reference_output"
    assert not f.useful
    assert f.conversion_strategy == "skip"
    assert "prior-output pattern" in f.reason


def test_versioned_informe_doc_is_dev_only(tmp_path):
    """Covers the `*` after `informe` for versioned reports (D17 refinement)."""
    project = _make_project_with_eva_outputs(tmp_path)
    typ = classify_project(project, extract_images=False)
    f = _find(typ, "4001670_informe_v2.doc")
    assert f.category == "reference_output"
    assert not f.useful


def test_loose_informe_pdf_is_dev_only(tmp_path):
    project = _make_project_with_eva_outputs(tmp_path)
    typ = classify_project(project, extract_images=False)
    f = _find(typ, "4001670_informe.pdf")
    assert f.category == "reference_output"
    assert not f.useful


def test_generated_docx_is_dev_only(tmp_path):
    """Covers both `_generated (1).docx` and `_generated_utms.docx` shapes."""
    project = _make_project_with_eva_outputs(tmp_path)
    typ = classify_project(project, extract_images=False)
    for name in ("4001670_generated (1).docx", "4001670_generated_utms.docx"):
        f = _find(typ, name)
        assert f.category == "reference_output", name
        assert not f.useful, name


def test_portada_doc_is_dev_only(tmp_path):
    project = _make_project_with_eva_outputs(tmp_path)
    typ = classify_project(project, extract_images=False)
    f = _find(typ, "4001670_portada.doc")
    assert f.category == "reference_output"
    assert not f.useful


def test_audit_visual_docx_is_dev_only(tmp_path):
    project = _make_project_with_eva_outputs(tmp_path)
    typ = classify_project(project, extract_images=False)
    f = _find(typ, "4001670_AUDIT_VISUAL.docx")
    assert f.category == "reference_output"
    assert not f.useful


def test_legitimate_input_alongside_eva_outputs_is_useful(tmp_path):
    """Make sure filename-pattern matching doesn't over-reach onto real inputs."""
    project = _make_project_with_eva_outputs(tmp_path)
    typ = classify_project(project, extract_images=False)
    f = _find(typ, "PENETROS.pdf")
    assert f.category == "pdf_text"
    assert f.useful


def test_filename_dev_only_is_case_insensitive(tmp_path):
    """Eva's real files use `AUDIT_VISUAL` in caps but we match either casing."""
    project = tmp_path / "demo_case"
    project.mkdir()
    (project / "foo_audit_visual_bar.docx").write_bytes(_make_docx_with_media(with_media=False))
    typ = classify_project(project, extract_images=False)
    f = _find(typ, "foo_audit_visual_bar.docx")
    assert f.category == "reference_output"


# ---------------------------------------------------------------------------
# Image extraction + source chain
# ---------------------------------------------------------------------------


def test_image_extraction_creates_file_entries(tmp_path):
    project = _make_project(tmp_path)
    typ = classify_project(project, extract_images=True)
    # PLAN_with_image.pdf should have produced at least one extracted image
    children = typ.children_of("PLAN_with_image.pdf")
    assert len(children) >= 1
    for c in children:
        assert c.category == "image"
        assert c.parent_path == "PLAN_with_image.pdf"
        assert c.useful


def test_extracted_images_land_in_sidecar_folder(tmp_path):
    project = _make_project(tmp_path)
    classify_project(project, extract_images=True)
    sidecar = project / "validation" / "ai_pipeline" / "extracted"
    assert sidecar.is_dir()
    # At least one subfolder per parent file that had images
    subdirs = [d for d in sidecar.iterdir() if d.is_dir()]
    assert len(subdirs) >= 1


def test_source_chain_for_email_attachment(tmp_path):
    """An email attachment should carry its msg parent in source_chain."""
    project = _make_project(tmp_path)
    typ = classify_project(project, extract_images=False)
    att_path = "validation/msg_attachments/email-1/attached.pdf"
    f = _find(typ, att_path)
    assert f.is_attachment
    assert "email-1.msg" in f.source_chain
    assert any(s.startswith("attachment:") for s in f.source_chain)


def test_source_chain_for_extracted_image_from_attachment(tmp_path):
    """An image extracted from an email attachment keeps the full chain."""
    project = _make_project(tmp_path)
    typ = classify_project(project, extract_images=True)
    att_path = "validation/msg_attachments/email-1/attached.pdf"
    children = typ.children_of(att_path)
    if not children:
        pytest.skip("attachment PDF produced no extracted images in this fixture")
    c = children[0]
    assert "email-1.msg" in c.source_chain
    assert any(s.startswith("attachment:") for s in c.source_chain)
    assert any(s.startswith("img:") for s in c.source_chain)


def test_no_extraction_when_flag_disabled(tmp_path):
    project = _make_project(tmp_path)
    typ = classify_project(project, extract_images=False)
    assert typ.children_of("PLAN_with_image.pdf") == []
    sidecar = project / "validation" / "ai_pipeline" / "extracted"
    assert not sidecar.exists()


def test_dev_only_files_are_not_extracted(tmp_path):
    project = _make_project(tmp_path)
    typ = classify_project(project, extract_images=True)
    assert typ.children_of("PDF/4001670_informe.pdf") == []


# ---------------------------------------------------------------------------
# Counts + Eva summary
# ---------------------------------------------------------------------------


def test_useful_and_skipped_counts_consistent(tmp_path):
    project = _make_project(tmp_path)
    typ = classify_project(project, extract_images=False)
    assert typ.useful_count + typ.skipped_count == len(typ.files)
    assert typ.useful_count == sum(1 for f in typ.files if f.useful)


def test_eva_summary_mentions_dev_only(tmp_path):
    project = _make_project(tmp_path)
    typ = classify_project(project, extract_images=False)
    joined = " ".join(typ.eva_summary).lower()
    assert "outputs anteriors" in joined or "dev-only" in joined or "producció" in joined


def test_counts_by_category_matches_files(tmp_path):
    project = _make_project(tmp_path)
    typ = classify_project(project, extract_images=False)
    expected = {}
    for f in typ.files:
        expected[f.category] = expected.get(f.category, 0) + 1
    assert typ.counts_by_category == expected


# ---------------------------------------------------------------------------
# Folder rollup + traversal
# ---------------------------------------------------------------------------


def test_folders_include_root_and_all_ancestors(tmp_path):
    project = _make_project(tmp_path)
    typ = classify_project(project, extract_images=False)
    paths = {f.path for f in typ.folders}
    assert "" in paths  # root
    assert "ANNEXES" in paths
    assert "FOTOGRAFIES" in paths


def test_subfolders_of_root(tmp_path):
    project = _make_project(tmp_path)
    typ = classify_project(project, extract_images=False)
    subs = typ.subfolders_of("")
    sub_paths = {f.path for f in subs}
    assert "ANNEXES" in sub_paths
    assert "PDF" in sub_paths


def test_dev_only_flag_on_folder(tmp_path):
    project = _make_project(tmp_path)
    typ = classify_project(project, extract_images=False)
    pdf_folder = next(f for f in typ.folders if f.path == "PDF")
    assert pdf_folder.is_dev_only
    annex_folder = next(f for f in typ.folders if f.path == "ANNEXES")
    assert not annex_folder.is_dev_only


def test_folder_tree_is_valid_adjacency_list(tmp_path):
    project = _make_project(tmp_path)
    typ = classify_project(project, extract_images=False)
    tree = typ.folder_tree()
    # Root key should map to a non-empty list
    assert "" in tree
    assert len(tree[""]) > 0


def test_lineage_of_known_file(tmp_path):
    project = _make_project(tmp_path)
    typ = classify_project(project, extract_images=False)
    att_path = "validation/msg_attachments/email-1/attached.pdf"
    chain = typ.lineage_of(att_path)
    assert "email-1.msg" in chain


def test_lineage_of_unknown_path_is_empty(tmp_path):
    project = _make_project(tmp_path)
    typ = classify_project(project, extract_images=False)
    assert typ.lineage_of("does/not/exist.pdf") == []


# ---------------------------------------------------------------------------
# Cache save/load
# ---------------------------------------------------------------------------


def test_save_and_load_roundtrip(tmp_path):
    project = _make_project(tmp_path)
    typ = classify_project(project, extract_images=False)
    out = save_typology(typ, project)
    assert out == project / "validation" / "ai_typology.json"
    loaded = load_typology(project)
    assert loaded is not None
    assert loaded.useful_count == typ.useful_count
    assert [f.path for f in loaded.files] == [f.path for f in typ.files]


def test_load_returns_none_when_absent(tmp_path):
    project = _make_project(tmp_path)
    assert load_typology(project) is None


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


def test_rejects_nonexistent_path(tmp_path):
    with pytest.raises(ValueError):
        classify_project(tmp_path / "does-not-exist")


# ---------------------------------------------------------------------------
# D1#1 tests — pre-Stage 4 logo filter via pHash
# ---------------------------------------------------------------------------


def _logo_refs_dir() -> Path:
    # Same path the production code uses; resolved relative to this test file.
    return Path(__file__).resolve().parent.parent / "schemas" / "ai_pipeline" / "logo_references"


def test_logo_reference_library_exists_and_loads():
    """The committed reference library must load cleanly and be non-empty."""
    _reset_logo_reference_cache()
    try:
        refs = _load_logo_references()
    finally:
        _reset_logo_reference_cache()
    assert refs, "logo reference library should be non-empty at default path"
    # Names come from the filename stems — sanity on at least one known one
    assert any("g3" in name.lower() for name in refs)


def test_reference_library_self_matches():
    """Each reference image must hash to itself at Hamming 0 — guards against
    accidental file corruption or mis-naming in the committed library."""
    import imagehash
    from PIL import Image

    _reset_logo_reference_cache()
    try:
        refs = _load_logo_references()
    finally:
        _reset_logo_reference_cache()

    refs_dir = _logo_refs_dir()
    for p in sorted(refs_dir.iterdir()):
        if p.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
            continue
        with Image.open(p) as img:
            h = imagehash.phash(img.convert("RGB"))
        assert h - refs[p.stem] == 0, f"reference {p.name} doesn't self-match"


def test_logo_filter_flags_identical_reference(tmp_path):
    """Embed one of the committed reference logos into a PDF; the extraction
    should produce a `logo_image` FileClass, not a plain `image`."""
    import fitz

    refs_dir = _logo_refs_dir()
    ref_path = refs_dir / "g3_tight.png"
    assert ref_path.is_file(), "expected committed reference"

    project = tmp_path / "proj"
    project.mkdir()
    # Build a PDF that embeds the G3 logo
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Document with a G3 logo embedded below. " * 5)
    page.insert_image(fitz.Rect(100, 200, 356, 456), filename=str(ref_path))
    (project / "has_logo.pdf").write_bytes(doc.tobytes())
    doc.close()

    _reset_logo_reference_cache()
    try:
        typ = classify_project(project, extract_images=True)
    finally:
        _reset_logo_reference_cache()

    extracted = [f for f in typ.files if f.parent_path == "has_logo.pdf"]
    assert extracted, "expected at least one extracted image"
    # Every extracted image should be flagged as a logo
    for f in extracted:
        assert f.category == "logo_image", f"expected logo_image, got {f.category} for {f.path}"
        assert f.useful is False
        assert f.conversion_strategy == "skip"
        assert "matches G3DT logo reference" in f.reason


def test_logo_filter_ignores_random_noise(tmp_path):
    """A PDF embedding a random-noise PNG must be classified as content, not logo."""
    import fitz

    project = tmp_path / "proj"
    project.mkdir()
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Document with random-noise image. " * 5)
    page.insert_image(fitz.Rect(100, 100, 356, 356), stream=_noisy_png_bytes(256))
    (project / "has_noise.pdf").write_bytes(doc.tobytes())
    doc.close()

    _reset_logo_reference_cache()
    try:
        typ = classify_project(project, extract_images=True)
    finally:
        _reset_logo_reference_cache()

    extracted = [f for f in typ.files if f.parent_path == "has_noise.pdf"]
    assert extracted, "expected at least one extracted image"
    for f in extracted:
        assert f.category == "image"
        assert f.useful is True


def test_logo_filter_degrades_gracefully_without_references(tmp_path, monkeypatch):
    """With an empty reference directory, the filter becomes a no-op:
    extracted images keep `category="image"`, `useful=True`."""
    import automation.ai_pipeline.typology as typology_mod

    empty_dir = tmp_path / "_empty_refs"
    empty_dir.mkdir()
    monkeypatch.setattr(typology_mod, "_LOGO_REFERENCES_DIR", empty_dir)

    # Build a project with the SAME PDF that embeds a real G3 logo
    refs_dir = _logo_refs_dir()
    ref_path = refs_dir / "g3_tight.png"
    project = tmp_path / "proj"
    project.mkdir()
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Doc. " * 5)
    page.insert_image(fitz.Rect(100, 200, 356, 456), filename=str(ref_path))
    (project / "has_logo.pdf").write_bytes(doc.tobytes())
    doc.close()

    _reset_logo_reference_cache()
    try:
        typ = classify_project(project, extract_images=True)
    finally:
        _reset_logo_reference_cache()

    extracted = [f for f in typ.files if f.parent_path == "has_logo.pdf"]
    assert extracted
    # Without references, the logo is NOT recognized — falls back to plain image.
    for f in extracted:
        assert f.category == "image"
        assert f.useful is True


def test_logo_threshold_constant_is_conservative():
    """Guardrail against someone accidentally relaxing the threshold to a value
    that admits real content (validated empty band is Hamming 7–21)."""
    assert 0 < LOGO_PHASH_THRESHOLD <= 10


# ---------------------------------------------------------------------------
# Silent-source rules — coordinates_text / accounting_memo / text_stub
# ---------------------------------------------------------------------------


def test_coordenades_txt_is_coordinates_text(tmp_path):
    """`*COORDENADES*.txt` should be classified as coordinates_text, useful=True,
    with the deterministic-parse conversion strategy."""
    project = tmp_path / "demo_coords"
    (project / "ANNEXES").mkdir(parents=True)
    (project / "ANNEXES" / "COORDENADES.txt").write_text(
        "Coordenades UTM (X);(Y);(Z);\n"
        "P-1\n"
        "308781,86 ; 4613950.63 ; 198.9\n",
        encoding="utf-8",
    )
    typ = classify_project(project, extract_images=False)
    f = _find(typ, "ANNEXES/COORDENADES.txt")
    assert f.category == "coordinates_text"
    assert f.useful is True
    assert f.conversion_strategy == "parse_deterministically"


def test_coordenades_txt_wins_over_text_stub_even_when_small_and_patternless(tmp_path):
    """Rule A (COORDENADES filename) must beat Rule B's small-text-stub guard.
    File is <150 bytes AND has no coord/depth pattern in the preview window."""
    project = tmp_path / "demo_coords_tiny"
    project.mkdir()
    (project / "COORDENADES.txt").write_text(
        "Coordenades UTM (X);(Y);(Z);\n", encoding="utf-8"
    )
    typ = classify_project(project, extract_images=False)
    f = _find(typ, "COORDENADES.txt")
    assert f.category == "coordinates_text"
    assert f.useful is True
    assert f.conversion_strategy == "parse_deterministically"


def test_classify_dte_txt_marks_skip(tmp_path):
    """DTE.txt accounting memo at root → category=accounting_memo, useful=False."""
    project = tmp_path / "demo_dte"
    project.mkdir()
    (project / "DTE.txt").write_text(
        "EN DATA 02/03 DTO AQUEST INFORME PER UN IMPORT DE 1016,40€ - VCT: 30/03/26",
        encoding="utf-8",
    )
    typ = classify_project(project, extract_images=False)
    f = _find(typ, "DTE.txt")
    assert f.category == "accounting_memo"
    assert f.useful is False
    assert f.conversion_strategy == "skip"


def test_classify_small_text_with_no_pattern_skips(tmp_path):
    """Small generic .txt (<150B) with no coord/depth pattern → text_stub, skipped."""
    project = tmp_path / "demo_stub"
    project.mkdir()
    (project / "note.txt").write_text("just a tiny note from Eva", encoding="utf-8")
    typ = classify_project(project, extract_images=False)
    f = _find(typ, "note.txt")
    assert f.category == "text_stub"
    assert f.useful is False
    assert f.conversion_strategy == "skip"


def test_classify_small_coord_text_kept_useful(tmp_path):
    """Small .txt that DOES contain a coord pattern must NOT be classified as text_stub."""
    project = tmp_path / "demo_coord_small"
    project.mkdir()
    (project / "coords.txt").write_text(
        "308781;4613950;198.9\n", encoding="utf-8"
    )
    typ = classify_project(project, extract_images=False)
    f = _find(typ, "coords.txt")
    assert f.category == "text"
    assert f.useful is True


def test_classify_small_depth_text_kept_useful(tmp_path):
    """Small .txt with a depth pattern (e.g. '-3.5 m') must NOT be skipped."""
    project = tmp_path / "demo_depth_small"
    project.mkdir()
    (project / "depths.txt").write_text("Refus a -3.5 m\n", encoding="utf-8")
    typ = classify_project(project, extract_images=False)
    f = _find(typ, "depths.txt")
    assert f.category == "text"
    assert f.useful is True


def test_classify_larger_text_not_subjected_to_pattern_guard(tmp_path):
    """A .txt file >=150B with no patterns is still kept (rule only fires <150B)."""
    project = tmp_path / "demo_larger"
    project.mkdir()
    (project / "long.txt").write_text("padding " * 50, encoding="utf-8")
    typ = classify_project(project, extract_images=False)
    f = _find(typ, "long.txt")
    assert f.category == "text"
    assert f.useful is True


# ---------------------------------------------------------------------------
# Pressupost boilerplate skip (Rule C)
# ---------------------------------------------------------------------------


def _build_pdf_with_n_images(out: Path, n: int) -> None:
    """Build a PDF embedding `n` distinct noisy images (one per page).

    Each image is large enough to pass MIN_IMAGE_BYTES; using random noise
    avoids any logo-filter false-positives.
    """
    import fitz

    doc = fitz.open()
    for i in range(n):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {i}")
        # Vary the seed by injecting a per-image stream
        page.insert_image(
            fitz.Rect(100, 100, 356, 356), stream=_noisy_png_bytes(64 + i)
        )
    out.write_bytes(doc.tobytes())
    doc.close()


def test_pressupost_early_image_skipped(tmp_path):
    """Extracted images with index <6 from a PRESSUPOST_* parent are
    classified `pressupost_boilerplate, useful=False, skip`."""
    project = tmp_path / "demo_press"
    project.mkdir()
    pdf = project / "PRESSUPOST_GEOTEC.pdf"
    _build_pdf_with_n_images(pdf, n=3)
    typ = classify_project(project, extract_images=True)
    children = typ.children_of("PRESSUPOST_GEOTEC.pdf")
    assert children, "expected extracted images from the pressupost PDF"
    for c in children:
        assert c.category == "pressupost_boilerplate"
        assert c.useful is False
        assert c.conversion_strategy == "skip"


def test_pressupost_late_image_kept(tmp_path):
    """Extracted images with index >=6 are NOT skipped by Rule C."""
    project = tmp_path / "demo_press_late"
    project.mkdir()
    pdf = project / "PRESSUPOST_GEOTEC.pdf"
    _build_pdf_with_n_images(pdf, n=8)
    typ = classify_project(project, extract_images=True)
    children = typ.children_of("PRESSUPOST_GEOTEC.pdf")
    indexed = {Path(c.path).name: c for c in children}
    # img_006 and img_007 should NOT be pressupost_boilerplate
    late = [c for name, c in indexed.items() if name.startswith("img_006") or name.startswith("img_007")]
    assert late, "expected at least one late-index extracted image"
    for c in late:
        assert c.category != "pressupost_boilerplate"
        assert c.useful is True


def test_pressupost_skip_only_for_pressupost_parent(tmp_path):
    """Rule C must NOT fire for non-pressupost parents."""
    project = tmp_path / "demo_other_parent"
    project.mkdir()
    pdf = project / "PLAN_COST_X.pdf"
    _build_pdf_with_n_images(pdf, n=2)
    typ = classify_project(project, extract_images=True)
    children = typ.children_of("PLAN_COST_X.pdf")
    assert children
    for c in children:
        assert c.category != "pressupost_boilerplate"
