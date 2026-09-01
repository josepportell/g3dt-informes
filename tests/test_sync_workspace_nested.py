"""Tests de `sync_workspace` per a projectes anidats (2026-05-06).

Cobreix:
- `browse_network`: navegació, arrel, validació path traversal, errors.
- `sync_to_workspace`: paths plans (compat enrere), paths anidats, marker,
  col·lisió de leaf names amb hash, idempotència.
- `copyback_report`: lectura de marker, retorn a subcarpeta correcta.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from automation import sync_workspace


# --- Fixtures ---------------------------------------------------------------


@pytest.fixture
def fake_network(tmp_path: Path) -> Path:
    """Crea una arrel de xarxa simulada amb projectes plans i anidats.

    Estructura:
        net/
        ├── 4001612 BELL-LLOC/                       (arrel - compat enrere)
        │   └── PENETROS.pdf
        ├── grup-L1-01/
        │   ├── grup-L2-01/
        │   │   ├── 3001621 CASTELLAR/               (anidat 2 nivells)
        │   │   │   └── A.01.pdf
        │   │   └── 3001631 RUBI/
        │   └── grup-L2-02/
        │       └── 4001607 LINYOLA/
        ├── grup-L1-02/
        │   └── grup-L2-04/
        │       └── 4001612 BELL-LLOC/               (col·lisió de leaf!)
        │           └── PENETROS.pdf
        └── grup-buit/                                (sense projectes)
    """
    net = tmp_path / "net"
    net.mkdir()

    (net / "4001612 BELL-LLOC").mkdir()
    (net / "4001612 BELL-LLOC" / "PENETROS.pdf").write_text("flat")

    nested1 = net / "grup-L1-01" / "grup-L2-01" / "3001621 CASTELLAR"
    nested1.mkdir(parents=True)
    (nested1 / "A.01.pdf").write_text("nested1")

    (net / "grup-L1-01" / "grup-L2-01" / "3001631 RUBI").mkdir(parents=True)
    (net / "grup-L1-01" / "grup-L2-02" / "4001607 LINYOLA").mkdir(parents=True)

    collision = net / "grup-L1-02" / "grup-L2-04" / "4001612 BELL-LLOC"
    collision.mkdir(parents=True)
    (collision / "PENETROS.pdf").write_text("collision")

    (net / "grup-buit").mkdir()

    return net


@pytest.fixture
def configured(monkeypatch, fake_network: Path, tmp_path: Path):
    """Configura les variables de config perquè apuntin a directoris temporals."""
    workspace = tmp_path / "workspace"
    monkeypatch.setattr(sync_workspace.config, "G3DT_NETWORK_PROJECTS", str(fake_network))
    monkeypatch.setattr(sync_workspace.config, "G3DT_LOCAL_WORKSPACE", str(workspace))
    return workspace


# --- browse_network ---------------------------------------------------------


def test_browse_root_lists_first_level(configured: Path):
    result = sync_workspace.browse_network("")
    assert result["current_path"] == ""
    assert result["parent_path"] is None
    assert "4001612 BELL-LLOC" in result["subdirs"]
    assert "grup-L1-01" in result["subdirs"]
    assert "grup-L1-02" in result["subdirs"]
    assert "grup-buit" in result["subdirs"]


def test_browse_navigates_subfolder(configured: Path):
    result = sync_workspace.browse_network("grup-L1-01/grup-L2-01")
    assert result["current_path"] == "grup-L1-01/grup-L2-01"
    assert result["parent_path"] == "grup-L1-01"
    assert sorted(result["subdirs"]) == ["3001621 CASTELLAR", "3001631 RUBI"]


def test_browse_root_parent_is_none(configured: Path):
    result = sync_workspace.browse_network("")
    assert result["parent_path"] is None


def test_browse_first_level_parent_is_root(configured: Path):
    result = sync_workspace.browse_network("grup-L1-01")
    assert result["parent_path"] == ""


def test_browse_handles_windows_separators(configured: Path):
    result = sync_workspace.browse_network("grup-L1-01\\grup-L2-01")
    assert result["current_path"] == "grup-L1-01/grup-L2-01"


def test_browse_empty_folder_returns_empty_subdirs(configured: Path):
    result = sync_workspace.browse_network("grup-buit")
    assert result["subdirs"] == []


def test_browse_nonexistent_path_raises(configured: Path):
    with pytest.raises(FileNotFoundError):
        sync_workspace.browse_network("does-not-exist")


@pytest.mark.parametrize("malicious", [
    "..",
    "../escape",
    "grup-L1-01/../..",
    "/absolute",
    "grup-L1-01/./grup-L2-01",
])
def test_browse_rejects_path_traversal(configured: Path, malicious: str):
    with pytest.raises(ValueError):
        sync_workspace.browse_network(malicious)


def test_browse_when_workflow_disabled_raises(monkeypatch):
    monkeypatch.setattr(sync_workspace.config, "G3DT_NETWORK_PROJECTS", "")
    monkeypatch.setattr(sync_workspace.config, "G3DT_LOCAL_WORKSPACE", "")
    with pytest.raises(RuntimeError):
        sync_workspace.browse_network("")


# --- sync_to_workspace ------------------------------------------------------


def test_sync_flat_path_backwards_compat(configured: Path):
    """Path d'1 component (com l'API antiga): copia i posa marker amb el mateix nom."""
    result = sync_workspace.sync_to_workspace("4001612 BELL-LLOC")
    assert result["status"] == "synced"
    assert result["leaf"] == "4001612 BELL-LLOC"
    assert result["network_path"] == "4001612 BELL-LLOC"
    dst = configured / "4001612 BELL-LLOC"
    assert dst.is_dir()
    assert (dst / "PENETROS.pdf").is_file()
    assert (dst / sync_workspace._NETWORK_PATH_MARKER).read_text() == "4001612 BELL-LLOC"


def test_sync_nested_path_uses_leaf_as_workspace_name(configured: Path):
    rel = "grup-L1-01/grup-L2-01/3001621 CASTELLAR"
    result = sync_workspace.sync_to_workspace(rel)
    assert result["status"] == "synced"
    assert result["leaf"] == "3001621 CASTELLAR"
    assert result["network_path"] == rel
    dst = configured / "3001621 CASTELLAR"
    assert dst.is_dir()
    assert (dst / "A.01.pdf").is_file()
    assert (dst / sync_workspace._NETWORK_PATH_MARKER).read_text() == rel


def test_sync_idempotent_skip_with_correct_marker(configured: Path):
    rel = "grup-L1-01/grup-L2-01/3001621 CASTELLAR"
    sync_workspace.sync_to_workspace(rel)
    result = sync_workspace.sync_to_workspace(rel)
    assert result["status"] == "skipped"
    assert result["leaf"] == "3001621 CASTELLAR"


def test_sync_idempotent_when_called_with_leaf_only(configured: Path):
    """Després del primer sync amb path complet, la crida amb només el leaf
    (com fa /api/prefills/<leaf> internament) ha de fer skip sense tocar xarxa."""
    rel = "grup-L1-01/grup-L2-01/3001621 CASTELLAR"
    sync_workspace.sync_to_workspace(rel)
    result = sync_workspace.sync_to_workspace("3001621 CASTELLAR")
    assert result["status"] == "skipped"
    assert result["network_path"] == rel  # encara apunta al path original anidat


def test_sync_collision_uses_hash_suffix(configured: Path):
    """Dos projectes amb el mateix leaf però paths diferents → segon obté suffix."""
    flat = "4001612 BELL-LLOC"
    nested = "grup-L1-02/grup-L2-04/4001612 BELL-LLOC"

    res1 = sync_workspace.sync_to_workspace(flat)
    res2 = sync_workspace.sync_to_workspace(nested)

    assert res1["leaf"] == "4001612 BELL-LLOC"
    assert res2["leaf"].startswith("4001612 BELL-LLOC__")
    assert res2["leaf"] != res1["leaf"]
    # Tots dos workspaces existeixen i tenen markers diferents
    assert (configured / res1["leaf"] / sync_workspace._NETWORK_PATH_MARKER).read_text() == flat
    assert (configured / res2["leaf"] / sync_workspace._NETWORK_PATH_MARKER).read_text() == nested


def test_sync_force_recopies(configured: Path):
    rel = "grup-L1-01/grup-L2-01/3001621 CASTELLAR"
    sync_workspace.sync_to_workspace(rel)
    # Modifica el workspace per detectar la re-còpia
    dst = configured / "3001621 CASTELLAR"
    (dst / "user_modified.txt").write_text("touched")

    result = sync_workspace.sync_to_workspace(rel, force=True)
    assert result["status"] == "synced"
    # El fitxer modificat no s'ha esborrat (copytree dirs_exist_ok preserva)
    # però els fitxers originals s'han re-copiat
    assert (dst / "A.01.pdf").is_file()


def test_sync_invalid_path_returns_error(configured: Path):
    result = sync_workspace.sync_to_workspace("../escape")
    assert result["status"] == "error"
    assert "invalid path" in result["error"].lower()


def test_sync_nonexistent_returns_error(configured: Path):
    result = sync_workspace.sync_to_workspace("does-not-exist")
    assert result["status"] == "error"


# --- Marcador = còpia completa (P0) -----------------------------------------
#
# El marcador només s'escriu quan `copytree` ha acabat. Si la primera
# sincronització d'un projecte de diversos GB mor al 40% (procés mort, SMB
# caigut), el destí existeix SENSE marcador. El camí de salt comprovava només
# `dst.exists()` i tot seguit «reparava» el marcador que faltava: el salt
# passava a ser permanent i el wizard generava informes amb PENETROS/SONDEIG
# absents, en silenci.


def test_an_interrupted_first_sync_is_redone_not_skipped(configured: Path, fake_network: Path):
    rel = "4001612 BELL-LLOC"
    net_project = fake_network / rel
    (net_project / "SONDEIG.pdf").write_text("el que faltava")

    # Primera sincronització morta al 40%: hi ha carpeta i un fitxer, cap marcador.
    dst = configured / rel
    dst.mkdir(parents=True)
    (dst / "PENETROS.pdf").write_text("flat")

    result = sync_workspace.sync_to_workspace(rel)

    assert result["status"] == "synced"
    assert (dst / "SONDEIG.pdf").read_text() == "el que faltava"
    assert (dst / sync_workspace._NETWORK_PATH_MARKER).read_text() == rel


def test_the_skip_path_never_invents_the_missing_marker(configured: Path, fake_network: Path):
    """Si el marcador falta, el destí és incomplet. Escriure'l sense copiar era
    convertir una còpia a mitges en 'ja el tens'."""
    rel = "4001612 BELL-LLOC"
    dst = configured / rel
    dst.mkdir(parents=True)

    calls: list[str] = []
    real_copytree = sync_workspace.shutil.copytree

    def spy(src, dest, **kw):
        calls.append(str(dest))
        return real_copytree(src, dest, **kw)

    sync_workspace.shutil.copytree = spy
    try:
        result = sync_workspace.sync_to_workspace(rel)
    finally:
        sync_workspace.shutil.copytree = real_copytree

    assert result["status"] == "synced"
    assert calls == [str(dst)], "el marcador no es pot escriure sense haver copiat"


def test_the_marker_is_written_atomically(configured: Path):
    rel = "grup-L1-01/grup-L2-01/3001621 CASTELLAR"
    sync_workspace.sync_to_workspace(rel)

    dst = configured / "3001621 CASTELLAR"
    leftovers = [p.name for p in dst.glob(f"{sync_workspace._NETWORK_PATH_MARKER}.*")]
    assert leftovers == []
    assert (dst / sync_workspace._NETWORK_PATH_MARKER).read_text() == rel


def test_a_workspace_belonging_to_another_project_is_an_error_not_a_merge(
    configured: Path, monkeypatch
):
    """Defensa: avui `_resolve_workspace_leaf` desambigua amb suffix i aquí no
    s'hi arriba mai. Si algun dia deixés de fer-ho, el destí NO es pot barrejar
    ni el marcador reescriure — l'informe tornaria a la carpeta equivocada."""
    nested = "grup-L1-02/grup-L2-04/4001612 BELL-LLOC"
    dst = configured / "4001612 BELL-LLOC"
    dst.mkdir(parents=True)
    (dst / sync_workspace._NETWORK_PATH_MARKER).write_text("4001612 BELL-LLOC")
    monkeypatch.setattr(sync_workspace, "_resolve_workspace_leaf", lambda rel: "4001612 BELL-LLOC")

    result = sync_workspace.sync_to_workspace(nested)

    assert result["status"] == "error"
    assert result["code"] == "workspace_mismatch"
    assert (dst / sync_workspace._NETWORK_PATH_MARKER).read_text() == "4001612 BELL-LLOC"


# --- copyback_report --------------------------------------------------------


def test_copyback_uses_marker_for_nested(configured: Path, tmp_path: Path):
    rel = "grup-L1-01/grup-L2-01/3001621 CASTELLAR"
    sync_workspace.sync_to_workspace(rel)

    # Simula generació de .docx
    docx = tmp_path / "informe.docx"
    docx.write_text("fake docx content")

    result = sync_workspace.copyback_report("3001621 CASTELLAR", docx)
    assert result["status"] == "copied"

    expected = sync_workspace.network_root() / "grup-L1-01" / "grup-L2-01" / "3001621 CASTELLAR" / "informe.docx"
    assert expected.is_file()
    assert expected.read_text() == "fake docx content"


def test_copyback_compat_with_no_marker(configured: Path, tmp_path: Path):
    """Workspace creat manualment sense marker (compat enrere): assumim path plà."""
    leaf = "4001612 BELL-LLOC"
    workspace = configured / leaf
    workspace.mkdir(parents=True)
    # NO escrivim marker

    docx = tmp_path / "old.docx"
    docx.write_text("legacy")

    result = sync_workspace.copyback_report(leaf, docx)
    assert result["status"] == "copied"
    expected = sync_workspace.network_root() / leaf / "old.docx"
    assert expected.is_file()


def test_copyback_collision_workspace_returns_to_correct_subfolder(configured: Path, tmp_path: Path):
    flat = "4001612 BELL-LLOC"
    nested = "grup-L1-02/grup-L2-04/4001612 BELL-LLOC"
    sync_workspace.sync_to_workspace(flat)
    res2 = sync_workspace.sync_to_workspace(nested)
    nested_leaf = res2["leaf"]

    docx = tmp_path / "report.docx"
    docx.write_text("nested copy")

    result = sync_workspace.copyback_report(nested_leaf, docx)
    assert result["status"] == "copied"

    # Ha de tornar a la carpeta anidada, NO a la flat
    expected_nested = sync_workspace.network_root() / "grup-L1-02" / "grup-L2-04" / "4001612 BELL-LLOC" / "report.docx"
    expected_flat = sync_workspace.network_root() / "4001612 BELL-LLOC" / "report.docx"
    assert expected_nested.is_file()
    assert not expected_flat.exists()


# --- Validació projecte (multi_project_container, not_a_project) -----------


def test_sync_root_rejected_as_container(configured: Path):
    """Clic a l'arrel: hard block, sense override possible."""
    result = sync_workspace.sync_to_workspace("4001612 BELL-LLOC")  # OK first to set up
    assert result["status"] == "synced"
    # Ara provem amb un path que apunta a un grup intermedi
    # (en aquest fixture l'arrel només la podem testar amb sync_to_workspace
    # via un path d'1 component que apunti a grup-L1-01 — que té subdirs però
    # no és projecte)
    result = sync_workspace.sync_to_workspace("grup-L1-01")
    assert result["status"] == "error"
    assert result["code"] == "multi_project_container"


def test_sync_intermediate_group_rejected(configured: Path):
    """Clic a grup-L1-02 (té subdir grup-L2-04 que té projectes): hard block."""
    result = sync_workspace.sync_to_workspace("grup-L1-02")
    assert result["status"] == "error"
    assert result["code"] == "multi_project_container"


def test_sync_no_markers_soft_blocked(configured: Path, fake_network: Path):
    """Carpeta sense markers ni subdirs: soft block, override possible."""
    # Crea un projecte buit (sense markers, sense subdirs)
    empty_project = fake_network / "projecte-buit"
    empty_project.mkdir()
    (empty_project / "notes.txt").write_text("just notes")

    result = sync_workspace.sync_to_workspace("projecte-buit")
    assert result["status"] == "error"
    assert result["code"] == "not_a_project"

    # Override: amb allow_no_markers funciona
    result = sync_workspace.sync_to_workspace("projecte-buit", allow_no_markers=True)
    assert result["status"] == "synced"
    assert result["leaf"] == "projecte-buit"


def test_sync_valid_project_with_markers_passes(configured: Path):
    """Projecte amb markers passa la validació sense override."""
    result = sync_workspace.sync_to_workspace("4001612 BELL-LLOC")
    assert result["status"] == "synced"


def test_sync_dpsh_in_annexes_recognized(configured: Path, fake_network: Path):
    """DPSH dins ANNEXES/ es reconeix com a marker de projecte."""
    proj = fake_network / "4001999 PROVA"
    (proj / "ANNEXES").mkdir(parents=True)
    (proj / "ANNEXES" / "4001999_DPSH.xls").write_text("dpsh data")

    result = sync_workspace.sync_to_workspace("4001999 PROVA")
    assert result["status"] == "synced"


def test_sync_dpsh_in_anexos_castellano_recognized(configured: Path, fake_network: Path):
    """DPSH dins ANEXOS/ (variant castellana) també es reconeix."""
    proj = fake_network / "4002000 PROVA-ES"
    (proj / "ANEXOS").mkdir(parents=True)
    (proj / "ANEXOS" / "4002000_DPSH.xlsx").write_text("dpsh data")

    result = sync_workspace.sync_to_workspace("4002000 PROVA-ES")
    assert result["status"] == "synced"


def test_sync_pdf_pattern_case_insensitive(configured: Path, fake_network: Path):
    """Els patrons de PDF accepten majúscules/minúscules barrejades."""
    proj = fake_network / "test-case"
    proj.mkdir()
    (proj / "Penetros.PDF").write_text("data")  # Mixed case

    result = sync_workspace.sync_to_workspace("test-case")
    assert result["status"] == "synced"


def test_looks_like_project_helpers(fake_network: Path):
    """Test directe del helper _looks_like_project."""
    # Projecte amb PENETROS.pdf
    assert sync_workspace._looks_like_project(fake_network / "4001612 BELL-LLOC")
    # Projecte amb A.01.pdf
    assert sync_workspace._looks_like_project(
        fake_network / "grup-L1-01" / "grup-L2-01" / "3001621 CASTELLAR"
    )
    # Sense markers
    assert not sync_workspace._looks_like_project(
        fake_network / "grup-L1-01" / "grup-L2-01" / "3001631 RUBI"
    )
    # Carpeta buida
    assert not sync_workspace._looks_like_project(fake_network / "grup-buit")
    # Path inexistent
    assert not sync_workspace._looks_like_project(fake_network / "no-existeix")


# --- resolve_network_path (helper de seguretat) ----------------------------


def test_resolve_path_traversal_blocked(configured: Path):
    with pytest.raises(ValueError):
        sync_workspace.resolve_network_path("../escape")


def test_resolve_handles_special_chars(configured: Path, tmp_path: Path):
    """Noms amb espais, accents, ñ, ç."""
    special = sync_workspace.network_root() / "Projecte amb àccents ñ ç"
    special.mkdir()
    resolved = sync_workspace.resolve_network_path("Projecte amb àccents ñ ç")
    assert resolved == special
