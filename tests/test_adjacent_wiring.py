"""Tests that synthesized/edited adjacent_*_fmt values reach the report
and survive the wizard save round-trip.

Covers:
- Fix 1 (report_generator): user + llm_synthesis_with_observations sources
  take precedence over the cadastre-template fallback per direction.
- Fix 1 fallback: empty user_data adjacent_*_fmt falls back to the cadastre
  template output.
- Fix 2 (wizard.save_wizard_data): round-trip of adjacent_*_fmt via
  user_data.json persists the fields and their sources.
- Fix 4 (_synthesize_with_llm): if ALL 4 cadastre adjacent_fmt values are
  empty/whitespace, the adjacent block must NOT appear in the prompt even
  when the ≥2 visual observation gate would otherwise fire.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402


# ---------------------------------------------------------------------------
# Fix 1 — resolve_adjacent_fmt precedence
# ---------------------------------------------------------------------------

def test_resolve_adjacent_fmt_prefers_llm_synthesis_value():
    from automation.adjacent_formatter import resolve_adjacent_fmt

    adj = {
        'north': 'parcel·la buida',
        'south': 'Carrer Antoni Bellet',
        'east': 'parcel·la buida',
        'west': 'parcel·la buida',
    }
    user_data = {
        'adjacent_north_fmt': 'Per la part nord amb X amb vegetació rasa.',
        '_sources': {
            'adjacent_north_fmt': 'llm_synthesis_with_observations',
        },
    }
    resolved = resolve_adjacent_fmt(adj, user_data, municipality="Bell-Lloc d'Urgell")
    assert resolved['adjacent_north_fmt'] == 'Per la part nord amb X amb vegetació rasa.'
    # Other directions fall back to cadastre template
    assert 'Per la part sud amb el Carrer Antoni Bellet' in resolved['adjacent_south_fmt']


def test_resolve_adjacent_fmt_prefers_user_value():
    from automation.adjacent_formatter import resolve_adjacent_fmt

    adj = {
        'north': 'parcel·la buida',
        'south': 'Carrer Antoni Bellet',
        'east': 'parcel·la buida',
        'west': 'parcel·la buida',
    }
    user_data = {
        'adjacent_south_fmt': "Eva's hand-written south sentence.",
        '_sources': {'adjacent_south_fmt': 'user'},
    }
    resolved = resolve_adjacent_fmt(adj, user_data, municipality="Bell-Lloc d'Urgell")
    assert resolved['adjacent_south_fmt'] == "Eva's hand-written south sentence."


def test_resolve_adjacent_fmt_falls_back_to_cadastre_when_no_user_value():
    from automation.adjacent_formatter import resolve_adjacent_fmt

    adj = {
        'north': 'parcel·la buida',
        'south': 'Carrer Antoni Bellet',
        'east': 'parcel·la buida',
        'west': 'parcel·la buida',
    }
    user_data: dict = {}  # no adjacent_*_fmt, no _sources
    resolved = resolve_adjacent_fmt(adj, user_data, municipality="Bell-Lloc d'Urgell")
    assert 'nord' in resolved['adjacent_north_fmt'].lower()
    assert 'Carrer Antoni Bellet' in resolved['adjacent_south_fmt']


def test_resolve_adjacent_fmt_ignores_untrusted_source():
    """A non-trusted source tag must not override the cadastre template."""
    from automation.adjacent_formatter import resolve_adjacent_fmt

    adj = {
        'north': 'parcel·la buida',
        'south': 'Carrer Antoni Bellet',
        'east': 'parcel·la buida',
        'west': 'parcel·la buida',
    }
    user_data = {
        'adjacent_north_fmt': 'Should not appear',
        '_sources': {'adjacent_north_fmt': 'formatted from Cadastre'},
    }
    resolved = resolve_adjacent_fmt(adj, user_data, municipality="Bell-Lloc d'Urgell")
    # Cadastre template wins because source is not in the trusted set
    assert 'Should not appear' not in resolved['adjacent_north_fmt']


def test_resolve_adjacent_fmt_empty_user_value_falls_back():
    from automation.adjacent_formatter import resolve_adjacent_fmt

    adj = {
        'north': 'parcel·la buida',
        'south': '', 'east': '', 'west': '',
    }
    user_data = {
        'adjacent_north_fmt': '',
        '_sources': {'adjacent_north_fmt': 'llm_synthesis_with_observations'},
    }
    resolved = resolve_adjacent_fmt(adj, user_data, municipality="Bell-Lloc d'Urgell")
    # Empty string user value should NOT win; cadastre template fills in
    assert 'nord' in resolved['adjacent_north_fmt'].lower()


# ---------------------------------------------------------------------------
# Fix 2 — save_wizard_data persists adjacent_*_fmt round-trip
# ---------------------------------------------------------------------------

def test_save_wizard_data_persists_adjacent_fmt_round_trip(tmp_path):
    from automation.wizard import save_wizard_data

    project = tmp_path / 'demo-project'
    project.mkdir()

    wizard_fields = {
        'adjacent_north_fmt': 'Per la part nord amb una parcel·la buida amb vegetació rasa.',
        'adjacent_south_fmt': 'Per la part sud amb el Carrer Antoni Bellet.',
        'adjacent_east_fmt': 'Per la part est amb una parcel·la buida.',
        'adjacent_west_fmt': 'I finalment, per la part oest amb una parcel·la buida.',
    }
    sources = {
        'adjacent_north_fmt': 'llm_synthesis_with_observations',
        'adjacent_south_fmt': 'formatted from Cadastre',
        'adjacent_east_fmt': 'user',
        'adjacent_west_fmt': 'llm_synthesis_with_observations',
    }
    path = save_wizard_data(project, wizard_fields, sources=sources)

    loaded = json.loads(path.read_text(encoding='utf-8'))
    for key, val in wizard_fields.items():
        assert loaded[key] == val, f"{key} lost on round-trip"
    for key, src in sources.items():
        assert loaded['_sources'][key] == src, f"{key} source lost on round-trip"


# ---------------------------------------------------------------------------
# Fix 4 — empty-cadastre edge case: skip adjacent block entirely
# ---------------------------------------------------------------------------

def _mock_llm(monkeypatch, result: dict) -> mock.MagicMock:
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


def _patch_gather(monkeypatch, observations: dict):
    from web import wizard_service
    monkeypatch.setattr(
        wizard_service, '_gather_visual_observations',
        lambda _p: observations,
    )


def test_synthesis_skips_adjacents_when_all_cadastre_fmt_empty(tmp_path, monkeypatch):
    """Even with ≥2 visuals, if every cadastre adjacent_fmt is empty/whitespace
    the prompt must NOT include the adjacent rules block — prevents the LLM
    from inventing prose from nothing."""
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
    })

    # All four adjacent_*_fmt are empty — this is the edge case
    merged = {
        'building_type': {'value': '', 'source': ''},
        'architect_name': {'value': '', 'source': ''},
        'client_name': {'value': '', 'source': ''},
        'location_sentence': {'value': '', 'source': ''},
        'site_description': {'value': '', 'source': ''},
        'site_condition': {'value': '', 'source': ''},
        'is_anthropized': {'value': '', 'source': ''},
        'building_structure_desc': {'value': '', 'source': ''},
        'street_address': {'value': '', 'source': ''},
        'site_municipality': {'value': "Bell-Lloc d'Urgell", 'source': 'cadastre'},
        'adjacent_north': {'value': '', 'source': ''},
        'adjacent_south': {'value': '', 'source': ''},
        'adjacent_east': {'value': '', 'source': ''},
        'adjacent_west': {'value': '', 'source': ''},
        'adjacent_north_fmt': {'value': '', 'source': 'formatted from Cadastre'},
        'adjacent_south_fmt': {'value': '   ', 'source': 'formatted from Cadastre'},
        'adjacent_east_fmt': {'value': '', 'source': 'formatted from Cadastre'},
        'adjacent_west_fmt': {'value': '', 'source': 'formatted from Cadastre'},
    }
    wizard_service._synthesize_with_llm(merged, tmp_path)

    prompt_text = mock_client.messages.create.call_args.kwargs['messages'][0]['content']
    # Adjacent rules / sources block must NOT be in the prompt
    for cid in (
        'adjacent_north_fmt', 'adjacent_south_fmt',
        'adjacent_east_fmt', 'adjacent_west_fmt',
    ):
        assert cid not in prompt_text, (
            f"{cid} should not appear in prompt when all cadastre fmt values empty"
        )
