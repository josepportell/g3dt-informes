"""Tests for automation.email_attachment_classifier."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from automation.email_attachment_classifier import (  # noqa: E402
    _layer1_filename,
    classify_email_attachments,
)
from automation.file_scanner import FileMapping, FileRole  # noqa: E402


def _make_attachment(project_path: Path, subject: str, filename: str, data: bytes = b"x" * 10) -> Path:
    """Create an attachment file under validation/msg_attachments/{subject}/{filename}."""
    att_dir = project_path / "validation" / "msg_attachments" / subject
    att_dir.mkdir(parents=True, exist_ok=True)
    att = att_dir / filename
    att.write_bytes(data)
    return att


def _make_fake_msg(project_path: Path, stem: str) -> Path:
    """Create a minimal .msg marker file so _source_msg_for can find it."""
    msg = project_path / f"{stem}.msg"
    msg.write_bytes(b"fake")
    return msg


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
# Integration tests — classify_email_attachments
# ---------------------------------------------------------------------------

class TestClassifyEmailAttachments:
    def test_filename_match_promotes_to_empty_role(self, tmp_path):
        """PROJECTE_BASIC*.pdf attachment should take the empty architect_project role."""
        _make_fake_msg(tmp_path, "Subject1")
        _make_attachment(tmp_path, "Subject1", "PROJECTE_BASIC.pdf")
        mapping = FileMapping()

        prov = classify_email_attachments(tmp_path, mapping, vision_client=None)

        # Role promoted
        assert "architect_project" in mapping.roles
        role = mapping.roles["architect_project"]
        assert role.path.endswith("PROJECTE_BASIC.pdf")
        assert role.confidence == "high"  # 0.9 maps to "high"
        assert role.detection == "email_attachment:filename"
        # Provenance recorded
        rel = role.path
        assert rel in prov
        entry = prov[rel]
        assert entry["classifier_used"] == "filename"
        assert entry["role_assigned"] == "architect_project"
        assert entry["confidence"] == 0.9

    def test_filename_match_doesnt_override_existing_role(self, tmp_path):
        """When architect_plan is already assigned, a matching attachment should
        be recorded in provenance but NOT promoted."""
        _make_fake_msg(tmp_path, "Subject1")
        _make_attachment(tmp_path, "Subject1", "A.01.pdf")
        existing = FileRole(
            path="A.01.pdf", confidence="high",
            detection="filename_pattern", vision_type="planol",
        )
        mapping = FileMapping(roles={"architect_plan": existing})

        prov = classify_email_attachments(tmp_path, mapping, vision_client=None)

        # Role unchanged (still pointing to the root file)
        assert mapping.roles["architect_plan"] is existing
        # Provenance still records the attachment as a candidate
        assert len(prov) == 1
        entry = next(iter(prov.values()))
        assert entry["classifier_used"] == "filename"
        assert entry["role_assigned"] is None   # NOT promoted
        assert entry["role_candidate"] == "architect_plan"

    def test_vision_classifier_routes_to_role(self, tmp_path):
        """A mock vision client returning 'architect_plan' promotes to role."""
        _make_fake_msg(tmp_path, "Subject1")
        _make_attachment(
            tmp_path, "Subject1", "image001.jpg",
            data=b"\xff\xd8\xff\xe0" + b"fake_jpeg_content" * 500,
        )
        mapping = FileMapping()

        def mock_vision(_path):
            return "architect_plan"

        prov = classify_email_attachments(tmp_path, mapping, vision_client=mock_vision)

        assert "architect_plan" in mapping.roles
        role = mapping.roles["architect_plan"]
        assert role.path.endswith("image001.jpg")
        assert role.detection == "email_attachment:vision"
        # 0.7 → "medium"
        assert role.confidence == "medium"
        entry = next(iter(prov.values()))
        assert entry["classifier_used"] == "vision"
        assert entry["confidence"] == 0.7

    def test_xlsx_skipped_by_vision(self, tmp_path):
        """XLSX files must not be sent to the vision layer."""
        _make_fake_msg(tmp_path, "Subject1")
        _make_attachment(tmp_path, "Subject1", "PLAN_COST_RANDOM.xlsx")
        mapping = FileMapping()

        calls = []
        def mock_vision(path):
            calls.append(path)
            return "architect_plan"

        prov = classify_email_attachments(tmp_path, mapping, vision_client=mock_vision)

        # Vision must not have been called
        assert calls == []
        # Provenance still written
        assert len(prov) == 1
        entry = next(iter(prov.values()))
        assert entry["classifier_used"] == "unclassified"
        assert entry["role_assigned"] is None

    def test_provenance_always_written(self, tmp_path):
        """Even 'other' / unrecognized attachments get a provenance entry."""
        _make_fake_msg(tmp_path, "Subject1")
        _make_attachment(
            tmp_path, "Subject1", "image001.jpg",
            data=b"\xff\xd8\xff\xe0" + b"fake" * 200,
        )
        mapping = FileMapping()

        def mock_vision(_path):
            return "other"

        prov = classify_email_attachments(tmp_path, mapping, vision_client=mock_vision)

        assert len(prov) == 1
        entry = next(iter(prov.values()))
        assert entry["role_assigned"] is None
        # probe_status should be 'ok' since the model replied with a valid category
        assert entry["probe_status"] == "ok"
        assert entry["classifier_used"] == "vision"

    def test_no_attachments_dir_returns_empty(self, tmp_path):
        """A project with no msg_attachments/ dir returns without mutating mapping."""
        mapping = FileMapping()
        prov = classify_email_attachments(tmp_path, mapping, vision_client=None)
        assert prov == {}
        assert mapping.roles == {}
