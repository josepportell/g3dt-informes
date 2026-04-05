"""
Format Writer.

Serializes Eva-confirmed format mappings to YAML files under
schemas/formats/learned/{role}/.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


def _find_project_root() -> Path:
    """Return the project root (parent of the automation/ package)."""
    return Path(__file__).resolve().parent.parent.parent


def write_learned_format(
    role: str,
    source_file: str,
    confirmed_mappings: list[dict],
    format_name: str | None = None,
) -> Path | None:
    """Write a learned format schema YAML file.

    Args:
        role: SmartScan role (e.g., "architect_plan")
        source_file: Original file name that triggered learning
        confirmed_mappings: List of {"label": "...", "concept_id": "..."} dicts
        format_name: Human-readable name (auto-generated if None)

    Returns:
        Path to created YAML file, or None if nothing to save
    """
    if not confirmed_mappings:
        return None

    # Generate format_id from role + labels hash
    labels_str = "|".join(sorted(m["label"] for m in confirmed_mappings))
    hash_suffix = hashlib.sha256(labels_str.encode()).hexdigest()[:8]
    format_id = f"learned_{role}_{hash_suffix}"

    if not format_name:
        format_name = f"Learned format: {role} ({source_file})"

    # Group mappings by concept_id
    label_groups: dict[str, list[str]] = {}
    for m in confirmed_mappings:
        cid = m["concept_id"]
        lbl = m["label"].upper()
        label_groups.setdefault(cid, []).append(lbl)

    label_mappings = []
    for concept_id, labels in sorted(label_groups.items()):
        label_mappings.append({
            "labels": sorted(set(labels)),
            "concept_id": concept_id,
            "confidence": 0.95,
        })

    schema = {
        "format_id": format_id,
        "name": format_name,
        "description": f"Auto-generated from Eva's confirmation on {source_file}",
        "document_roles": [role],
        "source_type": _role_to_source_type(role),
        "created_by": "eva",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_project_file": source_file,
        "label_mappings": label_mappings,
    }

    # Save to schemas/formats/learned/{role}/
    learned_dir = _find_project_root() / "schemas" / "formats" / "learned" / role
    learned_dir.mkdir(parents=True, exist_ok=True)
    out_path = learned_dir / f"{format_id}.yaml"
    out_path.write_text(
        yaml.dump(schema, default_flow_style=False, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    logger.info("Saved learned format: %s -> %s", format_id, out_path)
    return out_path


def _role_to_source_type(role: str) -> str:
    """Map SmartScan role to SOURCE_PRIORITY key."""
    mapping = {
        "architect_plan": "planol_vision",
        "dpsh_excel": "dades_camp_excel",
        "dpsh_field_sheet": "dpsh_vision",
        "sondeig_field_sheet": "sondeig_vision",
        "sondeig_annex": "sondeig_vision",
        "pressupost_pdf": "pressupost_pdf",
    }
    return mapping.get(role, "content_pdf")
