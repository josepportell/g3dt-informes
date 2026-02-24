"""
G3DT Report Automation Package

Modules for extracting data from G3DT project folders and generating
geotechnical reports.

Usage:
    from automation import DPSHExtractor, ProjectExtractor

    # Extract DPSH data only
    dpsh = DPSHExtractor('path/to/DPSH.xls')
    data = dpsh.extract_all()

    # Extract all project data
    project = ProjectExtractor('path/to/project/folder')
    data = project.extract_all()
"""

from .dpsh_extractor import (
    DPSHExtractor,
    DPSHData,
    DPSHTest,
    DPSHReading,
    GeotechCorrelations,
)

from .project_extractor import (
    ProjectExtractor,
    ProjectData,
    ClientData,
    FileInventory,
)

from .terzaghi_calculator import (
    TerzaghiCalculator,
    BearingCapacityResult,
    BearingCapacityFactors,
    FootingShape,
    calculate_from_dpsh,
)

from .data_schema import (
    DATA_ENTRY_SCHEMA,
    FieldDefinition,
    ValidationError,
    validate_data,
    validate_field,
    coerce_type,
    coerce_all,
    to_json_schema,
    get_required_fields,
)

from .cte_classifier import (
    CTEClassification,
    parse_floor_count,
    classify_building,
    classify_soil,
    get_cte_classification,
)

from .lab_extractor import (
    LabTestResult,
    LabResults,
    extract_lab_results,
)

from .report_generator import (
    ReportGenerator,
    GenerationResult,
)

from .folder_utils import parse_folder_name

__all__ = [
    'DPSHExtractor',
    'DPSHData',
    'DPSHTest',
    'DPSHReading',
    'GeotechCorrelations',
    'ProjectExtractor',
    'ProjectData',
    'ClientData',
    'FileInventory',
    'TerzaghiCalculator',
    'BearingCapacityResult',
    'BearingCapacityFactors',
    'FootingShape',
    'calculate_from_dpsh',
    'DATA_ENTRY_SCHEMA',
    'FieldDefinition',
    'ValidationError',
    'validate_data',
    'validate_field',
    'coerce_type',
    'coerce_all',
    'to_json_schema',
    'get_required_fields',
    'CTEClassification',
    'parse_floor_count',
    'classify_building',
    'classify_soil',
    'get_cte_classification',
    'LabTestResult',
    'LabResults',
    'extract_lab_results',
    'ReportGenerator',
    'GenerationResult',
    'parse_folder_name',
]

__version__ = '0.5.0'
