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

from .project_extractor import ProjectExtractor
from .report_data import ReportData, build_report_data, to_dict as report_data_to_dict
from .terzaghi_calculator import TerzaghiCalculator, FootingShape
from .sections import (
    Section1Generator,
    Section2Generator,
    Section3Generator,
    Section4Generator,
)

logger = logging.getLogger(__name__)


def _catalan_ordinal(n: int) -> str:
    """Return Catalan ordinal abbreviation: 1er, 2n, 3r, 4t, 5è, 6è..."""
    ordinals = {1: '1er', 2: '2n', 3: '3r', 4: '4t'}
    return ordinals.get(n, f'{n}è')


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
        self.template_path = Path(template_path) if template_path else self._find_template()
        self.user_data = self._load_user_data(user_data)

        self.project_data: dict = {}
        self.report_data: ReportData | None = None
        self.errors: list[str] = []
        self.warnings: list[str] = []

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

        Returns empty dict if None or loading fails.
        """
        if user_data is None:
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
            # Calculate Terzaghi if we have geotechnical parameters
            terzaghi_result = None
            geotech = self.project_data.get('geotechnical', {})
            if geotech:
                try:
                    calc = TerzaghiCalculator(
                        phi=geotech.get('friction_angle_deg', 30),
                        cohesion=0.0,  # Granular soils
                        gamma=geotech.get('density_g_cm3', 2.0),
                    )
                    # Use user-provided footing dimensions or defaults
                    B = self.user_data.get('footing_width_m', 1.0)
                    Df = self.user_data.get('foundation_depth_m', 0.8)
                    terzaghi_result = calc.calculate_qa(B=B, Df=Df, shape=FootingShape.SQUARE)
                except Exception as e:
                    self.warnings.append(f"Terzaghi calculation failed: {e}")

            # Auto-fill from sondeig_extracted.json: soil levels + sondeig test data
            try:
                sondeig_path = self.project_path / 'validation' / 'sondeig_extracted.json'
                if sondeig_path.exists():
                    with open(sondeig_path, 'r', encoding='utf-8') as f:
                        sondeig_data = json.load(f)
                    sondeig_tests = sondeig_data.get('sondeig_tests', [])
                    if sondeig_tests:
                        # Store full test data for the sondeig summary table
                        self.user_data['sondeig_tests'] = sondeig_tests

                        # Auto-fill soil levels if not already set
                        if self.user_data.get('num_soil_levels', 1) == 1:
                            layers = sondeig_tests[0].get('layers', [])
                            num_layers = len(layers)
                            if num_layers > 0:
                                self.user_data['num_soil_levels'] = num_layers
                                self.user_data['sondeig_layers'] = layers
                                logger.info(
                                    "Auto-filled num_soil_levels=%d from sondeig_extracted.json",
                                    num_layers,
                                )
            except Exception as e:
                self.warnings.append(f"Could not auto-fill from sondeig_extracted.json: {e}")

            self.report_data = build_report_data(
                project_data=self.project_data,
                user_data=self.user_data,
                terzaghi_result=terzaghi_result,
                project_path=str(self.project_path),
            )
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
                num_site_photos = 1  # Fallback default
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
            context['client'] = client_name
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
            context['num_floors'] = self.report_data.num_floors or ''

            # Building structure description from num_floors
            # "en planta baixa" when foundation starts at ground level (PB, PB+P1, etc.)
            # "de soterrani" when there's a basement (PS, etc.)
            num_floors_raw = (self.report_data.num_floors or '').upper()
            if num_floors_raw.startswith('PB'):
                context['building_structure_desc'] = 'en planta baixa'
            elif num_floors_raw.startswith('PS'):
                context['building_structure_desc'] = 'de soterrani'
            else:
                context['building_structure_desc'] = self.report_data.building_type or 'una estructura'

            # Municipality uppercase
            context['municipality_upper'] = (self.report_data.municipality or '').upper()

            # Street split: "Carrer X, 25220 Bell-Lloc" → street_1="Carrer X", street_2="Bell-Lloc d'Urgell"
            street = self.report_data.street_address or ''
            parts = street.split(',', 1)
            context['street_1'] = parts[0].strip() if parts else ''
            context['street_2'] = parts[1].strip().lstrip('0123456789 ') if len(parts) > 1 else ''

            # CTE Classification (original names)
            context['cte_building_class'] = self.report_data.cte_building_class or 'C-0'
            context['cte_soil_class'] = self.report_data.cte_soil_class or 'T-1'
            # CTE Classification (template names)
            context['cte_edificacio'] = self.report_data.cte_building_class or 'C-0'
            context['cte_sol'] = self.report_data.cte_soil_class or 'T-1'

            # Building dimensions for template
            context['plantes'] = self.report_data.num_floors or ''
            context['superficie_parcela'] = (
                f"{self.report_data.superficie_parcela:.0f}"
                if self.report_data.superficie_parcela else ''
            )
            context['superficie_construida'] = (
                f"{self.report_data.superficie_construida:.0f}"
                if self.report_data.superficie_construida else ''
            )

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
                    superficie = self.report_data.superficie_parcela or 600.0
                    auto_adj = get_adjacent_parcels(
                        self.report_data.utm_x,
                        self.report_data.utm_y,
                        superficie,
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

            context['adjacent_north'] = adj.get('north', '')
            context['adjacent_south'] = adj.get('south', '')
            context['adjacent_east'] = adj.get('east', '')
            context['adjacent_west'] = adj.get('west', '')
            context['adjacent_south_street'] = adj.get('south', '')

            # Adjacent formatting with Catalan articles
            def _format_adjacent(direction_cat: str, value: str) -> str:
                if not value:
                    return f'Per la part {direction_cat}, sense informació.'
                v = value.strip().rstrip('.')
                if v.lower().startswith(('carrer ', 'camí ', 'passeig ')):
                    return f'Per la part {direction_cat} amb el {v}.'
                if v.lower().startswith(('avinguda ', 'plaça ', 'ronda ', 'travessia ')):
                    return f'Per la part {direction_cat} amb la {v}.'
                if v.lower().startswith(('parcel·la', 'construcció', 'edificació', 'nau ')):
                    return f'Per la part {direction_cat} amb una {v}.'
                if v.lower().startswith(('solar', 'edifici', 'magatzem', 'terreny')):
                    return f'Per la part {direction_cat} amb un {v}.'
                return f'Per la part {direction_cat} amb {v}.'

            context['adjacent_north_fmt'] = _format_adjacent('nord', adj.get('north', ''))
            context['adjacent_south_fmt'] = _format_adjacent('sud', adj.get('south', ''))
            context['adjacent_east_fmt'] = _format_adjacent('est', adj.get('east', ''))

            # West gets special "I finalment" prefix
            west_val = adj.get('west', '')
            if west_val:
                west_body = _format_adjacent('oest', west_val)
                context['adjacent_west_fmt'] = 'I finalment, p' + west_body[1:]  # "Per" -> "per"
            else:
                context['adjacent_west_fmt'] = _format_adjacent('oest', '')

            # Access street extraction
            access = self.report_data.access_description or ''
            access_match = re.search(r'(?:des del|des de la|pel)\s+(.+?)(?:\.|$)', access, re.IGNORECASE)
            context['access_street'] = access_match.group(1).strip() if access_match else access

            # Site condition
            is_anthropized = getattr(self.report_data, 'is_anthropized', False)
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
                context['dpsh_test_ids'] = ', '.join(dpsh.test_ids)
                context['dpsh_avg_n20'] = f"{dpsh.overall_average_n20:.1f}"

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

            # SPT data
            spt = self.report_data.spt_data or {}
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
            for i in range(6):
                context[f'geology_para_{i+1}'] = ''
            if sections.get('section3'):
                s3 = sections['section3']

                # Geology paragraphs (split marc_geologic by double newline)
                geo_paras = s3.marc_geologic.split('\n\n') if s3.marc_geologic else []
                for i in range(6):
                    key = f'geology_para_{i+1}'
                    context[key] = geo_paras[i] if i < len(geo_paras) else ''

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
                        context['seismic_ab_text'] = ab_match.group(1)

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
                        'ordinal': _catalan_ordinal(level.level_number),
                        'materials_text': materials_text,
                        'depth_text': s3_depth_texts[i] if i < len(s3_depth_texts) else '',
                        'geomech_text': s3_geomech_texts[i] if i < len(s3_geomech_texts) else '',
                    })
            else:
                context['soil_levels'] = [{'description': '', 'ordinal': '1er', 'materials_text': '', 'depth_text': '', 'geomech_text': ''}]

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
                is_rock, rock_params_default,
            )

            soil_levels = self.report_data.soil_levels or []
            dpsh = self.report_data.dpsh

            # Table 5: Soil level summary rows
            context['soil_level_rows'] = []
            for level in soil_levels:
                context['soil_level_rows'].append({
                    'name': f'{_catalan_ordinal(level.level_number)} nivell.',
                    'material': level.description,
                })
            if not context['soil_level_rows']:
                context['soil_level_rows'] = [{'name': '', 'material': ''}]

            # Table 6: Permeability rows
            context['perm_rows'] = []
            if sections.get('section3') and sections['section3'].taula7_permeability:
                for i, perm in enumerate(sections['section3'].taula7_permeability):
                    ordinal = _catalan_ordinal(i + 1)
                    context['perm_rows'].append({
                        'name': f'{ordinal} nivell',
                        'k_value': perm.k_m_s,
                        'material': perm.material,
                    })
            # Ensure at least one row per soil level (fallback with empty k)
            if not context['perm_rows']:
                for level in soil_levels:
                    context['perm_rows'].append({
                        'name': f'{_catalan_ordinal(level.level_number)} nivell',
                        'k_value': '',
                        'material': level.description,
                    })
            if not context['perm_rows']:
                context['perm_rows'] = [{'name': '', 'k_value': '', 'material': ''}]

            # Table 7: Sulfates (stays single-row, NOT an array)
            context['sulfate_level_name'] = '1er nivell'
            context['sulfate_value'] = (
                f"{self.report_data.sulfate_mg_kg:.1f}"
                if self.report_data.sulfate_mg_kg else ''
            )
            context['sulfate_baumann'] = '---'
            context['sulfate_classification'] = (
                'No Agressius'
                if self.report_data.sulfate_mg_kg and self.report_data.sulfate_mg_kg < 2000
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
                    if sondeig_layers and level.level_number <= len(sondeig_layers):
                        sl = sondeig_layers[level.level_number - 1]
                        d_from = sl.get('depth_from_m', 0)
                        d_to = sl.get('depth_to_m', 999)
                        level_readings = [r for r in all_readings if d_from <= abs(r.depth_m) <= d_to]

                    # Nb range for this level
                    if level_readings:
                        nb_values = [r.nb for r in level_readings]
                        nb_min = min(nb_values)
                        nb_max = max(nb_values)
                        has_refusal = any(r.n20 >= 100 for r in level_readings)
                        nb_range = f"{nb_min:.0f}-R" if has_refusal else f"{nb_min:.0f}-{nb_max:.0f}"
                    else:
                        nb_range = ''

                    # Per-level geotechnical params
                    # Priority: user_data override > CTE correlations
                    geomech = self.user_data.get('geomech_params', {})

                    if geomech.get('gamma') or geomech.get('phi') or geomech.get('E'):
                        # Manual override — use exactly what G3DT specified
                        gamma = geomech.get('gamma') or nspt_to_gamma_g_cm3(avg_n20)
                        phi = geomech.get('phi') or nspt_to_phi(avg_n20)
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
                        gamma = nspt_to_gamma_g_cm3(avg_n20)
                        phi = nspt_to_phi(avg_n20)
                        E = nspt_to_E_kg_cm2(avg_n20)
                        cohesion = 0.0

                    # N display: G3DT may write "R" (refusal) instead of numeric
                    n_display = geomech.get('N') or (str(int(avg_n20)) if avg_n20 else '')
                    # Nb override
                    if geomech.get('Nb'):
                        nb_range = geomech['Nb']

                    context['geotech_rows'].append({
                        'name': f"{_catalan_ordinal(level.level_number)} nivell. {level.description}.",
                        'nb': nb_range,
                        'n': str(n_display),
                        'density': f"{gamma:.2f}",
                        'cohesion': f"{cohesion:.2f}",
                        'phi': f"{phi:.0f}\u00b0",
                        'E': f"{E:.0f}" if isinstance(E, (int, float)) else str(E),
                    })
            if not context['geotech_rows']:
                context['geotech_rows'] = [{'name': '', 'nb': '', 'n': '', 'density': '', 'cohesion': '', 'phi': '', 'E': ''}]

            # Keep old single-value vars for backward compatibility (used in text paragraphs)
            if context['geotech_rows'] and context['geotech_rows'][0]['name']:
                context['geotech_level_name'] = context['geotech_rows'][0]['name']
                context['geotech_nb'] = context['geotech_rows'][0]['nb']
                context['geotech_n'] = context['geotech_rows'][0]['n']
                context['geotech_density'] = context['geotech_rows'][0]['density']
                context['geotech_cohesion'] = context['geotech_rows'][0]['cohesion']
                context['geotech_phi'] = context['geotech_rows'][0]['phi']
                context['geotech_E'] = context['geotech_rows'][0]['E']
            else:
                context['geotech_level_name'] = ''
                context['geotech_nb'] = ''
                context['geotech_n'] = ''
                context['geotech_density'] = ''
                context['geotech_cohesion'] = ''
                context['geotech_phi'] = ''
                context['geotech_E'] = ''
            # Also keep single perm/soil vars for any paragraph references
            context['soil_level_name'] = context['soil_level_rows'][0]['name'] if context['soil_level_rows'] else ''
            context['soil_level_material'] = context['soil_level_rows'][0]['material'] if context['soil_level_rows'] else ''
            context['perm_level_name'] = context['perm_rows'][0]['name'] if context['perm_rows'] else ''
            context['perm_k_value'] = context['perm_rows'][0]['k_value'] if context['perm_rows'] else ''
            context['perm_material'] = context['perm_rows'][0]['material'] if context['perm_rows'] else ''

            # K30 ballast coefficient
            if self.report_data.geotechnical_params:
                k30 = self.report_data.geotechnical_params.E / 100
                context['k30_value'] = f"{k30:.1f}"
            else:
                context['k30_value'] = ''

            # Terzaghi results
            if self.report_data.terzaghi_result:
                tr = self.report_data.terzaghi_result
                context['qa_value'] = f"{tr.Qa:.2f}"
                context['settlement'] = f"{tr.settlement_cm:.2f}" if tr.settlement_cm else ''

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
            self.errors.append(f"Template rendering failed: {e}")
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
