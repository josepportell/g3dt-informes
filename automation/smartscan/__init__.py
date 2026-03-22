"""
SmartScan — 3-tier file classification for G3DT projects.

Usage:
    from automation.smartscan import scan_project

    result = scan_project('reference-material/4001612 BELL-LLOC')
    print(result.role_map)

    # Backward compatibility with FileScanner:
    file_mapping = result.to_file_mapping()
"""

from .classifier import scan_project
from .models import (
    ClassificationTier,
    FileClassification,
    SmartScanResult,
)

__all__ = [
    'scan_project',
    'ClassificationTier',
    'FileClassification',
    'SmartScanResult',
]
