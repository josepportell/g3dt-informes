"""Tests for role-aware bypass of `_SKIP_PHOTO_DIRS` in ConceptScout.

Role-tagged site photos (photo_site_overview, photo_test_point,
photo_spt_sample, field_photo) are the primary source for the 6 visual-
observation concepts (site_vegetation_visual, surrounding_context_visual,
etc.). Files with those roles must reach the probe queue even when they
sit under FOTOGRAFIES/ or FOTOS DE CAMP/.

These tests are hermetic — no LLM calls, no reference-material fixtures.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------------------------------------------------------------------------
# _load_allowed_photo_paths: reads roles from file_mapping.json safely.
# ---------------------------------------------------------------------------

def _write_mapping(tmp_path: Path, mapping: dict) -> None:
    (tmp_path / "file_mapping.json").write_text(
        json.dumps(mapping, ensure_ascii=False), encoding="utf-8",
    )


def test_load_allowed_photo_paths_returns_all_four_role_paths(tmp_path):
    """With a fixture that fills the 4 allow-listed roles, the loader
    returns all 4 normalized paths."""
    from automation.concept_scout.vision_probe import _load_allowed_photo_paths

    _write_mapping(tmp_path, {
        "roles": {
            "photo_site_overview": {"path": "ANNEXES/Altres/F3 VG.png"},
            "photo_test_point": {"path": "FOTOGRAFIES/P1.jpg"},
            "photo_spt_sample": {"path": "FOTOGRAFIES/SPT1.jpg"},
            "field_photo": {
                "path": "FOTOGRAFIES/Imagen de WhatsApp 2025-10-01.jpg"
            },
            # Unrelated roles must be ignored.
            "architect_plan": {"path": "25.0616/plan.pdf"},
            "dpsh_field_sheet": {"path": "PENETROS.pdf"},
        },
    })

    allowed = _load_allowed_photo_paths(tmp_path)
    assert allowed == {
        "ANNEXES/Altres/F3 VG.png",
        "FOTOGRAFIES/P1.jpg",
        "FOTOGRAFIES/SPT1.jpg",
        "FOTOGRAFIES/Imagen de WhatsApp 2025-10-01.jpg",
    }


def test_load_allowed_photo_paths_missing_file_returns_empty(tmp_path):
    """No `file_mapping.json` at the project root → empty set, no crash."""
    from automation.concept_scout.vision_probe import _load_allowed_photo_paths

    assert _load_allowed_photo_paths(tmp_path) == set()


def test_load_allowed_photo_paths_malformed_entry_is_skipped(tmp_path):
    """A role entry missing `path`, or with a non-dict/non-string payload,
    is skipped without raising; well-formed siblings still load."""
    from automation.concept_scout.vision_probe import _load_allowed_photo_paths

    _write_mapping(tmp_path, {
        "roles": {
            "photo_site_overview": {"confidence": "high"},  # no `path` key
            "photo_test_point": ["not", "a", "dict"],        # wrong type
            "photo_spt_sample": {"path": ""},                # empty string
            "field_photo": {"path": "FOTOGRAFIES/P1.jpg"},   # well-formed
        },
    })

    assert _load_allowed_photo_paths(tmp_path) == {"FOTOGRAFIES/P1.jpg"}


def test_load_allowed_photo_paths_invalid_json_returns_empty(tmp_path):
    """Unparseable `file_mapping.json` → empty set, no crash."""
    from automation.concept_scout.vision_probe import _load_allowed_photo_paths

    (tmp_path / "file_mapping.json").write_text("{not: json", encoding="utf-8")
    assert _load_allowed_photo_paths(tmp_path) == set()


def test_load_allowed_photo_paths_accepts_bare_string_path(tmp_path):
    """Defensive: tolerate roles stored as bare strings (not dict-with-path)."""
    from automation.concept_scout.vision_probe import _load_allowed_photo_paths

    _write_mapping(tmp_path, {
        "roles": {
            "field_photo": "FOTOGRAFIES/shot.jpg",
        },
    })
    assert _load_allowed_photo_paths(tmp_path) == {"FOTOGRAFIES/shot.jpg"}


# ---------------------------------------------------------------------------
# probe_unreadable_files integration: role-tagged photos bypass skip-dir.
# ---------------------------------------------------------------------------

def test_probe_gate_includes_role_tagged_photo_in_skip_dir(tmp_path, monkeypatch):
    """A FileEntry under FOTOGRAFIES/ whose path matches a role in
    `_PROBE_ALLOWED_PHOTO_ROLES` IS sent to the probe queue, even though
    it lives in a `_SKIP_PHOTO_DIRS` directory."""
    from automation.concept_scout import vision_probe
    from automation.concept_scout.models import FileEntry

    (tmp_path / "FOTOGRAFIES").mkdir()
    fake_img = tmp_path / "FOTOGRAFIES" / "P1.jpg"
    fake_img.write_bytes(b"\xff\xd8\xff")  # JPEG magic bytes

    _write_mapping(tmp_path, {
        "roles": {
            "photo_test_point": {"path": "FOTOGRAFIES/P1.jpg"},
        },
    })

    fe = FileEntry(
        path="FOTOGRAFIES/P1.jpg",
        type="image",
        size_kb=120,
        text_extractable=False,
        concepts_detected=[],
    )

    calls: list[str] = []

    def fake_run(file_path: Path) -> dict:
        calls.append(str(file_path))
        return {
            "document_type": "site_photo",
            "document_description": "test point photo",
            "concepts_found": [],
        }

    monkeypatch.setattr(vision_probe, "_run_probe", fake_run)

    vision_probe.probe_unreadable_files([fe], tmp_path)

    assert any("P1.jpg" in c for c in calls), (
        f"role-tagged photo under FOTOGRAFIES/ should be probed; "
        f"probe calls: {calls}"
    )


def test_probe_gate_skips_untagged_photo_in_skip_dir(tmp_path, monkeypatch):
    """A FileEntry under FOTOGRAFIES/ whose path is NOT in the role
    allow-list is still skipped (existing behaviour preserved)."""
    from automation.concept_scout import vision_probe
    from automation.concept_scout.models import FileEntry

    (tmp_path / "FOTOGRAFIES").mkdir()
    (tmp_path / "FOTOGRAFIES" / "random.jpg").write_bytes(b"\xff\xd8\xff")

    # file_mapping.json has only an unrelated role — random.jpg is not
    # role-tagged, so the photo-dir skip still applies.
    _write_mapping(tmp_path, {
        "roles": {
            "photo_test_point": {"path": "FOTOGRAFIES/P1.jpg"},
        },
    })

    fe = FileEntry(
        path="FOTOGRAFIES/random.jpg",
        type="image",
        size_kb=120,
        text_extractable=False,
        concepts_detected=[],
    )

    calls: list[str] = []
    monkeypatch.setattr(
        vision_probe, "_run_probe",
        lambda fp: calls.append(str(fp)) or None,
    )

    vision_probe.probe_unreadable_files([fe], tmp_path)

    assert calls == [], (
        f"untagged photo under FOTOGRAFIES/ must still be skipped; "
        f"unexpected probes: {calls}"
    )


def test_probe_gate_role_allowlist_does_not_bypass_legacy_output(
    tmp_path, monkeypatch,
):
    """Legacy Eva-output dirs (PDF/, PDF-V0/, etc.) are skipped independently
    of the role allow-list. A role-tagged file inside one of those dirs
    (pathological but possible in malformed fixtures) must NOT be probed."""
    from automation.concept_scout import vision_probe
    from automation.concept_scout.models import FileEntry

    (tmp_path / "PDF").mkdir()
    (tmp_path / "PDF" / "P1.jpg").write_bytes(b"\xff\xd8\xff")

    _write_mapping(tmp_path, {
        "roles": {
            "photo_test_point": {"path": "PDF/P1.jpg"},
        },
    })

    fe = FileEntry(
        path="PDF/P1.jpg",
        type="image",
        size_kb=120,
        text_extractable=False,
        concepts_detected=[],
    )

    calls: list[str] = []
    monkeypatch.setattr(
        vision_probe, "_run_probe",
        lambda fp: calls.append(str(fp)) or None,
    )

    vision_probe.probe_unreadable_files([fe], tmp_path)

    assert calls == [], (
        "legacy-output skip must apply regardless of role allow-list; "
        f"unexpected probes: {calls}"
    )
