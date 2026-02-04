"""
G3DT Section Generators Package

Per-section content generators for geotechnical reports.

Usage:
    from automation.sections import (
        Section1Generator, Section2Generator,
        Section3Generator, Section4Generator
    )

    generator1 = Section1Generator(report_data)
    content1 = generator1.generate_all()
"""

from .section1_presentacio import (
    Section1Generator,
    Section1Content,
)
from .section2_treballs import (
    Section2Generator,
    Section2Content,
)
from .section3_geologia import (
    Section3Generator,
    Section3Content,
)
from .section4_conclusions import (
    Section4Generator,
    Section4Content,
    GeotechParamsRow,
)

__all__ = [
    'Section1Generator',
    'Section1Content',
    'Section2Generator',
    'Section2Content',
    'Section3Generator',
    'Section3Content',
    'Section4Generator',
    'Section4Content',
    'GeotechParamsRow',
]
