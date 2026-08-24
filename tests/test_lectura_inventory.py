"""Fase 2 (via A, wizard headless) — tests de `automation/lectura/inventory.py`.

Fixtures: dues carpetes REALS de `reference-material/` ("4001612 BELL-LLOC" i
"3001631 RUBI") — excepció pactada per a tests (mai `/mnt/c`, mai dades sintètiques
per a l'enrutament real). `build_inventory` és read-only; `write_inventory` només
escriu a `tmp_path` (pytest), MAI dins de `reference-material/`.

Nota sobre "les 5 plantilles G3": l'enunciat de la Fase 2 conté dues instruccions
en tensió sobre l'Excel DPSH (`*_DPSH.xls`) — el llistat de "route python" l'hi
inclou com una de les 5 plantilles, però la decisió explícita ("route python+claude
NO ... decisió: una sola entrada amb route 'claude' i doc_type_hint dpsh_excel")
el treu d'aquesta llista. Es resol seguint la decisió explícita (més detallada i
tècnicament justificada: `g3_templates` ja el llegeix pel seu compte, fora de
l'inventari): les 4 plantilles restants (pressupost, fitxa de camp, comanda de
laboratori, PLAN_COST) són route "python"; l'Excel DPSH és route "claude" amb
`doc_type_hint == "dpsh_excel"`. Es testen totes 5 explícitament perquè quedi
documentat i verificable.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from automation.lectura.inventory import build_inventory, write_inventory  # noqa: E402

BELL_LLOC = PROJECT_ROOT / "reference-material" / "4001612 BELL-LLOC"
RUBI = PROJECT_ROOT / "reference-material" / "3001631 RUBI"


def _by_path(inv: dict) -> dict[str, dict]:
    return {f["path"]: f for f in inv["files"]}


# ---------------------------------------------------------------------------
# Estructura general
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("project", [BELL_LLOC, RUBI])
def test_no_file_without_route(project):
    inv = build_inventory(project)
    assert inv["files"], "l'inventari no pot ser buit sobre un projecte real"
    for f in inv["files"]:
        assert f["route"] in ("python", "claude", "skip"), f
        assert isinstance(f["priority"], int)
        assert f["path"] == f["path"].replace("\\", "/"), "separador ha de ser '/'"
        assert len(f["md5"]) == 32
        assert f["size"] >= 0
        assert f["mtime"]


@pytest.mark.parametrize("project", [BELL_LLOC, RUBI])
def test_top_level_keys(project):
    inv = build_inventory(project)
    assert set(inv.keys()) == {"generated", "project", "files", "duplicates"}
    assert inv["project"] == project.name


# ---------------------------------------------------------------------------
# Les 5 plantilles G3 de Bell-lloc (vegeu nota del docstring del mòdul)
# ---------------------------------------------------------------------------

def test_bell_lloc_g3_templates_routing():
    inv = build_inventory(BELL_LLOC)
    by_path = _by_path(inv)

    python_templates = {
        "25.0647/PRESSUPOST GEOTEC.BELL-LLOC.pdf": "pressupost_g3",
        "25.0647/DADES PER ANAR A CAMP_v1.xlsx": "fitxa_camp_g3",
        "comanda laboratori_4001612_BELL-LLOC.xls": "comanda_lab_g3",
        "25.0647/PLAN_COST_BELL-LLOC.xlsx": "plan_cost_g3",
    }
    for path, hint in python_templates.items():
        assert by_path[path]["route"] == "python", path
        assert by_path[path]["doc_type_hint"] == hint, path
        assert by_path[path]["priority"] == 0

    dpsh_excel = by_path["ANNEXES/4001612_DPSH.xls"]
    assert dpsh_excel["route"] == "claude"
    assert dpsh_excel["doc_type_hint"] == "dpsh_excel"
    assert dpsh_excel["priority"] > 0


def test_bell_lloc_cadastre_and_coordenades_are_python():
    inv = build_inventory(BELL_LLOC)
    by_path = _by_path(inv)
    for path in (
        "25.0647/4613172CG1141S0001SU-15.pdf",
        "25.0647/4613173CG1141S0001ZU-13.pdf",
    ):
        assert by_path[path]["route"] == "python"
        assert by_path[path]["doc_type_hint"] == "consulta_cadastre"
    coord = by_path["ANNEXES/ALTRES/COORDENADES.txt"]
    assert coord["route"] == "python"
    assert coord["doc_type_hint"] == "coordenades_gps"


# ---------------------------------------------------------------------------
# Documents-clau route claude, amb priority > 0
# ---------------------------------------------------------------------------

def test_bell_lloc_penetros_and_sondeig_annex_are_claude_with_priority():
    inv = build_inventory(BELL_LLOC)
    by_path = _by_path(inv)

    penetros = by_path["PENETROS.pdf"]
    assert penetros["route"] == "claude"
    assert penetros["priority"] > 0

    sondeig_annex = by_path["PDF/ANNEXES/4001612_sondeig.pdf"]
    assert sondeig_annex["route"] == "claude"
    assert sondeig_annex["priority"] > 0
    assert sondeig_annex["doc_type_hint"] == "annex_sondeig"


def test_rubi_penetros_is_claude_with_priority():
    # Rubí no té sondeig a rotació (no hi ha SONDEIG.pdf ni annex_sondeig al
    # corpus): només verifiquem PENETROS, que sí existeix ("3001631 - PENETROS.pdf").
    inv = build_inventory(RUBI)
    by_path = _by_path(inv)
    penetros = by_path["3001631 - PENETROS.pdf"]
    assert penetros["route"] == "claude"
    assert penetros["priority"] > 0
    assert penetros["doc_type_hint"] == "camp_penetros"


# ---------------------------------------------------------------------------
# Fotos → skip
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("project", [BELL_LLOC, RUBI])
def test_fotografies_dir_is_skip(project):
    inv = build_inventory(project)
    fotos = [f for f in inv["files"] if f["path"].startswith("FOTOGRAFIES/")]
    assert fotos, "el projecte hauria de tenir fitxers dins FOTOGRAFIES/"
    for f in fotos:
        assert f["route"] == "skip", f


# ---------------------------------------------------------------------------
# Volum de la cua claude
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("project", [BELL_LLOC, RUBI])
def test_claude_queue_size_in_expected_range(project):
    inv = build_inventory(project)
    n_claude = sum(1 for f in inv["files"] if f["route"] == "claude")
    assert 5 <= n_claude <= 20, n_claude


# ---------------------------------------------------------------------------
# Determinisme
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("project", [BELL_LLOC, RUBI])
def test_two_runs_are_identical_except_generated(project):
    inv1 = build_inventory(project)
    inv2 = build_inventory(project)
    inv1_no_ts = {k: v for k, v in inv1.items() if k != "generated"}
    inv2_no_ts = {k: v for k, v in inv2.items() if k != "generated"}
    assert inv1_no_ts == inv2_no_ts
    assert json.dumps(inv1_no_ts, sort_keys=True) == json.dumps(inv2_no_ts, sort_keys=True)


@pytest.mark.parametrize("project", [BELL_LLOC, RUBI])
def test_files_are_sorted_by_path(project):
    inv = build_inventory(project)
    paths = [f["path"] for f in inv["files"]]
    assert paths == sorted(paths)


# ---------------------------------------------------------------------------
# Duplicats (Bell-lloc: A.01.pdf arrel == 25.0647/A.01.pdf, mateix md5)
# ---------------------------------------------------------------------------

def test_bell_lloc_duplicate_a01_detected():
    inv = build_inventory(BELL_LLOC)
    flat = {p for group in inv["duplicates"] for p in group}
    assert "A.01.pdf" in flat
    assert "25.0647/A.01.pdf" in flat
    # "A.01 amb punts.pdf" té contingut diferent: no ha d'aparèixer al mateix grup
    group = next(g for g in inv["duplicates"] if "A.01.pdf" in g)
    assert "A.01 amb punts.pdf" not in group


def test_duplicates_only_include_non_skip_files():
    inv = build_inventory(BELL_LLOC)
    by_path = _by_path(inv)
    for group in inv["duplicates"]:
        for path in group:
            assert by_path[path]["route"] != "skip", path


# ---------------------------------------------------------------------------
# write_inventory (atòmic, mai dins reference-material/)
# ---------------------------------------------------------------------------

def test_write_inventory_creates_parseable_file(tmp_path):
    out_dir = tmp_path / "lectura"
    result_path = write_inventory(BELL_LLOC, out_dir)

    assert result_path == out_dir / "_inventory.json"
    assert result_path.exists()
    # Cap fitxer temporal orfe.
    assert list(out_dir.glob("*.tmp")) == []

    with result_path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    assert data["project"] == "4001612 BELL-LLOC"
    assert data["files"]
    assert any(f["route"] == "claude" for f in data["files"])


def test_write_inventory_does_not_touch_project_path(tmp_path):
    out_dir = tmp_path / "lectura"
    before = {p.relative_to(BELL_LLOC) for p in BELL_LLOC.rglob("*")}
    write_inventory(BELL_LLOC, out_dir)
    after = {p.relative_to(BELL_LLOC) for p in BELL_LLOC.rglob("*")}
    assert before == after, "write_inventory no ha d'escriure res dins project_path"
