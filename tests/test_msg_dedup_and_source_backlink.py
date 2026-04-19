"""Tests for MsgMiner attachment content-hash dedup and vision extractor
`_metadata.source_file` backlink.

Covers Stream C of the 2026-04-19 knob fixes:
- Knob #5: duplicate .msg attachments (same content) must be saved + mined once
  even when forwarded through multiple emails.
- Data gap: every `validation/{planol,sondeig,dpsh,...}_extracted.json` must
  carry `_metadata.source_file` so inspection tooling can trace vision fields
  back to the input PDF.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------------------------------------------------------------------------
# Change 1: MsgMiner dedup
# ---------------------------------------------------------------------------

class _FakeAttachment:
    """Mimic the bits of extract_msg.Attachment that MsgMiner uses."""

    def __init__(self, name: str, data: bytes) -> None:
        self.longFilename = name
        self.shortFilename = name
        self.data = data


class _FakeMsg:
    """Mimic the bits of extract_msg.Message that MsgMiner uses."""

    def __init__(
        self,
        body: str = "",
        subject: str = "",
        sender: str = "",
        attachments: list | None = None,
    ) -> None:
        self.body = body
        self.subject = subject
        self.sender = sender
        self.attachments = attachments or []

    def close(self) -> None:  # noqa: D401
        pass


def _make_miner(project_path: Path):
    from automation.fileminer.miners.msg_miner import MsgMiner, reset_attachment_registry

    reset_attachment_registry(project_path)
    return MsgMiner(project_path, "content_email")


class TestMsgAttachmentDedup:
    """Content-hash dedup for .msg attachments."""

    def test_identical_attachment_saved_once(self, tmp_path):
        """Two .msg files with the same attachment bytes → one on-disk copy."""
        from automation.fileminer.miners.msg_miner import reset_attachment_registry

        reset_attachment_registry(tmp_path)
        miner = _make_miner(tmp_path)

        # 10KB pdf-ish bytes (above _MIN_ATTACHMENT_BYTES = 5000)
        content = b"%PDF-1.4\n" + b"A" * 20_000
        att = _FakeAttachment("report.pdf", content)

        msg1_path = tmp_path / "email_one.msg"
        msg2_path = tmp_path / "email_two.msg"
        msg1_path.touch()
        msg2_path.touch()

        saved1 = miner._save_attachments(_FakeMsg(attachments=[att]), msg1_path)
        saved2 = miner._save_attachments(_FakeMsg(attachments=[att]), msg2_path)

        assert len(saved1) == 1
        assert len(saved2) == 1, "second .msg should still emit a signal for the attachment"

        # Only ONE file on disk despite two msg files referencing the same content
        all_pdfs = list((tmp_path / "validation" / "msg_attachments").rglob("*.pdf"))
        assert len(all_pdfs) == 1, f"expected 1 on-disk copy, got {len(all_pdfs)}: {all_pdfs}"

        # Second save must alias to the first path (not the email_two folder)
        assert saved2[0] == saved1[0], "duplicate should alias to the first-saved path"
        assert saved1[0].is_file()

    def test_different_content_same_name_both_saved(self, tmp_path):
        """Same filename but different bytes → both saved (no false dedup)."""
        from automation.fileminer.miners.msg_miner import reset_attachment_registry

        reset_attachment_registry(tmp_path)
        miner = _make_miner(tmp_path)

        att_a = _FakeAttachment("report.pdf", b"%PDF-A\n" + b"A" * 20_000)
        att_b = _FakeAttachment("report.pdf", b"%PDF-B\n" + b"B" * 20_000)

        msg1 = tmp_path / "e1.msg"; msg1.touch()
        msg2 = tmp_path / "e2.msg"; msg2.touch()

        saved1 = miner._save_attachments(_FakeMsg(attachments=[att_a]), msg1)
        saved2 = miner._save_attachments(_FakeMsg(attachments=[att_b]), msg2)

        all_pdfs = list((tmp_path / "validation" / "msg_attachments").rglob("*.pdf"))
        assert len(all_pdfs) == 2, (
            f"distinct content (same name) must both save, got {len(all_pdfs)}"
        )
        assert saved1[0] != saved2[0]

    def test_different_attachments_within_same_msg(self, tmp_path):
        """Two distinct attachments in the same .msg file both get saved."""
        from automation.fileminer.miners.msg_miner import reset_attachment_registry

        reset_attachment_registry(tmp_path)
        miner = _make_miner(tmp_path)

        att_a = _FakeAttachment("a.pdf", b"%PDF-A\n" + b"X" * 20_000)
        att_b = _FakeAttachment("b.pdf", b"%PDF-B\n" + b"Y" * 20_000)

        msg_path = tmp_path / "email.msg"; msg_path.touch()
        saved = miner._save_attachments(
            _FakeMsg(attachments=[att_a, att_b]), msg_path,
        )
        assert len(saved) == 2
        assert {p.name for p in saved} == {"a.pdf", "b.pdf"}

    def test_reset_registry_clears_dedup_state(self, tmp_path):
        """reset_attachment_registry releases the registry so future saves re-save."""
        from automation.fileminer.miners.msg_miner import reset_attachment_registry

        reset_attachment_registry(tmp_path)
        miner = _make_miner(tmp_path)

        content = b"%PDF-1.4\n" + b"Z" * 20_000
        att = _FakeAttachment("report.pdf", content)

        msg1 = tmp_path / "e1.msg"; msg1.touch()
        msg2 = tmp_path / "e2.msg"; msg2.touch()

        # First round: save under e1
        saved1 = miner._save_attachments(_FakeMsg(attachments=[att]), msg1)
        original = saved1[0]

        # Reset, delete on-disk copy, re-save under e2 → must write fresh copy
        reset_attachment_registry(tmp_path)
        original.unlink()
        saved2 = miner._save_attachments(_FakeMsg(attachments=[att]), msg2)

        assert saved2[0].is_file()
        assert saved2[0].parent.name == "e2"

    def test_tiny_attachment_skipped(self, tmp_path):
        """Below-threshold attachments are not saved (pre-existing behavior)."""
        from automation.fileminer.miners.msg_miner import reset_attachment_registry

        reset_attachment_registry(tmp_path)
        miner = _make_miner(tmp_path)

        att = _FakeAttachment("tiny.pdf", b"hi")
        msg = tmp_path / "e.msg"; msg.touch()

        saved = miner._save_attachments(_FakeMsg(attachments=[att]), msg)
        assert saved == []

    def test_dedup_via_seed_registry_preserves_existing_on_disk_duplicate(self, tmp_path):
        """Simulates production case: server restarts, finds a previously-saved
        attachment in validation/msg_attachments/, seeds the registry, then
        mines a new .msg whose attachment has identical content. The second
        save should alias to the pre-existing path (no new file written).
        """
        from automation.fileminer.miners.msg_miner import reset_attachment_registry

        # 1. Pre-populate a saved attachment under a prior msg stem on disk.
        content = b"%PDF-1.4\n" + b"S" * 30_000
        prior_stem_dir = tmp_path / "validation" / "msg_attachments" / "older_email"
        prior_stem_dir.mkdir(parents=True)
        prior_path = prior_stem_dir / "foo.pdf"
        prior_path.write_bytes(content)

        # 2. Fresh process → clear in-memory registry so the seed step runs
        #    over the disk contents we just created.
        reset_attachment_registry(tmp_path)
        miner = _make_miner(tmp_path)

        # 3. A new .msg arrives carrying an attachment with identical bytes.
        att = _FakeAttachment("foo.pdf", content)
        new_msg = tmp_path / "newer_email.msg"
        new_msg.touch()

        saved = miner._save_attachments(_FakeMsg(attachments=[att]), new_msg)

        # 4. No new file under newer_email/ — the save must alias to the
        #    pre-existing path discovered via the seed.
        new_stem_dir = tmp_path / "validation" / "msg_attachments" / "newer_email"
        new_stem_pdf = new_stem_dir / "foo.pdf"
        assert not new_stem_pdf.exists(), (
            "duplicate content must not be re-written under the new msg stem"
        )

        # 5. saved list references the pre-existing path.
        assert len(saved) == 1
        assert saved[0] == prior_path, (
            f"expected alias to {prior_path}, got {saved[0]}"
        )
        assert saved[0].read_bytes() == content


# ---------------------------------------------------------------------------
# Change 2: vision extractor source_file backlink
# ---------------------------------------------------------------------------

class TestAttachSourceMetadata:
    """Unit tests for `attach_source_metadata` helper."""

    def test_adds_metadata_block_with_source_file(self, tmp_path):
        from automation.vision_extractor import attach_source_metadata

        data: dict = {"architect_data": {"architect": "Eva"}}
        pdf_path = tmp_path / "A.01.pdf"
        pdf_path.write_bytes(b"%PDF")

        result = attach_source_metadata(data, pdf_path, project_path=tmp_path)

        assert "_metadata" in result
        assert result["_metadata"]["source_file"] == "A.01.pdf"
        assert "extracted_at" in result["_metadata"]
        # Original data untouched
        assert result["architect_data"]["architect"] == "Eva"

    def test_source_file_is_project_relative(self, tmp_path):
        from automation.vision_extractor import attach_source_metadata

        sub = tmp_path / "ANNEXES"
        sub.mkdir()
        pdf = sub / "4001612_sondeig.pdf"
        pdf.write_bytes(b"%PDF")

        data: dict = {"sondeig_tests": []}
        attach_source_metadata(data, pdf, project_path=tmp_path)

        # Normalize separator for cross-platform test robustness
        rel = data["_metadata"]["source_file"].replace("\\", "/")
        assert rel == "ANNEXES/4001612_sondeig.pdf"

    def test_basename_fallback_when_no_project_path(self, tmp_path):
        from automation.vision_extractor import attach_source_metadata

        pdf = tmp_path / "foo.pdf"
        pdf.write_bytes(b"%PDF")
        data: dict = {}
        attach_source_metadata(data, pdf)
        assert data["_metadata"]["source_file"] == "foo.pdf"

    def test_records_extraction_method_when_provided(self, tmp_path):
        from automation.vision_extractor import attach_source_metadata

        pdf = tmp_path / "x.pdf"
        pdf.write_bytes(b"%PDF")
        data: dict = {}
        attach_source_metadata(data, pdf, extraction_method="groq_vision")
        assert data["_metadata"]["extraction_method"] == "groq_vision"

    def test_preserves_existing_metadata_keys(self, tmp_path):
        from automation.vision_extractor import attach_source_metadata

        pdf = tmp_path / "x.pdf"
        pdf.write_bytes(b"%PDF")
        data = {"_metadata": {"source_file": "pre-existing.pdf"}}
        attach_source_metadata(data, pdf, project_path=tmp_path)
        # Does not overwrite existing source_file
        assert data["_metadata"]["source_file"] == "pre-existing.pdf"
        # Adds extracted_at
        assert "extracted_at" in data["_metadata"]


class TestExtractFromWritersHaveMetadata:
    """Ensure each public extractor stamps `_metadata.source_file`.

    These tests stub the Claude API so no network call is made.
    """

    def test_extract_from_planol_stamps_metadata(self, tmp_path, monkeypatch):
        import automation.vision_extractor as vx

        pdf = tmp_path / "A.01.pdf"
        pdf.write_bytes(b"%PDF")

        monkeypatch.setattr(vx, "_file_to_images", lambda p: [(b"img", "image/png")])
        monkeypatch.setattr(
            vx, "_call_vision",
            lambda *a, **kw: '```json\n{"architect_data": {"architect": "Eva"}}\n```',
        )

        result = vx.extract_from_planol(pdf)
        assert "_metadata" in result
        assert result["_metadata"]["source_file"] == "A.01.pdf"

    def test_extract_from_penetros_stamps_metadata(self, tmp_path, monkeypatch):
        import automation.vision_extractor as vx

        pdf = tmp_path / "PENETROS.pdf"
        pdf.write_bytes(b"%PDF")

        monkeypatch.setattr(vx, "_file_to_images", lambda p: [(b"img", "image/png")])
        monkeypatch.setattr(
            vx, "_call_vision", lambda *a, **kw: '{"dpsh_tests": []}',
        )

        result = vx.extract_from_penetros(pdf)
        assert result["_metadata"]["source_file"] == "PENETROS.pdf"

    def test_extract_from_sondeig_stamps_metadata(self, tmp_path, monkeypatch):
        import automation.vision_extractor as vx

        pdf = tmp_path / "SONDEIG.pdf"
        pdf.write_bytes(b"%PDF")

        monkeypatch.setattr(vx, "_file_to_images", lambda p: [(b"img", "image/png")])
        monkeypatch.setattr(
            vx, "_call_vision", lambda *a, **kw: '{"sondeig_tests": []}',
        )

        result = vx.extract_from_sondeig(pdf)
        assert result["_metadata"]["source_file"] == "SONDEIG.pdf"

    def test_extract_from_sondeig_annex_stamps_metadata(self, tmp_path, monkeypatch):
        import automation.vision_extractor as vx

        pdf = tmp_path / "annex_sondeig.pdf"
        pdf.write_bytes(b"%PDF")

        monkeypatch.setattr(vx, "_file_to_images", lambda p: [(b"img", "image/png")])
        monkeypatch.setattr(
            vx, "_call_vision", lambda *a, **kw: '{"geological_levels": []}',
        )

        result = vx.extract_from_sondeig_annex(pdf)
        assert result["_metadata"]["source_file"] == "annex_sondeig.pdf"


class TestExtractOrCacheWritesProjectRelativeSource:
    """`_extract_or_cache` must stamp project-relative source_file on fresh extractions."""

    def test_cache_write_includes_project_relative_source(self, tmp_path, monkeypatch):
        import automation.vision_extractor as vx

        project_path = tmp_path
        validation_dir = project_path / "validation"
        validation_dir.mkdir()

        annexes = project_path / "ANNEXES"
        annexes.mkdir()
        pdf = annexes / "A.01.pdf"
        pdf.write_bytes(b"%PDF")

        cache_path = validation_dir / "planol_extracted.json"

        def fake_extract(p: Path) -> dict:
            return {"architect_data": {"architect": "Eva"}}

        vx._extract_or_cache(
            "planol", "architect_plan", pdf, cache_path,
            fake_extract, force_refresh=True, project_path=project_path,
        )

        assert cache_path.exists()
        written = json.loads(cache_path.read_text(encoding="utf-8"))
        assert "_metadata" in written
        rel = written["_metadata"]["source_file"].replace("\\", "/")
        assert rel == "ANNEXES/A.01.pdf"
