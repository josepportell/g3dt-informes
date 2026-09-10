"""El botó «Actualitzar prefills» ha de forçar el refresc — i NOMÉS ell.

Hi havia un forat entre les dues meitats: `_auto_extract_cached` ja sabia
saltar-se la cache de disc (`force_refresh`), però el camí SSE la cridava
sense el paràmetre. Resultat: una caiguda transitòria d'ICGC/Cadastre/Groq
quedava servida fins a 30 dies i el botó hi tornava a encertar — clicar-lo no
canviava res.

Es prova la propietat sencera, no el cablejat d'un sol fitxer:

1. **Amb `?refresh=true` es força** — als dos endpoints SSE (`prefills-stream`,
   via B, i `lectura-stream`, via A) i fins al fons (`_auto_extract_cached`).
2. **Sense el paràmetre NO es força** — que és la meitat que costa diners: una
   obertura normal que es saltés la cache tornaria als 43-141 s per projecte,
   que és la latència que hem estat combatent.
3. **La UI l'envia des del botó i des d'enlloc més** — amb node, executant les
   funcions reals de `review.html` (mateix patró que
   `tests/test_review_html_lectura_ui.py`).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from automation import config  # noqa: E402
from tests.test_review_html_lectura_ui import _extract_block  # noqa: E402
from web import lectura_service  # noqa: E402
from web import wizard_service  # noqa: E402
from web.server import app  # noqa: E402

REVIEW_HTML = PROJECT_ROOT / "templates" / "validation" / "review.html"


@pytest.fixture
def fake_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Projecte sintètic BUIT (mateix patró que `tests/test_lectura_service.py`)."""
    ref_dir = tmp_path / "refs"
    ref_dir.mkdir()
    project_name = "4001612 BELL-LLOC"
    (ref_dir / project_name).mkdir(parents=True)
    monkeypatch.setattr(wizard_service, "_REF_DIR", ref_dir)
    monkeypatch.setattr("automation.sync_workspace.is_network_workflow_enabled", lambda: False)
    return project_name


def _recorder(seen: list[bool]):
    """Substitut del generator SSE que només apunta si li han demanat forçar."""
    def _fake(project_name, *, force_refresh=False, **kw):
        seen.append(force_refresh)
        yield "event: prefills\ndata: {}\n\n"
    return _fake


# ---------------------------------------------------------------------------
# 1. Endpoints SSE (`web/api.py`)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("query, expected", [("", False), ("?refresh=true", True)])
def test_prefills_stream_forwards_refresh(fake_project, monkeypatch, query, expected):
    seen: list[bool] = []
    monkeypatch.setattr(wizard_service, "get_prefills_streaming", _recorder(seen))

    r = TestClient(app).get(f"/api/prefills-stream/{fake_project}{query}")

    assert r.status_code == 200
    assert seen == [expected]


@pytest.mark.parametrize("query, expected", [("", False), ("?refresh=true", True)])
def test_lectura_stream_forwards_refresh(fake_project, monkeypatch, query, expected):
    monkeypatch.setattr(config, "G3DT_USE_LECTURA_HEADLESS", True)
    seen: list[bool] = []

    def _fake(project_name, *, attach=False, force_refresh=False):
        seen.append(force_refresh)
        yield "event: prefills\ndata: {}\n\n"

    monkeypatch.setattr(lectura_service, "get_lectura_streaming", _fake)

    r = TestClient(app).get(f"/api/lectura-stream/{fake_project}{query}")

    assert r.status_code == 200
    assert seen == [expected]


# ---------------------------------------------------------------------------
# 2. Fins al fons: `get_lectura_streaming` → job → `_auto_extract_cached`
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("force", [False, True])
def test_lectura_job_forwards_force_refresh_to_auto_extract(fake_project, monkeypatch, force):
    """Entre l'endpoint i la cache hi ha un job en un fil propi (Fase 10): el
    paràmetre ha de travessar `start_or_attach_job` i `run_lectura_job`."""
    seen: list[bool] = []

    def _fake_cached(project_path, *, force_refresh=False, on_progress=None):
        seen.append(force_refresh)
        return SimpleNamespace(prefills={}, sources={}, file_mapping=None, mining_result=None)

    monkeypatch.setattr(lectura_service, "_auto_extract_cached", _fake_cached)
    monkeypatch.setattr(lectura_service, "_merge_prefills", lambda *a, **kw: {})
    monkeypatch.setattr(lectura_service.shutil, "which", lambda *_: None)  # sense `claude`

    events = list(lectura_service.get_lectura_streaming(fake_project, force_refresh=force))

    assert any("event: prefills" in chunk for chunk in events)
    assert seen == [force]


def test_attaching_to_a_live_job_never_starts_an_extraction(fake_project, monkeypatch):
    """`attach=true` (l'Eva torna i clica la fila) no arrenca res: no hi ha
    cap execució nova on aplicar-hi el refresc, i el paràmetre no ha de
    provocar-ne una."""
    started: list = []
    monkeypatch.setattr(lectura_service, "start_or_attach_job",
                        lambda *a, **kw: started.append(kw) or (_ for _ in ()).throw(AssertionError))

    events = list(lectura_service.get_lectura_streaming(
        fake_project, attach=True, force_refresh=True,
    ))

    assert started == []
    assert any("event: error_event" in chunk for chunk in events)


# ---------------------------------------------------------------------------
# 3. La UI (`templates/validation/review.html`), executada de veritat amb node
# ---------------------------------------------------------------------------

_HARNESS = r"""
'use strict';

// El `failTimer` de 2,5 s d'openLecturaStream no ha de retenir el procés.
const setTimeout = () => 0;
const clearTimeout = () => {};

const urls = [];
class EventSource {
    constructor(url) { urls.push(url); }
    addEventListener() {}
    close() {}
}

let activeEventSource = null;
let selectedProject = '4001612 BELL-LLOC';
let wizardUserData = { ja_carregat: true };  // evita el fetch de user-data
let visionPollTimer = null;
let _jobsAttachNext = false;

const document = { querySelectorAll: () => [], getElementById: () => null };
function fetch() { return Promise.resolve({ ok: false, json: () => ({}) }); }

// Col·laboradors que aquestes funcions NO executen (només registren listeners).
const PRIORITY_ROLES = new Set();
const ROLE_LABELS = {};
function setStepState() {}
function appendStepFile() {}
function finishStepper() {}
function hideStepper() {}
function showWizardContent() {}
function showMessage() {}
function applyTemplatesFields() {}
function updateLecturaProgress() {}
function applyLecturaDecisions() {}
function loadProjectDataFallback() {}
function nbSetState() {}
function nbAfterCancel() {}
const emptyState = { style: {} };

__EXTRACTED__

const out = {};

// (a) URLs de l'stream de lectura (via A). Les promises queden pendents: només
//     ens interessa la URL, que es construeix en cridar `new EventSource`.
openLecturaStream(selectedProject, { refresh: true });
openLecturaStream(selectedProject, {});
openLecturaStream(selectedProject, { attach: true });
out.lectura = urls.splice(0);

// (b) El botó i l'obertura normal, pel camí de via B (`prefills-stream`).
const opts = [];
openLecturaStream = (p, o) => { opts.push(o || {}); return Promise.resolve(false); };

(async () => {
    await refreshPrefills();
    await new Promise((r) => queueMicrotask(r));
    await new Promise((r) => queueMicrotask(r));
    out.prefills_boto = urls.splice(0);
    out.opts_boto = opts.splice(0);

    await loadProjectData(selectedProject);
    await new Promise((r) => queueMicrotask(r));
    await new Promise((r) => queueMicrotask(r));
    out.prefills_obertura = urls.splice(0);
    out.opts_obertura = opts.splice(0);

    console.log(JSON.stringify(out));
})();
"""


@pytest.fixture(scope="module")
def js(tmp_path_factory) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node no disponible")
    src = REVIEW_HTML.read_text(encoding="utf-8")
    extracted = "\n\n".join(
        _extract_block(src, header)
        for header in (
            "function openLecturaStream(",
            "async function loadProjectData(",
            "async function refreshPrefills(",
        )
    )
    script = tmp_path_factory.mktemp("refresh-js") / "harness.js"
    script.write_text(_HARNESS.replace("__EXTRACTED__", extracted), encoding="utf-8")
    proc = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_the_button_asks_the_backend_to_refresh(js):
    assert js["opts_boto"] == [{"attach": False, "refresh": True}]
    assert js["prefills_boto"] == ["/api/prefills-stream/4001612%20BELL-LLOC?refresh=true"]


def test_opening_a_project_never_asks_to_refresh(js):
    """La meitat cara: si l'obertura normal forcés, tornaríem als 43-141 s."""
    assert js["opts_obertura"] == [{"attach": False, "refresh": False}]
    assert js["prefills_obertura"] == ["/api/prefills-stream/4001612%20BELL-LLOC"]


def test_lectura_stream_url_carries_refresh_only_when_asked(js):
    assert js["lectura"] == [
        "/api/lectura-stream/4001612%20BELL-LLOC?refresh=true",
        "/api/lectura-stream/4001612%20BELL-LLOC",
        # `attach` mana: enganxar-se a un job viu no pot rebobinar-lo.
        "/api/lectura-stream/4001612%20BELL-LLOC?attach=true",
    ]
