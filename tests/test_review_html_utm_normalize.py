"""`normalizeUtmXyDecimal` (`templates/validation/review.html`) — rèplica JS
de `contract.normalize_utm_xy_decimal` (Python).

Vegeu docs/troballes/TROBALLA-UTM-COMA-DECIMAL-2026-09-17.md. La taula de
casos ha de coincidir EXACTAMENT amb la de `tests/test_lectura_contract.py`
(`test_normalize_utm_xy_decimal_table`): les dues implementacions han de
donar el mateix resultat per al mateix input.

El revisor (2026-09-17) hi va trobar una divergència real: `parseFloat` és
tolerant amb sufixos no numèrics ("308.78X" → `308.78`) mentre que el
`float()` de Python llança `ValueError` i deixa el valor intacte. Es fixa
amb una regex estricta (`/^-?\\d+(\\.\\d+)?$/`) abans de confiar en
`parseFloat`; `test_normalize_utm_xy_decimal_rejects_garbage_suffix` cobreix
justament aquest cas.

Mateix mètode que `tests/test_review_html_source_label.py`: s'extreu la
funció real de `review.html` i s'executa sota Node.
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from tests.test_review_html_lectura_ui import REVIEW_HTML, _extract_block

_BLOCKS = ["function normalizeUtmXyDecimal("]


def _extract_const_statement(src: str, header: str) -> str:
    """Un `const X = <literal>;` sense claus: `_extract_block` no serveix
    (busca la primera `{` del fitxer, que no té res a veure)."""
    start = src.index(header)
    end = src.index(";", start)
    return src[start:end + 1]


# Mateixos casos que `test_normalize_utm_xy_decimal_table` a
# tests/test_lectura_contract.py — mantenir les dues taules sincronitzades.
_CASES = [
    ("308781,86", "308781.86"),
    ("308.781,86", "308781.86"),
    ("4613950.63", "4613950.63"),
    ("314418.9", "314418.9"),
    ("308781", "308781"),
    ("-308781,86", "-308781.86"),
    ("-308.781,86", "-308781.86"),
    ("4.613.950", "4613950"),
    ("4.613.950,63", "4613950.63"),
    ("308.781", "308781"),
    ("", ""),
    # cas del revisor: un sol punt, sufix no numèric -> intacte (NO
    # "30878X"; `parseFloat` no ha de decidir aquí).
    ("308.78X", "308.78X"),
]


def _extracted_source() -> str:
    src = REVIEW_HTML.read_text(encoding="utf-8")
    const = _extract_const_statement(src, "const UTM_XY_MIN_PLAUSIBLE = ")
    fn = "\n\n".join(_extract_block(src, header) for header in _BLOCKS)
    return const + "\n\n" + fn


_HARNESS = r"""
'use strict';

__EXTRACTED__

const inputs = __INPUTS__;
console.log(JSON.stringify(inputs.map((s) => normalizeUtmXyDecimal(s))));
"""


@pytest.fixture(scope="module")
def normalized(tmp_path_factory) -> list[str]:
    node = shutil.which("node")
    if not node:
        pytest.skip("node no disponible")
    script = tmp_path_factory.mktemp("utm-normalize-js") / "harness.mjs"
    script.write_text(
        _HARNESS
        .replace("__EXTRACTED__", _extracted_source())
        .replace("__INPUTS__", json.dumps([c[0] for c in _CASES])),
        encoding="utf-8",
    )
    proc = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


@pytest.mark.parametrize("raw, expected", _CASES)
def test_normalize_utm_xy_decimal_js(normalized, raw, expected):
    idx = [c[0] for c in _CASES].index(raw)
    assert normalized[idx] == expected, f"{raw!r} -> {normalized[idx]!r} (esperat {expected!r})"


def test_normalize_utm_xy_decimal_rejects_garbage_suffix(normalized):
    # Redundant amb la taula de dalt, però deixa explícit el cas que el
    # revisor va reproduir amb Node: abans d'aquesta correcció donava
    # "30878X" (parseFloat tolerant), no "308.78X" (intacte, com Python).
    idx = [c[0] for c in _CASES].index("308.78X")
    assert normalized[idx] == "308.78X"


# ---------------------------------------------------------------------------
# _updateUtmWarning — l'avís no s'ha de quedar enganxat en canviar de
# projecte (troballa 2 del revisor, 2026-09-17): l'element `.utm-warning` és
# un node DOM estàtic, reutilitzat per a tots els projectes.
# ---------------------------------------------------------------------------

_WARNING_HARNESS = r"""
'use strict';

function _mkEl() {
    const children = [];
    return {
        value: '',
        className: '',
        textContent: '',
        appendChild(c) { children.push(c); return c; },
        querySelector(sel) {
            if (sel === '.utm-warning') return children.find((c) => c.className === 'utm-warning') || null;
            return null;
        },
    };
}
const document = {
    createElement() { return { className: '', textContent: '' }; },
};

__EXTRACTED__

// Simula el node DOM ESTÀTIC `wiz-utm_x` reutilitzat entre dos projectes.
const el = _mkEl();
el.parentElement = el; // el warning penja del mateix contenidor fake

const steps = [];

// Projecte 1: valor espatllat -> input.value queda buit -> avís visible.
el.value = '';
_updateUtmWarning(el, '30878X');
steps.push(el.querySelector('.utm-warning') ? el.querySelector('.utm-warning').textContent : null);

// Projecte 2 (canvi de projecte): valor bo -> l'avís ha de desaparèixer.
el.value = '308781.86';
_updateUtmWarning(el, '308781.86');
steps.push(el.querySelector('.utm-warning') ? el.querySelector('.utm-warning').textContent : null);

console.log(JSON.stringify(steps));
"""


def test_utm_warning_does_not_leak_across_project_switch(tmp_path_factory):
    node = shutil.which("node")
    if not node:
        pytest.skip("node no disponible")
    src = REVIEW_HTML.read_text(encoding="utf-8")
    extracted = "\n\n".join(
        _extract_block(src, header) for header in ["function _updateUtmWarning("]
    )
    script = tmp_path_factory.mktemp("utm-warning-js") / "harness.mjs"
    script.write_text(_WARNING_HARNESS.replace("__EXTRACTED__", extracted), encoding="utf-8")
    proc = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    steps = json.loads(proc.stdout)
    assert steps[0], "el projecte espatllat hauria de mostrar l'avís"
    assert steps[1] == "", f"l'avís del projecte anterior s'ha quedat enganxat: {steps[1]!r}"
