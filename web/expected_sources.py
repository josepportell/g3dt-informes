"""Expected-source hints for wizard concepts.

Maps each concept_id that typically comes from a specific project-file role
to (group_label, [role_hints]). Used by the wizard to group missing fields
in the "Missing info" drawer, and to label the upload zone Eva sees.

Concepts without an entry fall back to a synthetic "Altres" group.

This lives in Python rather than in `schemas/concepts/report_variables.yaml`
intentionally: we want to iterate on mappings quickly without schema churn.
Once a mapping is stable in practice, it can graduate to the YAML schema.
"""
from __future__ import annotations

CONFIDENCE_THRESHOLD: float = 0.7

_PLANOL = "Plànol arquitecte"
_PLANOL_ROLES = ["architect_plan", "architect_plan_with_points", "projecte_arquitecte"]

EXPECTED_SOURCE_MAP: dict[str, tuple[str, list[str]]] = {
    # Identity fields read from the architect's planol (A.01.pdf / A01_*.pdf).
    "architect_name":         (_PLANOL, _PLANOL_ROLES),
    "architect_company":      (_PLANOL, _PLANOL_ROLES),
    "client_name":            (_PLANOL, _PLANOL_ROLES),
    "contact_name":           (_PLANOL, _PLANOL_ROLES),
    "client_email":           (_PLANOL, _PLANOL_ROLES),
    "client_phone":           (_PLANOL, _PLANOL_ROLES),
    "client_nif":             (_PLANOL, _PLANOL_ROLES),

    # Building attributes read from the architect's planol.
    "num_floors":             (_PLANOL, _PLANOL_ROLES),
    "building_height_m":      (_PLANOL, _PLANOL_ROLES),
    "building_type":          (_PLANOL, _PLANOL_ROLES),
    "has_basement":           (_PLANOL, _PLANOL_ROLES),
    "has_retaining_walls":    (_PLANOL, _PLANOL_ROLES),

    # Parcel dimensions read from the architect's planol.
    "superficie_parcela":     (_PLANOL, _PLANOL_ROLES),
    "superficie_construida":  (_PLANOL, _PLANOL_ROLES),
    "parcel_shape":           (_PLANOL, _PLANOL_ROLES),

    # Location / adjacents from the planol's caixetí and surrounding cotes.
    "street_address":         (_PLANOL, _PLANOL_ROLES),
    "adjacent_north":         (_PLANOL, _PLANOL_ROLES),
    "adjacent_south":         (_PLANOL, _PLANOL_ROLES),
    "adjacent_east":          (_PLANOL, _PLANOL_ROLES),
    "adjacent_west":          (_PLANOL, _PLANOL_ROLES),
}


def expected_source_for(concept_id: str) -> tuple[str, list[str]] | None:
    """Return (group_label, role_hints) for a concept, or None if not mapped."""
    return EXPECTED_SOURCE_MAP.get(concept_id)
