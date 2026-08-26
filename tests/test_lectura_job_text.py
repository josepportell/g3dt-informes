"""Fase 14a — la fila de la taula d'estat en el llenguatge de l'Eva (disseny §3.3).

Les regles de redacció del disseny són regles, no decoració, i per això es
proven: arrodonir a 5 min i mai «24 min 37 s», dir sempre «restants» i mai el
total, i que **«Interromput» no soni a error** (la cache per md5 fa que reprendre
costi només els documents que falten, i la taula ho ha de dir).
"""

from __future__ import annotations

from datetime import datetime

import pytest

from automation.lectura import job_text as JT

NOW = datetime(2026, 8, 26, 20, 0, 0)


def _job(state: str, **kw):
    base = {
        "project": "3001621 CASTELLAR",
        "state": state,
        "step": {"index": kw.pop("step", 0), "total": 4},
        "docs": {"done": kw.pop("done", 0), "total": kw.pop("total", 0)},
        "estimate_s": {"remaining": kw.pop("remaining", None), "basis": "test"},
    }
    base.update(kw)
    return base


# ---------------------------------------------------------------------------
# Regles de redacció
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(("seconds", "text"), [
    (None, None), (-1, None), (0, "< 1 min"), (59, "< 1 min"),
    (60, "≈ 1 min"), (140, "≈ 2 min"), (480, "≈ 8 min"), (599, "≈ 10 min"),
    (1477, "≈ 25 min"), (1500, "≈ 25 min"),
    (3600, "≈ 1 h"), (5400, "≈ 1 h 30 min"),
])
def test_estimates_never_show_seconds_and_stop_jittering_above_ten_minutes(seconds, text):
    assert JT._round_estimate(seconds) == text


def test_an_estimate_never_shows_seconds():
    row = JT.row(_job("reading", step=2, done=7, total=17, remaining=1477), now=NOW)
    assert row["estimacio"] == "≈ 25 min"
    assert "37" not in (row["detall"] or "")


def test_the_estimate_is_always_time_remaining_never_total():
    row = JT.row(_job("reading", step=2, done=7, total=17, remaining=1477), now=NOW)
    assert row["detall"] == "≈ 25 min restants"


@pytest.mark.parametrize(("iso", "text"), [
    ("2026-08-26T18:32:00", "avui 18:32"),
    ("2026-08-25T18:32:00", "ahir 18:32"),
    ("2026-08-12T09:05:00", "12/08 09:05"),
    ("no és una data", None),
    (None, None),
])
def test_timestamps_are_human_not_iso(iso, text):
    assert JT._when(iso, NOW) == text


# ---------------------------------------------------------------------------
# Una fila per estat (§3.3)
# ---------------------------------------------------------------------------

def test_reading_row_leads_with_the_counter():
    row = JT.row(_job("reading", step=2, done=7, total=17, remaining=1477), now=NOW)
    assert row["pas"] == "2/4"
    assert row["titol"] == "Llegint documents"
    assert row["comptador"] == "7/17"
    assert row["viu"] is True
    assert row["accio"] == "attach"


def test_ready_row_says_when_and_offers_enllestir():
    row = JT.row(_job("ready", step=4, done=13, total=13, finished_at="2026-08-25T18:32:00"), now=NOW)
    assert row["pas"] == "✓"
    assert row["titol"] == "Preparat (ahir 18:32)"
    assert row["preparat_el"] == "ahir 18:32"
    assert (row["accio"], row["accio_text"]) == ("enllestir", "Enllestir")
    assert row["viu"] is False


def test_interrupted_is_not_an_error():
    """§3.3, literal: «Interromput» NO és un error."""
    row = JT.row(_job("interrupted", step=2, done=12, total=17), now=NOW)
    assert row["pas"] == "⚠"
    assert row["titol"] == "Interromput a 2/4 (12/17 llegits)"
    assert "no es tornen a llegir" in row["detall"]
    assert (row["accio"], row["accio_text"]) == ("preparar", "Continuar")
    assert "error" not in row["titol"].lower()


def test_error_row_says_eficients_has_been_told():
    row = JT.row(_job("error", step=2, error="boom"), now=NOW)
    assert row["pas"] == "✗"
    assert row["titol"] == "No s'ha pogut preparar"
    assert row["detall"] == "avisat Eficients"
    assert row["accio"] == "error"


def test_cancelled_row_is_owned_by_eva():
    row = JT.row(_job("cancelled"), now=NOW)
    assert row["titol"] == "Aturat per tu"
    assert row["viu"] is False


@pytest.mark.parametrize(("state", "step", "titol"), [
    ("queued", 0, "En cua"),
    ("syncing", 1, "Copiant fitxers de la xarxa"),
    ("consolidating", 3, "Consolidant el que ha llegit"),
    ("merging", 4, "Preparant el formulari"),
])
def test_every_live_state_has_its_own_sentence(state, step, titol):
    row = JT.row(_job(state, step=step), now=NOW)
    assert row["titol"] == titol
    assert row["viu"] is True


def test_short_steps_show_under_a_minute_rather_than_nothing():
    assert JT.row(_job("syncing", step=1), now=NOW)["estimacio"] == "< 1 min"
    assert JT.row(_job("merging", step=4), now=NOW)["estimacio"] == "< 1 min"


# ---------------------------------------------------------------------------
# `network_delta` (el calcula la Fase 11; aquí només es redacta)
# ---------------------------------------------------------------------------

def test_ready_row_stays_silent_about_the_network_until_it_has_been_checked():
    """Millor no dir res que dir «res ha canviat» sense haver mirat."""
    assert JT.row(_job("ready", finished_at="2026-08-25T18:32:00"), now=NOW)["detall"] is None


def test_ready_row_quantifies_the_delta_when_there_is_one():
    row = JT.row(_job("ready", finished_at="2026-08-25T18:32:00",
                      network_delta={"new": 2, "changed": 0, "estimate_s": 480}), now=NOW)
    assert row["detall"] == "2 documents nous o canviats des de llavors → Enllestir ≈ 8 min"


def test_a_single_changed_document_is_singular():
    row = JT.row(_job("ready", finished_at="2026-08-25T18:32:00",
                      network_delta={"new": 0, "changed": 1}), now=NOW)
    assert row["detall"] == "1 document nou o canviat des de llavors"


def test_an_empty_delta_says_so():
    row = JT.row(_job("ready", finished_at="2026-08-25T18:32:00",
                      network_delta={"new": 0, "changed": 0}), now=NOW)
    assert row["detall"] == "res no ha canviat a la xarxa"


# ---------------------------------------------------------------------------
# Robustesa: una fila lletja abans que una taula que no es pinta
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("job", [
    {}, {"state": None}, {"state": "estat_inventat"},
    {"state": "reading", "step": "no és un dict", "docs": None, "estimate_s": None},
    {"state": "ready", "finished_at": 12345},
])
def test_a_malformed_job_still_produces_a_row(job):
    row = JT.row(job, now=NOW)
    assert set(row) >= {"pas", "titol", "accio", "viu"}


def test_rows_maps_over_a_list():
    out = JT.rows([_job("reading", step=2, done=1, total=3), _job("ready")], now=NOW)
    assert [r["viu"] for r in out] == [True, False]
