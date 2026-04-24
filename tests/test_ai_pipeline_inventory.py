"""Tests for AI pipeline Stage 1 — inventory."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from automation.ai_pipeline.inventory import (
    Inventory,
    build_inventory,
    load_inventory,
    save_inventory,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_project(tmp_path: Path) -> Path:
    """Create a small synthetic project layout on tmp_path."""
    project = tmp_path / "demo-project"
    (project / "ANNEXES").mkdir(parents=True)
    (project / "FOTOGRAFIES" / "DPSH").mkdir(parents=True)
    (project / "validation" / "msg_attachments" / "email-one").mkdir(parents=True)

    # Root files
    (project / "PENETROS.pdf").write_bytes(b"%PDF-1.4\n" + b"a" * 1024)
    (project / "DPSH.xls").write_bytes(b"XLS" + b"b" * 2048)
    # ANNEXES
    (project / "ANNEXES" / "sondeig.pdf").write_bytes(b"%PDF-1.4\n" + b"c" * 1024)
    # FOTOGRAFIES/DPSH
    (project / "FOTOGRAFIES" / "DPSH" / "foto1.jpg").write_bytes(b"\xff\xd8\xff" + b"d" * 512)
    # Pre-materialized msg attachment
    (project / "validation" / "msg_attachments" / "email-one" / "budget.pdf").write_bytes(
        b"%PDF-1.4\n" + b"e" * 1024
    )
    return project


# ---------------------------------------------------------------------------
# Shape + counts
# ---------------------------------------------------------------------------


def test_build_inventory_returns_inventory_model(tmp_path):
    project = _make_project(tmp_path)
    inv = build_inventory(project, extract_attachments=False)

    assert isinstance(inv, Inventory)
    assert inv.project_path == str(project.resolve())
    assert inv.total_files == len(inv.files)
    assert inv.scanned_at.endswith("+00:00")


def test_root_file_count_matches_folder_entry(tmp_path):
    project = _make_project(tmp_path)
    inv = build_inventory(project, extract_attachments=False)

    root_entry = next(f for f in inv.folders if f.path == "")
    assert root_entry.file_count == inv.root_file_count
    # We seeded 2 files at the project root
    assert inv.root_file_count == 2


def test_total_equals_sum_of_folder_counts(tmp_path):
    project = _make_project(tmp_path)
    inv = build_inventory(project, extract_attachments=False)
    assert inv.total_files == sum(f.file_count for f in inv.folders)


def test_folders_are_sorted_by_path(tmp_path):
    project = _make_project(tmp_path)
    inv = build_inventory(project, extract_attachments=False)
    paths = [f.path for f in inv.folders]
    assert paths == sorted(paths)


# ---------------------------------------------------------------------------
# Email attachment tagging
# ---------------------------------------------------------------------------


def test_email_attachment_kind_is_tagged(tmp_path):
    project = _make_project(tmp_path)
    inv = build_inventory(project, extract_attachments=False)

    attachments = [f for f in inv.files if f.kind == "email_attachment"]
    assert len(attachments) == 1
    att = attachments[0]
    assert att.path == "validation/msg_attachments/email-one/budget.pdf"
    assert att.parent_msg == "email-one.msg"


def test_regular_files_have_no_parent_msg(tmp_path):
    project = _make_project(tmp_path)
    inv = build_inventory(project, extract_attachments=False)
    for f in inv.files:
        if f.kind == "regular":
            assert f.parent_msg is None


def test_extracted_attachments_count(tmp_path):
    project = _make_project(tmp_path)
    inv = build_inventory(project, extract_attachments=False)
    assert inv.extracted_attachments == 1


# ---------------------------------------------------------------------------
# Query helpers (programmatic API)
# ---------------------------------------------------------------------------


def test_files_in_folder(tmp_path):
    project = _make_project(tmp_path)
    inv = build_inventory(project, extract_attachments=False)

    root_files = inv.files_in_folder("")
    assert {Path(f.path).name for f in root_files} == {"PENETROS.pdf", "DPSH.xls"}

    annexes = inv.files_in_folder("ANNEXES")
    assert {Path(f.path).name for f in annexes} == {"sondeig.pdf"}

    photos = inv.files_in_folder("FOTOGRAFIES/DPSH")
    assert {Path(f.path).name for f in photos} == {"foto1.jpg"}


def test_find_by_name_is_case_insensitive(tmp_path):
    project = _make_project(tmp_path)
    inv = build_inventory(project, extract_attachments=False)

    matches = inv.find_by_name("PENETROS")
    assert len(matches) == 1
    assert matches[0].path == "PENETROS.pdf"

    # lowercase query still matches uppercase filename
    assert len(inv.find_by_name("penetros")) == 1


def test_files_of_type(tmp_path):
    project = _make_project(tmp_path)
    inv = build_inventory(project, extract_attachments=False)

    pdfs = [f for f in inv.files if f.type.startswith("pdf")]
    assert len(pdfs) >= 2  # PENETROS + sondeig + attachment budget

    excels = inv.files_of_type("excel")
    assert len(excels) == 1


# ---------------------------------------------------------------------------
# Cache save/load round-trip
# ---------------------------------------------------------------------------


def test_save_and_load_inventory_roundtrip(tmp_path):
    project = _make_project(tmp_path)
    inv = build_inventory(project, extract_attachments=False)

    out = save_inventory(inv, project)
    assert out == project / "validation" / "ai_inventory.json"
    assert out.is_file()

    loaded = load_inventory(project)
    assert loaded is not None
    assert loaded.total_files == inv.total_files
    assert loaded.root_file_count == inv.root_file_count
    assert [f.path for f in loaded.files] == [f.path for f in inv.files]


def test_load_inventory_returns_none_when_missing(tmp_path):
    project = _make_project(tmp_path)
    assert load_inventory(project) is None


def test_no_flag_rewalks_no_cache_hit(tmp_path):
    """Without --save, build_inventory should rebuild each call (no implicit caching)."""
    project = _make_project(tmp_path)
    inv1 = build_inventory(project, extract_attachments=False)

    # Add a new file
    (project / "NEWFILE.txt").write_text("x" * 100)

    inv2 = build_inventory(project, extract_attachments=False)
    assert inv2.total_files == inv1.total_files + 1


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_build_inventory_rejects_nonexistent_path(tmp_path):
    with pytest.raises(ValueError):
        build_inventory(tmp_path / "does-not-exist")
