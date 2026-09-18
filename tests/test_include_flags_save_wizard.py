"""Punt 4 (2026-09-17): la tria de l'Eva sobre `include_earth_pressure`/`include_slope_stability` s'ha de
desar de debò a `user_data.json` amb `_sources[...] == 'user'` — i, mentre no hi toqui, la proposta
(`source == 'revisar'`) persisteix sense promoure's mai sola a 'user'.

Mateix patró de fixture que `tests/test_save_wizard_changed_fields_log.py`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from web import wizard_service

    ref_dir = tmp_path / "projectes"
    p = ref_dir / "3001621 CASTELLAR"
    (p / "validation" / "lectura").mkdir(parents=True)
    (p / "PENETROS.pdf").write_bytes(b"%PDF-1.4 penetros")
    monkeypatch.setattr(wizard_service, "_REF_DIR", ref_dir)
    return p


def test_untouched_proposal_never_self_promotes_to_user(project: Path, monkeypatch: pytest.MonkeyPatch):
    """L'Eva reenvia el formulari (autosave d'un altre camp) sense tocar els toggles: el valor que arriba
    és EXACTAMENT el que proposava el sistema (`True`, pendent 21,6 %) — no ha de quedar marcat 'user'."""
    from web import wizard_service
    from web.wizard_service import save_wizard

    monkeypatch.setitem(
        wizard_service._prefill_cache,
        "3001621 CASTELLAR",
        {
            "include_earth_pressure": {"value": True, "source": "revisar", "note": "Pendent mitjà: 21,6%."},
            "include_slope_stability": {"value": True, "source": "revisar", "note": "Pendent mitjà: 21,6%."},
        },
    )

    save_wizard("3001621 CASTELLAR", {
        "include_earth_pressure": True,
        "include_slope_stability": True,
    })

    user_data = json.loads((project / "user_data.json").read_text(encoding="utf-8"))
    assert user_data["include_earth_pressure"] is True
    assert user_data["_sources"]["include_earth_pressure"] == "revisar"
    assert user_data["_sources"]["include_slope_stability"] == "revisar"


def test_eva_flips_the_toggle_marks_user(project: Path, monkeypatch: pytest.MonkeyPatch):
    """L'Eva ha vist «21,6% → inclouria 4.4/4.5» i ha decidit que NO calen (cas Rubí): envia `False` on el
    sistema proposava `True` — ha de quedar `_sources == 'user'`."""
    from web import wizard_service
    from web.wizard_service import save_wizard

    monkeypatch.setitem(
        wizard_service._prefill_cache,
        "3001621 CASTELLAR",
        {
            "include_earth_pressure": {"value": True, "source": "revisar", "note": "Pendent mitjà: 21,6%."},
            "include_slope_stability": {"value": True, "source": "revisar", "note": "Pendent mitjà: 21,6%."},
        },
    )

    save_wizard("3001621 CASTELLAR", {
        "include_earth_pressure": False,
        "include_slope_stability": False,
    })

    user_data = json.loads((project / "user_data.json").read_text(encoding="utf-8"))
    assert user_data["include_earth_pressure"] is False
    assert user_data["include_slope_stability"] is False
    assert user_data["_sources"]["include_earth_pressure"] == "user"
    assert user_data["_sources"]["include_slope_stability"] == "user"


def test_eva_decision_survives_a_later_autosave_without_cache(project: Path, monkeypatch: pytest.MonkeyPatch):
    """Un cop l'Eva ha decidit (desat 1), un autosave posterior sense cache (bloc B, mateix bug real
    d'Alcoletge) no li ha de trepitjar la decisió cap a 'revisar'."""
    from web import wizard_service
    from web.wizard_service import save_wizard

    monkeypatch.setitem(
        wizard_service._prefill_cache,
        "3001621 CASTELLAR",
        {"include_earth_pressure": {"value": True, "source": "revisar", "note": "n"}},
    )
    save_wizard("3001621 CASTELLAR", {"include_earth_pressure": False})

    monkeypatch.delitem(wizard_service._prefill_cache, "3001621 CASTELLAR", raising=False)
    save_wizard("3001621 CASTELLAR", {"include_earth_pressure": False})

    user_data = json.loads((project / "user_data.json").read_text(encoding="utf-8"))
    assert user_data["_sources"]["include_earth_pressure"] == "user"


def test_eva_confirms_the_same_value_still_marks_user_via_forced_fields(
    project: Path, monkeypatch: pytest.MonkeyPatch
):
    """L'Eva clica el toggle i acaba confirmant EL MATEIX valor que proposava el sistema (`True`):
    `_is_changed` per valor NO ho detectaria com a canvi — sense `forced_user_fields` es perdria la
    seva decisió i, sense font 'user', `build_report_data` cauria al càlcul derivat (murs/soterrani
    per `include_earth_pressure`, que pot no coincidir amb la proposta del pendent)."""
    from web import wizard_service
    from web.wizard_service import save_wizard

    monkeypatch.setitem(
        wizard_service._prefill_cache,
        "3001621 CASTELLAR",
        {"include_earth_pressure": {"value": True, "source": "revisar", "note": "n"}},
    )

    save_wizard(
        "3001621 CASTELLAR",
        {"include_earth_pressure": True},
        forced_user_fields=["include_earth_pressure"],
    )

    user_data = json.loads((project / "user_data.json").read_text(encoding="utf-8"))
    assert user_data["include_earth_pressure"] is True
    assert user_data["_sources"]["include_earth_pressure"] == "user"


def test_forced_user_fields_ignores_names_outside_allowlist(project: Path, monkeypatch: pytest.MonkeyPatch):
    """Revisió 2026-09-18: el servidor no s'ha de refiar cegament de qualsevol nom que arribi a
    `forced_user_fields` — només `_FORCEABLE_USER_FIELDS` hi pot entrar. Un client (mal escrit o
    futur) que hi enviï `building_structure_desc` (un camp de prosa SENSE botó «D'acord», fora de
    l'allowlist) NO l'ha de poder marcar 'user' sense que l'Eva l'hagi tocat de debò -- trencaria
    la precedència Eva > lector."""
    from web import wizard_service
    from web.wizard_service import save_wizard

    monkeypatch.setitem(
        wizard_service._prefill_cache,
        "3001621 CASTELLAR",
        {"building_structure_desc": {"value": "estructura de formigó armat", "source": "revisar", "note": "n"}},
    )

    save_wizard(
        "3001621 CASTELLAR",
        {"building_structure_desc": "estructura de formigó armat"},  # mateix valor: sense canvi de valor
        forced_user_fields=["building_structure_desc"],
    )

    user_data = json.loads((project / "user_data.json").read_text(encoding="utf-8"))
    assert user_data["_sources"]["building_structure_desc"] == "revisar", (
        "un nom fora de l'allowlist no pot forçar 'user'"
    )


def test_eva_confirms_site_condition_without_editing_marks_user(
    project: Path, monkeypatch: pytest.MonkeyPatch
):
    """El forat que tanca aquesta feina (2026-09-18): l'Eva llegeix la frase de `site_condition`
    proposada pel sistema, hi està d'acord i prem el botó «D'acord» del wizard SENSE canviar-ne
    el text -- `confirmProposalField('site_condition')` envia `forced_user_fields=['site_condition']`
    amb el MATEIX valor. `site_condition` és ara a `_FORCEABLE_USER_FIELDS`: ha de quedar
    `source == 'user'`, igual que els toggles 4.4/4.5."""
    from web import wizard_service
    from web.wizard_service import save_wizard

    monkeypatch.setitem(
        wizard_service._prefill_cache,
        "3001621 CASTELLAR",
        {"site_condition": {"value": "El terreny es mostra pla.", "source": "revisar", "note": "n"}},
    )

    save_wizard(
        "3001621 CASTELLAR",
        {"site_condition": "El terreny es mostra pla."},  # mateix valor que la proposta: sense canvi de valor
        forced_user_fields=["site_condition"],
    )

    user_data = json.loads((project / "user_data.json").read_text(encoding="utf-8"))
    assert user_data["site_condition"] == "El terreny es mostra pla."
    assert user_data["_sources"]["site_condition"] == "user"
