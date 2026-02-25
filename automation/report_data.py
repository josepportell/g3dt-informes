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
    superficie_parcela: float
    superficie_construida: float
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
    is_anthropized: bool = False  # Solar antropitzat (urbanitzat/modificat)

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

    # Override ICGC unit (from 1:25k manual lookup)
    icgc_unit_code: str = ""
    icgc_unit_description: str = ""
    icgc_unit_epoch: str = ""

    # Geomech overrides (Nb, N from user_data.geomech_params)
    _geomech_overrides: dict = field(default_factory=dict)

    # Seccions condicionals
    include_expansivity: bool = False
    include_earth_pressure: bool = False
    include_slope_stability: bool = False
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
    """Auto-detect SPT availability from user_data or sondeig extraction."""
    # 1. Explicit user_data flag
    if user_data.get('has_spt') is True:
        return True
    # 2. Manual SPT data in user_data
    if user_data.get('spt_data'):
        return True
    # 3. Sondeig extraction with SPT results
    if project_path:
        import json
        from pathlib import Path
        sondeig_path = Path(project_path) / 'validation' / 'sondeig_extracted.json'
        if sondeig_path.exists():
            try:
                with open(sondeig_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for test in data.get('sondeig_tests', []):
                    if test.get('spt_results'):
                        return True
            except (json.JSONDecodeError, KeyError):
                pass
    return False


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
    geotechnical_params = None
    geomech = user_data.get('geomech_params', {})
    if dpsh_data and dpsh_data.tests:
        avg_n20 = dpsh_data.overall_average_n20
        try:
            from .cte_geomech import (
                nspt_to_phi, nspt_to_E_kg_cm2, nspt_to_gamma_g_cm3,
                is_rock, rock_params_default,
            )
            if geomech.get('gamma') or geomech.get('phi') or geomech.get('E'):
                gamma = geomech.get('gamma') or nspt_to_gamma_g_cm3(avg_n20)
                phi = geomech.get('phi') or nspt_to_phi(avg_n20)
                E = geomech.get('E') or nspt_to_E_kg_cm2(avg_n20)
                cohesion = geomech.get('cohesion', 0.0)
            elif is_rock(avg_n20):
                rock = rock_params_default()
                gamma, phi, E, cohesion = rock['gamma'], rock['phi'], rock['E'], rock['cohesion']
            else:
                gamma = nspt_to_gamma_g_cm3(avg_n20)
                phi = nspt_to_phi(avg_n20)
                E = nspt_to_E_kg_cm2(avg_n20)
                cohesion = 0.0
        except ImportError:
            # Fallback to old Peck/Hanson if cte_geomech not available
            gamma = geomech.get('gamma') or GeotechCorrelations.n_to_density(avg_n20)
            phi = geomech.get('phi') or GeotechCorrelations.n_to_friction_angle(avg_n20)
            E = geomech.get('E') or GeotechCorrelations.n_to_deformation_modulus(avg_n20)
            cohesion = geomech.get('cohesion', 0.0)
        geotechnical_params = GeotechnicalParams(
            gamma=gamma, cohesion=cohesion, phi=phi, E=E,
        )

    # Genera nivells de sol basics
    soil_levels = _generate_soil_levels(
        dpsh_data,
        user_data.get('num_soil_levels', 1),
        user_data.get('sondeig_layers'),
    )

    # Determina classes CTE
    cte_building_class = classify_building(
        area_m2=user_data.get('superficie_construida_m2', 0),
        floors=user_data.get('num_floors', 'Pb'),
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
        municipality=project.get('municipality', ''),
        report_date=report_date,
        # Client
        client=client,
        # Arquitecte/Projecte
        architect_name=user_data.get('architect_name', ''),
        architect_company=user_data.get('architect_company', ''),
        building_type=user_data.get('building_type', ''),
        num_floors=user_data.get('num_floors', ''),
        superficie_parcela=user_data.get('superficie_parcela_m2', 0.0),
        superficie_construida=user_data.get('superficie_construida_m2', 0.0),
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
        is_anthropized=user_data.get('is_anthropized', False),
        # Dades assaig
        dpsh=dpsh_data,
        sondeig_tests=user_data.get('sondeig_tests'),
        has_sondeig=user_data.get('has_sondeig', files.get('has_sondeig', False)),
        has_spt=_detect_spt(user_data, project_path),
        # Laboratori
        sulfate_mg_kg=user_data.get('sulfate_mg_kg'),
        aggressivity_class="",
        # Valors calculats
        cte_building_class=cte_building_class,
        cte_soil_class=cte_soil_class,
        soil_levels=soil_levels,
        geotechnical_params=geotechnical_params,
        terzaghi_result=terzaghi_result,
        # Override ICGC unit (manual 1:25k lookup)
        icgc_unit_code=user_data.get('icgc_unit_code', ''),
        icgc_unit_description=user_data.get('icgc_unit_description', ''),
        icgc_unit_epoch=user_data.get('icgc_unit_epoch', ''),
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
        superficie_parcela=building.get('superficie_parcela_m2', 0.0),
        superficie_construida=building.get('superficie_construida_m2', 0.0),
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
        is_anthropized=site.get('is_anthropized', False),
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
    )


def _generate_soil_levels(
    dpsh_data: DPSHData | None,
    num_levels: int,
    sondeig_layers: list[dict] | None = None,
) -> list[SoilLevel]:
    """
    Genera nivells de sòl a partir de les capes del sondeig i lectures DPSH.

    Si tenim sondeig_layers (de sondeig_extracted.json), partim les lectures
    DPSH per rang de profunditat i calculem N20 mitjana per capa.
    Si no, retornem un sol nivell amb la mitjana global.
    """
    if not dpsh_data or not dpsh_data.tests:
        return []

    # Collect all readings across all tests (depths are negative)
    all_readings = [r for test in dpsh_data.tests for r in test.readings]

    # If we have sondeig layer boundaries, split readings by depth range
    if sondeig_layers and len(sondeig_layers) > 1:
        levels = []
        for i, layer in enumerate(sondeig_layers):
            depth_from = layer.get('depth_from_m', 0.0)
            depth_to = layer.get('depth_to_m', 0.0)
            description = layer.get('description', f'Nivell {i + 1}')

            # Filter DPSH readings within this layer's depth range
            # Readings have negative depths; layer boundaries are positive
            layer_n20 = [
                r.n20 for r in all_readings
                if depth_from <= abs(r.depth_m) <= depth_to
            ]
            avg_n20 = sum(layer_n20) / len(layer_n20) if layer_n20 else dpsh_data.overall_average_n20
            thickness = depth_to - depth_from if depth_to > depth_from else None

            # Compute min/max N20 for Nb column
            n20_min = min(layer_n20) if layer_n20 else None
            n20_max = max(layer_n20) if layer_n20 else None

            levels.append(SoilLevel(
                level_number=i + 1,
                description=description,
                thickness_m=thickness,
                n20_average=avg_n20,
                depth_from_m=depth_from,
                depth_to_m=depth_to if depth_to > 0 else None,
                n20_min=n20_min,
                n20_max=n20_max,
            ))
        return levels

    # Fallback: single level with global average
    max_depth = max((abs(r.depth_m) for r in all_readings), default=0)
    all_n20 = [r.n20 for r in all_readings]
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
        )
    ]



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
