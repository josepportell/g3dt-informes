"""Tests for Phase B — visual observations schema + synthesis.

Covers:
- schemas/concepts/report_variables.yaml has the 6 visual concepts + site_condition.
- automation/concept_scout/vision_probe.py exposes them to the probe.
- web/wizard_service._synthesize_with_llm gathers + emits the narrative fields.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402


# ---------------------------------------------------------------------------
# Schema checks
# ---------------------------------------------------------------------------

_VISUAL_CONCEPTS = (
    "site_vegetation_visual",
    "site_slope_visual",
    "is_anthropized_visual",
    "building_to_demolish_visual",
    "access_road_visual",
    "surrounding_context_visual",
)


def test_visual_concepts_in_schema():
    """All 6 visual concepts + site_condition registered in concept registry."""
    from automation.schemas.loader import concept_registry
    all_ids = concept_registry.all_concept_ids()
    for cid in _VISUAL_CONCEPTS:
        assert cid in all_ids, f"{cid} missing from schema"
    assert "site_condition" in all_ids, "site_condition missing from schema"


def test_narrative_concepts_have_llm_synthesis_source():
    """The 4 narrative outputs accept llm_synthesis as a valid source."""
    from automation.schemas.loader import concept_registry
    all_ids = concept_registry.all_concept_ids()
    targets = (
        "site_description", "site_condition", "is_anthropized",
        "building_structure_desc",
    )
    for cid in targets:
        assert cid in all_ids, f"{cid} missing from schema"
        concept = concept_registry.get_concept(cid)
        assert concept is not None, f"{cid} not loaded"
        priorities = concept.source_priority or {}
        assert "llm_synthesis" in priorities, (
            f"{cid} should include 'llm_synthesis' in source_priority"
            f" (got {list(priorities)})"
        )


# ---------------------------------------------------------------------------
# vision_probe.py prompt extension
# ---------------------------------------------------------------------------

def test_vision_probe_detects_visual_observations():
    """_VISION_DETECTABLE_CONCEPTS includes the 6 visual concept_ids."""
    from automation.concept_scout.vision_probe import _VISION_DETECTABLE_CONCEPTS
    for cid in _VISUAL_CONCEPTS:
        assert cid in _VISION_DETECTABLE_CONCEPTS, f"{cid} not listed as vision-detectable"


def test_vision_probe_prompt_describes_visual_observations():
    """_PROBE_PROMPT enumerates each visual concept_id so the model knows them."""
    from automation.concept_scout.vision_probe import _PROBE_PROMPT
    for cid in _VISUAL_CONCEPTS:
        assert cid in _PROBE_PROMPT, f"{cid} missing from probe prompt"


# ---------------------------------------------------------------------------
# _gather_visual_observations helper
# ---------------------------------------------------------------------------

def test_gather_visual_observations_reads_concept_map(tmp_path):
    """Helper extracts entries from concept_map.concept_sources for visual concepts."""
    from web.wizard_service import _gather_visual_observations

    cm_dir = tmp_path / "validation"
    cm_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": {"project": tmp_path.name},
        "file_inventory": [],
        "concept_sources": {
            "site_slope_visual": [
                {"file": "FOTOGRAFIES/S1/a.jpg", "signal_preview": "pendent suau", "confidence": 0.8},
                {"file": "FOTOGRAFIES/S1/b.jpg", "signal_preview": "pendent suau", "confidence": 0.7},  # dupe after dedup in prompt formatter
            ],
            "site_vegetation_visual": [
                {"file": "FOTOGRAFIES/S1/a.jpg", "signal_preview": "vegetació rasa", "confidence": 0.9},
            ],
            # Not a visual concept — should be ignored
            "architect_name": [
                {"file": "A.01.pdf", "signal_preview": "JORDI BOSCH", "confidence": 0.95},
            ],
        },
    }
    (cm_dir / "concept_map.json").write_text(json.dumps(payload), encoding="utf-8")

    out = _gather_visual_observations(tmp_path)

    assert "site_slope_visual" in out
    assert len(out["site_slope_visual"]) == 2
    assert out["site_slope_visual"][0]["preview"] == "pendent suau"
    assert "site_vegetation_visual" in out
    # Non-visual concepts are NOT included
    assert "architect_name" not in out


def test_gather_visual_observations_missing_concept_map(tmp_path):
    """Returns {} when concept_map.json is absent — doesn't raise."""
    from web.wizard_service import _gather_visual_observations
    assert _gather_visual_observations(tmp_path) == {}


def test_format_visual_observations_for_prompt_dedupes():
    """Duplicate previews are merged into a single entry for the prompt block."""
    from web.wizard_service import _format_visual_observations_for_prompt

    obs = {
        "site_slope_visual": [
            {"file": "a.jpg", "preview": "pendent suau", "confidence": 0.8},
            {"file": "b.jpg", "preview": "pendent suau", "confidence": 0.7},
            {"file": "c.jpg", "preview": "pendent moderat cap al sud", "confidence": 0.9},
        ],
        "site_vegetation_visual": [
            {"file": "a.jpg", "preview": "vegetació rasa", "confidence": 0.9},
        ],
    }
    out = _format_visual_observations_for_prompt(obs)
    # "pendent suau" appears once, not twice
    assert out.count("pendent suau") == 1
    assert "pendent moderat" in out
    assert "vegetació rasa" in out
    # Short labels used (without _visual suffix)
    assert "site_slope:" in out
    assert "site_vegetation:" in out


def test_format_visual_observations_empty():
    """Empty observations dict yields a helpful placeholder line."""
    from web.wizard_service import _format_visual_observations_for_prompt
    out = _format_visual_observations_for_prompt({})
    assert "no visual observations" in out.lower()


# ---------------------------------------------------------------------------
# _synthesize_with_llm — narrative field extraction
# ---------------------------------------------------------------------------

def _minimal_merged() -> dict:
    return {
        "building_type": {"value": "un habitatge unifamiliar", "source": "vision_planol"},
        "architect_name": {"value": "JORDI BOSCH", "source": "vision_planol"},
        "client_name": {"value": "RAMON MITJANA S.L", "source": "vision_planol"},
        "location_sentence": {"value": "", "source": ""},
        "site_description": {"value": "", "source": ""},
        "site_condition": {"value": "", "source": ""},
        "is_anthropized": {"value": "", "source": ""},
        "building_structure_desc": {"value": "", "source": ""},
        "street_address": {"value": "Carrer Antoni Bellet 12", "source": "vision_planol"},
        "site_municipality": {"value": "Bell-Lloc d'Urgell", "source": "cadastre"},
        "num_floors": {"value": "Pb+1Pp", "source": "vision_planol"},
        "has_basement": {"value": "no", "source": "vision_planol"},
        "building_height_m": {"value": "7.5", "source": "vision_planol"},
        "site_slope_class": {"value": "Pla", "source": "icgc"},
    }


def test_synthesize_extracts_narrative_fields(tmp_path, monkeypatch):
    """When the LLM returns the 8 fields, the 4 narrative ones get applied
    with source='llm_synthesis_with_observations'."""
    from web import wizard_service

    monkeypatch.setattr(wizard_service.config, "ANTHROPIC_API_KEY", "sk-test-key")

    mock_response = mock.MagicMock()
    mock_response.content = [mock.MagicMock(
        text=json.dumps({
            "building_type": "un habitatge unifamiliar",
            "architect_name": "JORDI BOSCH",
            "client_name": "RAMON MITJANA S.L",
            "location_sentence": "al Carrer Antoni Bellet 12 de Bell-Lloc d'Urgell",
            "site_description": "La parcel·la es presenta totalment buida, lliure de construccions i vegetació, presentant un terreny lleugerament inclinat cap al sud.",
            "site_condition": "pla",
            "is_anthropized": "no",
            "building_structure_desc": "en planta baixa",
        }),
    )]
    mock_client = mock.MagicMock()
    mock_client.messages.create.return_value = mock_response

    with mock.patch("automation.llm_client.get_anthropic_client", return_value=mock_client):
        merged = _minimal_merged()
        wizard_service._synthesize_with_llm(merged, tmp_path)

    assert merged["site_description"]["value"].startswith("La parcel·la")
    assert merged["site_description"]["source"] == "llm_synthesis_with_observations"
    assert merged["site_condition"]["value"] == "pla"
    assert merged["site_condition"]["source"] == "llm_synthesis_with_observations"
    assert merged["is_anthropized"]["value"] == "no"
    assert merged["building_structure_desc"]["value"] == "en planta baixa"
    # Identity fields kept separate source (plain llm_synthesis — no _set() override)
    # Note: here architect_name already had vision_planol source, so synthesis
    # cannot overwrite it (trusted source).


def test_synthesis_doesnt_override_user_narrative(tmp_path, monkeypatch):
    """User-edited site_description must not be replaced by synthesis."""
    from web import wizard_service

    monkeypatch.setattr(wizard_service.config, "ANTHROPIC_API_KEY", "sk-test-key")

    mock_response = mock.MagicMock()
    mock_response.content = [mock.MagicMock(
        text=json.dumps({
            "building_type": "", "architect_name": "", "client_name": "",
            "location_sentence": "",
            "site_description": "Synthesis prose that should NOT win.",
            "site_condition": "pla",
            "is_anthropized": "no",
            "building_structure_desc": "",
        }),
    )]
    mock_client = mock.MagicMock()
    mock_client.messages.create.return_value = mock_response

    merged = _minimal_merged()
    merged["site_description"] = {
        "value": "Eva wrote this manually.",
        "source": "user",
    }

    with mock.patch("automation.llm_client.get_anthropic_client", return_value=mock_client):
        wizard_service._synthesize_with_llm(merged, tmp_path)

    # User value preserved
    assert merged["site_description"]["value"] == "Eva wrote this manually."
    assert merged["site_description"]["source"] == "user"
    # Non-user fields still populated
    assert merged["site_condition"]["value"] == "pla"


def test_is_anthropized_normalized_to_si_or_no(tmp_path, monkeypatch):
    """Canonical 'si'/'no' emitted regardless of LLM output variant."""
    from web import wizard_service

    monkeypatch.setattr(wizard_service.config, "ANTHROPIC_API_KEY", "sk-test-key")

    for raw, expected in [
        ("true", "si"), ("yes", "si"), ("sí", "si"), ("SI", "si"), ("1", "si"),
        ("false", "no"), ("no", "no"), ("0", "no"),
    ]:
        mock_response = mock.MagicMock()
        mock_response.content = [mock.MagicMock(
            text=json.dumps({
                "building_type": "", "architect_name": "", "client_name": "",
                "location_sentence": "",
                "site_description": "", "site_condition": "",
                "is_anthropized": raw,
                "building_structure_desc": "",
            }),
        )]
        mock_client = mock.MagicMock()
        mock_client.messages.create.return_value = mock_response

        merged = _minimal_merged()
        with mock.patch(
            "automation.llm_client.get_anthropic_client", return_value=mock_client,
        ):
            wizard_service._synthesize_with_llm(merged, tmp_path)

        assert merged["is_anthropized"]["value"] == expected, (
            f"raw={raw!r}: got {merged['is_anthropized']['value']!r}, "
            f"expected {expected!r}"
        )


# ---------------------------------------------------------------------------
# Diagnostic component attribution
# ---------------------------------------------------------------------------

def test_diagnostic_assigns_visual_synthesis_bucket():
    """classify_source_component routes llm_synthesis_with_observations
    to the new visual_synthesis bucket (not plain llm_synthesis)."""
    from scripts.diagnostic_trace import classify_source_component

    assert classify_source_component("llm_synthesis_with_observations") == "visual_synthesis"
    assert classify_source_component("llm_synthesis") == "llm_synthesis"
    assert classify_source_component("vision_probe:site_photo") == "visual_synthesis"
