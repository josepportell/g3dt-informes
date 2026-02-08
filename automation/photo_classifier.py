#!/usr/bin/env python3
"""
Photo Classifier for G3DT Report Generation

Scans FOTOGRAFIES/ folder, identifies unclassified photos,
and renames them after visual classification by the Claude Code agent.

Usage (from skill orchestration):
    from automation.photo_classifier import PhotoClassifier

    classifier = PhotoClassifier(project_path)
    status = classifier.scan()
    # status.classified = already slug-named photos
    # status.unclassified = photos needing visual analysis
    # status.all_covered = True if all 4 categories have photos

    # After visual classification:
    classifier.apply_classification({
        '/path/to/P1.jpg': 'dpsh',        # category key
        '/path/to/photo2.jpg': 'sondeig',
        '/path/to/photo3.jpg': 'site',
    })
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .image_manager import PHOTO_SLUGS, PHOTO_CATEGORY_DIRS

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png'}


@dataclass
class PhotoStatus:
    """Result of scanning FOTOGRAFIES/ folder."""
    classified: dict[str, list[Path]] = field(default_factory=dict)   # category -> [paths]
    unclassified: list[Path] = field(default_factory=list)            # photos without slug names
    missing_categories: list[str] = field(default_factory=list)       # categories with no photos

    @property
    def all_covered(self) -> bool:
        """True if all 4 categories have at least one photo."""
        return len(self.missing_categories) == 0

    @property
    def needs_classification(self) -> bool:
        """True if there are unclassified photos AND missing categories."""
        return len(self.unclassified) > 0 and len(self.missing_categories) > 0


class PhotoClassifier:
    """Scans and classifies field photos for G3DT reports."""

    def __init__(self, project_path: str | Path):
        self.project_path = Path(project_path)
        self.foto_dir = self.project_path / 'FOTOGRAFIES'

    def scan(self) -> PhotoStatus:
        """
        Scan FOTOGRAFIES/ and categorize photos.

        Returns PhotoStatus with:
        - classified: photos already matching slug convention
        - unclassified: photos that need visual classification
        - missing_categories: categories without any slug-named photo
        """
        status = PhotoStatus()

        if not self.foto_dir.exists():
            logger.warning(f"FOTOGRAFIES/ not found at {self.foto_dir}")
            status.missing_categories = list(PHOTO_SLUGS.keys())
            return status

        # Initialize classified dict
        for category in PHOTO_SLUGS:
            status.classified[category] = []

        # Collect ALL image files across FOTOGRAFIES/ and subdirs
        slug_named: set[str] = set()  # lowered paths of slug-matched files

        # Check each category for slug-named files
        for category, slug in PHOTO_SLUGS.items():
            subdir = PHOTO_CATEGORY_DIRS[category]
            search_dir = self.foto_dir / subdir if subdir else self.foto_dir

            if not search_dir.exists():
                continue

            # Find files matching slug prefix
            for f in sorted(search_dir.iterdir()):
                if not f.is_file() or f.suffix.lower() not in IMAGE_EXTENSIONS:
                    continue
                if f.name.lower().startswith(slug.lower()):
                    status.classified[category].append(f)
                    slug_named.add(str(f).lower())

        # Also search root for dpsh/sondeig slugs (they might be there too)
        for category in ('dpsh', 'sondeig'):
            slug = PHOTO_SLUGS[category]
            for f in sorted(self.foto_dir.iterdir()):
                if not f.is_file() or f.suffix.lower() not in IMAGE_EXTENSIONS:
                    continue
                if f.name.lower().startswith(slug.lower()) and str(f).lower() not in slug_named:
                    status.classified[category].append(f)
                    slug_named.add(str(f).lower())

        # Collect all non-slug images as unclassified
        for directory in self._all_photo_dirs():
            if not directory.exists():
                continue
            for f in sorted(directory.iterdir()):
                if not f.is_file() or f.suffix.lower() not in IMAGE_EXTENSIONS:
                    continue
                if f.name == 'Thumbs.db':
                    continue
                if str(f).lower() not in slug_named:
                    status.unclassified.append(f)

        # Determine missing categories
        for category in PHOTO_SLUGS:
            if not status.classified[category]:
                status.missing_categories.append(category)

        # Log summary
        classified_count = sum(len(v) for v in status.classified.values())
        logger.info(
            f"Photo scan: {classified_count} classified, "
            f"{len(status.unclassified)} unclassified, "
            f"{len(status.missing_categories)} missing categories"
        )

        return status

    def apply_classification(self, classifications: dict[str, str]) -> dict[str, list[Path]]:
        """
        Rename photos based on classification results.

        Args:
            classifications: dict mapping photo path (str) -> category key
                e.g. {'/path/to/P1.jpg': 'dpsh', '/path/to/IMG_001.jpg': 'site'}

        Returns:
            dict mapping category -> list of new paths of renamed files
        """
        result: dict[str, list[Path]] = {}

        # Count how many of each category we already have (for numbering)
        existing_counts: dict[str, int] = {}
        status = self.scan()
        for category, files in status.classified.items():
            existing_counts[category] = len(files)

        for photo_path_str, category in classifications.items():
            photo_path = Path(photo_path_str)

            if not photo_path.exists():
                logger.warning(f"Photo not found: {photo_path}")
                continue

            if category not in PHOTO_SLUGS:
                logger.warning(f"Unknown category '{category}' for {photo_path}")
                continue

            slug = PHOTO_SLUGS[category]
            subdir = PHOTO_CATEGORY_DIRS[category]
            target_dir = self.foto_dir / subdir if subdir else self.foto_dir
            target_dir.mkdir(parents=True, exist_ok=True)

            # Determine filename with numbering
            count = existing_counts.get(category, 0) + 1
            existing_counts[category] = count

            ext = photo_path.suffix.lower()
            if category == 'site':
                # Site photos get numbered: vista_general_1.jpg, vista_general_2.jpg
                new_name = f"{slug}_{count}{ext}"
            else:
                # Other categories: single file, no number unless duplicate
                if count == 1:
                    new_name = f"{slug}{ext}"
                else:
                    new_name = f"{slug}_{count}{ext}"

            new_path = target_dir / new_name

            # Avoid overwriting existing files
            if new_path.exists():
                stem = new_path.stem
                suffix = new_path.suffix
                n = 2
                while (target_dir / f"{stem}_{n}{suffix}").exists():
                    n += 1
                new_path = target_dir / f"{stem}_{n}{suffix}"
                logger.warning(f"Target already existed, using {new_path.name}")

            # Copy (not move) to preserve originals
            shutil.copy2(str(photo_path), str(new_path))
            result.setdefault(category, []).append(new_path)
            logger.info(f"Classified: {photo_path.name} -> {new_path.name} ({category})")

        return result

    def _all_photo_dirs(self) -> list[Path]:
        """All directories that might contain photos."""
        dirs = [self.foto_dir]
        for subdir_name in ('DPSH', 'SONDEIG'):
            subdir = self.foto_dir / subdir_name
            if subdir.exists():
                dirs.append(subdir)
        return dirs

    def summary(self) -> str:
        """Human-readable summary of photo status."""
        status = self.scan()
        lines = ["Estat de les fotografies:"]

        for category, slug in PHOTO_SLUGS.items():
            files = status.classified[category]
            if files:
                names = ", ".join(f.name for f in files)
                lines.append(f"  {category} ({slug}): {len(files)} foto(s) - {names}")
            else:
                lines.append(f"  {category} ({slug}): CAP FOTO")

        if status.unclassified:
            lines.append(f"\n  Fotos sense classificar: {len(status.unclassified)}")
            for f in status.unclassified:
                # Show relative path from FOTOGRAFIES/
                try:
                    rel = f.relative_to(self.foto_dir)
                except ValueError:
                    rel = f.name
                lines.append(f"    - {rel}")

        if status.all_covered:
            lines.append("\n  Totes les categories cobertes.")
        else:
            lines.append(f"\n  Categories pendents: {', '.join(status.missing_categories)}")

        return "\n".join(lines)
