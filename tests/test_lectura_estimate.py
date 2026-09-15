"""Bloc E (`docs/PLA-UX-WIZARD-2026-09.md`) — durada estimada ABANS del clic.

`GET /api/jobs/estimate/{project_name:path}` mai copia ni escaneja amb md5:
resol la carpeta (local o de xarxa, sense sincronitzar-la) i compta els
documents que `route == "claude"` (`automation.lectura.inventory.
count_claude_documents`). Si ja hi ha un job `ready` per aquest projecte, es
reutilitza el `network_delta` que `list_jobs()` ja cacheja (1 min) en lloc de
tornar a recórrer la carpeta sencera.

Mateix patró que `tests/test_lectura_service.py` (`network_project`,
`_write_job_file`, `TestClient(app)`); les proves de text reutilitzen l'estil
paramètric de `tests/test_lectura_job_text.py`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from automation import config  # noqa: E402
from web import lectura_service  # noqa: E402
from web import wizard_service  # noqa: E402
from web.server import app  # noqa: E402


# ---------------------------------------------------------------------------
# Text de l'estimació (funció pura, sense I/O)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("n_docs", "estimate_s", "text"), [
    (0, 60, "0 documents · uns 1 min · pots tancar la pestanya i tornar"),
    (1, 40, "1 document · menys d'1 min · pots tancar la pestanya i tornar"),
    (18, 2400, "18 documents · uns 40 min · pots tancar la pestanya i tornar"),
])
def test_estimate_text_before_starting(n_docs, estimate_s, text):
    assert lectura_service._estimate_text(n_docs, estimate_s, ready=False) == text


@pytest.mark.parametrize(("n_docs", "estimate_s", "text"), [
    (0, 60, "res no ha canviat · uns 1 min"),
    (2, 600, "2 documents nous o canviats · uns 10 min"),
    (1, 600, "1 document nou o canviat · uns 10 min"),
])
def test_estimate_text_when_a_job_is_ready(n_docs, estimate_s, text):
    assert lectura_service._estimate_text(n_docs, estimate_s, ready=True) == text


def test_estimate_text_never_shows_seconds():
    text = lectura_service._estimate_text(3, 45, ready=False)
    assert "45 s" not in text
    assert "menys d'1 min" in text


def test_estimate_text_marks_a_partial_count():
    text = lectura_service._estimate_text(4, 300, ready=False, partial=True)
    assert "recompte parcial" in text


# ---------------------------------------------------------------------------
# Mode dev/local (sense xarxa): `wizard_service._REF_DIR`
# ---------------------------------------------------------------------------


@pytest.fixture
def local_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[str, Path]:
    """Mode dev/classic: cal desactivar EXPLÍCITAMENT el workflow de xarxa,
    perquè el `.env` d'aquest worktree en té un de configurat de veritat
    (`G3DT_NETWORK_PROJECTS`/`G3DT_LOCAL_WORKSPACE`) — mateix parany que
    `network_project`/`network_setup` eviten fent-ho a l'inrevés."""
    from automation import sync_workspace

    ref_dir = tmp_path / "refs"
    project_name = "4001612 BELL-LLOC"
    project_path = ref_dir / project_name
    (project_path / "PDF" / "ANNEXES").mkdir(parents=True)
    (project_path / "PDF" / "ANNEXES" / f"{project_name}_sondeig.pdf").write_bytes(b"%PDF")
    (project_path / "PDF" / "ANNEXES" / f"{project_name}_DPSH.pdf").write_bytes(b"%PDF")
    (project_path / "A.01 planol.pdf").write_bytes(b"%PDF")
    monkeypatch.setattr(wizard_service, "_REF_DIR", ref_dir)
    monkeypatch.setattr(config, "G3DT_USE_LECTURA_HEADLESS", True)
    monkeypatch.setattr(sync_workspace.config, "G3DT_NETWORK_PROJECTS", "")
    monkeypatch.setattr(sync_workspace.config, "G3DT_LOCAL_WORKSPACE", "")
    return project_name, project_path


def test_local_project_counts_documents_without_a_job(local_project):
    project_name, _ = local_project
    result = lectura_service.estimate_for_project(project_name)
    assert result["n_docs"] == 3
    assert result["estimate_s"] > 0
    assert "3 documents" in result["text"]
    assert "pots tancar la pestanya i tornar" in result["text"]
    assert result["ready"] is False


def test_a_project_that_does_not_exist_returns_no_figures(local_project):
    result = lectura_service.estimate_for_project("no existeix enlloc")
    assert result == {"n_docs": 0, "estimate_s": None, "text": "", "ready": False}


def test_endpoint_is_gated_like_the_rest_of_the_pipeline(local_project, monkeypatch):
    project_name, _ = local_project
    monkeypatch.setattr(config, "G3DT_USE_LECTURA_HEADLESS", False)

    r = TestClient(app).get(f"/api/jobs/estimate/{project_name}")

    assert r.status_code == 404


def test_endpoint_returns_the_estimate_when_enabled(local_project):
    project_name, _ = local_project
    r = TestClient(app).get(f"/api/jobs/estimate/{project_name}")

    assert r.status_code == 200
    body = r.json()
    assert body["n_docs"] == 3
    assert "documents" in body["text"]


# ---------------------------------------------------------------------------
# Mode xarxa: resol sense copiar; reutilitza el `network_delta` d'un `ready`
# ---------------------------------------------------------------------------


@pytest.fixture
def network_setup(tmp_path, monkeypatch):
    """Xarxa + workspace temporals, SENSE sincronitzar cap projecte encara."""
    from automation import sync_workspace

    net, ws = tmp_path / "net", tmp_path / "ws"
    net.mkdir()
    ws.mkdir()
    monkeypatch.setattr(sync_workspace.config, "G3DT_NETWORK_PROJECTS", str(net))
    monkeypatch.setattr(sync_workspace.config, "G3DT_LOCAL_WORKSPACE", str(ws))
    monkeypatch.setattr(wizard_service, "_REF_DIR", ws)
    monkeypatch.setattr(config, "G3DT_USE_LECTURA_HEADLESS", True)
    lectura_service._delta_cache.clear()
    return net, ws


def test_a_project_not_yet_copied_is_counted_straight_off_the_network(network_setup):
    net, ws = network_setup
    project = "3001621 CASTELLAR"
    (net / project / "PDF" / "ANNEXES").mkdir(parents=True)
    (net / project / "PDF" / "ANNEXES" / f"{project}_sondeig.pdf").write_bytes(b"%PDF")
    (net / project / "PRESSUPOST GEOTECNIC.pdf").write_bytes(b"%PDF")  # route python

    result = lectura_service.estimate_for_project(project)

    assert result["n_docs"] == 1
    assert not (ws / project).exists(), "l'estimació mai copia el projecte"


def test_a_nested_network_path_not_yet_copied_resolves_by_leaf(network_setup):
    net, ws = network_setup
    (net / "2025" / "Lleida" / "3001621 CASTELLAR" / "PDF" / "ANNEXES").mkdir(parents=True)
    sondeig = net / "2025" / "Lleida" / "3001621 CASTELLAR" / "PDF" / "ANNEXES" / "3001621_sondeig.pdf"
    sondeig.write_bytes(b"%PDF")

    result = lectura_service.estimate_for_project("2025/Lleida/3001621 CASTELLAR")

    assert result["n_docs"] == 1
    assert not ws.exists() or not any(ws.iterdir()), "l'estimació mai copia el projecte"


def _write_ready_job(project_path: Path, project: str, network_delta: dict | None) -> None:
    job_dir = project_path / "validation" / "lectura"
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "_job.json").write_text(json.dumps({
        "schema_version": 1, "project": project, "button": "preparar", "state": "ready",
        "step": {"index": 4, "total": 4},
        "docs": {"total": 1, "done": 1, "cached": 0, "errors": 0, "current": []},
        "started_at": "2026-08-26T17:00:00", "updated_at": "2026-08-26T18:32:00",
        "finished_at": "2026-08-26T18:32:00",
        "estimate_s": {"remaining": None, "basis": "t"}, "result": None, "error": None,
        "pid": 1, "claude_version": None, "network_delta": network_delta,
    }), encoding="utf-8")


def test_a_ready_project_reuses_the_network_delta_instead_of_recounting(network_setup, monkeypatch):
    from automation import sync_workspace

    net, ws = network_setup
    project = "4001612 BELL-LLOC"
    (net / project).mkdir(parents=True)
    (net / project / "PENETROS.pdf").write_text("camp", encoding="utf-8")
    sync_workspace.sync_to_workspace(project, allow_no_markers=True)
    _write_ready_job(ws / project, project, network_delta=None)
    (net / project / "A.01.pdf").write_text("plànol nou", encoding="utf-8")

    called = []
    monkeypatch.setattr(
        "automation.lectura.inventory.count_claude_documents",
        lambda p: called.append(p) or {"n_docs": 999, "n_files": 999},
    )

    result = lectura_service.estimate_for_project(project)

    assert not called, "amb un job ready, mai torna a comptar tota la carpeta"
    assert result["n_docs"] == 1
    assert "1 document nou o canviat" in result["text"]
    assert result["ready"] is True


def test_a_ready_project_with_nothing_changed(network_setup):
    from automation import sync_workspace

    net, ws = network_setup
    project = "4001612 BELL-LLOC"
    (net / project).mkdir(parents=True)
    (net / project / "PENETROS.pdf").write_text("camp", encoding="utf-8")
    sync_workspace.sync_to_workspace(project, allow_no_markers=True)
    _write_ready_job(ws / project, project, network_delta=None)

    result = lectura_service.estimate_for_project(project)

    assert result["n_docs"] == 0
    assert result["text"].startswith("res no ha canviat")
