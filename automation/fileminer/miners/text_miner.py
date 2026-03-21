"""Plain text file miner (.txt) -- extracts signals from text files."""

from __future__ import annotations

import logging
from pathlib import Path

from ..base import BaseMiner
from ..models import Signal
from ._detection import run_all_detectors

logger = logging.getLogger(__name__)

# Encoding fallback chain (ported from content_discovery.py)
_TEXT_ENCODINGS = ('utf-8', 'latin-1', 'cp1252')


class TextMiner(BaseMiner):
    """Extract signals from plain text files."""

    def can_mine(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == '.txt'

    def mine(self, file_path: Path) -> list[Signal]:
        text = self._read_text(file_path)
        if not text:
            return []

        rel_path = self._relative_path(file_path)
        return run_all_detectors(text, rel_path, confidence_offset=0.0)

    @staticmethod
    def _read_text(file_path: Path) -> str | None:
        """Read text file with encoding fallback chain."""
        for enc in _TEXT_ENCODINGS:
            try:
                return file_path.read_text(encoding=enc)
            except (UnicodeDecodeError, UnicodeError):
                continue
            except OSError as exc:
                logger.debug("Could not read %s: %s", file_path, exc)
                return None
        return None
