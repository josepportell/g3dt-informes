"""Outlook .msg email miner -- extracts signals from email body + saves attachments."""

from __future__ import annotations

import hashlib
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

# Content-hash registry for attachment dedup.
# Keyed by resolved project_path (str) -> {content_hash: first_saved_path}.
# Scoped per project so concurrent mining of different projects stay isolated.
# The same .pdf attached to multiple emails (common forwarded threads) is only
# written to disk + mined + vision-probed once; subsequent occurrences emit a
# signal pointing at the first-saved path so downstream stages naturally dedup
# by path (already implemented via processed_paths sets in fileminer/__init__.py).
_ATTACHMENT_HASH_REGISTRY: dict[str, dict[str, Path]] = {}

# Projects whose on-disk attachments have already been hashed into the registry
# during this process (seed step is O(N) on file count, so we do it once).
_SEEDED_PROJECTS: set[str] = set()


def reset_attachment_registry(project_path: Path | None = None) -> None:
    """Clear the dedup registry.

    Useful for tests and for forcing re-mining within a single process.
    If project_path is None, clears all projects.
    """
    if project_path is None:
        _ATTACHMENT_HASH_REGISTRY.clear()
        _SEEDED_PROJECTS.clear()
    else:
        key = str(project_path.resolve())
        _ATTACHMENT_HASH_REGISTRY.pop(key, None)
        _SEEDED_PROJECTS.discard(key)


def _hash_bytes(data: bytes) -> str:
    """Return sha256 hex digest of the given bytes."""
    return hashlib.sha256(data).hexdigest()


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
            # ── 1. Mine email body text (exclude address fields — email
            #    bodies/footers are unreliable address sources; Linyola got
            #    "administracion@g3dt.com..." parsed as street_address)
            _ADDRESS_LABELS = {
                'street_address', 'site_address', 'client_address',
                'Street address', 'Site address',
            }
            body = msg.body or ''
            if body:
                body_signals = run_all_detectors(body, rel_path, confidence_offset=-0.05)
                for sig in body_signals:
                    if sig.label in _ADDRESS_LABELS or getattr(sig, 'maps_to', None) in _ADDRESS_LABELS:
                        logger.debug("Skipping address signal from email body: %s=%r", sig.label, sig.value)
                        continue
                    signals.append(sig)

            # ── 2. Mine subject line for project hints (same address filter)
            subject = msg.subject or ''
            if subject:
                subject_signals = run_all_detectors(subject, rel_path, confidence_offset=-0.10)
                for sig in subject_signals:
                    if sig.label in _ADDRESS_LABELS or getattr(sig, 'maps_to', None) in _ADDRESS_LABELS:
                        logger.debug("Skipping address signal from email subject: %s=%r", sig.label, sig.value)
                        continue
                    signals.append(sig)

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

        Deduplicates by content hash (sha256): if an attachment with identical
        bytes has already been saved elsewhere in this project (e.g. forwarded
        through multiple emails), we skip the write and emit the first-saved
        path instead. Downstream stages dedup by path, so this cuts redundant
        mining/vision calls.

        Returns list of saved file paths (absolute). For duplicate content
        the returned path is the FIRST occurrence in the project, not the
        current msg's folder.
        """
        saved: list[Path] = []

        if not msg.attachments:
            return saved

        # Per-project hash registry (keyed on resolved absolute project path).
        project_key = str(self.project_path.resolve())
        registry = _ATTACHMENT_HASH_REGISTRY.setdefault(project_key, {})

        # Seed registry with any already-on-disk attachments from prior runs,
        # so a mid-session re-run doesn't duplicate work. Only done once per
        # process per project (cheap: reads small attachment files).
        self._seed_registry_from_disk(registry)

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

                content_hash = _hash_bytes(data)

                # Dedup: same content already saved under another msg stem?
                existing = registry.get(content_hash)
                if existing is not None and existing.is_file():
                    logger.info(
                        "Skipping duplicate attachment %s from %s (sha256=%s, alias_of=%s)",
                        name, msg_file_path.name, content_hash[:12],
                        existing.relative_to(self.project_path) if existing.is_relative_to(self.project_path) else existing,
                    )
                    saved.append(existing)
                    continue

                out_path = att_dir / name
                if out_path.exists():
                    # Don't overwrite — attachment already saved from a previous run.
                    # Register its hash so later duplicates in this session alias to it.
                    try:
                        prior_bytes = out_path.read_bytes()
                        registry.setdefault(_hash_bytes(prior_bytes), out_path)
                    except OSError:
                        pass
                    saved.append(out_path)
                    continue

                out_path.write_bytes(data)
                registry[content_hash] = out_path
                saved.append(out_path)
                logger.info("Saved attachment %s from %s (%d KB, sha256=%s)",
                            name, msg_file_path.name, len(data) // 1024,
                            content_hash[:12])

            except Exception as e:
                logger.warning("Failed to save attachment from %s: %s",
                               msg_file_path.name, e)

        return saved

    def _seed_registry_from_disk(self, registry: dict[str, Path]) -> None:
        """Populate hash registry from already-saved attachments on disk.

        Runs at most once per project per process (tracked via _SEEDED_PROJECTS).
        Lets subsequent mining sessions in the same process re-use the dedup
        logic when validation/msg_attachments/ has content from a prior run.
        """
        project_key = str(self.project_path.resolve())
        if project_key in _SEEDED_PROJECTS:
            return
        _SEEDED_PROJECTS.add(project_key)

        att_root = self.project_path / 'validation' / 'msg_attachments'
        if not att_root.is_dir():
            return
        for f in sorted(att_root.rglob('*')):
            if not f.is_file():
                continue
            if f.suffix.lower() not in _PROCESSABLE_EXTENSIONS:
                continue
            try:
                h = _hash_bytes(f.read_bytes())
            except OSError:
                continue
            # First encountered wins (sorted walk = deterministic ordering)
            registry.setdefault(h, f)
