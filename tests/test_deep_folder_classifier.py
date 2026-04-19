"""Tests for automation.deep_folder_classifier."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from automation.deep_folder_classifier import (  # noqa: E402
    _layer1_filename,
    _layer0_probe_cache,
    _doc_type_to_role,
    classify_unclassified_files,
)
from automation.file_scanner import FileMapping, FileRole  # noqa: E402


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

def _make_attachment(
    project_path: Path, subject: str, filename: str, data: bytes = b"x" * 10,
) -> Path:
    """Create a file under validation/msg_attachments/{subject}/{filename}."""
    att_dir = project_path / "validation" / "msg_attachments" / subject
    att_dir.mkdir(parents=True, exist_ok=True)
    att = att_dir / filename
    att.write_bytes(data)
    return att


def _make_deep_file(
    project_path: Path, subdirs: tuple[str, ...], filename: str,
    data: bytes = b"x" * 10,
) -> Path:
    """Create a file at project_path / subdirs[0] / .../ filename."""
    target = project_path.joinpath(*subdirs)
    target.mkdir(parents=True, exist_ok=True)
    out = target / filename
    out.write_bytes(data)
    return out


def _make_fake_msg(project_path: Path, stem: str) -> Path:
    msg = project_path / f"{stem}.msg"
    msg.write_bytes(b"fake")
    return msg


def _write_probe_cache(
    probes_dir: Path, file_path: Path, doc_type: str,
    doc_desc: str = "", concepts: list[dict] | None = None,
) -> Path:
    """Write a ConceptScout-style probe cache entry for file_path.

    Uses the same hashing scheme as `automation.concept_scout.vision_probe._cache_key`.
    """
    probes_dir.mkdir(parents=True, exist_ok=True)
    stat = file_path.stat()
    raw = f"{file_path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}"
    key = hashlib.md5(raw.encode()).hexdigest()[:12]
    payload = {
        "document_type": doc_type,
        "document_description": doc_desc,
        "concepts_found": concepts or [],
    }
    cache_file = probes_dir / f"{key}.json"
    cache_file.write_text(json.dumps(payload), encoding="utf-8")
    return cache_file


def _write_concept_map(
    project_path: Path, files: list[str],
) -> Path:
    """Write a minimal concept_map.json with file_inventory entries."""
    cm_dir = project_path / "validation"
    cm_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": {"project": project_path.name},
        "file_inventory": [
            {"path": p, "type": "image", "text_extractable": False}
            for p in files
        ],
        "concept_sources": {},
        "unresolved": [],
        "warnings": [],
    }
    cm_path = cm_dir / "concept_map.json"
    cm_path.write_text(json.dumps(payload), encoding="utf-8")
    return cm_path


# ---------------------------------------------------------------------------
# Layer 1 filename tests
# ---------------------------------------------------------------------------

class TestLayer1Filename:
    def test_matches_architect_project(self, tmp_path):
        att = _make_attachment(tmp_path, "Subject1", "PROJECTE_BASIC_V2.pdf")
        assert _layer1_filename(att) == "architect_project"

    def test_matches_architect_plan(self, tmp_path):
        att = _make_attachment(tmp_path, "Subject1", "A.01.pdf")
        assert _layer1_filename(att) == "architect_plan"

    def test_no_match_for_random_image(self, tmp_path):
        att = _make_attachment(tmp_path, "Subject1", "image001.jpg")
        assert _layer1_filename(att) is None


# ---------------------------------------------------------------------------
# Layer 0 probe-cache tests
# ---------------------------------------------------------------------------

class TestLayer0ProbeCache:
    def test_returns_cached_result(self, tmp_path):
        probes = tmp_path / "validation" / "concept_probes"
        att = _make_attachment(tmp_path, "Subject1", "image001.jpg")
        _write_probe_cache(probes, att, "architect_plan", "Dimensioned floor plan")
        out = _layer0_probe_cache(att, probes)
        assert out is not None
        assert out["document_type"] == "architect_plan"

    def test_cache_miss_returns_none(self, tmp_path):
        probes = tmp_path / "validation" / "concept_probes"
        probes.mkdir(parents=True, exist_ok=True)
        att = _make_attachment(tmp_path, "Subject1", "never_probed.jpg")
        assert _layer0_probe_cache(att, probes) is None

    def test_no_probes_dir_returns_none(self, tmp_path):
        att = _make_attachment(tmp_path, "Subject1", "image001.jpg")
        assert _layer0_probe_cache(att, None) is None


class TestDocTypeToRole:
    def test_simple_mapping(self, tmp_path):
        att = _make_attachment(tmp_path, "Subject1", "image001.jpg")
        assert _doc_type_to_role("architect_plan", "", att) == "architect_plan"

    def test_map_topographic_becomes_geological_map(self, tmp_path):
        att = _make_attachment(tmp_path, "Subject1", "F4_MGEOL.png")
        role = _doc_type_to_role(
            "map", "Topographic map with contour lines", att,
        )
        assert role == "figure_geological_map"

    def test_map_situation_becomes_situation_plan(self, tmp_path):
        att = _make_attachment(tmp_path, "Subject1", "F1_SIT.png")
        role = _doc_type_to_role("map", "Situation map of the plot", att)
        assert role == "situation_plan"

    def test_field_sheet_dpsh_by_filename(self, tmp_path):
        att = _make_attachment(tmp_path, "Subject1", "dpsh_photo.jpg")
        role = _doc_type_to_role("field_sheet", "Handwritten sheet", att)
        assert role == "dpsh_field_sheet"

    def test_field_sheet_sondeig_by_filename(self, tmp_path):
        att = _make_attachment(tmp_path, "Subject1", "sondeig_page1.jpg")
        role = _doc_type_to_role("field_sheet", "Handwritten sheet", att)
        assert role == "sondeig_field_sheet"

    def test_unknown_doc_type_returns_none(self, tmp_path):
        att = _make_attachment(tmp_path, "Subject1", "image001.jpg")
        assert _doc_type_to_role("xml_invoice", "", att) is None


# ---------------------------------------------------------------------------
# Integration — classify_unclassified_files (msg attachments only)
# ---------------------------------------------------------------------------

class TestClassifyMsgAttachments:
    def test_filename_match_promotes_to_empty_role(self, tmp_path):
        _make_fake_msg(tmp_path, "Subject1")
        _make_attachment(tmp_path, "Subject1", "PROJECTE_BASIC.pdf")
        mapping = FileMapping()

        prov = classify_unclassified_files(tmp_path, mapping, vision_client=None)

        assert "architect_project" in mapping.roles
        role = mapping.roles["architect_project"]
        assert role.path.endswith("PROJECTE_BASIC.pdf")
        assert role.confidence == "high"
        assert role.detection == "deep_folder:filename"
        rel = role.path
        assert rel in prov
        entry = prov[rel]
        assert entry["classifier_used"] == "filename"
        assert entry["role_assigned"] == "architect_project"
        assert entry["confidence"] == 0.9

    def test_filename_match_doesnt_override_existing_role(self, tmp_path):
        _make_fake_msg(tmp_path, "Subject1")
        _make_attachment(tmp_path, "Subject1", "A.01.pdf")
        existing = FileRole(
            path="A.01.pdf", confidence="high",
            detection="filename_pattern", vision_type="planol",
        )
        mapping = FileMapping(roles={"architect_plan": existing})

        prov = classify_unclassified_files(tmp_path, mapping, vision_client=None)

        assert mapping.roles["architect_plan"] is existing
        assert len(prov) == 1
        entry = next(iter(prov.values()))
        assert entry["classifier_used"] == "filename"
        assert entry["role_assigned"] is None
        assert entry["role_candidate"] == "architect_plan"

    def test_vision_classifier_routes_to_role(self, tmp_path):
        _make_fake_msg(tmp_path, "Subject1")
        _make_attachment(
            tmp_path, "Subject1", "image001.jpg",
            data=b"\xff\xd8\xff\xe0" + b"fake_jpeg_content" * 500,
        )
        mapping = FileMapping()

        def mock_vision(_path):
            return "architect_plan"

        prov = classify_unclassified_files(
            tmp_path, mapping, vision_client=mock_vision,
        )

        assert "architect_plan" in mapping.roles
        role = mapping.roles["architect_plan"]
        assert role.path.endswith("image001.jpg")
        assert role.detection == "deep_folder:vision"
        assert role.confidence == "medium"  # 0.7 → medium
        entry = next(iter(prov.values()))
        assert entry["classifier_used"] == "vision"
        assert entry["confidence"] == 0.7

    def test_xlsx_skipped_by_vision(self, tmp_path):
        _make_fake_msg(tmp_path, "Subject1")
        _make_attachment(tmp_path, "Subject1", "PLAN_COST_RANDOM.xlsx")
        mapping = FileMapping()

        calls = []
        def mock_vision(path):
            calls.append(path)
            return "architect_plan"

        prov = classify_unclassified_files(
            tmp_path, mapping, vision_client=mock_vision,
        )

        assert calls == []
        assert len(prov) == 1
        entry = next(iter(prov.values()))
        assert entry["classifier_used"] == "unclassified"
        assert entry["role_assigned"] is None

    def test_provenance_always_written(self, tmp_path):
        _make_fake_msg(tmp_path, "Subject1")
        _make_attachment(
            tmp_path, "Subject1", "image001.jpg",
            data=b"\xff\xd8\xff\xe0" + b"fake" * 200,
        )
        mapping = FileMapping()

        def mock_vision(_path):
            return "other"

        prov = classify_unclassified_files(
            tmp_path, mapping, vision_client=mock_vision,
        )

        assert len(prov) == 1
        entry = next(iter(prov.values()))
        assert entry["role_assigned"] is None
        assert entry["probe_status"] == "ok"
        assert entry["classifier_used"] == "vision"

    def test_no_attachments_dir_returns_empty(self, tmp_path):
        mapping = FileMapping()
        prov = classify_unclassified_files(tmp_path, mapping, vision_client=None)
        assert prov == {}
        assert mapping.roles == {}


# ---------------------------------------------------------------------------
# Phase A — NEW tests
# ---------------------------------------------------------------------------

class TestLayer0Integration:
    def test_probe_cache_hit_promotes_empty_role(self, tmp_path):
        """Layer 0 probe cache hit should bypass filename/vision layers."""
        _make_fake_msg(tmp_path, "Subject1")
        att = _make_attachment(
            tmp_path, "Subject1", "image001.jpg", data=b"fake" * 100,
        )
        probes = tmp_path / "validation" / "concept_probes"
        _write_probe_cache(probes, att, "architect_plan", "Floor plan")
        mapping = FileMapping()

        # vision_client=None — should still succeed via probe cache
        prov = classify_unclassified_files(tmp_path, mapping, vision_client=None)

        assert "architect_plan" in mapping.roles
        assert mapping.roles["architect_plan"].detection == "deep_folder:probe_cache"
        entry = next(iter(prov.values()))
        assert entry["classifier_used"] == "probe_cache"
        assert entry["doc_type"] == "architect_plan"
        assert entry["confidence"] == 0.85

    def test_probe_cache_disambiguates_map(self, tmp_path):
        """doc_type=map with 'topographic' description → figure_geological_map."""
        _make_fake_msg(tmp_path, "Subject1")
        att = _make_attachment(
            tmp_path, "Subject1", "F4_MGEOL.png", data=b"fake" * 100,
        )
        probes = tmp_path / "validation" / "concept_probes"
        _write_probe_cache(probes, att, "map", "Topographic map with contours")
        mapping = FileMapping()

        classify_unclassified_files(tmp_path, mapping, vision_client=None)

        assert "figure_geological_map" in mapping.roles

    def test_probe_cache_field_sheet_dpsh_via_filename(self, tmp_path):
        """doc_type=field_sheet + filename 'dpsh' → dpsh_field_sheet."""
        _make_fake_msg(tmp_path, "Subject1")
        att = _make_attachment(
            tmp_path, "Subject1", "dpsh_p1.jpg", data=b"fake" * 100,
        )
        probes = tmp_path / "validation" / "concept_probes"
        _write_probe_cache(probes, att, "field_sheet", "Handwritten notes")
        mapping = FileMapping()

        classify_unclassified_files(tmp_path, mapping, vision_client=None)

        assert "dpsh_field_sheet" in mapping.roles

    def test_probe_cache_field_sheet_sondeig_via_filename(self, tmp_path):
        """doc_type=field_sheet + filename 'sondeig' → sondeig_field_sheet."""
        _make_fake_msg(tmp_path, "Subject1")
        att = _make_attachment(
            tmp_path, "Subject1", "sondeig_p1.jpg", data=b"fake" * 100,
        )
        probes = tmp_path / "validation" / "concept_probes"
        _write_probe_cache(probes, att, "field_sheet", "Handwritten notes")
        mapping = FileMapping()

        classify_unclassified_files(tmp_path, mapping, vision_client=None)

        assert "sondeig_field_sheet" in mapping.roles


class TestVisionCap:
    def test_vision_cap_enforced(self, tmp_path, monkeypatch):
        """MAX_VISION_CALLS_PER_RUN=2 — 5 unclassified images, only 2 get vision."""
        monkeypatch.setattr(
            "automation.deep_folder_classifier.MAX_VISION_CALLS_PER_RUN", 2,
        )

        _make_fake_msg(tmp_path, "Subject1")
        calls = []

        def mock_vision(path):
            calls.append(path)
            return "architect_plan"

        # Create 5 image files; all have random names, no filename match
        jpg_data = b"\xff\xd8\xff\xe0" + b"fake" * 500
        for i in range(5):
            _make_attachment(tmp_path, "Subject1", f"img_random_{i}.jpg", data=jpg_data)
        mapping = FileMapping()

        prov = classify_unclassified_files(
            tmp_path, mapping, vision_client=mock_vision,
        )

        assert len(calls) == 2  # exactly at the cap
        assert len(prov) == 5   # all 5 still recorded
        capped = [v for v in prov.values() if "vision_cap_reached" in v["probe_detail"]]
        assert len(capped) == 3


class TestOutputDirFilter:
    def test_pdf_annexes_output_excluded(self, tmp_path):
        """Files in PDF/ANNEXES/ are Eva's exported reports, never input roles."""
        # Exported situation plan (NOT an input file)
        exported = _make_deep_file(
            tmp_path, ("PDF", "ANNEXES"), "3001621_planol_de_situacio.pdf",
            data=b"fake" * 100,
        )
        _write_concept_map(tmp_path, [str(exported.relative_to(tmp_path))])
        probes = tmp_path / "validation" / "concept_probes"
        # Even if ConceptScout classified it as situation_plan, we must skip
        _write_probe_cache(probes, exported, "map", "Situation map")
        mapping = FileMapping()

        prov = classify_unclassified_files(tmp_path, mapping, vision_client=None)

        # File must NOT be in provenance (filtered out before classification)
        assert str(exported.relative_to(tmp_path)) not in prov
        # situation_plan role must NOT be promoted from an output file
        assert "situation_plan" not in mapping.roles

    def test_pdf_v0_letra_output_excluded(self, tmp_path):
        """Files in PDF_V0/LETRA/ (cover pages) must also be skipped."""
        exported = _make_deep_file(
            tmp_path, ("PDF_V0", "LETRA"), "4001679_portada_V0.pdf",
            data=b"fake" * 100,
        )
        _write_concept_map(tmp_path, [str(exported.relative_to(tmp_path))])
        mapping = FileMapping()

        prov = classify_unclassified_files(tmp_path, mapping, vision_client=None)
        assert str(exported.relative_to(tmp_path)) not in prov

    def test_validation_artifact_excluded(self, tmp_path):
        """Files under validation/concept_probes/ and validation/mined_images/
        must be skipped (they're pipeline artifacts)."""
        artifact = _make_deep_file(
            tmp_path, ("validation", "mined_images"), "page01_img1.png",
            data=b"fake" * 100,
        )
        _write_concept_map(tmp_path, [str(artifact.relative_to(tmp_path))])
        mapping = FileMapping()

        prov = classify_unclassified_files(tmp_path, mapping, vision_client=None)
        assert str(artifact.relative_to(tmp_path)) not in prov


class TestDeepFolderWalk:
    def test_concept_map_deep_folder_file_classified(self, tmp_path):
        """File in FOTOGRAFIES/S1/ surfaces via concept_map and gets classified."""
        # Put a WhatsApp-style photo in FOTOGRAFIES/S1/ (a deep subfolder)
        photo = _make_deep_file(
            tmp_path, ("FOTOGRAFIES", "S1"), "IMG-20230101-WA0001.jpg",
            data=b"\xff\xd8\xff\xe0" + b"fake" * 200,
        )
        # Write concept_map.json that lists this file
        _write_concept_map(tmp_path, [str(photo.relative_to(tmp_path))])
        # Write a probe cache entry that classifies it as site_photo
        probes = tmp_path / "validation" / "concept_probes"
        _write_probe_cache(probes, photo, "site_photo", "WhatsApp slope photo")
        mapping = FileMapping()

        prov = classify_unclassified_files(tmp_path, mapping, vision_client=None)

        # File should be in provenance and field_photo role should get promoted
        rel = str(photo.relative_to(tmp_path))
        assert rel in prov
        assert prov[rel]["classifier_used"] == "probe_cache"
        assert "field_photo" in mapping.roles

    def test_concept_map_files_already_assigned_are_skipped(self, tmp_path):
        """Files already in mapping.roles must not be reprocessed."""
        photo = _make_deep_file(
            tmp_path, ("FOTOGRAFIES", "S1"), "IMG.jpg", data=b"fake" * 100,
        )
        _write_concept_map(tmp_path, [str(photo.relative_to(tmp_path))])
        # Pre-assign the file to a role
        existing = FileRole(
            path=str(photo.relative_to(tmp_path)), confidence="high",
            detection="filename", vision_type=None,
        )
        mapping = FileMapping(roles={"field_photo": existing})

        prov = classify_unclassified_files(tmp_path, mapping, vision_client=None)

        # The assigned file should NOT appear in provenance
        assert str(photo.relative_to(tmp_path)) not in prov


# ---------------------------------------------------------------------------
# Backward-compat wrapper
# ---------------------------------------------------------------------------

class TestBackwardCompat:
    def test_classify_email_attachments_wrapper_still_works(self, tmp_path):
        """The old API name still promotes files to deep_folder_files."""
        from automation.deep_folder_classifier import classify_email_attachments

        _make_fake_msg(tmp_path, "Subject1")
        _make_attachment(tmp_path, "Subject1", "PROJECTE_BASIC.pdf")
        mapping = FileMapping()

        prov = classify_email_attachments(tmp_path, mapping, vision_client=None)

        assert "architect_project" in mapping.roles
        assert len(prov) == 1
        # Provenance written to the new field
        assert mapping.deep_folder_files == prov
