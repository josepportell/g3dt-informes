"""Fase 11 — delta-sync xarxa → workspace (disseny annex §4).

`sync_to_workspace` copia un projecte un sol cop. Amb carpetes compartides on hi
toca gent cada dia, això deixava dues sortides dolentes: treballar amb fitxers
vells sense dir-ho, o `force` i recopiar-ho tot per SMB. `sync_delta` mira què ha
canviat i porta només això.

El que es prova, per ordre d'importància:

1. **Res es perd.** El que desapareix de la xarxa es MOU a `_esborrats/`, i el
   que produeix el pipeline al workspace (informe, `file_mapping.json`,
   `user_data.json`) no es toca mai — no és a la xarxa, però no hi ha de ser.
2. **Un fitxer tocat però igual no compta com a canvi** (§4): és el cas normal
   quan algú obre un PDF i el desa. Zero re-lectures.
3. **`check_only` no toca res**: és el que fa la taula d'estat cada minut.
4. **md5 només quan mida+mtime difereixen**: llegir totes les fotografies per
   SMB costaria més que la còpia sencera.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from automation import sync_workspace as SW


@pytest.fixture
def net_and_ws(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    net = tmp_path / "net"
    ws = tmp_path / "ws"
    (net / "4001612 BELL-LLOC" / "ANNEXES").mkdir(parents=True)
    ws.mkdir()
    monkeypatch.setattr(SW.config, "G3DT_NETWORK_PROJECTS", str(net))
    monkeypatch.setattr(SW.config, "G3DT_LOCAL_WORKSPACE", str(ws))
    return net / "4001612 BELL-LLOC", ws / "4001612 BELL-LLOC"


def _write(path: Path, text: str, mtime: float | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if mtime is not None:
        os.utime(path, (mtime, mtime))


def _seed(net_project: Path) -> None:
    _write(net_project / "PENETROS.pdf", "camp", 1_700_000_000)
    _write(net_project / "ANNEXES" / "4001612_DPSH.xls", "excel", 1_700_000_000)
    _write(net_project / "COORDENADES.txt", "P-1\n1;2;3\n", 1_700_000_000)


def _sync_first_time() -> dict:
    return SW.sync_to_workspace("4001612 BELL-LLOC", allow_no_markers=True)


# ---------------------------------------------------------------------------
# Casos base
# ---------------------------------------------------------------------------

def test_nothing_changed_means_nothing_to_do(net_and_ws):
    net_project, _ = net_and_ws
    _seed(net_project)
    _sync_first_time()

    d = SW.sync_delta("4001612 BELL-LLOC")

    assert d["status"] == "ok"
    assert (d["new"], d["changed"], d["deleted"]) == ([], [], [])
    assert d["copied"] == 0 and d["moved"] == 0


def test_a_new_file_is_copied(net_and_ws):
    net_project, ws_project = net_and_ws
    _seed(net_project)
    _sync_first_time()
    _write(net_project / "ANNEXES" / "4001612_sondeig.pdf", "annex nou")

    d = SW.sync_delta("4001612 BELL-LLOC")

    assert d["new"] == ["ANNEXES/4001612_sondeig.pdf"]
    assert d["copied"] == 1
    assert (ws_project / "ANNEXES" / "4001612_sondeig.pdf").read_text(encoding="utf-8") == "annex nou"


def test_a_changed_file_is_recopied(net_and_ws):
    net_project, ws_project = net_and_ws
    _seed(net_project)
    _sync_first_time()
    _write(net_project / "PENETROS.pdf", "camp revisat", 1_700_090_000)

    d = SW.sync_delta("4001612 BELL-LLOC")

    assert d["changed"] == ["PENETROS.pdf"]
    assert (ws_project / "PENETROS.pdf").read_text(encoding="utf-8") == "camp revisat"


def test_touched_but_identical_is_not_a_change(net_and_ws):
    """§4: obrir i desar un PDF sense canviar bytes. mtime nou, md5 igual."""
    net_project, _ = net_and_ws
    _seed(net_project)
    _sync_first_time()
    _write(net_project / "PENETROS.pdf", "camp", 1_700_500_000)   # mateix contingut

    d = SW.sync_delta("4001612 BELL-LLOC")

    assert d["changed"] == []
    assert d["hashed"] == 1, "ha calgut un md5 per descobrir-ho, i només un"


def test_md5_is_only_read_when_size_or_mtime_differ(net_and_ws):
    """La raó de ser del pas 2: no llegir GB de fotografies per SMB."""
    net_project, _ = net_and_ws
    _seed(net_project)
    for i in range(10):
        _write(net_project / "FOTOGRAFIES" / f"foto{i}.jpg", "x" * 100, 1_700_000_000)
    _sync_first_time()

    d = SW.sync_delta("4001612 BELL-LLOC", check_only=True)

    assert d["checked"] == 13
    assert d["hashed"] == 0


# ---------------------------------------------------------------------------
# 1. Res es perd
# ---------------------------------------------------------------------------

def test_a_file_deleted_on_the_network_is_moved_not_removed(net_and_ws):
    net_project, ws_project = net_and_ws
    _seed(net_project)
    _sync_first_time()
    (net_project / "COORDENADES.txt").unlink()

    d = SW.sync_delta("4001612 BELL-LLOC")

    assert d["deleted"] == ["COORDENADES.txt"] and d["moved"] == 1
    assert not (ws_project / "COORDENADES.txt").exists()
    apartat = ws_project / SW.DELETED_DIRNAME / "COORDENADES.txt"
    assert apartat.read_text(encoding="utf-8").startswith("P-1")


@pytest.mark.parametrize("name", [
    "file_mapping.json", "user_data.json", "_user_data_prev.json",
    "photo_selection.json", "4001612_generated.docx", "4001612_AUDIT_VISUAL.docx",
])
def test_what_the_pipeline_produces_is_never_treated_as_deleted(net_and_ws, name):
    """Errar aquí seria moure l'informe de l'Eva a `_esborrats/`."""
    net_project, ws_project = net_and_ws
    _seed(net_project)
    _sync_first_time()
    _write(ws_project / name, "sortida local")

    d = SW.sync_delta("4001612 BELL-LLOC")

    assert d["deleted"] == []
    assert (ws_project / name).exists()


def test_validation_and_the_marker_are_out_of_the_comparison(net_and_ws):
    net_project, ws_project = net_and_ws
    _seed(net_project)
    _sync_first_time()
    _write(ws_project / "validation" / "lectura" / "_decisions.json", "{}")
    _write(ws_project / "validation" / "concept_map.json", "{}")

    d = SW.sync_delta("4001612 BELL-LLOC")

    assert d["deleted"] == []
    assert (ws_project / "validation" / "lectura" / "_decisions.json").exists()
    assert (ws_project / SW._NETWORK_PATH_MARKER).exists()


def test_the_deleted_drawer_is_not_re_examined_on_the_next_run(net_and_ws):
    net_project, ws_project = net_and_ws
    _seed(net_project)
    _sync_first_time()
    (net_project / "COORDENADES.txt").unlink()
    SW.sync_delta("4001612 BELL-LLOC")

    again = SW.sync_delta("4001612 BELL-LLOC")

    assert (again["deleted"], again["moved"]) == ([], 0)


# ---------------------------------------------------------------------------
# 3. `check_only` no toca res
# ---------------------------------------------------------------------------

def test_check_only_reports_without_copying_or_moving(net_and_ws):
    net_project, ws_project = net_and_ws
    _seed(net_project)
    _sync_first_time()
    _write(net_project / "A.01.pdf", "plànol nou")
    (net_project / "COORDENADES.txt").unlink()

    d = SW.sync_delta("4001612 BELL-LLOC", check_only=True)

    assert d["new"] == ["A.01.pdf"] and d["deleted"] == ["COORDENADES.txt"]
    assert (d["copied"], d["moved"]) == (0, 0)
    assert not (ws_project / "A.01.pdf").exists()
    assert (ws_project / "COORDENADES.txt").exists()
    assert not (ws_project / SW.DELETED_DIRNAME).exists()


# ---------------------------------------------------------------------------
# Estats de sortida
# ---------------------------------------------------------------------------

def test_a_project_not_yet_in_the_workspace_asks_for_a_full_sync(net_and_ws):
    net_project, _ = net_and_ws
    _seed(net_project)

    d = SW.sync_delta("4001612 BELL-LLOC")

    assert d["status"] == "absent"
    assert d["leaf"] == "4001612 BELL-LLOC"


def test_without_the_network_workflow_it_does_nothing(net_and_ws, monkeypatch):
    monkeypatch.setattr(SW.config, "G3DT_NETWORK_PROJECTS", "")

    assert SW.sync_delta("qualsevol")["status"] == "skipped"


def test_an_unknown_network_folder_is_an_error_not_a_crash(net_and_ws):
    assert SW.sync_delta("no existeix")["status"] == "error"


def test_path_traversal_is_rejected(net_and_ws):
    assert SW.sync_delta("../../etc")["status"] == "error"


def test_nested_projects_keep_their_workspace_leaf(tmp_path, monkeypatch):
    net, ws = tmp_path / "net", tmp_path / "ws"
    nested = net / "2025" / "Lleida" / "3001621 CASTELLAR"
    nested.mkdir(parents=True)
    ws.mkdir()
    _write(nested / "A.01.pdf", "plànol", 1_700_000_000)
    monkeypatch.setattr(SW.config, "G3DT_NETWORK_PROJECTS", str(net))
    monkeypatch.setattr(SW.config, "G3DT_LOCAL_WORKSPACE", str(ws))
    SW.sync_to_workspace("2025/Lleida/3001621 CASTELLAR", allow_no_markers=True)
    _write(nested / "PENETROS.pdf", "camp")

    d = SW.sync_delta("2025/Lleida/3001621 CASTELLAR")

    assert d["leaf"] == "3001621 CASTELLAR"
    assert d["network_path"] == "2025/Lleida/3001621 CASTELLAR"
    assert d["new"] == ["PENETROS.pdf"]
    assert (ws / "3001621 CASTELLAR" / "PENETROS.pdf").exists()


def test_a_copy_lands_whole_or_not_at_all(net_and_ws):
    """Còpia a temporal + `os.replace`: mai un fitxer a mitges al workspace."""
    net_project, ws_project = net_and_ws
    _seed(net_project)
    _sync_first_time()
    _write(net_project / "gran.pdf", "y" * 5000)

    SW.sync_delta("4001612 BELL-LLOC")

    assert (ws_project / "gran.pdf").read_text(encoding="utf-8") == "y" * 5000
    assert [p.name for p in ws_project.glob(".sync-*")] == []


def test_sync_to_workspace_is_untouched(net_and_ws):
    """La Fase 11 afegeix una funció; no canvia la que ja hi havia."""
    net_project, _ = net_and_ws
    _seed(net_project)

    first = _sync_first_time()
    second = _sync_first_time()

    assert first["status"] == "synced"
    assert second["status"] == "skipped"
