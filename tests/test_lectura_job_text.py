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


def test_reading_row_with_no_telemetry_basis_shows_no_fake_time():
    """2026-09-17 (mesura Rubí): abans que `Job._recompute_estimate()` s'hagi cridat mai,
    `estimate_s` són els valors de naixement del dataclass — `{"remaining": 0, "basis": ""}`.
    Aquest zero vol dir "encara no tinc cap mesura", no "ja quasi està": la fila NO ha de
    dir cap temps. Mesurat de veritat: la fila va dir «0/12 · < 1 min restants» durant
    3 min 43 s abans que el primer document acabés de llegir-se."""
    row = JT.row({
        "project": "3001621 CASTELLAR",
        "state": "reading",
        "step": {"index": 2, "total": 4},
        "docs": {"done": 0, "total": 12},
        "estimate_s": {"remaining": 0, "basis": ""},
    }, now=NOW)
    assert row["comptador"] == "0/12"
    assert row["estimacio"] is None
    assert row["detall"] is None


def test_reading_row_keeps_a_real_less_than_one_minute():
    """El «< 1 min» segueix sent legítim quan HI HA base (encara que sigui la mediana per
    defecte per manca de mostres) i el temps restant real és petit — no es pot matar aquest
    cas per arreglar el fals de dalt.

    Nota (reviewer 2026-09-17): guarda d'invariant adjacent, no prova de la correcció —
    `_job()` ja posa `basis="test"` per defecte, així que aquest test passaria igual sense
    l'arreglo; el que fixa el defecte és `test_reading_row_with_no_telemetry_basis_shows_no_fake_time`."""
    row = JT.row(_job("reading", step=2, done=11, total=12, remaining=30), now=NOW)
    assert row["estimacio"] == "< 1 min"
    assert row["detall"] == "< 1 min restants"


def test_ready_row_never_shows_a_new_time_even_with_a_stale_estimate():
    """El job acabat no ha de guanyar cap text de temps nou, encara que `estimate_s` porti
    un `remaining`/`basis` residual d'abans d'acabar (READY ja força `estimacio = None`,
    aquest test ho fixa perquè no torni a trencar-se).

    Nota (reviewer 2026-09-17): guarda d'invariant adjacent, no prova de la correcció — READY
    ja sobreescriu `estimacio = None` explícitament abans i després de l'arreglo."""
    row = JT.row(
        _job("ready", step=4, done=13, total=13, finished_at="2026-08-25T18:32:00", remaining=45),
        now=NOW,
    )
    assert row["estimacio"] is None
    assert "restants" not in (row["detall"] or "")


def test_ready_row_says_when_and_offers_enllestir():
    row = JT.row(_job("ready", step=4, done=13, total=13, finished_at="2026-08-25T18:32:00"), now=NOW)
    assert row["pas"] == "✓"
    assert row["titol"] == "Preparat (ahir 18:32)"
    assert row["preparat_el"] == "ahir 18:32"
    assert (row["accio"], row["accio_text"]) == ("enllestir", "Enllestir")
    assert row["viu"] is False


def test_ready_row_never_says_preparat_when_nothing_was_actually_read():
    """2026-09-16: prova WSL amb la sessió de Claude caducada — 13 documents × 2 intents,
    cap llegit (`docs.failed == 13 == total`; els 2 "done" venen de duplicats saltats,
    ja no compten arran de l'arreglo a l'origen, però la guarda ni els mira). El job va
    acabar en `ready` dient «Preparat» net, com si l'informe es pogués enllestir amb zero
    documents llegits."""
    job = _job("ready", step=4, finished_at="2026-08-26T11:26:00",
                docs={"total": 13, "done": 2, "cached": 0, "errors": 26, "failed": 13})
    row = JT.row(job, now=NOW)
    assert "Preparat (" not in row["titol"]
    assert "sense llegir" in row["titol"]


def test_ready_row_never_says_preparat_even_when_done_matches_total_with_reviewer_snapshot():
    """CRÍTIC (reviewer, 2026-09-16): l'snapshot reproduït amb un projecte d'1 document real + el
    seu duplicat, on `done == total` (1 == 1) amagava que el document real havia fallat sencer
    (`docs.failed == 1 == total`, amb els 2 errors — un per intent — que el runner hi ha atribuït).
    La guarda no pot dependre de `done` (ni tan sols de comparar-lo amb `total`)."""
    job = _job("ready", step=4, finished_at="2026-08-26T11:26:00",
                docs={"total": 1, "done": 1, "cached": 0, "errors": 2, "failed": 1})
    row = JT.row(job, now=NOW)
    assert "Preparat (" not in row["titol"]
    assert "sense llegir" in row["titol"]


def test_ready_row_stays_preparat_when_transient_retries_succeeded_the_known_false_positive():
    """CRÍTIC (reviewer, 2026-09-17): el defecte de la versió anterior de la guarda (`errors >=
    total`). 2 documents, tots dos han necessitat un reintent transitori (PENETROS ja treballa a
    tocar del topall de temps, `runner.py` ~L614 — no és hipotètic) i els DOS s'han llegit:
    `{"total": 2, "done": 2, "errors": 2, "failed": 0}`. La fila ha de ser un «Preparat» NET."""
    job = _job("ready", step=4, finished_at="2026-08-26T11:26:00",
                docs={"total": 2, "done": 2, "cached": 0, "errors": 2, "failed": 0})
    row = JT.row(job, now=NOW)
    assert row["titol"] == "Preparat (avui 11:26)"


def test_ready_row_still_says_preparat_for_a_healthy_run_with_more_done_than_total():
    """Abans de l'arrel arreglada a `jobs.py`, `done` podia superar `total` en un job SA
    (duplicats saltats comptant com a `lectura_doc` abans que `docs_total` es conegués). Es manté
    com a test de robustesa (job antic al disc, o una altra font futura de `done` inflat): amb
    `failed == 0` la fila no ha de disparar l'avís de C encara que `done` no quadri amb `total`."""
    job = _job("ready", step=4, finished_at="2026-08-26T11:26:00",
                docs={"total": 13, "done": 15, "cached": 0, "errors": 0, "failed": 0})
    row = JT.row(job, now=NOW)
    assert row["titol"] == "Preparat (avui 11:26)"


def test_ready_row_still_says_preparat_when_everything_came_from_cache():
    job = _job("ready", step=4, finished_at="2026-08-26T11:26:00",
                docs={"total": 13, "done": 13, "cached": 13, "errors": 0, "failed": 0})
    row = JT.row(job, now=NOW)
    assert row["titol"] == "Preparat (avui 11:26)"


def test_ready_row_is_clean_for_an_old_job_json_without_the_failed_key():
    """Compatibilitat amb `_job.json` escrits abans d'aquest arreglo (2026-09-17): sense la clau
    `failed`, la guarda ha de ser INNÒCUA — mai un avís fals en repintar un job vell. Snapshot
    real trobat al clon de proves: 18 documents, 19 "done" (el comptador antic, inflat per un
    duplicat), 0 errors, i CAP clau `failed`."""
    job = _job("ready", step=4, finished_at="2026-08-26T11:26:00",
                docs={"total": 18, "done": 19, "cached": 0, "errors": 0})
    row = JT.row(job, now=NOW)
    assert row["titol"] == "Preparat (avui 11:26)"


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


def test_usage_limit_row_is_not_a_breakdown_and_says_how_to_resume():
    row = JT.row(_job("error", step=2, error={"code": "usage_limit", "detail": "La lectura s'ha aturat"}), now=NOW)
    assert row["pas"] == "✗"
    assert "límit d'ús" in row["titol"]
    assert "prem Preparar" in row["detall"] and "es conserven" in row["detall"]
    assert row["viu"] is False


def test_expired_auth_row_says_to_log_in_again_not_that_eficients_was_told():
    """2026-09-16: sessió de Claude caducada — no és una avaria nostra, així que la fila
    no ha de dir «avisat Eficients» sinó explicar el que l'Eva pot fer ella mateixa.
    2026-09-17 (decisió del Josep): l'Eva no obre mai un terminal — el detall apunta a la
    drecera dedicada de l'escriptori, «Tornar a entrar a Claude», no a `claude login`."""
    row = JT.row(_job("error", step=2, error={"code": "auth", "detail": "OAuth session expired"}), now=NOW)
    assert row["pas"] == "✗"
    assert "tornar a iniciar sessió" in row["titol"]
    assert "es conserven" in row["detall"] and "Preparar" in row["detall"]
    assert "Tornar a entrar a Claude" in row["detall"]
    assert "claude login" not in row["detall"] and "terminal" not in row["detall"]
    assert "avisat Eficients" not in row["titol"] and "avisat Eficients" not in row["detall"]
    assert row["viu"] is False


def test_cancelled_row_is_owned_by_eva():
    row = JT.row(_job("cancelled"), now=NOW)
    assert row["titol"] == "Aturat per tu"
    assert row["viu"] is False


@pytest.mark.parametrize(("state", "step", "titol"), [
    ("queued", 0, "En cua"),
    ("syncing", 1, "Copiant fitxers de la xarxa"),
    ("consolidating", 3, "Consolidant el que ha llegit"),
    ("imatges", 4, "Triant les imatges de l'informe"),
    ("merging", 5, "Preparant el formulari"),
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
