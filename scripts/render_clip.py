#!/usr/bin/env python3
"""Zoom sota demanda sobre una pàgina de PDF (fitz/PyMuPDF), perquè el model
no es construeixi l'eina `fitz` per fer un retall (vegeu
`docs/wizard-headless/mesures/probes/2026-08-24-tall-stream-json/turns.md`,
usos 3-5-7-10).

`--clip` en FRACCIONS 0-1 de l'amplada/alçada de la pàgina (no punts, no px):
`0.0,0.30,0.5,0.62` és el 30-62 % de l'alçada, meitat esquerra de l'amplada.
Sense `--clip`, renderitza la pàgina sencera.

`--grid RxC` subdivideix la regió (`--clip` si es dona, si no la pàgina
sencera) en R files x C columnes, cada cel·la ampliada un 10 % de la seva
pròpia mida cap a les cel·les veïnes (mateixa fórmula que les meitats de
`automation/lectura/preext.py`: cel·la de mida `1/N` ampliada `0.10 * (1/N)`
a cada vora interna).

Ús:
    .venv/bin/python scripts/render_clip.py PDF --page 1 --out /tmp/pagina.png
    .venv/bin/python scripts/render_clip.py PDF --page 1 --clip 0.0,0.30,0.5,0.62 --dpi 400 --out /tmp/clip.png
    .venv/bin/python scripts/render_clip.py PDF --page 1 --grid 2x2 --out /tmp/grid.png

Sortida: `OK PNG {w}x{h}px` (una línia; amb `--grid`, una línia per cel·la amb
el path). Errors: `ERROR: ...` a stderr, exit 2.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_GRID_RE = re.compile(r"^(\d+)x(\d+)$", re.IGNORECASE)
_GRID_OVERLAP_FRACTION = 0.10


def _parse_clip(raw: str) -> tuple[float, float, float, float]:
    parts = raw.split(",")
    if len(parts) != 4:
        raise ValueError(f"--clip ha de tenir 4 valors 'x0,y0,x1,y1', trobat {raw!r}")
    x0, y0, x1, y1 = (float(p) for p in parts)
    if not (0.0 <= x0 < x1 <= 1.0 and 0.0 <= y0 < y1 <= 1.0):
        raise ValueError(f"--clip fora de rang o invertit (calen fraccions 0-1, x0<x1, y0<y1): {raw!r}")
    return x0, y0, x1, y1


def _parse_grid(raw: str) -> tuple[int, int]:
    m = _GRID_RE.match(raw.strip())
    if not m:
        raise ValueError(f"--grid ha de ser 'RxC' (p. ex. '2x2'), trobat {raw!r}")
    rows, cols = int(m.group(1)), int(m.group(2))
    if rows < 1 or cols < 1:
        raise ValueError(f"--grid: files/columnes han de ser >= 1, trobat {raw!r}")
    return rows, cols


def _grid_cells(
    base: tuple[float, float, float, float], rows: int, cols: int,
) -> list[tuple[int, int, float, float, float, float]]:
    """Retorna `[(r, c, x0, y0, x1, y1)]` (fraccions), cel·les ampliades un
    10 % de la seva pròpia mida cap a les veïnes internes."""
    bx0, by0, bx1, by1 = base
    cell_w = (bx1 - bx0) / cols
    cell_h = (by1 - by0) / rows
    ow = cell_w * _GRID_OVERLAP_FRACTION
    oh = cell_h * _GRID_OVERLAP_FRACTION

    cells = []
    for r in range(rows):
        for c in range(cols):
            x0 = bx0 + c * cell_w - (ow if c > 0 else 0.0)
            x1 = bx0 + (c + 1) * cell_w + (ow if c < cols - 1 else 0.0)
            y0 = by0 + r * cell_h - (oh if r > 0 else 0.0)
            y1 = by0 + (r + 1) * cell_h + (oh if r < rows - 1 else 0.0)
            cells.append((r, c, max(bx0, x0), max(by0, y0), min(bx1, x1), min(by1, y1)))
    return cells


def _fraction_rect_to_points(page, x0: float, y0: float, x1: float, y1: float):
    import fitz

    rect = page.rect
    return fitz.Rect(x0 * rect.width, y0 * rect.height, x1 * rect.width, y1 * rect.height)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pdf", type=Path, help="Fitxer PDF")
    parser.add_argument("--page", type=int, required=True, help="Número de pàgina, 1-based")
    parser.add_argument("--clip", default=None, help="'x0,y0,x1,y1' en fraccions 0-1 (per defecte: pàgina sencera)")
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--grid", default=None, help="'RxC' (p. ex. '2x2'): subdivideix la regió en una graella")
    parser.add_argument("--out", type=Path, required=True, help="PNG de sortida")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)

    try:
        base = _parse_clip(args.clip) if args.clip else (0.0, 0.0, 1.0, 1.0)
        grid = _parse_grid(args.grid) if args.grid else None
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if not args.pdf.exists():
        print(f"ERROR: PDF no trobat: {args.pdf}", file=sys.stderr)
        return 2

    try:
        import fitz  # PyMuPDF

        doc = fitz.open(str(args.pdf))
    except Exception as exc:
        print(f"ERROR: no s'ha pogut obrir el PDF: {exc}", file=sys.stderr)
        return 2

    try:
        if args.page < 1 or args.page > doc.page_count:
            print(f"ERROR: pàgina {args.page} fora de rang (el PDF té {doc.page_count} pàgines)", file=sys.stderr)
            return 2
        page = doc.load_page(args.page - 1)

        args.out.parent.mkdir(parents=True, exist_ok=True)

        if grid is None:
            clip_rect = _fraction_rect_to_points(page, *base)
            pix = page.get_pixmap(dpi=args.dpi, clip=clip_rect)
            pix.save(str(args.out))
            print(f"OK PNG {pix.width}x{pix.height}px")
            return 0

        rows, cols = grid
        out_stem = args.out.with_suffix("")
        for r, c, x0, y0, x1, y1 in _grid_cells(base, rows, cols):
            clip_rect = _fraction_rect_to_points(page, x0, y0, x1, y1)
            pix = page.get_pixmap(dpi=args.dpi, clip=clip_rect)
            cell_path = out_stem.parent / f"{out_stem.name}-r{r}c{c}.png"
            pix.save(str(cell_path))
            print(f"OK PNG {pix.width}x{pix.height}px {cell_path}")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    finally:
        doc.close()


if __name__ == "__main__":
    sys.exit(main())
