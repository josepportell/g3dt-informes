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
]

__version__ = '0.2.0'
