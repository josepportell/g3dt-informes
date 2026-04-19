"""Folder-name miner -- emits a deterministic expedient signal from the project folder name.

G3DT project folders follow the convention `<7-digit expedient> <MUNICIPALITY>`
(e.g. `4001607 LINYOLA`). When the first whitespace-separated token matches
`^\\d{7}$`, we emit an `expedient` signal with `source_type = "folder_name"`.

This is defense-in-depth: the per-concept priority in
`schemas/concepts/report_variables.yaml` gives `folder_name` priority 15 for
expedient, which beats any regex-mined candidate from document text.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..models import Signal, SignalType

# G3DT expedient convention: 7 consecutive digits (e.g. 4001607, 3001621).
_EXPEDIENT_TOKEN_RE = re.compile(r"^\d{7}$")


def emit_folder_name_signals(project_path: Path) -> list[Signal]:
    """Return deterministic signals derived from the project folder basename.

    Currently emits one `expedient` signal when the folder basename's first
    whitespace-separated token is exactly 7 digits. Returns an empty list if
    no match (we never guess).
    """
    folder_name = project_path.name
    first_token = folder_name.split(maxsplit=1)[0] if folder_name else ""

    if not _EXPEDIENT_TOKEN_RE.fullmatch(first_token):
        return []

    return [
        Signal(
            type=SignalType.TEXT,
            label="folder_name",
            value=first_token,
            raw_value=folder_name,
            maps_to="expedient",
            concept_id="expedient",
            source_file="",
            source_location="project folder basename",
            extraction_method="folder_name",
            confidence=1.0,
        ),
    ]
