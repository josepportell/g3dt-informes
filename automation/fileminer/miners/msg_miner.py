"""Outlook .msg email miner -- extracts signals from email body + saves attachments."""

from __future__ import annotations

import logging
from pathlib import Path

from ..base import BaseMiner
from ..models import Signal, SignalType
from ._detection import run_all_detectors

logger = logging.getLogger(__name__)

# Attachment extensions worth saving for re-processing by the pipeline
_PROCESSABLE_EXTENSIONS = {'.pdf', '.xls', '.xlsx', '.doc', '.docx', '.txt', '.jpg', '.jpeg', '.png'}

# Minimum attachment size to save (skip tiny inline images like signatures)
_MIN_ATTACHMENT_BYTES = 5_000  # 5KB


class MsgMiner(BaseMiner):
    """Extract signals from Outlook .msg email files.

    Mines the email body text with standard detectors (phones, emails,
    NIF, addresses, label-values). Also saves processable attachments
    to validation/msg_attachments/{stem}/ so they can re-enter the pipeline.
    """

    def can_mine(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == '.msg'

    def mine(self, file_path: Path) -> list[Signal]:
        try:
            import extract_msg
        except ImportError:
            logger.warning("extract-msg not installed, skipping %s", file_path.name)
            return []

        try:
            msg = extract_msg.Message(str(file_path))
        except Exception as e:
            logger.warning("Cannot open .msg %s: %s", file_path.name, e)
            return []

        signals: list[Signal] = []
        rel_path = self._relative_path(file_path)

        try:
            # ── 1. Mine email body text
            body = msg.body or ''
            if body:
                body_signals = run_all_detectors(body, rel_path, confidence_offset=-0.05)
                signals.extend(body_signals)

            # ── 2. Mine subject line for project hints
            subject = msg.subject or ''
            if subject:
                subject_signals = run_all_detectors(subject, rel_path, confidence_offset=-0.10)
                signals.extend(subject_signals)

            # ── 3. Extract sender email/name
            sender = msg.sender or ''
            if sender and '@' in sender:
                signals.append(Signal(
                    type=SignalType.TEXT,
                    label="sender_email",
                    value=sender,
                    source_file=rel_path,
                    extraction_method="msg_sender",
                    confidence=0.5,
                    source_type=self.source_type,
                ))

            # ── 4. Save processable attachments
            saved_attachments = self._save_attachments(msg, file_path)
            for att_path in saved_attachments:
                signals.append(Signal(
                    type=SignalType.TEXT,
                    label="msg_attachment",
                    value=str(att_path),
                    source_file=rel_path,
                    extraction_method="msg_attachment",
                    confidence=0.9,
                    source_type=self.source_type,
                ))

        except Exception as e:
            logger.warning("Error mining .msg %s: %s", file_path.name, e)
        finally:
            try:
                msg.close()
            except Exception:
                pass

        return signals

    def _save_attachments(self, msg, msg_file_path: Path) -> list[Path]:
        """Save processable attachments to validation/msg_attachments/{stem}/.

        Returns list of saved file paths (absolute).
        """
        saved: list[Path] = []

        if not msg.attachments:
            return saved

        # Create output directory: {project}/validation/msg_attachments/{msg_stem}/
        att_dir = self.project_path / 'validation' / 'msg_attachments' / msg_file_path.stem
        att_dir.mkdir(parents=True, exist_ok=True)

        for att in msg.attachments:
            try:
                name = att.longFilename or att.shortFilename
                if not name:
                    continue

                data = att.data
                if not data or len(data) < _MIN_ATTACHMENT_BYTES:
                    continue

                ext = Path(name).suffix.lower()
                if ext not in _PROCESSABLE_EXTENSIONS:
                    continue

                out_path = att_dir / name
                if out_path.exists():
                    # Don't overwrite — attachment already saved from a previous run
                    saved.append(out_path)
                    continue

                out_path.write_bytes(data)
                saved.append(out_path)
                logger.info("Saved attachment %s from %s (%d KB)",
                            name, msg_file_path.name, len(data) // 1024)

            except Exception as e:
                logger.warning("Failed to save attachment from %s: %s",
                               msg_file_path.name, e)

        return saved
