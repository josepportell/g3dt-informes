"""Bloc G (`docs/PLA-UX-WIZARD-2026-09.md`) — el desat registra al log quins
camps ha canviat l'Eva.

`save_wizard` ja calcula `_is_changed` per pintar els badges de font; aquí
NOMÉS s'hi afegeix una línia INFO amb els NOMS dels camps canviats EN AQUEST
desat (mai valors — res de dades personals al log). L'objectiu (Josep,
2026-09-14): amb 3-4 projectes reals via A saber què no toca mai Eva.

Mateix patró de fixture que `tests/test_wizard_service_lectura_freeze_and_cache.py`
(`project`, `wizard_service._REF_DIR` apuntant a `tmp_path`).
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Projecte mínim resoluble per nom (`wizard_service._REF_DIR`)."""
    from web import wizard_service

    ref_dir = tmp_path / "projectes"
    p = ref_dir / "3001621 CASTELLAR"
    (p / "validation" / "lectura").mkdir(parents=True)
    (p / "PENETROS.pdf").write_bytes(b"%PDF-1.4 penetros")
    monkeypatch.setattr(wizard_service, "_REF_DIR", ref_dir)
    return p


def _log_line(caplog: pytest.LogCaptureFixture) -> str:
    for record in caplog.records:
        if record.getMessage().startswith("wizard desat "):
            return record.getMessage()
    raise AssertionError("cap línia 'wizard desat ...' al log")


def test_a_save_with_two_changed_fields_logs_them_by_name(project: Path, caplog: pytest.LogCaptureFixture):
    from web.wizard_service import save_wizard

    caplog.set_level(logging.INFO, logger="web.wizard_service")

    save_wizard("3001621 CASTELLAR", {"client_name": "Fontanet SL", "architect_name": "X. Mateu"})

    line = _log_line(caplog)
    assert "2 camps canviats per l'Eva" in line
    assert "client_name" in line
    assert "architect_name" in line
    # Mai valors: les dades que Eva ha escrit no viatgen al log.
    assert "Fontanet SL" not in line
    assert "X. Mateu" not in line


def test_a_three_consecutive_autosaves_never_repeat_an_already_user_field(
    project: Path, caplog: pytest.LogCaptureFixture
):
    """Bug real reproduit pel reviewer (2026-09-15): `_prefill_cache` es buida
    a cada desat (`_prefill_cache.pop`) i res la reomple entre autosaves --
    calcular `_already_user` des d'ella feia que el 2n i 3r desat tornessin a
    llistar `client_name` com si l'Eva l'hagués tocat ARA, quan ja era seu des
    del 1r desat. Cap dels tres desats toca `_prefill_cache` manualment: aixo
    simularia una recarrega de pagina que a la practica no passa entre
    autosaves.
    """
    from web.wizard_service import save_wizard

    caplog.set_level(logging.INFO, logger="web.wizard_service")

    # Desat 1: Eva escriu client_name -> 1 camp canviat.
    save_wizard("3001621 CASTELLAR", {"client_name": "Fontanet SL"})
    line1 = _log_line(caplog)
    assert "1 camps canviats per l'Eva: client_name" in line1
    caplog.clear()

    # Desat 2: Eva escriu architect_name, client_name es manté igual -> NOMÉS
    # architect_name (client_name ja era seu, no s'ha de tornar a comptar).
    save_wizard(
        "3001621 CASTELLAR",
        {"client_name": "Fontanet SL", "architect_name": "X. Mateu"},
    )
    line2 = _log_line(caplog)
    assert "1 camps canviats per l'Eva: architect_name" in line2
    assert "client_name" not in line2
    caplog.clear()

    # Desat 3: res canvia -> 0 camps.
    save_wizard(
        "3001621 CASTELLAR",
        {"client_name": "Fontanet SL", "architect_name": "X. Mateu"},
    )
    line3 = _log_line(caplog)
    assert "0 camps canviats per l'Eva: cap" in line3


def test_an_empty_save_logs_zero_and_no_field_names(project: Path, caplog: pytest.LogCaptureFixture):
    from web.wizard_service import save_wizard

    caplog.set_level(logging.INFO, logger="web.wizard_service")

    save_wizard("3001621 CASTELLAR", {})

    line = _log_line(caplog)
    assert line.endswith("0 camps canviats per l'Eva: cap")


def test_b_autosave_without_cache_does_not_re_flag_untouched_fields(
    project: Path, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
):
    """Bug real (Alcoletge, 2026-09-16): amb la cache buida (el desat
    automàtic del botó "Generar informe", sense recàrrega de pàgina), TOT
    camp no buit del formulari es marcava 'user' encara que Eva no l'hagués
    tocat. Aquí es reprodueix amb un prefill (cache) previ i un segon desat
    IDÈNTIC sense cache: el log ha de dir 0 i `_sources` no pot promoure cap
    camp intocat a 'user'.
    """
    from web import wizard_service
    from web.wizard_service import save_wizard

    caplog.set_level(logging.INFO, logger="web.wizard_service")

    monkeypatch.setitem(
        wizard_service._prefill_cache,
        "3001621 CASTELLAR",
        {
            "client_name": {"value": "Promotors del Segrià SL", "source": "plànol A.01.pdf"},
            "num_floors": {"value": None, "source": "defecte"},
            "geomech_cohesion": {"value": 0.0, "source": "soil_type=granular"},
            "geomech_gamma": {"value": 2.0, "source": "CTE D.27 (granular)"},
            "soil_type_level_1": {"value": "granular", "source": "lectura sondeig.pdf"},
            "soil_type_level_2": {"value": "granular", "source": "lectura sondeig.pdf"},
        },
    )

    # Desat 1: Eva NOMÉS escriu num_floors i building_height_m (2 camps nous);
    # la resta és el que ja hi havia al formulari (prefills o derivats).
    save_wizard(
        "3001621 CASTELLAR",
        {
            "client_name": "Promotors del Segrià SL",
            "num_floors": "Pb + 1Pp",
            "building_height_m": "6.5",
            "soil_types": ["granular", "granular"],
        },
        expert_overrides={"geomech_params": {"cohesion": 0.0, "gamma": 2.0}},
    )
    line1 = _log_line(caplog)
    assert "2 camps canviats per l'Eva" in line1
    assert "num_floors" in line1
    assert "building_height_m" in line1
    assert "client_name" not in line1
    assert "geomech_cohesion" not in line1
    assert "geomech_gamma" not in line1
    assert "soil_types" not in line1
    caplog.clear()

    # Desat 2 (autosave del botó "Generar informe"): mateix payload, SENSE
    # tornar a omplir `_prefill_cache` (es va buidar en acabar el desat 1).
    monkeypatch.delitem(wizard_service._prefill_cache, "3001621 CASTELLAR", raising=False)
    save_wizard(
        "3001621 CASTELLAR",
        {
            "client_name": "Promotors del Segrià SL",
            "num_floors": "Pb + 1Pp",
            "building_height_m": "6.5",
            "soil_types": ["granular", "granular"],
        },
        expert_overrides={"geomech_params": {"cohesion": 0.0, "gamma": 2.0}},
    )
    line2 = _log_line(caplog)
    assert "0 camps canviats per l'Eva: cap" in line2

    import json
    user_data = json.loads((project / "user_data.json").read_text(encoding="utf-8"))
    sources = user_data["_sources"]
    # Els dos camps que l'Eva SÍ ha escrit al desat 1 continuen 'user'.
    assert sources["num_floors"] == "user"
    assert sources["building_height_m"] == "user"
    # Cap dels que no ha tocat MAI s'ha promogut a 'user'.
    assert sources.get("client_name") != "user"
    assert sources.get("geomech_cohesion") != "user"
    assert sources.get("geomech_gamma") != "user"
    assert sources.get("soil_types") != "user"


def test_c_sources_survive_an_autosave_without_cache(
    project: Path, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
):
    """Les fonts reals (lectura, ICGC/Cadastre...) no es perden ni es
    reescriuen a 'user' quan la cache és buida i la base cau al
    `user_data.json` anterior."""
    from web import wizard_service
    from web.wizard_service import save_wizard

    caplog.set_level(logging.INFO, logger="web.wizard_service")

    monkeypatch.setitem(
        wizard_service._prefill_cache,
        "3001621 CASTELLAR",
        {"site_municipality": {"value": "Alcoletge", "source": "ICGC / Cadastre"}},
    )
    save_wizard("3001621 CASTELLAR", {"site_municipality": "Alcoletge"})
    caplog.clear()

    monkeypatch.delitem(wizard_service._prefill_cache, "3001621 CASTELLAR", raising=False)
    save_wizard("3001621 CASTELLAR", {"site_municipality": "Alcoletge"})

    import json
    user_data = json.loads((project / "user_data.json").read_text(encoding="utf-8"))
    assert user_data["_sources"]["site_municipality"] == "ICGC / Cadastre"


def test_d_normalized_comparison_ignores_format_only_differences(
    project: Path, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
):
    """Valors REALS (no buits) als dos costats que només difereixen en
    format: `0.0` (float) vs `"0"` (string), i una llista amb el mateix
    contingut pero amb espais extra. Amb la comparació ingènua `str(a) !=
    str(b)` d'abans (`str(0.0)` = `"0.0"` != `"0"`; la llista amb espais dona
    una altra cadena) totes dues es marcarien com a canvi — aquest test
    exigeix `_values_equal`, no la regla D (que només actua amb un valor buit
    al formulari; vegeu `test_f_blank_form_value_never_promotes...`)."""
    from web import wizard_service
    from web.wizard_service import save_wizard

    caplog.set_level(logging.INFO, logger="web.wizard_service")

    monkeypatch.setitem(
        wizard_service._prefill_cache,
        "3001621 CASTELLAR",
        {
            "superficie_parcela_m2": {"value": 0.0, "source": "cadastre"},
            "adjacent_north": {"value": ["Carrer Major, 3"], "source": "lectura"},
        },
    )

    save_wizard(
        "3001621 CASTELLAR",
        {
            "superficie_parcela_m2": "0",
            "adjacent_north": [" Carrer Major, 3 "],
        },
    )

    line = _log_line(caplog)
    assert "0 camps canviats per l'Eva: cap" in line


def test_f_blank_form_value_never_promotes_even_when_base_has_a_value(
    project: Path, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
):
    """Regla D (no `_values_equal`): un prefill amb valor real (`2.0`) i un
    desat amb `None` no és un canvi de l'Eva — és el formulari reenviant un
    camp que no ha tocat. Aquest cas es talla ABANS de `_values_equal` (per
    això viu en un test separat de `test_d`, que exerceix la normalització)."""
    from web import wizard_service
    from web.wizard_service import save_wizard

    caplog.set_level(logging.INFO, logger="web.wizard_service")

    monkeypatch.setitem(
        wizard_service._prefill_cache,
        "3001621 CASTELLAR",
        {"num_floors": {"value": 2.0, "source": "planol"}},
    )

    save_wizard("3001621 CASTELLAR", {"num_floors": None})

    line = _log_line(caplog)
    assert "0 camps canviats per l'Eva: cap" in line

    import json
    user_data = json.loads((project / "user_data.json").read_text(encoding="utf-8"))
    assert user_data.get("_sources", {}).get("num_floors") != "user"


def test_e_a_real_change_still_counts_and_marks_user(
    project: Path, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
):
    from web import wizard_service
    from web.wizard_service import save_wizard

    caplog.set_level(logging.INFO, logger="web.wizard_service")

    monkeypatch.setitem(
        wizard_service._prefill_cache,
        "3001621 CASTELLAR",
        {"num_floors": {"value": 2.0, "source": "planol"}},
    )

    save_wizard("3001621 CASTELLAR", {"num_floors": "3"})

    line = _log_line(caplog)
    assert "1 camps canviats per l'Eva: num_floors" in line

    import json
    user_data = json.loads((project / "user_data.json").read_text(encoding="utf-8"))
    assert user_data["_sources"]["num_floors"] == "user"
