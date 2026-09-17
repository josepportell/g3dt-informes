"""Tests per a `automation/lectura/jobs.py` (Fase 10, via A, tres botons).

Vegeu `docs/DISSENY-ANNEX-TRES-BOTONS-JOBS-NOTIFICACIONS-2026-08-24.md` §3
(registre de jobs, format `_job.json` §3.2, estats §3.3, transicions §3.4).

Mòdul autocontingut: NO importa res de `web/`. La majoria de tests
instancien `Job` directament (sense fil, per poder comprovar l'estat a
disc entre events determinísticament); els tests de lock/excepció usen
`JobRegistry.start()` amb un fil real (necessari perquè el comportament
que es prova viu dins `_run()`).
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path

from automation.lectura import jobs

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fresh_job(tmp_path: Path, project: str = "proj") -> jobs.Job:
    job_path = tmp_path / project / "validation" / "lectura" / jobs.JOB_FILENAME
    return jobs.Job(
        project=project,
        button="preparar",
        job_path=job_path,
        started_at="2026-08-25T10:00:00",
        updated_at="2026-08-25T10:00:00",
        concurrency=2,
        telemetry_paths_fn=lambda: [],
    )


def _read_job(job_path: Path) -> dict:
    return json.loads(job_path.read_text(encoding="utf-8"))


def _minimal_job_payload(project: str, *, state: str, pid: int, updated_at: str) -> dict:
    return {
        "schema_version": 1,
        "project": project,
        "button": "preparar",
        "state": state,
        "step": {"index": 2, "total": 4},
        "docs": {"total": 5, "done": 2, "cached": 0, "errors": 0, "current": []},
        "started_at": updated_at,
        "updated_at": updated_at,
        "finished_at": None,
        "estimate_s": {"remaining": 100, "basis": "x"},
        "result": None,
        "error": None,
        "pid": pid,
        "claude_version": None,
        "network_delta": None,
    }


# ---------------------------------------------------------------------------
# Transicions (Job.emit, sense fil)
# ---------------------------------------------------------------------------


def test_transitions_happy_path_reading_consolidating_merging_ready(tmp_path):
    job = _fresh_job(tmp_path)
    job.write()

    job.emit("lectura_inventari", {"n_files": 5})
    assert _read_job(job.job_path)["state"] == jobs.READING

    job.emit("lectura_inici", {"n_claude": 3, "n_python": 0, "docs": ["a.pdf", "b.pdf", "c.pdf"]})
    assert job.docs_total == 3

    job.emit("lectura_doc_inici", {"doc": "a.pdf"})
    job.emit("lectura_doc_inici", {"doc": "b.pdf"})
    job.emit("lectura_doc_inici", {"doc": "c.pdf"})
    assert set(job.docs_current) == {"a.pdf", "b.pdf", "c.pdf"}

    job.emit("lectura_doc", {"doc": "a.pdf", "cached": False, "attempt": 1})
    job.emit("lectura_doc", {"doc": "b.pdf", "cached": True})
    job.emit("lectura_doc", {"doc": "c.pdf", "cached": False, "attempt": 1})
    on_disk = _read_job(job.job_path)
    assert on_disk["state"] == jobs.READING
    assert on_disk["docs"] == {"total": 3, "done": 3, "cached": 1, "errors": 0, "failed": 0, "current": []}

    job.emit("lectura_decisions_marker", {"cached": False})
    on_disk = _read_job(job.job_path)
    assert on_disk["state"] == jobs.CONSOLIDATING
    assert on_disk["step"]["index"] == 3

    job.emit("lectura_fi", {"n_docs": 3, "by_status": {"ok": 3}, "elapsed_s_total": 1.2, "degraded": False})
    on_disk = _read_job(job.job_path)
    assert on_disk["state"] == jobs.MERGING
    assert on_disk["step"]["index"] == 5

    # Lectors d'imatges (2026-09-10): pas 4 de 5, entre la consolidació i el merge.
    job.emit("lector_imatges_inici", {"lector": "fotos", "n": 1, "of": 2})
    on_disk = _read_job(job.job_path)
    assert on_disk["state"] == jobs.IMATGES
    assert on_disk["step"] == {"index": 4, "total": 5}
    assert on_disk["estimate_s"]["remaining"] == int(2 * jobs._DEFAULT_LECTOR_S + 60)
    job.emit("lector_imatges_fi", {"lector": "fotos", "status": "ok", "elapsed_s": 40.0})
    job.emit("lector_imatges_inici", {"lector": "figures", "n": 2, "of": 2})
    assert _read_job(job.job_path)["estimate_s"]["remaining"] == int(jobs._DEFAULT_LECTOR_S + 60)
    job.emit("lector_imatges_fi", {"lector": "figures", "status": "ok", "elapsed_s": 50.0})

    job.emit("merge_inici", {})
    on_disk = _read_job(job.job_path)
    assert on_disk["state"] == jobs.MERGING
    assert on_disk["step"]["index"] == 5

    job.emit("prefills", {"client_name": {"value": "x", "source": "lectura"}})
    on_disk = _read_job(job.job_path)
    assert on_disk["state"] == jobs.READY
    assert on_disk["step"]["index"] == 5
    assert on_disk["result"] == {"ok": True, "degraded": False, "fallback": None}
    assert on_disk["finished_at"] is not None


def test_lectura_doc_error_increments_errors_without_touching_done(tmp_path):
    job = _fresh_job(tmp_path)
    job.emit("lectura_inici", {"n_claude": 1})
    job.emit("lectura_doc_inici", {"doc": "a.pdf"})
    job.emit("lectura_doc_error", {"doc": "a.pdf", "attempt": 1, "rc": 1, "timeout": False})

    assert job.docs_errors == 1
    assert job.docs_done == 0
    on_disk = _read_job(job.job_path)
    assert on_disk["docs"]["errors"] == 1
    assert on_disk["docs"]["done"] == 0


def test_docs_failed_only_counts_definitive_failures_from_lectura_fi(tmp_path):
    """Tercera passada (reviewer, 2026-09-17): `docs.failed` és un comptador NOU, separat
    d'`errors` (per intent). Un document que falla al primer intent i encerta al segon aporta
    un `errors` però NO ha de comptar mai a `failed` — `automation/lectura/runner.py` només
    inclou a `docs_failed` (dins `lectura_fi`) els documents amb estat FINAL `"failed"` o
    `"skipped_systemic"`, mai un intent intermedi."""
    job = _fresh_job(tmp_path)
    job.emit("lectura_inici", {"n_claude": 3})
    # a.pdf: falla el primer intent, encerta el segon — errors puja, failed NO.
    job.emit("lectura_doc_error", {"doc": "a.pdf", "attempt": 1, "rc": 1, "timeout": False})
    job.emit("lectura_doc", {"doc": "a.pdf", "cached": False, "attempt": 2})
    # b.pdf i c.pdf: intents esgotats / parada sistèmica — el runner ho reporta a `docs_failed`.
    job.emit("lectura_fi", {"n_docs": 3, "by_status": {"ok": 1, "failed": 1, "skipped_systemic": 1},
                            "elapsed_s_total": 3.0, "degraded": True,
                            "docs_failed": ["b.pdf", "c.pdf"]})

    assert job.docs_errors == 1
    assert job.docs_done == 1
    assert job.docs_failed == 2
    on_disk = _read_job(job.job_path)
    assert on_disk["docs"]["failed"] == 2
    assert on_disk["docs"]["errors"] == 1
    assert on_disk["docs"]["done"] == 1


def test_skipped_duplicate_does_not_inflate_done_or_cached(tmp_path):
    """CRÍTIC (reviewer, 2026-09-16): un duplicat saltat (`runner._run_lectura` emet
    `lectura_doc` amb `skipped_duplicate: True` ABANS de conèixer `docs_total`) no és un
    document llegit. Comptar-lo com a "done" produïa els defectes coneguts 19/18 i 15/13
    (DECISION-LOG 2026-09-10/2026-09-16) i, més greu, permetia que un `done` inflat amagués
    un run 100% trencat a `job_text._reading_found_nothing`. El progrés d'un run sa ha de
    seguir arribant EXACTAMENT a `total/total`, mai per sobre."""
    job = _fresh_job(tmp_path)
    job.emit("lectura_doc", {"doc": "annex_a_copy.pdf", "skipped_duplicate": True})
    assert job.docs_done == 0 and job.docs_cached == 0

    job.emit("lectura_inici", {"n_claude": 2, "docs": ["a.pdf", "b.pdf"]})
    job.emit("lectura_doc", {"doc": "a.pdf", "cached": False, "attempt": 1})
    job.emit("lectura_doc", {"doc": "b.pdf", "cached": True})

    on_disk = _read_job(job.job_path)
    assert on_disk["docs"] == {"total": 2, "done": 2, "cached": 1, "errors": 0, "failed": 0, "current": []}


def test_cancelled_event_sets_cancelled_state(tmp_path):
    job = _fresh_job(tmp_path)
    job.emit("lectura_inventari", {"n_files": 1})
    job.emit("cancelled", {"phase": "documents"})

    assert job.state == jobs.CANCELLED
    assert job.finished_at is not None
    on_disk = _read_job(job.job_path)
    assert on_disk["state"] == jobs.CANCELLED
    assert on_disk["finished_at"] is not None


def test_error_event_sets_error_state_with_detail(tmp_path):
    job = _fresh_job(tmp_path)
    job.emit("error_event", {"message": "spawn crash"})

    assert job.state == jobs.ERROR
    assert job.error == {"code": "exception", "detail": "spawn crash"}
    on_disk = _read_job(job.job_path)
    assert on_disk["state"] == jobs.ERROR
    assert on_disk["error"]["detail"] == "spawn crash"


# ---------------------------------------------------------------------------
# JobRegistry: excepció / sense event terminal (fil real)
# ---------------------------------------------------------------------------


def test_registry_start_exception_in_target_sets_error(tmp_path):
    registry = jobs.JobRegistry()
    project_path = tmp_path / "proj_boom"

    def _boom(job: jobs.Job) -> None:
        raise RuntimeError("mock target crash")

    job, created = registry.start(
        "proj_boom", project_path, "preparar", _boom,
        concurrency=2, telemetry_paths_fn=lambda: [],
    )
    assert created is True
    job.thread.join(timeout=5)

    assert job.state == jobs.ERROR
    assert job.error == {"code": "exception", "detail": "mock target crash"}
    assert job.finished_at is not None


def test_registry_start_target_without_terminal_event_sets_error(tmp_path):
    registry = jobs.JobRegistry()
    project_path = tmp_path / "proj_silent"

    def _silent(job: jobs.Job) -> None:
        job.emit("lectura_inventari", {"n_files": 1})  # cap event terminal

    job, created = registry.start(
        "proj_silent", project_path, "preparar", _silent,
        concurrency=2, telemetry_paths_fn=lambda: [],
    )
    assert created is True
    job.thread.join(timeout=5)

    assert job.state == jobs.ERROR
    assert job.error["detail"] == "job ended without terminal event"


# ---------------------------------------------------------------------------
# Lock: un job viu per projecte
# ---------------------------------------------------------------------------


def test_registry_start_second_call_attaches_to_live_job_then_new_after_terminal(tmp_path):
    registry = jobs.JobRegistry()
    project_path = tmp_path / "proj_lock"
    gate = threading.Event()

    def _blocked(job: jobs.Job) -> None:
        gate.wait(timeout=5)
        job.emit("cancelled", {"phase": "test"})

    job1, created1 = registry.start(
        "proj_lock", project_path, "preparar", _blocked,
        concurrency=2, telemetry_paths_fn=lambda: [],
    )
    assert created1 is True

    job2, created2 = registry.start(
        "proj_lock", project_path, "enllestir", _blocked,
        concurrency=2, telemetry_paths_fn=lambda: [],
    )
    assert created2 is False
    assert job2 is job1

    gate.set()
    job1.thread.join(timeout=5)
    assert job1.state == jobs.CANCELLED

    gate2 = threading.Event()

    def _blocked2(job: jobs.Job) -> None:
        gate2.wait(timeout=5)
        job.emit("cancelled", {"phase": "test2"})

    job3, created3 = registry.start(
        "proj_lock", project_path, "preparar", _blocked2,
        concurrency=2, telemetry_paths_fn=lambda: [],
    )
    assert created3 is True
    assert job3 is not job1

    gate2.set()
    job3.thread.join(timeout=5)
    assert job3.state == jobs.CANCELLED


# ---------------------------------------------------------------------------
# Subscriptor tardà: replay + live, sense duplicats ni forats
# ---------------------------------------------------------------------------


def test_late_subscriber_gets_replay_then_live_events(tmp_path):
    job = _fresh_job(tmp_path)
    job.emit("lectura_inventari", {"n_files": 1})
    job.emit("lectura_inici", {"n_claude": 1})
    job.emit("lectura_doc_inici", {"doc": "a.pdf"})

    q = job.subscribe()
    replayed = [q.get(timeout=1) for _ in range(3)]
    assert [name for name, _ in replayed] == ["lectura_inventari", "lectura_inici", "lectura_doc_inici"]

    job.emit("lectura_doc", {"doc": "a.pdf", "cached": False})
    job.emit("prefills", {"x": 1})

    live = [q.get(timeout=1) for _ in range(2)]
    assert [name for name, _ in live] == ["lectura_doc", "prefills"]
    assert q.empty()


def test_two_subscribers_receive_identical_event_stream(tmp_path):
    job = _fresh_job(tmp_path)
    job.emit("lectura_inventari", {"n_files": 1})

    q1 = job.subscribe()
    q2 = job.subscribe()

    job.emit("prefills", {"x": 1})

    for q in (q1, q2):
        items = [q.get(timeout=1), q.get(timeout=1)]
        assert [name for name, _ in items] == ["lectura_inventari", "prefills"]
        assert q.empty()


# ---------------------------------------------------------------------------
# list_jobs
# ---------------------------------------------------------------------------


def test_list_jobs_marks_stale_pid_job_as_interrupted_and_rewrites_file(tmp_path):
    registry = jobs.JobRegistry()
    root = tmp_path / "root_stale"
    job_dir = root / "proj_stale" / "validation" / "lectura"
    job_dir.mkdir(parents=True)
    job_path = job_dir / jobs.JOB_FILENAME
    stale_pid = os.getpid() + 1
    payload = _minimal_job_payload("proj_stale", state=jobs.READING, pid=stale_pid, updated_at="2026-08-25T10:00:00")
    job_path.write_text(json.dumps(payload), encoding="utf-8")

    result = registry.list_jobs(root)

    assert len(result) == 1
    assert result[0]["state"] == jobs.INTERRUPTED
    assert result[0]["docs"]["done"] == 2
    assert result[0]["docs"]["total"] == 5
    assert result[0]["error"] is None

    on_disk = json.loads(job_path.read_text(encoding="utf-8"))
    assert on_disk["state"] == jobs.INTERRUPTED


def test_list_jobs_uses_live_registry_snapshot_when_available(tmp_path):
    registry = jobs.JobRegistry()
    root = tmp_path / "root_live"
    project_dir = root / "proj_live"
    (project_dir / "validation" / "lectura").mkdir(parents=True)
    gate = threading.Event()

    def _blocked(job: jobs.Job) -> None:
        gate.wait(timeout=5)
        job.emit("cancelled", {"phase": "x"})

    job, _created = registry.start(
        "proj_live", project_dir, "preparar", _blocked,
        concurrency=2, telemetry_paths_fn=lambda: [],
    )

    result = registry.list_jobs(root)
    assert len(result) == 1
    assert result[0]["project"] == "proj_live"
    assert result[0]["pid"] == os.getpid()

    gate.set()
    job.thread.join(timeout=5)


def test_list_jobs_filters_out_entries_older_than_max_age(tmp_path):
    registry = jobs.JobRegistry()
    root = tmp_path / "root_old"
    job_dir = root / "proj_old" / "validation" / "lectura"
    job_dir.mkdir(parents=True)
    old_updated = (datetime.now() - timedelta(days=40)).isoformat(timespec="seconds")
    payload = _minimal_job_payload("proj_old", state=jobs.READY, pid=os.getpid(), updated_at=old_updated)
    (job_dir / jobs.JOB_FILENAME).write_text(json.dumps(payload), encoding="utf-8")

    assert registry.list_jobs(root, max_age_days=30) == []
    assert len(registry.list_jobs(root, max_age_days=None)) == 1
    assert len(registry.mark_interrupted_at_startup(root)) == 1


def test_list_jobs_ignores_malformed_job_file(tmp_path):
    registry = jobs.JobRegistry()
    root = tmp_path / "root_bad"
    job_dir = root / "proj_bad" / "validation" / "lectura"
    job_dir.mkdir(parents=True)
    (job_dir / jobs.JOB_FILENAME).write_text("{not valid json", encoding="utf-8")

    assert registry.list_jobs(root) == []


def test_list_jobs_orders_live_jobs_before_terminal_ones(tmp_path):
    registry = jobs.JobRegistry()
    root = tmp_path / "root_order"

    terminal_dir = root / "proj_terminal" / "validation" / "lectura"
    terminal_dir.mkdir(parents=True)
    now = datetime.now().isoformat(timespec="seconds")
    payload = _minimal_job_payload("proj_terminal", state=jobs.READY, pid=os.getpid(), updated_at=now)
    payload["result"] = {"ok": True, "degraded": False, "fallback": None}
    (terminal_dir / jobs.JOB_FILENAME).write_text(json.dumps(payload), encoding="utf-8")

    (root / "proj_live3" / "validation" / "lectura").mkdir(parents=True)
    gate = threading.Event()

    def _blocked(job: jobs.Job) -> None:
        gate.wait(timeout=5)
        job.emit("cancelled", {"phase": "x"})

    job, _created = registry.start(
        "proj_live3", root / "proj_live3", "preparar", _blocked,
        concurrency=2, telemetry_paths_fn=lambda: [],
    )

    result = registry.list_jobs(root)
    assert [r["project"] for r in result] == ["proj_live3", "proj_terminal"]

    gate.set()
    job.thread.join(timeout=5)


# ---------------------------------------------------------------------------
# estimate_remaining
# ---------------------------------------------------------------------------


def test_estimate_remaining_default_basis_with_no_telemetry(tmp_path):
    job = _fresh_job(tmp_path)
    job.state = jobs.READING
    job.docs_total = 5
    job.docs_done = 0
    job._docs_total_known = True  # simula que `lectura_inici` ja ha passat

    result = jobs.estimate_remaining(job, [], concurrency=2)

    assert result["basis"].startswith("default")
    assert result["remaining"] == 3 * 270 + 600 + 2 * jobs._DEFAULT_LECTOR_S + 60  # ceil(5/2)=3 blocs + 2 lectors


def test_estimate_remaining_median_from_five_samples(tmp_path):
    job = _fresh_job(tmp_path)
    job.state = jobs.READING
    job._docs_total_known = True  # simula que `lectura_inici` ja ha passat
    telemetry_path = tmp_path / "_telemetry.jsonl"
    lines = [
        json.dumps({"mode": "only", "cached": False, "rc": 0, "elapsed_s": v})
        for v in (100, 200, 300, 400, 500)
    ]
    telemetry_path.write_text("\n".join(lines), encoding="utf-8")

    result = jobs.estimate_remaining(job, [telemetry_path], concurrency=2)

    assert "median_doc_s=300" in result["basis"]


def test_estimate_remaining_ignores_cached_and_nonzero_rc_rows(tmp_path):
    job = _fresh_job(tmp_path)
    job.state = jobs.READING
    job._docs_total_known = True  # simula que `lectura_inici` ja ha passat
    telemetry_path = tmp_path / "_telemetry.jsonl"
    good = [{"mode": "only", "cached": False, "rc": 0, "elapsed_s": 250} for _ in range(50)]
    bad_cached = [{"mode": "only", "cached": True, "rc": 0, "elapsed_s": 999} for _ in range(5)]
    bad_rc = [{"mode": "only", "cached": False, "rc": 1, "elapsed_s": 999} for _ in range(5)]
    lines = [json.dumps(row) for row in good + bad_cached + bad_rc]
    telemetry_path.write_text("\n".join(lines), encoding="utf-8")

    result = jobs.estimate_remaining(job, [telemetry_path], concurrency=2)

    assert "median_doc_s=250" in result["basis"]
    assert "from 50 telemetry rows" in result["basis"]


def test_estimate_remaining_blocks_ceiling_with_concurrency(tmp_path):
    job = _fresh_job(tmp_path)
    job.state = jobs.READING
    job.docs_total = 7
    job.docs_done = 0
    job._docs_total_known = True  # simula que `lectura_inici` ja ha passat

    result = jobs.estimate_remaining(job, [], concurrency=3)

    assert result["remaining"] == 3 * 270 + 600 + 2 * jobs._DEFAULT_LECTOR_S + 60  # ceil(7/3)=3 blocs + 2 lectors


def test_estimate_remaining_terminal_state_is_zero(tmp_path):
    job = _fresh_job(tmp_path)
    job.state = jobs.READY

    result = jobs.estimate_remaining(job, [], concurrency=2)

    assert result == {"remaining": 0, "basis": "terminal"}


def test_estimate_remaining_reading_before_docs_total_is_known_gives_no_fake_number(tmp_path):
    """Reviewer 2026-09-17 (forat real): sense la guarda, `job.state == READING` amb
    `docs_total` encara a 0 ("no sabut", no "sabut i és zero") calculava `blocks=0` i encara
    hi sumava els extres de READING (consolidació + lectors), donant un número real-semblant
    però fals — `basis` ja no era buida perquè hi havia telemetria a la màquina."""
    job = _fresh_job(tmp_path)
    job.state = jobs.READING
    telemetry_path = tmp_path / "_telemetry.jsonl"
    lines = [
        json.dumps({"mode": "only", "cached": False, "rc": 0, "elapsed_s": v})
        for v in (100, 200, 300, 400, 500)
    ]
    telemetry_path.write_text("\n".join(lines), encoding="utf-8")

    assert job._docs_total_known is False
    result = jobs.estimate_remaining(job, [telemetry_path], concurrency=2)

    assert result == {"remaining": 0, "basis": ""}


def test_lectura_inici_recomputes_estimate_immediately_when_telemetry_exists(tmp_path):
    """2026-09-17 (mesura Rubí): abans, `estimate_remaining_s`/`estimate_basis` es quedaven
    als valors de naixement del dataclass (`0`/`""`) fins al primer `lectura_doc` —
    amb 12 documents i concurrència 2, això podia trigar minuts, i durant aquesta finestra
    la fila deia «< 1 min restants» (fals). A `lectura_inici` ja se sap `docs_total`; si hi
    ha telemetria disponible a la màquina, l'estimació ha de ser real de seguida, no `0`."""
    job = _fresh_job(tmp_path)
    telemetry_path = tmp_path / "_telemetry.jsonl"
    lines = [
        json.dumps({"mode": "only", "cached": False, "rc": 0, "elapsed_s": v})
        for v in (100, 200, 300, 400, 500)
    ]
    telemetry_path.write_text("\n".join(lines), encoding="utf-8")
    job.telemetry_paths_fn = lambda: [telemetry_path]

    job.emit("lectura_inventari", {"n_files": 12})
    assert job.docs_total == 0
    assert job.estimate_basis == ""  # encara no es coneix `docs_total`

    job.emit("lectura_inici", {"n_claude": 12, "n_python": 0, "docs": []})

    assert job.docs_total == 12
    assert job.docs_done == 0
    assert job.estimate_remaining_s > 0
    assert "median_doc_s=300" in job.estimate_basis


def test_skipped_duplicate_before_lectura_inici_does_not_produce_a_fake_estimate(tmp_path):
    """Reviewer 2026-09-17 — seqüència reproduïda EXACTA de `runner._run_lectura`
    (~L1255-1263): els duplicats saltats emeten `lectura_doc` amb `skipped_duplicate=True`
    ABANS que `lectura_inici` sàpiga `docs_total`. `_recompute_estimate()` es crida igualment
    des d'aquell `lectura_doc` (és incondicional): abans de la guarda, com que hi havia
    telemetria a la màquina, `basis` ja no era buida i sortia un número real-semblant però
    fals («≈ 14 min» amb `blocks=0`). Ha de seguir sense estimació fins que `lectura_inici`
    sàpiga de veritat quants documents hi ha."""
    job = _fresh_job(tmp_path)
    telemetry_path = tmp_path / "_telemetry.jsonl"
    lines = [
        json.dumps({"mode": "only", "cached": False, "rc": 0, "elapsed_s": v})
        for v in (100, 200, 300, 400, 500)
    ]
    telemetry_path.write_text("\n".join(lines), encoding="utf-8")
    job.telemetry_paths_fn = lambda: [telemetry_path]

    job.emit("lectura_inventari", {"n_files": 13})
    assert job.estimate_basis == ""
    assert job.estimate_remaining_s == 0

    # Duplicat saltat, ABANS de `lectura_inici` (com fa `runner.py`).
    job.emit("lectura_doc", {"doc": "annex_a_copy.pdf", "skipped_duplicate": True})
    assert job.docs_done == 0 and job.docs_cached == 0  # invariant intacte: no compta com llegit
    assert job.estimate_basis == "", "no ha de sortir cap número mentre `docs_total` és desconegut"
    assert job.estimate_remaining_s == 0

    # Ara sí: `lectura_inici` fixa `docs_total` amb un valor de veritat.
    job.emit("lectura_inici", {"n_claude": 12, "n_python": 0, "docs": []})
    assert job.docs_total == 12
    assert job.estimate_remaining_s > 0
    assert "median_doc_s=300" in job.estimate_basis


# ---------------------------------------------------------------------------
# Escriptura atòmica
# ---------------------------------------------------------------------------


def test_write_is_atomic_leaves_no_tmp_files(tmp_path):
    job = _fresh_job(tmp_path)
    sequence = [
        ("lectura_inventari", {"n_files": 1}),
        ("lectura_inici", {"n_claude": 1}),
        ("lectura_doc_inici", {"doc": "a.pdf"}),
        ("lectura_doc", {"doc": "a.pdf", "cached": False}),
        ("lectura_decisions_marker", {"cached": False}),
        ("lectura_fi", {"degraded": False}),
        ("prefills", {"x": 1}),
    ]
    for event_type, detail in sequence:
        job.emit(event_type, detail)

    job_dir = job.job_path.parent
    assert list(job_dir.glob("*.tmp")) == []
    assert job.job_path.exists()


def test_error_event_keeps_its_code_for_the_usage_limit(tmp_path):
    job = _fresh_job(tmp_path)
    job.write()
    job.emit("error_event", {"code": "usage_limit", "reason": "resets at 3pm", "message": "La lectura s'ha aturat"})
    on_disk = _read_job(job.job_path)
    assert on_disk["state"] == jobs.ERROR
    assert on_disk["error"] == {"code": "usage_limit", "detail": "La lectura s'ha aturat"}
