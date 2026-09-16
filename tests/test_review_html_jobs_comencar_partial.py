"""Esmena de revisio: `_jobsUpdateComencarButton()` amagava l'avis de recompte
parcial (`templates/validation/review.html`).

Bug: quan `/api/jobs/estimate` no pot recorrer la carpeta sencera (tall de
xarxa al principi del recorregut, `count_claude_documents` a
`automation/lectura/inventory.py`) torna `partial: true` amb `n_docs` sovint a
0 -- una xifra incompleta, no "cap document". La branca `else if
(!data.n_docs)` es mirava ABANS de `data.partial` i pintava «Tria la carpeta
del projecte» amb el boto desactivat, tapant el `data.text` informatiu («no he
pogut mirar tota la carpeta…») i impedint que l'Eva continués (l'accio
`preparar` es valida igualment: el job real fa l'inventari complet).

Fix: `data.partial` es comprova abans de `!data.n_docs`; si es parcial es
mostra `data.text` i el boto es queda actiu.

Aqui nomes es fa una comprovacio estatica de l'ordre de les dues branques dins
del text de la funcio real (extreta de `review.html` amb el mateix mecanisme
que `tests/test_review_html_lectura_ui.py`) -- si algu torna a invertir-les,
aquest test ho detecta sense necessitat d'executar la funcio sota Node.
"""

from __future__ import annotations

from tests.test_review_html_lectura_ui import REVIEW_HTML, _extract_block

_HEADER = "async function _jobsUpdateComencarButton("


def _function_source() -> str:
    src = REVIEW_HTML.read_text(encoding="utf-8")
    return _extract_block(src, _HEADER)


def test_partial_branch_exists_before_no_docs_branch():
    fn = _function_source()
    assert "data.partial" in fn, "la branca de recompte parcial ha desaparegut"
    assert "!data.n_docs" in fn, "la branca de carpeta sense documents ha desaparegut"

    partial_idx = fn.index("data.partial")
    no_docs_idx = fn.index("!data.n_docs")
    assert partial_idx < no_docs_idx, (
        "`data.partial` s'ha de comprovar ABANS que `!data.n_docs`: si no, un "
        "recompte parcial amb n_docs=0 mostra «Tria la carpeta del projecte» "
        "en lloc de l'avis informatiu de tall de xarxa"
    )
