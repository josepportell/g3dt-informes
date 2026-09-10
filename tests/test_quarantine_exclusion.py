"""La quarantena del delta-sync (`_esborrats/`) no l'ha de llegir cap escàner.

`sync_workspace.sync_delta` MOU a `<workspace>/_esborrats/` els fitxers que han
desaparegut de la xarxa (no els esborra: si la detecció s'erra, no s'ha perdut
res). Si un escàner hi entra, el document substituït —posem l'`A.01.pdf` vell de
l'arquitecte— torna a la lectura i competeix amb el nou.

Fixtures: còpies de fitxers REALS de `reference-material/4001612 BELL-LLOC` dins
de `tmp_path` (mai s'escriu a `reference-material/`).
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from automation import auto_result_cache, g3_templates, sync_workspace  # noqa: E402
from automation.concept_scout import scanner as scout_scanner  # noqa: E402
from automation.fileminer import _SKIP_DIRS as FILEMINER_SKIP_DIRS  # noqa: E402
from automation.fileminer import mine_project  # noqa: E402
from automation.lectura.inventory import build_inventory  # noqa: E402

BELL_LLOC = PROJECT_ROOT / "reference-material" / "4001612 BELL-LLOC"
_COORDENADES = BELL_LLOC / "ANNEXES" / "ALTRES" / "COORDENADES.txt"
_PLAN_COST = BELL_LLOC / "25.0647" / "PLAN_COST_BELL-LLOC.xlsx"

pytestmark = pytest.mark.skipif(not BELL_LLOC.exists(), reason="fixtures reference-material absents")

QUARANTINE = sync_workspace.DELETED_DIRNAME


@pytest.fixture
def project(tmp_path):
    """Projecte amb dos fitxers reals vius i les seves versions en quarantena."""
    root = tmp_path / "4001612 BELL-LLOC"
    (root / QUARANTINE).mkdir(parents=True)
    for src in (_COORDENADES, _PLAN_COST):
        shutil.copy2(src, root / src.name)
        shutil.copy2(src, root / QUARANTINE / src.name)
    return root


def test_quarantine_dirname_present_in_every_scanner():
    """Guarda contra un canvi de nom de `sync_workspace.DELETED_DIRNAME`."""
    assert QUARANTINE in g3_templates.EXCLUDE_DIRS
    assert QUARANTINE in FILEMINER_SKIP_DIRS
    assert QUARANTINE in scout_scanner._SKIP_DIRS
    assert QUARANTINE in auto_result_cache._EXCLUDED_DIRS


def test_inventory_routes_quarantine_to_skip(project):
    by_path = {f["path"]: f for f in build_inventory(project)["files"]}

    viu = by_path["COORDENADES.txt"]
    assert viu["route"] == "python"
    assert viu["doc_type_hint"] == "coordenades_gps"

    mort = by_path[f"{QUARANTINE}/COORDENADES.txt"]
    assert mort["route"] == "skip"
    assert mort["doc_type_hint"] == "exclos_carpeta"
    assert all(f["route"] == "skip" for f in by_path.values()
               if f["path"].startswith(f"{QUARANTINE}/"))


def test_g3_templates_does_not_read_quarantine(project):
    result = g3_templates.read_project(project)
    assert [d["source_path"] for d in result["documents"]] == ["PLAN_COST_BELL-LLOC.xlsx"]
    assert result["concepts"]["municipality"][0]["source"] == "PLAN_COST_BELL-LLOC.xlsx"


def test_fileminer_does_not_mine_quarantine(project):
    result = mine_project(project)
    assert result.signals, "el fitxer viu sí que ha de donar senyals"
    assert not [s for s in result.signals if QUARANTINE in s.source_file]


def test_concept_scout_does_not_enumerate_quarantine(project):
    paths = [e.path for e in scout_scanner.enumerate_project_files(project)]
    assert "COORDENADES.txt" in paths
    assert not [p for p in paths if p.startswith(f"{QUARANTINE}/")]


def test_auto_result_cache_fingerprint_ignores_quarantine(project):
    before = auto_result_cache.inputs_fingerprint(project)
    (project / QUARANTINE / "A.01.pdf").write_bytes(b"%PDF-1.4 antic\n")
    assert auto_result_cache.inputs_fingerprint(project) == before

    # Control: un fitxer nou FORA de la quarantena sí que ha de moure l'empremta.
    (project / "A.01.pdf").write_bytes(b"%PDF-1.4 nou\n")
    assert auto_result_cache.inputs_fingerprint(project) != before
