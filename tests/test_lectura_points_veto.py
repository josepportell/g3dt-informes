"""Tests del veto pels punts de camp (peça 5 del disseny d'adreces).

Vegeu `docs/DISSENY-ADRECES-I-MUNICIPI-2026-09-01.md` §6. Formulació confirmada pel Josep:

    punts FORA  -> el valor no s'omple, i el motiu es veu
    punts DINS  -> corrobora (nota informativa, com sempre)
    CAP punt    -> neutre, com abans

La regla només pot **vetar**, mai **exigir**: 4 dels 8 projectes del corpus no tenen fitxer de
coordenades. 0 xarxa.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

pytest.importorskip("shapely")

from automation.lectura import cadastre_reader as R  # noqa: E402
from automation.lectura.consolidate import decide  # noqa: E402

#: Quadrat de 100 m de costat amb el cantó a (400000, 4600000), en UTM 25831.
_SQUARE = [(400000.0, 4600000.0), (400100.0, 4600000.0), (400100.0, 4600100.0),
           (400000.0, 4600100.0), (400000.0, 4600000.0)]


def _project_with_points(tmp_path: Path, points: list[tuple[float, float]]) -> Path:
    proj = tmp_path / "9999999 PROVA"
    (proj / "ANNEXES" / "ALTRES").mkdir(parents=True)
    # Format real (`parse_coordenades`): capçalera, i per punt una línia `P-N` i una `x ; y ; z`.
    body = "Coordenades UTM (X);(Y);(Z);\n" + "\n".join(
        f"P-{i + 1}\n{x} ; {y} ; 100.0" for i, (x, y) in enumerate(points)
    )
    (proj / "ANNEXES" / "ALTRES" / "COORDENADES.txt").write_text(body, encoding="utf-8")
    return proj


@pytest.fixture
def wired(monkeypatch, tmp_path):
    """Adreça, municipi, via i portal ja resolts: només queda la geometria."""
    monkeypatch.setattr(R, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(R, "_consulta_via_all_streets", lambda p, m: [("ARBRELLS DELS", "CL", "1")])
    monkeypatch.setattr(R, "_consulta_via", lambda *a, **k: ("ARBRELLS DELS", "CL", "1"))
    monkeypatch.setattr(
        R, "resolve_portal",
        lambda *a, **k: [R.ParcelHit(rc="AAAA1111AA0001", pnp="18", plp="A")],
    )
    monkeypatch.setattr(R, "parcel_area_and_polygon", lambda rc: (441, list(_SQUARE)))


def _decided() -> dict[str, dict]:
    return {
        "street_address": {"estat": "segur", "value": "Carrer Arbrells, 18A"},
        "municipality": {"estat": "segur", "value": "Castellar del Vallès"},
    }


def _signals(key: str, proj: Path) -> list:
    return R.cadastre_portal_signals(key, _decided(), proj)


# ------------------------------------------------------------------ PointsCheck


@pytest.mark.parametrize(
    "check,veta,per_que",
    [
        (R.PointsCheck(inside=0, total=5, farthest_m=703.0), True, "cap dins i lluny"),
        (R.PointsCheck(inside=0, total=1, farthest_m=400.0), True, "un sol punt també val"),
        (R.PointsCheck(inside=5, total=5, farthest_m=0.0), False, "tots dins"),
        (R.PointsCheck(inside=1, total=5, farthest_m=300.0), False, "algun dins: no es veta"),
        (R.PointsCheck(inside=0, total=3, farthest_m=4.0), False, "deriva de GPS, no una altra parcel·la"),
        (R.PointsCheck(inside=0, total=0, farthest_m=0.0), False, "sense punts no diu res"),
    ],
)
def test_quan_veta(check: R.PointsCheck, veta: bool, per_que: str) -> None:
    assert check.vetoes is veta, per_que


def test_la_tolerancia_es_de_gps_no_de_parcel_la() -> None:
    """10 m: molt per sobre de la deriva del GPS de camp (~0,6 m) i molt per sota de la
    distància a una parcel·la veïna (~20 m per a 441 m²)."""
    assert 1.0 < R._MAX_POINT_DRIFT_M < 20.0


# ------------------------------------------------------------------------ veto


def test_punts_fora_no_omplen_la_superficie(wired, tmp_path) -> None:
    proj = _project_with_points(tmp_path, [(400500.0, 4600500.0), (400600.0, 4600600.0)])
    sigs = _signals("superficie_parcela", proj)
    assert [s.value for s in sigs] == [None]


def test_el_motiu_arriba_a_la_cel_la_que_veu_l_eva(wired, tmp_path) -> None:
    """El canal és `decide()`: recull el `note` dels senyals sense valor a la cel·la
    `no_trobat`, i el popup del wizard el pinta (`review.html`, branca `no_trobat`)."""
    proj = _project_with_points(tmp_path, [(400500.0, 4600500.0)])
    cell = decide(_signals("superficie_parcela", proj), sources_checked=["Cadastre"],
                  field_name="superficie_parcela")
    assert cell["estat"] == "no_trobat" and cell["value"] is None
    nota = cell["note"]
    assert "punts d'assaig" in nota and "FORA" in nota
    assert "0/1 dins" in nota and "m)" in nota          # el recompte i la distància concrets
    assert "COORDENADES.txt" in nota                     # on ha de mirar


def test_el_motiu_diu_de_quin_camp_parla(wired, tmp_path) -> None:
    proj = _project_with_points(tmp_path, [(400500.0, 4600500.0)])
    assert "la superfície" in _signals("superficie_parcela", proj)[0].note
    assert "la referència cadastral" in _signals("referencia_catastral", proj)[0].note


def test_punts_dins_corroboren_i_omplen(wired, tmp_path) -> None:
    proj = _project_with_points(tmp_path, [(400050.0, 4600050.0), (400060.0, 4600040.0)])
    sigs = _signals("superficie_parcela", proj)
    assert [s.value for s in sigs] == ["441"]
    assert "2/2 punts d'assaig dins" in sigs[0].note


def test_sense_fitxer_de_coordenades_res_no_canvia(wired, tmp_path) -> None:
    """La regla només pot vetar, mai exigir: 4 dels 8 projectes del corpus no en tenen."""
    proj = tmp_path / "9999999 SENSE PUNTS"
    proj.mkdir()
    sigs = _signals("superficie_parcela", proj)
    assert [s.value for s in sigs] == ["441"]
    assert "punts d'assaig" not in (sigs[0].note or "")


def test_un_sol_punt_ja_veta(wired, tmp_path) -> None:
    """Un punt a 400 m és igual de concloent que cinc (Bell-lloc i Alcoletge en tenen un)."""
    proj = _project_with_points(tmp_path, [(400500.0, 4600500.0)])
    assert [s.value for s in _signals("superficie_parcela", proj)] == [None]


def test_un_punt_just_a_fora_no_veta(wired, tmp_path) -> None:
    """A 5 m del límit és deriva de GPS/cadastre, no una altra parcel·la."""
    proj = _project_with_points(tmp_path, [(400105.0, 4600050.0)])
    sigs = _signals("superficie_parcela", proj)
    assert [s.value for s in sigs] == ["441"]
