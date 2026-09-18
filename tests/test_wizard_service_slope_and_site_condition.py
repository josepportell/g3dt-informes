"""Fixes B i D3 (2026-09-17) a `web/wizard_service.py`: el pendent desconegut ja no es força a 0,0, i es
resol l'ICGC quan hi ha UTM però encara no hi ha pendent (abans ningú el consultava un cop geocodificats els
adjacents). Vegeu `automation/narrative_criteria.py::site_condition_sentence` (Fix A) — el defecte de fons era
comú als dos fitxers.
"""

from __future__ import annotations

import json
from pathlib import Path

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
    """Fix B1: sense `slope_percent` a `merged`, la raó (ara a `note`, 2026-09-17 — «el sistema proposa, no
    decideix») NO diu «0%» (era el bug: forçava el pendent a 0,0 i mentia dient que ho sabia)."""
    merged: dict = {"site_description": {"value": "text ja fixat", "source": "user"}}
    wizard_service._generate_template_prefills_from_merged(merged)
    assert "site_condition" in merged
    assert merged["site_condition"]["source"] == "revisar"
    assert "0%" not in merged["site_condition"]["note"], merged["site_condition"]["note"]
    assert "desconegut" in merged["site_condition"]["note"]


def test_site_condition_prefill_explicit_zero_slope_still_says_zero():
    """Un 0,0 llegit de debò (ICGC) sí ha de dir «0%» a `note` — no es toca el comportament conegut, només
    on es guarda la raó (2026-09-17: `source='revisar'` + `note`, no codificat dins el `source`)."""
    merged: dict = {
        "site_description": {"value": "text ja fixat", "source": "user"},
        "slope_percent": {"value": 0.0, "source": "ICGC MDT 2m"},
    }
    wizard_service._generate_template_prefills_from_merged(merged)
    assert merged["site_condition"]["source"] == "revisar"
    assert "0,0%" in merged["site_condition"]["note"]


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


# --- Revisió 2026-09-18: la `note` de `site_condition` desapareixia després del primer autosave ---
#
# `_load_existing_user_data()` (`automation/wizard.py`) NOMÉS persisteix `value`/`source`, mai `note`.
# La guarda antiga (`if not _get_val('site_condition')`) confonia «el camp té valor» amb «l'Eva ho ha
# decidit» — a partir del segon autosave el recàlcul se saltava i la nota (la raó que l'Eva ha de
# llegir) es perdia en silenci, encara que `source` seguís sent 'revisar'.

@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    ref_dir = tmp_path / "projectes"
    p = ref_dir / "3001621 CASTELLAR"
    p.mkdir(parents=True)
    monkeypatch.setattr(wizard_service, "_REF_DIR", ref_dir)
    return p


def test_site_condition_note_survives_second_prefill_pass_after_autosave(
    project: Path, monkeypatch: pytest.MonkeyPatch
):
    """Dues passades de prefills amb un `user_data.json` desat entremig: la `note` ha de seguir
    sent-hi a la segona passada. Reprodueix la cadena real: 1a crida (calcula i proposa) -> autosave
    (persisteix value+source, SENSE note) -> 2a crida (havia de recalcular i no ho feia)."""
    from web.wizard_service import save_wizard
    from automation.wizard import UserDataWizard

    project_name = project.name

    # 1a passada: es calcula la proposta (com faria `_merge_prefills` la primera vegada).
    merged1: dict = {
        "site_description": {"value": "text ja fixat", "source": "user"},
        "slope_percent": {"value": 21.6, "source": "ICGC MDT 2m"},
    }
    wizard_service._generate_template_prefills_from_merged(merged1)
    assert "note" in merged1["site_condition"], "la 1a passada ha de generar la nota"

    # Autosave: un altre camp del formulari es toca (site_condition arriba igual, com fa
    # `collectWizardFields()` sempre). La cache de prefills reflecteix el que ha vist l'Eva.
    monkeypatch.setitem(
        wizard_service._prefill_cache,
        project_name,
        {"site_condition": merged1["site_condition"], "slope_percent": merged1["slope_percent"]},
    )
    save_wizard(project_name, {"site_condition": merged1["site_condition"]["value"]})

    user_data = json.loads((project / "user_data.json").read_text(encoding="utf-8"))
    assert user_data["_sources"]["site_condition"] == "revisar", "no l'ha tocat l'Eva: no promou a 'user'"

    # 2a passada: es recarrega el projecte (com faria `UserDataWizard.load_prefills()` a la
    # següent obertura o al següent autosave). El prefill reconstruït NO té 'note' (mai es
    # persisteix) — és exactament el bug reproduït.
    wizard = UserDataWizard(str(project))
    wizard.load_prefills()
    assert "note" not in wizard.prefills["site_condition"], (
        "`_load_existing_user_data` mai persisteix 'note' — si aquesta assumpció canvia, cal repensar el fix"
    )

    merged2: dict = {"slope_percent": merged1["slope_percent"]}
    merged2.update(wizard.prefills)
    wizard_service._generate_template_prefills_from_merged(merged2)

    assert "note" in merged2["site_condition"], "la nota ha de reaparèixer a la 2a passada"
    assert "21,6%" in merged2["site_condition"]["note"]
    assert merged2["site_condition"]["source"] == "revisar"


def test_site_condition_recomputes_when_slope_becomes_known_later():
    """Si el pendent es resol més endavant (p. ex. una consulta ICGC que abans havia fallat), la frase
    proposada s'ha d'actualitzar — no quedar-se amb la vella («desconegut») presentada com a vigent."""
    merged: dict = {
        "site_description": {"value": "text ja fixat", "source": "user"},
    }
    wizard_service._generate_template_prefills_from_merged(merged)
    assert "desconegut" in merged["site_condition"]["note"]

    # El pendent es resol (nova crida ICGC, mateix `merged` que continua sense decisió de l'Eva).
    merged["slope_percent"] = {"value": 33.0, "source": "ICGC MDT 2m"}
    wizard_service._generate_template_prefills_from_merged(merged)
    assert "desconegut" not in merged["site_condition"]["note"]
    assert "33,0%" in merged["site_condition"]["note"]


def test_site_condition_user_edit_is_never_recomputed():
    """Una frase escrita per l'Eva (`source == 'user'`) no es toca mai, encara que el pendent canviï."""
    merged: dict = {
        "site_description": {"value": "text ja fixat", "source": "user"},
        "slope_percent": {"value": 21.6, "source": "ICGC MDT 2m"},
        "site_condition": {"value": "Text escrit per l'Eva a mà.", "source": "user"},
    }
    wizard_service._generate_template_prefills_from_merged(merged)
    assert merged["site_condition"] == {"value": "Text escrit per l'Eva a mà.", "source": "user"}


def test_include_flags_independent_when_only_one_decided_by_user():
    """Cas típic (revisió 2026-09-18): l'Eva decideix «no calen empentes» i deixa «estabilitat de
    vessant» sense tocar. El segon camp ha de seguir-se recalculant amb `note`, no quedar-se congelat
    a 'revisar' sense raó — la guarda antiga era tot-o-res i el saltava sencer."""
    merged: dict = {
        "site_description": {"value": "text ja fixat", "source": "user"},
        "slope_percent": {"value": 21.6, "source": "ICGC MDT 2m"},
        "include_earth_pressure": {"value": False, "source": "user"},
    }
    wizard_service._generate_template_prefills_from_merged(merged)
    assert merged["include_earth_pressure"] == {"value": False, "source": "user"}
    assert merged["include_slope_stability"]["source"] == "revisar"
    assert "note" in merged["include_slope_stability"]
    assert "21,6%" in merged["include_slope_stability"]["note"]
