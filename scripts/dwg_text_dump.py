"""Extreu tot el text d'un fitxer DWG (AutoCAD) via LibreDWG + ezdxf.

Cadena: dwg2dxf (LibreDWG, binari natiu; ~/.local/bin o PATH) converteix el DWG a DXF,
i ezdxf llegeix les entitats de text (TEXT, MTEXT, ATTRIB/ATTDEF, atributs d'INSERT)
de model space, paper spaces i blocs. Pensat per al nivell A: caixetins (promotor,
arquitecte, RC, adreça), taules de paràmetres urbanístics, i etiquetes de plànol.

Verificat 2026-08-23 amb els 4 DWG de Tulipa (AC1032/2018 i AC1027/2013):
el caixetí del topogràfic porta les 2 referències cadastrals i el promotor;
PARAMETRES URBANISTICS porta les superfícies de parcel·la del planejament.
Compte: els blocs poden portar restes de plantilla d'ALTRES projectes (Pas 0 del
skill g3dt-llegir-projecte: posar cada text en context abans d'usar-lo).

Ús:
    .venv/bin/python scripts/dwg_text_dump.py FITXER.dwg [ALTRE.dwg ...] [--json SORTIDA.json]

Sense --json, imprimeix una línia per text: [fitxer][espai][tipus] text
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def find_dwg2dxf() -> str:
    exe = shutil.which("dwg2dxf") or shutil.which(
        "dwg2dxf", path=str(Path.home() / ".local" / "bin")
    )
    if not exe:
        sys.exit(
            "dwg2dxf no trobat (LibreDWG). Instal·lació: baixar "
            "https://ftp.gnu.org/gnu/libredwg/libredwg-0.13.3.tar.xz, "
            "./configure --prefix=$HOME/.local --disable-bindings --disable-shared && make && make install"
        )
    return exe


def clean_mtext(s: str) -> str:
    s = re.sub(r"\\[A-Za-z][^;\\]*;", "", s)
    s = s.replace("{", "").replace("}", "").replace("\\P", "\n")
    return " ".join(s.split())


def collect_texts(dxf_path: Path) -> list[dict]:
    import ezdxf

    doc = ezdxf.readfile(dxf_path)
    out: list[dict] = []

    def add(where: str, etype: str, text: str, entity) -> None:
        text = clean_mtext(text) if etype == "MTEXT" else " ".join(text.split())
        if not text:
            return
        pos = getattr(entity.dxf, "insert", None)
        out.append(
            {
                "space": where,
                "type": etype,
                "text": text,
                "layer": entity.dxf.layer,
                "xy": [round(pos.x, 2), round(pos.y, 2)] if pos is not None else None,
            }
        )

    def walk(space, where: str) -> None:
        for e in space:
            t = e.dxftype()
            try:
                if t in ("TEXT", "ATTRIB", "ATTDEF"):
                    add(where, t, e.dxf.text, e)
                elif t == "MTEXT":
                    add(where, t, e.plain_text(), e)
                elif t == "INSERT":
                    for a in e.attribs:
                        add(where, "INSERT/ATTRIB", a.dxf.text, a)
            except Exception:  # entitats corruptes post-conversió: salta-les
                continue

    walk(doc.modelspace(), "model")
    for name in doc.layout_names():
        if name.lower() != "model":
            walk(doc.layout(name), f"paper:{name}")
    for blk in doc.blocks:
        if not blk.name.startswith(("*Model_Space", "*Paper_Space")):
            walk(blk, f"block:{blk.name}")
    return out


def dump_file(dwg: Path, exe: str) -> dict:
    with tempfile.TemporaryDirectory() as td:
        dxf = Path(td) / (dwg.stem + ".dxf")
        res = subprocess.run(
            [exe, "-o", str(dxf), str(dwg)], capture_output=True, text=True, timeout=600
        )
        if not dxf.exists() or dxf.stat().st_size == 0:
            return {"file": str(dwg), "error": (res.stderr or "conversió buida")[-500:]}
        version = open(dwg, "rb").read(6).decode("ascii", "replace")
        return {"file": str(dwg), "dwg_version": version, "texts": collect_texts(dxf)}


def main() -> None:
    args = sys.argv[1:]
    json_out = None
    if "--json" in args:
        i = args.index("--json")
        json_out = Path(args[i + 1])
        del args[i : i + 2]
    if not args:
        sys.exit(__doc__)
    exe = find_dwg2dxf()
    results = [dump_file(Path(a), exe) for a in args]
    if json_out:
        json_out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{sum(len(r.get('texts', [])) for r in results)} textos → {json_out}")
    else:
        for r in results:
            if "error" in r:
                print(f"[{r['file']}] ERROR: {r['error']}")
                continue
            for t in r["texts"]:
                print(f"[{Path(r['file']).name}][{t['space']}][{t['type']}] {t['text']}")


if __name__ == "__main__":
    main()
