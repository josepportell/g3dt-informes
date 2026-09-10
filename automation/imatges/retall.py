"""Peça 3 del pas 3 d'imatges (2026-09-07): retall del DIBUIX d'un plànol PDF, sense caixetí ni llegenda.

L'Eva no posa mai la pàgina sencera a l'informe: del `tall.pdf` en retalla la secció (l'eix de cotes, les etiquetes dels
punts i els estrats) i deixa fora el mapa de situació, la llegenda, la barra d'escala, el logo de G3 i el caixetí
(7/7 signats). Aquí es troba aquest rectangle de manera determinista, amb el contingut vectorial de la pàgina:

1. **Nucli**: els farciments amples i de color (els estrats). Un `tall.pdf` sempre en té: són el dibuix.
2. **Finestra**: el nucli eixamplat (per defecte 25 % a l'esquerra per a l'eix de cotes, 15 % a la dreta, 75 % de
   l'alçada a dalt per a les etiquetes «P-1»/«A'» —i com a mínim 40 mm: les etiquetes pengen 15-32 mm sobre els
   estrats als 7 signats, i una secció curta (30 mm) no hi arribava—, 20 % a baix per als «Nb=R»). Res de fora hi
   entra mai.
3. **Creixement fins al buit blanc**: dins la finestra, s'hi afegeixen els traços i les paraules que toquen el que ja
   tenim (a menys de 5 mm) fins que no en queda cap de contigu. La franja de la llegenda i el mapa queden fora perquè
   entre ells i la secció hi ha blanc. «Blanc» són 5 mm en absolut, no una fracció de l'alçada del nucli: mesurat als
   7 signats (2026-09-09), els números de l'eix de cotes són a 0,4-3,7 mm de la barra (l'Eva els posa 7/7) i la
   llegenda mai a menys de 16 mm de la secció (l'Eva la deixa fora 7/7).

**Un traç són tants objectes com rectangles.** El FreeHand exporta com a UN SOL traç un grup de línies o guions
separats (la línia superior de la caixa de la llegenda i la línia del terreny de la secció alhora; les dues línies
d'una caixa): la seva caixa englobant abasta l'espai entre elles sense cap tinta a dins, i entrava al nucli com un
«estrat» ample i ple (Linyola i Vilanova: 49 i 73 mm de llegenda i plànol a sobre de la secció). `_ink_rects` mira
la tinta (cada rectangle del traç), no la caixa.

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
GAP_MM = 5.0               # «blanc» = més de 5 mm (eix de cotes a 0,4-3,7 mm; llegenda mai a menys de 16 mm; 7 signats)
PAD_LEFT, PAD_RIGHT = 0.25, 0.15
PAD_UP, PAD_DOWN = 0.75, 0.20
PAD_UP_MIN_MM = 40.0       # les etiquetes «P-n»/«A-A'» pengen 15-32 mm sobre els estrats (7 signats, 2026-09-09)
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


def _ink_rects(d) -> list:
    """Rectangles amb TINTA d'un traç. Si tots els items són rectangles (línies, guions, marcs que el FreeHand agrupa en
    un sol traç), cada rectangle és un objecte; si no (polígons dels estrats, corbes), la caixa del traç."""
    import fitz
    items = d.get("items") or []
    if items and all(it[0] == "re" for it in items):
        return [fitz.Rect(it[1]) for it in items]
    return [fitz.Rect(d["rect"])]


def detect_section_region(page, *, gap_mm: float = GAP_MM, pad_left: float = PAD_LEFT, pad_right: float = PAD_RIGHT,
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
        fill = d.get("fill")
        if not fill:
            continue
        if max(fill) - min(fill) < 0.06 and min(fill) > 0.9:      # blanc: caixa de la llegenda, no un estrat
            continue
        for r in _ink_rects(d):                                     # la tinta, no la caixa del traç
            if r.y1 > y_bottom or r.width < CORE_MIN_WIDTH * W or r.width > 0.97 * W:
                continue
            if abs(r.get_area()) < CORE_MIN_AREA * page_area or _covered(r, images):
                continue
            core |= r
            found += 1
    if not found:
        return None

    cw, chh = core.width, core.height
    window = fitz.Rect(max(0, core.x0 - pad_left * cw), max(0, core.y0 - max(pad_up * chh, PAD_UP_MIN_MM / 25.4 * 72)),
                       min(W, core.x1 + pad_right * cw), min(y_bottom, core.y1 + pad_down * chh))
    items = []
    for d in draws:
        for r in _ink_rects(d):
            if r.width < 0.97 * W and r.height < 0.97 * H and _inside(window, r) and not _covered(r, images):
                items.append(r)
    for w in words:
        r = fitz.Rect(w[0], w[1], w[2], w[3])
        if _inside(window, r) and not _covered(r, images):
            items.append(r)

    box = fitz.Rect(core)
    tol = gap_mm / 25.4 * 72
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


# --------------------------------------------------------------------------------------------------------------
# Peça 5 del pas 3 (2026-09-08): la FIGURA DE SITUACIÓ, els dos mapes del mateix full, recomposats.
#
# L'Eva obre l'informe amb dos mapes de costat: el topogràfic del municipi amb el punt vermell i, a la dreta,
# l'ortofoto o el topogràfic ampliat amb la zona en taronja (7/7 signats; a Bell-lloc són dos retalls del plànol de
# l'arquitecte i a Anciles la Sede del Catastro). Aquells dos mapes són exactament els dos que ja té a dalt del full
# «plànol de situació», sobre el dibuix amb punts que fa servir la peça 4.
#
# El nucli de cada mapa és una imatge incrustada; el creixement fins al blanc hi afegeix el marc i el que ella hi
# dibuixa a sobre (la fletxa que uneix els dos mapes, el rectangle de la zona). Les altres imatges del full —l'altre
# mapa, el dibuix gran, la fletxa de nord, el logo— són zones excloses, i el caixetí, límit dur.
#
# **L'ordre es decideix amb els rectangles ORIGINALS, abans de créixer.** És l'única cosa d'aquesta peça que es va
# haver de mesurar dues vegades: ordenar els rectangles ja crescuts sembla igual i no ho és, perquè el creixement d'un
# mapa li pot moure la vora esquerra per davant de l'altre i els inverteix. Amb l'ordre pres abans de créixer, els
# quatre projectes que hi encerten donen la mateixa imatge que el signat; amb l'ordre pres després, només dos.
#
# Mesurat sobre els 7 signats (peça 5): Castellar (phash 10), Rubí (6), Alcoletge (4) i Anciles (10) idèntics al
# signat. Linyola queda a 18 (la mateixa figura a ull: els seus dos retalls porten una mica més de marge vertical) i
# Bell-lloc fa una altra cosa (dos retalls del plànol de l'arquitecte, «Font: Projecte»).

SIT_MAP_MIN_AREA = 0.03    # àrea mínima per ser un «mapa» i no la fletxa de nord ni el logo
SIT_GAP = 0.01             # tolerància del creixement, en fracció de l'alçada del mapa
SIT_WINDOW = 0.10          # finestra al voltant del mapa
SIT_SEPARATION = 0.02      # separació blanca entre els dos mapes, en fracció de l'alçada


def _grow_to_white(page, core, others, y_bottom, gap: float, window: float):
    """El rectangle del mapa amb el que el toca, fins a trobar blanc. Coordenades sense girar."""
    import fitz

    W, H = page.mediabox.width, page.mediabox.height
    box = fitz.Rect(core)
    win = fitz.Rect(max(0, core.x0 - window * core.width), max(0, core.y0 - window * core.height),
                    min(W, core.x1 + window * core.width), min(H, core.y1 + window * core.height))
    items = []
    for d in page.get_drawings():
        r = fitz.Rect(d["rect"])
        if r.width < 0.97 * W and r.height < 0.97 * H and _inside(win, r) and not _covered(r, others):
            items.append(r)
    for w in page.get_text("words"):
        r = fitz.Rect(w[0], w[1], w[2], w[3])
        if _inside(win, r) and not _covered(r, others):
            items.append(r)
    tol = gap * core.height
    changed = True
    while changed:
        changed = False
        rest = []
        for r in items:
            if _touches(box, r, tol):
                box = _union(box, r)
                changed = True
            else:
                rest.append(r)
        items = rest
    return box & fitz.Rect(0, 0, W, y_bottom)


def detect_situation_maps(page, *, gap: float = SIT_GAP, window: float = SIT_WINDOW):
    """Els dos mapes de situació del full, en ordre de lectura (esquerra→dreta, dalt→baix) i girats com `page.rect`.

    `None` si el full no en té dos de prou grans (aleshores no hi ha figura de situació: mai se n'inventa una).
    """
    import fitz

    W, H = page.mediabox.width, page.mediabox.height
    rects = [fitz.Rect(r) for im in page.get_images(full=True) for r in page.get_image_rects(im[0])]
    if len(rects) < 3:                       # el dibuix gran + dos mapes com a mínim
        return None
    rects.sort(key=lambda r: abs(r.get_area()), reverse=True)
    if abs(rects[0].get_area()) < PLAN_CORE_MIN_AREA * W * H:
        return None                          # cap dibuix gran: no és el full net sinó l'export imprimible del
                                             # FreeHand, amb el raster en tires (algunes passen del 3 % de la pàgina
                                             # i es farien passar per mapes). Mateix filtre que la peça 4.
    maps = [r for r in rects[1:] if abs(r.get_area()) >= SIT_MAP_MIN_AREA * W * H][:2]
    if len(maps) < 2:
        return None
    # ORDRE DE LECTURA del full amb els rectangles originals (vegeu la nota de dalt): d'esquerra a dreta i, quan
    # tots dos són a la mateixa columna, de dalt a baix — a Castellar i Alcoletge els dos mapes queden l'un sobre
    # l'altre al full i l'Eva els posa de costat, el de dalt a l'esquerra.
    maps.sort(key=lambda r: (lambda q: (round(q.x0, 1), round(q.y0, 1)))(r * page.rotation_matrix))

    words = page.get_text("words")
    ys = [w[1] for w in words if w[4].lower().strip(":.") in TITLE_BLOCK_WORDS]
    y_bottom = min(ys) if ys else H
    out = []
    for core in maps:
        others = [r for r in rects if r is not core]
        out.append((_grow_to_white(page, core, others, y_bottom, gap, window) * page.rotation_matrix) & page.rect)
    return out


def compose_situation(pdf_path: Path, output_path: Path, *, page_number: int = 0, dpi: int = 200,
                      separation: float = SIT_SEPARATION) -> Path | None:
    """Renderitza els dos mapes del full i els posa de costat, a la mateixa alçada, sobre blanc.

    `None` si el full no té dos mapes (qui crida no imprimeix cap figura de situació).
    """
    try:
        import fitz
        from PIL import Image

        doc = fitz.open(str(pdf_path))
        page = doc[page_number]
        clips = detect_situation_maps(page)
        if not clips:
            doc.close()
            log.info("Sense dos mapes de situació a %s p%d", pdf_path.name, page_number + 1)
            return None
        tiles = []
        for clip in clips:
            if clip.width < 20 or clip.height < 20:
                doc.close()
                return None
            pix = page.get_pixmap(dpi=dpi, clip=clip)
            tiles.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
        doc.close()

        h = max(t.height for t in tiles)
        tiles = [t if t.height == h else t.resize((max(1, round(t.width * h / t.height)), h), Image.LANCZOS)
                 for t in tiles]
        sep = round(separation * h)
        comp = Image.new("RGB", (sum(t.width for t in tiles) + sep * (len(tiles) - 1), h), (255, 255, 255))
        x = 0
        for t in tiles:
            comp.paste(t, (x, 0))
            x += t.width + sep
        output_path.parent.mkdir(parents=True, exist_ok=True)
        comp.save(str(output_path))
        log.info("Figura de situació de %s → %s (%d×%d)", pdf_path.name, output_path.name, comp.width, comp.height)
        return output_path
    except Exception as exc:
        log.warning("No s'ha pogut compondre la figura de situació de %s: %s", pdf_path.name, exc)
        return None
