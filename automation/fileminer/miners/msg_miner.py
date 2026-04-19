"""Outlook .msg email miner -- extracts signals from email body + saves attachments."""

from __future__ import annotations

import hashlib
import logging
import threading
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

# Lock guarding mutations of _ATTACHMENT_HASH_REGISTRY. The vision/mining
# pipeline calls miners from a ThreadPoolExecutor (see web/vision_groq.py),
# so concurrent .msg extraction on the same project can race the
# check-then-write sequence in _save_attachments. A single module-level
# lock is sufficient — held briefly around the registry decision + update
# (NOT around disk writes); see _save_attachments for the release pattern.
_REGISTRY_LOCK = threading.Lock()


def reset_attachment_registry(project_path: Path | None = None) -> None:
    """Clear the dedup registry.

    Useful for tests and for forcing re-mining within a single process.
    If project_path is None, clears all projects.
    """
    with _REGISTRY_LOCK:
        if project_path is None:
            _ATTACHMENT_HASH_REGISTRY.clear()
        else:
            key = str(project_path.resolve())
            _ATTACHMENT_HASH_REGISTRY.pop(key, None)


def _hash_bytes(data: bytes) -> str:
    """Return sha256 hex digest of the given bytes."""
    return hashlib.sha256(data).hexdigest()


def _hash_file(path: Path) -> str:
    """Return sha256 hex digest of a file, streaming from disk.

    Uses hashlib.file_digest (Python 3.11+, available per pyproject.toml
    requires-python) to avoid loading whole files into memory.
    """
    with path.open('rb') as fh:
        return hashlib.file_digest(fh, 'sha256').hexdigest()


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
        with _REGISTRY_LOCK:
            registry = _ATTACHMENT_HASH_REGISTRY.setdefault(project_key, {})

        # Seed registry with any already-on-disk attachments from prior runs,
        # so a mid-session re-run (or a long-running server's subsequent sweep)
        # doesn't duplicate work. Re-seeded unconditionally on every call — the
        # streaming hash makes it cheap, and caching across sweeps would miss
        # files added to disk between invocations in the long-running server.
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
                out_path = att_dir / name

                # Decide action under lock (dedup check + path reservation).
                # We hold the lock across the decision and the registry write,
                # but release it before the actual disk I/O (write_bytes).
                # This keeps the critical section tiny and lets other threads
                # progress even during large attachment writes.
                with _REGISTRY_LOCK:
                    existing = registry.get(content_hash)
                    if existing is not None and existing.is_file():
                        alias_target = existing
                        action = 'alias'
                    elif out_path.exists():
                        # Prior run already wrote this exact path. The seed step
                        # should have registered its hash already; skip re-hash
                        # when that's the case. Only re-hash for the rare drift
                        # case (path exists on disk but wasn't in the seed).
                        already_registered = any(
                            p == out_path for p in registry.values()
                        )
                        action = 'exists'
                    else:
                        # Reserve the slot so a concurrent identical attachment
                        # on another thread aliases to this one instead of
                        # racing a second write.
                        registry[content_hash] = out_path
                        action = 'write'

                if action == 'alias':
                    logger.info(
                        "Skipping duplicate attachment %s from %s (sha256=%s, alias_of=%s)",
                        name, msg_file_path.name, content_hash[:12],
                        alias_target.relative_to(self.project_path) if alias_target.is_relative_to(self.project_path) else alias_target,
                    )
                    saved.append(alias_target)
                    continue

                if action == 'exists':
                    if not already_registered:
                        # Path on disk is not tracked by the registry (seed missed
                        # it, or a test cleared the registry after a prior run).
                        # Stream-hash once and register.
                        try:
                            prior_hash = _hash_file(out_path)
                            with _REGISTRY_LOCK:
                                registry.setdefault(prior_hash, out_path)
                        except OSError:
                            pass
                    saved.append(out_path)
                    continue

                # action == 'write'
                try:
                    out_path.write_bytes(data)
                    saved.append(out_path)
                    logger.info("Saved attachment %s from %s (%d KB, sha256=%s)",
                                name, msg_file_path.name, len(data) // 1024,
                                content_hash[:12])
                except OSError:
                    # Write failed — release our reservation so a retry can
                    # attempt again on a later sweep.
                    with _REGISTRY_LOCK:
                        if registry.get(content_hash) == out_path:
                            registry.pop(content_hash, None)
                    raise

            except Exception as e:
                logger.warning("Failed to save attachment from %s: %s",
                               msg_file_path.name, e)

        return saved

    def _seed_registry_from_disk(self, registry: dict[str, Path]) -> None:
        """Populate hash registry from already-saved attachments on disk.

        Re-seeds unconditionally on every call — in production G3DT runs as a
        long-running FastAPI server, so a cached "seeded once" flag would miss
        attachments written to disk between sweeps. Streaming hash via
        hashlib.file_digest keeps per-sweep cost low.

        Already-registered paths are skipped (cheap path-membership check),
        so repeat calls within one process pay only for newly-appeared files.
        """
        att_root = self.project_path / 'validation' / 'msg_attachments'
        if not att_root.is_dir():
            return

        # Snapshot the set of already-tracked paths to skip re-hashing files
        # the registry has already seen in this or a prior call.
        with _REGISTRY_LOCK:
            tracked_paths = set(registry.values())

        for f in sorted(att_root.rglob('*')):
            if not f.is_file():
                continue
            if f.suffix.lower() not in _PROCESSABLE_EXTENSIONS:
                continue
            if f in tracked_paths:
                continue
            try:
                h = _hash_file(f)
            except OSError:
                continue
            # First encountered wins (sorted walk = deterministic ordering)
            with _REGISTRY_LOCK:
                registry.setdefault(h, f)
