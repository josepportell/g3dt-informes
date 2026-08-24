"""Tests per al servei + endpoint SSE (Fase 5+6, via A) — `web/lectura_service.py`
+ les 3 edicions quirúrgiques a `web/wizard_service.py::_merge_prefills`
(paràmetre `skip_vision`) i `web/api.py` (`_require_lectura_enabled` +
`GET /api/lectura-stream/{p}`).

Vegeu `docs/DISSENY-WIZARD-HEADLESS-CANDIDATS-2026-08-24.md` §2, §7, §8.3 i
§9 Fases 5-6, i el complement del coordinador (2026-08-24) sobre els events
`templates_fields`/`decisions` enriquits vs. els marcadors del runner.

CAP crida real: `automation.auto_extractor.auto_extract`,
`automation.lectura.runner.run_lectura`, `web.wizard_service._run_vision_phase`
i `shutil.which` es substitueixen sempre per fakes. `_merge_prefills` NO es
mocka (corre real, sobre un projecte sintètic buit a `tmp_path`) perquè és
precisament el que la Fase 6 estén — però `ANTHROPIC_API_KEY` es buida via
monkeypatch com a xarxa de seguretat addicional (evita que
`_synthesize_with_llm` intenti una crida real si l'entorn `.env` en té una).

`docs/wizard-headless/fase0-acceptacio/escalars_decisions.json` és el fixture
REAL (Fase 0, Bell-lloc) — es llegeix, mai s'escriu ni es modifica.

Escenaris (3) i (4) testegen `_apply_lectura_overlay` com a funció pura,
directament: `_clear_stale_user_data` (reutilitzada tal qual de
`wizard_service`, sense tocar) renombra qualsevol `user_data.json` existent a
`_user_data_prev.json` a l'INICI de cada pipeline (comportament d'avui, igual
a `get_prefills_streaming`), així que la precedència "Eva mana sempre" no es
pot exercitar de cap manera realista a través d'un `user_data.json` escrit
abans de cridar `get_lectura_streaming` — es verifica doncs directament sobre
la funció que implementa la regla.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from automation import config  # noqa: E402
from automation.lectura.runner import LecturaResult  # noqa: E402
from web import lectura_service  # noqa: E402
from web import wizard_service  # noqa: E402
from web.server import app  # noqa: E402

_ESCALARS_FIXTURE_PATH = (
    PROJECT_ROOT / "docs" / "wizard-headless" / "fase0-acceptacio" / "escalars_decisions.json"
)


def _load_escalars_fixture() -> dict:
    """Fixture REAL, read-only (mai escrit ni mutat pels tests)."""
    return json.loads(_ESCALARS_FIXTURE_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Fixtures pytest
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[str, Path]:
    """Projecte sintètic BUIT a `tmp_path`, amb `wizard_service._REF_DIR`
    apuntant-hi (mateix patró que `tests/test_ai_pipeline_ranking_api.py`).
    """
    ref_dir = tmp_path / "refs"
    ref_dir.mkdir()
    project_name = "4001612 BELL-LLOC"
    project_path = ref_dir / project_name
    project_path.mkdir(parents=True)
    monkeypatch.setattr(wizard_service, "_REF_DIR", ref_dir)
    return project_name, project_path


@pytest.fixture(autouse=True)
def _no_real_llm_or_vision(monkeypatch: pytest.MonkeyPatch):
    """Xarxa de seguretat: buida ANTHROPIC_API_KEY perquè
    `_synthesize_with_llm` (cridada dins `_merge_prefills`, real als tests)
    faci `return` immediat sense intentar cap crida, independentment del que
    hi hagi a `.env` d'aquest repo."""
    monkeypatch.setattr(wizard_service.config, "ANTHROPIC_API_KEY", "")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_sse(chunks: list[str]) -> list[tuple[str, dict]]:
    parsed: list[tuple[str, dict]] = []
    for chunk in chunks:
        event_name = None
        data_line = None
        for line in chunk.strip("\n").split("\n"):
            if line.startswith("event: "):
                event_name = line[len("event: "):]
            elif line.startswith("data: "):
                data_line = line[len("data: "):]
        if event_name is not None:
            parsed.append((event_name, json.loads(data_line) if data_line else {}))
    return parsed


def _make_fake_auto_extract(prefills: dict | None = None, sources: dict | None = None, emit_step: bool = True):
    def _fake(project_path, on_progress=None):
        if emit_step and on_progress is not None:
            on_progress("step", {"step": "auto_extract", "status": "done"})
        return SimpleNamespace(
            prefills=dict(prefills or {}),
            sources=dict(sources or {}),
            file_mapping=None,
            mining_result=None,
        )
    return _fake


_G3_TEMPLATES_SAMPLE = {
    "project": "4001612 BELL-LLOC",
    "read_on": "2026-08-24T12:00:00",
    "reader": "test-fixture (NO real g3_templates.read_project call)",
    "documents": [],
    "concepts": {
        "expedient": [
            {"value": "4001612", "location": "Hoja1!N19", "quote": "4001612",
             "confidence": 0.95, "source": "comanda laboratori.xls", "document_type": "comanda_lab_g3"},
        ],
        "field_date": [
            {"value": "2026-01-15", "location": "fitxa!F38", "quote": "15/01/2026",
             "confidence": 0.9, "source": "DADES PER ANAR A CAMP.xlsx", "document_type": "fitxa_camp_g3"},
        ],
    },
}


def _make_fake_run_lectura(*, decisions: dict | None, degraded: bool = False, write_templates: bool = True):
    """Fake de `automation.lectura.runner.run_lectura`: NO crida `claude`,
    escriu `_g3_templates.json` sintètic a `out_dir` (com fa el runner real
    ABANS de `lectura_inici`) i emet 6 events via `on_event`, incloent els
    DOS noms que col·lideixen amb els que `get_lectura_streaming` injecta
    pel seu compte (`templates_fields` amb `{n_documents}`, `decisions` amb
    `{cached}`) — verifica que el servei els reanomena en lloc de perdre'ls.
    """
    def _fake(project_path, *, out_dir=None, on_event=None, should_cancel=None, force=False):
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        if write_templates:
            (out_dir / "_g3_templates.json").write_text(
                json.dumps(_G3_TEMPLATES_SAMPLE, ensure_ascii=False), encoding="utf-8",
            )
        if on_event is not None:
            on_event("lectura_inventari", {"n_files": 3})
            on_event("templates_fields", {"n_documents": 2})  # marcador del runner
            on_event("lectura_inici", {"n_claude": 1, "n_python": 0, "docs": ["annex_a.pdf"]})
            on_event("lectura_doc_inici", {"doc": "annex_a.pdf"})
            on_event("lectura_doc", {"doc": "annex_a.pdf", "cached": False})
            on_event("decisions", {"cached": False})  # marcador del runner
            on_event("lectura_fi", {
                "n_docs": 1, "by_status": {"ok": 1}, "elapsed_s_total": 0.1, "degraded": degraded,
            })
        return LecturaResult(
            decisions=decisions,
            per_doc=[{"doc": "annex_a.pdf", "status": "ok", "attempts": 1, "elapsed_s": 0.1}],
            degraded=degraded,
            mode="document",
            telemetry_path=out_dir / "_telemetry.jsonl",
        )
    return _fake


# ---------------------------------------------------------------------------
# (1) Happy path: lectura OK, vision NO cridada, events enriquits presents
# ---------------------------------------------------------------------------


def test_happy_path_lectura_ok_vision_not_called(fake_project, monkeypatch):
    project_name, _ = fake_project

    vision_calls: list = []
    monkeypatch.setattr(wizard_service, "_run_vision_phase", lambda *a, **k: vision_calls.append((a, k)))
    monkeypatch.setattr("automation.auto_extractor.auto_extract", _make_fake_auto_extract())

    decisions = _load_escalars_fixture()
    monkeypatch.setattr(lectura_service, "run_lectura", _make_fake_run_lectura(decisions=decisions))
    monkeypatch.setattr(lectura_service.shutil, "which", lambda *_: "/usr/bin/claude")

    events = _parse_sse(list(lectura_service.get_lectura_streaming(project_name)))
    names = [n for n, _ in events]

    # Vision (via B) NO s'executa: la lectura ha produït decisions vàlides.
    assert vision_calls == []

    # step d'auto_extract (fil A) reenviat tal qual.
    assert "step" in names

    # Marcadors del runner reanomenats (mai perduts, mai amb el nom "real").
    assert "lectura_templates_marker" in names
    assert [p for n, p in events if n == "lectura_templates_marker"][0] == {"n_documents": 2}
    assert "lectura_decisions_marker" in names
    assert [p for n, p in events if n == "lectura_decisions_marker"][0] == {"cached": False}

    # Cap event crua "templates_fields"/"decisions" del runner arriba amb
    # payload de marcador — només amb el payload enriquit d'aquest servei.
    for n, p in events:
        if n == "templates_fields":
            assert "n_documents" not in p
        if n == "decisions":
            assert "cached" not in p

    # ordre relatiu: inventari abans dels marcadors, marcadors abans de fi.
    assert names.index("lectura_inventari") < names.index("lectura_templates_marker")
    assert names.index("lectura_inici") < names.index("lectura_fi")


def test_happy_path_templates_fields_event_payload(fake_project, monkeypatch):
    """Event propi `templates_fields`: payload real (millor senyal/concepte),
    NO el marcador `{n_documents}` del runner."""
    project_name, _ = fake_project

    monkeypatch.setattr(wizard_service, "_run_vision_phase", lambda *a, **k: None)
    monkeypatch.setattr("automation.auto_extractor.auto_extract", _make_fake_auto_extract())

    decisions = _load_escalars_fixture()
    monkeypatch.setattr(lectura_service, "run_lectura", _make_fake_run_lectura(decisions=decisions))
    monkeypatch.setattr(lectura_service.shutil, "which", lambda *_: "/usr/bin/claude")

    events = _parse_sse(list(lectura_service.get_lectura_streaming(project_name)))
    templates_events = [p for n, p in events if n == "templates_fields"]

    assert len(templates_events) == 1
    assert templates_events[0] == {
        "expedient": {"value": "4001612", "location": "Hoja1!N19", "quote": "4001612", "confidence": 0.95},
        "field_date": {"value": "2026-01-15", "location": "fitxa!F38", "quote": "15/01/2026", "confidence": 0.9},
    }


def test_happy_path_decisions_event_payload_present_before_prefills(fake_project, monkeypatch):
    """Event propi `decisions`: payload sencer `{decisions, degraded, per_doc}`,
    present ABANS del merge final (`prefills`)."""
    project_name, _ = fake_project

    monkeypatch.setattr(wizard_service, "_run_vision_phase", lambda *a, **k: None)
    monkeypatch.setattr("automation.auto_extractor.auto_extract", _make_fake_auto_extract())

    decisions = _load_escalars_fixture()
    monkeypatch.setattr(lectura_service, "run_lectura", _make_fake_run_lectura(decisions=decisions, degraded=False))
    monkeypatch.setattr(lectura_service.shutil, "which", lambda *_: "/usr/bin/claude")

    events = _parse_sse(list(lectura_service.get_lectura_streaming(project_name)))
    names = [n for n, _ in events]

    decisions_events = [p for n, p in events if n == "decisions"]
    assert len(decisions_events) == 1
    payload = decisions_events[0]
    assert set(payload.keys()) == {"decisions", "degraded", "per_doc"}
    assert payload["decisions"]["project"] == "4001612 BELL-LLOC"
    assert payload["degraded"] is False
    assert payload["per_doc"] == [{"doc": "annex_a.pdf", "status": "ok", "attempts": 1, "elapsed_s": 0.1}]

    assert names.index("decisions") < names.index("prefills")


def test_happy_path_prefills_merged_fields_and_lectura_key(fake_project, monkeypatch):
    project_name, _ = fake_project

    monkeypatch.setattr(wizard_service, "_run_vision_phase", lambda *a, **k: None)
    monkeypatch.setattr("automation.auto_extractor.auto_extract", _make_fake_auto_extract())

    decisions = _load_escalars_fixture()
    monkeypatch.setattr(lectura_service, "run_lectura", _make_fake_run_lectura(decisions=decisions))
    monkeypatch.setattr(lectura_service.shutil, "which", lambda *_: "/usr/bin/claude")

    events = _parse_sse(list(lectura_service.get_lectura_streaming(project_name)))
    prefill_events = [p for n, p in events if n == "prefills"]
    assert len(prefill_events) == 1
    merged = prefill_events[0]

    assert merged["_lectura"]["source"] == "system"
    assert merged["_lectura"]["value"]["degraded"] is False
    assert merged["_lectura"]["value"]["decisions"]["project"] == "4001612 BELL-LLOC"

    # segur -> source "lectura"
    assert merged["client_name"] == {
        "value": decisions["fields"]["client_name"]["value"], "source": "lectura",
    }
    assert merged["site_municipality"] == {
        "value": decisions["fields"]["municipality"]["value"], "source": "lectura",
    }

    # candidats -> candidates[0], source "lectura_candidats"
    assert merged["street_address"] == {
        "value": decisions["fields"]["street_address"]["candidates"][0]["value"],
        "source": "lectura_candidats",
    }
    assert merged["superficie_parcela_m2"] == {
        "value": decisions["fields"]["superficie_parcela"]["candidates"][0]["value"],
        "source": "lectura_candidats",
    }


# ---------------------------------------------------------------------------
# (2) claude absent -> fallback complet a via B
# ---------------------------------------------------------------------------


def test_claude_not_found_falls_back_to_via_b(fake_project, monkeypatch):
    project_name, _ = fake_project

    vision_calls: list = []
    monkeypatch.setattr(wizard_service, "_run_vision_phase", lambda *a, **k: vision_calls.append((a, k)))
    monkeypatch.setattr("automation.auto_extractor.auto_extract", _make_fake_auto_extract())

    run_lectura_calls: list = []
    monkeypatch.setattr(
        lectura_service, "run_lectura",
        lambda *a, **k: run_lectura_calls.append((a, k)),
    )
    monkeypatch.setattr(lectura_service.shutil, "which", lambda *_: None)

    events = _parse_sse(list(lectura_service.get_lectura_streaming(project_name)))
    names = [n for n, _ in events]

    assert "lectura_fallback" in names
    fallback_payload = [p for n, p in events if n == "lectura_fallback"][0]
    assert fallback_payload["reason"] == "claude_not_found"

    # run_lectura mai s'invoca quan `claude` no es troba.
    assert run_lectura_calls == []

    # Forma triada (disseny §7 punt 1): via B COMPLETA — vision SÍ es crida.
    assert len(vision_calls) == 1

    prefill_events = [p for n, p in events if n == "prefills"]
    assert len(prefill_events) == 1
    # Forma triada per aquest servei (documentada al mòdul i aquí): en
    # fallback NO s'afegeix `_lectura` — `merged` és exactament el que via B
    # produiria avui, sense cap regressió ni marcador ambigu de degradació.
    assert "_lectura" not in prefill_events[0]

    assert "decisions" not in names
    assert "lectura_decisions_marker" not in names


def test_run_lectura_exception_falls_back_to_via_b(fake_project, monkeypatch):
    project_name, _ = fake_project

    vision_calls: list = []
    monkeypatch.setattr(wizard_service, "_run_vision_phase", lambda *a, **k: vision_calls.append((a, k)))
    monkeypatch.setattr("automation.auto_extractor.auto_extract", _make_fake_auto_extract())

    def _boom(*a, **k):
        raise RuntimeError("mock claude spawn crash")

    monkeypatch.setattr(lectura_service, "run_lectura", _boom)
    monkeypatch.setattr(lectura_service.shutil, "which", lambda *_: "/usr/bin/claude")

    events = _parse_sse(list(lectura_service.get_lectura_streaming(project_name)))
    names = [n for n, _ in events]

    assert "lectura_fallback" in names
    fallback_payload = [p for n, p in events if n == "lectura_fallback"][0]
    assert fallback_payload["reason"] == "exception"
    assert "mock claude spawn crash" in fallback_payload["detail"]

    assert len(vision_calls) == 1
    prefill_events = [p for n, p in events if n == "prefills"]
    assert "_lectura" not in prefill_events[0]


# ---------------------------------------------------------------------------
# (3) Precedència user_data + (4) no_trobat — `_apply_lectura_overlay` pur
# ---------------------------------------------------------------------------


def test_overlay_respects_user_source_precedence():
    decisions = _load_escalars_fixture()
    assert decisions["fields"]["client_name"]["estat"] == "segur"
    assert decisions["fields"]["client_name"]["value"] != "EVA VALUE"

    merged = {"client_name": {"value": "EVA VALUE", "source": "user"}}
    lectura_service._apply_lectura_overlay(merged, decisions)

    assert merged["client_name"] == {"value": "EVA VALUE", "source": "user"}


def test_overlay_respects_user_data_anterior_fallback_source():
    decisions = _load_escalars_fixture()
    merged = {"site_municipality": {"value": "EVA MUNI", "source": "user_data.json anterior"}}
    lectura_service._apply_lectura_overlay(merged, decisions)

    assert merged["site_municipality"] == {"value": "EVA MUNI", "source": "user_data.json anterior"}


def test_overlay_writes_segur_and_candidats_when_not_locked():
    decisions = _load_escalars_fixture()
    merged: dict = {}
    lectura_service._apply_lectura_overlay(merged, decisions)

    assert merged["client_name"] == {
        "value": decisions["fields"]["client_name"]["value"], "source": "lectura",
    }
    assert merged["street_address"] == {
        "value": decisions["fields"]["street_address"]["candidates"][0]["value"],
        "source": "lectura_candidats",
    }
    # Claus sense mapping de wizard confirmat (MAPPING_DECISIONS_WIZARD[...] is None)
    # mai toquen `merged`.
    assert "expedient" not in merged
    assert "referencia_catastral" not in merged
    assert "num_dpsh_tests" not in merged
    assert "field_date" not in merged


def test_overlay_no_trobat_never_writes_value():
    decisions = _load_escalars_fixture()
    decisions["fields"]["client_name"] = {
        "estat": "no_trobat", "value": None, "sources_checked": ["pressupost", "fitxa"],
    }
    merged: dict = {}
    lectura_service._apply_lectura_overlay(merged, decisions)

    assert "client_name" not in merged


# ---------------------------------------------------------------------------
# (5) Endpoint FastAPI — flag off -> 404; flag on -> 200 + stream
# ---------------------------------------------------------------------------


def test_lectura_stream_endpoint_404_when_flag_off(monkeypatch):
    monkeypatch.setattr(config, "G3DT_USE_LECTURA_HEADLESS", False)

    client = TestClient(app)
    r = client.get("/api/lectura-stream/anything")

    assert r.status_code == 404


def test_lectura_stream_endpoint_200_with_events_when_flag_on(fake_project, monkeypatch):
    project_name, _ = fake_project
    monkeypatch.setattr(config, "G3DT_USE_LECTURA_HEADLESS", True)
    monkeypatch.setattr("automation.sync_workspace.is_network_workflow_enabled", lambda: False)

    monkeypatch.setattr(wizard_service, "_run_vision_phase", lambda *a, **k: None)
    monkeypatch.setattr("automation.auto_extractor.auto_extract", _make_fake_auto_extract())

    decisions = _load_escalars_fixture()
    monkeypatch.setattr(lectura_service, "run_lectura", _make_fake_run_lectura(decisions=decisions))
    monkeypatch.setattr(lectura_service.shutil, "which", lambda *_: "/usr/bin/claude")

    client = TestClient(app)
    r = client.get(f"/api/lectura-stream/{project_name}")

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    body = r.content.decode("utf-8")
    assert "event: prefills" in body
    assert "event: templates_fields" in body
    assert "event: decisions" in body
    assert "event: lectura_templates_marker" in body
    assert "event: lectura_decisions_marker" in body


def test_lectura_stream_endpoint_404_when_project_missing(monkeypatch, tmp_path):
    ref_dir = tmp_path / "refs_empty"
    ref_dir.mkdir()
    monkeypatch.setattr(wizard_service, "_REF_DIR", ref_dir)
    monkeypatch.setattr(config, "G3DT_USE_LECTURA_HEADLESS", True)
    monkeypatch.setattr("automation.sync_workspace.is_network_workflow_enabled", lambda: False)

    client = TestClient(app)
    r = client.get("/api/lectura-stream/does-not-exist")

    assert r.status_code == 404
