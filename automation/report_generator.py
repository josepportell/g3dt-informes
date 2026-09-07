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
from .spt_n_column import NO_SPT, assign_spt_n30
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


def _level_material(level) -> str:
    """Text de material d'un nivell per a una cel·la de taula.

    Fase 8b: quan la descripcio ve de la lectura (via A) ja es la redaccio que
    Eva ha triat entre els candidats — hi va LITERAL. Nomes s'escurça la
    descripcio automatica derivada del sondeig/DPSH.
    """
    desc = getattr(level, 'description', '') or ''
    if getattr(level, 'description_verbatim', False):
        return desc
    return _shorten_material_desc(desc)


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


def insitu_table_range(has_sondeig: bool, first: int = 3, has_spt_table: bool = True, lang: str = 'ca') -> tuple[str, int]:
    """(«3 i 4» / «3, 4 i 5», última taula) del bloc d'assaigs in situ: DPSH + sondeig (si n'hi ha) + SPT/MA.

    L'Eva numera TAULES (7/7 signats): «Taula 3 i 4» sense sondeig, «Taula 3, 4 i 5» amb sondeig. `lang='es'`
    → «3 y 4». Compartit pel generador (`_build_numbering_context`) i el wizard (`_compute_narrative_prefills`).
    """
    n = 1 + (1 if has_sondeig else 0) + (1 if has_spt_table else 0)
    nums = [str(first + i) for i in range(n)]
    conj = 'y' if lang == 'es' else 'i'
    text = nums[0] if n == 1 else f"{', '.join(nums[:-1])} {conj} {nums[-1]}"
    return text, first + n - 1


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

            # P5 (2026-09-07): sense sondeig, les capes surten de la taula `soil_levels` LLEGIDA (tall de
            # correlació, via A), no del segmentador DPSH. Es posen a `user_data` com les del sondeig perquè
            # el càlcul inicial (Terzaghi-Peck del nivell portant) i les files de la taula geotècnica vegin la
            # mateixa geometria que `build_report_data`. L'N20 per capa l'omple `build_report_data` (té el DPSH).
            if not self.user_data.get('sondeig_layers'):
                try:
                    from .report_data import lectura_sondeig_layers
                    lectura_layers = lectura_sondeig_layers(self.user_data, self.project_path, tables=self.lectura_tables)
                    if lectura_layers:
                        self.user_data['sondeig_layers'] = lectura_layers
                        if 'num_soil_levels' not in self.user_data:
                            self.user_data['num_soil_levels'] = len(lectura_layers)
                        logger.info("P5: %d capes des de la lectura (soil_levels de/a): %s", len(lectura_layers),
                                    [(l['depth_from_m'], l['depth_to_m']) for l in lectura_layers])
                except Exception as e:
                    self.warnings.append(f"P5: no s'han pogut derivar les capes de la lectura: {e}")

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

            # P5: la geometria que ha usat el càlcul (sondeig, lectura o segmentador) també per a Terzaghi-Peck
            # i les files de la taula geotècnica. Abans, sense `sondeig_layers` a `user_data`, el Qa imprès
            # sortia amb l'N20 GLOBAL (limitació coneguda del DECISION-LOG 2026-09-06 (vespre)): Anciles amb
            # pous a 2,9 usava Nb 17,6 (global) en lloc dels 26,3 de les graves portants.
            if not self.user_data.get('sondeig_layers') and getattr(self.report_data, 'sondeig_layers_used', None):
                self.user_data['sondeig_layers'] = list(self.report_data.sondeig_layers_used)

            # P5: gruix «fins a la fondària investigada» amb la fondària de rebuig IMPRESA en aquest informe
            # (files DPSH llegides «-1.69»; si no, l'anotació «R:» del full de camp; l'Excel arrodoneix al tram
            # de 0,20 → 1,80): Alcoletge 1,69 − 1,40 = 0,29* com el signat.
            self._refresh_open_thickness()

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
                            foundation_depth=float(Df) if Df else 0.8,
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

            # Fase 8b: litologia llegida (i triada per Eva) -> descripcio dels
            # nivells. Es fa DESPRES dels calculs a proposit: el tipus de sol i
            # els parametres ja estan decidits sobre `sondeig_layers`; aqui nomes
            # canvia el TEXT que veura Eva a les taules i a la narrativa.
            self._apply_lectura_soil_levels()

            return self.report_data

        except Exception as e:
            self.errors.append(f"Error building report data: {e}")
            return None

    # === Fase 8b: taules llegides (via A) ===

    @property
    def lectura_tables(self) -> dict:
        """Files de taula llegides per la via A, llestes per al `.docx`.

        Ordre de preferencia:
          1. `user_data['lectura_tables']` — el que Eva va desar al wizard
             (les seves tries ja aplicades). Congelat: un canvi posterior de
             `_decisions.json` no li mou l'informe sota els peus.
          2. `validation/lectura/_decisions.json` del projecte — perque un
             informe generat sense passar pel wizard (CLI, harness) tambe
             surti amb les taules llegides.

        A la via B cap de les dues existeix i retorna `{}`: comportament
        identic al d'avui.
        """
        cached = getattr(self, '_lectura_tables_cache', None)
        if cached is not None:
            return cached
        tables = self.user_data.get('lectura_tables')
        if not isinstance(tables, dict) or not tables:
            try:
                from .lectura.tables_report import load_project_tables
                tables = load_project_tables(
                    self.project_path, self.user_data.get('lectura_selections'),
                )
            except Exception as e:  # pragma: no cover - defensiu
                self.warnings.append(f"Could not load lectura tables: {e}")
                tables = {}
        self._lectura_tables_cache = tables if isinstance(tables, dict) else {}
        return self._lectura_tables_cache

    def _apply_lectura_tables(self, context: dict) -> None:
        """Fase 8b — bolca les taules llegides al context de la plantilla.

        Cada bloc es substitueix sencer i nomes si la lectura en te files;
        els blocs que la lectura no ha trobat es queden com estaven (via B).
        `superficie_construida` i la capçalera de la mostra de laboratori hi
        van tambe: son camps que el wizard NO te com a input i que, sense
        aquest pont, no arribarien mai a l'informe.
        """
        tables = self.lectura_tables
        if not tables:
            return
        applied = []
        for key in ('dpsh_tests', 'sondeig_tests', 'spt_ma_tests'):
            rows = tables.get(key)
            if rows:
                context[key] = rows
                applied.append(f"{key}={len(rows)}")
        spt_rows = tables.get('spt_ma_tests') or []
        if spt_rows:
            first = spt_rows[0]
            context['spt_test_id'] = first.get('test_id', '')
            context['spt_location'] = first.get('location', '')
            context['spt_depth_range'] = first.get('depth_range', '')
            context['spt_n30'] = first.get('n30', '')
            context['spt_lithology'] = first.get('lithology', '')
        superficie = tables.get('superficie_construida')
        if superficie and not context.get('superficie_construida'):
            context['superficie_construida'] = superficie
            applied.append('superficie_construida')
        lab = tables.get('lab') or {}
        for ctx_key, lab_key in (
            ('lab_sample_id', 'sample_id'),
            ('lab_location', 'location'),
            ('lab_depth', 'depth'),
        ):
            if lab.get(lab_key) and not context.get(ctx_key):
                context[ctx_key] = lab[lab_key]
                applied.append(ctx_key)
        if applied:
            logger.info("Fase 8b: taules de la lectura aplicades (%s)", ', '.join(applied))

    def _apply_lectura_soil_levels(self) -> None:
        """Aplica la litologia llegida a `report_data.soil_levels`.

        Alineacio per NUMERO de nivell (`levels_by_number`), no per index: l'or
        pot portar una capa vegetal sense numerar que l'informe no te com a
        nivell propi. Les fondaries `de`/`a` NO es toquen (son entrada de
        calcul: gruixos, taula sismica) — fora d'abast de la Fase 8b.
        """
        levels = (self.lectura_tables or {}).get('soil_levels')
        if not levels or not self.report_data or not self.report_data.soil_levels:
            return
        from .lectura.tables_report import levels_by_number
        by_number = levels_by_number(levels)
        if not by_number:
            return
        applied = 0
        for level in self.report_data.soil_levels:
            row = by_number.get(level.level_number)
            litologia = (row or {}).get('litologia')
            if not litologia:
                continue
            level.description = litologia
            # Text ja triat per Eva: va literal a les cel·les, sense escurçar.
            level.description_verbatim = True
            applied += 1
        if applied:
            logger.info("Fase 8b: %d nivell(s) amb litologia de la lectura", applied)
        missing = len(self.report_data.soil_levels) - applied
        if missing > 0:
            self.warnings.append(
                f"Lectura: {missing} nivell(s) de l'informe sense litologia llegida "
                f"(llegits: {sorted(by_number)}); es manté la descripció automàtica."
            )

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

        # Vistes generals (peça 3, 2026-09-07): el bloc (taula de 2 fotos + peu) és CONDICIONAL. 4/7 signats no el
        # porten (la Fotografia 1 hi és la màquina); Bell-lloc 2 fotos, Rubí 1 (Google Earth), Vilanova 1. Defecte: les
        # fotos de vista general que l'Eva ha triat a la pestanya de fotos (`photo_selection.json` amb source=user); si
        # no, 0. `num_site_photos` del wizard mana. Abans: sempre 2 («Eva always places 2 side-by-side photos», fals a
        # 4/7) i la numeració de la màquina i dels materials arrossegava +2.
        from .narrative_criteria import language_for_report, photo_site_caption
        num_site_photos = self.user_data.get('num_site_photos')
        if num_site_photos in (None, ''):
            num_site_photos = self._site_photos_from_user_selection()
        try:
            num_site_photos = max(0, min(2, int(num_site_photos or 0)))
        except (TypeError, ValueError):
            num_site_photos = 0
        photo_counter += num_site_photos
        photo_site_text = photo_site_caption(num_site_photos, language_for_report(self.report_data, self.user_data))

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

        # In-situ test tables («Taula 3 i 4. Resum dels assaigs in situ realitzats»): l'Eva compta TAULES,
        # no assaigs (7/7 signats, 2026-09-07): DPSH (1) + sondeig (1 si n'hi ha) + SPT/MA (1, la plantilla
        # la imprimeix sempre) → «3 i 4» sense sondeig (Rubí, Linyola, Alcoletge, Vilanova), «3, 4 i 5» amb
        # sondeig (Castellar, Bell-lloc, Anciles). Abans: nombre d'assaigs DPSH (3 DPSH → «3, 4 i 5», 4/7 X).
        table_dpsh_range, table_counter = insitu_table_range(has_sondeig, first=table_counter + 1)
        _ = num_dpsh_tests  # no decideix la numeració

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
            '_num_site_photos': num_site_photos,
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

    def _refresh_open_thickness(self) -> None:
        """Recalcula `thickness_m` dels nivells `thickness_open` amb la fondària màxima assolida IMPRESA."""
        rd = self.report_data
        if not rd or not rd.soil_levels or not any(getattr(lv, 'thickness_open', False) for lv in rd.soil_levels):
            return
        reached = 0.0
        for row in (self.lectura_tables or {}).get('dpsh_tests') or []:
            try:
                reached = max(reached, abs(float(str(row.get('depth', '')).replace(',', '.'))))
            except (TypeError, ValueError):
                continue
        if reached <= 0 and rd.dpsh and rd.dpsh.tests:
            reached = max((t.depth_reached for t in rd.dpsh.tests), default=0.0)
        if reached <= 0:
            return
        for lv in rd.soil_levels:
            if getattr(lv, 'thickness_open', False) and reached > lv.depth_from_m:
                lv.thickness_m = round(reached - lv.depth_from_m, 2)

    def _signature_date(self):
        """`user_data['data_signatura']` (ISO `YYYY-MM-DD` o `DD/MM/YYYY`) si és vàlida; si no, `report_date`."""
        from datetime import date, datetime
        raw = self.user_data.get('data_signatura')
        if raw not in (None, ''):
            text = str(raw).strip()
            for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
                try:
                    return datetime.strptime(text[:10], fmt).date()
                except ValueError:
                    continue
            self.warnings.append(f"Data de signatura no reconeguda («{text}»): s'usa la data d'avui")
        rd = getattr(self.report_data, 'report_date', None)
        return rd or date.today()

    def _site_photos_from_user_selection(self) -> int:
        """Fotos de vista general triades per l'Eva a la pestanya de fotos (`validation/photo_selection.json`,
        source=user: `site_1`/`site_2` no nuls). Cap tria explícita → 0 (la selecció automàtica/IA sempre omple els dos
        forats i no diu res del que l'Eva vol imprimir)."""
        sel_path = self.project_path / 'validation' / 'photo_selection.json'
        if not sel_path.exists():
            return 0
        try:
            data = json.loads(sel_path.read_text(encoding='utf-8'))
        except Exception:
            return 0
        if not isinstance(data, dict) or data.get('source') != 'user':
            return 0
        return sum(1 for k in ('site_1', 'site_2') if data.get(k))

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
            # Primera ranura de la plantilla («El dia {{ data_camp_inici_text }}, es va visitar l'obra»): nomes el
            # primer dia; la segona («s'ha realitzat el dia {{ data_camp_text }}») porta tots els dies (Josep 2026-09-05;
            # els signats de Bell-lloc: «El dia 1 d'octubre» / «el dia 1 i 6 d'octubre»).
            from .dpsh_extractor import first_field_day_text
            context['data_camp_inici_text'] = first_field_day_text(
                self.report_data.field_work_dates, self.report_data.field_work_dates_text)
            # Data de signatura (bloc 1, 2026-09-07): la que l'Eva escriu al wizard (`data_signatura`, ISO);
            # si no, la data de l'informe (avui). Mateix format que la data de camp («29 d'octubre de 2025»:
            # «d'» davant vocal, dia sense zero), que és com la signa (0/7 abans: «06 de setembre de 2026»).
            from .dpsh_extractor import format_dates_catalan
            d = self._signature_date()
            context['data_signatura_text'] = format_dates_catalan([d.isoformat()])

            # Architect
            context['architect_name'] = self.report_data.architect_name or ''
            context['architect_company'] = self.report_data.architect_company or ''
            context['architect_name_upper'] = (self.report_data.architect_name or '').upper()

            # Building
            context['building_type'] = self.report_data.building_type or ''
            context['building_type_lower'] = (self.report_data.building_type or '').lower()
            context['num_floors'] = format_floor_notation(self.report_data.num_floors or '')

            # Building structure: clàusula sencera després de «…construcció d'una estructura » per criteri
            # (`narrative_criteria.building_structure_clause`, 2026-09-06): PB sol → (a) «en planta baixa, i per tant…»;
            # amb pis → (b) «sense nivell de soterrani, i per tant…»; soterrani → (c). El valor del wizard (Eva) mana;
            # els valors curts antics («en planta baixa») es mapegen a la clàusula. Abans: `building_type` sencer dins
            # la frase quan les plantes eren buides (Alcoletge).
            from .narrative_criteria import building_structure_clause, language_for_report
            _lang = language_for_report(self.report_data, self.user_data)
            context['report_language'] = _lang
            _bsd = building_structure_clause(
                self.report_data.num_floors, getattr(self.report_data, 'has_basement', None), _lang,
                current=self.user_data.get('building_structure_desc'),
            )
            context['building_structure_desc'] = _bsd.value
            context['_narr_building_structure'] = _bsd.to_dict()

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
            # Referències cadastrals del PROJECTE (lectura, pel portal: `cadastral_refs`; 2026-09-06, peça 2):
            # manen sobre l'UTM del punt de màquina i permeten adjacents sense UTM (Rubí, Vilanova, Anciles).
            from .parcel_context import parse_rc_list
            _rc_list = parse_rc_list(self.user_data.get('cadastral_refs') or getattr(self.report_data, 'cadastral_ref', None))
            context['_parcel_rcs'] = _rc_list
            _has_utm = bool(self.report_data.utm_x and self.report_data.utm_y)
            if any_still_empty and (_rc_list or _has_utm):
                try:
                    from .cadastre_adjacents import get_adjacent_parcels, CadastreError
                    from .report_data import _eval_numeric
                    superficie = _eval_numeric(self.report_data.superficie_parcela) or 600.0
                    rc14 = _rc_list or getattr(self.report_data, 'cadastral_ref', None)
                    municipality = self.report_data.municipality
                    auto_adj = get_adjacent_parcels(
                        self.report_data.utm_x if _has_utm else None,
                        self.report_data.utm_y if _has_utm else None,
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
            # 2026-09-06 (peça 2): «Situat entre X i Y» de la lectura tal qual, carrers duplicats pel nom normalitzat
            # fora («Carrer Arbrells» ≡ «Carrer dels Arbrells»), municipi del padró («Bell-lloc d'Urgell»).
            from .narrative_criteria import location_sentence_from_streets
            context['location_sentence'] = location_sentence_from_streets(
                context.get('street_1', ''), second_street, municipality, _lang,
            )

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
            _acc_user = str(self.user_data.get('access_street') or '').strip()   # camp del wizard (peça 3)
            if _acc_user:
                context['access_street'] = _acc_user
            if not context['access_street']:
                # 2026-09-06 (peça 2): el costat que és carrer → «carrer adjacent situat al sud» (+ candidats)
                from .adjacent_formatter import access_street_from_adjacents
                _acc, _acc_cands = access_street_from_adjacents(adj, context.get('street_1', ''), _lang)
                context['access_street'] = _acc
                context['_narr_access'] = {'value': _acc, 'candidates': _acc_cands}

            # Introducció dels adjacents (2.1.1, 7/7 signats): «La parcel·la objecte d'estudi es situa al {nord} del
            # municipi de {Municipi}, pren una morfologia {rectangular} i limita:» — posició des del centre del municipi
            # (Nominatim, cache) i forma pel polígon del Cadastre; `site_position`/`parcel_shape` del wizard manen.
            try:
                from .narrative_criteria import municipality_proper
                from .parcel_context import (adjacent_intro, centroid, municipality_centre_utm,
                                             position_in_municipality, shape_word)
                _poly: list = []
                if _rc_list:
                    from .cadastre_adjacents import project_polygon
                    _poly = project_polygon(_rc_list)
                _cen = centroid(_poly) if _poly else (
                    (self.report_data.utm_x, self.report_data.utm_y) if _has_utm else None)
                _pos = (self.user_data.get('site_position') or '').strip() or None
                if not _pos and _cen and municipality:
                    _pos = position_in_municipality(
                        _cen, municipality_centre_utm(municipality, self.user_data.get('province', '') or ''), _lang)
                _shape = (self.user_data.get('parcel_shape') or '').strip() or shape_word(_poly, _lang)
                context['adjacent_intro'] = adjacent_intro(_pos, municipality_proper(municipality), _shape, _lang)
                context['_narr_parcel'] = {'position': _pos, 'shape': _shape, 'centroid': _cen, 'rcs': _rc_list}
            except Exception as e:
                self.warnings.append(f"Introducció dels adjacents: {e}")
                context.setdefault('adjacent_intro', '')

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

            # Site condition: FRASE SENCERA per criteri (`narrative_criteria.site_condition_sentence`, 2026-09-06):
            # pendent > 10 % → «Tot i no ser un solar pla…»; antropitzat → «Degut a que…»; si no «Com que es tracta
            # d'un solar pla…». La plantilla ja no porta la capçalera fixa «Degut a que es tracta d'un solar {{ }}».
            # El valor del wizard (Eva o `computed`) mana si és una frase; els valors curts antics («pla») es recalculen.
            from .narrative_criteria import site_condition_sentence
            _slope_pct = context.get('slope_percent') or getattr(self.report_data, 'slope_percent', None)
            _sc = site_condition_sentence(_slope_pct, getattr(self.report_data, 'is_anthropized', None), _lang)
            _sc_user = str(self.user_data.get('site_condition') or '').strip()
            if len(_sc_user.split()) >= 4:
                context['site_condition'] = _sc_user
            else:
                context['site_condition'] = _sc.value
            context['_narr_site_condition'] = _sc.to_dict()

            # Estat del solar per criteri (peça 3, 2026-09-07; `narrative_criteria.site_description_sentence`): NOMÉS el
            # bloc 2 de «2.1.2» (l'accés, «En solars propers…» i «Destacar…» ja són text fix de la plantilla). Fets:
            # construcció pròpia al Cadastre (DNPRC de les referències del projecte) i pendent ICGC. El text de l'Eva
            # al wizard mana. Abans: `site_description` buit a la via A (7/7 NO_DATA).
            from .narrative_criteria import site_description_sentence
            _own = None
            try:
                from .parcel_context import own_parcel_buildings
                _own = own_parcel_buildings(context.get('_parcel_rcs') or [])
            except Exception as e:
                self.warnings.append(f"Construccions de la parcel·la pròpia (DNPRC): {e}")
            _sd = site_description_sentence(_slope_pct, _own, _lang, current=self.report_data.site_description)
            context['site_description'] = _sd.value
            context['_narr_site_description'] = _sd.to_dict()
            context['_own_parcel_building'] = _own

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
            # La taula SPT/MA de la plantilla es un bucle (pot tenir mes d'una
            # fila: Anciles en te 3). Per defecte, la fila unica de sempre —
            # tambe quan es buida, per no canviar la sortida de la via B.
            context['spt_ma_tests'] = [{
                'test_id': context['spt_test_id'],
                'location': context['spt_location'],
                'depth_range': context['spt_depth_range'],
                'n30': context['spt_n30'],
                'lithology': context['spt_lithology'],
            }]

            # --- Fase 8b: les taules llegides manen sobre les de la via B ----
            # Substitucio EN BLOC (no cel·la a cel·la): les files llegides son
            # les del full de camp/annex, amb la cota per punt i la fondaria
            # exacta del peu "Rebuig a", que es el que Eva escriu a l'informe.
            self._apply_lectura_tables(context)

            # Lab data - auto-fill from lab PDF if not provided (una sola lectura del GTL: també dona el bloc
            # «ASSAIGS REALITZATS» per a `lab_tests_text`, peça 3)
            _lab_results = None
            try:
                from .lab_extractor import extract_lab_results
                _lab_results = extract_lab_results(self.project_path)
            except (ImportError, Exception) as e:
                self.warnings.append(f"Could not extract lab results from PDF: {e}")
            if not self.report_data.lab_tests and _lab_results is not None:
                try:
                    lab_results = _lab_results
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
            # Assaigs realitzats per criteri (peça 3, 2026-09-07; `narrative_criteria.lab_tests_lines`): la llista del
            # bloc «ASSAIGS REALITZATS» del GTL amb el vocabulari de l'Eva («1 assaig de contingut en sulfats UNE 83963 :
            # 2008» sol; llista granulometria → Atterberg → Lambe → sulfats). Abans: el `type` del primer assaig
            # («Contingut en sulfats solubles UNE 83963:2008», que l'Eva no escriu mai). El wizard mana.
            from .narrative_criteria import lab_tests_lines
            _lab_user = str(self.user_data.get('lab_tests_text') or '').strip()
            _lt = lab_tests_lines(getattr(_lab_results, 'lab_tests_text', '') if _lab_results else '', _lang)
            context['lab_tests_text'] = _lab_user or _lt.value or lab.get('type', '')
            context['_narr_lab_tests'] = _lt.to_dict()

            # Geology paragraphs from section 3
            context['materials_level_1'] = ''
            context['materials_intro'] = ''
            context['seismic_ab_text'] = ''
            context['radon_zone'] = '1'
            context['radon_zone_description'] = ''
            context['radon_sentence'] = ''
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
                    # Frase sencera del radó per criteri (`narrative_criteria.radon_sentence`, 2026-09-06): zona 0 →
                    # «no pertany a cap municipi…» (Linyola), municipi en majúscules amb «de/d'». La cua antiga
                    # («, municipi amb concentracions mitjanes… Es recomana…») no és de cap signat: buida.
                    from .narrative_criteria import radon_sentence
                    _rs = radon_sentence(radon_info.zone, municipality, _lang)
                    context['radon_sentence'] = _rs.value
                    context['_narr_radon'] = _rs.to_dict()
                    context['radon_zone_description'] = ''

                # `csn_radon_text` (cartografia CSN per coordenades) NO s'emet: el paràgraf del CSN ja és text fix de la
                # plantilla (p474) i el generador l'imprimia dues vegades. Cap signat porta el text de coordenades.
                context['csn_radon_text'] = ''

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
                        'description_short': _level_material(level),
                        'ordinal': _catalan_ordinal(level.level_number),
                        'materials_text': materials_text,
                        'depth_text': s3_depth_texts[i] if i < len(s3_depth_texts) else '',
                        'geomech_text': s3_geomech_texts[i] if i < len(s3_geomech_texts) else '',
                    })
            else:
                context['soil_levels'] = [{'description': '', 'description_short': '', 'ordinal': '1er', 'materials_text': '', 'depth_text': '', 'geomech_text': ''}]

            # Conclusions geology intro (dynamic level count)
            num_levels = len(self.report_data.soil_levels) if self.report_data.soil_levels else 1
            from .narrative_criteria import levels_detected
            context['conclusions_levels_detected'] = levels_detected(num_levels, context.get('report_language', 'ca'))

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
                    'material': _level_material(level),
                    'material_short': _level_material(level),
                })
            if not context['soil_level_rows']:
                context['soil_level_rows'] = [{'name': '', 'material': '', 'material_short': ''}]

            # Table 6: Permeability rows
            context['perm_rows'] = []
            if sections.get('section3') and sections['section3'].taula7_permeability:
                # Fase 8b: quan el nivell porta litologia llegida, el text de
                # la fila de permeabilitat es el mateix (mateix nivell, mateix
                # material) — si no, la taula de nivells i aquesta dirien coses
                # diferents del mateix estrat.
                levels_by_num = {lv.level_number: lv for lv in soil_levels}
                for i, perm in enumerate(sections['section3'].taula7_permeability):
                    ordinal = _catalan_ordinal(i + 1)
                    lv = levels_by_num.get(i + 1)
                    material = (
                        _level_material(lv)
                        if lv is not None and getattr(lv, 'description_verbatim', False)
                        else _shorten_material_desc(perm.material)
                    )
                    context['perm_rows'].append({
                        'name': f'{ordinal} nivell',
                        'k_value': perm.k_m_s,
                        'material': material,
                        'material_short': material,
                    })
            # Ensure at least one row per soil level (fallback with empty k)
            if not context['perm_rows']:
                for level in soil_levels:
                    context['perm_rows'].append({
                        'name': f'{_catalan_ordinal(level.level_number)} nivell',
                        'k_value': '',
                        'material': _level_material(level),
                        'material_short': _level_material(level),
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

            # P3 (2026-09-06): criteris per nivell (règim per Nb i rebuig, litologia) — es
            # calculen un cop i serveixen la taula sísmica (8) i la geotècnica (9).
            from .geotech_criteria import geotech_by_criteria
            level_criteria: dict[int, Any] = {}
            level_refusal: dict[int, bool] = {}
            if dpsh and dpsh.tests:
                from .report_data import _level_has_refusal
                for level in soil_levels:
                    # Rebuig dins del rang del NIVELL de l'informe (criteri de la cel·la «Nb»: «25-R»)
                    _ref = _level_has_refusal(dpsh, level)
                    level_refusal[level.level_number] = _ref
                    _n20 = level.n20_average or 0
                    level_criteria[level.level_number] = geotech_by_criteria(
                        _n20 / 0.83 if _n20 else 0, _n20, level.soil_type, level.description, _ref,
                    )

            # Table 8: Seismic rows (one per soil level)
            context['seismic_rows'] = []
            for level in soil_levels:
                avg_n20 = level.n20_average
                crit = level_criteria.get(level.level_number)
                if crit is not None:
                    # Tipus NCSE-02 per règim (roca/dens II, mitjà III, fluix IV)
                    terrain_type, c_coeff = crit.seismic_type, crit.seismic_C
                else:
                    if avg_n20 >= 30:
                        terrain_type = 'Tipus II'
                    elif avg_n20 >= 10:
                        terrain_type = 'Tipus III'
                    else:
                        terrain_type = 'Tipus IV'
                    c_coeff = {
                        'Tipus I': '1.0', 'Tipus II': '1.3',
                        'Tipus III': '1.6', 'Tipus IV': '2.0',
                    }.get(terrain_type, '1.3')
                thickness = f"{level.thickness_m:.2f}" if level.thickness_m else ''
                if thickness and getattr(level, 'thickness_open', False):
                    thickness += '*'  # «fins a la fondària investigada» (P5: Linyola 1.30*, Alcoletge 0.29*)
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
            spt_n_by_level: dict[int, str] = {}
            if dpsh and dpsh.tests:
                all_readings = [r for test in dpsh.tests for r in test.readings]
                # P0 (2026-09-06): la columna «N» és l'N30 de l'SPT del nivell, mai la
                # mitjana N20 del DPSH (7/7 signats). Font: les files de la taula SPT/MA
                # tal com s'imprimeixen en aquest mateix informe (lectura via A si n'hi
                # ha, si no la fila de la via B), perquè les dues taules diguin el mateix.
                spt_n_by_level, spt_n_notes = assign_spt_n30(
                    context.get('spt_ma_tests') or [], soil_levels,
                )
                for note in spt_n_notes:
                    self.warnings.append(f"Columna N (SPT): {note}")
                    logger.warning("Columna N (SPT): %s", note)
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
                            # «-R» si el DPSH rebutja dins del NIVELL (mateix criteri que el règim); mai en un
                            # rebliment (el rebuig hi és el substrat: Alcoletge signat «5-0», sense R)
                            has_refusal = level_refusal.get(level.level_number, any(r.n20 >= 100 for r in level_readings))
                            _crit_lv = level_criteria.get(level.level_number)
                            if _crit_lv is not None and getattr(_crit_lv, 'klass', '') == 'rebliment':
                                has_refusal = False
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

                    # P3: criteri del nivell (candidats amb procedència); l'override mana per camp
                    crit = level_criteria.get(level.level_number)
                    if crit is None:
                        crit = geotech_by_criteria(avg_nb, avg_n20, level_soil_type, level.description,
                                                   level_refusal.get(level.level_number,
                                                                     any(r.n20 >= 100 for r in level_readings)))
                    E_display = crit.E_display
                    if geomech.get('gamma') or geomech.get('phi') or geomech.get('E'):
                        # Manual override — use exactly what G3DT specified
                        gamma = geomech.get('gamma') or crit.gamma
                        phi = geomech.get('phi') or crit.phi
                        E = geomech.get('E') or crit.E
                        if geomech.get('E'):
                            E_display = str(geomech.get('E'))
                        cohesion = geomech.get('cohesion', 0.0)
                    else:
                        gamma, phi, E, cohesion = crit.gamma, crit.phi, crit.E, crit.cohesion

                    # N display: N30 de l'SPT del nivell («R» si rebutja, «--» si al
                    # nivell no hi ha SPT). L'override expert `geomech_params.N` mana.
                    n_display = geomech.get('N') or spt_n_by_level.get(level.level_number, NO_SPT)
                    # Nb override
                    if geomech.get('Nb'):
                        nb_display = geomech['Nb']

                    context['geotech_rows'].append({
                        'name': f"{_catalan_ordinal(level.level_number)} nivell. {_level_material(level).rstrip('.')}.",
                        'material_short': _level_material(level),
                        'nb': nb_display,
                        'n': str(n_display),
                        'density': f"{gamma:.2f}",
                        'cohesion': f"{cohesion:.2f}",
                        'phi': f"{phi:.0f}\u00b0",
                        'E': E_display if E_display else (f"{E:.0f}" if isinstance(E, (int, float)) else str(E)),
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
                # Calculation transparency notes
                B = self.user_data.get('footing_width_m', 1.0)
                Df = self.user_data.get('foundation_depth_m', 0.8)
                # Assentament per CRITERI (2026-09-06, `automation/settlement_criteria.py`): frase per
                # règim del nivell portant (granular → valor; roca/cohesiu o < 1,0 → genèrica) i Es amb
                # candidats (2,5×N SPT del nivell → 2,5×Nb del nivell → E). Substitueix el 2,5×Nb global
                # del càlcul inicial; l'«Es assentament» escrit al wizard mana.
                try:
                    from .settlement_criteria import settlement_by_criteria, settlement_regime, parse_spt_n, calc_note
                    from .geotech_criteria import _classify, lith_flags
                    _rd = self.report_data
                    _bnum = getattr(_rd, 'bearing_level_number', None)
                    _blev = next((l for l in soil_levels if l.level_number == _bnum), soil_levels[-1] if soil_levels else None)
                    _gp = _rd.geotechnical_params
                    _coh = float(_gp.cohesion) if _gp else 0.0
                    _crit_b = level_criteria.get(_bnum) if _bnum is not None else None
                    _klass = _classify(_blev.soil_type if _blev else 'granular',
                                       lith_flags(_blev.description if _blev else ''), _coh >= 0.5)
                    _regime = settlement_regime(_klass, _coh, _crit_b.regime if _crit_b is not None else None)
                    _nb_level = (_blev.n20_average / 0.83) if _blev and _blev.n20_average else None
                    _n_spt = parse_spt_n(spt_n_by_level.get(_bnum)) if _bnum is not None else None
                    _es_ud = self.user_data.get('Es_settlement')
                    try:
                        _es_ud = float(_es_ud) if _es_ud not in (None, '') else None
                    except (TypeError, ValueError):
                        _es_ud = None
                    sc = settlement_by_criteria(
                        q_net=tr.Qa, B=float(B or 1.0), Df=float(Df or 0.8), gamma=tr.gamma, nb=_nb_level,
                        n_spt=_n_spt, E=(_gp.E if _gp else None), regime=_regime, Es_override=_es_ud,
                    )
                    tr.settlement_cm, tr.Es_used, tr.settlement_generic = sc.settlement_cm, sc.Es, sc.generic
                    tr.settlement_regime, tr.Es_source, tr.settlement_sentence = sc.regime, sc.Es_source, sc.sentence
                    tr.Es_candidates = [c.__dict__ for c in sc.candidates]
                    tr.settlement_type = 'immediat' if sc.regime == 'granular' else 'diferit'
                    context['settlement_sentence'] = sc.sentence
                    context['_calc_settlement'], context['_calc_Es'] = calc_note(sc, float(B or 1.0))
                    for _n in sc.notes:
                        if _n.startswith('⚠'):
                            self.warnings.append(f"Assentament: {_n}")
                except Exception as exc:
                    self.warnings.append(f"Assentament per criteri: {exc}")
                    context['settlement_sentence'] = tr.format_settlement_for_report()
                context['settlement'] = f"{tr.settlement_cm:.2f}" if tr.settlement_cm else ''
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
                context.setdefault('_calc_settlement', "")
                context.setdefault('_calc_Es', "")
            else:
                context['qa_value'] = ''
                context['settlement'] = ''
                context['settlement_sentence'] = ''
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
        # Vistes generals: només les que el peu anuncia (peça 3); el bloc sencer cau si `photo_site_text` és buit
        _n_site = context.get('_num_site_photos')
        if _n_site is not None:
            if int(_n_site) < 2:
                context['photo_site_image_2'] = ''
            if int(_n_site) < 1:
                context['photo_site_image_1'] = ''

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
