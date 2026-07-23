#!/usr/bin/env python3
"""
G3DT Report Generator

Main orchestrator for automated geotechnical report generation.
Combines data extraction, calculations, section generation, and template rendering.

Dependencies:
    - docxtpl: Template rendering (pip install docxtpl)
    - xlrd: Excel reading for DPSH (pip install xlrd)

Usage:
    from automation.report_generator import ReportGenerator

    generator = ReportGenerator(
        project_path='/path/to/project/folder',
        user_data='/path/to/user_input.json'  # or dict
    )
    result = generator.generate('output_report.docx')

CLI:
    python3 -m automation.report_generator /path/to/project --user-data input.json --output report.docx

Author: Eficients.cat
Date: 2026-02-03
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import json
import logging
import re
import sys

from .formatting import format_floor_notation
from .project_extractor import ProjectExtractor
from .report_data import ReportData, build_report_data, to_dict as report_data_to_dict
from .terzaghi_calculator import TerzaghiCalculator, FootingShape
from .vision_normalizer import load_dpsh_json, load_sondeig_json
from .sections import (
    Section1Generator,
    Section2Generator,
    Section3Generator,
    Section4Generator,
)

logger = logging.getLogger(__name__)

# Eva's typical value ranges by soil category (confirmed 2026-02-26)
_TYPICAL_RANGES = {
    'granular': {'gamma': '2.0', 'c': '0.0-0.05', 'phi': '38-39', 'E': '450-650', 'Qa_cap': '3.0'},
    'cohesive': {'gamma': '1.90', 'c': '0.05', 'phi': '28', 'E': '100', 'Qa_cap': '3.0'},
    'rock': {'gamma': '2.20', 'c': '1.0', 'phi': '30-35', 'E': '>500-800', 'Qa_cap': '4.0-4.5'},
}


def _catalan_ordinal(n: int) -> str:
    """Return Catalan ordinal abbreviation: 1er, 2n, 3r, 4t, 5è, 6è..."""
    ordinals = {1: '1er', 2: '2n', 3: '3r', 4: '4t'}
    return ordinals.get(n, f'{n}è')






def _shorten_material_desc(desc: str) -> str:
    """Shorten a sondeig layer description for table cells.

    Strips secondary details after first comma or period, keeping only
    the primary material identification.
    E.g.: "Graves incloses en matriu sorrenca d'aspectes carbonatats, i de coloracions clars. Tram totalment carbonatat."
    -> "Graves incloses en matriu sorrenca d'aspectes carbonatats"
    """
    if not desc:
        return desc
    for sep in [', i de ', ', de ', '. ', ', ']:
        idx = desc.find(sep)
        if idx > 0:
            return desc[:idx]
    return desc


@dataclass
class ContextPreviewResult:
    """Result of a dry-run context build (no template rendering)."""
    context: dict[str, Any]
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class GenerationResult:
    """Result of report generation."""
    success: bool
    output_path: str | None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ReportGenerator:
    """
    Main orchestrator for report generation.

    Workflow:
    1. Load project data (from folder structure)
    2. Load user input data (from JSON or dict)
    3. Build unified ReportData
    4. Run section generators (1-4)
    5. Render into docx template
    6. Save output
    """

    DEFAULT_TEMPLATE_NAME = 'g3dt-jinja-template.docx'

    MESOS_CAT = {
        1: 'gener', 2: 'febrer', 3: 'març', 4: 'abril',
        5: 'maig', 6: 'juny', 7: 'juliol', 8: 'agost',
        9: 'setembre', 10: 'octubre', 11: 'novembre', 12: 'desembre',
    }

    def __init__(
        self,
        project_path: str | Path,
        user_data: dict | str | Path | None = None,
        template_path: str | Path | None = None,
    ):
        """
        Initialize generator with data sources.

        Args:
            project_path: Path to project folder (contains DPSH, client data, etc.)
            user_data: User input as dict, or path to JSON file
            template_path: Custom template path (uses default if None)
        """
        self.project_path = Path(project_path)
        self.project_data: dict = {}
        self.report_data: ReportData | None = None
        self.errors: list[str] = []
        self.warnings: list[str] = []

        self.template_path = Path(template_path) if template_path else self._find_template()
        self.user_data = self._load_user_data(user_data)

    def _find_template(self) -> Path:
        """
        Find the default template.

        Searches in:
        1. templates/ relative to project_path
        2. templates/ relative to automation package
        """
        # Try relative to project folder
        candidate = self.project_path / 'templates' / self.DEFAULT_TEMPLATE_NAME
        if candidate.exists():
            return candidate

        # Try relative to automation package (g3dt/templates)
        package_dir = Path(__file__).parent.parent
        candidate = package_dir / 'templates' / self.DEFAULT_TEMPLATE_NAME
        if candidate.exists():
            return candidate

        # Return default path even if not found (will error later)
        return package_dir / 'templates' / self.DEFAULT_TEMPLATE_NAME

    def _load_user_data(self, user_data: dict | str | Path | None) -> dict:
        """
        Load user data from dict or JSON file.

        Auto-discovers user_data.json in project folder if None.
        Returns empty dict if nothing found or loading fails.
        """
        if user_data is None:
            # Auto-discover user_data.json in project folder
            auto_path = self.project_path / 'user_data.json'
            if auto_path.exists():
                user_data = auto_path
            else:
                return {}

        if isinstance(user_data, dict):
            return user_data

        # Treat as path
        path = Path(user_data)
        if not path.exists():
            self.warnings.append(f"User data file not found: {path}")
            return {}

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    self.warnings.append(f"User data is not a dict: {type(data)}")
                    return {}
                return data
        except json.JSONDecodeError as e:
            self.errors.append(f"Invalid JSON in user data file: {e}")
            return {}
        except Exception as e:
            self.errors.append(f"Error loading user data: {e}")
            return {}

    def _extract_spt_data(self) -> dict | None:
        """Extract SPT data from sondeig_extracted.json or dpsh_extracted.json.

        Uses vision_normalizer for canonical key access.
        Checks sondeig first (spt_results), then falls back to dpsh (spt_in_dpsh).
        """
        # --- Source 1: sondeig_extracted.json ---
        sondeig_path = self.project_path / 'validation' / 'sondeig_extracted.json'
        if sondeig_path.exists():
            try:
                data = load_sondeig_json(sondeig_path)
                for test in data.get('sondeig_tests', []):
                    for spt in test.get('spt_results', []):
                        depth_from = spt.get('depth_from_m')
                        depth_to = spt.get('depth_to_m')
                        depth_range = f"-{depth_from:.2f} a {depth_to:.2f}" if depth_from is not None and depth_to is not None else ''
                        # Get lithology from the layer at SPT depth
                        lithology = ''
                        for layer in test.get('layers', []):
                            layer_from = layer.get('depth_from_m')
                            layer_from = 0 if layer_from is None else layer_from
                            layer_to = layer.get('depth_to_m')
                            layer_to = 99 if layer_to is None else layer_to
                            if layer_from <= (depth_from or 0) < layer_to:
                                lithology = layer.get('description', '')
                                break
                        return {
                            'test_id': spt.get('test_id', 'SPT-1'),
                            'location': test.get('test_id', 'S-1'),
                            'depth_range': depth_range,
                            'n30': spt.get('n_spt', ''),
                            'lithology': lithology,
                        }
            except Exception as e:
                logger.warning(f"Could not extract SPT from sondeig: {e}")

        # --- Source 2: dpsh_extracted.json (SPT in DPSH field sheet) ---
        dpsh_path = self.project_path / 'validation' / 'dpsh_extracted.json'
        if dpsh_path.exists():
            try:
                dpsh_data = load_dpsh_json(dpsh_path)
                spt = dpsh_data.get('spt_in_dpsh')
                if spt:
                    depth_from = spt.get('depth_from_m')
                    depth_to = spt.get('depth_to_m')
                    depth_range = f"-{depth_from:.2f} a -{depth_to:.2f}" if depth_from is not None and depth_to is not None else ''
                    # Format location as P-N (add hyphen if missing)
                    ref = spt.get('location', '')
                    if ref and '-' not in ref:
                        ref = re.sub(r'([A-Za-z]+)(\d+)', r'\1-\2', ref)
                    return {
                        'test_id': spt.get('test_id', 'SPT-1'),
                        'location': ref,
                        'depth_range': depth_range,
                        'n30': spt.get('n_spt', ''),
                        'lithology': '',
                    }
            except Exception as e:
                logger.warning(f"Could not extract SPT from dpsh: {e}")

        return None

    # Keep old name as alias for backwards compatibility
    _extract_spt_from_sondeig = _extract_spt_data

    def extract_project_data(self) -> dict:
        """
        Extract all data from project folder.

        Returns dict suitable for build_report_data().
        """
        try:
            extractor = ProjectExtractor(str(self.project_path))
            project_data = extractor.extract_all()
            self.project_data = project_data.to_dict()
            return self.project_data
        except FileNotFoundError as e:
            self.errors.append(f"Project folder not found: {e}")
            return {}
        except Exception as e:
            self.errors.append(f"Error extracting project data: {e}")
            return {}

    def build_report_data(self) -> ReportData | None:
        """
        Build unified ReportData from all sources.

        Includes Terzaghi calculation if DPSH data available.
        """
        if not self.project_data:
            self.errors.append("No project data available. Call extract_project_data() first.")
            return None

        try:
            # Auto-fill from sondeig data (annex preferred over field sheet)
            try:
                from .vision_normalizer import load_sondeig_merged
                sondeig_data = load_sondeig_merged(self.project_path / 'validation')
                if sondeig_data:
                    sondeig_tests = sondeig_data.get('sondeig_tests', [])
                    if sondeig_tests:
                        # Store full test data for the sondeig summary table
                        self.user_data['sondeig_tests'] = sondeig_tests

                        # Always populate sondeig_layers (needed for rock
                        # detection and per-layer N20 computation)
                        layers = sondeig_tests[0].get('layers', [])
                        if layers and not self.user_data.get('sondeig_layers'):
                            self.user_data['sondeig_layers'] = layers

                        # Auto-fill num_soil_levels only if NOT already set in user_data
                        # (user/wizard choice takes precedence over auto-detection)
                        # Prefer num_geological_levels (from "Unitat litològica" column)
                        # over len(layers) which counts individual soil strata
                        geo_levels = sondeig_tests[0].get('num_geological_levels')
                        num_levels = geo_levels if geo_levels is not None else len(layers)
                        if 'num_soil_levels' not in self.user_data and num_levels > 0:
                            self.user_data['num_soil_levels'] = num_levels
                            logger.info(
                                "Auto-filled num_soil_levels=%d from sondeig_extracted.json",
                                num_levels,
                            )

                    # Override cota_referencia with borehole elevation_z
                    # (field-measured, more accurate than ICGC MDT satellite data).
                    # Always override unless source is explicitly 'user' (Eva typed it).
                    elev_z = sondeig_data.get('elevation_z')
                    if elev_z is not None:
                        cota_source = self.user_data.get('_sources', {}).get('cota_referencia', '')
                        if cota_source != 'user':
                            try:
                                cota_val = float(elev_z)
                                self.user_data['cota_referencia'] = f"+{cota_val:.2f}"
                                logger.info(
                                    "Overrode cota_referencia=+%.2f from sondeig elevation_z (was: %s, source: %s)",
                                    cota_val, self.user_data.get('cota_referencia', ''), cota_source,
                                )
                            except (ValueError, TypeError):
                                pass
            except Exception as e:
                self.warnings.append(f"Could not auto-fill from sondeig_extracted.json: {e}")

            # Auto-fill annotated refusal depths from dpsh_extracted.json
            # (handwritten "R:" annotation is more accurate than Excel last-row depth)
            try:
                dpsh_ext_path = self.project_path / 'validation' / 'dpsh_extracted.json'
                if dpsh_ext_path.exists():
                    dpsh_ext_data = load_dpsh_json(dpsh_ext_path)
                    # Store refusal depths indexed by test_id for patching DPSHTest later
                    refusal_map = {}
                    for test in dpsh_ext_data.get('dpsh_tests', []):
                        tid = test.get('test_id', '')
                        rdm = test.get('refusal_depth_m')
                        if tid and rdm is not None:
                            refusal_map[tid] = rdm
                    if refusal_map:
                        self.user_data['_dpsh_refusal_annotated'] = refusal_map
                        logger.info(
                            "Loaded annotated refusal depths from dpsh_extracted.json: %s",
                            refusal_map,
                        )
            except Exception as e:
                self.warnings.append(f"Could not load dpsh_extracted.json refusal depths: {e}")

            self.report_data = build_report_data(
                project_data=self.project_data,
                user_data=self.user_data,
                terzaghi_result=None,
                project_path=str(self.project_path),
            )

            # Patch DPSHTest objects with annotated refusal depths from field sheet
            refusal_map = self.user_data.get('_dpsh_refusal_annotated', {})
            if refusal_map and self.report_data.dpsh:
                for test in self.report_data.dpsh.tests:
                    if test.test_id in refusal_map:
                        test.refusal_depth_annotated = refusal_map[test.test_id]
                        logger.info(
                            "Patched %s depth: Excel %.2f → annotated %.2f",
                            test.test_id, abs(test.max_depth),
                            abs(test.refusal_depth_annotated),
                        )

            # Calculate Terzaghi AFTER build_report_data (needs correct cohesion for rock cap)
            if self.report_data.geotechnical_params:
                try:
                    gp = self.report_data.geotechnical_params
                    calc = TerzaghiCalculator(
                        phi=gp.phi,
                        cohesion=gp.cohesion,
                        gamma=gp.gamma,
                    )
                    B = self.user_data.get('footing_width_m', 1.0)
                    Df = self.user_data.get('foundation_depth_m', 0.8)
                    # Nb for Terzaghi-Peck — use bearing-stratum N20
                    # (Eva's skip-soft-top rule; consistent with build_report_data)
                    from .report_data import _bearing_stratum_n20
                    sondeig_layers = self.user_data.get('sondeig_layers') or []
                    soil_types_list = self.user_data.get('soil_types') or []
                    if self.report_data.dpsh and sondeig_layers:
                        avg_n20 = _bearing_stratum_n20(
                            self.report_data.dpsh, sondeig_layers, soil_types_list,
                        )
                    else:
                        avg_n20 = self.report_data.dpsh.overall_average_n20 if self.report_data.dpsh else None
                    nb_for_tp = avg_n20 / 0.83 if avg_n20 else None
                    # Granular if cohesion < 0.5 (consistent with rock cap logic)
                    is_granular = gp.cohesion < 0.5
                    # Soil type from bearing stratum (last soil_level is bearing material;
                    # _generate_soil_levels merges to keep deepest description when
                    # num_levels < len(sondeig_layers))
                    soil_type = self.report_data.soil_levels[-1].soil_type if self.report_data.soil_levels else 'granular'
                    # Es_settlement from wizard/user_data (overrides auto 2.5×Nb)
                    Es_override = self.user_data.get('Es_settlement')
                    self.report_data.terzaghi_result = calc.calculate_qa(
                        B=B, Df=Df, shape=FootingShape.SQUARE,
                        E=gp.E,
                        nspt=nb_for_tp, is_granular=is_granular,
                        soil_type=soil_type,
                        Es_override=Es_override,
                    )
                except Exception as e:
                    self.warnings.append(f"Terzaghi calculation failed: {e}")

            return self.report_data

        except Exception as e:
            self.errors.append(f"Error building report data: {e}")
            return None

    def generate_sections(self) -> dict[str, Any]:
        """
        Generate all section content.

        Returns dict with keys: section1, section2, section3, section4
        """
        if not self.report_data:
            self.errors.append("No report data. Call build_report_data() first.")
            return {}

        context: dict[str, Any] = {}

        try:
            section1 = Section1Generator(self.report_data)
            context['section1'] = section1.generate_all()
        except Exception as e:
            self.errors.append(f"Section 1 generation failed: {e}")
            context['section1'] = None

        try:
            section2 = Section2Generator(self.report_data)
            context['section2'] = section2.generate_all()
        except Exception as e:
            self.errors.append(f"Section 2 generation failed: {e}")
            context['section2'] = None

        try:
            section3 = Section3Generator(self.report_data)
            context['section3'] = section3.generate_all()
        except Exception as e:
            self.errors.append(f"Section 3 generation failed: {e}")
            context['section3'] = None

        try:
            section4 = Section4Generator(self.report_data)
            context['section4'] = section4.generate_all()
        except Exception as e:
            self.errors.append(f"Section 4 generation failed: {e}")
            context['section4'] = None

        # Check if all sections failed
        if all(context.get(f'section{i}') is None for i in range(1, 5)):
            self.errors.append("CRITICAL: All section generators failed. Report would be empty.")

        return context

    def _build_numbering_context(self) -> dict[str, Any]:
        """
        Build dynamic numbering for figures, photos, and tables.

        Numbering depends on:
        - num_project_figures: Project-specific figures from user (0-3)
        - has_sondeig: Adds one photo for sondeig machine
        - num_dpsh_tests: Affects table range for DPSH results

        Returns dict with all numbering variables for template.
        """
        if not self.report_data:
            return {}

        # Get configuration from user_data
        num_project_figures = self.user_data.get('num_project_figures', 0)
        has_sondeig = self.report_data.has_sondeig
        num_dpsh_tests = self.report_data.num_dpsh_tests

        # === FIGURE NUMBERING ===
        # Project figures come first (from architect's project)
        fig_counter = num_project_figures

        # Cadastre map (from architect plan crops)
        fig_counter += 1
        fig_cadastre_num = fig_counter

        # Aerial view (from architect plan crops)
        fig_counter += 1
        fig_aerea_num = fig_counter

        # Main architect plan with building layout
        fig_counter += 1
        fig_main_plan_num = fig_counter

        # SPT spoon diagram (if present in section 2.4)
        fig_counter += 1
        fig_spt_cullera_num = fig_counter

        # Geological map
        fig_counter += 1
        fig_geological_num = fig_counter

        # Correlation section
        fig_counter += 1
        fig_correlation_num = fig_counter

        # === PHOTO NUMBERING ===
        photo_counter = 0

        # Site view(s) - auto-detect from FOTOGRAFIES/ if not explicitly set
        num_site_photos = self.user_data.get('num_site_photos', 0)
        if num_site_photos == 0:
            # Auto-detect: count vista_general_* files in FOTOGRAFIES/
            foto_dir = self.project_path / 'FOTOGRAFIES'
            if foto_dir.exists():
                site_photos = sorted(foto_dir.glob('vista_general_*'))
                num_site_photos = min(len(site_photos), 2)
            if num_site_photos == 0:
                num_site_photos = 2  # Eva always places 2 side-by-side photos
        photo_counter += num_site_photos
        if num_site_photos == 1:
            photo_site_text = "Fotografia 1"
        else:
            photo_site_text = "Fotografia 1 i Fotografia 2"

        # DPSH machine photo
        photo_counter += 1
        photo_dpsh_num = photo_counter

        # Sondeig machine photo (conditional)
        if has_sondeig:
            photo_counter += 1
            photo_sondeig_num = photo_counter
        else:
            photo_sondeig_num = None

        # Materials detail photo
        photo_counter += 1
        photo_materials_num = photo_counter

        # === TABLE NUMBERING ===
        # Tables 1-2 are always: Building summary, CTE classification
        table_counter = 2

        # In-situ test tables: DPSH + sondeig combined in one range
        # Pattern from samples:
        # - 2 DPSH tests (no sondeig) = "Taula 3 i 4"
        # - 2 DPSH + 1 sondeig = "Taula 3, 4 i 5"
        # - 3 DPSH tests (no sondeig) = "Taula 3, 4 i 5"
        total_insitu_tables = num_dpsh_tests + (1 if has_sondeig else 0)
        table_dpsh_start = table_counter + 1  # Usually 3

        if total_insitu_tables <= 2:
            table_dpsh_end = table_dpsh_start + 1  # "3 i 4"
            table_dpsh_range = f"{table_dpsh_start} i {table_dpsh_end}"
            table_counter = table_dpsh_end
        else:
            table_dpsh_end = table_dpsh_start + 2  # "3, 4 i 5"
            table_dpsh_range = f"{table_dpsh_start}, {table_dpsh_start + 1} i {table_dpsh_end}"
            table_counter = table_dpsh_end

        # Lab results table
        table_counter += 1
        table_lab_num = table_counter

        # Permeability table
        table_counter += 1
        table_permeability_num = table_counter

        # Lab values table
        table_counter += 1
        table_lab_values_num = table_counter

        # Seismic table
        table_counter += 1
        table_seismic_num = table_counter

        # Soil characteristics table
        table_counter += 1
        table_soil_chars_num = table_counter

        return {
            # Figure numbers
            'fig_cadastre_num': fig_cadastre_num,
            'fig_aerea_num': fig_aerea_num,
            'fig_main_plan_num': fig_main_plan_num,
            'fig_spt_cullera_num': fig_spt_cullera_num,
            'fig_geological_num': fig_geological_num,
            'fig_correlation_num': fig_correlation_num,
            # Backward-compat aliases
            'fig_location_num': fig_cadastre_num,
            'fig_building_num': fig_main_plan_num,
            # Photo numbers
            'photo_site_text': photo_site_text,
            'photo_dpsh_num': photo_dpsh_num,
            'photo_sondeig_num': photo_sondeig_num if photo_sondeig_num else '',
            'photo_materials_num': photo_materials_num,
            # Table numbers
            'table_dpsh_range': table_dpsh_range,
            'table_lab_num': table_lab_num,
            'table_permeability_num': table_permeability_num,
            'table_lab_values_num': table_lab_values_num,
            'table_seismic_num': table_seismic_num,
            'table_soil_chars_num': table_soil_chars_num,
        }

    def _build_template_context(self, sections: dict[str, Any]) -> dict[str, Any]:
        """
        Build context dict for template rendering.

        Maps generator output to template placeholders.
        Current template expects: client, location, expedient, data_camp_text, data_signatura_text
        """
        context: dict[str, Any] = {}

        # Add dynamic numbering
        context.update(self._build_numbering_context())

        # Include structured section data (for future templates)
        context.update(sections)

        # Map to current template's expected flat variables
        if self.report_data:
            # Basic project info
            client_name = self.report_data.client.company_name or ''
            # Format company suffix: SL -> S.L., SLU -> S.L.U.
            client_name = re.sub(r'\bSLU\b', 'S.L.U.', client_name)
            client_name = re.sub(r'\bSL\b', 'S.L.', client_name)
            context['client'] = client_name.upper()
            context['expedient'] = self.report_data.expedient or ''
            context['street_address'] = self.report_data.street_address or ''
            context['municipality'] = self.report_data.municipality or ''

            # Dates - auto-fill from DPSH PDF if not provided
            if not self.report_data.field_work_dates_text:
                try:
                    from .dpsh_extractor import extract_field_dates, format_dates_catalan
                    pdf_dates = extract_field_dates(self.project_path)
                    if pdf_dates:
                        self.report_data.field_work_dates_text = format_dates_catalan(pdf_dates)
                        logger.info(f"Auto-filled field_work_dates from DPSH PDF: {pdf_dates}")
                except (ImportError, Exception) as e:
                    self.warnings.append(f"Could not extract dates from DPSH PDF: {e}")
            context['data_camp_text'] = self.report_data.field_work_dates_text or ''
            d = self.report_data.report_date
            mes = self.MESOS_CAT.get(d.month, d.strftime('%B'))
            context['data_signatura_text'] = f"{d.day:02d} de {mes} de {d.year}"

            # Architect
            context['architect_name'] = self.report_data.architect_name or ''
            context['architect_company'] = self.report_data.architect_company or ''
            context['architect_name_upper'] = (self.report_data.architect_name or '').upper()

            # Building
            context['building_type'] = self.report_data.building_type or ''
            context['building_type_lower'] = (self.report_data.building_type or '').lower()
            context['num_floors'] = format_floor_notation(self.report_data.num_floors or '')

            # Building structure description from num_floors
            # "en planta baixa" when foundation starts at ground level (PB, PB+P1, etc.)
            # "de soterrani" when there's a basement (PS, etc.)
            num_floors_raw = (self.report_data.num_floors or '').upper()
            if num_floors_raw.startswith('PB'):
                context['building_structure_desc'] = 'en planta baixa'
            elif num_floors_raw.startswith('PS'):
                context['building_structure_desc'] = 'de soterrani'
            else:
                context['building_structure_desc'] = self.report_data.building_type or 'en planta baixa'

            # Municipality uppercase
            context['municipality_upper'] = (self.report_data.municipality or '').upper()

            # Street split: "Carrer X, 25220 Bell-Lloc" → street_1="Carrer X", street_2="Bell-Lloc d'Urgell"
            street = self.report_data.street_address or ''
            parts = street.split(',', 1)
            context['street_1'] = parts[0].strip() if parts else ''
            street_2 = parts[1].strip().lstrip('0123456789 ') if len(parts) > 1 else ''
            # Fall back to municipality if no comma in address
            if not street_2:
                street_2 = self.report_data.municipality or ''
            context['street_2'] = street_2

            # CTE Classification (original names)
            context['cte_building_class'] = self.report_data.cte_building_class or 'C-0'
            context['cte_soil_class'] = self.report_data.cte_soil_class or 'T-1'
            # CTE Classification (template names)
            context['cte_edificacio'] = self.report_data.cte_building_class or 'C-0'
            context['cte_sol'] = self.report_data.cte_soil_class or 'T-1'

            # Building dimensions for template
            context['plantes'] = format_floor_notation(self.report_data.num_floors or '')
            # Prefer cadastral surface for Taula 1 (official parcel area)
            # Fall back to planol surface if cadastral not available
            context['superficie_parcela'] = (
                self.report_data.superficie_cadastral
                or self.report_data.superficie_parcela
                or ''
            )
            context['superficie_cadastral'] = self.report_data.superficie_cadastral or ''
            context['superficie_parcela_planol'] = self.report_data.superficie_parcela or ''
            context['superficie_construida'] = self.report_data.superficie_construida or ''

            # Descriptions
            context['access_description'] = self.report_data.access_description or ''
            context['site_description'] = self.report_data.site_description or ''

            # Laboratori d'assaigs
            context['lab_field_company'] = self.report_data.lab_company or 'TPS PROSPECCIÓ DEL SUBSÒL SL'
            context['lab_field_description'] = self.report_data.lab_description or "laboratori d'assaigs per al control de qualitat de l'edificació"
            lab_alias = f" ({self.report_data.lab_company_alias})" if self.report_data.lab_company_alias else ""
            context['lab_testing_company'] = (self.report_data.lab_company or 'TPS PROSPECCIÓ DEL SUBSÒL SL') + lab_alias
            context['lab_testing_description'] = self.report_data.lab_description or "laboratori d'assaigs per al control de qualitat de l'edificació"

            # Auto-fill cota_referencia from ICGC MDT if not provided
            if not self.report_data.cota_referencia and self.report_data.utm_x and self.report_data.utm_y:
                try:
                    from .icgc_geology import get_elevation, format_cota_referencia, ICGCError
                    elevation = get_elevation(self.report_data.utm_x, self.report_data.utm_y)
                    self.report_data.cota_referencia = format_cota_referencia(elevation)
                    logger.info(f"Auto-filled cota_referencia from ICGC MDT: {self.report_data.cota_referencia}")
                except ImportError as e:
                    self.warnings.append(f"icgc_geology module not available, skipping cota auto-fill: {e}")
                except ICGCError as e:
                    self.warnings.append(f"Could not auto-fill cota_referencia from ICGC MDT: {e}")

            context['cota_referencia'] = self.report_data.cota_referencia or ''

            # Location details
            context['street_address'] = self.report_data.street_address or ''

            # Auto-fill adjacent parcels: visor JSON (priority 1) then API probes (priority 2)
            adj = self.report_data.adjacent_parcels or {}

            # Priority 1: Read from visor JSON (generated by /g3dt-adjacents-visor skill)
            visor_path = self.project_path / 'validation' / 'adjacents_visor.json'
            if visor_path.exists():
                try:
                    with open(visor_path, 'r', encoding='utf-8') as f:
                        visor_data = json.load(f)
                    visor_adj = visor_data.get('adjacents', {})
                    for d in ('north', 'south', 'east', 'west'):
                        if not adj.get(d) and visor_adj.get(d):
                            adj[d] = visor_adj[d]
                            logger.info(f"Auto-filled adjacent_{d} from visor: {adj[d]}")
                except Exception as e:
                    self.warnings.append(f"Could not read visor adjacents: {e}")

            # Priority 2: API probes fallback (cadastre_adjacents)
            any_still_empty = any(
                not adj.get(d) for d in ('north', 'south', 'east', 'west')
            )
            if any_still_empty and self.report_data.utm_x and self.report_data.utm_y:
                try:
                    from .cadastre_adjacents import get_adjacent_parcels, CadastreError
                    from .report_data import _eval_numeric
                    superficie = _eval_numeric(self.report_data.superficie_parcela) or 600.0
                    rc14 = getattr(self.report_data, 'cadastral_ref', None)
                    municipality = self.report_data.municipality
                    auto_adj = get_adjacent_parcels(
                        self.report_data.utm_x,
                        self.report_data.utm_y,
                        superficie,
                        rc14=rc14,
                        municipality=municipality,
                    )
                    for d in ('north', 'south', 'east', 'west'):
                        if not adj.get(d) and auto_adj.get(d):
                            adj[d] = auto_adj[d]
                            logger.info(f"Auto-filled adjacent_{d} from Cadastre: {adj[d]}")
                except ImportError as e:
                    self.warnings.append(f"cadastre_adjacents module not available, skipping adjacent auto-fill: {e}")
                except CadastreError as e:
                    self.warnings.append(f"Could not auto-fill adjacents from Cadastre: {e}")
                except Exception as e:
                    self.warnings.append(f"Unexpected error during adjacent auto-fill: {e}")

            # Clean municipality from adjacent street names (cadastre LDT may include it)
            if self.report_data.municipality:
                _muni_pattern = re.escape(self.report_data.municipality)
                for direction in ('north', 'south', 'east', 'west'):
                    val = adj.get(direction, '')
                    if val:
                        cleaned = re.sub(r'\s+' + _muni_pattern + r'\s*$', '', val, flags=re.IGNORECASE).strip()
                        if cleaned and cleaned != val:
                            adj[direction] = cleaned
                            logger.info(f"Cleaned municipality from adjacent_{direction}: '{val}' → '{cleaned}'")

            context['adjacent_north'] = adj.get('north', '')
            context['adjacent_south'] = adj.get('south', '')
            context['adjacent_east'] = adj.get('east', '')
            context['adjacent_west'] = adj.get('west', '')
            # Find the second bordering street (any direction: S→E→W→N, different from street_1)
            street_prefixes = ('carrer ', 'camí ', 'passeig ', 'avinguda ', 'plaça ', 'ronda ', 'travessia ')
            street_1_lower = context.get('street_1', '').lower()
            second_street = ''
            for direction in ('south', 'east', 'west', 'north'):
                val = adj.get(direction, '').strip()
                if val and val.lower().startswith(street_prefixes) and val.lower() != street_1_lower:
                    second_street = val
                    break
            context['adjacent_nearest_street'] = second_street

            # Build grammatically correct location sentence for P60
            # Catalan articles: el (masc), la (fem), l' (before vowel)
            def _street_article(name: str) -> str:
                s = name.strip().lower()
                if s.startswith(('avinguda', 'autopista')):
                    return "l'"
                if s.startswith(('plaça', 'ronda', 'travessia', 'partida')):
                    return 'la '
                return 'el '

            municipality = self.report_data.municipality or ''
            muni_suffix = f" de {municipality}" if municipality else ''
            st1 = context.get('street_1', '')
            if street_1_lower and second_street:
                art1 = _street_article(st1)
                art2 = _street_article(second_street)
                context['location_sentence'] = f"entre {art1}{st1} i {art2}{second_street}{muni_suffix}"
            elif street_1_lower:
                art = _street_article(st1)
                # Catalan preposition "a" + article: al (a+el), a la, a l'
                if art == "l'":
                    loc_prep = "a l'"
                elif art == 'la ':
                    loc_prep = "a la "
                else:
                    loc_prep = "al "  # a + el contraction
                context['location_sentence'] = f"{loc_prep}{st1}{muni_suffix}"
            elif municipality:
                context['location_sentence'] = f"al terme municipal de {municipality}"
            else:
                context['location_sentence'] = "en una ubicació no especificada"

            # Adjacent formatting with bilingual support (Catalan/Spanish).
            # Priority per direction (see resolve_adjacent_fmt):
            #   1. Eva's user edit (user_data source='user')
            #   2. LLM synthesis with visual observations
            #      (user_data source='llm_synthesis_with_observations')
            #   3. Cadastre-template fallback (format_all_adjacents)
            # Without this precedence, synthesized/edited values are silently
            # overwritten by the raw cadastre template when the report is built.
            from automation.adjacent_formatter import resolve_adjacent_fmt
            municipality = self.report_data.municipality or None
            adj_resolved = resolve_adjacent_fmt(adj, self.user_data, municipality)
            context.update(adj_resolved)

            # Access street extraction — strip sentence prefix + preposition + suffix
            # to get just the street name (e.g. "El dia dels treballs ... a través del Carrer X existent al sud." → "Carrer X")
            access = self.report_data.access_description or ''
            # Strip full-sentence prefix if present (new format)
            _prefix_pat = r"El dia dels treballs de camp es realitza l['\u2019]entrada a la zona d['\u2019]estudi a trav[eé]s\s*"
            _prefix_m = re.match(_prefix_pat, access, re.IGNORECASE)
            if _prefix_m:
                access = access[_prefix_m.end():]
            access_match = re.search(
                r"(?:des del|des de la|del|de la|de l['\u2019]?)\s*(.+?)(?:\s+existent\b|\.|$)",
                access, re.IGNORECASE,
            )
            context['access_street'] = access_match.group(1).strip() if access_match else access

            # Site condition
            is_anthropized = getattr(self.report_data, 'is_anthropized', None)
            if is_anthropized is None:
                context['site_condition'] = 'pla'
            else:
                context['site_condition'] = 'antropitzat' if is_anthropized else 'no antropitzat'

            # Auto-fill is_sloped from ICGC MDT slope analysis
            if self.report_data.utm_x and self.report_data.utm_y:
                try:
                    from .icgc_geology import get_slope
                    slope_pct, slope_dir = get_slope(
                        self.report_data.utm_x, self.report_data.utm_y
                    )
                    if slope_pct > 15.0:
                        if not getattr(self.report_data, 'is_sloped', False):
                            logger.info(f"Auto-set is_sloped=True (slope={slope_pct:.1f}% {slope_dir})")
                        context['is_sloped'] = True
                        context['slope_percent'] = f"{slope_pct:.1f}"
                        context['slope_direction'] = slope_dir
                    else:
                        context['is_sloped'] = getattr(self.report_data, 'is_sloped', False)
                        context['slope_percent'] = f"{slope_pct:.1f}"
                        context['slope_direction'] = slope_dir
                except (ImportError, Exception) as e:
                    self.warnings.append(f"Could not calculate slope from ICGC MDT: {e}")
                    context['is_sloped'] = getattr(self.report_data, 'is_sloped', False)

            # Conditional sections - Sondeig
            has_sondeig = getattr(self.report_data, 'has_sondeig', False)
            context['has_sondeig'] = has_sondeig

            # Dynamic section numbering based on has_sondeig
            if has_sondeig:
                context['section_sondeig_num'] = '2.4.2'
                context['section_spt_num'] = '2.4.3'
                context['section_resum_num'] = '2.4.4'
            else:
                context['section_sondeig_num'] = ''  # Not used
                context['section_spt_num'] = '2.4.2'
                context['section_resum_num'] = '2.4.3'

            # Geothermal section
            context['include_geothermal'] = getattr(self.report_data, 'include_geothermal', False)

            # Phase 3: Conditional sections
            include_expansivity = getattr(self.report_data, 'include_expansivity', False)
            include_earth_pressure = getattr(self.report_data, 'include_earth_pressure', False)
            include_slope_stability = getattr(self.report_data, 'include_slope_stability', False)

            # Auto-activate slope stability + earth pressure when slope detected
            if context.get('is_sloped'):
                if not include_slope_stability:
                    include_slope_stability = True
                    logger.info("Auto-activated slope stability (slope auto-detected from ICGC MDT)")
                if not include_earth_pressure:
                    include_earth_pressure = True
                    logger.info("Auto-activated earth pressure (slope auto-detected → retaining walls needed)")

            context['include_expansivity'] = include_expansivity
            context['include_earth_pressure'] = include_earth_pressure
            context['include_slope_stability'] = include_slope_stability
            context['show_granulometric'] = getattr(self.report_data, 'show_granulometric', False)

            # Dynamic section numbering for Section 3 (affected by expansivity)
            if include_expansivity:
                context['section_excavabilitat_num'] = '3.6'
                context['section_sismica_num'] = '3.7'
                context['section_rado_num'] = '3.8'
            else:
                context['section_excavabilitat_num'] = '3.5'
                context['section_sismica_num'] = '3.6'
                context['section_rado_num'] = '3.7'

            # Dynamic section numbering for Section 4 (affected by earth pressure + slope)
            context['section_fonamentacio_num'] = '4.3'
            if include_earth_pressure:
                context['section_empentes_num'] = '4.4'
                context['section_estabilitat_num'] = '4.5' if include_slope_stability else ''
            else:
                context['section_empentes_num'] = ''
                context['section_estabilitat_num'] = '4.4' if include_slope_stability else ''

            # Soil levels for section 3.2 - built later after section3 processing

            # DPSH summary
            if self.report_data.dpsh:
                dpsh = self.report_data.dpsh
                context['num_dpsh_tests'] = dpsh.num_tests
                context['dpsh_test_ids'] = ','.join(dpsh.test_ids)
                # Eva shows "Nb mig" (Nb average), not N20 average.
                # Use bearing stratum N20 when available, convert to Nb (N20/0.83), integer format.
                bearing_n20 = (
                    self.report_data.soil_levels[-1].n20_average
                    if self.report_data.soil_levels
                    else dpsh.overall_average_n20
                )
                context['dpsh_avg_n20'] = f"{bearing_n20 / 0.83:.0f}"

            # DPSH table rows
            dpsh_tests = []
            if self.report_data.dpsh:
                for test in self.report_data.dpsh.tests:
                    cota = self.report_data.cota_referencia or ''
                    max_depth = f"{test.depth_reached:.2f}" if test.readings else ''
                    has_refusal = 'Si' if test.refusal_reached else 'No'
                    water = 'No detectat'
                    if test.water_depth is not None:
                        water = f"{abs(test.water_depth):.2f} m"
                    dpsh_tests.append({
                        'test_id': test.test_id,
                        'cota': cota,
                        'depth': f"-{max_depth}" if max_depth else '',
                        'refusal': has_refusal,
                        'water': water,
                    })
            context['dpsh_tests'] = dpsh_tests

            # Sondeig summary table rows
            sondeig_table_tests = []
            if sections.get('section2') and sections['section2'].taula4_sondeig:
                sondeig_table_tests = sections['section2'].taula4_sondeig
            context['sondeig_tests'] = sondeig_table_tests

            # SPT data — from user_data, fallback to sondeig_extracted.json
            spt = self.report_data.spt_data
            if not spt and self.report_data.has_spt:
                spt = self._extract_spt_from_sondeig()
            spt = spt or {}
            context['spt_test_id'] = spt.get('test_id', '')
            context['spt_location'] = spt.get('location', '')
            context['spt_depth_range'] = spt.get('depth_range', '')
            context['spt_n30'] = str(spt.get('n30', ''))
            context['spt_lithology'] = spt.get('lithology', '')

            # Lab data - auto-fill from lab PDF if not provided
            if not self.report_data.lab_tests:
                try:
                    from .lab_extractor import extract_lab_results
                    lab_results = extract_lab_results(self.project_path)
                    if lab_results.tests:
                        self.report_data.lab_tests = [t.to_dict() for t in lab_results.tests]
                        logger.info(f"Auto-filled lab_tests from {lab_results.source_file}")
                    if lab_results.sulfate_mg_kg is not None and not self.report_data.sulfate_mg_kg:
                        self.report_data.sulfate_mg_kg = lab_results.sulfate_mg_kg
                        logger.info(f"Auto-filled sulfate_mg_kg: {lab_results.sulfate_mg_kg}")
                except (ImportError, Exception) as e:
                    self.warnings.append(f"Could not extract lab results from PDF: {e}")

            lab = self.report_data.lab_tests[0] if self.report_data.lab_tests else {}
            context['lab_sample_id'] = lab.get('sample_id', '')
            context['lab_location'] = lab.get('location', '')
            context['lab_depth'] = lab.get('depth', '')
            context['lab_tests_text'] = lab.get('type', '')

            # Geology paragraphs from section 3
            context['materials_level_1'] = ''
            context['materials_intro'] = ''
            context['seismic_ab_text'] = ''
            context['radon_zone'] = '1'
            context['radon_zone_description'] = ''
            context['csn_radon_text'] = ''
            for i in range(6):
                context[f'geology_para_{i+1}'] = ''
            context['geology_paragraphs'] = []
            if sections.get('section3'):
                s3 = sections['section3']

                # Use paragraph list directly (no more split/truncation)
                geo_paras = s3.marc_geologic_paragraphs if s3.marc_geologic_paragraphs else []
                # Populate legacy geology_para_N for backward compat
                for i in range(6):
                    key = f'geology_para_{i+1}'
                    context[key] = geo_paras[i] if i < len(geo_paras) else ''
                # Pass full list for dynamic template loop
                context['geology_paragraphs'] = geo_paras

                # Materials
                if s3.materials_levels:
                    context['materials_level_1'] = s3.materials_levels[0]
                else:
                    context['materials_level_1'] = ''

                context['materials_intro'] = s3.materials_intro

                # Sismica (extract ab value from generated text)
                if s3.sismica:
                    ab_match = re.search(r'ab\s*=\s*([\d.]+)', s3.sismica)
                    if ab_match:
                        # Use comma as decimal separator (Catalan format)
                        context['seismic_ab_text'] = ab_match.group(1).replace('.', ',')

                # Check if seismic lookup found the municipality
                municipality = self.report_data.municipality or ''
                if municipality:
                    from .municipal_data import get_seismic_ab_with_status
                    seismic_result = get_seismic_ab_with_status(municipality)
                    if not seismic_result.found:
                        self.warnings.append(
                            f"Municipi '{municipality}' no trobat a la base de dades sísmica "
                            f"(només Catalunya). Valor ab per defecte: {seismic_result.ab}g. "
                            f"Reviseu manualment."
                        )

                # Radon (zone + CSN coordinate potential)
                if municipality:
                    from .municipal_data import get_radon_info_with_status
                    radon_result = get_radon_info_with_status(municipality)
                    radon_info = radon_result.info
                    if not radon_result.found:
                        self.warnings.append(
                            f"Municipi '{municipality}' no trobat a la base de dades de radó "
                            f"(només Catalunya). Zona per defecte: {radon_info.zone}. "
                            f"Reviseu manualment."
                        )
                    context['radon_zone'] = str(radon_info.zone)
                    if radon_info.zone == 0:
                        context['radon_zone_description'] = ', municipi amb baixes concentracions de gas radó.'
                    elif radon_info.zone == 1:
                        context['radon_zone_description'] = (
                            ', municipi amb concentracions mitjanes de gas radó en edificis tancats. '
                            'Es recomana la implementació de mesures bàsiques de protecció.'
                        )
                    else:  # zone == 2
                        context['radon_zone_description'] = (
                            ', municipi amb concentracions potencialment elevades de gas radó en edificis tancats. '
                            'És obligatòria la implementació de mesures de protecció segons CTE DB HS6.'
                        )

                utm_x = self.report_data.utm_x
                utm_y = self.report_data.utm_y
                if utm_x and utm_y:
                    try:
                        from .csn_radon import get_radon_potential_text
                        csn_text = get_radon_potential_text(utm_x, utm_y)
                        if csn_text:
                            context['csn_radon_text'] = csn_text
                    except Exception as e:
                        import logging
                        logging.getLogger(__name__).warning(f"Could not get CSN radon potential: {e}")

            # Section-derived text variables
            context['materials_depth_text'] = ''
            context['materials_geomech_text'] = ''
            context['conclusions_level_1'] = context.get('materials_level_1', '')

            # Soil levels for section 3.2 (needs section3 data)
            s3_materials = []
            s3_depth_texts = []
            s3_geomech_texts = []
            if sections.get('section3'):
                s3 = sections['section3']
                if hasattr(s3, 'materials_levels'):
                    s3_materials = s3.materials_levels or []
                if hasattr(s3, 'depth_texts'):
                    s3_depth_texts = s3.depth_texts or []
                if hasattr(s3, 'geomech_texts'):
                    s3_geomech_texts = s3.geomech_texts or []

            if self.report_data.soil_levels:
                context['soil_levels'] = []
                for i, level in enumerate(self.report_data.soil_levels):
                    materials_text = s3_materials[i] if i < len(s3_materials) else ''
                    context['soil_levels'].append({
                        'description': level.description,
                        'description_short': _shorten_material_desc(level.description),
                        'ordinal': _catalan_ordinal(level.level_number),
                        'materials_text': materials_text,
                        'depth_text': s3_depth_texts[i] if i < len(s3_depth_texts) else '',
                        'geomech_text': s3_geomech_texts[i] if i < len(s3_geomech_texts) else '',
                    })
            else:
                context['soil_levels'] = [{'description': '', 'description_short': '', 'ordinal': '1er', 'materials_text': '', 'depth_text': '', 'geomech_text': ''}]

            # Conclusions geology intro (dynamic level count)
            num_levels = len(self.report_data.soil_levels) if self.report_data.soil_levels else 1
            if num_levels == 1:
                context['conclusions_levels_detected'] = "Es detecta un sol nivell de materials des del punt de vista geològic/geotècnic en el subsòl del solar en estudi."
            else:
                context['conclusions_levels_detected'] = f"Es detecten {num_levels} nivells de materials des del punt de vista geològic/geotècnic en el subsòl del solar en estudi."

            # === Multi-level table context ===
            from .dpsh_extractor import GeotechCorrelations
            from .cte_geomech import (
                nspt_to_phi, nspt_to_E_kg_cm2, nspt_to_gamma_g_cm3,
                is_rock, rock_params_default, soil_type_to_cohesion,
            )

            soil_levels = self.report_data.soil_levels or []
            dpsh = self.report_data.dpsh

            # Table 5: Soil level summary rows
            context['soil_level_rows'] = []
            for level in soil_levels:
                context['soil_level_rows'].append({
                    'name': f'{_catalan_ordinal(level.level_number)} nivell.',
                    'material': _shorten_material_desc(level.description),
                    'material_short': _shorten_material_desc(level.description),
                })
            if not context['soil_level_rows']:
                context['soil_level_rows'] = [{'name': '', 'material': '', 'material_short': ''}]

            # Table 6: Permeability rows
            context['perm_rows'] = []
            if sections.get('section3') and sections['section3'].taula7_permeability:
                for i, perm in enumerate(sections['section3'].taula7_permeability):
                    ordinal = _catalan_ordinal(i + 1)
                    context['perm_rows'].append({
                        'name': f'{ordinal} nivell',
                        'k_value': perm.k_m_s,
                        'material': _shorten_material_desc(perm.material),
                        'material_short': _shorten_material_desc(perm.material),
                    })
            # Ensure at least one row per soil level (fallback with empty k)
            if not context['perm_rows']:
                for level in soil_levels:
                    context['perm_rows'].append({
                        'name': f'{_catalan_ordinal(level.level_number)} nivell',
                        'k_value': '',
                        'material': _shorten_material_desc(level.description),
                        'material_short': _shorten_material_desc(level.description),
                    })
            if not context['perm_rows']:
                context['perm_rows'] = [{'name': '', 'k_value': '', 'material': '', 'material_short': ''}]

            # Table 7: Sulfates (stays single-row, NOT an array)
            context['sulfate_level_name'] = '1er nivell'
            context['sulfate_value'] = (
                f"{self.report_data.sulfate_mg_kg:.1f}"
                if self.report_data.sulfate_mg_kg is not None else ''
            )
            context['sulfate_baumann'] = '---'
            context['sulfate_classification'] = (
                'No Agressius'
                if self.report_data.sulfate_mg_kg is not None and self.report_data.sulfate_mg_kg < 2000
                else ''
            )

            # Table 8: Seismic rows (one per soil level)
            context['seismic_rows'] = []
            for level in soil_levels:
                avg_n20 = level.n20_average
                # Terrain type based on N20
                if avg_n20 >= 30:
                    terrain_type = 'Tipus II'
                elif avg_n20 >= 10:
                    terrain_type = 'Tipus III'
                else:
                    terrain_type = 'Tipus IV'
                thickness = f"{level.thickness_m:.2f}" if level.thickness_m else ''
                # C coefficient based on terrain type
                c_coeff = {
                    'Tipus I': '1.0', 'Tipus II': '1.3',
                    'Tipus III': '1.6', 'Tipus IV': '2.0',
                }.get(terrain_type, '1.3')
                context['seismic_rows'].append({
                    'num': str(level.level_number),
                    'terrain_type': terrain_type,
                    'thickness': thickness,
                    'c_coeff': c_coeff,
                })
            if not context['seismic_rows']:
                context['seismic_rows'] = [{'num': '', 'terrain_type': '', 'thickness': '', 'c_coeff': ''}]

            # Table 9: Geotechnical parameters rows (one per soil level)
            context['geotech_rows'] = []
            if dpsh and dpsh.tests:
                all_readings = [r for test in dpsh.tests for r in test.readings]
                for level in soil_levels:
                    avg_n20 = level.n20_average
                    # Filter readings by depth range from sondeig_layers
                    level_readings = all_readings  # default: all
                    sondeig_layers = self.user_data.get('sondeig_layers', [])
                    num_user_levels = self.user_data.get('num_soil_levels', 1)
                    # Only filter by sondeig layer depth when user level count matches sondeig layer count
                    if sondeig_layers and num_user_levels == len(sondeig_layers) and level.level_number <= len(sondeig_layers):
                        sl = sondeig_layers[level.level_number - 1]
                        d_from = sl.get('depth_from_m')
                        d_from = 0 if d_from is None else d_from
                        d_to = sl.get('depth_to_m')
                        d_to = 999 if d_to is None else d_to
                        level_readings = [
                            r for r in all_readings
                            if r.depth_m is not None and d_from <= abs(r.depth_m) <= d_to
                        ]

                    # Representative Nb for this level (Eva shows average Nb as integer, e.g. "25-R")
                    if level_readings:
                        # Check for Nb override from geomech_params
                        geomech = self.user_data.get('geomech_params', {})
                        nb_override = geomech.get('Nb', '')
                        if nb_override:
                            nb_display = str(nb_override)
                        else:
                            # Use level's bearing stratum N20 average, convert to Nb
                            avg_nb_display = avg_n20 / 0.83 if avg_n20 else 0
                            has_refusal = any(r.n20 >= 100 for r in level_readings)
                            nb_display = f"{avg_nb_display:.0f}-R" if has_refusal else f"{avg_nb_display:.0f}"
                    else:
                        nb_display = ''

                    # Per-level geotechnical params
                    # Priority: user_data override > CTE correlations
                    geomech = self.user_data.get('geomech_params', {})
                    # Convert N20 → Nb for correlations (Eva: "imprescindible")
                    avg_nb = avg_n20 / 0.83 if avg_n20 else 0
                    # Determine soil type from level description
                    level_soil_type = level.soil_type

                    if geomech.get('gamma') or geomech.get('phi') or geomech.get('E'):
                        # Manual override — use exactly what G3DT specified
                        gamma = geomech.get('gamma') or nspt_to_gamma_g_cm3(avg_n20, level_soil_type)
                        phi = geomech.get('phi') or nspt_to_phi(avg_nb, level_soil_type)
                        E = geomech.get('E') or nspt_to_E_kg_cm2(avg_n20)
                        cohesion = geomech.get('cohesion', 0.0)
                    elif is_rock(avg_n20, level.description):
                        # Rock detected — use CTE rock defaults
                        rock = rock_params_default()
                        gamma = rock['gamma']
                        phi = rock['phi']
                        E = rock['E']
                        cohesion = rock['cohesion']
                    else:
                        # CTE correlations for soil
                        gamma = nspt_to_gamma_g_cm3(avg_n20, level_soil_type)
                        phi = nspt_to_phi(avg_nb, level_soil_type)
                        E = nspt_to_E_kg_cm2(avg_n20)
                        cohesion = soil_type_to_cohesion(level_soil_type)

                    # N display: G3DT may write "R" (refusal) instead of numeric
                    n_display = geomech.get('N') or (str(int(avg_n20)) if avg_n20 else '')
                    # Nb override
                    if geomech.get('Nb'):
                        nb_display = geomech['Nb']

                    context['geotech_rows'].append({
                        'name': f"{_catalan_ordinal(level.level_number)} nivell. {_shorten_material_desc(level.description)}.",
                        'material_short': _shorten_material_desc(level.description),
                        'nb': nb_display,
                        'n': str(n_display),
                        'density': f"{gamma:.2f}",
                        'cohesion': f"{cohesion:.2f}",
                        'phi': f"{phi:.0f}\u00b0",
                        'E': f"{E:.0f}" if isinstance(E, (int, float)) else str(E),
                    })
            if not context['geotech_rows']:
                context['geotech_rows'] = [{'name': '', 'material_short': '', 'nb': '', 'n': '', 'density': '', 'cohesion': '', 'phi': '', 'E': ''}]

            # Determine soil category for Eva's typical ranges (used by both geotech and Qa blocks)
            gp = self.report_data.geotechnical_params
            sl = self.report_data.soil_levels[-1] if self.report_data.soil_levels else None
            soil_cat = 'rock' if (gp and gp.cohesion and gp.cohesion >= 0.5) else (
                'cohesive' if sl and sl.soil_type == 'cohesive' else 'granular')
            ranges = _TYPICAL_RANGES.get(soil_cat, _TYPICAL_RANGES['granular'])

            # Keep old single-value vars for backward compatibility (used in text paragraphs)
            # Use deepest level (bearing stratum) — Eva's reports always show bearing stratum params
            if context['geotech_rows'] and context['geotech_rows'][-1]['name']:
                bearing = context['geotech_rows'][-1]
                context['geotech_level_name'] = bearing['name']
                context['geotech_nb'] = bearing['nb']
                context['geotech_n'] = bearing['n']
                context['geotech_density'] = bearing['density']
                context['geotech_cohesion'] = bearing['cohesion']
                context['geotech_phi'] = bearing['phi']
                context['geotech_E'] = bearing['E']
                # Calculation transparency for Tier C variables
                if gp:
                    n20_src = f"N20={sl.n20_average:.0f}" if sl and sl.n20_average else ""
                    context['_calc_E'] = f"CTE D.23 {n20_src} | Rang Eva: {ranges['E']}" if n20_src else ""
                    context['_calc_phi'] = (
                        f"Schmertmann Nb={sl.n20_average/0.83:.0f} | Rang Eva: {ranges['phi']}"
                    ) if sl and sl.n20_average else ""
                    context['_calc_gamma'] = f"CTE D.27 {sl.soil_type} | Rang Eva: {ranges['gamma']}" if sl else ""
                    context['_calc_cohesion'] = f"Rang Eva: {ranges['c']}"
            else:
                context['geotech_level_name'] = ''
                context['geotech_nb'] = ''
                context['geotech_n'] = ''
                context['geotech_density'] = ''
                context['geotech_cohesion'] = ''
                context['geotech_phi'] = ''
                context['geotech_E'] = ''
                context['_calc_E'] = ''
                context['_calc_phi'] = ''
                context['_calc_gamma'] = ''
                context['_calc_cohesion'] = ''
            # Also keep single perm/soil vars for any paragraph references
            context['soil_level_name'] = context['soil_level_rows'][0]['name'] if context['soil_level_rows'] else ''
            context['soil_level_material'] = context['soil_level_rows'][0]['material'] if context['soil_level_rows'] else ''
            context['perm_level_name'] = context['perm_rows'][0]['name'] if context['perm_rows'] else ''
            context['perm_k_value'] = context['perm_rows'][0]['k_value'] if context['perm_rows'] else ''
            context['perm_material'] = context['perm_rows'][0]['material'] if context['perm_rows'] else ''

            # K30 ballast coefficient — Winkler: K30 = E / (α × B₀)
            # B₀ = 30 cm (standard plate), α = depth influence factor
            if self.report_data.geotechnical_params:
                gp = self.report_data.geotechnical_params
                if gp.cohesion and gp.cohesion > 0:
                    # Rock (α=2.0): K30 = E / 60
                    k30 = gp.E / 60
                    k30_formula = f"E/60 = {gp.E:.0f}/60 (roca, c={gp.cohesion})"
                else:
                    # Granular (α=2.5): K30 = E / 75
                    k30 = gp.E / 75
                    k30_formula = f"E/75 = {gp.E:.0f}/75 (granular)"
                # Round K30 to nearest integer (Eva's practice)
                k30 = round(k30)
                context['k30_value'] = f"{k30:.1f}"
                context['_calc_k30'] = k30_formula
            else:
                context['k30_value'] = ''
                context['_calc_k30'] = ''

            # Terzaghi results
            if self.report_data.terzaghi_result:
                tr = self.report_data.terzaghi_result
                context['qa_value'] = f"{tr.Qa:.2f}"
                context['settlement'] = f"{tr.settlement_cm:.2f}" if tr.settlement_cm else ''
                # Calculation transparency notes
                B = self.user_data.get('footing_width_m', 1.0)
                Df = self.user_data.get('foundation_depth_m', 0.8)
                avg_n20 = self.report_data.dpsh.overall_average_n20 if self.report_data.dpsh else None
                nb = avg_n20 / 0.83 if avg_n20 else None
                # Soil category for Eva's Qa cap range (uses shared soil_cat/ranges)
                # Qa note with Terzaghi-Peck breakdown
                if nb:
                    formula = f"Nb/12={nb:.0f}/12={nb/12:.2f}"
                    if tr.Fw is not None:
                        formula += f" / Fw={tr.Fw:.2f}"
                    if tr.Fd_tp is not None:
                        formula += f" x Fd={tr.Fd_tp:.2f}"
                    if tr.Qa_uncapped is not None:
                        context['_calc_qa'] = f"{formula} = {tr.Qa_uncapped:.2f} | Cap: {tr.Qa:.2f} ({ranges['Qa_cap']})"
                    else:
                        context['_calc_qa'] = f"{formula} = {tr.Qa:.2f} | Rang Eva: {ranges['Qa_cap']}"
                else:
                    context['_calc_qa'] = ""
                # Settlement note with sensitivity +/-25% Es
                if tr.settlement_cm and tr.Es_used:
                    Es = tr.Es_used
                    base = tr.settlement_cm
                    Es_low = Es * 0.75
                    Es_high = Es * 1.25
                    s_low = base * Es / Es_high
                    s_high = base * Es / Es_low
                    context['_calc_settlement'] = (
                        f"Schmertmann Es={Es:.0f}, B={B}m \u2192 {base:.2f} cm"
                        f" | Si Es={Es_low:.0f}: {s_high:.2f} cm"
                        f" | Si Es={Es_high:.0f}: {s_low:.2f} cm"
                    )
                    context['_calc_Es'] = f"Es={Es:.0f} (2.5\u00d7Nb) | \u00b125%: {Es_low:.0f}-{Es_high:.0f}"
                else:
                    context['_calc_settlement'] = ""
                    context['_calc_Es'] = ""
            else:
                context['qa_value'] = ''
                context['settlement'] = ''
                context['_calc_qa'] = ''
                context['_calc_settlement'] = ''
                context['_calc_Es'] = ''

            # Section 4 conditional content (empentes, estabilitat, expansivitat)
            if sections.get('section4'):
                s4 = sections['section4']
                if s4.empentes_paragraph:
                    context['empentes_paragraph'] = s4.empentes_paragraph
                if s4.ka_value is not None:
                    context['ka_value'] = f"{s4.ka_value:.3f}"
                if s4.kp_value is not None:
                    context['kp_value'] = f"{s4.kp_value:.3f}"
                if s4.estabilitat_paragraph:
                    context['estabilitat_paragraph'] = s4.estabilitat_paragraph
                if s4.expansivitat_paragraph:
                    context['expansivitat_paragraph'] = s4.expansivitat_paragraph
                if s4.geologia_summary:
                    context['conclusions_geologia_summary'] = s4.geologia_summary
                if s4.water_statement:
                    context['conclusions_water_statement'] = s4.water_statement
                if s4.aggressivity_statement:
                    context['conclusions_aggressivity_statement'] = s4.aggressivity_statement

            # Defaults for conditional section content
            context.setdefault('empentes_paragraph', '')
            context.setdefault('ka_value', '')
            context.setdefault('kp_value', '')
            context.setdefault('estabilitat_paragraph', '')
            context.setdefault('expansivitat_paragraph', '')
            context.setdefault('conclusions_geologia_summary', '')
            context.setdefault('conclusions_water_statement', '')
            context.setdefault('conclusions_aggressivity_statement', '')

            # Include full structured data for advanced templates
            context['project'] = report_data_to_dict(self.report_data)

        return context

    def render_template(self, context: dict, output_path: Path) -> None:
        """
        Render the docx template with generated content.

        Requires docxtpl library.
        """
        try:
            from docxtpl import DocxTemplate
        except ImportError:
            self.errors.append(
                "docxtpl library not installed. Install with: pip install docxtpl"
            )
            raise

        if not self.template_path.exists():
            self.errors.append(f"Template not found: {self.template_path}")
            raise FileNotFoundError(f"Template not found: {self.template_path}")

        doc = DocxTemplate(str(self.template_path))

        # Add images to context (InlineImage requires the DocxTemplate instance)
        try:
            from .image_manager import ImageManager
            img_mgr = ImageManager(self.project_path, self.report_data, doc)
            image_ctx = img_mgr.build_context()
            context.update(image_ctx)
        except Exception as e:
            self.warnings.append(f"Image insertion failed (report will have placeholders): {e}")

        doc.render(context)
        doc.save(str(output_path))

    def generate(self, output_path: str | Path) -> GenerationResult:
        """
        Main entry point - generate complete report.

        Args:
            output_path: Where to save the generated .docx

        Returns:
            GenerationResult with success status and any errors/warnings
        """
        output_path = Path(output_path)

        # Validate/create output directory
        output_dir = output_path.parent
        if output_dir and not output_dir.exists():
            try:
                output_dir.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                self.errors.append(f"Cannot create output directory '{output_dir}': {e}")
                return GenerationResult(
                    success=False,
                    output_path=None,
                    errors=self.errors.copy(),
                    warnings=self.warnings.copy(),
                )

        # Step 1: Extract project data
        self.extract_project_data()
        if self.errors:
            return GenerationResult(
                success=False,
                output_path=None,
                errors=self.errors.copy(),
                warnings=self.warnings.copy(),
            )

        # Step 2: Build unified report data
        self.build_report_data()
        if not self.report_data:
            return GenerationResult(
                success=False,
                output_path=None,
                errors=self.errors.copy(),
                warnings=self.warnings.copy(),
            )

        # Step 2b: Auto-activate conditional sections before generation
        # (Section4Generator checks these flags to decide what to generate)
        if getattr(self.report_data, 'is_sloped', False):
            if not getattr(self.report_data, 'include_slope_stability', False):
                self.report_data.include_slope_stability = True
                logger.info("Auto-activated slope stability (is_sloped=True)")
            if not getattr(self.report_data, 'include_earth_pressure', False):
                self.report_data.include_earth_pressure = True
                logger.info("Auto-activated earth pressure (is_sloped=True → retaining walls)")

        # Step 3: Generate sections
        sections = self.generate_sections()

        # Step 4: Build template context (maps sections to template variables)
        context = self._build_template_context(sections)

        # Step 5: Render template
        try:
            self.render_template(context, output_path)
        except Exception as e:
            self.errors.append(f"Template rendering failed: {type(e).__name__}: {e}")
            logger.exception("Template rendering failed during render_template")
            return GenerationResult(
                success=False,
                output_path=None,
                errors=self.errors.copy(),
                warnings=self.warnings.copy(),
            )

        return GenerationResult(
            success=True,
            output_path=str(output_path),
            errors=self.errors.copy(),
            warnings=self.warnings.copy(),
        )

    def build_context_preview(self) -> ContextPreviewResult:
        """Build full template context without rendering (for readiness check).

        Runs the same pipeline as generate() — extract, build, sections,
        context — but stops before render_template(). No stages skipped.
        """
        # Step 1: Extract project data
        self.extract_project_data()
        if self.errors:
            return ContextPreviewResult(
                context={},
                errors=self.errors.copy(),
                warnings=self.warnings.copy(),
            )

        # Step 2: Build unified report data
        self.build_report_data()
        if not self.report_data:
            return ContextPreviewResult(
                context={},
                errors=self.errors.copy(),
                warnings=self.warnings.copy(),
            )

        # Step 2b: Auto-activate conditional sections (same as generate())
        if getattr(self.report_data, 'is_sloped', False):
            if not getattr(self.report_data, 'include_slope_stability', False):
                self.report_data.include_slope_stability = True
            if not getattr(self.report_data, 'include_earth_pressure', False):
                self.report_data.include_earth_pressure = True

        # Step 3: Generate sections
        sections = self.generate_sections()

        # Step 4: Build template context
        context = self._build_template_context(sections)

        return ContextPreviewResult(
            context=context,
            errors=self.errors.copy(),
            warnings=self.warnings.copy(),
        )


def main():
    """Command-line interface."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Generate G3DT geotechnical report from project folder',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Generate with minimal input
    python3 -m automation.report_generator ./4001612-bell-lloc -o report.docx

    # With user data file
    python3 -m automation.report_generator ./4001612-bell-lloc \\
        --user-data input.json -o report.docx

    # With custom template
    python3 -m automation.report_generator ./4001612-bell-lloc \\
        --template custom_template.docx -o report.docx
"""
    )

    parser.add_argument(
        'project_path',
        help='Path to project folder'
    )
    parser.add_argument(
        '-u', '--user-data',
        dest='user_data',
        help='Path to user input JSON file'
    )
    parser.add_argument(
        '-t', '--template',
        dest='template',
        help='Path to custom docx template'
    )
    parser.add_argument(
        '-o', '--output',
        required=True,
        help='Output path for generated report'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show detailed output'
    )

    args = parser.parse_args()

    # Create generator
    generator = ReportGenerator(
        project_path=args.project_path,
        user_data=args.user_data,
        template_path=args.template,
    )

    if args.verbose:
        print(f"Project: {generator.project_path}")
        print(f"Template: {generator.template_path}")
        print(f"User data: {args.user_data or '(none)'}")
        print(f"Output: {args.output}")
        print()

    # Generate
    result = generator.generate(args.output)

    # Report results
    if result.warnings:
        print("Warnings:")
        for w in result.warnings:
            print(f"  - {w}")

    if result.errors:
        print("Errors:")
        for e in result.errors:
            print(f"  - {e}")

    if result.success:
        print(f"\nReport generated successfully: {result.output_path}")
        sys.exit(0)
    else:
        print("\nReport generation failed.")
        sys.exit(1)


if __name__ == '__main__':
    main()
