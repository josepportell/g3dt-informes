"""Esmenes de revisio W1/W2 a `_wizardSourceLabel()` (`templates/validation/review.html`).

El badge de font del wizard tradueix la cadena tecnica que emet
`web/wizard_service.py` a una etiqueta que l'Eva entén (`_wizardSourceLabel`,
prop de `setSourceBadge`). El reviewer hi va trobar dos falsos positius:

1. **"plànol" massa ampla** — qualsevol cadena amb `visió`/`vision` queia a
   "plànol" (p. ex. `vision (fotos camp)`, que és lectura de fotos de camp, no
   el plànol de l'arquitecte). Ara "plànol" nomes surt amb els tokens propis
   del document (`planol`/`plànol`/`A.01`/`architect_plan`) i mai amb "ICGC".
2. **"assaigs de camp" massa ampla** — `xls`/`lab` sols hi bastaven, i per
   tant una COMANDA de laboratori (document administratiu, no un resultat
   d'assaig: `fileminer:comanda laboratori_....xls`) hi queia igual que un
   `DPSH.xls` real. Ara nomes hi entren els tokens de l'assaig i mai si la
   cadena conté "comanda".

Mateix metode que `tests/test_review_html_lectura_ui.py`: s'extreu la funcio
real de `review.html` i s'executa sota Node.
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from tests.test_review_html_lectura_ui import REVIEW_HTML, _extract_block

_BLOCKS = ["function _wizardSourceLabel("]


def _extracted_source() -> str:
    src = REVIEW_HTML.read_text(encoding="utf-8")
    return "\n\n".join(_extract_block(src, header) for header in _BLOCKS)


# Cadena real -> etiqueta esperada. Inclou les cadenes citades explicitament
# al brief de revisio (2026-09-15) mes els casos que en delimiten les regles.
_CASES = [
    ("user", "tu"),
    ("user_data.json anterior", "tu"),
    ("default estandard", "per defecte"),
    ("default (avui)", "per defecte"),
    ("revisar", "revisar"),
    ("groq_llm:PDF V0/LLETRA/4001612_informe_v0.pdf", "el teu informe anterior"),
    ("planol A.01.pdf", "plànol"),
    ("ICGC ortho+visió", "ICGC / Cadastre"),
    ("ICGC WMS 1:50k", "ICGC / Cadastre"),
    ("vision (fotos camp)", "llegit als documents"),
    ("vision_probe:FOTOGRAFIES\\P1.jpeg", "llegit als documents"),
    ("sondeig elevation_z", "assaigs de camp"),
    ("DPSH (2 assaigs)", "assaigs de camp"),
    ("DPSH/Lab PDF", "assaigs de camp"),
    ("2.5×Nb (Nb=30.3)", "calculat"),
    ("Terzaghi-Peck", "calculat"),
    ("granular net (signat Bell-lloc, Anciles 2)", "calculat"),
    ("CTE D.23 banda baixa …", "calculat"),
    ("llm_synthesis_with_observations", "llegit als documents"),
    ("fileminer:comanda laboratori_3001722_VACARISSES.xls", "llegit als documents"),
    ("docs intel (PRESSUPOST OBRA block)", "llegit als documents"),
    ("Eva template: 'Vacarisses' (tier 1)", "el teu informe anterior"),
    ("plantilla", "el teu informe anterior"),
    ("computed (slope 3%)", "calculat"),
    ("contingut:ANNEXES/ALTRES/COORDENADES.txt", "llegit als documents"),
    ("lectura", "llegit als documents"),
]

_HARNESS = r"""
'use strict';

__EXTRACTED__

const inputs = __INPUTS__;
console.log(JSON.stringify(inputs.map((s) => _wizardSourceLabel(s).label)));
"""


@pytest.fixture(scope="module")
def labels(tmp_path_factory) -> list[str]:
    node = shutil.which("node")
    if not node:
        pytest.skip("node no disponible")
    script = tmp_path_factory.mktemp("source-label-js") / "harness.mjs"
    script.write_text(
        _HARNESS
        .replace("__EXTRACTED__", _extracted_source())
        .replace("__INPUTS__", json.dumps([c[0] for c in _CASES])),
        encoding="utf-8",
    )
    proc = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


@pytest.mark.parametrize("source, expected", _CASES)
def test_source_label(labels, source, expected):
    idx = [c[0] for c in _CASES].index(source)
    assert labels[idx] == expected, f"{source!r} -> {labels[idx]!r} (esperat {expected!r})"
