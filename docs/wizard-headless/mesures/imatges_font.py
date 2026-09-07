#!/usr/bin/env python3
"""Peça 0 del pas 3 d'imatges (2026-09-07): mesura per figura «MATEIXA FONT que l'Eva», per a M341.

Fins al bloc 4, M341 només deia si cada forat d'imatge de la plantilla era present / pendent / absent. Aquí, per a cada
figura o foto que l'Eva posa al signat (veritat del pas 1: `docs/imatges/veritat/<slug>/index.json` + imatges a mida real
a `~/g3dt-e2e/imatges/veritat/<slug>/`), es mira la imatge que NOSALTRES posem al forat corresponent i es puntua:

  MATCH     la mateixa imatge sencera (phash ≤ 10: fotos, PNG d'ALTRES tal qual, mateix retall)
  CLOSE     la mateixa font amb un altre retall o composició (NCC multiescala amb penalització PSR ≥ 0,7: la veritat dins
            la nostra o la nostra dins la veritat)
  MISMATCH  posem una imatge que no ve de la mateixa font (a ull pot ser-ho: els dibuixos CAD de línia fina queden a
            0,3-0,5; la mesura és una tendència, la lectura visual mana per a les decisions)
  NO_DATA   no posem res (forat absent o «[Imatge pendent]»): res fals imprès, com als escalars

Una nostra imatge només pot servir UNA figura de l'Eva (assignació un a un, la millor primer); les nostres que queden
sense figura de l'Eva són «sobrants» (`fig_aerea` a 6 de 7 signats, el plànol sencer quan l'Eva no posa cap figura del
projecte). Fora de mesura: la cullera SPT (estàtica del generador), les estàtiques de la plantilla, les figures «extra»
sense ranura (estabilitat de Castellar, signatura d'Anciles: D10) i els duplicats d'un mateix media dins el signat.

Els tres càlculs (`load_gray`, `ncc_max`, `best_scaled`) són còpia literal de `docs/imatges/scripts/match.py` (pas 1),
calibrats allà (idèntic 1,00, retall 0,90, no relacionat 0,34-0,47): no canviar la penalització PSR, el `psr = 99` quan
la plantilla és tota la imatge, l'escala nativa 1:1 ni l'`alpha_composite` sobre blanc.

Ús sol (sense M341), sobre un diccionari forat → camí d'imatge, o re-mesura d'un run (camins desats a `_compare_imatges.json`):
  PYTHONPATH=$PWD .venv/bin/python docs/wizard-headless/mesures/imatges_font.py castellar fig_correlation_image=/x/tall.jpg …
  PYTHONPATH=$PWD .venv/bin/python docs/wizard-headless/mesures/imatges_font.py --remeasure docs/wizard-headless/mesures/runs/<run>
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

import imagehash
import numpy as np
from PIL import Image, ImageOps
from scipy.ndimage import gaussian_filter
from scipy.signal import fftconvolve

REPO = Path(__file__).resolve().parents[3]
TRUTH_IDX = REPO / "docs" / "imatges" / "veritat"
TRUTH_IMG = Path(os.environ.get("G3DT_IMATGES_VERITAT", "~/g3dt-e2e/imatges/veritat")).expanduser()

PHASH_MAX = 10     # mateixa imatge sencera (handoff 1330 §2)
NCC_MIN = 0.70     # score efectiu = ncc · min(1, psr / 6): «fort» = ncc ≥ 0,7 i PSR ≥ 6

#: Forat de la plantilla → ranures de l'Eva amb què es compara (pas 2, D1-D9).
SLOT_MAP = {
    "fig_cadastre_image": ("fig_situacio",),
    "fig_aerea_image": ("fig_situacio",),           # 0/7 signats; només pot coincidir amb la 2a imatge de situació
    "fig_main_plan_image": ("fig_assaigs", "fig_projecte"),
    "fig_geological_image": ("fig_geologic",),
    "fig_correlation_image": ("fig_tall",),
    "photo_dpsh_image": ("foto_dpsh",),
    "photo_sondeig_image": ("foto_sondeig",),
    "photo_materials_image": ("foto_materials",),
    "photo_site_image_1": ("foto_vista",),
    "photo_site_image_2": ("foto_vista",),
}
SKIP_TRUTH = ("fig_spt_cullera", "static_plantilla")
EXTRA_PREFIX = "fig_extra_"
PLACEHOLDER = "[Imatge pendent]"
STATUS_RANK = {"MATCH": 0, "CLOSE": 1, "MISMATCH": 2}

# ----------------------------------------------------------------------------------------------- match.py (pas 1)
MAXSIDE = 360
SIGMA = 0.9
MINSIDE = 36
SCALES = [round(0.12 * 1.17 ** k, 4) for k in range(15)]
SCALES = [s for s in SCALES if s <= 1.0] + [1.0]


def load_gray(p, maxside=MAXSIDE):
    im = Image.open(p); im = ImageOps.exif_transpose(im)
    if im.mode in ('RGBA', 'LA') or (im.mode == 'P' and 'transparency' in im.info):
        im = im.convert('RGBA'); bg = Image.new('RGBA', im.size, (255, 255, 255, 255)); im = Image.alpha_composite(bg, im)
    im = im.convert('L'); orig = im.size
    s = maxside / max(im.size)
    if s < 1: im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    a = np.asarray(im, dtype=np.float64) / 255.0
    return gaussian_filter(a, SIGMA), orig


def ncc_max(I, t):
    h, w = t.shape
    if h > I.shape[0] or w > I.shape[1] or h < 8 or w < 8: return -1.0, None
    t0 = t - t.mean(); dt = np.sqrt((t0 ** 2).sum())
    if dt < 1e-3: return -1.0, None
    ones = np.ones_like(t)
    corr = fftconvolve(I, t0[::-1, ::-1], mode='valid')
    s1 = fftconvolve(I, ones, mode='valid'); s2 = fftconvolve(I * I, ones, mode='valid')
    n = h * w
    var = s2 - s1 * s1 / n
    floor = n * (0.03 ** 2)
    flat = var < floor; var[flat] = floor
    ncc = corr / (np.sqrt(var) * dt); ncc[flat] = 0.0
    ncc = np.clip(ncc, -1.0, 1.0)
    k = int(np.argmax(ncc)); y, x = divmod(k, ncc.shape[1])
    peak = float(ncc[y, x])
    if ncc.size > 50:
        mask = np.ones_like(ncc, dtype=bool); y0, y1 = max(0, y - h // 4), y + h // 4 + 1; x0, x1 = max(0, x - w // 4), x + w // 4 + 1
        mask[y0:y1, x0:x1] = False
        rest = ncc[mask]
        psr = (peak - rest.mean()) / (rest.std() + 1e-6) if rest.size > 20 else 0.0
    else: psr = 99.0   # plantilla ~ imatge sencera: el pic es l'unic possible
    return peak, (y, x, round(float(psr), 1))


def best_scaled(I, T, native=None):
    best = (-1.0, None, None)
    widths = sorted(set([s * I.shape[1] for s in SCALES] + ([native] if native else [])))
    Tim = Image.fromarray((np.clip(T, 0, 1) * 255).astype(np.uint8))
    for tw in widths:
        sc = tw / T.shape[1]; th = T.shape[0] * sc
        if th > I.shape[0]: sc = I.shape[0] / T.shape[0]; tw = T.shape[1] * sc; th = I.shape[0]
        if tw > I.shape[1]: sc = I.shape[1] / T.shape[1]; tw = I.shape[1]; th = T.shape[0] * sc
        if tw < MINSIDE or th < MINSIDE: continue
        t = np.asarray(Tim.resize((max(8, round(tw)), max(8, round(th))), Image.LANCZOS), dtype=np.float64) / 255.0
        sc_, pos = ncc_max(I, t)
        psr = pos[2] if pos else 0.0
        # penalitza pics poc singulars (textura generica): score = ncc * min(1, psr/6)
        eff = sc_ * min(1.0, psr / 6.0) if pos else sc_
        if eff > best[0]: best = (eff, round(tw / I.shape[1], 3), {'pos': pos[:2], 'shape': list(t.shape), 'ncc': round(sc_, 3), 'psr': psr} if pos else None)
    return best
# ------------------------------------------------------------------------------------------------------------------


def truth_figures(slug: str, idx_dir: Path = None, img_dir: Path = None) -> list[dict]:
    """Figures de l'Eva que entren a la mesura, en ordre de document."""
    idx_dir = idx_dir or TRUTH_IDX; img_dir = img_dir or TRUTH_IMG
    d = json.loads((idx_dir / slug / "index.json").read_text(encoding="utf-8"))
    out, seen = [], set()
    for im in d["images"]:
        slot = im["slot"]
        if im.get("static_of") or slot in SKIP_TRUTH or slot.startswith(EXTRA_PREFIX):
            continue
        key = (slot, im.get("md5"))
        if key in seen:                       # Vilanova: la Fotografia 2 dues vegades (mateix rId) → una figura
            continue
        seen.add(key)
        p = img_dir / slug / im["file"]
        if p.suffix.lower() == ".wmf":
            p = p.with_suffix(".png")
        if not p.exists():
            raise FileNotFoundError(f"veritat a mida real absent: {p} (regenera amb docs/imatges/scripts/truth_extract.py)")
        out.append({"n": im["n"], "slot": slot, "caption": im.get("caption") or "", "file": im["file"], "path": p})
    return out


def our_images(ctx: dict) -> dict[str, str]:
    """Forat de la plantilla → camí de la imatge que s'imprimeix (InlineImage viu del context, o camí directe)."""
    out = {}
    for slot in SLOT_MAP:
        v = ctx.get(slot)
        if v is None:
            continue
        path = getattr(v, "image_descriptor", None)          # docxtpl.InlineImage viu (mai `str()`: docxtpl intentaria inserir-lo)
        if path is None:
            path = v if isinstance(v, (str, os.PathLike)) else None
        if not path or PLACEHOLDER in str(path) or not str(path).strip():
            continue
        if slot == "photo_sondeig_image" and not ctx.get("has_sondeig"):
            continue                          # dins `{%p if has_sondeig %}`: no s'imprimeix
        if slot.startswith("photo_site_image") and not (ctx.get("photo_site_text") or "").strip():
            continue                          # dins `{%p if photo_site_text %}`
        if not Path(str(path)).exists():
            continue
        out[slot] = str(path)
    return out


def score_pair(truth_path: Path, ours_path: str, allow_reverse: bool = True) -> dict:
    """phash sencer; si no, NCC veritat-dins-nostra i (figures) nostra-dins-veritat, escala nativa inclosa."""
    ti = ImageOps.exif_transpose(Image.open(truth_path)).convert("RGB")
    oi = ImageOps.exif_transpose(Image.open(ours_path)).convert("RGB")      # l'orientació EXIF del fitxer de camp compta
    th = imagehash.phash(ti)
    d = int(th - imagehash.phash(oi))
    if d <= PHASH_MAX:
        return {"status": "MATCH", "phash_d": d, "ncc": None, "psr": None, "scale": None, "dir": "sencera"}
    # la mateixa foto girada (Rubí materials: 1080×1920 nostra, 1920×1080 al signat) és la mateixa font mal orientada
    for ang in (90, 180, 270):
        dr = int(th - imagehash.phash(oi.rotate(ang, expand=True)))
        if dr <= PHASH_MAX:
            return {"status": "CLOSE", "phash_d": d, "ncc": None, "psr": None, "scale": None, "dir": f"rotada {ang}°", "phash_rot": dr}
    T, torig = load_gray(truth_path); O, oorig = load_gray(ours_path)
    nat_in = torig[0] * (O.shape[1] / oorig[0])
    s_in, sc_in, pos_in = best_scaled(O, T, native=nat_in)
    best = (s_in, sc_in, pos_in, "veritat dins nostra")
    if allow_reverse:
        nat_rev = oorig[0] * (T.shape[1] / torig[0])
        s_rev, sc_rev, pos_rev = best_scaled(T, O, native=nat_rev)
        if s_rev > best[0]:
            best = (s_rev, sc_rev, pos_rev, "nostra dins veritat")
    eff, sc, pos, direction = best
    return {"status": "CLOSE" if eff >= NCC_MIN else "MISMATCH", "phash_d": d, "ncc": round(float(eff), 3),
            "psr": (pos or {}).get("psr"), "ncc_raw": (pos or {}).get("ncc"), "scale": sc, "dir": direction}


def compare_images(truths: list[dict], ours: dict[str, str]) -> dict:
    """Assignació un a un (la millor parella primer). Retorna files per figura de l'Eva + sobrants + totals."""
    cands = {}
    for slot, path in ours.items():
        for t in truths:
            if t["slot"] in SLOT_MAP[slot]:
                r = score_pair(t["path"], path, allow_reverse=not t["slot"].startswith("foto_"))
                cands[(t["n"], slot)] = r
    order = sorted(cands.items(), key=lambda kv: (STATUS_RANK[kv[1]["status"]], kv[1]["phash_d"] if kv[1]["status"] == "MATCH" else -(kv[1]["ncc"] or 0)))
    used_t, used_o, chosen = set(), set(), {}
    for (n, slot), r in order:
        if n in used_t or slot in used_o:
            continue
        used_t.add(n); used_o.add(slot); chosen[n] = (slot, r)
    rows = []
    for t in truths:
        if t["n"] in chosen:
            slot, r = chosen[t["n"]]
            rows.append({"n": t["n"], "slot_eva": t["slot"], "caption": t["caption"][:90], "file_eva": t["file"],
                         "ours_slot": slot, "file_ours": Path(ours[slot]).name, **r})
        else:
            rows.append({"n": t["n"], "slot_eva": t["slot"], "caption": t["caption"][:90], "file_eva": t["file"],
                         "ours_slot": None, "file_ours": None, "status": "NO_DATA", "phash_d": None, "ncc": None,
                         "psr": None, "scale": None, "dir": None})
    sobrants = [{"ours_slot": s, "file_ours": Path(p).name} for s, p in ours.items() if s not in used_o]
    totals = Counter(r["status"] for r in rows)
    for k in ("MATCH", "CLOSE", "MISMATCH", "NO_DATA"):
        totals.setdefault(k, 0)
    by_slot = {}
    for r in rows:
        by_slot.setdefault(r["slot_eva"], Counter())[r["status"]] += 1
    return {"rows": rows, "sobrants": sobrants, "sobrants_n": len(sobrants), "totals": dict(totals),
            "by_slot": {k: dict(v) for k, v in by_slot.items()}, "ours_paths": dict(ours)}


def compare_project(slug: str, ctx: dict) -> dict:
    return compare_images(truth_figures(slug), our_images(ctx))


def pct(c: dict) -> str:
    """Mateixa convenció que `mesura_informe._pct`: (M + C) / (M + C + X); ND fora del percentatge (es veu a la columna)."""
    comp = c.get("MATCH", 0) + c.get("CLOSE", 0) + c.get("MISMATCH", 0)
    return f"{100 * (c.get('MATCH', 0) + c.get('CLOSE', 0)) / comp:.0f} %" if comp else "—"


def format_rows(res: dict, tag: str) -> str:
    L = [f"# Imatges «mateixa font que l'Eva» — {tag}", "",
         "| # | ranura Eva | peu | nostre forat | estat | phash | ncc | psr | escala | direcció |", "|--:|---|---|---|---|--:|--:|--:|--:|---|"]
    for r in res["rows"]:
        L.append(f"| {r['n']} | `{r['slot_eva']}` | {r['caption'][:60]} | {('`' + r['ours_slot'] + '`') if r['ours_slot'] else '—'} | "
                 f"**{r['status']}** | {r['phash_d'] if r['phash_d'] is not None else '—'} | {r['ncc'] if r['ncc'] is not None else '—'} | "
                 f"{r['psr'] if r['psr'] is not None else '—'} | {r['scale'] if r['scale'] is not None else '—'} | {r['dir'] or '—'} |")
    t = res["totals"]
    L += ["", f"Totals: {t['MATCH']} M · {t['CLOSE']} C · {t['MISMATCH']} X · {t['NO_DATA']} ND → {pct(t)}; "
          f"sobrants (nostres sense figura de l'Eva): {res['sobrants_n']} " + ", ".join(f"`{s['ours_slot']}`" for s in res["sobrants"])]
    return "\n".join(L) + "\n"


def agregat_section(results: dict, variant: str = "viaA") -> list[str]:
    """Secció per a `_AGREGAT-341.md`: per projecte i per ranura de l'Eva."""
    L = ["## Imatges (viaA): MATEIXA FONT que l'Eva, per figura del signat — M (mateixa imatge) · C (mateixa font, altre retall) · X · ND (no posem res)", "",
         "| projecte | M | C | X | ND | % | sobrants | X i ND (ranura de l'Eva) |", "|---|--:|--:|--:|--:|--:|--:|---|"]
    tot, by_slot = Counter(), {}
    for slug, per in results.items():
        f = (per.get(variant) or {}).get("images_font")
        if not f:
            continue
        t = f["totals"]; tot.update(t)
        bad = [f"`{r['slot_eva']}`:{'X' if r['status'] == 'MISMATCH' else 'ND'}" for r in f["rows"] if r["status"] in ("MISMATCH", "NO_DATA")]
        L.append(f"| {slug} | {t['MATCH']} | {t['CLOSE']} | {t['MISMATCH']} | {t['NO_DATA']} | {pct(t)} | {f['sobrants_n']} | {', '.join(bad) or '—'} |")
        for s, c in f["by_slot"].items():
            by_slot.setdefault(s, Counter()).update(c)
    if tot:
        L.append(f"| **total** | **{tot['MATCH']}** | **{tot['CLOSE']}** | **{tot['MISMATCH']}** | **{tot['NO_DATA']}** | **{pct(tot)}** | | |")
    L += ["", "| ranura de l'Eva | M | C | X | ND | % |", "|---|--:|--:|--:|--:|--:|"]
    for s in sorted(by_slot, key=lambda k: (not k.startswith("fig_"), k)):
        c = by_slot[s]
        L.append(f"| `{s}` | {c.get('MATCH', 0)} | {c.get('CLOSE', 0)} | {c.get('MISMATCH', 0)} | {c.get('NO_DATA', 0)} | {pct(c)} |")
    L += ["", f"Llindars: M = phash ≤ {PHASH_MAX}; C = NCC·min(1, PSR/6) ≥ {NCC_MIN} (veritat dins nostra, o nostra dins veritat per a figures). "
          "Fora: cullera SPT, estàtiques, figures «extra» sense ranura (D10), duplicats del signat. X per hash pot ser mateixa font a ull "
          "(línia fina): tendència, no veredicte. Detall per projecte a `<slug>/viaA/_compare_imatges.txt`.", ""]
    return L


def remeasure_run(run_dir: Path, variant: str = "viaA") -> dict:
    """Torna a puntuar un run existent des dels camins desats a `_compare_imatges.json` (sense regenerar cap informe)."""
    out = {}
    for d in sorted(run_dir.iterdir()):
        j = d / variant / "_compare_imatges.json"
        if not j.exists():
            continue
        ours = json.loads(j.read_text(encoding="utf-8")).get("ours_paths") or {}
        res = compare_images(truth_figures(d.name), {k: v for k, v in ours.items() if Path(v).exists()})
        out[d.name] = res
        (d / variant / "_compare_imatges.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        (d / variant / "_compare_imatges.txt").write_text(format_rows(res, f"{d.name}/{variant}"), encoding="utf-8")
    return out


if __name__ == "__main__":
    if sys.argv[1:2] == ["--remeasure"]:
        res = remeasure_run(Path(sys.argv[2]))
        print("\n".join(agregat_section({s: {"viaA": {"images_font": r}} for s, r in res.items()})))
    else:
        slug = sys.argv[1]
        ours = dict(a.split("=", 1) for a in sys.argv[2:])
        res = compare_images(truth_figures(slug), {k: v for k, v in ours.items() if Path(v).exists()})
        print(format_rows(res, slug))
