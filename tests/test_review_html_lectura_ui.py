"""Correccions del 2026-09-01 a `templates/validation/review.html` (blocs de lectura).

`review.html` fa 10.000 línies, no té framework i fins ara no tenia cap test.
Aquí no se n'inventa cap: s'EXTREUEN les funcions concretes que canvien i
s'executen sota Node amb el mínim de DOM fals perquè corrin. Si algú les
reanomena, l'extracció peta i el test ho diu — que és exactament el que volem.

Els tres defectes coberts:

1. **Contaminació entre projectes** — `lecturaState.selections` no es reiniciava
   mai. L'Eva clicava un chip N30 al projecte A, triava el projecte B al
   desplegable (sense recàrrega) i en desar B s'hi enviava la clau d'A; com que
   les claus són genèriques (`{bloc}.{índex}.{cel·la}`), el backend la casava
   contra el `_decisions.json` de B i hi congelava el valor d'A.

2. **L'input deia una cosa i el badge una altra** — `applyTemplatesFields`
   (TEMPS 1a) sobreescrivia l'input amb el valor provisional de la plantilla G3,
   però la branca `segur` d'`applyLecturaDecisions` (TEMPS 3) només omplia camps
   BUITS: l'input es quedava amb el provisional mentre el badge i el popup deien
   el valor consolidat.

3. **Tries congelades perdudes** — després d'una recàrrega, `selections`
   arrencava buit i tornar a pintar la taula reescrivia el candidat 1 per sobre
   de la tria validada de l'Eva.

4. **Tries congelades ressuscitades a cegues** (2026-09-01) — recuperar-les sense
   comprovar-les era pitjor que perdre-les. Les claus són posicionals
   (`{bloc}.{índex}.{cel·la}`): quan arriba un document nou i les files es
   reordenen, la tria d'ahir aterra sobre una altra fila. Als desplegables de
   litologia queia a «altre…» (visible però mort); als chips N30 no es marcava
   res i s'enviava igual. Ara només sobreviu la tria que casa amb un candidat
   d'aquella cel·la, o el text lliure que l'Eva ha escrit i que viatja MARCAT
   (`_lliure`).

5. **Fuita entre projectes per una porta nova** — `wizardUserData` és una global
   sense marca de projecte. Una resposta tardana de `/api/user-data/A` (l'Eva ja
   ha triat B al desplegable) injectava les tries d'A al mapa de B, que és
   exactament el que tanca el punt 1.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REVIEW_HTML = Path(__file__).resolve().parent.parent / "templates" / "validation" / "review.html"

# Funcions reals que s'executen (la resta del fitxer no es carrega mai).
_FUNCTIONS = [
    "function _lecturaEnsureProject(",
    "function _lecturaSetSelection(",
    "function _lecturaClearSelection(",
    "function _lecturaSelectionFor(",
    "function _lecturaIsFreeText(",
    "function _lecturaResetState(",
    "function _lecturaRestoreSelections(",
    "function _lecturaTruncate(",
    "function _lecturaBadgeClassAndLabel(",
    "function _lecturaLitologiaSelect(",
    "function _lecturaN30Cell(",
    "function applyLecturaDecisions(",
    "function getLecturaSelections(",
]
_CONSTS = ["const LECTURA_MAPPING = ", "let lecturaState = "]


def _extract_block(src: str, header: str) -> str:
    """Text des de `header` fins a la clau que el tanca (ignora cadenes i comentaris)."""
    start = src.index(header)
    i = src.index("{", start)
    depth, j, mode = 0, i, None
    while j < len(src):
        ch, nxt = src[j], src[j + 1] if j + 1 < len(src) else ""
        if mode in ("'", '"', "`"):
            if ch == "\\":
                j += 2
                continue
            if ch == mode:
                mode = None
        elif mode == "//":
            if ch == "\n":
                mode = None
        elif mode == "/*":
            if ch == "*" and nxt == "/":
                mode = None
                j += 2
                continue
        elif ch == "/" and nxt in ("/", "*"):
            mode = "//" if nxt == "/" else "/*"
            j += 2
            continue
        elif ch in "'\"`":
            mode = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return src[start: j + 1]
        j += 1
    raise AssertionError(f"bloc no tancat a review.html: {header}")


def _extracted_source() -> str:
    src = REVIEW_HTML.read_text(encoding="utf-8")
    blocks = [_extract_block(src, h) for h in _CONSTS]
    blocks = [b if b.endswith(";") else b + ";" for b in blocks]
    blocks += [_extract_block(src, h) for h in _FUNCTIONS]
    return "\n\n".join(blocks)


# DOM fals: només el que aquestes funcions toquen.
_HARNESS = r"""
'use strict';

function _mkEl(tag) {
    const el = {
        tag: tag, children: [], style: {}, dataset: {}, value: '', textContent: '',
        className: '', title: '', type: '', placeholder: '',
        // Un <select> real val la primera <option> mentre ningu no el toca:
        // sense aixo el cas "candidat 1 per defecte" no es pot distingir.
        appendChild(c) {
            this.children.push(c);
            if (this.tag === 'select' && c.tag === 'option' && this.value === '') this.value = c.value;
            return c;
        },
        querySelectorAll() { return []; },
        remove() {}, focus() {},
    };
    el.classList = {
        add(c) { el.className = (el.className + ' ' + c).trim(); },
        remove(c) { el.className = el.className.split(' ').filter(x => x && x !== c).join(' '); },
        contains(c) { return el.className.split(' ').indexOf(c) >= 0; },
        toggle() {},
    };
    return el;
}

const _byId = {};
const document = {
    getElementById: (id) => _byId[id] || null,
    createElement: _mkEl,
    querySelectorAll: () => [],
    addEventListener: () => {},
};

// Estat global que les funcions extretes llegeixen.
let selectedProject = null;
let wizardUserData = {};
let wizardUserDataProject = null;

// Col·laboradors que NO s'estan provant.
const _fields = {};
const _userSourced = new Set();
function _lecturaFieldEl(k) { return _fields[k] || null; }
function _lecturaIsUserSourced(k) { return _userSourced.has(k); }
function _lecturaRenderFieldBadge() { return null; }
function _lecturaCellBadgeSpan() { return _mkEl('span'); }
function renderLecturaExtraFields() {}
function renderLecturaTables() {}
function showLecturaPopup() {}

__EXTRACTED__

const out = {};

// -- 1. Contaminació entre projectes ---------------------------------------
selectedProject = 'A';
_lecturaResetState();
_lecturaSetSelection('spt_ma_tests.0.n30', 42);
out.a_selections = getLecturaSelections();

selectedProject = 'B';                       // canvi de projecte SENSE reset
out.b_without_reset = getLecturaSelections();
_lecturaSetSelection('soil_levels.0.litologia', 'Argiles');
out.b_after_write = getLecturaSelections();

selectedProject = 'A';
_lecturaResetState();
_lecturaSetSelection('soil_levels.0.litologia', 'Reblert');
selectedProject = 'B';
_lecturaResetState();                        // el que fa `onProjectChange`
out.b_after_reset = getLecturaSelections();

// -- 2. `segur` sobreescriu el provisional, mai el que ha escrit l'Eva ------
selectedProject = 'P';
_lecturaResetState();
_fields['superficie_parcela_m2'] = _mkEl('input');
_fields['superficie_parcela_m2'].value = '120 m2';        // TEMPS 1a (plantilla G3)
_fields['site_municipality'] = _mkEl('input');
_fields['site_municipality'].value = 'el que ha escrit l\'Eva';
_userSourced.add('site_municipality');
_fields['num_floors'] = _mkEl('input');
_fields['num_floors'].value = 'PB+1';
_fields['building_type'] = _mkEl('input');
_fields['building_type'].value = 'provisional';
_fields['architect_name'] = _mkEl('input');
_fields['architect_name'].value = 'provisional';

applyLecturaDecisions({
    fields: {
        superficie_parcela: { estat: 'segur', value: '135 m2' },
        municipality: { estat: 'segur', value: 'Castellar del Vallès' },
        num_floors: { estat: 'segur', value: '' },
        building_type: { estat: 'no_trobat' },
        architect_name: { estat: 'candidats', candidates: [{ value: 'X. Mateu' }] },
    },
}, false);

out.segur_overwrites_provisional = _fields['superficie_parcela_m2'].value;
out.segur_respects_user = _fields['site_municipality'].value;
out.segur_empty_never_wipes = _fields['num_floors'].value;
out.no_trobat_never_writes = _fields['building_type'].value;
out.candidats_still_overwrite = _fields['architect_name'].value;

// -- 3. Tries congelades: restauració des de user_data ----------------------
function _renderLitologia(project, saved, candidates) {
    selectedProject = project;
    _lecturaResetState();
    wizardUserData = saved ? { lectura_selections: saved } : {};
    wizardUserDataProject = project;
    _lecturaRestoreSelections(wizardUserData);
    const node = _lecturaLitologiaSelect('soil_levels.0.litologia',
        { estat: 'candidats', candidates: candidates });
    const select = node.children[0];
    const free = node.children[2];
    return {
        select: select.value,
        free: free ? free.value : null,
        freeVisible: free ? free.style.display : null,
        selection: getLecturaSelections()['soil_levels.0.litologia'],
        sent: getLecturaSelections(),
    };
}

const CANDS = [{ value: 'Reblert antropic' }, { value: 'Argiles llimoses marrons' }];
const FREE_TEXT = 'Graves amb matriu sorrenca (Eva)';

out.litologia_default = _renderLitologia('P1', null, CANDS);
out.litologia_restored = _renderLitologia(
    'P2', { 'soil_levels.0.litologia': 'Argiles llimoses marrons' }, CANDS);
// Text lliure MARCAT: es recupera a "altre…".
out.litologia_free_text = _renderLitologia(
    'P3', { 'soil_levels.0.litologia': FREE_TEXT, _lliure: ['soil_levels.0.litologia'] }, CANDS);
// Tria d'una lectura anterior que ja no casa amb cap candidat i NO ve marcada:
// es descarta (les claus son posicionals — aterraria a la fila equivocada).
out.litologia_dead_choice = _renderLitologia(
    'P3b', { 'soil_levels.0.litologia': 'Argiles llimoses amb graves (lectura VELLA)' }, CANDS);

// L'Eva escriu text lliure: surt marcat cap al backend.
selectedProject = 'P3c';
_lecturaResetState();
const litNode = _lecturaLitologiaSelect('soil_levels.0.litologia',
    { estat: 'candidats', candidates: CANDS });
litNode.children[2].value = 'Sorres denses (a ma)';
litNode.children[2].oninput();
out.free_text_marked = getLecturaSelections();
// ...i si torna a un candidat, la marca cau.
litNode.children[0].value = '1';
litNode.children[0].onchange();
out.free_text_unmarked = getLecturaSelections();

function _renderN30(project, saved, candidates) {
    selectedProject = project;
    _lecturaResetState();
    wizardUserData = { lectura_selections: saved };
    wizardUserDataProject = project;
    _lecturaRestoreSelections(wizardUserData);
    const node = _lecturaN30Cell('spt_ma_tests.0', { n30: { candidates: candidates } });
    return {
        chips: node.children.map(c => ({ text: c.textContent, cls: c.className })),
        sent: getLecturaSelections(),
    };
}

const n30 = _renderN30('P4', { 'spt_ma_tests.0.n30': 40 }, [{ value: 20 }, { value: 40 }]);
out.n30_chips = n30.chips;
out.n30_selection = n30.sent['spt_ma_tests.0.n30'];
// Re-lectura: la suma d'ahir ja no es cap dels candidats d'aquesta fila.
out.n30_dead_choice = _renderN30('P4b', { 'spt_ma_tests.0.n30': 40 },
    [{ value: 12 }, { value: 18 }]).sent;

// Una tria viva mana sobre la desada.
selectedProject = 'P5';
_lecturaResetState();
_lecturaSetSelection('soil_levels.0.litologia', 'viva');
wizardUserDataProject = 'P5';
_lecturaRestoreSelections({ lectura_selections: { 'soil_levels.0.litologia': 'desada' } });
out.live_wins = getLecturaSelections()['soil_levels.0.litologia'];

// -- 4. El user_data d'un altre projecte no es restaura mai -----------------
selectedProject = 'B';
_lecturaResetState();
// Resposta tardana de `/api/user-data/A`: l'Eva ja es al projecte B.
wizardUserDataProject = 'A';
_lecturaRestoreSelections({ lectura_selections: { 'soil_levels.0.litologia': "d'A" } });
out.late_response_from_other_project = getLecturaSelections();
// Amb projecte explicit (el punt de crida d'`onProjectChange`), igual.
_lecturaRestoreSelections({ lectura_selections: { 'soil_levels.0.litologia': "d'A" } }, 'A');
out.late_response_explicit = getLecturaSelections();
// I la del projecte que es veu, si.
_lecturaRestoreSelections({ lectura_selections: { 'soil_levels.0.litologia': 'de B' } }, 'B');
out.own_response_restores = getLecturaSelections();

console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def js(tmp_path_factory) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node no disponible")
    script = tmp_path_factory.mktemp("lectura-js") / "harness.js"
    script.write_text(_HARNESS.replace("__EXTRACTED__", _extracted_source()), encoding="utf-8")
    proc = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


# ---------------------------------------------------------------------------
# 1. Contaminació entre projectes
# ---------------------------------------------------------------------------

def test_selections_belong_to_the_project_that_produced_them(js):
    assert js["a_selections"] == {"spt_ma_tests.0.n30": 42}
    # Canviar de projecte al desplegable: el desat de B no pot dur claus d'A.
    assert js["b_without_reset"] == {}
    assert js["b_after_write"] == {"soil_levels.0.litologia": "Argiles"}


def test_project_change_resets_the_selections(js):
    assert js["b_after_reset"] == {}


# ---------------------------------------------------------------------------
# 2. Asimetria de guardes (input vs badge)
# ---------------------------------------------------------------------------

def test_segur_overwrites_the_provisional_template_value(js):
    assert js["segur_overwrites_provisional"] == "135 m2"


def test_segur_never_touches_what_eva_typed(js):
    assert js["segur_respects_user"] == "el que ha escrit l'Eva"


def test_segur_without_value_never_wipes_the_field(js):
    assert js["segur_empty_never_wipes"] == "PB+1"


def test_no_trobat_still_never_writes(js):
    assert js["no_trobat_never_writes"] == "provisional"


def test_candidats_branch_is_unchanged(js):
    assert js["candidats_still_overwrite"] == "X. Mateu"


# ---------------------------------------------------------------------------
# 3. Tries congelades restaurades en tornar a pintar
# ---------------------------------------------------------------------------

def test_litologia_defaults_to_the_first_candidate(js):
    """Disseny D3: mai en blanc, mai fals-segur."""
    assert js["litologia_default"]["select"] == "0"
    assert js["litologia_default"]["selection"] == "Reblert antropic"


def test_litologia_restores_the_saved_candidate(js):
    assert js["litologia_restored"]["select"] == "1"
    assert js["litologia_restored"]["selection"] == "Argiles llimoses marrons"


def test_litologia_restores_saved_free_text_when_marked(js):
    free = js["litologia_free_text"]
    assert free["select"] == "altre"
    assert free["free"] == "Graves amb matriu sorrenca (Eva)"
    assert free["freeVisible"] == "block"
    assert free["selection"] == "Graves amb matriu sorrenca (Eva)"
    assert free["sent"]["_lliure"] == ["soil_levels.0.litologia"]


def test_litologia_discards_a_choice_from_a_dead_reading(js):
    """Sense marca de text lliure, un valor que ja no casa amb cap candidat és
    d'una lectura anterior: les claus són posicionals i aterraria a la fila
    equivocada. Mana el candidat 1."""
    dead = js["litologia_dead_choice"]
    assert dead["select"] == "0"
    assert dead["selection"] == "Reblert antropic"
    assert "_lliure" not in dead["sent"]


def test_free_text_typed_by_eva_travels_marked(js):
    assert js["free_text_marked"] == {
        "soil_levels.0.litologia": "Sorres denses (a ma)",
        "_lliure": ["soil_levels.0.litologia"],
    }


def test_going_back_to_a_candidate_drops_the_free_text_mark(js):
    assert js["free_text_unmarked"] == {"soil_levels.0.litologia": "Argiles llimoses marrons"}


def test_n30_marks_the_saved_chip(js):
    chips = js["n30_chips"]
    assert [c["text"] for c in chips] == ["20", "40"]
    assert "selected" not in chips[0]["cls"]
    assert "selected" in chips[1]["cls"]
    assert js["n30_selection"] == 40


def test_n30_erases_a_choice_that_matches_no_chip(js):
    """Deixar-la al mapa era el pitjor dels casos: no es marcava enlloc (l'Eva no
    la veia) i s'enviava igual."""
    assert js["n30_dead_choice"] == {}


def test_a_live_choice_wins_over_the_saved_one(js):
    assert js["live_wins"] == "viva"


# ---------------------------------------------------------------------------
# 4. Resposta tardana de /api/user-data (fuita entre projectes, porta nova)
# ---------------------------------------------------------------------------

def test_a_late_user_data_response_never_lands_on_another_project(js):
    assert js["late_response_from_other_project"] == {}
    assert js["late_response_explicit"] == {}


def test_the_current_projects_user_data_still_restores(js):
    assert js["own_response_restores"] == {"soil_levels.0.litologia": "de B"}
