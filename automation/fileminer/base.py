"""Base class for all FileMiner miners."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from .models import Signal


class BaseMiner(ABC):
    """Abstract base class for file miners.

    Each miner handles one file type and extracts Signal objects.
    """

    def __init__(self, project_path: Path, source_type: str) -> None:
        """
        Args:
            project_path: Root path of the project being mined
            source_type: Default source type for signals (e.g., "dades_camp_excel")
        """
        self.project_path = project_path
        self.source_type = source_type

    @abstractmethod
    def mine(self, file_path: Path) -> list[Signal]:
        """Extract signals from a single file.

        Args:
            file_path: Absolute path to the file to mine

        Returns:
            List of Signal objects extracted from the file
        """
        ...

    @abstractmethod
    def can_mine(self, file_path: Path) -> bool:
        """Check if this miner can handle the given file.

        Args:
            file_path: Absolute path to the file

        Returns:
            True if this miner should process this file
        """
        ...

    def _relative_path(self, file_path: Path) -> str:
        """Get path relative to project root, for signal provenance."""
        try:
            return str(file_path.relative_to(self.project_path))
        except ValueError:
            return str(file_path)
