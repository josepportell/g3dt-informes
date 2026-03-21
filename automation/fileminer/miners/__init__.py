"""Miner registry -- maps file extensions to miner classes."""

from __future__ import annotations

from pathlib import Path

from ..base import BaseMiner


def get_miners_for_file(
    file_path: Path,
    project_path: Path,
    source_type: str = "content",
) -> list[BaseMiner]:
    """Get appropriate miner instances for a file based on its extension.

    Args:
        file_path: The file to mine
        project_path: Project root (passed to miner constructor)
        source_type: Source type override (e.g., "dades_camp_excel")

    Returns:
        List of miner instances that can handle this file
    """
    suffix = file_path.suffix.lower()
    miners: list[BaseMiner] = []

    if suffix in ('.xls', '.xlsx'):
        from .excel_miner import ExcelMiner
        miners.append(ExcelMiner(project_path, source_type))
    elif suffix == '.pdf':
        from .pdf_text_miner import PdfTextMiner
        miners.append(PdfTextMiner(project_path, source_type))
    elif suffix == '.txt':
        from .text_miner import TextMiner
        miners.append(TextMiner(project_path, source_type))
    elif suffix in ('.doc', '.docx'):
        from .docx_miner import DocxMiner
        miners.append(DocxMiner(project_path, source_type))

    return miners
