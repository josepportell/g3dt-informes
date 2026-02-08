#!/usr/bin/env python3
"""
Image Manager for G3DT Report Generation

Discovers field photos and downloads ICGC images, then builds
InlineImage context for docxtpl template rendering.

Usage:
    from automation.image_manager import ImageManager

    # Inside report_generator.py, after creating DocxTemplate:
    img_mgr = ImageManager(project_path, report_data, tpl)
    image_ctx = img_mgr.build_context()
    context.update(image_ctx)

Author: Eficients.cat
Date: 2026-02-07
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Image widths for different types (in millimeters)
IMAGE_WIDTH_LOCATION = 150  # Orthophoto / location map
IMAGE_WIDTH_GEOLOGICAL = 150  # Geological map
IMAGE_WIDTH_PHOTO = 120  # Field photos (DPSH, sondeig, site)
IMAGE_WIDTH_SPT_CULLERA = 100  # SPT spoon diagram (smaller, technical)

PLACEHOLDER_TEXT = "[Imatge pendent]"

# Photo slug mapping for named discovery
PHOTO_SLUGS = {
    'site': 'vista_general',
    'dpsh': 'maquina_dpsh',
    'sondeig': 'maquina_sondeig',
    'materials': 'detall_materials',
}

# Directory within FOTOGRAFIES/ where each category's photos should live
PHOTO_CATEGORY_DIRS = {
    'site': '',           # root of FOTOGRAFIES/
    'dpsh': 'DPSH',       # FOTOGRAFIES/DPSH/
    'sondeig': 'SONDEIG', # FOTOGRAFIES/SONDEIG/
    'materials': '',      # root of FOTOGRAFIES/
}


class ImageManager:
    """
    Manages image discovery and InlineImage context building.

    Handles 4 image types:
    1. Cullera SPT (static, same for all projects)
    2. Field photos (from FOTOGRAFIES/ subfolders)
    3. Orthophoto ICGC (aerial location view)
    4. Geological map ICGC
    """

    def __init__(
        self,
        project_path: Path,
        report_data: Any,  # ReportData object
        tpl: Any,  # DocxTemplate object (needed for InlineImage)
    ):
        self.project_path = Path(project_path)
        self.report_data = report_data
        self.tpl = tpl
        # G3DT root is 2 levels up from automation/ (or find via templates/)
        self._g3dt_root = Path(__file__).parent.parent
        # Cache dir for downloaded ICGC images
        self._cache_dir = Path.home() / ".g3dt" / "cache" / "images"

    def discover_photos(self) -> dict[str, list[Path]]:
        """
        Scan FOTOGRAFIES/ for field photos using slug-based naming convention.

        Naming convention (case-insensitive prefix match):
        - vista_general*.jpg → Site view photos (1-2)
        - maquina_dpsh*.jpg → DPSH machine photo
        - maquina_sondeig*.jpg → Sondeig machine photo
        - detall_materials*.jpg → Materials detail photo

        Falls back to first file in subfolder if slug not found.
        """
        foto_dir = self.project_path / 'FOTOGRAFIES'
        result: dict[str, list[Path]] = {
            'site': [], 'dpsh': [], 'sondeig': [], 'materials': [],
        }

        if not foto_dir.exists():
            logger.warning(f"FOTOGRAFIES/ folder not found at {foto_dir}")
            return result

        image_exts = {'.jpg', '.jpeg', '.png'}

        def _glob_photos(directory: Path) -> list[Path]:
            """Glob for image files, deduplicated for case-insensitive FS."""
            seen: set[str] = set()
            photos: list[Path] = []
            for ext in ('*.jpg', '*.jpeg', '*.png', '*.JPG', '*.JPEG', '*.PNG'):
                for f in sorted(directory.glob(ext)):
                    key = str(f).lower()
                    if f.is_file() and f.name != 'Thumbs.db' and key not in seen:
                        seen.add(key)
                        photos.append(f)
            return photos

        def _find_by_slug(slug: str, directories: list[Path]) -> list[Path]:
            """Search directories for files matching slug prefix (case-insensitive)."""
            for directory in directories:
                if not directory.exists():
                    continue
                matches = []
                for f in sorted(directory.glob(f'{slug}*')):
                    if (f.is_file()
                            and f.name != 'Thumbs.db'
                            and f.suffix.lower() in image_exts):
                        matches.append(f)
                # Also check uppercase slug variant
                slug_upper = slug.upper()
                if slug_upper != slug:
                    for f in sorted(directory.glob(f'{slug_upper}*')):
                        if (f.is_file()
                                and f.name != 'Thumbs.db'
                                and f.suffix.lower() in image_exts
                                and f not in matches):
                            matches.append(f)
                if matches:
                    return sorted(matches, key=lambda p: p.name.lower())
            return []

        # Search locations per key (primary, then fallback)
        search_dirs: dict[str, list[Path]] = {}
        for key, subdir in PHOTO_CATEGORY_DIRS.items():
            primary = foto_dir / subdir if subdir else foto_dir
            if subdir:
                search_dirs[key] = [primary, foto_dir]
            else:
                search_dirs[key] = [primary]

        # Fallback subdirectories (used when slug not found)
        fallback_subdirs: dict[str, Path | None] = {
            'site': None,  # root, no subfolder fallback
            'dpsh': foto_dir / 'DPSH',
            'sondeig': foto_dir / 'SONDEIG',
            'materials': None,
        }

        for key, slug in PHOTO_SLUGS.items():
            matches = _find_by_slug(slug, search_dirs[key])
            if matches:
                result[key] = matches
            else:
                # Fallback: first image in subfolder (legacy behavior)
                fallback_dir = fallback_subdirs[key]
                if fallback_dir and fallback_dir.exists():
                    fallback = _glob_photos(fallback_dir)
                    if fallback:
                        result[key] = fallback[:1]
                        logger.warning(
                            f"No '{slug}*' photo found for '{key}', "
                            f"using first file in {fallback_dir.name}/. "
                            f"Consider renaming to {slug}_1{fallback[0].suffix}"
                        )

        logger.info(
            f"Discovered photos: site={len(result['site'])}, "
            f"dpsh={len(result['dpsh'])}, sondeig={len(result['sondeig'])}, "
            f"materials={len(result['materials'])}"
        )
        return result

    def _get_cullera_spt_path(self) -> Path | None:
        """Get path to static cullera SPT image."""
        path = self._g3dt_root / 'templates' / 'images' / 'cullera_spt.jpg'
        if path.exists():
            return path
        # Also try .png
        path_png = path.with_suffix('.png')
        if path_png.exists():
            return path_png
        logger.warning(f"Cullera SPT image not found at {path}")
        return None

    def _find_project_pdf(self, patterns: list[str]) -> Path | None:
        """Find first matching PDF in project folder."""
        for pattern in patterns:
            matches = sorted(self.project_path.glob(pattern))
            if matches:
                return matches[0]
        return None

    def _render_pdf_to_image(self, pdf_path: Path, output_path: Path, dpi: int = 150) -> Path | None:
        """Render first page of PDF to JPEG using pymupdf."""
        try:
            import fitz
            doc = fitz.open(str(pdf_path))
            page = doc[0]
            pix = page.get_pixmap(dpi=dpi)
            pix.save(str(output_path))
            doc.close()
            logger.info(f"Rendered PDF to image: {pdf_path.name} -> {output_path.name}")
            return output_path
        except Exception as e:
            logger.warning(f"Failed to render PDF {pdf_path.name}: {e}")
            return None

    def _download_icgc_images(self) -> dict[str, Path]:
        """
        Download orthophoto + geological map if UTM coords available.

        Returns dict with keys 'orthophoto' and/or 'geological_map',
        values are paths to downloaded images. Missing keys = download failed.
        """
        result: dict[str, Path] = {}

        utm_x = getattr(self.report_data, 'utm_x', None)
        utm_y = getattr(self.report_data, 'utm_y', None)

        if utm_x is None or utm_y is None:
            logger.warning("No UTM coordinates available, skipping ICGC image download")
            return result

        self._cache_dir.mkdir(parents=True, exist_ok=True)

        try:
            from .icgc_geology import get_orthophoto_image, ICGCError
            ortho_path = self._cache_dir / f"ortho_{utm_x:.0f}_{utm_y:.0f}.jpg"
            if not ortho_path.exists():
                get_orthophoto_image(utm_x, utm_y, ortho_path)
            result['orthophoto'] = ortho_path
            logger.info(f"Orthophoto ready: {ortho_path}")
        except Exception as e:
            logger.warning(f"Failed to download orthophoto: {e}")

        try:
            from .icgc_geology import get_geological_map_image, ICGCError
            geo_path = self._cache_dir / f"geological_{utm_x:.0f}_{utm_y:.0f}.jpg"
            if not geo_path.exists():
                get_geological_map_image(utm_x, utm_y, geo_path)
            result['geological_map'] = geo_path
            logger.info(f"Geological map ready: {geo_path}")
        except Exception as e:
            logger.warning(f"Failed to download geological map: {e}")

        return result

    def build_context(self) -> dict[str, Any]:
        """
        Build template context with InlineImage objects or placeholder strings.

        Returns dict to be merged into the main template context.
        Keys match template variables: fig_location_image, fig_geological_image,
        fig_spt_cullera_image, photo_site_image_1, photo_site_image_2,
        photo_dpsh_image, photo_sondeig_image
        """
        try:
            from docxtpl import InlineImage
            from docx.shared import Mm
        except ImportError:
            logger.error("docxtpl not installed, cannot create InlineImage objects")
            return {}

        context: dict[str, Any] = {}

        # 1. Cullera SPT (static)
        cullera_path = self._get_cullera_spt_path()
        if cullera_path:
            context['fig_spt_cullera_image'] = InlineImage(
                self.tpl, str(cullera_path), width=Mm(IMAGE_WIDTH_SPT_CULLERA)
            )
        else:
            context['fig_spt_cullera_image'] = PLACEHOLDER_TEXT

        # 2. Field photos
        photos = self.discover_photos()

        # Site photos (up to 2)
        if photos['site']:
            context['photo_site_image_1'] = InlineImage(
                self.tpl, str(photos['site'][0]), width=Mm(IMAGE_WIDTH_PHOTO)
            )
        else:
            context['photo_site_image_1'] = PLACEHOLDER_TEXT

        if len(photos['site']) >= 2:
            context['photo_site_image_2'] = InlineImage(
                self.tpl, str(photos['site'][1]), width=Mm(IMAGE_WIDTH_PHOTO)
            )
        else:
            context['photo_site_image_2'] = PLACEHOLDER_TEXT

        # DPSH photo (first found)
        if photos['dpsh']:
            context['photo_dpsh_image'] = InlineImage(
                self.tpl, str(photos['dpsh'][0]), width=Mm(IMAGE_WIDTH_PHOTO)
            )
        else:
            context['photo_dpsh_image'] = PLACEHOLDER_TEXT

        # Sondeig photo (first found)
        if photos['sondeig']:
            context['photo_sondeig_image'] = InlineImage(
                self.tpl, str(photos['sondeig'][0]), width=Mm(IMAGE_WIDTH_PHOTO)
            )
        else:
            context['photo_sondeig_image'] = PLACEHOLDER_TEXT

        # Materials detail photo
        if photos.get('materials'):
            context['photo_materials_image'] = InlineImage(
                self.tpl, str(photos['materials'][0]), width=Mm(IMAGE_WIDTH_PHOTO)
            )
        else:
            context['photo_materials_image'] = PLACEHOLDER_TEXT

        # 3. ICGC images (orthophoto + geological map)
        icgc_images = self._download_icgc_images()

        if 'orthophoto' in icgc_images:
            context['fig_location_image'] = InlineImage(
                self.tpl, str(icgc_images['orthophoto']), width=Mm(IMAGE_WIDTH_LOCATION)
            )
        else:
            context['fig_location_image'] = PLACEHOLDER_TEXT

        if 'geological_map' in icgc_images:
            context['fig_geological_image'] = InlineImage(
                self.tpl, str(icgc_images['geological_map']), width=Mm(IMAGE_WIDTH_GEOLOGICAL)
            )
        else:
            context['fig_geological_image'] = PLACEHOLDER_TEXT

        # 4. PDF-rendered images (building plan + correlation cross-section)
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        # Building plan from A.01.pdf
        planol_pdf = self._find_project_pdf(['A.01.pdf', 'A.*.pdf'])
        if planol_pdf:
            cached = self._cache_dir / f"planol_{planol_pdf.stem}.jpg"
            if not cached.exists():
                self._render_pdf_to_image(planol_pdf, cached)
            if cached.exists():
                context['fig_building_image'] = InlineImage(
                    self.tpl, str(cached), width=Mm(IMAGE_WIDTH_LOCATION)
                )
        context.setdefault('fig_building_image', PLACEHOLDER_TEXT)

        # Correlation cross-section from tall.pdf
        tall_pdf = self._find_project_pdf(['tall.pdf', 'tall*.pdf'])
        if tall_pdf:
            cached = self._cache_dir / f"tall_{tall_pdf.stem}.jpg"
            if not cached.exists():
                self._render_pdf_to_image(tall_pdf, cached)
            if cached.exists():
                context['fig_correlation_image'] = InlineImage(
                    self.tpl, str(cached), width=Mm(IMAGE_WIDTH_LOCATION)
                )
        context.setdefault('fig_correlation_image', PLACEHOLDER_TEXT)

        # Log summary
        num_images = sum(1 for v in context.values() if not isinstance(v, str))
        num_placeholders = sum(1 for v in context.values() if isinstance(v, str))
        logger.info(f"Image context built: {num_images} images, {num_placeholders} placeholders")

        return context
