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


def test_a_second_save_of_the_same_values_logs_zero_changes(project: Path, caplog: pytest.LogCaptureFixture):
    from web import wizard_service
    from web.wizard_service import save_wizard

    caplog.set_level(logging.INFO, logger="web.wizard_service")

    save_wizard("3001621 CASTELLAR", {"client_name": "Fontanet SL"})
    caplog.clear()

    # Simula que la UI ha tornat a demanar els prefills entremig (com faria
    # una recàrrega real) i ara el badge d'aquest camp ja diu 'user' amb el
    # mateix valor que s'acaba de desar: el segon desat no canvia res.
    wizard_service._prefill_cache["3001621 CASTELLAR"] = {
        "client_name": {"value": "Fontanet SL", "source": "user"},
    }

    save_wizard("3001621 CASTELLAR", {"client_name": "Fontanet SL"})

    line = _log_line(caplog)
    assert "0 camps canviats per l'Eva: cap" in line


def test_an_empty_save_logs_zero_and_no_field_names(project: Path, caplog: pytest.LogCaptureFixture):
    from web.wizard_service import save_wizard

    caplog.set_level(logging.INFO, logger="web.wizard_service")

    save_wizard("3001621 CASTELLAR", {})

    line = _log_line(caplog)
    assert line.endswith("0 camps canviats per l'Eva: cap")
