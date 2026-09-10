"""Fase 13(a) — `AutoExtractionResult` persistit a disc.

Acceptació de la fila 13 del pla (`docs/DISSENY-ANNEX-TRES-BOTONS-JOBS-\
NOTIFICACIONS-2026-08-24.md` §10): «2a càrrega sense xarxa ni Groq → prefills
iguals; invalidació per `inputs_md5`».

El que es cobreix aquí:

1. **Empremta** — quins fitxers compten i quins no (les sortides del propi
   pipeline no poden invalidar la cache que acaben d'omplir), i que el
   contingut mana sobre l'mtime (el delta-sync de la Fase 11 recopiarà fitxers
   sense canviar-los).
2. **Round-trip** — els objectes niats (`DPSHData`, `FileMapping`,
   `MiningResult`, `ConceptMap`, …) tornen com el que eren, no com a dicts.
3. **Les quatre barreres d'invalidació** — empremta, TTL, `CACHE_VERSION`,
   fitxer il·legible.
4. **Mai llançar** — una cache que peta no pot deixar l'Eva sense prefills.
5. **`wizard_service._auto_extract_cached`** — l'embolcall: en un encert NO es
   crida `auto_extract` (cap crida de xarxa ni de Groq) i els events de progrés
   es reprodueixen.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from automation import auto_result_cache as arc


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Carpeta de projecte mínima amb entrades i sortides del pipeline."""
    p = tmp_path / "3001621 CASTELLAR"
    (p / "ANNEXES").mkdir(parents=True)
    (p / "validation").mkdir()
    (p / "PENETROS.pdf").write_bytes(b"%PDF-1.4 penetros")
    (p / "ANNEXES" / "3001621_DPSH.xls").write_bytes(b"excel-bytes")
    (p / "COORDENADES.txt").write_text("X: 1\nY: 2\n", encoding="utf-8")
    # Sortides del pipeline (no compten com a entrada)
    (p / "file_mapping.json").write_text('{"roles": {}}', encoding="utf-8")
    (p / "validation" / "concept_map.json").write_text("{}", encoding="utf-8")
    return p


def _result(**kwargs):
    from automation.auto_extractor import AutoExtractionResult
    return AutoExtractionResult(**kwargs)


def _rich_result():
    """Resultat amb un exemplar de cada tipus niat que la cache ha de tornar viu."""
    from automation.concept_scout.models import ConceptMap, ConceptSource, FileEntry
    from automation.content_discovery import ContentDiscoveryResult, DiscoveredItem
    from automation.dpsh_extractor import DPSHData, DPSHReading, DPSHTest
    from automation.file_scanner import FileMapping, FileRole, IgnoredFile
    from automation.fileminer.models import MiningResult, Signal, SignalType
    from automation.lab_extractor import LabResults, LabTestResult

    return _result(
        prefills={"client_name": "GRUP ALMA", "utm_x": 419876.0, "num_plantes": 2},
        sources={"client_name": "fileminer:PRESSUPOST.pdf", "utm_x": "COORDENADES.txt"},
        dpsh_data=DPSHData(
            expedient="3001621",
            source_file="ANNEXES/3001621_DPSH.xls",
            tests=[DPSHTest(
                test_id="P-1",
                correction_factor=0.83,
                refusal_depth_annotated=-4.2,
                readings=[
                    DPSHReading(depth_m=-0.2, n20=6, nb=7.2),
                    DPSHReading(depth_m=-0.4, n20=11, nb=13.3, water_level=True, soil_level="N1"),
                ],
            )],
        ),
        lab_results=LabResults(
            sulfate_mg_kg=118.0,
            source_file="4687-GTL-25.pdf",
            lab_testing_company="TPS",
            tests=[LabTestResult(type="sulfats", sample_id="SPT-1", value=118.0, unit="mg/kg")],
        ),
        file_mapping=FileMapping(
            roles={"dpsh_excel": FileRole(path="ANNEXES/3001621_DPSH.xls", confidence="alta", detection="filename")},
            ignored=[IgnoredFile(path="Thumbs.db", reason="soroll")],
            unassigned=["misteri.pdf"],
            deep_folder_files={"ALTRES/x.pdf": {"role": "altre"}},
        ),
        content_discovery=ContentDiscoveryResult(
            items=[DiscoveredItem(category="utm_coordinates", source_file="COORDENADES.txt",
                                  confidence="high", data={"utm_x": 419876.0})],
            files_scanned=56, files_skipped=3, duration_seconds=1.25,
        ),
        mining_result=MiningResult(
            project_path="/x/3001621",
            files_mined=12,
            signals=[Signal(type=SignalType.TEXT, label="CLIENT", value="GRUP ALMA",
                            source_file="PRESSUPOST.pdf", confidence=0.9)],
        ),
        mining_alternatives={"client_name": [{"value": "ALMA SL", "source": "correu.msg", "confidence": 0.8}]},
        concept_map=ConceptMap(
            metadata={"project": "3001621"},
            file_inventory=[FileEntry(path="PENETROS.pdf", type="pdf_scanned", size_kb=1600)],
            concept_sources={"client_name": [ConceptSource(file="PRESSUPOST.pdf", confidence=0.9, page=1)]},
            unresolved=["radon"],
        ),
        steps_completed=["Fase 0: FileScanner"],
        steps_skipped=[("Fase 2", "sense PDF de laboratori")],
        duration_seconds=43.2,
        deep_folder_promoted=[("altre", "ALTRES/x.pdf")],
    )


# ---------------------------------------------------------------------------
# 1. Empremta dels fitxers d'entrada
# ---------------------------------------------------------------------------

def test_fingerprint_is_stable_between_calls(project: Path):
    assert arc.inputs_fingerprint(project) == arc.inputs_fingerprint(project)


def test_fingerprint_changes_when_an_input_changes(project: Path):
    before = arc.inputs_fingerprint(project)
    (project / "PENETROS.pdf").write_bytes(b"%PDF-1.4 penetros REVISAT")
    assert arc.inputs_fingerprint(project) != before


def test_fingerprint_changes_when_an_input_is_added_or_removed(project: Path):
    before = arc.inputs_fingerprint(project)
    (project / "ANNEXES" / "3001621_sondeig.pdf").write_bytes(b"nou annex")
    after_add = arc.inputs_fingerprint(project)
    assert after_add != before
    (project / "PENETROS.pdf").unlink()
    assert arc.inputs_fingerprint(project) not in (before, after_add)


def test_fingerprint_ignores_pipeline_outputs(project: Path):
    """Si les pròpies sortides comptessin, la cache s'invalidaria a si mateixa.

    Comprovat empíricament sobre Castellar (snapshot md5 de 173 fitxers abans i
    després d'un `auto_extract`): l'únic fitxer que canvia fora de `validation/`
    és `file_mapping.json`.
    """
    before = arc.inputs_fingerprint(project)
    (project / "file_mapping.json").write_text('{"roles": {"planol": {}}}', encoding="utf-8")
    (project / "validation" / "concept_map.json").write_text('{"tot": "nou"}', encoding="utf-8")
    (project / "validation" / "dpsh_extracted.json").write_text("{}", encoding="utf-8")
    (project / "validation" / "_auto_result.json").write_text("{}", encoding="utf-8")
    (project / "_user_data_prev.json").write_text('{"utm_x": 9}', encoding="utf-8")
    (project / "~$comanda.xls").write_bytes(b"lock d'office")
    assert arc.inputs_fingerprint(project) == before


def test_fingerprint_ignores_mtime_when_content_is_identical(project: Path):
    """El delta-sync (Fase 11) recopiarà fitxers de la xarxa: una còpia canvia
    l'mtime sense canviar res. Amb `mida+mtime` la cache no encertaria mai."""
    before = arc.inputs_fingerprint(project)
    target = project / "PENETROS.pdf"
    data = target.read_bytes()
    target.unlink()
    target.write_bytes(data)
    import os
    os.utime(target, (1_600_000_000, 1_600_000_000))
    assert arc.inputs_fingerprint(project) == before


def test_fingerprint_tracks_user_data_keys_phase3_reads(project: Path):
    """`user_data.json` no compta sencer (l'Eva hi desa 300 camps) però sí les
    claus que la Fase 3 llegeix per anar a ICGC/Cadastre."""
    ud = project / "user_data.json"
    ud.write_text(json.dumps({"utm_x": 419876, "notes_internes": "hola"}), encoding="utf-8")
    before = arc.inputs_fingerprint(project)

    ud.write_text(json.dumps({"utm_x": 419876, "notes_internes": "adéu"}), encoding="utf-8")
    assert arc.inputs_fingerprint(project) == before, "un camp irrellevant no pot invalidar"

    ud.write_text(json.dumps({"utm_x": 999999, "notes_internes": "adéu"}), encoding="utf-8")
    assert arc.inputs_fingerprint(project) != before, "moure les UTM sí que ha d'invalidar"


# ---------------------------------------------------------------------------
# 2. Round-trip
# ---------------------------------------------------------------------------

def test_roundtrip_rebuilds_every_nested_type(project: Path):
    from automation.concept_scout.models import ConceptMap
    from automation.content_discovery import ContentDiscoveryResult
    from automation.dpsh_extractor import DPSHData, DPSHReading, DPSHTest
    from automation.file_scanner import FileMapping, FileRole
    from automation.fileminer.models import MiningResult, Signal
    from automation.lab_extractor import LabResults

    original = _rich_result()
    assert arc.save(project, original) is not None
    cached = arc.load(project)
    assert cached is not None
    r = cached.result

    assert arc.serialize(r) == arc.serialize(original)

    assert isinstance(r.dpsh_data, DPSHData)
    assert isinstance(r.dpsh_data.tests[0], DPSHTest)
    assert isinstance(r.dpsh_data.tests[0].readings[0], DPSHReading)
    assert isinstance(r.lab_results, LabResults)
    assert isinstance(r.file_mapping, FileMapping)
    assert isinstance(r.file_mapping.roles["dpsh_excel"], FileRole)
    assert isinstance(r.content_discovery, ContentDiscoveryResult)
    assert isinstance(r.mining_result, MiningResult)
    assert isinstance(r.mining_result.signals[0], Signal)
    assert isinstance(r.concept_map, ConceptMap)

    # Les propietats calculades han de tornar a funcionar (el wizard les usa)
    assert r.dpsh_data.num_tests == 1
    assert r.dpsh_data.tests[0].readings[1].water_level is True
    assert r.dpsh_data.tests[0].refusal_depth_annotated == -4.2
    assert r.file_mapping.roles["dpsh_excel"].path == "ANNEXES/3001621_DPSH.xls"
    assert r.concept_map.concept_sources["client_name"][0].page == 1
    assert r.steps_skipped == [("Fase 2", "sense PDF de laboratori")]
    assert r.deep_folder_promoted == [("altre", "ALTRES/x.pdf")]


def test_mining_alternatives_stay_plain_dicts(project: Path):
    """El comentari del camp diu `[Signal, ...]` però `auto_extractor.py` L.634
    i L.748 hi posen dicts plans. Ho va destapar el round-trip d'aquesta fase."""
    arc.save(project, _rich_result())
    r = arc.load(project).result
    alt = r.mining_alternatives["client_name"][0]
    assert isinstance(alt, dict)
    assert alt == {"value": "ALMA SL", "source": "correu.msg", "confidence": 0.8}


def test_events_are_replayed_verbatim(project: Path):
    events = [("step", {"step": "scan", "status": "done"}), ("file", {"name": "A.01.pdf"})]
    arc.save(project, _result(), events)
    assert arc.load(project).events == events


# ---------------------------------------------------------------------------
# 3. Les quatre barreres d'invalidació
# ---------------------------------------------------------------------------

def test_miss_when_an_input_changed(project: Path):
    arc.save(project, _result(prefills={"a": 1}))
    assert arc.load(project) is not None
    (project / "PENETROS.pdf").write_bytes(b"%PDF-1.4 versio nova del camp")
    assert arc.load(project) is None


def test_miss_when_expired(project: Path, monkeypatch: pytest.MonkeyPatch):
    arc.save(project, _result())
    path = arc.cache_path(project)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["saved_at"] = (datetime.now() - timedelta(days=arc.TTL_DAYS + 1)).isoformat(timespec="seconds")
    path.write_text(json.dumps(data), encoding="utf-8")
    assert arc.load(project) is None, "els camps HTTP (ICGC/Cadastre) no poden viure per sempre"


def test_hit_just_inside_the_ttl(project: Path):
    arc.save(project, _result(prefills={"a": 1}))
    path = arc.cache_path(project)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["saved_at"] = (datetime.now() - timedelta(days=arc.TTL_DAYS - 1)).isoformat(timespec="seconds")
    path.write_text(json.dumps(data), encoding="utf-8")
    assert arc.load(project) is not None


def test_miss_on_future_timestamp(project: Path):
    """Rellotge mogut enrere: no confiar en una entrada del futur."""
    arc.save(project, _result())
    path = arc.cache_path(project)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["saved_at"] = (datetime.now() + timedelta(days=2)).isoformat(timespec="seconds")
    path.write_text(json.dumps(data), encoding="utf-8")
    assert arc.load(project) is None


def test_miss_on_old_cache_version(project: Path):
    arc.save(project, _result())
    path = arc.cache_path(project)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["cache_version"] = arc.CACHE_VERSION - 1
    path.write_text(json.dumps(data), encoding="utf-8")
    assert arc.load(project) is None


@pytest.mark.parametrize("blob", ["{ no és json", "[]", '{"cache_version": 1}'])
def test_miss_on_unusable_file(project: Path, blob: str):
    arc.cache_path(project).write_text(blob, encoding="utf-8")
    assert arc.load(project) is None


def test_miss_when_absent(project: Path):
    assert arc.load(project) is None


def test_invalidate_is_idempotent(project: Path):
    arc.save(project, _result())
    arc.invalidate(project)
    arc.invalidate(project)
    assert not arc.cache_path(project).exists()
    assert arc.load(project) is None


# ---------------------------------------------------------------------------
# 4. Mai llançar / desactivable
# ---------------------------------------------------------------------------

def test_save_refuses_unserializable_result_without_raising(project: Path):
    class Opac:
        pass

    assert arc.save(project, _result(dpsh_data=Opac())) is None
    assert not arc.cache_path(project).exists(), "millor cap cache que una de degradada"


def test_load_survives_a_result_it_cannot_rebuild(project: Path):
    arc.save(project, _result(prefills={"a": 1}))
    path = arc.cache_path(project)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["result"]["dpsh_data"] = {"camp_inventat": 1}
    path.write_text(json.dumps(data), encoding="utf-8")
    assert arc.load(project) is None


def test_save_leaves_no_temporary_file(project: Path):
    arc.save(project, _rich_result())
    leftovers = [p.name for p in (project / "validation").iterdir() if p.name.startswith("._auto_result-")]
    assert leftovers == []


def test_env_switches_disable_it(project: Path, monkeypatch: pytest.MonkeyPatch):
    arc.save(project, _result(prefills={"a": 1}))
    assert arc.load(project) is not None

    monkeypatch.setenv("G3DT_AUTO_RESULT_CACHE", "0")
    assert arc.load(project) is None
    assert arc.save(project, _result()) is None
    monkeypatch.delenv("G3DT_AUTO_RESULT_CACHE")

    monkeypatch.setenv("G3DT_NO_CACHE", "1")
    assert arc.load(project) is None


# ---------------------------------------------------------------------------
# 5. L'embolcall de `wizard_service`
# ---------------------------------------------------------------------------

def test_wrapper_runs_auto_extract_and_saves_on_a_cold_cache(project: Path, monkeypatch: pytest.MonkeyPatch):
    import automation.auto_extractor as ae
    from web import wizard_service

    calls = []

    def fake(path, on_progress=None, **kw):
        calls.append(path)
        if on_progress:
            on_progress("step", {"step": "scan", "status": "done"})
        return _result(prefills={"client_name": "GRUP ALMA"})

    monkeypatch.setattr(ae, "auto_extract", fake)
    seen: list[tuple[str, dict]] = []
    result = wizard_service._auto_extract_cached(project, on_progress=lambda t, d: seen.append((t, d)))

    assert calls == [project]
    assert result.prefills == {"client_name": "GRUP ALMA"}
    assert seen == [("step", {"step": "scan", "status": "done"})]
    assert arc.cache_path(project).exists()


def test_wrapper_hit_never_calls_auto_extract_and_replays_events(project: Path, monkeypatch: pytest.MonkeyPatch):
    """L'acceptació de la fila 13: 2a càrrega sense xarxa ni Groq."""
    import automation.auto_extractor as ae
    from web import wizard_service

    arc.save(project, _result(prefills={"client_name": "GRUP ALMA"}),
             [("step", {"step": "scan", "status": "done"}), ("source", {"name": "ICGC", "ok": True})])

    def forbidden(*a, **kw):
        raise AssertionError("auto_extract no s'ha de cridar amb la cache calenta")

    monkeypatch.setattr(ae, "auto_extract", forbidden)
    seen: list[tuple[str, dict]] = []
    result = wizard_service._auto_extract_cached(project, on_progress=lambda t, d: seen.append((t, d)))

    assert result.prefills == {"client_name": "GRUP ALMA"}
    assert seen == [("step", {"step": "scan", "status": "done"}), ("source", {"name": "ICGC", "ok": True})]


def test_wrapper_force_refresh_reruns_and_refreshes_the_entry(project: Path, monkeypatch: pytest.MonkeyPatch):
    import automation.auto_extractor as ae
    from web import wizard_service

    arc.save(project, _result(prefills={"client_name": "VELL"}))
    monkeypatch.setattr(ae, "auto_extract", lambda path, on_progress=None, **kw: _result(prefills={"client_name": "NOU"}))

    result = wizard_service._auto_extract_cached(project, force_refresh=True)
    assert result.prefills == {"client_name": "NOU"}
    assert arc.load(project).result.prefills == {"client_name": "NOU"}


def test_miss_when_a_pipeline_output_it_relies_on_disappeared(project: Path):
    """`_merge_prefills` rellegeix `file_mapping.json` i `concept_map.json` del
    disc. Són fora de l'empremta a posta, així que el seu esborrat només es pot
    detectar així."""
    arc.save(project, _result(prefills={"a": 1}))
    assert arc.load(project) is not None
    (project / "file_mapping.json").unlink()
    assert arc.load(project) is None


def test_output_that_did_not_exist_at_save_time_is_not_required(project: Path):
    (project / "validation" / "concept_map.json").unlink()
    arc.save(project, _result(prefills={"a": 1}))
    assert arc.load(project) is not None
