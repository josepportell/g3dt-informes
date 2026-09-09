#!/usr/bin/env python3
"""Peça 7a (2026-09-08): la plantilla parteix la ranura única de figura en tres blocs amb peu propi i nombre variable.

Abans (peça 1): a l'1.1 hi havia `fig_cadastre_image` (taula d'una cel·la, peu «Situació de la zona d'estudi.») i
`fig_main_plan_image` (peu de Bell-lloc, «Ubicació de l'habitatge a l'interior de la parcel·la. Font: Projecte.»),
i el retall del dibuix amb punts de la peça 4 s'imprimia sota aquest peu a quatre projectes d'assaigs.

Després (D11 del pas 2, GO Josep 2026-09-08):
  1.1  {%p if not fig_situacio_image_2 %} taula 1 cel·la  + «Figura N. Situació de la zona d'estudi.» {%p endif %}
       {%p if fig_situacio_image_2 %}     dues imatges en línia + «Figura N i Figura N+1. Detall de la ubicació de
                                          la parcel·la en estudi. Font: Projecte.» {%p endif %}        (Bell-lloc;
                                          sense taula nova: l'extractor aparella les taules per ordre)
       {%p if fig_projecte_image_1 %} imatge + «Figura N. {{ fig_projecte_caption_1 }}» {%p endif %}   (0-2)
       {%p if fig_projecte_image_2 %} imatge + «Figura N. {{ fig_projecte_caption_2 }}» {%p endif %}
  2.2  {%p if fig_assaigs_image %}    imatge + «Figura N. Situació de l'estructura projectada i els assaigs
                                          realitzats.» {%p endif %}     (5 de 6 signats la posen al 2.2)

Tot es clona d'elements que ja hi són (la taula de situació, els paràgrafs `{%p if %}` / `{%p endif %}` del bloc de
vistes generals, el paràgraf d'imatge i el peu): cap XML escrit a mà, cap taula nova.

Ús:  PYTHONPATH=$PWD .venv/bin/python docs/imatges/scripts/peca7_plantilla.py [templates/g3dt-jinja-template.docx]
Idempotent: si la plantilla ja té `fig_assaigs_image`, no fa res.
"""
from __future__ import annotations

import copy
import shutil
import sys
import zipfile
from pathlib import Path

from lxml import etree

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
REPO = Path(__file__).resolve().parents[3]

CAP_SIT_1 = "Figura {{ fig_situacio_num }}. Situació de la zona d'estudi."
CAP_SIT_2 = ("Figura {{ fig_situacio_num }} i Figura {{ fig_situacio_2_num }}. Detall de la ubicació de la parcel·la "
             "en estudi. Font: Projecte.")
CAP_PROJ = "Figura {{ fig_projecte_%d_num }}. {{ fig_projecte_caption_%d }}"
CAP_ASSAIGS = "Figura {{ fig_assaigs_num }}. Situació de l'estructura projectada i els assaigs realitzats."


def _text(p) -> str:
    return "".join(t.text or "" for t in p.iter(W + "t"))


def _set_text(p, text: str) -> None:
    """Deixa un sol run amb el text (conserva el `rPr` del primer run)."""
    runs = list(p.iter(W + "r"))
    if not runs:
        raise ValueError(f"paràgraf sense runs: {_text(p)!r}")
    first = runs[0]
    for r in runs[1:]:
        r.getparent().remove(r)
    for t in list(first.iter(W + "t")):
        first.remove(t)
    t = etree.SubElement(first, W + "t")
    t.text = text
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")


def _clone_p(p, text: str):
    q = copy.deepcopy(p)
    _set_text(q, text)
    return q


def _tbl_of(p):
    e = p
    while e is not None and etree.QName(e).localname != "tbl":
        e = e.getparent()
    return e


def transform(doc_xml: bytes) -> bytes:
    root = etree.fromstring(doc_xml)
    body = root.find(W + "body")
    ps = list(body.iter(W + "p"))
    by_text = {_text(p): p for p in ps}
    if "{{ fig_assaigs_image }}" in by_text:
        print("la plantilla ja té la peça 7a: res a fer")
        return doc_xml

    p_sit_img = by_text["{{ fig_cadastre_image }}"]
    p_sit_cap = by_text["Figura {{ fig_cadastre_num }}. Situació de la zona d'estudi."]
    p_plan_img = by_text["{{ fig_main_plan_image }}"]
    p_plan_cap = by_text["Figura {{ fig_main_plan_num }}. Ubicació de l'habitatge a l'interior de la parcel·la. Font: Projecte."]
    p_if_site = by_text["{%p if photo_site_text %}"]
    p_endif_site = [p for p in ps if _text(p) == "{%p endif %}" and ps.index(p) > ps.index(p_if_site)][0]
    p_lab_field = [p for p in ps if _text(p).startswith("Els assaigs in situ han estat realitzats per {{ lab_field_company }}")][0]

    tbl_sit = _tbl_of(p_sit_img)
    assert tbl_sit is not None and tbl_sit.getparent() is body
    n_tbl_before = len(body.findall(W + "tbl"))

    # ── 1.1: bloc de situació (1 imatge) ──
    _set_text(p_sit_img, "{{ fig_situacio_image_1 }}")
    _set_text(p_sit_cap, CAP_SIT_1)
    tbl_sit.addprevious(_clone_p(p_if_site, "{%p if not fig_situacio_image_2 %}"))
    endif_1 = _clone_p(p_endif_site, "{%p endif %}")
    p_sit_cap.addnext(endif_1)

    # ── 1.1: bloc de situació (2 imatges, Bell-lloc): les dues imatges EN LÍNIA dins un sol paràgraf centrat ──
    # No una taula: l'extractor de referència aparella les taules del signat amb les de la plantilla PER ORDRE, i una
    # taula més aquí mou totes les veritats que surten de taules (mesurat 2026-09-08: 23-28 claus per projecte a la
    # deriva amb la taula, 0 sense). Dos `InlineImage` de 70 mm en un mateix paràgraf queden de costat.
    if_2 = _clone_p(p_if_site, "{%p if fig_situacio_image_2 %}")
    img_2 = _clone_p(p_plan_img, "{{ fig_situacio_image_1 }}  {{ fig_situacio_image_2 }}")
    cap_2 = _clone_p(p_sit_cap, CAP_SIT_2)
    endif_2 = _clone_p(p_endif_site, "{%p endif %}")
    endif_1.addnext(if_2)
    if_2.addnext(img_2)
    img_2.addnext(cap_2)
    cap_2.addnext(endif_2)

    # ── 1.1: figures del projecte (0-2): el paràgraf d'imatge i el peu que hi havia, reaprofitats ──
    _set_text(p_plan_img, "{{ fig_projecte_image_1 }}")
    _set_text(p_plan_cap, CAP_PROJ % (1, 1))
    if_p1 = _clone_p(p_if_site, "{%p if fig_projecte_image_1 %}")
    endif_p1 = _clone_p(p_endif_site, "{%p endif %}")
    p_plan_img.addprevious(if_p1)
    p_plan_cap.addnext(endif_p1)
    if_p2 = _clone_p(p_if_site, "{%p if fig_projecte_image_2 %}")
    img_p2 = _clone_p(p_plan_img, "{{ fig_projecte_image_2 }}")
    cap_p2 = _clone_p(p_plan_cap, CAP_PROJ % (2, 2))
    endif_p2 = _clone_p(p_endif_site, "{%p endif %}")
    endif_p1.addnext(if_p2)
    if_p2.addnext(img_p2)
    img_p2.addnext(cap_p2)
    cap_p2.addnext(endif_p2)

    # ── 2.2: la figura d'assaigs, després del paràgraf del laboratori de camp (posició de Rubí, la plantilla base) ──
    if_a = _clone_p(p_if_site, "{%p if fig_assaigs_image %}")
    img_a = _clone_p(p_plan_img, "{{ fig_assaigs_image }}")
    cap_a = _clone_p(p_plan_cap, CAP_ASSAIGS)
    endif_a = _clone_p(p_endif_site, "{%p endif %}")
    p_lab_field.addnext(if_a)
    if_a.addnext(img_a)
    img_a.addnext(cap_a)
    cap_a.addnext(endif_a)

    assert len(body.findall(W + "tbl")) == n_tbl_before, "cap taula nova: l'extractor les aparella per ordre"
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def main(path: Path) -> int:
    src = zipfile.ZipFile(path)
    new_doc = transform(src.read("word/document.xml"))
    if new_doc == src.read("word/document.xml"):
        return 0
    bak = path.with_suffix(".docx.bak-peca7")
    shutil.copy2(path, bak)
    tmp = path.with_suffix(".docx.tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as out:
        for item in src.infolist():
            data = new_doc if item.filename == "word/document.xml" else src.read(item.filename)
            out.writestr(item, data)
    src.close()
    tmp.replace(path)
    print(f"plantilla escrita: {path} (còpia a {bak.name})")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "templates" / "g3dt-jinja-template.docx"))
