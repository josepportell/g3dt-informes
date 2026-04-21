"""Tests for Phase B — per-direction adjacent narrative synthesis.

Covers:
- schemas/concepts/report_variables.yaml has 4 `adjacent_*_fmt` concepts with
  `llm_synthesis` priority between `user` and `formatted_cadastre`.
- web/wizard_service._synthesize_with_llm gates adjacent synthesis on
  ≥2 visual observations and emits per-direction overrides.
- Empty/missing LLM output for a direction leaves the cadastre-template
  value untouched (silent fallback).
- Language hint (CA/ES) propagates into the prompt payload.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402


_ADJACENT_FMT_CONCEPTS = (
    'adjacent_north_fmt',
    'adjacent_south_fmt',
    'adjacent_east_fmt',
    'adjacent_west_fmt',
)


# ---------------------------------------------------------------------------
# Schema checks
# ---------------------------------------------------------------------------

def test_adjacent_fmt_concepts_in_schema():
    """All 4 adjacent_*_fmt concepts are registered."""
    from automation.schemas.loader import concept_registry
    all_ids = concept_registry.all_concept_ids()
    for cid in _ADJACENT_FMT_CONCEPTS:
        assert cid in all_ids, f"{cid} missing from schema"


def test_adjacent_fmt_priority_order():
    """For each adjacent_*_fmt: user < llm_synthesis < formatted_cadastre.

    Mirrors the site_description priority relationship (user beats
    llm_synthesis beats cadastre-template fallback).
    """
    from automation.schemas.loader import concept_registry
    for cid in _ADJACENT_FMT_CONCEPTS:
        concept = concept_registry.get_concept(cid)
        assert concept is not None, f"{cid} not loaded"
        prios = concept.source_priority or {}
        assert 'user' in prios, f"{cid} missing 'user' source priority"
        assert 'llm_synthesis' in prios, f"{cid} missing 'llm_synthesis' source priority"
        assert 'formatted_cadastre' in prios, (
            f"{cid} missing 'formatted_cadastre' source priority"
        )
        # Lower priority number = wins (per ConceptRegistry docs).
        assert prios['user'] < prios['llm_synthesis'], (
            f"{cid}: user ({prios['user']}) must outrank llm_synthesis ({prios['llm_synthesis']})"
        )
        assert prios['llm_synthesis'] < prios['formatted_cadastre'], (
            f"{cid}: llm_synthesis ({prios['llm_synthesis']}) must outrank "
            f"formatted_cadastre ({prios['formatted_cadastre']})"
        )


def test_adjacent_fmt_priority_matches_site_description():
    """llm_synthesis priority for adjacent_*_fmt matches site_description (20)."""
    from automation.schemas.loader import concept_registry
    site_desc = concept_registry.get_concept('site_description')
    assert site_desc is not None
    site_desc_llm_prio = site_desc.source_priority.get('llm_synthesis')
    assert site_desc_llm_prio is not None, "site_description is missing llm_synthesis prio"

    for cid in _ADJACENT_FMT_CONCEPTS:
        concept = concept_registry.get_concept(cid)
        assert concept.source_priority['llm_synthesis'] == site_desc_llm_prio, (
            f"{cid} llm_synthesis prio should mirror site_description's"
        )


# ---------------------------------------------------------------------------
# Synthesis gate + call behaviour
# ---------------------------------------------------------------------------

def _merged_with_cadastre_adjacents(municipality: str = "Bell-Lloc d'Urgell") -> dict:
    """Baseline merged dict where the cadastre template has populated the 4
    adjacent_*_fmt fields (as wizard_service does before _synthesize_with_llm)."""
    return {
        'building_type': {'value': 'un habitatge unifamiliar', 'source': 'vision_planol'},
        'architect_name': {'value': 'JORDI BOSCH', 'source': 'vision_planol'},
        'client_name': {'value': 'RAMON MITJANA S.L', 'source': 'vision_planol'},
        'location_sentence': {'value': '', 'source': ''},
        'site_description': {'value': '', 'source': ''},
        'site_condition': {'value': '', 'source': ''},
        'is_anthropized': {'value': '', 'source': ''},
        'building_structure_desc': {'value': '', 'source': ''},
        'street_address': {'value': 'Carrer Antoni Bellet 12', 'source': 'vision_planol'},
        'site_municipality': {'value': municipality, 'source': 'cadastre'},
        'num_floors': {'value': 'Pb+1Pp', 'source': 'vision_planol'},
        'has_basement': {'value': 'no', 'source': 'vision_planol'},
        'building_height_m': {'value': '7.5', 'source': 'vision_planol'},
        'site_slope_class': {'value': 'Pla', 'source': 'icgc'},
        'adjacent_north': {'value': 'parcel·la buida', 'source': 'cadastre_api'},
        'adjacent_south': {'value': 'Carrer Antoni Bellet', 'source': 'cadastre_api'},
        'adjacent_east': {'value': 'parcel·la buida', 'source': 'cadastre_api'},
        'adjacent_west': {'value': 'parcel·la buida', 'source': 'cadastre_api'},
        'adjacent_north_fmt': {
            'value': 'Per la part nord amb una parcel·la buida.',
            'source': 'formatted from Cadastre',
        },
        'adjacent_south_fmt': {
            'value': 'Per la part sud amb el Carrer Antoni Bellet.',
            'source': 'formatted from Cadastre',
        },
        'adjacent_east_fmt': {
            'value': 'Per la part est amb una parcel·la buida.',
            'source': 'formatted from Cadastre',
        },
        'adjacent_west_fmt': {
            'value': 'I finalment, per la part oest amb una parcel·la buida.',
            'source': 'formatted from Cadastre',
        },
    }


def _patch_gather(monkeypatch, observations: dict):
    """Stub _gather_visual_observations to return a fixed observation set."""
    from web import wizard_service
    monkeypatch.setattr(
        wizard_service, '_gather_visual_observations',
        lambda _p: observations,
    )


def _mock_llm(monkeypatch, result: dict) -> mock.MagicMock:
    """Install a mock Anthropic client returning `result` as JSON text.

    Returns the mock client so tests can inspect the prompt payload.
    """
    from web import wizard_service
    monkeypatch.setattr(wizard_service.config, 'ANTHROPIC_API_KEY', 'sk-test')

    mock_response = mock.MagicMock()
    mock_response.content = [mock.MagicMock(text=json.dumps(result))]
    mock_client = mock.MagicMock()
    mock_client.messages.create.return_value = mock_response

    monkeypatch.setattr(
        'automation.llm_client.get_anthropic_client',
        lambda: mock_client,
    )
    return mock_client


def test_gate_triggers_when_visuals_sufficient(tmp_path, monkeypatch):
    """≥2 visual observations → adjacent_*_fmt appear in the LLM prompt."""
    from web import wizard_service

    observations = {
        'site_slope_visual': [{'file': 'a.jpg', 'preview': 'pla', 'confidence': 0.9}],
        'site_vegetation_visual': [
            {'file': 'b.jpg', 'preview': 'vegetació rasa', 'confidence': 0.9},
        ],
    }
    _patch_gather(monkeypatch, observations)

    mock_client = _mock_llm(monkeypatch, {
        'building_type': '', 'architect_name': '', 'client_name': '',
        'location_sentence': '', 'site_description': '', 'site_condition': '',
        'is_anthropized': '', 'building_structure_desc': '',
        'adjacent_north_fmt': 'Per la part nord amb una parcel·la buida amb vegetació rasa.',
        'adjacent_south_fmt': 'Per la part sud amb el Carrer Antoni Bellet.',
        'adjacent_east_fmt': 'Per la part est amb una parcel·la buida amb vegetació rasa.',
        'adjacent_west_fmt': 'I finalment, per la part oest amb una parcel·la buida.',
    })

    merged = _merged_with_cadastre_adjacents()
    wizard_service._synthesize_with_llm(merged, tmp_path)

    # Inspect the prompt that was sent to the LLM.
    assert mock_client.messages.create.called
    call = mock_client.messages.create.call_args
    prompt_text = call.kwargs['messages'][0]['content']
    for cid in _ADJACENT_FMT_CONCEPTS:
        assert cid in prompt_text, f"{cid} missing from prompt payload"
    # Eva-voice instruction from the task spec
    assert "Eva's voice" in prompt_text
    assert 'MUST NOT invent' in prompt_text


def test_gate_blocks_when_visuals_below_threshold(tmp_path, monkeypatch):
    """0 or 1 visuals → adjacent_*_fmt NOT included in prompt payload and the
    cadastre-template values remain in merged."""
    from web import wizard_service

    # Case A: zero observations
    _patch_gather(monkeypatch, {})
    mock_client = _mock_llm(monkeypatch, {
        'building_type': '', 'architect_name': '', 'client_name': '',
        'location_sentence': '', 'site_description': '', 'site_condition': '',
        'is_anthropized': '', 'building_structure_desc': '',
    })

    merged = _merged_with_cadastre_adjacents()
    wizard_service._synthesize_with_llm(merged, tmp_path)

    prompt_text = mock_client.messages.create.call_args.kwargs['messages'][0]['content']
    for cid in _ADJACENT_FMT_CONCEPTS:
        assert cid not in prompt_text, f"{cid} should not appear in prompt when gate closed"
    # Cadastre-template values untouched
    assert merged['adjacent_north_fmt']['source'] == 'formatted from Cadastre'
    assert merged['adjacent_south_fmt']['source'] == 'formatted from Cadastre'

    # Case B: exactly one observation — still blocked
    _patch_gather(monkeypatch, {
        'site_slope_visual': [{'file': 'a.jpg', 'preview': 'pla', 'confidence': 0.9}],
    })
    mock_client = _mock_llm(monkeypatch, {
        'building_type': '', 'architect_name': '', 'client_name': '',
        'location_sentence': '', 'site_description': '', 'site_condition': '',
        'is_anthropized': '', 'building_structure_desc': '',
    })

    merged = _merged_with_cadastre_adjacents()
    wizard_service._synthesize_with_llm(merged, tmp_path)

    prompt_text = mock_client.messages.create.call_args.kwargs['messages'][0]['content']
    for cid in _ADJACENT_FMT_CONCEPTS:
        assert cid not in prompt_text, f"{cid} should not appear in prompt with single visual"
    assert merged['adjacent_north_fmt']['source'] == 'formatted from Cadastre'


def test_empty_llm_adjacent_leaves_cadastre_fallback(tmp_path, monkeypatch):
    """When the LLM returns an empty string for one direction, the cadastre
    template value stays in place (silent fallback)."""
    from web import wizard_service

    _patch_gather(monkeypatch, {
        'site_slope_visual': [{'file': 'a.jpg', 'preview': 'pla', 'confidence': 0.9}],
        'site_vegetation_visual': [
            {'file': 'b.jpg', 'preview': 'rasa', 'confidence': 0.9},
        ],
    })

    _mock_llm(monkeypatch, {
        'building_type': '', 'architect_name': '', 'client_name': '',
        'location_sentence': '', 'site_description': '', 'site_condition': '',
        'is_anthropized': '', 'building_structure_desc': '',
        # North gets new value, others return empty — cadastre should remain.
        'adjacent_north_fmt': 'Per la part nord amb una parcel·la buida amb vegetació rasa.',
        'adjacent_south_fmt': '',
        'adjacent_east_fmt': '',
        'adjacent_west_fmt': '',
    })

    merged = _merged_with_cadastre_adjacents()
    wizard_service._synthesize_with_llm(merged, tmp_path)

    # North overridden by synthesis
    assert merged['adjacent_north_fmt']['source'] == 'llm_synthesis_with_observations'
    assert 'vegetació rasa' in merged['adjacent_north_fmt']['value']

    # South/east/west keep cadastre-template value + source
    for d in ('south', 'east', 'west'):
        key = f'adjacent_{d}_fmt'
        assert merged[key]['source'] == 'formatted from Cadastre', (
            f"{key} should retain cadastre-template source, got {merged[key]}"
        )


def test_adjacent_synthesis_respects_user_edit(tmp_path, monkeypatch):
    """User-edited adjacent_*_fmt is never overwritten by synthesis."""
    from web import wizard_service

    _patch_gather(monkeypatch, {
        'site_slope_visual': [{'file': 'a.jpg', 'preview': 'pla', 'confidence': 0.9}],
        'site_vegetation_visual': [
            {'file': 'b.jpg', 'preview': 'rasa', 'confidence': 0.9},
        ],
    })

    _mock_llm(monkeypatch, {
        'building_type': '', 'architect_name': '', 'client_name': '',
        'location_sentence': '', 'site_description': '', 'site_condition': '',
        'is_anthropized': '', 'building_structure_desc': '',
        'adjacent_north_fmt': 'Synthesis prose that must NOT win.',
        'adjacent_south_fmt': '', 'adjacent_east_fmt': '', 'adjacent_west_fmt': '',
    })

    merged = _merged_with_cadastre_adjacents()
    merged['adjacent_north_fmt'] = {
        'value': "Eva's hand-written north description.",
        'source': 'user',
    }
    wizard_service._synthesize_with_llm(merged, tmp_path)

    assert merged['adjacent_north_fmt']['source'] == 'user'
    assert merged['adjacent_north_fmt']['value'] == "Eva's hand-written north description."


def test_language_hint_catalan_by_default(tmp_path, monkeypatch):
    """Catalan-majority signals → Catalan direction labels in prompt."""
    from web import wizard_service

    _patch_gather(monkeypatch, {
        'site_slope_visual': [{'file': 'a.jpg', 'preview': 'pla', 'confidence': 0.9}],
        'site_vegetation_visual': [
            {'file': 'b.jpg', 'preview': 'rasa', 'confidence': 0.9},
        ],
    })
    mock_client = _mock_llm(monkeypatch, {
        'building_type': '', 'architect_name': '', 'client_name': '',
        'location_sentence': '', 'site_description': '', 'site_condition': '',
        'is_anthropized': '', 'building_structure_desc': '',
        'adjacent_north_fmt': '', 'adjacent_south_fmt': '',
        'adjacent_east_fmt': '', 'adjacent_west_fmt': '',
    })

    merged = _merged_with_cadastre_adjacents(municipality="Bell-Lloc d'Urgell")
    wizard_service._synthesize_with_llm(merged, tmp_path)

    prompt_text = mock_client.messages.create.call_args.kwargs['messages'][0]['content']
    # Catalan direction labels + language name
    assert 'nord/sud/est/oest' in prompt_text
    assert 'Catalan' in prompt_text


def test_language_hint_spanish_for_es_municipality(tmp_path, monkeypatch):
    """Spanish-municipality signals → Spanish direction labels in prompt."""
    from web import wizard_service

    _patch_gather(monkeypatch, {
        'site_slope_visual': [{'file': 'a.jpg', 'preview': 'llano', 'confidence': 0.9}],
        'site_vegetation_visual': [
            {'file': 'b.jpg', 'preview': 'sin vegetación', 'confidence': 0.9},
        ],
    })
    mock_client = _mock_llm(monkeypatch, {
        'building_type': '', 'architect_name': '', 'client_name': '',
        'location_sentence': '', 'site_description': '', 'site_condition': '',
        'is_anthropized': '', 'building_structure_desc': '',
        'adjacent_north_fmt': '', 'adjacent_south_fmt': '',
        'adjacent_east_fmt': '', 'adjacent_west_fmt': '',
    })

    # Use a Spanish municipality (Anciles is listed in _ES_MUNICIPALITIES)
    merged = _merged_with_cadastre_adjacents(municipality='Anciles')
    wizard_service._synthesize_with_llm(merged, tmp_path)

    prompt_text = mock_client.messages.create.call_args.kwargs['messages'][0]['content']
    assert 'norte/sur/este/oeste' in prompt_text
    assert 'Spanish' in prompt_text
