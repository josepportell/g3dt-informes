"""L'avís del delta-sync arriba a la pantalla (`templates/validation/review.html`).

`automation/sync_workspace.py::sync_delta` pot tornar `status="ok"` havent pres
una decisió prudent EN SILENCI: si no ha pogut llegir la carpeta de xarxa
sencera, o si de cop hi han desaparegut molts documents, copia el que veu i **no
aparta res**. Deixa un `warning` ja redactat al resultat, i fins ara aquell text
es quedava al log del servidor: l'Eva podia estar llegint una còpia incompleta
convençuda que tot era normal.

`web/api.py` el porta ara a la resposta de `POST /api/jobs` (`warnings` + `sync`,
mateix contracte que el `warnings` de `/api/generate`) i aquest fitxer cobreix
l'altra meitat: que es vegi, que es vegi ON es veu (el panell dels jobs, que és
visible encara que el formulari del wizard no s'obri mai — cas «Preparar»), i
que **no sobrevisqui a un canvi de projecte**.

Mateix mètode que `tests/test_review_html_lectura_ui.py`: s'EXTREUEN les funcions
reals de `review.html` i s'executen sota Node amb el mínim de DOM fals. Si algú
les reanomena, l'extracció peta i el test ho diu.

La trampa que cobreix `test_the_banner_survives_the_project_change_of_its_own_run`:
`onProjectChange()` neteja els avisos del projecte anterior, i `jobsRun()` la
crida. Pintar l'avís ABANS se l'enduria — l'avís no es veuria mai justament al
camí més habitual (Enllestir / Des de zero).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.test_review_html_lectura_ui import REVIEW_HTML, _extract_block

# Funcions reals que s'executen (la resta del fitxer no es carrega mai).
_BLOCKS = [
    "let lecturaState = ",
    "function _lecturaResetState(",
    "function _jobsEl(",
    "function _jobsSetBusy(",
    "function _jobsRenderSyncWarnings(",
    "async function jobsRun(",
    "async function jobsRowAction(",
]


def _extracted_source() -> str:
    src = REVIEW_HTML.read_text(encoding="utf-8")
    blocks = []
    for header in _BLOCKS:
        block = _extract_block(src, header)
        blocks.append(block + ";" if header.startswith("let ") else block)
    return "\n\n".join(blocks)


# El text real de `sync_workspace.sync_delta` (cas «desaparició en massa»).
_WARNING = (
    "Han desaparegut de cop 4 dels 6 documents que aquesta còpia local havia rebut "
    "de la carpeta de xarxa. Per prudència no se n'ha apartat cap: els tens tots on "
    "eren. S'ha portat el que hi ha de nou o de canviat."
)

_HARNESS = r"""
'use strict';

// -- DOM fals: només el que aquestes funcions toquen ------------------------
const _byId = {};        // el que ja és a la pàgina
const _created = [];     // el que crea el codi (el bàner)

function _mkEl(tag) {
    const el = {
        tag: tag, id: '', className: '', textContent: '', value: '', disabled: false,
        style: {}, children: [], parent: null, attached: false,
        appendChild(c) { c.parent = this; c.attached = true; this.children.push(c); return c; },
        remove() {
            this.attached = false;
            if (this.parent) {
                this.parent.children = this.parent.children.filter((x) => x !== this);
                this.parent = null;
            }
        },
    };
    _created.push(el);
    return el;
}

const document = {
    createElement: _mkEl,
    createTextNode: (t) => ({ tag: '#text', textContent: t, children: [] }),
    getElementById: (id) => {
        if (_byId[id]) return _byId[id];
        for (const el of _created) if (el.id === id && el.attached) return el;
        return null;
    },
};

// Text visible d'un node (el bàner es construeix amb `createTextNode`).
function _text(el) {
    if (!el) return null;
    return (el.textContent || '') + el.children.map(_text).join('');
}
function _banner() { return document.getElementById('sync-warning-notice'); }
function _snapshot() {
    const b = _banner();
    if (!b) return null;
    return { text: _text(b), cls: b.className, parentIsJobsPanel: b.parent === _byId['jobsPanel'] };
}

_byId['jobsPanel'] = _mkEl('div');

// -- Estat global i col·laboradors que NO s'estan provant --------------------
let selectedProject = null;
let _jobsBusy = false;
let _jobsAttachNext = false;
let _jobsEnabled = true;

let _nextResponse = null;
const _calls = [];

async function fetch(url, opts) { _calls.push(url); return _nextResponse; }
function _reply(status, payload) {
    return { ok: status < 400, status: status, statusText: '', json: async () => payload };
}

function showMessage() {}
async function jobsRefresh() {}
function _jobsSchedule() {}
function nbSetState() {}
async function _jobsResolveProject() { return selectedProject; }

// Rèplica del cap d'`onProjectChange()` (review.html): fixa el projecte i
// reinicialitza l'estat de lectura, que és qui treu els avisos del projecte
// anterior. La resta de la funció real no toca res d'això.
function onProjectChange(project) {
    selectedProject = project;
    _lecturaResetState();
}

__EXTRACTED__

const out = {};
const WARNING = __WARNING__;

// -- 1. Enllestir / Des de zero: l'avís sobreviu al canvi de projecte del run --
selectedProject = '4001612 BELL-LLOC';
_nextResponse = _reply(202, { job: {}, attach: false, warnings: [WARNING],
                              sync: { mass_disappearance: true, vanished: 4 } });
await jobsRun('desde_zero');
out.after_desde_zero = _snapshot();

// -- 2. ...però NO al canvi a un altre projecte ------------------------------
onProjectChange('3001631 RUBI');
out.after_project_change = _snapshot();

// -- 3. «Preparar»: el formulari no s'obre mai, l'avís s'ha de veure igual ----
selectedProject = '3001631 RUBI';
_nextResponse = _reply(202, { job: {}, attach: false, warnings: [WARNING] });
await jobsRun('preparar');
out.after_preparar = _snapshot();

// -- 4. El projecte següent va bé: l'avís de l'anterior desapareix ------------
_nextResponse = _reply(202, { job: {}, attach: false, warnings: [] });
await jobsRun('desde_zero');
out.after_clean_run = _snapshot();

// -- 5. Botó de la fila (mateix camí, altra porta) ---------------------------
_nextResponse = _reply(409, { job: {}, attach: true, warnings: [WARNING] });
await jobsRowAction('enllestir', '4001612 BELL-LLOC', 0);
out.after_row_action = _snapshot();

// -- 6. Resposta sense `warnings` (servidor antic, o error de xarxa) ---------
_nextResponse = _reply(202, { job: {}, attach: false });
await jobsRun('desde_zero');
out.after_response_without_warnings = _snapshot();

// -- 7. Res no s'ha desactivat pel camí (l'avís no bloqueja) ------------------
out.busy_after = _jobsBusy;

console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def js(tmp_path_factory) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node no disponible")
    script = tmp_path_factory.mktemp("sync-warning-js") / "harness.mjs"
    script.write_text(
        _HARNESS
        .replace("__EXTRACTED__", _extracted_source())
        .replace("__WARNING__", json.dumps(_WARNING)),
        encoding="utf-8",
    )
    proc = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_the_warning_reaches_the_screen_verbatim(js):
    """El text el redacta el backend (diu què ha passat i què ha fet el sistema,
    i no acusa la xarxa). Aquí no es reescriu: s'emmarca."""
    banner = js["after_desde_zero"]
    assert banner is not None
    assert _WARNING in banner["text"]


def test_the_banner_says_the_project_and_that_eva_can_carry_on(js):
    text = js["after_desde_zero"]["text"]
    assert "4001612 BELL-LLOC" in text
    assert "Pots continuar" in text
    assert "mira la carpeta del projecte" in text


def test_the_banner_is_an_amber_notice_not_an_error(js):
    assert js["after_desde_zero"]["cls"] == "lectura-degraded-banner"


def test_the_banner_lives_in_the_jobs_panel(js):
    """Al panell dels jobs, no dins del formulari del wizard: amb «Preparar» el
    formulari no s'obre mai i l'avís s'ha de veure igualment."""
    assert js["after_desde_zero"]["parentIsJobsPanel"] is True
    assert js["after_preparar"] is not None
    assert _WARNING in js["after_preparar"]["text"]


def test_the_banner_survives_the_project_change_of_its_own_run(js):
    """`jobsRun()` crida `onProjectChange()`, que neteja els avisos del projecte
    anterior. Pintar-lo abans se l'enduria pel camí més habitual."""
    assert js["after_desde_zero"] is not None


def test_the_banner_never_survives_a_change_of_project(js):
    """Contaminació entre projectes: l'avís parla dels documents d'un projecte
    concret."""
    assert js["after_project_change"] is None


def test_a_clean_run_clears_a_previous_warning(js):
    assert js["after_clean_run"] is None


def test_the_row_button_shows_it_too(js):
    assert js["after_row_action"] is not None
    assert _WARNING in js["after_row_action"]["text"]


def test_a_response_without_warnings_neither_crashes_nor_shows_anything(js):
    assert js["after_response_without_warnings"] is None


def test_nothing_stays_blocked(js):
    assert js["busy_after"] is False
