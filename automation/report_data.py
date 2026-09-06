#!/usr/bin/env python3
"""
G3DT Report Data Model

Model de dades unificat per a la generacio d'informes geotecnics.
Combina dades de multiples fonts:
- DPSH data (dpsh_extractor.py)
- Project data (project_extractor.py)
- User input (data_schema.py)
- Calculated values (terzaghi_calculator.py)

Usage:
    from report_data import ReportData, build_report_data

    report_data = build_report_data(
        project_data=project_extractor.extract_all().to_dict(),
        user_data=validated_form_data,
        dpsh_data=dpsh_extractor.extract_all(),
        terzaghi_result=calculator.calculate_qa(...)
    )

Author: Eficients.cat
Date: 2026-02-03
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import date
from pathlib import Path
from typing import Any

from .cte_classifier import classify_building
from .dpsh_extractor import DPSHData, DPSHTest, DPSHReading, GeotechCorrelations

logger = logging.getLogger(__name__)
from .terzaghi_calculator import BearingCapacityResult, FootingShape


# --- Nivell portant (P2a+P2b, 2026-09-06) ---------------------------------------
# Criteri de l'Eva (7/7 signats, `docs/RECERCA-CRITERIS-DESCRITS-ALS-INFORMES-2026-09-03.md`):
# la frase del Qa declara SEMPRE el nivell portant amb l'encastament: «encastada entre
# 20-40 cm en els materials del <n-èsim> nivell sanejat». El nivell portant és el que la
# sabata (o el pou) ASSOLEIX a la fondària de fonamentació, no «el competent més profund»
# (Rubí: graves, no els gresos de sota; Vilanova: argiles, no les sorrenques). Quan la
# fonamentació baixa a un segon nivell (pous: Linyola, Anciles) és una DECISIÓ de l'Eva
# que entra pel camp `foundation_depth_m` del wizard: el codi no ho endevina.
EMBEDMENT_MIN_M = 0.2          # encastament mínim al nivell portant («20-40 cm»)
DEFAULT_FOUNDATION_DEPTH_M = 0.8  # defecte històric del càlcul (Terzaghi) quan el wizard no diu res


def foundation_depth_from_user_data(user_data: dict | None) -> tuple[float, bool]:
    """(Df en m, és_el_defecte). Accepta «1,0», 1, «0.3 m». Df ≤ 0 o absent → defecte."""
    raw = (user_data or {}).get('foundation_depth_m')
    try:
        if raw is None or raw == '':
            return DEFAULT_FOUNDATION_DEPTH_M, True
        if isinstance(raw, str):
            raw = raw.replace(',', '.').replace('m', '').strip()
        df = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_FOUNDATION_DEPTH_M, True
    if df <= 0:
        return DEFAULT_FOUNDATION_DEPTH_M, True
    return df, False


def _bearing_soil_type(
    soil_types: list[str] | None,
    soil_levels: list,
    sondeig_layers: list[dict],
    bearing_idx: int,
    description: str,
) -> str:
    """Tipus de sòl del nivell portant.

    Els `soil_types` del wizard són PER NIVELL DE L'INFORME (`soil_type_level_{i}`),
    no per capa del sondeig: només s'apliquen quan n'hi ha tants com nivells
    generats (llavors, el del nivell que conté el sostre de la capa portant). Si
    la llista ve d'una altra estructura de nivells (p. ex. un `user_data` antic
    amb 2 nivells «limo/grava» quan avui l'informe en té 1), es detecta per la
    descripció de la capa portant. Bell-lloc 2026-09-06: «limo» s'aplicava a les
    graves carbonatades i Qa queia de 3,0 a 2,0.
    """
    from .cte_geomech import detect_soil_type
    types = [t for t in (soil_types or [])]
    if types and soil_levels and len(types) == len(soil_levels):
        top = 0.0
        if sondeig_layers and 0 <= bearing_idx < len(sondeig_layers):
            top = float(sondeig_layers[bearing_idx].get('depth_from_m') or 0.0)
        k = None
        for i, lv in enumerate(soil_levels):
            lo = float(getattr(lv, 'depth_from_m', 0.0) or 0.0)
            hi = getattr(lv, 'depth_to_m', None)
            if lo <= top and (hi is None or top < float(hi)):
                k = i
                break
        if k is None:
            k = min(bearing_idx, len(soil_levels) - 1)
        if types[k]:
            return types[k]
    if types and len(types) == 1 and len(soil_levels) <= 1 and types[0]:
        return types[0]
    return detect_soil_type(description) if description else 'granular'


def _eval_numeric(val: Any) -> float:
    """Evaluate a numeric value or simple arithmetic expression (e.g. '70+20' → 90.0).

    Used internally when a numeric result is needed from user_data fields
    that may contain expressions like '260+68'.
    """
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        val = val.strip()
        if not val:
            return 0.0
        # Only allow digits, decimal points, +, -, *, / and whitespace
        import re
        if re.fullmatch(r'[\d\s.+\-*/()]+', val):
            try:
                result = eval(val, {"__builtins__": {}})  # noqa: S307
                if isinstance(result, (int, float)):
                    return float(result)
            except Exception:
                pass
        # Try simple float parse as fallback
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0
    return 0.0


@dataclass
class ClientData:
    """Dades del client per a l'informe."""
    company_name: str
    contact_name: str | None = None
    nif: str | None = None
    address: str | None = None


@dataclass
class SoilLevel:
    """Nivell de sol identificat als assaigs."""
    level_number: int
    description: str
    thickness_m: float | None  # None si es desconegut o continua
    n20_average: float
    depth_from_m: float = 0.0  # Top of layer (meters below surface)
    depth_to_m: float | None = None  # Bottom of layer (None = unknown/continues)
    n20_min: float | None = None  # Min N20 in layer (excl. refusal)
    n20_max: float | None = None  # Max N20 in layer (100 = refusal)
    soil_type: str = "granular"     # granular/arena/grava/arena_limosa/limo/arcilla
    # Fase 8b: la descripcio ve de la lectura (via A) i ja es la redaccio que
    # Eva ha triat -> a les cel·les de taula hi va LITERAL, sense escurçar.
    description_verbatim: bool = False


@dataclass
class GeotechnicalParams:
    """Parametres geotecnics derivats dels assaigs."""
    gamma: float  # g/cm3 (densitat)
    cohesion: float  # kg/cm2
    phi: float  # graus (angle de friccio)
    E: float  # kg/cm2 (modul de deformacio)


@dataclass
class ReportData:
    """
    Dades completes per generar un informe geotecnic.

    Aquesta classe centralitza totes les dades necessaries per generar
    un informe, independentment de la plantilla utilitzada.
    """

    # Identificacio del projecte
    expedient: str
    municipality: str
    report_date: date

    # Client
    client: ClientData

    # Arquitecte/Projecte (de data_schema)
    architect_name: str
    architect_company: str
    building_type: str
    num_floors: str
    superficie_parcela: str
    superficie_cadastral: str
    superficie_construida: str
    has_basement: bool
    has_retaining_walls: bool

    # Ubicacio
    street_address: str
    utm_x: float | None = None
    utm_y: float | None = None

    # Descripcions del solar i treballs de camp
    site_description: str = ""
    access_description: str = ""
    cota_referencia: str = ""
    field_work_dates: list[str] = field(default_factory=list)
    field_work_dates_text: str = ""

    # Laboratori d'assaigs
    lab_company: str = ""            # "TPS PROSPECCIÓ DEL SUBSÒL SL"
    lab_company_alias: str = ""      # "SOIL ASSAIG" (optional brand name)
    lab_description: str = ""        # "laboratori d'assaigs per al control de qualitat de l'edificació"

    # Dades de camp (sondeig/SPT)
    sondeig_tests: list[dict] | None = None  # From sondeig_extracted.json
    spt_data: dict | None = None
    lab_tests: list[dict] = field(default_factory=list)

    # Observacions del terreny
    adjacent_parcels: dict = field(default_factory=dict)  # {north, south, east, west}
    site_position: str = "centre"
    parcel_shape: str = "rectangular"
    is_urban: bool = True
    is_sloped: bool = False
    slope_percent: float | None = None  # Pendent del terreny (%)
    slope_direction: str | None = None  # Direcció dominant del pendent
    is_anthropized: bool | None = None  # Eva decideix via radio buttons
    slope_height_m: float | None = None  # Alçada del talús (m), per Hoek & Bray

    # Dades d'assaig (de dpsh_extractor)
    dpsh: DPSHData | None = None
    has_sondeig: bool = False
    has_spt: bool = False

    # Dades de laboratori
    sulfate_mg_kg: float | None = None
    aggressivity_class: str = ""  # No agressiu per defecte

    # Valors calculats
    cte_building_class: str = "C-0"  # C-0, C-1, C-2
    cte_soil_class: str = "T-1"  # T-1, T-2, T-3
    soil_levels: list[SoilLevel] = field(default_factory=list)
    geotechnical_params: GeotechnicalParams | None = None

    # Resultat Terzaghi (de terzaghi_calculator)
    terzaghi_result: BearingCapacityResult | None = None

    # Nivell portant triat (P2a+P2b, 2026-09-06): traçabilitat del càlcul
    bearing_layer_idx: int | None = None
    bearing_layer_description: str = ""
    foundation_depth_used_m: float | None = None
    foundation_depth_is_default: bool = False
    # P3: candidats amb procedència de γ/c/φ/E del nivell portant (geotech_criteria.GeotechCriteria.to_dict)
    geotech_criteria: dict | None = None

    # Override ICGC unit (from 1:25k manual lookup)
    icgc_unit_code: str = ""
    icgc_unit_description: str = ""
    icgc_unit_epoch: str = ""

    # Historia geologica template (Eva's .docx path, from auto-extractor or wizard)
    historia_geologica_template: str = ""

    # Geomech overrides (Nb, N from user_data.geomech_params)
    _geomech_overrides: dict = field(default_factory=dict)

    # Seccions condicionals
    include_expansivity: bool = False
    include_earth_pressure: bool = False
    include_slope_stability: bool = False
    show_granulometric: bool = False
    include_geothermal: bool = False

    @property
    def num_dpsh_tests(self) -> int:
        """Nombre d'assaigs DPSH realitzats."""
        return self.dpsh.num_tests if self.dpsh else 0

    @property
    def overall_n20_average(self) -> float:
        """Mitjana general de N20."""
        return self.dpsh.overall_average_n20 if self.dpsh else 0.0

    @property
    def water_detected(self) -> bool:
        """Si s'ha detectat nivell freatic."""
        return self.dpsh.any_water_detected if self.dpsh else False

    @property
    def qa_value(self) -> float | None:
        """Capacitat portant admissible (kg/cm2)."""
        return self.terzaghi_result.Qa if self.terzaghi_result else None

    @property
    def qa_formatted(self) -> str:
        """Qa formatejat per a l'informe."""
        if self.terzaghi_result:
            return self.terzaghi_result.format_for_report()
        return ""


class ReportDataValidationError(ValueError):
    """Error raised when input data to build_report_data is invalid."""
    pass


def _expedient_from_folder(folder_name: str) -> str:
    """Extract just the expedient code from a project folder name."""
    from .folder_utils import parse_folder_name
    expedient, _ = parse_folder_name(folder_name)
    return expedient


def load_validated_dpsh(project_path: Path) -> DPSHData | None:
    """
    Load DPSH data from approved validation file if available.

    Checks for validation/dpsh_approved.json in the project folder.
    If found and status is "approved", converts to DPSHData for report use.

    Args:
        project_path: Path to the project folder

    Returns:
        DPSHData if approved validation file exists, None otherwise
    """
    approved_path = project_path / "validation" / "dpsh_approved.json"
    if not approved_path.exists():
        return None

    try:
        # Import here to avoid circular imports
        from .validation.schemas import DPSHValidationFile, ValidationStatus

        validation_file = DPSHValidationFile.load(approved_path)

        # Only use if status is approved
        if validation_file.status != ValidationStatus.APPROVED:
            return None

        # Convert to DPSHData
        tests = []
        for vtest in validation_file.dpsh_tests:
            readings = []
            for vr in vtest.readings:
                # Skip unknown values that weren't corrected
                if vr.n20 == '??':
                    continue
                n20_val = int(vr.n20) if isinstance(vr.n20, str) else vr.n20
                readings.append(DPSHReading(
                    depth_m=-abs(vr.depth_m),  # Internal convention: negative depths
                    n20=n20_val,
                    nb=n20_val / vtest.correction_factor,
                    torque=vr.torque,
                    water_level=vr.water_indicator,
                    soil_level=None,
                ))

            tests.append(DPSHTest(
                test_id=vtest.test_id,
                readings=readings,
                correction_factor=vtest.correction_factor,
            ))

        return DPSHData(
            expedient=_expedient_from_folder(approved_path.parent.parent.name),
            tests=tests,
            source_file=f"validation/{approved_path.name}",
        )

    except Exception as e:
        logger.warning("Could not load validated DPSH data: %s", e)
        return None


def _detect_spt(user_data: dict, project_path: str = '') -> bool:
    """Auto-detect SPT availability from user_data or sondeig/dpsh extraction.

    Uses vision_normalizer for canonical key access.
    """
    # 1. Explicit user_data flag
    if user_data.get('has_spt') is True:
        return True
    # 2. Manual SPT data in user_data
    if user_data.get('spt_data'):
        return True
    # 3. Check normalized vision JSONs
    if project_path:
        from pathlib import Path
        from .vision_normalizer import load_sondeig_merged, load_dpsh_json

        data = load_sondeig_merged(Path(project_path) / 'validation')
        for test in data.get('sondeig_tests', []):
            if test.get('spt_results'):
                return True
        # 4. SPT recorded in DPSH field sheet (e.g. Rubí — no sondeig)
        dpsh_path = Path(project_path) / 'validation' / 'dpsh_extracted.json'
        if dpsh_path.exists():
            try:
                dpsh_data = load_dpsh_json(dpsh_path)
                if dpsh_data.get('spt_in_dpsh'):
                    return True
            except (json.JSONDecodeError, KeyError):
                pass
    return False


def _clean_municipality(name: str) -> str:
    """Strip trailing version digits from folder-derived municipality names."""
    from .folder_utils import municipality_for_report
    return municipality_for_report(name)


def build_report_data(
    project_data: dict,
    user_data: dict,
    dpsh_data: DPSHData | None = None,
    terzaghi_result: BearingCapacityResult | None = None,
    report_date: date | None = None,
    project_path: str = '',
) -> ReportData:
    """
    Construeix ReportData a partir de totes les fonts de dades.

    Args:
        project_data: Diccionari de ProjectExtractor.to_dict()
        user_data: Diccionari validat de data_schema
        dpsh_data: Dades DPSH extretes (opcional si ja esta a project_data)
        terzaghi_result: Resultat del calcul de capacitat portant
        report_date: Data de l'informe (per defecte avui)

    Returns:
        ReportData complet i llest per generar l'informe

    Raises:
        ReportDataValidationError: If required fields are missing or invalid
    """
    # Input validation
    if project_data is None:
        raise ReportDataValidationError("project_data cannot be None")
    if not isinstance(project_data, dict):
        raise ReportDataValidationError(
            f"project_data must be a dict, got {type(project_data).__name__}"
        )
    if user_data is None:
        raise ReportDataValidationError("user_data cannot be None")
    if not isinstance(user_data, dict):
        raise ReportDataValidationError(
            f"user_data must be a dict, got {type(user_data).__name__}"
        )

    if report_date is None:
        report_date = date.today()

    # Extreu dades del projecte
    project = project_data.get('project', {})
    client_dict = project_data.get('client', {})

    # Construeix ClientData
    client = ClientData(
        company_name=client_dict.get('company_name', ''),
        contact_name=client_dict.get('representative'),
        nif=client_dict.get('nif'),
        address=_build_full_address(client_dict),
    )

    # User override for client name (from wizard client_name field)
    if user_data.get('client_name'):
        client = ClientData(
            company_name=user_data['client_name'],
            contact_name=client.contact_name,
            nif=client.nif,
            address=client.address,
        )

    # Determina DPSHData
    # Prioritza el parametre dpsh_data, sino mira project_data
    if dpsh_data is None and 'dpsh' in project_data and project_data['dpsh']:
        # Reconstrueix DPSHData des del dict (simplificat)
        dpsh_dict = project_data['dpsh']
        dpsh_data = _reconstruct_dpsh_from_dict(dpsh_dict)

    # Extreu files inventory
    files = project_data.get('files', {})

    # Construeix adjacent_parcels
    adjacent_parcels = {
        'north': user_data.get('adjacent_north', ''),
        'south': user_data.get('adjacent_south', ''),
        'east': user_data.get('adjacent_east', ''),
        'west': user_data.get('adjacent_west', ''),
    }

    # Calcula parametres geotecnics (manual override > CTE > Peck/Hanson)
    # For multi-level projects, use bearing stratum (deepest layer) N20,
    # not global average which mixes shallow fill with bearing material.
    geotechnical_params = None
    geomech = user_data.get('geomech_params', {})
    sondeig_layers: list[dict] = user_data.get('sondeig_layers') or []
    foundation_depth, df_is_default = foundation_depth_from_user_data(user_data)
    if df_is_default:
        logger.warning(
            "foundation_depth_m absent del wizard: nivell portant triat amb Df=%.1f m per defecte "
            "(confirmar la fondària de fonamentació).", foundation_depth,
        )
    bearing_layer_idx: int | None = None
    geotech_criteria_dict: dict | None = None
    soil_levels: list[SoilLevel] = []
    if dpsh_data and dpsh_data.tests:
        # Auto-fill from sondeig_extracted.json when user_data has no layers
        # (defense-in-depth: report_generator also does this, but
        # build_report_data may be called independently e.g. from audit)
        if not sondeig_layers and project_path:
            try:
                from .vision_normalizer import load_sondeig_merged
                sdata = load_sondeig_merged(Path(project_path) / 'validation')
                tests = sdata.get('sondeig_tests', [])
                if tests and tests[0].get('layers'):
                    sondeig_layers = tests[0]['layers']
                    logger.info("Auto-filled sondeig_layers from sondeig data in build_report_data")
            except Exception:
                pass
        if not sondeig_layers:
            from .dpsh_segmenter import segment_by_n20_step
            sondeig_layers = segment_by_n20_step(dpsh_data)
            if sondeig_layers and len(sondeig_layers) > 1:
                logger.info(
                    "dpsh_segmenter synthesized %d sondeig_layers from DPSH "
                    "(no sondeig file or empty sondeig extraction).",
                    len(sondeig_layers),
                )
        soil_types_list = user_data.get('soil_types', [])
        # Nivells de l'informe (abans dels paràmetres: el tipus de sòl del portant
        # s'alinea per nivell de l'informe, no per capa del sondeig)
        soil_levels = _generate_soil_levels(
            dpsh_data,
            user_data.get('num_soil_levels', 1),
            sondeig_layers or None,
            user_data.get('soil_types'),
            foundation_depth,
        )
        avg_n20 = _bearing_stratum_n20(dpsh_data, sondeig_layers, soil_types_list, foundation_depth)
        # Convert N20 → Nb (Borrows) for all correlations.
        # DPSH has more energy than Borrows; dividing by 0.83 corrects
        # for the energy difference.  Eva confirmed this is essential.
        # Ref: Dapena, Lacasa & García (2000).
        NB_FACTOR = 0.83
        avg_nb = avg_n20 / NB_FACTOR
        try:
            from .cte_geomech import (
                nspt_to_phi, nspt_to_E_kg_cm2, nspt_to_gamma_g_cm3,
                is_rock, rock_params_default, soil_type_to_cohesion,
            )
            # Bearing-layer picked by Eva's skip-soft-top rule
            # (automation.bicapa.select_bearing_layer).  For profiles where
            # deepest ≡ competent (most G3DT projects), this matches the
            # legacy "always last" behaviour; for fill-over-competent
            # profiles (Alcoletge), it correctly skips the fill.
            bearing_idx = _select_bearing_layer_idx(sondeig_layers, soil_types_list, foundation_depth) if sondeig_layers else 0
            bearing_layer_idx = bearing_idx if sondeig_layers else None
            # Build description for rock detection — use bearing stratum.
            # IMPORTANT: Only use sondeig layer descriptions (field observations),
            # NOT icgc_unit_description (regional geology). ICGC describes the
            # formation-level geology which always contains rock terms
            # ("bretxes", "lutites", "conglomerat") even for granular sites.
            rock_description = ""
            if sondeig_layers:
                rock_description = sondeig_layers[bearing_idx].get('description', '')

            # Tipus de sòl del nivell portant: per nivell de l'informe (vegeu _bearing_soil_type)
            soil_type = _bearing_soil_type(
                soil_types_list, soil_levels, sondeig_layers, bearing_idx, rock_description,
            )

            # P3 (2026-09-06): paràmetres per CRITERI amb candidats i procedència
            # (`automation/geotech_criteria.py`); l'override expert mana per camp.
            from .geotech_criteria import geotech_by_criteria
            # Rebuig: al NIVELL de l'informe que conté la capa portant (criteri de la cel·la «Nb»
            # signada, «25-R»); si no hi ha nivells, al rang de la capa.
            _bearing_level = _report_level_for_layer(soil_levels, sondeig_layers, bearing_idx) if sondeig_layers else (
                soil_levels[0] if soil_levels else None)
            bearing_refusal = _level_has_refusal(dpsh_data, _bearing_level) if _bearing_level is not None else \
                _bearing_stratum_has_refusal(dpsh_data, sondeig_layers, soil_types_list, foundation_depth)
            crit = geotech_by_criteria(avg_nb, avg_n20, soil_type, rock_description, bearing_refusal)
            geotech_criteria_dict = crit.to_dict()
            if geomech.get('gamma') or geomech.get('phi') or geomech.get('E'):
                gamma = geomech.get('gamma') or crit.gamma
                phi = geomech.get('phi') or crit.phi
                E = geomech.get('E') or crit.E
                cohesion = geomech.get('cohesion', 0.0)
            else:
                gamma, phi, E, cohesion = crit.gamma, crit.phi, crit.E, crit.cohesion
        except ImportError:
            # Fallback to old Peck/Hanson if cte_geomech not available
            gamma = geomech.get('gamma') or GeotechCorrelations.n_to_density(avg_n20)
            phi = geomech.get('phi') or GeotechCorrelations.n_to_friction_angle(avg_n20)
            E = geomech.get('E') or GeotechCorrelations.n_to_deformation_modulus(avg_n20)
            cohesion = geomech.get('cohesion', 0.0)
        geotechnical_params = GeotechnicalParams(
            gamma=gamma, cohesion=cohesion, phi=phi, E=E,
        )

    # (els nivells de sòl ja s'han generat a dalt, amb els mateixos sondeig_layers)

    # Merge levels if Eva has flagged it
    if user_data.get('merge_to_single_level', False) and len(soil_levels) > 1:
        soil_levels = _merge_soil_levels(soil_levels)

    # Determina classes CTE
    # If both area and floors are missing/default, C-1 is a safe default
    _area_raw = user_data.get('superficie_construida_m2', '')
    _area = _eval_numeric(_area_raw)
    _floors = user_data.get('num_floors', '')
    if not _area and not _floors:
        cte_building_class = "C-1"
    else:
        cte_building_class = classify_building(
            area_m2=_area,
            floors=_floors or 'Pb',
            has_basement=user_data.get('has_basement', False),
        )
    cte_soil_class = _determine_soil_class(dpsh_data)

    # Determina seccions condicionals
    include_earth_pressure = (
        user_data.get('has_basement', False) or
        user_data.get('has_retaining_walls', False)
    )
    include_slope_stability = user_data.get('is_sloped', False)

    return ReportData(
        # Identificacio
        expedient=project.get('expedient', ''),
        municipality=user_data.get('site_municipality') or _clean_municipality(project.get('municipality', '')),
        report_date=report_date,
        # Client
        client=client,
        # Arquitecte/Projecte
        architect_name=user_data.get('architect_name', ''),
        architect_company=user_data.get('architect_company', ''),
        building_type=user_data.get('building_type', ''),
        num_floors=user_data.get('num_floors', ''),
        superficie_parcela=str(user_data.get('superficie_parcela_m2', '') or ''),
        superficie_cadastral=str(user_data.get('superficie_cadastral_m2', '') or ''),
        superficie_construida=str(_area_raw) if _area_raw else '',
        has_basement=user_data.get('has_basement', False),
        has_retaining_walls=user_data.get('has_retaining_walls', False),
        # Ubicacio
        street_address=user_data.get('street_address', ''),
        utm_x=user_data.get('utm_x'),
        utm_y=user_data.get('utm_y'),
        # Descripcions
        site_description=user_data.get('site_description', ''),
        access_description=user_data.get('access_description', ''),
        cota_referencia=user_data.get('cota_referencia', ''),
        field_work_dates=user_data.get('field_work_dates', []),
        field_work_dates_text=user_data.get('field_work_dates_text', ''),
        lab_company=user_data.get('lab_company', ''),
        lab_company_alias=user_data.get('lab_company_alias', ''),
        lab_description=user_data.get('lab_description', ''),
        spt_data=user_data.get('spt_data'),
        lab_tests=user_data.get('lab_tests', []),
        # Observacions terreny
        adjacent_parcels=adjacent_parcels,
        site_position=user_data.get('site_position', 'centre'),
        parcel_shape=user_data.get('parcel_shape', 'rectangular'),
        is_urban=user_data.get('is_urban', True),
        is_sloped=user_data.get('is_sloped', False),
        slope_percent=user_data.get('slope_percent'),
        slope_direction=user_data.get('slope_direction'),
        slope_height_m=user_data.get('slope_height_m'),
        is_anthropized=user_data.get('is_anthropized'),
        # Dades assaig
        dpsh=dpsh_data,
        sondeig_tests=user_data.get('sondeig_tests'),
        has_sondeig=user_data.get('has_sondeig', files.get('has_sondeig', False)),
        has_spt=_detect_spt(user_data, project_path),
        # Laboratori — auto-extract sulfate from lab PDF if not in user_data
        sulfate_mg_kg=_resolve_sulfate(user_data, project_path),
        aggressivity_class="",
        # Valors calculats
        cte_building_class=cte_building_class,
        cte_soil_class=cte_soil_class,
        soil_levels=soil_levels,
        geotechnical_params=geotechnical_params,
        bearing_layer_idx=bearing_layer_idx,
        bearing_layer_description=(sondeig_layers[bearing_layer_idx].get('description', '') if bearing_layer_idx is not None else ''),
        foundation_depth_used_m=foundation_depth,
        foundation_depth_is_default=df_is_default,
        geotech_criteria=geotech_criteria_dict,
        terzaghi_result=terzaghi_result,
        # Override ICGC unit (manual 1:25k lookup)
        icgc_unit_code=user_data.get('icgc_unit_code', ''),
        icgc_unit_description=user_data.get('icgc_unit_description', ''),
        icgc_unit_epoch=user_data.get('icgc_unit_epoch', ''),
        # Historia geologica template path
        historia_geologica_template=user_data.get('historia_geologica_template', ''),
        # Geomech overrides (Nb, N for Taula 10)
        _geomech_overrides={
            'Nb': geomech.get('Nb', ''),
            'N': geomech.get('N', ''),
        },
        # Seccions condicionals
        include_expansivity=False,  # Determinat per tipus de sol
        include_earth_pressure=include_earth_pressure,
        include_slope_stability=include_slope_stability,
        include_geothermal=user_data.get('include_geothermal', False),
        show_granulometric=user_data.get('show_granulometric', False),
    )


def to_dict(report_data: ReportData) -> dict[str, Any]:
    """
    Converteix ReportData a diccionari serialitzable a JSON.

    Args:
        report_data: Instancia de ReportData

    Returns:
        Diccionari amb totes les dades
    """
    result: dict[str, Any] = {
        'project': {
            'expedient': report_data.expedient,
            'municipality': report_data.municipality,
            'report_date': report_data.report_date.isoformat(),
        },
        'client': {
            'company_name': report_data.client.company_name,
            'contact_name': report_data.client.contact_name,
            'nif': report_data.client.nif,
            'address': report_data.client.address,
        },
        'architect': {
            'name': report_data.architect_name,
            'company': report_data.architect_company,
        },
        'building': {
            'type': report_data.building_type,
            'num_floors': report_data.num_floors,
            'superficie_parcela_m2': report_data.superficie_parcela,
            'superficie_cadastral_m2': report_data.superficie_cadastral,
            'superficie_construida_m2': report_data.superficie_construida,
            'has_basement': report_data.has_basement,
            'has_retaining_walls': report_data.has_retaining_walls,
        },
        'location': {
            'street_address': report_data.street_address,
            'utm_x': report_data.utm_x,
            'utm_y': report_data.utm_y,
        },
        'descriptions': {
            'site_description': report_data.site_description,
            'access_description': report_data.access_description,
            'cota_referencia': report_data.cota_referencia,
            'field_work_dates': report_data.field_work_dates,
            'field_work_dates_text': report_data.field_work_dates_text,
            'lab_company': report_data.lab_company,
            'lab_company_alias': report_data.lab_company_alias,
            'lab_description': report_data.lab_description,
        },
        'sondeig_tests': report_data.sondeig_tests,
        'spt_data': report_data.spt_data,
        'lab_tests': report_data.lab_tests,
        'site': {
            'adjacent_parcels': report_data.adjacent_parcels,
            'position': report_data.site_position,
            'shape': report_data.parcel_shape,
            'is_urban': report_data.is_urban,
            'is_sloped': report_data.is_sloped,
            'slope_percent': report_data.slope_percent,
            'slope_direction': report_data.slope_direction,
            'slope_height_m': report_data.slope_height_m,
            'is_anthropized': report_data.is_anthropized,
        },
        'tests': {
            'has_dpsh': report_data.dpsh is not None,
            'num_dpsh_tests': report_data.num_dpsh_tests,
            'has_sondeig': report_data.has_sondeig,
            'has_spt': report_data.has_spt,
            'water_detected': report_data.water_detected,
        },
        'lab': {
            'sulfate_mg_kg': report_data.sulfate_mg_kg,
            'aggressivity_class': report_data.aggressivity_class,
        },
        'cte': {
            'building_class': report_data.cte_building_class,
            'soil_class': report_data.cte_soil_class,
        },
        'soil_levels': [
            {
                'level_number': level.level_number,
                'description': level.description,
                'thickness_m': level.thickness_m,
                'n20_average': level.n20_average,  # Full precision for serialization
                'depth_from_m': level.depth_from_m,
                'depth_to_m': level.depth_to_m,
                'n20_min': level.n20_min,
                'n20_max': level.n20_max,
                'soil_type': level.soil_type,
            }
            for level in report_data.soil_levels
        ],
        'geotechnical_params': None,
        'terzaghi': None,
        'conditional_sections': {
            'include_expansivity': report_data.include_expansivity,
            'include_earth_pressure': report_data.include_earth_pressure,
            'include_slope_stability': report_data.include_slope_stability,
            'include_geothermal': report_data.include_geothermal,
            'show_granulometric': report_data.show_granulometric,
        },
    }

    # Afegeix parametres geotecnics si disponibles
    # Note: Full precision preserved for serialization; round only for display
    if report_data.geotechnical_params:
        gp = report_data.geotechnical_params
        result['geotechnical_params'] = {
            'gamma_g_cm3': gp.gamma,
            'cohesion_kg_cm2': gp.cohesion,
            'phi_deg': gp.phi,
            'E_kg_cm2': gp.E,
        }

    # Afegeix resultat Terzaghi si disponible
    if report_data.terzaghi_result:
        result['terzaghi'] = report_data.terzaghi_result.to_dict()

    # Afegeix DPSH si disponible
    if report_data.dpsh:
        result['dpsh'] = report_data.dpsh.to_dict()

    return result


def from_dict(data: dict[str, Any]) -> ReportData:
    """
    Reconstrueix ReportData des d'un diccionari.

    Args:
        data: Diccionari amb les dades (tipicament de JSON)

    Returns:
        Instancia de ReportData
    """
    project = data.get('project', {})
    client_dict = data.get('client', {})
    architect = data.get('architect', {})
    building = data.get('building', {})
    location = data.get('location', {})
    descriptions = data.get('descriptions', {})
    site = data.get('site', {})
    tests = data.get('tests', {})
    lab = data.get('lab', {})
    cte = data.get('cte', {})
    conditional = data.get('conditional_sections', {})

    # Reconstrueix client
    client = ClientData(
        company_name=client_dict.get('company_name', ''),
        contact_name=client_dict.get('contact_name'),
        nif=client_dict.get('nif'),
        address=client_dict.get('address'),
    )

    # Reconstrueix soil_levels
    soil_levels = [
        SoilLevel(
            level_number=sl['level_number'],
            description=sl['description'],
            thickness_m=sl.get('thickness_m'),
            n20_average=sl['n20_average'],
            depth_from_m=sl.get('depth_from_m', 0.0),
            depth_to_m=sl.get('depth_to_m'),
            n20_min=sl.get('n20_min'),
            n20_max=sl.get('n20_max'),
            soil_type=sl.get('soil_type', 'granular'),
        )
        for sl in data.get('soil_levels', [])
    ]

    # Reconstrueix geotechnical_params
    geotechnical_params = None
    gp_dict = data.get('geotechnical_params')
    if gp_dict:
        geotechnical_params = GeotechnicalParams(
            gamma=gp_dict['gamma_g_cm3'],
            cohesion=gp_dict['cohesion_kg_cm2'],
            phi=gp_dict['phi_deg'],
            E=gp_dict['E_kg_cm2'],
        )

    # Reconstrueix DPSH
    dpsh_data = None
    if 'dpsh' in data and data['dpsh']:
        dpsh_data = _reconstruct_dpsh_from_dict(data['dpsh'])

    # Reconstrueix Terzaghi result
    terzaghi_result = None
    if data.get('terzaghi'):
        terzaghi_result = _reconstruct_terzaghi_from_dict(data['terzaghi'])

    # Parseja data
    report_date_str = project.get('report_date', '')
    if report_date_str:
        report_date = date.fromisoformat(report_date_str)
    else:
        report_date = date.today()

    return ReportData(
        expedient=project.get('expedient', ''),
        municipality=project.get('municipality', ''),
        report_date=report_date,
        client=client,
        architect_name=architect.get('name', ''),
        architect_company=architect.get('company', ''),
        building_type=building.get('type', ''),
        num_floors=building.get('num_floors', ''),
        superficie_parcela=str(building.get('superficie_parcela_m2', '') or ''),
        superficie_cadastral=str(building.get('superficie_cadastral_m2', '') or ''),
        superficie_construida=str(building.get('superficie_construida_m2', '') or ''),
        has_basement=building.get('has_basement', False),
        has_retaining_walls=building.get('has_retaining_walls', False),
        street_address=location.get('street_address', ''),
        utm_x=location.get('utm_x'),
        utm_y=location.get('utm_y'),
        site_description=descriptions.get('site_description', ''),
        access_description=descriptions.get('access_description', ''),
        cota_referencia=descriptions.get('cota_referencia', ''),
        field_work_dates=descriptions.get('field_work_dates', []),
        field_work_dates_text=descriptions.get('field_work_dates_text', ''),
        lab_company=descriptions.get('lab_company', ''),
        lab_company_alias=descriptions.get('lab_company_alias', ''),
        lab_description=descriptions.get('lab_description', ''),
        sondeig_tests=data.get('sondeig_tests'),
        spt_data=data.get('spt_data'),
        lab_tests=data.get('lab_tests', []),
        adjacent_parcels=site.get('adjacent_parcels', {}),
        site_position=site.get('position', 'centre'),
        parcel_shape=site.get('shape', 'rectangular'),
        is_urban=site.get('is_urban', True),
        is_sloped=site.get('is_sloped', False),
        slope_percent=site.get('slope_percent'),
        slope_direction=site.get('slope_direction'),
        slope_height_m=site.get('slope_height_m'),
        is_anthropized=site.get('is_anthropized'),
        dpsh=dpsh_data,
        has_sondeig=tests.get('has_sondeig', False),
        has_spt=tests.get('has_spt', False),
        sulfate_mg_kg=lab.get('sulfate_mg_kg'),
        aggressivity_class=lab.get('aggressivity_class', ''),
        cte_building_class=cte.get('building_class', 'C-0'),
        cte_soil_class=cte.get('soil_class', 'T-1'),
        soil_levels=soil_levels,
        geotechnical_params=geotechnical_params,
        terzaghi_result=terzaghi_result,
        include_expansivity=conditional.get('include_expansivity', False),
        include_earth_pressure=conditional.get('include_earth_pressure', False),
        include_slope_stability=conditional.get('include_slope_stability', False),
        show_granulometric=conditional.get('show_granulometric', False),
        include_geothermal=conditional.get('include_geothermal', False),
    )


# === Funcions auxiliars ===

def _build_full_address(client_dict: dict) -> str | None:
    """Construeix l'adreca completa del client."""
    parts = []
    if client_dict.get('address'):
        parts.append(client_dict['address'])
    if client_dict.get('postal_code') or client_dict.get('city'):
        city_part = ' '.join(filter(None, [
            client_dict.get('postal_code'),
            client_dict.get('city'),
        ]))
        if city_part:
            parts.append(city_part)
    return ', '.join(parts) if parts else None


def _reconstruct_dpsh_from_dict(dpsh_dict: dict) -> DPSHData:
    """
    Reconstrueix DPSHData des d'un diccionari.

    Depth convention:
    - DPSHData.to_dict() serializes depths as POSITIVE values (abs(depth_m))
    - DPSHReading stores depths as NEGATIVE values (below surface convention)
    - This function converts back: positive dict value -> negative internal value
    """
    tests = []
    for test_dict in dpsh_dict.get('tests', []):
        readings = []
        for r in test_dict.get('readings', []):
            # Dict stores positive depths; convert to negative (below-surface convention)
            depth_value = r['depth_m']
            depth_m = -abs(depth_value) if depth_value >= 0 else depth_value
            readings.append(DPSHReading(
                depth_m=depth_m,
                n20=r['n20'],
                nb=r['nb'],
                torque=r.get('torque'),
                water_level=r.get('water_level', False),
                soil_level=r.get('soil_level'),
            ))
        tests.append(DPSHTest(
            test_id=test_dict['test_id'],
            readings=readings,
            correction_factor=test_dict.get('correction_factor', 0.83),
        ))

    return DPSHData(
        expedient=dpsh_dict.get('expedient', ''),
        tests=tests,
        source_file=dpsh_dict.get('source_file', ''),
    )


def _reconstruct_terzaghi_from_dict(data: dict) -> BearingCapacityResult:
    """Reconstrueix BearingCapacityResult des d'un diccionari."""
    inputs = data.get('inputs', {})
    factors = data.get('factors', {})
    results = data.get('results', {})

    return BearingCapacityResult(
        phi=inputs.get('phi_deg', 30),
        cohesion=inputs.get('cohesion_kg_cm2', 0),
        gamma=inputs.get('gamma_g_cm3', 2.0),
        B=inputs.get('B_m', 1.0),
        Df=inputs.get('Df_m', 0.5),
        L=inputs.get('L_m'),
        shape=FootingShape(inputs.get('shape', 'strip')),
        Nc=factors.get('Nc', 0),
        Nq=factors.get('Nq', 0),
        Ngamma=factors.get('Ngamma', 0),
        sc=factors.get('sc', 1),
        sq=factors.get('sq', 1),
        sgamma=factors.get('sgamma', 1),
        qu=results.get('qu_kg_cm2', 0),
        safety_factor=results.get('safety_factor', 3),
        Qa=results.get('Qa_kg_cm2', 0),
        settlement_cm=results.get('settlement_cm'),
        settlement_type=results.get('settlement_type', 'immediat'),
        Es_used=results.get('Es_used_kg_cm2'),
        qa_terzaghi_peck=results.get('qa_terzaghi_peck_kg_cm2'),
        Qa_uncapped=results.get('Qa_uncapped_kg_cm2'),
        Fw=results.get('Fw'),
        Fd_tp=results.get('Fd_tp'),
        qa_governs=results.get('qa_governs', 'terzaghi'),
    )


def _select_bearing_layer_idx(
    sondeig_layers: list[dict],
    soil_types: list[str] | None = None,
    foundation_depth: float = DEFAULT_FOUNDATION_DEPTH_M,
) -> int:
    """Índex del nivell portant: el PRIMER competent que la sabata assoleix.

    Embolcalla `automation.bicapa.select_bearing_layer` (recorre de dalt a
    baix; salta les capes que acaben per sobre de `Df + EMBEDMENT_MIN_M`, les
    de rebliment/terra vegetal i les massa fluixes) sobre els dicts de capa
    del sondeig. `foundation_depth` és la Df real (`foundation_depth_m` del
    wizard); l'encastament mínim s'hi suma aquí perquè tots els cridants
    apliquin el mateix criteri. Si cap capa és competent, cau a la més
    profunda (proxy segur) amb avís.

    Fins al 2026-09-06 recorria les capes INVERTIDES («el competent més
    profund», Df fix 0,8): Rubí sortia vestit de roca (gresos a 3,35 m amb
    la sabata a 1,0). Evidència signada i alternatives: DECISION-LOG
    2026-09-06 (tarda, 2). Ref: `docs/METODOLOGIA-EVA.md` §5.9 (Alcoletge).
    """
    if not sondeig_layers:
        return 0
    if len(sondeig_layers) == 1:
        return 0

    try:
        from .bicapa import SoilLayer, select_bearing_layer
        from .cte_geomech import (
            detect_soil_type, nspt_to_phi, soil_type_to_cohesion,
        )
    except ImportError as e:
        logger.warning(
            "bicapa module unavailable (%s); falling back to deepest-layer "
            "bearing. Eva's skip-soft-top rule is DISABLED.", e,
        )
        return len(sondeig_layers) - 1

    def _safe_float(v, default):
        try:
            return float(v) if v is not None else default
        except (TypeError, ValueError):
            return default

    try:
        built: list[SoilLayer] = []
        for idx, d in enumerate(sondeig_layers):
            desc = d.get('description', '') or ''
            st = (soil_types[idx] if soil_types and idx < len(soil_types) else None) or detect_soil_type(desc)
            nspt = d.get('n20_average') or d.get('nspt')
            try:
                nspt = float(nspt) if nspt is not None else None
            except (TypeError, ValueError):
                nspt = None
            phi = nspt_to_phi(nspt, st) if nspt is not None else 30.0
            cohesion = soil_type_to_cohesion(st)
            depth_top = _safe_float(d.get('depth_from_m'), 0.0)
            depth_bottom = _safe_float(d.get('depth_to_m'), depth_top + 1.0)
            built.append(SoilLayer(
                depth_top=depth_top,
                depth_bottom=depth_bottom,
                soil_type=st,
                nspt=nspt,
                phi=phi,
                cohesion=cohesion,
                description=desc,
            ))

        # De dalt a baix: el primer nivell competent que la sabata assoleix
        # (Df + encastament mínim). Les capes que acaben per sobre no carreguen;
        # rebliment / terra vegetal / massa fluix se salten (sanejat).
        try:
            _, idx = select_bearing_layer(
                built, foundation_depth=round(foundation_depth + EMBEDMENT_MIN_M, 3),  # 1,4 + 0,2 = 1,5999…
            )
        except ValueError:
            # All layers weak or above Df — fall back to deepest (safest proxy)
            logger.warning(
                "_select_bearing_layer_idx: no competent layer at Df=%.2f m; "
                "falling back to deepest.", foundation_depth,
            )
            return len(sondeig_layers) - 1

        if idx != len(sondeig_layers) - 1:
            logger.info(
                "Nivell portant: idx=%d (no el més profund, %d) amb Df=%.2f m + %.1f m d'encastament.",
                idx, len(sondeig_layers) - 1, foundation_depth, EMBEDMENT_MIN_M,
            )
        return idx
    except (TypeError, KeyError) as exc:
        # Construction failed — fall back to deepest (safest single-layer proxy)
        logger.warning(
            "_select_bearing_layer_idx falling back to deepest layer: %s", exc,
        )
        return len(sondeig_layers) - 1


def _report_level_for_layer(soil_levels: list, sondeig_layers: list[dict], layer_idx: int):
    """Nivell de l'informe (SoilLevel) que conté el sostre de la capa `layer_idx`; None si no n'hi ha."""
    if not soil_levels:
        return None
    top = 0.0
    if sondeig_layers and 0 <= layer_idx < len(sondeig_layers):
        top = float(sondeig_layers[layer_idx].get('depth_from_m') or 0.0)
    for lv in soil_levels:
        lo = float(getattr(lv, 'depth_from_m', 0.0) or 0.0)
        hi = getattr(lv, 'depth_to_m', None)
        if lo <= top and (hi is None or top < float(hi)):
            return lv
    return soil_levels[min(layer_idx, len(soil_levels) - 1)]


def _level_has_refusal(dpsh_data: DPSHData, level) -> bool:
    """El DPSH rebutja (N20 ≥ 100) dins del rang de fondàries del nivell de l'informe.

    És el criteri de la cel·la «Nb» signada («25-R»): el rebuig pertany al NIVELL, encara que
    caigui just sota la capa portant (Bell-lloc: sabata a 0,3 m sobre les graves 0-1,0; rebuig
    a 1,0-1,6 dins del mateix nivell geològic)."""
    if not dpsh_data or not dpsh_data.tests or level is None:
        return False
    lo = float(getattr(level, 'depth_from_m', 0.0) or 0.0)
    hi = getattr(level, 'depth_to_m', None)
    hi = float('inf') if hi is None else float(hi)
    return any(
        lo <= abs(r.depth_m) <= hi and r.n20 >= 100
        for t in dpsh_data.tests for r in t.readings if r.depth_m is not None
    )


def _bearing_stratum_has_refusal(
    dpsh_data: DPSHData,
    sondeig_layers: list[dict],
    soil_types: list[str] | None = None,
    foundation_depth: float = DEFAULT_FOUNDATION_DEPTH_M,
) -> bool:
    """El DPSH rebutja (N20 ≥ 100) dins del nivell portant (mateix rang que `_bearing_stratum_n20`)."""
    if not dpsh_data or not dpsh_data.tests:
        return False
    if not sondeig_layers or len(sondeig_layers) < 2:
        return any(r.n20 >= 100 for t in dpsh_data.tests for r in t.readings)
    bearing_idx = _select_bearing_layer_idx(sondeig_layers, soil_types, foundation_depth)
    bearing = sondeig_layers[bearing_idx]
    depth_from = bearing.get('depth_from_m', 0.0) or 0.0
    depth_to = bearing.get('depth_to_m')
    apply_upper = bearing_idx != len(sondeig_layers) - 1 and depth_to is not None
    for test in dpsh_data.tests:
        for r in test.readings:
            d = abs(r.depth_m)
            if d < depth_from or (apply_upper and d > depth_to):
                continue
            if r.n20 >= 100:
                return True
    return False


def _bearing_stratum_n20(
    dpsh_data: DPSHData,
    sondeig_layers: list[dict],
    soil_types: list[str] | None = None,
    foundation_depth: float = DEFAULT_FOUNDATION_DEPTH_M,
) -> float:
    """Get average N20 for the bearing stratum per Eva's skip-soft-top rule.

    For multi-level projects, the bearing stratum is the first competent
    layer (skipping fill / rebliment / very weak top layers). DPSH readings
    in shallower fill layers should not influence the geotechnical
    parameters used for foundation design.

    Falls back to global average when:
    - No sondeig layers exist (single-level project)
    - Only one sondeig layer
    - No DPSH readings fall in the bearing stratum's depth range
    """
    if not sondeig_layers or len(sondeig_layers) < 2:
        return dpsh_data.overall_average_n20

    bearing_idx = _select_bearing_layer_idx(sondeig_layers, soil_types, foundation_depth)
    bearing = sondeig_layers[bearing_idx]
    depth_from = bearing.get('depth_from_m', 0.0)
    depth_to = bearing.get('depth_to_m')

    # Only apply the depth_to upper bound when the bearing layer is NOT the
    # deepest (i.e. bicapa picked a middle layer because the deepest is weak).
    # When bearing == deepest (the common G3DT case), integrate everything
    # from depth_from downward to preserve legacy behaviour — DPSH typically
    # continues deeper than sondeig layer boundaries.
    apply_upper = bearing_idx != len(sondeig_layers) - 1

    # Collect DPSH readings inside the bearing stratum depth range
    bearing_n20: list[float] = []
    for test in dpsh_data.tests:
        for r in test.readings:
            d = abs(r.depth_m)
            if d < depth_from:
                continue
            if apply_upper and depth_to is not None and d > depth_to:
                continue
            if r.n20 >= 100:
                continue
            bearing_n20.append(r.n20)

    if not bearing_n20:
        return dpsh_data.overall_average_n20

    return sum(bearing_n20) / len(bearing_n20)


def _group_layers_by_geological_level(sondeig_layers: list[dict]) -> list[list[int]] | None:
    """Agrupa ÍNDEXS de capa per runs consecutius de 'geological_level'.

    Els nivells geològics surten de la columna "Unitat litològica" de l'annex
    formatat (criteri d'Eva). Diversos materials poden compartir nivell.
    Exemple: geological_level = [1,1,2,3,3] -> [[0,1],[2],[3,4]] (3 grups).

    Retorna None si el camp 'geological_level' falta o és None a QUALSEVOL capa
    (p.ex. sondeig sintetitzat per dpsh_segmenter, o full de camp sense la
    columna). En aquest cas el caller cau a la lògica per-material actual.
    """
    levels: list[int] = []
    for layer in sondeig_layers:
        gl = layer.get('geological_level')
        if not isinstance(gl, int):
            return None
        levels.append(gl)

    # Agrupació per RUNS CONSECUTIUS: assumeix sondeig_layers ordenat per
    # profunditat (sempre és així, ve de l'annex de dalt a baix). Per tant un
    # cas no físic com [1,2,1] donaria 3 grups, per disseny.
    groups: list[list[int]] = []
    for i, gl in enumerate(levels):
        if groups and gl == levels[i - 1]:
            groups[-1].append(i)
        else:
            groups.append([i])
    return groups


def _generate_soil_levels(
    dpsh_data: DPSHData | None,
    num_levels: int,
    sondeig_layers: list[dict] | None = None,
    soil_types: list[str] | None = None,
    foundation_depth: float = DEFAULT_FOUNDATION_DEPTH_M,
) -> list[SoilLevel]:
    """
    Genera nivells de sòl a partir de les capes del sondeig i lectures DPSH.

    Si tenim sondeig_layers (de sondeig_extracted.json), partim les lectures
    DPSH per rang de profunditat i calculem N20 mitjana per capa.
    Si no, retornem un sol nivell amb la mitjana global.
    """
    from .cte_geomech import detect_soil_type

    if not dpsh_data or not dpsh_data.tests:
        return []

    # Collect all readings across all tests (depths are negative)
    all_readings = [r for test in dpsh_data.tests for r in test.readings]

    # If we have sondeig layer boundaries, split readings by depth range
    if sondeig_layers and len(sondeig_layers) > 1:
        def _collapse_to_single() -> list[SoilLevel]:
            # Nivell únic: descripció, tipus de sòl i N20 del NIVELL PORTANT (el que
            # la sabata assoleix a Df), no de la capa més profunda. Rubí: l'Eva
            # descriu i parametritza les graves, no els gresos de sota (P2a).
            max_depth = max((abs(r.depth_m) for r in all_readings), default=0)
            bearing_idx = _select_bearing_layer_idx(sondeig_layers, soil_types, foundation_depth)
            bearing = sondeig_layers[bearing_idx]
            desc = bearing.get('description', 'Nivell principal')
            if soil_types and len(soil_types) == 1 and soil_types[0]:
                st = soil_types[0]  # l'usuari ha declarat 1 nivell: el seu tipus és el del nivell únic
            else:
                st = detect_soil_type(desc)  # llista d'una altra estructura de nivells: no s'indexa per capa
            # N20 del nivell portant (mateix criteri que _bearing_stratum_n20: sense
            # límit superior només quan el portant és la capa més profunda)
            bearing_avg = _bearing_stratum_n20(dpsh_data, sondeig_layers, soil_types, foundation_depth)
            depth_from = bearing.get('depth_from_m', 0.0)
            depth_to = bearing.get('depth_to_m')
            apply_upper = bearing_idx != len(sondeig_layers) - 1 and depth_to is not None
            bearing_n20 = [
                r.n20 for r in all_readings
                if abs(r.depth_m) >= depth_from and r.n20 < 100
                and (not apply_upper or abs(r.depth_m) <= depth_to)
            ]
            all_n20 = bearing_n20 if bearing_n20 else [r.n20 for r in all_readings if r.n20 < 100]
            return [SoilLevel(
                level_number=1,
                description=desc,
                thickness_m=max_depth if max_depth > 0 else None,
                n20_average=bearing_avg,
                depth_from_m=0.0,
                depth_to_m=max_depth if max_depth > 0 else None,
                n20_min=min(all_n20) if all_n20 else None,
                n20_max=max(all_n20) if all_n20 else None,
                soil_type=st,
            )]

        # Prefer grouping by geological_level (Eva's "Unitat litològica" criterion):
        # diversos materials poden compartir un mateix nivell geològic.
        groups = _group_layers_by_geological_level(sondeig_layers)
        if groups is not None:
            n_groups = len(groups)
            # Override a la baixa: Eva pot forçar 1 nivell; n_groups==1 també col·lapsa.
            if num_levels < n_groups or n_groups == 1:
                return _collapse_to_single()
            # un SoilLevel per grup geològic
            levels = []
            for gi, idxs in enumerate(groups):
                is_last = gi == n_groups - 1
                first = sondeig_layers[idxs[0]]
                last = sondeig_layers[idxs[-1]]
                depth_from = first.get('depth_from_m', 0.0)
                depth_to = last.get('depth_to_m', 0.0)
                bearing_from = last.get('depth_from_m', depth_from)  # ferm del grup = capa més profunda
                # N20 al sub-rang de ferm del grup; per a l'ÚLTIM grup treure el límit
                # superior (DPSH va més profund que el sondeig) — mateix principi que
                # el bloc de col·lapse / _bearing_stratum_n20. Exclou rebuig (n20>=100).
                # Defensa: si depth_to és None (capa sense límit inferior) tractem-la
                # com a sense límit superior, igual que l'últim grup, per no petar.
                apply_upper = (not is_last) and depth_to is not None and depth_to > 0
                layer_n20 = [
                    r.n20 for r in all_readings
                    if abs(r.depth_m) >= bearing_from
                    and (not apply_upper or abs(r.depth_m) <= depth_to)
                    and r.n20 < 100
                ]
                avg_n20 = sum(layer_n20) / len(layer_n20) if layer_n20 else dpsh_data.overall_average_n20
                description = last.get('description', f'Nivell {gi + 1}')  # ferm = capa més profunda
                st = soil_types[idxs[-1]] if soil_types and idxs[-1] < len(soil_types) else detect_soil_type(description)
                thickness = depth_to - depth_from if depth_to is not None and depth_to > depth_from else None
                levels.append(SoilLevel(
                    level_number=gi + 1,
                    description=description,
                    thickness_m=thickness,
                    n20_average=avg_n20,
                    depth_from_m=depth_from,
                    depth_to_m=depth_to if depth_to is not None and depth_to > 0 else None,
                    n20_min=min(layer_n20) if layer_n20 else None,
                    n20_max=max(layer_n20) if layer_n20 else None,
                    soil_type=st,
                ))
            return levels

        # Fallback (groups is None): legacy per-material logic.
        # When user says 1 level but sondeig has 2+ layers, use ALL readings
        # (DPSH goes deeper than sondeig — filtering by sondeig depth loses readings)
        if num_levels < len(sondeig_layers):
            return _collapse_to_single()

        levels = []
        for i, layer in enumerate(sondeig_layers):
            depth_from = layer.get('depth_from_m', 0.0)
            depth_to = layer.get('depth_to_m', 0.0)
            description = layer.get('description', f'Nivell {i + 1}')

            # Filter DPSH readings within this layer's depth range
            # Readings have negative depths; layer boundaries are positive
            # Exclude refusal values (N20 >= 100)
            layer_n20 = [
                r.n20 for r in all_readings
                if depth_from <= abs(r.depth_m) <= depth_to and r.n20 < 100
            ]
            avg_n20 = sum(layer_n20) / len(layer_n20) if layer_n20 else dpsh_data.overall_average_n20
            thickness = depth_to - depth_from if depth_to > depth_from else None

            # Compute min/max N20 for Nb column
            n20_min = min(layer_n20) if layer_n20 else None
            n20_max = max(layer_n20) if layer_n20 else None

            # Determine soil_type: wizard override > auto-detection
            st = soil_types[i] if soil_types and i < len(soil_types) else detect_soil_type(description)

            levels.append(SoilLevel(
                level_number=i + 1,
                description=description,
                thickness_m=thickness,
                n20_average=avg_n20,
                depth_from_m=depth_from,
                depth_to_m=depth_to if depth_to > 0 else None,
                n20_min=n20_min,
                n20_max=n20_max,
                soil_type=st,
            ))

        return levels

    # Fallback: single level with global average
    max_depth = max((abs(r.depth_m) for r in all_readings), default=0)
    all_n20 = [r.n20 for r in all_readings if r.n20 < 100]
    st = soil_types[0] if soil_types else "granular"
    return [
        SoilLevel(
            level_number=1,
            description="Nivell principal",
            thickness_m=max_depth if max_depth > 0 else None,
            n20_average=dpsh_data.overall_average_n20,
            depth_from_m=0.0,
            depth_to_m=max_depth if max_depth > 0 else None,
            n20_min=min(all_n20) if all_n20 else None,
            n20_max=max(all_n20) if all_n20 else None,
            soil_type=st,
        )
    ]



def _merge_soil_levels(levels: list[SoilLevel]) -> list[SoilLevel]:
    """
    Merge multiple soil levels into a single representative level.

    Used when Eva decides the multi-level split is not meaningful
    (e.g., thin superficial layer that's just topsoil).
    """
    if not levels or len(levels) <= 1:
        return levels

    # Use the deepest (last) layer's description — this is the bearing material
    # (surface layers are typically topsoil/fill that gets excavated)
    combined_desc = levels[-1].description

    # Overall depth range
    depth_from = levels[0].depth_from_m
    depth_to = max(
        (lvl.depth_to_m for lvl in levels if lvl.depth_to_m is not None),
        default=None,
    )
    thickness = (depth_to - depth_from) if depth_to is not None else None

    # Weighted average N20 by thickness (or simple average if thickness unknown)
    total_weight = 0.0
    weighted_sum = 0.0
    for lvl in levels:
        w = lvl.thickness_m or 1.0
        weighted_sum += lvl.n20_average * w
        total_weight += w
    avg_n20 = weighted_sum / total_weight if total_weight > 0 else levels[0].n20_average

    # Min/max across all levels
    all_mins = [lvl.n20_min for lvl in levels if lvl.n20_min is not None]
    all_maxs = [lvl.n20_max for lvl in levels if lvl.n20_max is not None]

    return [SoilLevel(
        level_number=1,
        description=combined_desc,
        thickness_m=thickness,
        n20_average=avg_n20,
        depth_from_m=depth_from,
        depth_to_m=depth_to,
        n20_min=min(all_mins) if all_mins else None,
        n20_max=max(all_maxs) if all_maxs else None,
        soil_type=levels[-1].soil_type,
    )]


def _resolve_sulfate(
    user_data: dict,
    project_path: Path | None,
) -> float | None:
    """
    Resolve sulfate value: user_data first, then auto-extract from lab PDF.
    """
    value = user_data.get('sulfate_mg_kg')
    if value is not None:
        return value

    if not project_path:
        return None

    try:
        from .lab_extractor import extract_lab_results
        lab = extract_lab_results(project_path)
        if lab.sulfate_mg_kg is not None:
            logger.info(f"Auto-extracted sulfate: {lab.sulfate_mg_kg} mg/kg")
            return lab.sulfate_mg_kg
    except Exception as e:
        logger.debug(f"Lab extraction failed: {e}")

    return None


def _determine_soil_class(dpsh_data: DPSHData | None) -> str:
    """
    Determina la classe de terreny segons CTE.

    Classes:
    - T-1: Terrenys favorables
    - T-2: Terrenys intermedis
    - T-3: Terrenys desfavorables
    """
    if not dpsh_data or not dpsh_data.tests:
        return "T-2"  # Per defecte, intermedi

    avg_n20 = dpsh_data.overall_average_n20

    if avg_n20 >= 30:
        return "T-1"  # Favorable (dens)
    if avg_n20 >= 10:
        return "T-2"  # Intermedi
    return "T-3"  # Desfavorable (fluix)


# === CLI per a testing ===

if __name__ == '__main__':
    import sys

    print("=== G3DT Report Data Model ===\n")
    print("Aquest modul defineix el model de dades unificat per a informes.")
    print("\nClasses disponibles:")
    print("  - ClientData: Dades del client")
    print("  - SoilLevel: Nivell de sol identificat")
    print("  - GeotechnicalParams: Parametres geotecnics")
    print("  - ReportData: Dades completes de l'informe")
    print("\nFuncions:")
    print("  - build_report_data(): Construeix ReportData des de multiples fonts")
    print("  - to_dict(): Serialitza a diccionari JSON")
    print("  - from_dict(): Reconstrueix des de diccionari")

    # Exemple basic
    print("\n--- Exemple basic ---")
    client = ClientData(
        company_name="Exemple SL",
        contact_name="Joan Garcia",
        nif="B12345678",
    )
    print(f"Client: {client.company_name} ({client.nif})")

    params = GeotechnicalParams(
        gamma=2.1,
        cohesion=0.0,
        phi=38.0,
        E=400.0,
    )
    print(f"Params: gamma={params.gamma}, phi={params.phi}, E={params.E}")
