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
