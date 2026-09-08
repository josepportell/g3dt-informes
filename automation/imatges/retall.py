"""Peça 3 del pas 3 d'imatges (2026-09-07): retall del DIBUIX d'un plànol PDF, sense caixetí ni llegenda.

L'Eva no posa mai la pàgina sencera a l'informe: del `tall.pdf` en retalla la secció (l'eix de cotes, les etiquetes dels
punts i els estrats) i deixa fora el mapa de situació, la llegenda, la barra d'escala, el logo de G3 i el caixetí
(7/7 signats). Aquí es troba aquest rectangle de manera determinista, amb el contingut vectorial de la pàgina:

1. **Nucli**: els farciments amples i de color (els estrats). Un `tall.pdf` sempre en té: són el dibuix.
2. **Finestra**: el nucli eixamplat (per defecte 25 % a l'esquerra per a l'eix de cotes, 15 % a la dreta, 75 % de
   l'alçada a dalt per a les etiquetes «P-1»/«A'», 20 % a baix per als «Nb=R»). Res de fora hi entra mai.
3. **Creixement fins al buit blanc**: dins la finestra, s'hi afegeixen els traços i les paraules que toquen el que ja
   tenim (amb una tolerància del 5 % de l'alçada del nucli) fins que no en queda cap de contigu. La franja de la
   llegenda i el mapa queden fora perquè entre ells i la secció hi ha blanc.

Límits durs: la franja del caixetí (per sobre del primer text «TÍTOL/TÍTULO/Data/Fecha/Exp/Pàgina») i les imatges
incrustades (el mapa de situació i el logo). Si no hi ha nucli, es retorna `None` i qui crida ha de fer servir la
pàgina sencera (mai s'inventa un retall).

Mesurat sobre els 7 signats (peça 3): 3 retalls idèntics als de l'Eva (phash ≤ 10) i 4 de la mateixa font amb un
enquadrament diferent, cap error; abans, amb la pàgina sencera, 0 idèntics, 5 de la mateixa font i 2 errors.
"""
from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)

#: Textos del caixetí: el dibuix sempre queda per sobre del primer que aparegui.
TITLE_BLOCK_WORDS = {"títol", "titulo", "título", "data", "fecha", "exp", "pàgina", "pagina", "página"}
CORE_MIN_WIDTH = 0.25      # amplada mínima d'un farciment per ser «estrat», en fracció de la pàgina
CORE_MIN_AREA = 0.01       # àrea mínima, en fracció de la pàgina
GAP = 0.05                 # tolerància del creixement, en fracció de l'alçada del nucli
PAD_LEFT, PAD_RIGHT = 0.25, 0.15
PAD_UP, PAD_DOWN = 0.75, 0.20
MARGIN = 0.006             # marge final, en fracció del costat gran de la pàgina


def _covered(rect, zones, share: float = 0.5) -> bool:
    """El rectangle queda dins d'una zona exclosa (mapa, logo). Els traços degenerats (línies d'amplada 0, que a
    `get_drawings` donen àrea 0) es jutgen pel centre: amb l'àrea no es podrien comparar mai."""
    import fitz
    r = fitz.Rect(rect)
    area = abs(r.get_area())
    for z in zones:
        if area < 1e-6:
            if fitz.Rect(z).contains(fitz.Point((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)):
                return True
            continue
        inter = r & z
        if inter.is_valid and abs(inter.get_area()) > share * area:
            return True
    return False


def _touches(box, r, tol: float) -> bool:
    """El rectangle toca la caixa amb una tolerància. Solapament d'AABB, no àrea: les línies verticals de les
    etiquetes «P-1» tenen amplada 0 i qualsevol prova per àrea les deixaria sempre fora."""
    return (r.x0 <= box.x1 + tol and r.x1 >= box.x0 - tol
            and r.y0 <= box.y1 + tol and r.y1 >= box.y0 - tol)


def _inside(outer, r) -> bool:
    """`r` és dins d'`outer`. Per coordenades, no `Rect.contains`: un traç degenerat (amplada o alçada 0) és un
    rectangle «buit» per a PyMuPDF i les operacions de conjunt no s'hi comporten com esperaríem."""
    return outer.x0 <= r.x0 and r.x1 <= outer.x1 and outer.y0 <= r.y0 and r.y1 <= outer.y1


def _union(box, r):
    """Unió que també funciona amb rectangles degenerats (`box |= r` els ignora)."""
    import fitz
    return fitz.Rect(min(box.x0, r.x0), min(box.y0, r.y0), max(box.x1, r.x1), max(box.y1, r.y1))


def detect_section_region(page, *, gap: float = GAP, pad_left: float = PAD_LEFT, pad_right: float = PAD_RIGHT,
                          pad_up: float = PAD_UP, pad_down: float = PAD_DOWN):
    """Rectangle del dibuix dins la pàgina (`fitz.Rect`), o `None` si no s'hi troba cap nucli d'estrats."""
    import fitz

    W, H = page.rect.width, page.rect.height
    page_area = W * H
    words = page.get_text("words")
    draws = page.get_drawings()

    ys = [w[1] for w in words if w[4].lower().strip(":.") in TITLE_BLOCK_WORDS]
    y_bottom = min(ys) if ys else H
    images = [fitz.Rect(r) for im in page.get_images(full=True) for r in page.get_image_rects(im[0])]

    core = fitz.Rect(W, H, 0, 0)
    found = 0
    for d in draws:
        r = d["rect"]
        fill = d.get("fill")
        if not fill or r.y1 > y_bottom or r.width < CORE_MIN_WIDTH * W or r.width > 0.97 * W:
            continue
        if abs(r.get_area()) < CORE_MIN_AREA * page_area or _covered(r, images):
            continue
        if max(fill) - min(fill) < 0.06 and min(fill) > 0.9:      # blanc: caixa de la llegenda, no un estrat
            continue
        core |= r
        found += 1
    if not found:
        return None

    cw, chh = core.width, core.height
    window = fitz.Rect(max(0, core.x0 - pad_left * cw), max(0, core.y0 - pad_up * chh),
                       min(W, core.x1 + pad_right * cw), min(y_bottom, core.y1 + pad_down * chh))
    items = []
    for d in draws:
        r = fitz.Rect(d["rect"])
        if r.width < 0.97 * W and r.height < 0.97 * H and _inside(window, r) and not _covered(r, images):
            items.append(r)
    for w in words:
        r = fitz.Rect(w[0], w[1], w[2], w[3])
        if _inside(window, r) and not _covered(r, images):
            items.append(r)

    box = fitz.Rect(core)
    tol = gap * chh
    changed = True
    while changed:                       # creix mentre hi hagi contingut contigu; s'atura al blanc
        changed = False
        rest = []
        for r in items:
            if _touches(box, r, tol):
                box = _union(box, r)
                changed = True
            else:
                rest.append(r)
        items = rest

    m = MARGIN * max(W, H)
    return fitz.Rect(max(0, box.x0 - m), max(0, box.y0 - m), min(W, box.x1 + m), min(y_bottom, box.y1 + m))


def crop_drawing(pdf_path: Path, output_path: Path, *, page_number: int = 0, dpi: int = 200) -> Path | None:
    """Renderitza NOMÉS el dibuix de la pàgina a `output_path`. `None` si no s'hi troba (qui crida fa la pàgina sencera)."""
    try:
        import fitz
        doc = fitz.open(str(pdf_path))
        page = doc[page_number]
        clip = detect_section_region(page)
        if clip is None or clip.width < 20 or clip.height < 20:
            doc.close()
            log.info("Sense dibuix detectat a %s p%d: cal la pàgina sencera", pdf_path.name, page_number + 1)
            return None
        output_path.parent.mkdir(parents=True, exist_ok=True)
        page.get_pixmap(dpi=dpi, clip=clip).save(str(output_path))
        doc.close()
        log.info("Retall del dibuix de %s → %s (%.0f×%.0f pt)", pdf_path.name, output_path.name, clip.width, clip.height)
        return output_path
    except Exception as exc:
        log.warning("No s'ha pogut retallar el dibuix de %s: %s", pdf_path.name, exc)
        return None


# --------------------------------------------------------------------------------------------------------------
# Peça 4 del pas 3 (2026-09-08): el DIBUIX AMB PUNTS del full «plànol de situació» de l'Eva.
#
# La figura del capítol 2.2 («…i els assaigs realitzats», 6/7 signats) i la del projecte a Bell-lloc i Vilanova
# surten totes del mateix lloc: el full d'annex que l'Eva dibuixa al FreeHand ABANS d'obrir el wizard (memòria
# `eva_workflow_annexes_before_wizard`). Aquell full és sempre igual: dos mapes de situació petits a dalt, el
# plànol o l'ortofoto GRAN a sota amb els punts d'assaig que ella hi posa, la fletxa de nord, el logo de G3 i el
# caixetí. El dibuix que va a l'informe és la imatge gran, amb les cotes i les etiquetes que hi ha dibuixat a sobre.
#
# Per això aquí el nucli NO són els farciments (`detect_section_region`, que serveix per al tall): és la imatge
# incrustada més gran de la pàgina. Al voltant s'hi afegeix, com a la peça 3, el que la toca fins a trobar blanc —
# les cotes vermelles i les etiquetes «P-1» que l'Eva dibuixa a fora de la imatge. Les altres imatges (els dos
# mapes, el nord, el logo) són zones excloses, i el caixetí és un límit dur.
#
# Dues diferències de mecànica respecte de la peça 3, totes dues per la mateixa raó — aquests fulls són A3
# VERTICAL girats 270°:
#   * `get_images` / `get_drawings` / `get_text` donen coordenades SENSE girar, i `page.rect` les dona girades.
#     Tota la geometria es fa sense girar i el rectangle final es passa per `page.rotation_matrix`.
#   * la tolerància del creixement és 1 % de l'alçada del nucli, no 5 %: aquí el nucli és el dibuix sencer (40 %
#     de la pàgina) i no una franja d'estrats. Mesurat: 0,5 %, 1 % i 2 % donen el mateix resultat als 7 projectes;
#     a partir del 5 % el creixement salta a la llegenda d'Anciles i al 10 % als mapes de Castellar i Rubí.
#
# Mesurat sobre els 7 signats (peça 4): 6 retalls idèntics als de l'Eva (phash ≤ 10) — Castellar, Rubí, Alcoletge
# i Anciles a la figura d'assaigs, Bell-lloc i Vilanova a la del projecte — i 1 de font diferent (Linyola, que va
# fer servir la planta del projecte de l'arquitecte i no el seu propi annex).

PLAN_CORE_MIN_AREA = 0.15   # àrea mínima de la imatge gran, en fracció de la pàgina: descarta els fulls «impresos»
PLAN_GAP = 0.01             # tolerància del creixement, en fracció de l'alçada del nucli
PLAN_WINDOW = 0.15          # finestra al voltant del nucli: res de més enllà no hi entra mai


def detect_plan_region(page, *, gap: float = PLAN_GAP, window: float = PLAN_WINDOW):
    """Rectangle del dibuix amb punts dins la pàgina, ja girat com `page.rect`.

    `None` si la pàgina no té cap imatge incrustada prou gran (els `pl situ.pdf` de l'arrel són exports de
    FreeHand amb el raster tallat en centenars de tires: cap d'elles és el dibuix). Qui crida ha de provar el
    candidat següent; mai s'inventa un retall.
    """
    import fitz

    W, H = page.mediabox.width, page.mediabox.height        # espai SENSE girar
    rects = [fitz.Rect(r) for im in page.get_images(full=True) for r in page.get_image_rects(im[0])]
    if not rects:
        return None
    core = max(rects, key=lambda r: abs(r.get_area()))
    if abs(core.get_area()) < PLAN_CORE_MIN_AREA * W * H:
        return None
    others = [r for r in rects if r != core]

    words = page.get_text("words")
    ys = [w[1] for w in words if w[4].lower().strip(":.") in TITLE_BLOCK_WORDS and w[1] > core.y0]
    y_bottom = min(ys) if ys else H
    page_box = fitz.Rect(0, 0, W, y_bottom)
    box = fitz.Rect(core) & page_box

    win = fitz.Rect(max(0, core.x0 - window * core.width), max(0, core.y0 - window * core.height),
                    min(W, core.x1 + window * core.width), min(y_bottom, core.y1 + window * core.height))
    items = []
    for d in page.get_drawings():
        r = fitz.Rect(d["rect"])
        if r.width < 0.97 * W and r.height < 0.97 * H and _inside(win, r) and not _covered(r, others):
            items.append(r)
    for w in words:
        r = fitz.Rect(w[0], w[1], w[2], w[3])
        if _inside(win, r) and not _covered(r, others):
            items.append(r)

    tol = gap * core.height
    changed = True
    while changed:                       # creix mentre hi hagi contingut contigu; s'atura al blanc
        changed = False
        rest = []
        for r in items:
            if _touches(box, r, tol):
                box = _union(box, r)
                changed = True
            else:
                rest.append(r)
        items = rest

    return (box & page_box) * page.rotation_matrix


def crop_plan(pdf_path: Path, output_path: Path, *, page_number: int = 0, dpi: int = 200) -> Path | None:
    """Renderitza NOMÉS el dibuix amb punts del full de situació. `None` si no s'hi troba (proveu el candidat següent)."""
    try:
        import fitz
        doc = fitz.open(str(pdf_path))
        page = doc[page_number]
        clip = detect_plan_region(page)
        if clip is None or clip.width < 20 or clip.height < 20:
            doc.close()
            log.info("Sense dibuix amb punts a %s p%d", pdf_path.name, page_number + 1)
            return None
        output_path.parent.mkdir(parents=True, exist_ok=True)
        page.get_pixmap(dpi=dpi, clip=clip).save(str(output_path))
        doc.close()
        log.info("Retall del dibuix amb punts de %s → %s (%.0f×%.0f pt)", pdf_path.name, output_path.name,
                 clip.width, clip.height)
        return output_path
    except Exception as exc:
        log.warning("No s'ha pogut retallar el dibuix amb punts de %s: %s", pdf_path.name, exc)
        return None
