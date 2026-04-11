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
IMAGE_HEIGHT_SIDE_BY_SIDE = 52  # 4:3 landscape aspect ratio (70 * 3/4 ≈ 52mm)
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

# SmartScan role → photo category mapping (Phase 6: role-based image placement)
# When SmartScan classifies an image with one of these roles, use it for the
# corresponding report photo slot — regardless of filename or folder location.
ROLE_TO_PHOTO_CATEGORY = {
    'photo_site_overview': 'site',
    'photo_dpsh_equipment': 'dpsh',
    'photo_sondeig_equipment': 'sondeig',
    'photo_spt_sample': 'materials',
    'photo_test_point': 'site',  # fallback: test point photos as site views
    'field_photo': 'site',  # generic WhatsApp field photos as site views
}

# SmartScan role → figure context variable mapping
# These roles provide images for specific figure slots in the report.
ROLE_TO_FIGURE_VAR = {
    'figure_situation_map': 'fig_cadastre_image',
    'figure_geological_map': 'fig_geological_image',
    'figure_test_points': 'fig_test_points_image',
    'figure_correlation': 'fig_correlation_image',
}


# ──────────────────────────────────────────────────────────────
# AI Photo Selection prompt (Phase 7)
# ──────────────────────────────────────────────────────────────

PHOTO_SELECTION_PROMPT = """You are selecting field photographs for a geotechnical report.

The report needs these photos in specific slots:

SLOT 1 — "site_1": General view of the construction site or plot. Wide angle showing
  the terrain, surroundings, access road. The reader should understand WHERE the project is.
SLOT 2 — "site_2": Second site overview from a different angle or showing a different aspect.
  Together with site_1, these go side-by-side to give a complete picture of the site.
SLOT 3 — "dpsh": The DPSH penetrometer machine/equipment during testing. Shows the rig,
  the tube going into the ground, or the hammer mechanism.
SLOT 4 — "sondeig": The borehole/drilling (sondeig) machine during testing. Shows the
  rotary rig, drill rods, or the drilling process. ONLY if borehole testing was performed.
SLOT 5 — "materials": Close-up of soil samples, SPT spoon with soil, core boxes, or
  material detail. Shows what the soil/rock looks like.

Below are numbered thumbnail images from the project's field photos folder.
For each slot, pick the BEST image number. If no image fits a slot, use null.
An image can only be assigned to ONE slot (no duplicates).

Respond in JSON:
{"site_1": <number>, "site_2": <number>, "dpsh": <number>, "sondeig": <number|null>, "materials": <number>}
"""


class ImageManager:
    """
    Manages image discovery and InlineImage context building.

    Handles 4 image types:
    1. Cullera SPT (static, same for all projects)
    2. Field photos (from FOTOGRAFIES/ subfolders)
    3. Orthophoto ICGC (aerial location view)
    4. Geological map ICGC

    Phase 7: AI photo selection — Claude/Groq sees all photos and picks best per slot.
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
        Discover field photos using SmartScan roles first, then slug-based fallback.

        Priority chain:
        1. SmartScan roles (Phase 6): if file_mapping.json has photo_dpsh_equipment,
           photo_site_overview, etc., use those images directly
        2. Slug-based naming: vista_general*.jpg, maquina_dpsh*.jpg, etc.
        3. First file in subfolder (legacy fallback)
        """
        result: dict[str, list[Path]] = {
            'site': [], 'dpsh': [], 'sondeig': [], 'materials': [],
        }

        # ── Priority 1: SmartScan role-based discovery (seeds results) ──
        roles = self._load_file_mapping()
        if roles:
            for role_name, category in ROLE_TO_PHOTO_CATEGORY.items():
                if role_name in roles:
                    photo_path = self.project_path / roles[role_name]['path']
                    if photo_path.exists() and photo_path not in result[category]:
                        result[category].append(photo_path)
                        logger.info(f"Photo from SmartScan role: {role_name} → {category} ({photo_path.name})")

        # ── Priority 1b: SmartScan role_files (ALL photos per role) ──
        role_files = self._load_role_files()
        if role_files:
            for role_name, category in ROLE_TO_PHOTO_CATEGORY.items():
                if role_name in role_files:
                    for rf in role_files[role_name]:
                        photo_path = self.project_path / rf['path']
                        if photo_path.exists() and photo_path not in result[category]:
                            result[category].append(photo_path)
                            logger.info(f"Photo from role_files: {role_name} → {category} ({photo_path.name})")

        # Always continue with slug-based search to find ADDITIONAL photos.
        # The report needs multiple photos per category (e.g., 2 site photos
        # side-by-side). SmartScan roles give one winner per role — slugs supplement.

        # ── Priority 2+3: Slug-based + fallback (supplements role results) ──
        foto_dir = self._find_photos_dir()
        if not foto_dir:
            if all(result.values()):
                return result  # roles found enough, no photos dir needed
            logger.warning("No photos directory found")
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
            if result[key]:
                # Already seeded by SmartScan roles — skip slug search for this category
                continue
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

    def _load_user_photo_selection(self) -> dict[str, list[Path]] | None:
        """Load user-curated photo selection from photo_selection.json.

        Returns dict matching discover_photos() format if a user selection
        exists (source == "user"), or None to fall through to AI/pattern.
        """
        cache_path = self.project_path / 'validation' / 'photo_selection.json'
        if not cache_path.exists():
            return None

        try:
            import json
            data = json.loads(cache_path.read_text(encoding='utf-8'))
        except Exception:
            return None

        if data.get('source') != 'user':
            return None

        result: dict[str, list[Path]] = {
            'site': [], 'dpsh': [], 'sondeig': [], 'materials': [],
        }

        slot_to_category = {
            'site_1': 'site', 'site_2': 'site',
            'dpsh': 'dpsh', 'sondeig': 'sondeig', 'materials': 'materials',
        }

        for slot, category in slot_to_category.items():
            rel_path = data.get(slot)
            if not rel_path:
                continue
            full_path = self.project_path / rel_path
            if not str(full_path.resolve()).startswith(str(self.project_path.resolve())):
                continue
            photo = full_path.resolve()
            if photo.is_file() and photo not in result[category]:
                result[category].append(photo)

        if any(result.values()):
            logger.info(
                "User photo selection loaded: %s",
                {k: [p.name for p in v] for k, v in result.items() if v},
            )
            return result

        return None

    def select_photos_ai(self) -> dict[str, list[Path]] | None:
        """Phase 7: AI-based photo selection.

        Gathers all candidate photos, creates a numbered thumbnail grid,
        and asks Claude Code (or Groq fallback) to pick the best photo
        for each report slot.

        Returns dict matching discover_photos() format, or None if AI
        selection not available (caller falls back to pattern matching).
        """
        foto_dir = self._find_photos_dir()
        if not foto_dir:
            return None

        # Gather ALL image files recursively from photos dir
        image_exts = {'.jpg', '.jpeg', '.png'}
        candidates: list[Path] = []
        for f in sorted(foto_dir.rglob('*')):
            if f.is_file() and f.suffix.lower() in image_exts and f.name != 'Thumbs.db':
                candidates.append(f)

        if len(candidates) < 2:
            return None  # Not enough photos to warrant AI selection

        # Check cache — never overwrite user-curated selection
        cache_path = self.project_path / 'validation' / 'photo_selection.json'
        if cache_path.exists():
            try:
                import json
                cached = json.loads(cache_path.read_text(encoding='utf-8'))
                if cached.get('source') == 'user':
                    logger.info("User photo selection exists, skipping AI selection")
                    return None
                selection = self._parse_ai_selection(cached, candidates)
                if selection:
                    logger.info("Photo selection loaded from cache (%d slots filled)",
                                sum(1 for v in selection.values() if v))
                    return selection
            except Exception:
                pass

        # Build thumbnail grid
        grid_bytes = self._build_thumbnail_grid(candidates)
        if not grid_bytes:
            return None

        # Build prompt with numbered legend
        legend = "\n".join(f"  {i+1}. {c.name} ({c.parent.name}/)" for i, c in enumerate(candidates))
        prompt = PHOTO_SELECTION_PROMPT + f"\n\nAvailable photos ({len(candidates)} total):\n{legend}"

        # Try Claude Code CLI first (we ARE the runtime)
        result = self._call_claude_for_photos(prompt, grid_bytes)

        # Fallback: Groq Llama 4 Scout
        if result is None:
            result = self._call_groq_for_photos(prompt, grid_bytes)

        if result is None:
            logger.info("AI photo selection not available, falling back to pattern matching")
            return None

        # Cache result
        try:
            import json
            (self.project_path / 'validation').mkdir(exist_ok=True)
            cache_path.write_text(json.dumps(result, indent=2), encoding='utf-8')
        except Exception:
            pass

        selection = self._parse_ai_selection(result, candidates)
        if selection:
            logger.info("AI photo selection: %s",
                        {k: [p.name for p in v] for k, v in selection.items() if v})
        return selection

    def _build_thumbnail_grid(self, candidates: list[Path], thumb_size: int = 200) -> bytes | None:
        """Create a grid image with numbered thumbnails of all candidate photos."""
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            logger.warning("Pillow not available for thumbnail grid")
            return None

        try:
            n = len(candidates)
            cols = min(4, n)
            rows = (n + cols - 1) // cols
            cell_w = thumb_size + 10
            cell_h = thumb_size + 30  # extra space for number label
            grid_w = cols * cell_w + 10
            grid_h = rows * cell_h + 10

            grid = Image.new('RGB', (grid_w, grid_h), (255, 255, 255))
            draw = ImageDraw.Draw(grid)

            for idx, photo_path in enumerate(candidates):
                row, col = divmod(idx, cols)
                x = col * cell_w + 10
                y = row * cell_h + 25  # leave space for number at top

                try:
                    img = Image.open(str(photo_path))
                    img.thumbnail((thumb_size, thumb_size))
                    grid.paste(img, (x, y))
                    img.close()
                except Exception:
                    # Draw placeholder rectangle
                    draw.rectangle([x, y, x + thumb_size, y + thumb_size], outline='gray')

                # Draw number label
                draw.text((x + 2, y - 18), f"{idx + 1}", fill='black')

            import io
            buf = io.BytesIO()
            grid.save(buf, format='JPEG', quality=85)
            return buf.getvalue()

        except Exception as e:
            logger.warning("Failed to build thumbnail grid: %s", e)
            return None

    def _call_claude_for_photos(self, prompt: str, grid_bytes: bytes) -> dict | None:
        """Call Claude Code CLI with thumbnail grid for photo selection."""
        import base64
        import json
        import os
        import subprocess

        claude_path = os.getenv("G3DT_CLAUDE_PATH", "claude")

        # Write grid to temp file for Claude to read
        grid_path = self.project_path / 'validation' / '_photo_grid.jpg'
        grid_path.parent.mkdir(exist_ok=True)
        grid_path.write_bytes(grid_bytes)

        full_prompt = (
            f"Read the image at {grid_path} and analyze the numbered photos.\n\n"
            f"{prompt}\n\n"
            "Respond with ONLY the JSON object, nothing else."
        )

        try:
            result = subprocess.run(
                [claude_path, '-p', full_prompt, '--output-format', 'json'],
                capture_output=True, text=True, timeout=60,
                cwd='/tmp',  # avoid loading project CLAUDE.md
            )

            if result.returncode != 0:
                logger.warning("Claude CLI photo selection failed: %s", result.stderr[:200])
                return None

            # Parse Claude's response — extract JSON from output
            output = result.stdout.strip()
            try:
                # claude --output-format json wraps in {"result": "..."}
                wrapper = json.loads(output)
                text = wrapper.get('result', output)
            except json.JSONDecodeError:
                text = output

            json_start = text.find('{')
            json_end = text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                selection = json.loads(text[json_start:json_end])
                logger.info("Claude photo selection: %s", selection)
                return selection

        except FileNotFoundError:
            logger.debug("Claude CLI not found at %s", claude_path)
        except subprocess.TimeoutExpired:
            logger.warning("Claude CLI photo selection timed out")
        except Exception as e:
            logger.warning("Claude CLI photo selection error: %s", e)
        finally:
            try:
                grid_path.unlink(missing_ok=True)
            except Exception:
                pass

        return None

    def _call_groq_for_photos(self, prompt: str, grid_bytes: bytes) -> dict | None:
        """Fallback: call Groq Llama 4 Scout for photo selection."""
        import base64
        import json
        import os

        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            return None

        try:
            import httpx
        except ImportError:
            return None

        img_b64 = base64.b64encode(grid_bytes).decode('utf-8')

        payload = {
            "model": "meta-llama/llama-4-scout-17b-16e-instruct",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt + "\n\nRespond with ONLY the JSON object."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                ],
            }],
            "temperature": 0.0,
            "max_tokens": 256,
            "response_format": {"type": "json_object"},
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                )
            if resp.status_code != 200:
                logger.warning("Groq photo selection: HTTP %d", resp.status_code)
                return None

            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            result = json.loads(content)
            logger.info("Groq photo selection: %s", result)
            return result

        except Exception as e:
            logger.warning("Groq photo selection error: %s", e)
            return None

    def _parse_ai_selection(
        self, selection: dict, candidates: list[Path]
    ) -> dict[str, list[Path]] | None:
        """Parse AI selection JSON into discover_photos() format."""
        result: dict[str, list[Path]] = {
            'site': [], 'dpsh': [], 'sondeig': [], 'materials': [],
        }

        slot_to_category = {
            'site_1': 'site', 'site_2': 'site',
            'dpsh': 'dpsh', 'sondeig': 'sondeig', 'materials': 'materials',
        }

        for slot, category in slot_to_category.items():
            idx = selection.get(slot)
            if idx is None:
                continue
            try:
                idx = int(idx) - 1  # 1-indexed to 0-indexed
                if 0 <= idx < len(candidates):
                    photo = candidates[idx]
                    if photo not in result[category]:
                        result[category].append(photo)
            except (ValueError, TypeError):
                continue

        # Only return if AI actually selected something
        if any(result.values()):
            return result
        return None

    def _find_photos_dir(self) -> Path | None:
        """Find the photos directory using SmartScan role or common names."""
        # Priority 1: SmartScan photos_dir role
        roles = self._load_file_mapping()
        if roles and 'photos_dir' in roles:
            candidate = self.project_path / roles['photos_dir']['path']
            if candidate.exists() and candidate.is_dir():
                return candidate

        # Priority 2: common directory names
        for name in ['FOTOGRAFIES', 'FOTOS DE CAMP + PLANOL PUNTS', 'FOTOGRAFÍAS']:
            candidate = self.project_path / name
            if candidate.exists() and candidate.is_dir():
                return candidate

        # Priority 3: glob for FOTOS*
        for d in sorted(self.project_path.iterdir()):
            if d.is_dir() and d.name.upper().startswith('FOTOS'):
                return d

        return None

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

    def _load_role_files(self) -> dict | None:
        """Load role_files from file_mapping.json if available.

        Returns dict mapping role_name -> list of {path, confidence, detection}.
        Returns None if file_mapping.json doesn't exist or has no role_files.
        """
        mapping_path = self.project_path / 'file_mapping.json'
        if not mapping_path.exists():
            return None
        try:
            import json
            return json.loads(mapping_path.read_text()).get('role_files')
        except Exception as e:
            logger.warning(f"Could not read role_files from file_mapping.json: {e}")
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

    def _find_situation_plan(self, roles: dict | None) -> Path | None:
        """Find situation plan PDF (plànol de situació) for cadastral map crop."""
        # Priority 1: file_mapping.json role
        if roles and 'situation_plan' in roles:
            candidate = self.project_path / roles['situation_plan']['path']
            if candidate.exists():
                return candidate
        # Priority 2: glob for common names
        for pattern in ['pl*situaci*.pdf', '*planol*situacio*.pdf', '*plànol*situació*.pdf']:
            matches = sorted(self.project_path.glob(pattern))
            if matches:
                return matches[0]
        # Priority 3: PDF/ANNEXES/ subfolder
        for annexes in [self.project_path / 'PDF' / 'ANNEXES', self.project_path / 'ANNEXES']:
            for pattern in ['*situaci*.pdf', '*situació*.pdf']:
                matches = sorted(annexes.glob(pattern))
                if matches:
                    return matches[0]
        return None

    def _render_situation_plan_left(self, pdf_path: Path, output_path: Path, dpi: int = 200) -> Path | None:
        """Render left ~38% of situation plan page (cadastral maps area)."""
        try:
            import fitz
            doc = fitz.open(str(pdf_path))
            page = doc[0]
            r = page.rect
            # Situation plans have cadastral maps on the left ~38% of the page
            left_clip = fitz.Rect(r.x0, r.y0, r.x0 + r.width * 0.38, r.y1)
            pix = page.get_pixmap(dpi=dpi, clip=left_clip)
            pix.save(str(output_path))
            doc.close()
            logger.info(f"Rendered situation plan left crop: {pdf_path.name} -> {output_path.name}")
            return output_path
        except Exception as e:
            logger.warning(f"Failed to render situation plan crop {pdf_path.name}: {e}")
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

    def _get_planol_bbox_clip(self, pdf_path: Path) -> tuple[float, float, float, float] | None:
        """Read floor_plan_bbox from planol_extracted.json and convert to PyMuPDF clip rect.

        Returns (x0, y0, x1, y1) in PDF points, or None if not available.
        """
        planol_json = self.project_path / 'validation' / 'planol_extracted.json'
        if not planol_json.exists():
            return None

        try:
            import json
            data = json.loads(planol_json.read_text(encoding='utf-8'))
            bbox = data.get('floor_plan_bbox')
            if not bbox:
                return None

            confidence = bbox.get('confidence', 0)
            if confidence < 0.7:
                logger.info("floor_plan_bbox confidence %.2f < 0.7, using full page", confidence)
                return None

            top_pct = bbox.get('top_pct', 0)
            left_pct = bbox.get('left_pct', 0)
            bottom_pct = bbox.get('bottom_pct', 100)
            right_pct = bbox.get('right_pct', 100)

            # Convert percentages to absolute PDF coordinates
            import fitz
            doc = fitz.open(str(pdf_path))
            page = doc[0]
            r = page.rect
            doc.close()

            x0 = r.x0 + r.width * left_pct / 100
            y0 = r.y0 + r.height * top_pct / 100
            x1 = r.x0 + r.width * right_pct / 100
            y1 = r.y0 + r.height * bottom_pct / 100

            logger.info(
                "floor_plan_bbox: %.1f%%,%.1f%% → %.1f%%,%.1f%% (confidence=%.2f) → clip=(%.0f,%.0f,%.0f,%.0f)",
                left_pct, top_pct, right_pct, bottom_pct, confidence, x0, y0, x1, y1
            )
            return (x0, y0, x1, y1)
        except Exception as e:
            logger.warning("Failed to read floor_plan_bbox: %s", e)
            return None

    def _download_icgc_images(self) -> dict[str, Path]:
        """
        Download orthophoto + geological map + parcel orthophoto if UTM coords available.

        Returns dict with keys 'orthophoto', 'orthophoto_parcel', and/or 'geological_map',
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

        # Shared cadastre lookup for parcel overlay (Google or ICGC)
        rc14 = None
        polygon = None
        try:
            from .cadastre_adjacents import get_cadastral_reference, get_parcel_geometry_utm
            rc14_full, _ldt = get_cadastral_reference(utm_x, utm_y)
            if rc14_full and len(rc14_full) >= 14:
                rc14 = rc14_full[:14]
                polygon = get_parcel_geometry_utm(rc14)
        except Exception as e:
            logger.warning(f"Failed to get cadastre geometry: {e}")

        # Try Google satellite first (preferred source for parcel overlay)
        if rc14 and polygon:
            try:
                from .google_satellite import (
                    get_google_satellite_with_parcel,
                    GoogleSatelliteNoAPIKeyError,
                    GoogleSatelliteError,
                )
                google_path = self._cache_dir / f"google_sat_parcel_{utm_x:.0f}_{utm_y:.0f}.png"
                if not google_path.exists():
                    get_google_satellite_with_parcel(utm_x, utm_y, polygon, google_path)
                if google_path.exists():
                    result['orthophoto_parcel'] = google_path
                    logger.info(f"Google satellite with parcel outline ready: {google_path}")
            except GoogleSatelliteNoAPIKeyError:
                logger.info("No GOOGLE_MAPS_API_KEY set, falling back to ICGC orthophoto")
            except GoogleSatelliteError as e:
                logger.warning(f"Google satellite failed: {e}, falling back to ICGC")

        # Fall back to ICGC parcel overlay
        if 'orthophoto_parcel' not in result and rc14 and polygon:
            try:
                from .icgc_geology import get_orthophoto_with_parcel
                parcel_path = self._cache_dir / f"orthophoto_parcel_{utm_x:.0f}_{utm_y:.0f}.png"
                if not parcel_path.exists():
                    get_orthophoto_with_parcel(utm_x, utm_y, polygon, parcel_path)
                if parcel_path.exists():
                    result['orthophoto_parcel'] = parcel_path
                    logger.info(f"ICGC orthophoto with parcel outline ready: {parcel_path}")
            except Exception as e:
                logger.warning(f"Failed to create ICGC parcel orthophoto: {e}")

        # Fall back to plain orthophoto if no parcel overlay available
        if 'orthophoto' in result and 'orthophoto_parcel' not in result:
            result['orthophoto_parcel_plain'] = result['orthophoto']
            logger.info("Falling back to plain orthophoto (no parcel outline)")

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

        # 2. Field photos — user selection > AI selection > pattern matching
        photos = (
            self._load_user_photo_selection()
            or self.select_photos_ai()
            or self.discover_photos()
        )

        # Site photos (up to 2) — forced 4:3 landscape to match Eva's layout
        if photos['site']:
            context['photo_site_image_1'] = InlineImage(
                self.tpl, str(photos['site'][0]),
                width=Mm(IMAGE_WIDTH_SIDE_BY_SIDE),
                height=Mm(IMAGE_HEIGHT_SIDE_BY_SIDE),
            )
        else:
            context['photo_site_image_1'] = PLACEHOLDER_TEXT

        if len(photos['site']) >= 2:
            context['photo_site_image_2'] = InlineImage(
                self.tpl, str(photos['site'][1]),
                width=Mm(IMAGE_WIDTH_SIDE_BY_SIDE),
                height=Mm(IMAGE_HEIGHT_SIDE_BY_SIDE),
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
        #    cadastre: left portion of situation_plan PDF (cadastral maps)
        #    aerea: ICGC/Google satellite fallback (handled below)
        #    main_plan: from A.01.pdf (WITHOUT dots — shows "punt de partida")
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        roles = self._load_file_mapping()
        has_plan_crops = False

        # 3a. Cadastre + aerea from architect_plan_with_points clip_regions (if defined)
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

        # 3a-fallback. Cadastre from situation_plan: crop left ~38% (cadastral maps)
        if 'fig_cadastre_image' not in context:
            sit_plan_pdf = self._find_situation_plan(roles)
            if sit_plan_pdf:
                cached = self._cache_dir / f"cadastre_sitplan_{sit_plan_pdf.stem}.jpg"
                if not cached.exists():
                    self._render_situation_plan_left(sit_plan_pdf, cached)
                if cached.exists():
                    context['fig_cadastre_image'] = InlineImage(
                        self.tpl, str(cached), width=Mm(IMAGE_WIDTH_SIDE_BY_SIDE)
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
            # Priority 2: vision-detected floor_plan_bbox from planol_extracted.json
            bbox_clip = self._get_planol_bbox_clip(base_plan_pdf)
            if bbox_clip:
                cached = self._cache_dir / f"main_plan_crop_{base_plan_pdf.stem}.jpg"
                # Invalidate if planol_extracted.json is newer than cached image
                planol_json = self.project_path / 'validation' / 'planol_extracted.json'
                if cached.exists() and planol_json.exists() and planol_json.stat().st_mtime > cached.stat().st_mtime:
                    cached.unlink()
                    logger.info("Invalidated stale main_plan crop cache")
                if not cached.exists():
                    self._render_pdf_region(base_plan_pdf, cached, bbox_clip)
                if cached.exists():
                    context['fig_main_plan_image'] = InlineImage(
                        self.tpl, str(cached), width=Mm(IMAGE_WIDTH_MAIN_PLAN)
                    )
                    has_plan_crops = True
            else:
                # Priority 3: full page render (no bbox available)
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

        # ICGC images: geological map + orthophoto with parcel outline as aerea fallback
        icgc_images = self._download_icgc_images()
        if 'geological_map' in icgc_images:
            context['fig_geological_image'] = InlineImage(
                self.tpl, str(icgc_images['geological_map']), width=Mm(IMAGE_WIDTH_GEOLOGICAL)
            )
        else:
            context['fig_geological_image'] = PLACEHOLDER_TEXT

        # Fallback: if fig_aerea_image is still a placeholder, use parcel orthophoto
        if context.get('fig_aerea_image') == PLACEHOLDER_TEXT:
            if 'orthophoto_parcel' in icgc_images:
                context['fig_aerea_image'] = InlineImage(
                    self.tpl, str(icgc_images['orthophoto_parcel']),
                    width=Mm(IMAGE_WIDTH_SIDE_BY_SIDE)
                )
                context['fig_location_image'] = context['fig_aerea_image']
                source = "Google satellite" if "google_sat" in str(icgc_images['orthophoto_parcel']) else "ICGC orthophoto"
                logger.info(f"Using {source} with parcel outline as fig_aerea_image")
            elif 'orthophoto_parcel_plain' in icgc_images:
                context['fig_aerea_image'] = InlineImage(
                    self.tpl, str(icgc_images['orthophoto_parcel_plain']),
                    width=Mm(IMAGE_WIDTH_SIDE_BY_SIDE)
                )
                context['fig_location_image'] = context['fig_aerea_image']
                logger.info("Using plain ICGC orthophoto as fig_aerea_image (parcel outline unavailable)")

        # ── SmartScan figure roles (Phase 6) ──
        # If SmartScan classified images as figure roles, use them directly.
        # These override the derived/downloaded versions (ICGC, PDF crops).
        if roles:
            for role_name, var_name in ROLE_TO_FIGURE_VAR.items():
                if role_name in roles and var_name not in context:
                    fig_path = self.project_path / roles[role_name]['path']
                    if fig_path.exists():
                        context[var_name] = InlineImage(
                            self.tpl, str(fig_path), width=Mm(IMAGE_WIDTH_LOCATION)
                        )
                        logger.info(f"Figure from SmartScan role: {role_name} → {var_name} ({fig_path.name})")

        # Correlation section: SmartScan role → file_mapping → fallback glob
        if 'fig_correlation_image' not in context:
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
