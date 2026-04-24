"""AI pipeline — LLM-first project processing (inventory → classification → conversion → analysis → values → report).

Coexists with the existing deterministic pipeline (FileScanner, FileMiner, ConceptScout).
Stage 1: inventory (this module).
"""

from .inventory import Inventory, InventoryFile, FolderSummary, build_inventory
from .typology import (
    FileClass,
    FolderClass,
    ProjectTypology,
    classify_project,
    load_typology,
    save_typology,
)

__all__ = [
    "Inventory", "InventoryFile", "FolderSummary", "build_inventory",
    "FileClass", "FolderClass", "ProjectTypology",
    "classify_project", "load_typology", "save_typology",
]
