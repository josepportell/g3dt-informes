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
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Image widths for different types (in millimeters)
IMAGE_WIDTH_LOCATION = 150  # Orthophoto / location map
IMAGE_WIDTH_GEOLOGICAL = 150  # Geological map
IMAGE_WIDTH_PHOTO = 120  # Field photos (DPSH, sondeig, site)
IMAGE_WIDTH_SPT_CULLERA = 150  # SPT spoon diagram (full-width, same as other figures)
IMAGE_WIDTH_SIDE_BY_SIDE = 70   # Each image in 2-column layout (mm)
IMAGE_WIDTH_MAIN_PLAN = 150     # Big architect plan crop (full-width)

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
            'site': foto_dir,  # root of FOTOGRAFIES/ for site views
            'dpsh': foto_dir / 'DPSH',
            'sondeig': foto_dir / 'SONDEIG',
            'materials': foto_dir / 'SONDEIG',  # materials detail often in SONDEIG/
        }
        # Max fallback images per category (site needs 2 for side-by-side)
        fallback_max: dict[str, int] = {
            'site': 2, 'dpsh': 1, 'sondeig': 1, 'materials': 1,
        }

        for key, slug in PHOTO_SLUGS.items():
            matches = _find_by_slug(slug, search_dirs[key])
            if matches:
                result[key] = matches
            else:
                # Fallback: first image(s) in directory (legacy behavior)
                # Prefer numbered photos (P1.jpg, P2.jpg) over WhatsApp/random names
                fallback_dir = fallback_subdirs[key]
                if fallback_dir and fallback_dir.exists():
                    fallback = _glob_photos(fallback_dir)
                    if fallback:
                        # Exclude photos already claimed by other categories
                        claimed = {str(p) for cat_photos in result.values() for p in cat_photos}
                        available = [f for f in fallback if str(f) not in claimed]
                        if not available:
                            available = fallback
                        numbered = [f for f in available if re.match(r'^[Pp]\d', f.name)]
                        chosen = numbered if numbered else available
                        # Materials: pick last photo (core box taken last in field)
                        if key == 'materials':
                            chosen = chosen[-1:]
                        n = fallback_max.get(key, 1)
                        result[key] = chosen[:n]
                        logger.warning(
                            f"No '{slug}*' photo found for '{key}', "
                            f"using first {n} file(s) in {fallback_dir.name}/. "
                            f"Consider renaming to {slug}_1{chosen[0].suffix}"
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

    def _load_file_mapping(self) -> dict | None:
        """Load file roles from file_mapping.json if it exists."""
        mapping_path = self.project_path / 'file_mapping.json'
        if not mapping_path.exists():
            return None
        try:
            import json
            return json.loads(mapping_path.read_text()).get('roles', {})
        except Exception as e:
            logger.warning(f"Could not read file_mapping.json: {e}")
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

    def _render_pdf_region(self, pdf_path: Path, output_path: Path, clip_rect: tuple, dpi: int = 200) -> Path | None:
        """Render a clipped region of the first page of a PDF to JPEG."""
        try:
            import fitz
            doc = fitz.open(str(pdf_path))
            page = doc[0]
            pix = page.get_pixmap(dpi=dpi, clip=fitz.Rect(*clip_rect))
            pix.save(str(output_path))
            doc.close()
            logger.info(f"Rendered PDF region to image: {pdf_path.name} clip={clip_rect} -> {output_path.name}")
            return output_path
        except Exception as e:
            logger.warning(f"Failed to render PDF region {pdf_path.name}: {e}")
            return None

    def _find_architect_plan_with_points(self) -> tuple[Path | None, dict | None]:
        """
        Find 'A.01 amb punts.pdf' with clip coordinates.

        Priority 1: file_mapping.json role architect_plan_with_points with clip_regions
        Priority 2: Glob for A.01*punts*.pdf (no predefined clips)

        Returns (pdf_path, clip_regions_dict) or (None, None).
        """
        roles = self._load_file_mapping()

        # Priority 1: file_mapping.json
        if roles and 'architect_plan_with_points' in roles:
            role = roles['architect_plan_with_points']
            candidate = self.project_path / role['path']
            if candidate.exists():
                clip_regions = role.get('clip_regions')
                logger.info(f"Found architect plan with points: {candidate.name} (clip_regions={'yes' if clip_regions else 'no'})")
                return candidate, clip_regions

        # Priority 2: Glob fallback
        for pattern in ['A.01*punts*.pdf', 'A.*punts*.pdf']:
            matches = sorted(self.project_path.glob(pattern))
            if matches:
                logger.info(f"Found architect plan with points via glob: {matches[0].name} (no clip_regions)")
                return matches[0], None

        return None, None

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
            from .icgc_geology import get_geological_map_with_terrain, get_geological_map_image, ICGCError
            composite_path = self._cache_dir / f"geological_composite_{utm_x:.0f}_{utm_y:.0f}.png"
            if not composite_path.exists():
                get_geological_map_with_terrain(utm_x, utm_y, composite_path)
            result['geological_map'] = composite_path
            logger.info(f"Geological composite map ready: {composite_path}")
        except Exception as e:
            logger.warning(f"Composite geological map failed, falling back to opaque: {e}")
            try:
                geo_path = self._cache_dir / f"geological_{utm_x:.0f}_{utm_y:.0f}.jpg"
                if not geo_path.exists():
                    get_geological_map_image(utm_x, utm_y, geo_path)
                result['geological_map'] = geo_path
                logger.info(f"Geological map (opaque fallback) ready: {geo_path}")
            except Exception as e2:
                logger.warning(f"Failed to download geological map: {e2}")

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

        # 3. Architect plan crops (replaces orthophoto for location figures)
        #    cadastre + aerea: from "amb punts" (WITH dots — shows investigation points)
        #    main_plan: from A.01.pdf (WITHOUT dots — shows "punt de partida")
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        roles = self._load_file_mapping()
        has_plan_crops = False

        # 3a. Cadastre + aerea from architect_plan_with_points (with dots)
        points_pdf, points_clips = self._find_architect_plan_with_points()
        if points_pdf and points_clips:
            for region_name, var_name, width in [
                ('cadastre', 'fig_cadastre_image', IMAGE_WIDTH_SIDE_BY_SIDE),
                ('aerea', 'fig_aerea_image', IMAGE_WIDTH_SIDE_BY_SIDE),
            ]:
                if region_name in points_clips:
                    clip_rect = points_clips[region_name]
                    if not (isinstance(clip_rect, (list, tuple)) and len(clip_rect) == 4):
                        logger.warning(f"Invalid clip_rect for {region_name}: {clip_rect}")
                        continue
                    cached = self._cache_dir / f"{region_name}_{points_pdf.stem}.jpg"
                    if not cached.exists():
                        self._render_pdf_region(points_pdf, cached, tuple(clip_rect))
                    if cached.exists():
                        context[var_name] = InlineImage(
                            self.tpl, str(cached), width=Mm(width)
                        )
                        has_plan_crops = True
        context.setdefault('fig_cadastre_image', PLACEHOLDER_TEXT)
        context.setdefault('fig_aerea_image', PLACEHOLDER_TEXT)

        # 3b. Main plan from architect_plan (WITHOUT dots — punt de partida)
        base_plan_pdf = None
        base_clip_regions = None
        if roles and 'architect_plan' in roles:
            role = roles['architect_plan']
            candidate = self.project_path / role['path']
            if candidate.exists():
                base_plan_pdf = candidate
                base_clip_regions = role.get('clip_regions')

        if base_plan_pdf and base_clip_regions and 'main_plan' in base_clip_regions:
            clip_rect = base_clip_regions['main_plan']
            if isinstance(clip_rect, (list, tuple)) and len(clip_rect) == 4:
                cached = self._cache_dir / f"main_plan_{base_plan_pdf.stem}.jpg"
                if not cached.exists():
                    self._render_pdf_region(base_plan_pdf, cached, tuple(clip_rect))
                if cached.exists():
                    context['fig_main_plan_image'] = InlineImage(
                        self.tpl, str(cached), width=Mm(IMAGE_WIDTH_MAIN_PLAN)
                    )
                    has_plan_crops = True
        elif base_plan_pdf:
            # Has A.01.pdf but no clip_regions — render full page
            cached = self._cache_dir / f"planol_{base_plan_pdf.stem}.jpg"
            if not cached.exists():
                self._render_pdf_to_image(base_plan_pdf, cached)
            if cached.exists():
                context['fig_main_plan_image'] = InlineImage(
                    self.tpl, str(cached), width=Mm(IMAGE_WIDTH_MAIN_PLAN)
                )
        else:
            # Fallback: no base plan, try "amb punts" or glob
            fallback_pdf = points_pdf or self._find_project_pdf(['A.01.pdf', 'A.*.pdf'])
            if fallback_pdf:
                cached = self._cache_dir / f"planol_{fallback_pdf.stem}.jpg"
                if not cached.exists():
                    self._render_pdf_to_image(fallback_pdf, cached)
                if cached.exists():
                    context['fig_main_plan_image'] = InlineImage(
                        self.tpl, str(cached), width=Mm(IMAGE_WIDTH_MAIN_PLAN)
                    )
        context.setdefault('fig_main_plan_image', PLACEHOLDER_TEXT)

        context['has_plan_crops'] = has_plan_crops

        # Backward-compat aliases
        context['fig_location_image'] = context.get('fig_cadastre_image', PLACEHOLDER_TEXT)
        context['fig_building_image'] = context.get('fig_main_plan_image', PLACEHOLDER_TEXT)

        # ICGC images: geological map + orthophoto as aerea fallback
        icgc_images = self._download_icgc_images()
        if 'geological_map' in icgc_images:
            context['fig_geological_image'] = InlineImage(
                self.tpl, str(icgc_images['geological_map']), width=Mm(IMAGE_WIDTH_GEOLOGICAL)
            )
        else:
            context['fig_geological_image'] = PLACEHOLDER_TEXT

        # Use ICGC orthophoto as fallback for aerea when no clip_regions
        if context.get('fig_aerea_image') == PLACEHOLDER_TEXT and 'orthophoto' in icgc_images:
            context['fig_aerea_image'] = InlineImage(
                self.tpl, str(icgc_images['orthophoto']), width=Mm(IMAGE_WIDTH_SIDE_BY_SIDE)
            )
            context['fig_location_image'] = context['fig_aerea_image']

        # Correlation section: file_mapping -> fallback glob
        tall_pdf = None
        if roles and 'correlation_section' in roles:
            candidate = self.project_path / roles['correlation_section']['path']
            if candidate.exists():
                tall_pdf = candidate
        if tall_pdf is None:
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
