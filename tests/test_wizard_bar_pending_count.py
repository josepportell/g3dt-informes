"""Esmena de revisio: `_wizardBarPendingCount()` comptava de mes
(`templates/validation/review.html`).

Bug (verificat al navegador): `_wizardBarPendingCount()` i
`scrollToFirstPendingField()` feien `querySelectorAll('.source-badge.revisar,
.estat-badge.candidats, .estat-badge.no_trobat')` sobre `#wizardForm`. La
llegenda de colors (`#sourceLegend`, Bloc D) viu dins de `#wizardForm` i conte
una mostra `<span class="source-badge revisar">` nomes per ensenyar el color
-- es comptava com a camp pendent real, sumant sempre 1 de mes ("Queda 1 camp
a revisar" quan no en quedava cap).

A mes, un mateix camp pot tenir alhora el badge `.source-badge.revisar`
(`#src-<field>`) i un `.estat-badge` (candidats/no_trobat) al mateix
contenidor (`_lecturaRenderFieldBadge` els afegeix com a germans) -- calia
comptar CAMPS, no badges.

Fix: `_wizardBarPendingBadges()` exclou qualsevol badge dins de
`.source-legend` i dedupica per `.wizard-field`. `_wizardBarPendingCount()` i
`scrollToFirstPendingField()` en depenen (una sola font de veritat).

Mateix metode que `tests/test_review_html_lectura_ui.py`: s'extreu la funcio
real de `review.html` i s'executa sota Node amb un DOM fals minimalista.
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from tests.test_review_html_lectura_ui import REVIEW_HTML, _extract_block

_BLOCKS = [
    "function _wizardBarPendingBadges(",
    "function _wizardBarPendingCount(",
]


def _extracted_source() -> str:
    src = REVIEW_HTML.read_text(encoding="utf-8")
    return "\n\n".join(_extract_block(src, header) for header in _BLOCKS)


# DOM fals minimalista: nomes el que `_wizardBarPendingBadges` toca
# (`document.getElementById`, `querySelectorAll` amb selectors de classe
# compostos separats per comes, `closest` amb un sol selector de classe).
_HARNESS = r"""
'use strict';

function matchesSimpleSelector(el, sel) {
    const classes = sel.trim().split('.').filter(Boolean);
    const elClasses = (el.className || '').split(/\s+/).filter(Boolean);
    return classes.every((c) => elClasses.includes(c));
}

function mkEl(tag, className) {
    const el = {
        tag: tag,
        className: className || '',
        children: [],
        parent: null,
        appendChild(c) { c.parent = el; el.children.push(c); return c; },
        closest(sel) {
            let cur = el;
            while (cur) {
                if (matchesSimpleSelector(cur, sel)) return cur;
                cur = cur.parent;
            }
            return null;
        },
        querySelectorAll(selectorList) {
            const selectors = selectorList.split(',').map((s) => s.trim());
            const results = [];
            const walk = (node) => {
                node.children.forEach((child) => {
                    if (selectors.some((s) => matchesSimpleSelector(child, s))) results.push(child);
                    walk(child);
                });
            };
            walk(el);
            return results;
        },
    };
    return el;
}

const _byId = {};
const document = { getElementById: (id) => _byId[id] || null };

// Arbre: llegenda (mostra a excloure) + 4 camps de prova.
const form = mkEl('div');
_byId.wizardForm = form;

const legend = mkEl('div', 'source-legend');
form.appendChild(legend);
legend.appendChild(mkEl('span', 'source-badge revisar')); // mostra de color, NO es un camp

const field1 = mkEl('div', 'wizard-field');
form.appendChild(field1);
const label1 = mkEl('label');
field1.appendChild(label1);
label1.appendChild(mkEl('span', 'source-badge revisar')); // pendent real

const field2 = mkEl('div', 'wizard-field');
form.appendChild(field2);
const label2 = mkEl('label');
field2.appendChild(label2);
label2.appendChild(mkEl('span', 'source-badge')); // no pendent
label2.appendChild(mkEl('span', 'estat-badge candidats')); // pendent real

const field3 = mkEl('div', 'wizard-field');
form.appendChild(field3);
const label3 = mkEl('label');
field3.appendChild(label3);
label3.appendChild(mkEl('span', 'source-badge revisar')); // pendent real
label3.appendChild(mkEl('span', 'estat-badge no_trobat')); // MATEIX camp -> no duplicar

const field4 = mkEl('div', 'wizard-field');
form.appendChild(field4);
field4.appendChild(mkEl('span', 'source-badge')); // no pendent

__EXTRACTED__

console.log(JSON.stringify({
    count: _wizardBarPendingCount(),
    first: _wizardBarPendingBadges()[0] ? _wizardBarPendingBadges()[0].className : null,
}));
"""


@pytest.fixture(scope="module")
def result(tmp_path_factory) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node no disponible")
    script = tmp_path_factory.mktemp("wizard-bar-pending-js") / "harness.mjs"
    script.write_text(
        _HARNESS.replace("__EXTRACTED__", _extracted_source()),
        encoding="utf-8",
    )
    proc = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_legend_sample_not_counted_and_fields_deduped(result):
    # 3 camps pendents reals (field1, field2, field3), NO 4 (llegenda exclosa)
    # ni 4 comptant field3 dues vegades (revisar + estat-badge alhora).
    assert result["count"] == 3, result


def test_first_pending_skips_the_legend(result):
    # El primer pendent ha de ser el del field1, mai la mostra de la llegenda.
    assert result["first"] == "source-badge revisar", result
