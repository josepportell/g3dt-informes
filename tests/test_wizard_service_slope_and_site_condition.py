"""Fixes B i D3 (2026-09-17) a `web/wizard_service.py`: el pendent desconegut ja no es força a 0,0, i es
resol l'ICGC quan hi ha UTM però encara no hi ha pendent (abans ningú el consultava un cop geocodificats els
adjacents). Vegeu `automation/narrative_criteria.py::site_condition_sentence` (Fix A) — el defecte de fons era
comú als dos fitxers.
"""

from __future__ import annotations

import pytest

from web import wizard_service


def test_fill_missing_slope_queries_icgc_when_utm_known(monkeypatch: pytest.MonkeyPatch):
    """B2: si no hi ha `slope_percent` però sí UTM, es consulta l'ICGC (mateix llindar 15,0 % que
    `auto_extractor._phase3_slope`) i s'omplen `slope_percent`/`slope_direction`/`is_sloped`."""
    calls = []

    def fake_get_slope(utm_x, utm_y, *a, **kw):
        calls.append((utm_x, utm_y))
        return 21.6, "N"

    monkeypatch.setattr("automation.icgc_geology.get_slope", fake_get_slope)

    merged = {
        "utm_x": {"value": 311000.5, "source": "geocode:adjacents_fallback"},
        "utm_y": {"value": 4604000.2, "source": "geocode:adjacents_fallback"},
    }
    wizard_service._fill_missing_slope(merged)

    assert calls == [(311000.5, 4604000.2)]
    assert merged["slope_percent"]["value"] == 21.6
    assert merged["slope_direction"]["value"] == "N"
    assert merged["is_sloped"]["value"] is True, "21,6 % > 15,0 %"


def test_fill_missing_slope_never_defaults_to_zero_on_failure(monkeypatch: pytest.MonkeyPatch):
    """El desconegut es queda desconegut: una crida ICGC fallida NO deixa `slope_percent=0`."""
    def fake_get_slope(*a, **kw):
        raise RuntimeError("xarxa caiguda")

    monkeypatch.setattr("automation.icgc_geology.get_slope", fake_get_slope)

    merged = {
        "utm_x": {"value": 311000.5, "source": "geocode:adjacents_fallback"},
        "utm_y": {"value": 4604000.2, "source": "geocode:adjacents_fallback"},
    }
    wizard_service._fill_missing_slope(merged)

    assert "slope_percent" not in merged
    assert "is_sloped" not in merged


def test_fill_missing_slope_skips_without_utm():
    """Sense UTM, no s'intenta res (evita una crida ICGC inútil amb coordenades absents)."""
    merged: dict = {}
    wizard_service._fill_missing_slope(merged)
    assert "slope_percent" not in merged


def test_fill_missing_slope_skips_when_slope_already_known(monkeypatch: pytest.MonkeyPatch):
    """Un `slope_percent` ja conegut (fins i tot 0,0 explícit) no es recalcula."""
    called = []
    monkeypatch.setattr("automation.icgc_geology.get_slope", lambda *a, **kw: called.append(1) or (99.0, "N"))

    merged = {
        "slope_percent": {"value": 0.0, "source": "ICGC MDT 2m"},
        "utm_x": {"value": 1.0, "source": "x"},
        "utm_y": {"value": 2.0, "source": "y"},
    }
    wizard_service._fill_missing_slope(merged)
    assert not called
    assert merged["slope_percent"]["value"] == 0.0


def test_site_condition_prefill_unknown_slope_is_not_forced_to_zero():
    """Fix B1: sense `slope_percent` a `merged`, la font NO diu «slope 0%» (era el bug: forçava el pendent
    a 0,0 i el `source` mentia dient que ho sabia)."""
    merged: dict = {"site_description": {"value": "text ja fixat", "source": "user"}}
    wizard_service._generate_template_prefills_from_merged(merged)
    assert "site_condition" in merged
    assert "0%" not in merged["site_condition"]["source"], merged["site_condition"]["source"]
    assert "desconegut" in merged["site_condition"]["source"]


def test_site_condition_prefill_explicit_zero_slope_still_says_zero():
    """Un 0,0 llegit de debò (ICGC) sí ha de dir «slope 0%» — no es toca el comportament conegut."""
    merged: dict = {
        "site_description": {"value": "text ja fixat", "source": "user"},
        "slope_percent": {"value": 0.0, "source": "ICGC MDT 2m"},
    }
    wizard_service._generate_template_prefills_from_merged(merged)
    assert "slope 0%" in merged["site_condition"]["source"]


def test_include_flags_marked_revisar_when_slope_unknown():
    """D3: pendent desconegut → `include_earth_pressure`/`include_slope_stability` arriben marcats «revisar»
    perquè l'Eva decideixi (abans el sistema ho decidia sol i en silenci)."""
    merged: dict = {"site_description": {"value": "text ja fixat", "source": "user"}}
    wizard_service._generate_template_prefills_from_merged(merged)
    assert merged["include_earth_pressure"]["source"] == "revisar"
    assert merged["include_slope_stability"]["source"] == "revisar"


def test_include_flags_proposed_but_still_revisar_when_slope_known_and_flat():
    """D4 (2026-09-17): amb xarxa disponible el pendent es resol sol i ABANS el marcador «revisar» no
    s'activava mai — el tester ho ha verificat. Josep: el pendent MITJÀ de l'ICGC no decideix aquestes
    seccions (ho decideix el pendent a la fonamentació, judici de la visita); el sistema PROPOSA (aquí:
    pla → no calen) però sempre deixa el camp per revisar, amb la raó a `note`."""
    merged: dict = {
        "site_description": {"value": "text ja fixat", "source": "user"},
        "slope_percent": {"value": 3.0, "source": "ICGC MDT 2m"},
    }
    wizard_service._generate_template_prefills_from_merged(merged)
    assert merged["include_earth_pressure"]["source"] == "revisar"
    assert merged["include_slope_stability"]["source"] == "revisar"
    assert merged["include_earth_pressure"]["value"] is False
    assert merged["include_slope_stability"]["value"] is False
    assert "3,0%" in merged["include_earth_pressure"]["note"]
    assert "ICGC MDT 2m" in merged["include_earth_pressure"]["note"]


def test_include_flags_proposed_true_when_slope_known_and_steep():
    """Pendent conegut per sobre del llindar (15,0%, mateix que `_fill_missing_slope`) → proposta True, amb
    la font i el valor del pendent a `note` (Rubí: 21,6% de l'ICGC però pla a la zona de treball — la
    proposta és només un punt de partida, mai la decisió final)."""
    merged: dict = {
        "site_description": {"value": "text ja fixat", "source": "user"},
        "slope_percent": {"value": 21.6, "source": "ICGC MDT (post-geocode adjacents)"},
        "slope_direction": {"value": "W", "source": "ICGC MDT (post-geocode adjacents)"},
    }
    wizard_service._generate_template_prefills_from_merged(merged)
    assert merged["include_earth_pressure"]["value"] is True
    assert merged["include_slope_stability"]["value"] is True
    assert merged["include_earth_pressure"]["source"] == "revisar"
    assert merged["include_slope_stability"]["source"] == "revisar"
    assert "21,6%" in merged["include_earth_pressure"]["note"]
    assert "cap a W" in merged["include_earth_pressure"]["note"]
    assert "4.4 Empentes de terres" in merged["include_earth_pressure"]["note"]
    assert "4.5 Estabilitat de vessant" in merged["include_slope_stability"]["note"]


def test_include_flags_respect_user_edit():
    """Un cop hi hagi UI (fora d'abast d'aquesta tanda), la tria de l'Eva (`source='user'`) ha de guanyar
    sempre — el backend no li ha de trepitjar la decisió amb una proposta nova."""
    merged: dict = {
        "site_description": {"value": "text ja fixat", "source": "user"},
        "slope_percent": {"value": 21.6, "source": "ICGC MDT 2m"},
        "include_earth_pressure": {"value": False, "source": "user"},
        "include_slope_stability": {"value": False, "source": "user"},
    }
    wizard_service._generate_template_prefills_from_merged(merged)
    assert merged["include_earth_pressure"] == {"value": False, "source": "user"}
    assert merged["include_slope_stability"] == {"value": False, "source": "user"}
