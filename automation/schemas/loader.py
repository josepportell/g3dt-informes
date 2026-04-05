from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from .models import ConceptDefinition, FormatSchema

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Project root detection
# ---------------------------------------------------------------------------

def _find_project_root() -> Path:
    """Return the project root (parent of the automation/ package)."""
    return Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# ConceptRegistry
# ---------------------------------------------------------------------------

class ConceptRegistry:
    """Loads concept definitions from schemas/concepts/report_variables.yaml."""

    def __init__(self) -> None:
        self._concepts: dict[str, ConceptDefinition] = {}
        self._loaded = False

    # -- lazy loading -------------------------------------------------------

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        path = _find_project_root() / "schemas" / "concepts" / "report_variables.yaml"
        if not path.exists():
            logger.warning("Concept definitions not found at %s — registry empty", path)
            return
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Failed to parse %s — registry empty", path, exc_info=True)
            return
        if not isinstance(raw, dict):
            logger.warning("Expected top-level dict in %s, got %s", path, type(raw).__name__)
            return
        concepts_raw = raw.get("concepts", {})
        if isinstance(concepts_raw, dict):
            # YAML format: {concept_id: {fields...}}
            for cid, fields in concepts_raw.items():
                if not isinstance(fields, dict):
                    logger.warning("Skipping invalid concept entry: %s", cid, exc_info=True)
                    continue
                try:
                    concept = ConceptDefinition(concept_id=cid, **fields)
                    self._concepts[concept.concept_id] = concept
                except Exception:
                    logger.warning("Skipping invalid concept entry: %s", cid, exc_info=True)
        elif isinstance(concepts_raw, list):
            # Alternative format: [{concept_id: ..., fields...}, ...]
            for item in concepts_raw:
                try:
                    concept = ConceptDefinition(**item)
                    self._concepts[concept.concept_id] = concept
                except Exception:
                    logger.warning("Skipping invalid concept entry: %s", item, exc_info=True)

    # -- public API ---------------------------------------------------------

    def get_concept(self, concept_id: str) -> ConceptDefinition | None:
        self._ensure_loaded()
        return self._concepts.get(concept_id)

    def get_priority(self, concept_id: str, source_type: str) -> int:
        """Return the source priority for a concept.

        If the concept is not found or the source is not in its priorities,
        returns 50 (the default for unknown sources).
        """
        self._ensure_loaded()
        concept = self._concepts.get(concept_id)
        if concept is None:
            return 50
        return concept.source_priority.get(source_type, 50)

    def all_concept_ids(self) -> set[str]:
        self._ensure_loaded()
        return set(self._concepts.keys())

    def get_default_priority(self, source_type: str) -> int:
        """Fallback priority when concept_id is unknown.

        Scans all concepts and returns the *minimum* (best) priority
        registered for this source_type across any concept.  If no concept
        mentions the source_type, returns 50.

        This mirrors the behaviour of the flat SOURCE_PRIORITY dict in
        label_map.py: a single global number per source_type.
        """
        self._ensure_loaded()
        best: int | None = None
        for concept in self._concepts.values():
            prio = concept.source_priority.get(source_type)
            if prio is not None and (best is None or prio < best):
                best = prio
        return best if best is not None else 50


# ---------------------------------------------------------------------------
# FormatRegistry
# ---------------------------------------------------------------------------

class FormatRegistry:
    """Loads format schemas from schemas/formats/*.yaml and learned/**/*.yaml."""

    def __init__(self) -> None:
        self._formats: dict[str, FormatSchema] = {}
        self._loaded = False

    # -- lazy loading -------------------------------------------------------

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        base = _find_project_root() / "schemas" / "formats"
        if not base.exists():
            logger.warning("Format schemas directory not found at %s — registry empty", base)
            return
        yaml_files = list(base.glob("*.yaml")) + list(base.glob("learned/**/*.yaml"))
        for path in yaml_files:
            try:
                raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            except Exception:
                logger.warning("Failed to parse %s — skipping", path, exc_info=True)
                continue
            if not isinstance(raw, dict):
                logger.warning("Expected top-level dict in %s, got %s", path, type(raw).__name__)
                continue
            try:
                fmt = FormatSchema(**raw)
                self._formats[fmt.format_id] = fmt
            except Exception:
                logger.warning("Skipping invalid format in %s", path, exc_info=True)

    # -- public API ---------------------------------------------------------

    def get_format(self, format_id: str) -> FormatSchema | None:
        self._ensure_loaded()
        return self._formats.get(format_id)

    def formats_for_role(self, role: str) -> list[FormatSchema]:
        self._ensure_loaded()
        return [f for f in self._formats.values() if role in f.document_roles]

    def label_to_concept(self, label: str, format_id: str | None = None) -> str | None:
        """Given an uppercase label, return the concept_id it maps to.

        If *format_id* is given, search that format first.  Falls back to
        searching all formats (first match wins).
        """
        self._ensure_loaded()
        upper = label.upper()

        if format_id is not None:
            fmt = self._formats.get(format_id)
            if fmt is not None:
                for mapping in fmt.label_mappings:
                    if upper in mapping.labels:
                        return mapping.concept_id

        for fmt in self._formats.values():
            if fmt.format_id == format_id:
                continue  # already searched above
            for mapping in fmt.label_mappings:
                if upper in mapping.labels:
                    return mapping.concept_id

        return None

    def build_label_map(self) -> dict[str, str]:
        """Build a flat {UPPERCASE_LABEL: concept_id} dict.

        This is the backward-compatibility bridge that replaces
        LABEL_TO_VARIABLE in label_map.py.  All format schemas' label
        mappings are merged.  In case of conflicts the first format loaded
        wins (alphabetical by file path due to glob ordering).
        """
        self._ensure_loaded()
        result: dict[str, str] = {}
        for fmt in self._formats.values():
            for mapping in fmt.label_mappings:
                for lbl in mapping.labels:
                    if lbl not in result:
                        result[lbl] = mapping.concept_id
        return result


# ---------------------------------------------------------------------------
# Module-level singletons (lazy)
# ---------------------------------------------------------------------------

class _LazyProxy:
    """Delays construction until first attribute access."""

    def __init__(self, factory: type) -> None:
        self._factory = factory
        self._instance: Any = None

    def _resolve(self) -> Any:
        if self._instance is None:
            self._instance = self._factory()
        return self._instance

    def __getattr__(self, name: str) -> Any:
        return getattr(self._resolve(), name)


concept_registry: ConceptRegistry = _LazyProxy(ConceptRegistry)  # type: ignore[assignment]
format_registry: FormatRegistry = _LazyProxy(FormatRegistry)  # type: ignore[assignment]
