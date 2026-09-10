"""Peça 7b del pas 3 d'imatges (2026-09-09): lector de FIGURES del projecte amb Claude Code (skill `g3dt-llegir-figures`).

Què fa (D4 del pas 2): tria, MIRANT-LES, les figures que l'Eva treu del projecte de l'arquitecte i del seu propi full
«plànol de situació»: la figura d'ASSAIGS (el dibuix amb els punts, capítol 2.2), les figures del PROJECTE (0-2, «Font:
Projecte», capítol 1.1: secció, emplaçament, topogràfic, tipologies) i, només quan el plànol de l'arquitecte porta els
dos mapes de situació com a insets (Bell-lloc), les dues imatges de SITUACIÓ. Claude Code rep un full de contacte amb tots
els candidats (pàgines dels PDF del projecte, imatges de l'expedient, PNG d'ALTRES de l'Eva i el retall determinista del
seu annex), cada candidat renderitzat amb una quadrícula de coordenades (fraccions 0-1) per poder dir el retall, i els
exemplars dels signats d'ALTRES projectes (leave-one-out). Python fa la part determinista: inventari, renders, prompt,
crida `claude -p` (el runner de la lectura), validació, retall (+ retall del marge blanc) i escriptura de
`validation/figure_selection.json` amb `source: "lector"` (precedència al generador: Eva `user` > `lector` > determinista).

Mai inventa: sense candidat clar, la ranura queda `null` i surt a `cap_font`; cap figura del projecte «per omplir».
Cost: UNA crida de visió per projecte.

Ús: `automation.imatges.lector_figures.run(project_path, exclude_slug=…, lang=…)`; corpus dels 7 signats:
`docs/wizard-headless/mesures/llegir_figures_corpus.py`. El generador crida `apply_selection(project, cache_dir)`.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import time
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageOps

from automation.imatges.lector_fotos import (  # noqa: F401  (reutilitzats: mateixa mecànica que el lector de fotos)
    EVA_PNG_DIRS, SLUG_KEYS, TRUTH_IDX, TRUTH_IMG, _fonts, _norm, _roles, grid, parse_json_text, slug_of,
)

log = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parents[2]
SKILL = REPO / ".claude" / "commands" / "g3dt-llegir-figures.md"
SUBDIR = "_lector_figures"          # dins `validation/`
SELECTION = "figure_selection.json"
BACKUP = "figure_selection.abans-lector.json"
RESULT = "figures_lector.json"
SLOTS = ("assaigs", "projecte", "situacio")
#: ranura de la veritat (pas 1) → nom del bloc d'exemplars al prompt
EXEMPLAR_SLOTS = {"fig_assaigs": "assaigs", "fig_projecte": "projecte", "fig_situacio": "situacio"}
IMG_EXTS = {".jpg", ".jpeg", ".png"}
EXPEDIENT_DIR_RE = re.compile(r"^\d{2}\.\d{4}$")           # la carpeta de l'expedient amb els documents del client
#: fitxers de G3 (no del projecte de l'arquitecte) pel nom, quan són fora de les carpetes de G3. Dins la carpeta
#: d'expedient només hi cauen els pressupostos i l'informe de G3: la resta és del client (a Linyola, «Punts de
#: Sondeig_Silvia_Jaume.pdf» és la planta de l'arquitecte AMB els punts, la figura d'assaigs del signat).
G3_NAME_RE = re.compile(r"pressupost|presupuesto|informe|portada|gtl|lab-?sig|penetro|sondei|sondeo|\btall\b|corte de|fotograf"
                        r"|pl\.? ?situ|plànol de situaci|plano de situaci|thumbs\.db", re.I)
G3_IN_EXPEDIENT_RE = re.compile(r"pressupost|presupuesto|informe|portada|thumbs\.db", re.I)
G3_DIR_PREFIXES = ("PDF", "ANNEX", "ANEJ", "ANEX", "ACCEPT", "ACEPT", "FOTO", "VALIDATION", "_")
ARCHITECT_ROLES = ("architect_plan", "architect_plan_with_points", "architect_project", "figure_test_points")
MAX_PAGES_PER_PDF = 40
MAX_CANDIDATES = 60
MIN_DRAWINGS = 5                    # una pàgina només de text no és cap candidat
THUMB_W, THUMB_H = 360, 270
DETAIL_MAX_SIDE = 1600
MIN_CROP_AREA = 0.02
MAX_ALTERNATIVES = 3                # acció 4: candidats de més per ranura que l'Eva veu al wizard


def _cache_dir() -> Path:
    try:
        from automation import config
        return Path(config.cache_dir("images"))
    except Exception:
        d = Path(os.environ.get("G3DT_CACHE_DIR", "~/.g3dt/cache")).expanduser() / "images"
        d.mkdir(parents=True, exist_ok=True)
        return d


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()[:10]


# ------------------------------------------------------------------------------------------------ candidats
def _is_g3_dir(rel: Path) -> bool:
    top = rel.parts[0].upper() if len(rel.parts) > 1 else ""
    return top.startswith(G3_DIR_PREFIXES)


def _is_eva_png(rel: Path) -> bool:
    return len(rel.parts) >= 2 and any(part.upper() in EVA_PNG_DIRS for part in rel.parts[:-1]) and rel.suffix.lower() in IMG_EXTS


def project_documents(project: Path) -> list[tuple[Path, str, list[str]]]:
    """(fitxer, tipus, rols) dels documents que poden dur figures: el projecte de l'arquitecte (carpeta d'expedient
    `NN.NNNN/`, fitxers de l'arrel amb rol d'arquitecte o sense cap patró de G3) i els PNG d'`ALTRES`/`OTROS` de l'Eva."""
    roles = _roles(project)
    out: list[tuple[Path, str, list[str]]] = []
    seen_md5: set[str] = set()
    for f in sorted(project.rglob("*")):
        if not f.is_file() or f.name.startswith("_") or f.name == "Thumbs.db":
            continue
        rel = f.relative_to(project)
        if "validation" in rel.parts:
            continue
        suf = f.suffix.lower()
        if suf not in IMG_EXTS and suf != ".pdf":
            continue
        rel_s = rel.as_posix()
        rs = roles.get(rel_s, [])
        kind = None
        if _is_eva_png(rel):
            kind = "eva_png"
        elif len(rel.parts) > 1 and EXPEDIENT_DIR_RE.match(rel.parts[0]) and not G3_IN_EXPEDIENT_RE.search(f.name):
            kind = "project_page" if suf == ".pdf" else "project_image"
        elif len(rel.parts) == 1 and (any(r in ARCHITECT_ROLES for r in rs) or (suf == ".pdf" and not G3_NAME_RE.search(f.name)
                                                                                    and not any(r in rs for r in ("situation_plan", "correlation_section", "dpsh_field_sheet", "sondeig_field_sheet", "gtl_report")))):
            kind = "project_page" if suf == ".pdf" else "project_image"
        elif not _is_g3_dir(rel) and len(rel.parts) > 1 and not G3_NAME_RE.search(f.name) and any(r in ARCHITECT_ROLES for r in rs):
            kind = "project_page" if suf == ".pdf" else "project_image"
        if kind is None:
            continue
        if suf == ".pdf" and any(r in rs for r in ("situation_plan", "correlation_section")):
            continue                              # els fulls de l'Eva van pel camí determinista, no són del projecte
        try:
            d = _md5(f)
        except OSError:
            continue
        if d in seen_md5:
            continue                              # el mateix fitxer amb dos noms
        seen_md5.add(d)
        out.append((f, kind, rs))
    return out


def annex_drawing(project: Path) -> Path | None:
    """El retall determinista del dibuix del full «plànol de situació» de l'Eva (peça 4), si n'hi ha."""
    try:
        from automation.image_manager import ImageManager
        from automation.imatges.retall import crop_plan
        mgr = ImageManager(project, None, None)
        for sit_pdf in mgr._situation_plan_candidates(mgr._load_file_mapping()):
            cached = mgr._cache_name("plan_crop", sit_pdf)
            if not cached.exists() and crop_plan(sit_pdf, cached) is None:
                continue
            return cached
    except Exception as exc:
        log.warning("annex_drawing %s: %s", project, exc)
    return None


def _page_has_drawing(page) -> bool:
    try:
        if page.get_images():
            return True
        return len(page.get_drawings()) >= MIN_DRAWINGS
    except Exception:
        return True


def _render_page(pdf: Path, pno: int, out: Path, max_side: int) -> tuple[int, int]:
    import fitz
    doc = fitz.open(pdf)
    page = doc[pno]
    scale = max_side / max(page.rect.width, page.rect.height)
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    pix.save(str(out))
    doc.close()
    return pix.width, pix.height


BANNER_H = 30


def draw_grid(src: Path, out: Path, step: float = 0.1, label: str = "") -> Path:
    """La imatge amb una quadrícula de fraccions (0-1, origen a dalt a l'esquerra) perquè el lector pugui dir el retall,
    i una franja a dalt amb l'etiqueta «candidat N · fitxer · pàgina» (fora de la quadrícula: les fraccions són de la
    imatge, no de la franja). L'etiqueta hi és perquè el lector, quan mira, vegi QUIN índex està mirant: a la primera
    passada (Linyola) va descriure la secció de la p11 i va escriure l'índex de la p3."""
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    if max(im.size) > DETAIL_MAX_SIDE:
        im.thumbnail((DETAIL_MAX_SIDE, DETAIL_MAX_SIDE))
    W, H = im.size
    font, fontb = _fonts()
    over = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    n = int(round(1 / step))
    for k in range(1, n):
        x = int(W * k * step); y = int(H * k * step)
        d.line([(x, 0), (x, H)], fill=(220, 0, 0, 110), width=1)
        d.line([(0, y), (W, y)], fill=(220, 0, 0, 110), width=1)
        lab = f"{k * step:.1f}"
        d.rectangle([x + 2, 2, x + 30, 16], fill=(255, 255, 255, 200)); d.text((x + 4, 2), lab, fill=(200, 0, 0, 255), font=font)
        d.rectangle([2, y + 2, 30, y + 16], fill=(255, 255, 255, 200)); d.text((4, y + 2), lab, fill=(200, 0, 0, 255), font=font)
    d.rectangle([0, 0, W - 1, H - 1], outline=(220, 0, 0, 160), width=2)
    body = Image.alpha_composite(im.convert("RGBA"), over).convert("RGB")
    if label:
        canvas = Image.new("RGB", (W, H + BANNER_H), (255, 240, 200))
        ImageDraw.Draw(canvas).text((8, 7), label[:140], fill=(120, 0, 0), font=fontb)
        canvas.paste(body, (0, BANNER_H))
        body = canvas
    body.save(out, quality=85)
    return out


def inventory(project: Path, work: Path) -> dict:
    """Candidats numerats (retall de l'annex de l'Eva, pàgines del projecte, imatges de l'expedient, PNG d'ALTRES), amb
    render en miniatura i render amb quadrícula. Cada candidat: idx, kind, rel, page, dims, roles, detail (camí)."""
    import fitz
    project = Path(project)
    pages_dir = work / "pages"; pages_dir.mkdir(parents=True, exist_ok=True)
    cands: list[dict] = []
    warnings: list[str] = []

    def add(kind: str, rel: str, page: int | None, src: Path, roles: list[str], note: str = ""):
        idx = len(cands) + 1
        label = f"CANDIDAT {idx} · {Path(rel).name}" + (f" · pàgina {page}" if page else "") + f" · {kind}"
        detail = draw_grid(src, pages_dir / f"cand_{idx:02d}.jpg", label=label)
        im = Image.open(src); dims = [im.width, im.height]
        cands.append({"idx": idx, "kind": kind, "rel": rel, "page": page, "dims": dims, "roles": roles,
                      "src": str(src), "detail": str(detail), "note": note})

    ann = annex_drawing(project)
    if ann is not None:
        add("annex_crop", ann.name, None, ann, [], "retall del dibuix del full «plànol de situació» de l'Eva (determinista, peça 4)")
    else:
        warnings.append("cap full «plànol de situació» amb dibuix: sense retall de l'annex")
    for f, kind, roles in project_documents(project):
        if len(cands) >= MAX_CANDIDATES:
            warnings.append(f"més de {MAX_CANDIDATES} candidats: la resta no s'ha mirat"); break
        rel = f.relative_to(project).as_posix()
        if kind == "project_page":
            try:
                doc = fitz.open(f); n = len(doc)
            except Exception as exc:
                warnings.append(f"{rel}: no s'obre ({exc})"); continue
            if n > MAX_PAGES_PER_PDF:
                warnings.append(f"{rel}: {n} pàgines, només les {MAX_PAGES_PER_PDF} primeres")
            for pno in range(min(n, MAX_PAGES_PER_PDF)):
                if len(cands) >= MAX_CANDIDATES:
                    break
                if not _page_has_drawing(doc[pno]):
                    continue
                tmp = pages_dir / f"src_{f.stem[:30]}_{_md5(f)}_p{pno + 1}.png"
                try:
                    _render_page(f, pno, tmp, DETAIL_MAX_SIDE)
                except Exception as exc:
                    warnings.append(f"{rel} p{pno + 1}: no es renderitza ({exc})"); continue
                add(kind, rel, pno + 1, tmp, roles, f"pàgina {pno + 1} de {n}")
            doc.close()
        else:
            try:
                Image.open(f).close()
            except Exception as exc:
                warnings.append(f"{rel}: no s'obre ({exc})"); continue
            add(kind, rel, None, f, roles, "PNG compost per l'Eva (ANNEXES/ALTRES)" if kind == "eva_png" else "imatge de l'expedient")
    return {"project": str(project), "candidates": cands, "warnings": warnings}


def contact_sheet(inv: dict, out: Path) -> Path:
    cells = []
    for c in inv["candidates"]:
        pg = f" p{c['page']}" if c.get("page") else ""
        rol = f" · rol {','.join(c['roles'])}" if c.get("roles") else ""
        cells.append((f"{c['idx']}. {Path(c['rel']).name}{pg} [{c['dims'][0]}×{c['dims'][1]}] {c['kind']}{rol}", c["src"]))
    return grid(cells, out, W=THUMB_W, H=THUMB_H, cols=4,
                title=f"FIGURES CANDIDATES {Path(inv['project']).name} — {len(cells)} candidats (número = índex)")


def exemplar_sheets(exclude_slug: str | None, out_dir: Path) -> dict:
    """Per ranura, les figures que l'Eva va posar als signats dels ALTRES projectes (leave-one-out), amb el seu peu."""
    out: dict[str, dict] = {}
    if not TRUTH_IDX.exists() or not TRUTH_IMG.exists():
        return out
    for truth_slot, name in EXEMPLAR_SLOTS.items():
        cells, slugs, captions = [], [], []
        for slug in SLUG_KEYS:
            if slug == exclude_slug:
                continue
            idx = TRUTH_IDX / slug / "index.json"
            if not idx.exists():
                continue
            for im in json.loads(idx.read_text(encoding="utf-8"))["images"]:
                if im.get("slot") != truth_slot or im.get("static_of"):
                    continue
                p = TRUTH_IMG / slug / im["file"]
                if p.exists():
                    cap = (im.get("caption") or "")
                    cells.append((f"{slug} · {cap[:80]}", str(p))); slugs.append(slug); captions.append(f"{slug}: {cap}")
        if cells:
            path = grid(cells, out_dir / f"exemplars_{name}.jpg", W=300, H=225, cols=4,
                        title=f"EXEMPLARS «{name}» — el que l'Eva posa als signats dels altres projectes")
            out[name] = {"path": str(path), "n": len(cells), "slugs": sorted(set(slugs)), "captions": captions}
    return out


# ------------------------------------------------------------------------------------------------ prompt i crida
def build_prompt(inv: dict, sheet: Path, exemplars: dict, out_json: Path, lang: str) -> str:
    skill = SKILL.read_text(encoding="utf-8") if SKILL.exists() else ""
    L = [skill.strip(), "", "---", "", f"## Projecte: `{Path(inv['project']).name}` · idioma de l'informe: **{lang}**", ""]
    L.append(f"- Full de contacte amb TOTS els candidats (número = índex): `{sheet}`")
    L.append("- Cada candidat renderitzat amb la QUADRÍCULA de coordenades (fraccions 0-1, origen a dalt a l'esquerra, la franja de "
             "l'etiqueta no hi compta), per dir-ne el retall. La franja de dalt diu «CANDIDAT N · fitxer · pàgina»: l'índex que "
             "escriguis ha de ser el de la franja de la imatge que has mirat:")
    for c in inv["candidates"]:
        L.append(f"  - candidat {c['idx']}: `{c['detail']}`")
    for name, e in exemplars.items():
        L.append(f"- Exemplars «{name}» (altres projectes, {e['n']} figures): `{e['path']}`")
        for cap in e.get("captions", []):
            L.append(f"    - peu: {cap}")
    ann = next((c for c in inv["candidates"] if c["kind"] == "annex_crop"), None)
    if ann:
        L.append(f"- Avui (determinista) la figura d'assaigs és el candidat {ann['idx']} sencer (el retall del full de l'Eva). "
                 "La de situació són els dos mapes del mateix full, de costat: no la toquis si no és el cas de Bell-lloc.")
    else:
        L.append("- Avui no hi ha cap retall del full de situació de l'Eva: la figura d'assaigs està buida.")
    L += ["", "### Candidats (índex · fitxer · pàgina · mides · tipus · rol SmartScan)", ""]
    for c in inv["candidates"]:
        pg = f" · p{c['page']}" if c.get("page") else ""
        L.append(f"{c['idx']}. `{c['rel']}`{pg} · {c['dims'][0]}×{c['dims'][1]} · {c['kind']} · {c['note']}"
                 + (f" · rol {','.join(c['roles'])}" if c.get("roles") else ""))
    if inv.get("warnings"):
        L += ["", "Avisos de l'inventari: " + "; ".join(inv["warnings"])]
    L += ["", "### Sortida", "", f"Escriu el JSON (només el JSON, sense res més) a `{out_json}` amb el Write tool i imprimeix-lo també com a resposta final."]
    return "\n".join(L) + "\n"


def _crop_ok(c) -> list[float] | None:
    if c is None:
        return None
    if not (isinstance(c, (list, tuple)) and len(c) == 4):
        return None
    try:
        x0, y0, x1, y1 = (float(v) for v in c)
    except (TypeError, ValueError):
        return None
    x0, y0, x1, y1 = max(0.0, x0), max(0.0, y0), min(1.0, x1), min(1.0, y1)
    if x1 - x0 < 0.05 or y1 - y0 < 0.05 or (x1 - x0) * (y1 - y0) < MIN_CROP_AREA:
        return None
    return [round(x0, 3), round(y0, 3), round(x1, 3), round(y1, 3)]


def validate_selection(sel: dict, cands: list[dict]) -> tuple[dict, list[str]]:
    """Índex → candidat; retalls dins [0,1] i prou grans; ≤ 2 figures del projecte amb peu; cap (candidat, retall) repetit."""
    by_idx = {c["idx"]: c for c in cands}
    warnings: list[str] = []
    used: set[tuple] = set()

    def entry(v, slot: str, need_caption: bool = False) -> dict | None:
        if not isinstance(v, dict):
            if v not in (None, ""):
                warnings.append(f"{slot}: «{v!s:.40}» no és cap objecte {{idx, crop}}")
            return None
        try:
            c = by_idx.get(int(v.get("idx")))
        except (TypeError, ValueError):
            c = None
        if c is None:
            warnings.append(f"{slot}: idx «{v.get('idx')}» no és cap candidat"); return None
        crop = _crop_ok(v.get("crop"))
        if v.get("crop") is not None and crop is None:
            warnings.append(f"{slot}: retall «{v.get('crop')}» no vàlid → sencer")
        key = (c["idx"], tuple(crop) if crop else None)
        if key in used:
            warnings.append(f"{slot}: candidat {c['idx']} amb el mateix retall ja assignat → null"); return None
        cap = str(v.get("caption") or "").strip()
        if need_caption and not cap:
            warnings.append(f"{slot}: figura del projecte sense peu → null"); return None
        used.add(key)
        e = {"idx": c["idx"], "kind": c["kind"], "rel": c["rel"], "page": c.get("page"), "src": c["src"], "crop": crop}
        if need_caption:
            e["caption"] = cap[:200]
        return e

    clean: dict = {"assaigs": entry(sel.get("assaigs"), "assaigs"), "projecte": [], "situacio": None}
    proj = sel.get("projecte") or []
    if isinstance(proj, dict):
        proj = [proj]
    for k, v in enumerate(list(proj)[:2], 1):
        e = entry(v, f"projecte {k}", need_caption=True)
        if e:
            clean["projecte"].append(e)
    if len(proj) > 2:
        warnings.append(f"projecte: {len(proj)} figures, només les 2 primeres")
    # Acció 4 (2026-09-09): fins a 3 candidats MÉS per ranura (assaigs, projecte), amb raó; l'Eva els veu al wizard.
    alts: dict[str, list[dict]] = {}
    raw_alts = sel.get("alternatives")
    chosen = set(used)
    if isinstance(raw_alts, dict):
        for slot in ("assaigs", "projecte"):
            items = raw_alts.get(slot)
            if not isinstance(items, list):
                continue
            lst: list[dict] = []; seen: set[tuple] = set()
            for it in items:
                if not isinstance(it, dict):
                    continue
                try:
                    c = by_idx.get(int(it.get("idx")))
                except (TypeError, ValueError):
                    c = None
                if c is None:
                    warnings.append(f"alternatives {slot}: idx «{it.get('idx')}» no és cap candidat"); continue
                crop = _crop_ok(it.get("crop"))
                key = (c["idx"], tuple(crop) if crop else None)
                if key in chosen or key in seen:
                    continue
                seen.add(key)
                e = {"idx": c["idx"], "kind": c["kind"], "rel": c["rel"], "page": c.get("page"), "src": c["src"], "crop": crop,
                     "rao": str(it.get("rao") or "").strip()[:200]}
                cap = str(it.get("caption") or "").strip()
                if cap:
                    e["caption"] = cap[:200]
                lst.append(e)
                if len(lst) >= MAX_ALTERNATIVES:
                    break
            if lst:
                alts[slot] = lst
    if alts:
        clean["alternatives"] = alts
    sit = sel.get("situacio")
    if isinstance(sit, dict) and sit.get("idx") is not None:
        crops = [_crop_ok(c) for c in (sit.get("crops") or [])]
        crops = [c for c in crops if c]
        try:
            c = by_idx.get(int(sit.get("idx")))
        except (TypeError, ValueError):
            c = None
        if c is None or len(crops) != 2:
            warnings.append("situacio: cal un candidat i DOS retalls vàlids → es queda la composició del full")
        else:
            clean["situacio"] = {"idx": c["idx"], "kind": c["kind"], "rel": c["rel"], "page": c.get("page"), "src": c["src"], "crops": crops}
    return clean, warnings


# ------------------------------------------------------------------------------------------------ retalls
def trim_white(im: Image.Image, margin: float = 0.01, thresh: int = 18) -> Image.Image:
    """Treu el marge blanc (amb un petit marge): el lector dona el retall generós i aquí s'ajusta al contingut."""
    rgb = im.convert("RGB")
    bg = Image.new("RGB", rgb.size, (255, 255, 255))
    diff = ImageChops.difference(rgb, bg).convert("L").point(lambda v: 255 if v > thresh else 0)
    box = diff.getbbox()
    if not box:
        return im
    m = int(max(im.size) * margin)
    x0, y0, x1, y1 = max(0, box[0] - m), max(0, box[1] - m), min(im.width, box[2] + m), min(im.height, box[3] + m)
    if (x1 - x0) < 0.2 * im.width or (y1 - y0) < 0.2 * im.height:
        return im                                  # un retall que es menja el 80 % no és un marge
    return im.crop((x0, y0, x1, y1))


def render_entry(project: Path, entry: dict, out: Path, crop: list[float] | None = None, dpi: int = 200) -> Path | None:
    """Renderitza un candidat (pàgina de PDF o imatge) amb el retall en fraccions, i treu el marge blanc."""
    project = Path(project)
    crop = crop if crop is not None else entry.get("crop")
    try:
        if entry["kind"] == "project_page":
            import fitz
            doc = fitz.open(project / entry["rel"]); page = doc[int(entry["page"]) - 1]
            r = page.rect
            clip = fitz.Rect(r.x0 + r.width * crop[0], r.y0 + r.height * crop[1], r.x0 + r.width * crop[2], r.y0 + r.height * crop[3]) if crop else r
            side = max(clip.width, clip.height) * dpi / 72
            eff = dpi if side <= 4000 else int(dpi * 4000 / side)
            pix = page.get_pixmap(dpi=eff, clip=clip, alpha=False)
            im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            doc.close()
        else:
            src = Path(entry["src"]) if entry.get("src") else project / entry["rel"]
            im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
            if crop:
                W, H = im.size
                im = im.crop((int(W * crop[0]), int(H * crop[1]), int(W * crop[2]), int(H * crop[3])))
        if crop or entry["kind"] == "project_page":
            im = trim_white(im)
        out.parent.mkdir(parents=True, exist_ok=True)
        im.save(out, quality=92)
        return out
    except Exception as exc:
        log.warning("render_entry %s: %s", entry, exc)
        return None


def _out_name(cache: Path, slot: str, entry: dict, crop: list[float] | None) -> Path:
    src = Path(entry["src"]) if entry.get("src") else None
    try:
        d = _md5(src) if src and src.exists() else "nohash"
    except OSError:
        d = "nohash"
    tag = "-".join(f"{v:.3f}" for v in crop) if crop else "sencer"
    return cache / f"figsel_{slot}_{Path(entry['rel']).stem[:30]}_p{entry.get('page') or 0}_{d}_{tag}.jpg"


def load_selection(project: Path) -> dict | None:
    p = Path(project) / "validation" / SELECTION
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    return d if isinstance(d, dict) and d.get("source") in ("user", "lector") else None


def apply_selection(project: Path, cache_dir: Path | None = None) -> dict:
    """Les imatges (camins a la cau) i peus que la selecció del lector/de l'Eva aporta al context del generador:
    `fig_assaigs_image`, `fig_projecte_image_1/2` + `fig_projecte_caption_1/2`, `fig_situacio_image_1/2`."""
    sel = load_selection(project)
    if not sel:
        return {}
    cache = Path(cache_dir) if cache_dir else _cache_dir()
    # La selecció MANA sobre les tres ranures que cobreix, també quan diu «cap»: `assaigs: null` buida la figura
    # d'assaigs determinista (si no, Bell-lloc imprimia el mateix dibuix dues vegades: com a projecte a l'1.1 i com
    # a assaigs al 2.2, mesurat 2026-09-09) i una llista `projecte` curta buida les ranures que no omple.
    out: dict = {"fig_assaigs_image": "", "fig_projecte_image_1": "", "fig_projecte_caption_1": "",
                 "fig_projecte_image_2": "", "fig_projecte_caption_2": ""}
    e = sel.get("assaigs")
    if isinstance(e, dict):
        p = _out_name(cache, "assaigs", e, e.get("crop"))
        if p.exists() or render_entry(project, e, p):
            out["fig_assaigs_image"] = p
    for k, e in enumerate((sel.get("projecte") or [])[:2], 1):
        if not isinstance(e, dict):
            continue
        p = _out_name(cache, f"projecte{k}", e, e.get("crop"))
        if p.exists() or render_entry(project, e, p):
            out[f"fig_projecte_image_{k}"] = p
            out[f"fig_projecte_caption_{k}"] = e.get("caption") or ""
    # La situació doble només si l'ha triada l'EVA (`user`): la del lector no s'aplica (regla dels insets retirada el
    # 2026-09-09: encerta a Bell-lloc i falla a Alcoletge, on substituïa una M per dues X).
    s = sel.get("situacio") if sel.get("source") == "user" else None
    if isinstance(s, dict) and len(s.get("crops") or []) == 2:
        paths = []
        for k, crop in enumerate(s["crops"], 1):
            p = _out_name(cache, f"situacio{k}", s, crop)
            if p.exists() or render_entry(project, s, p, crop=crop):
                paths.append(p)
        if len(paths) == 2:
            out["fig_situacio_image_1"], out["fig_situacio_image_2"] = paths
    elif isinstance(s, dict) and s.get("rel"):
        # una sola imatge sencera (pujada de l'Eva, 2026-09-10): la plantilla ja té el cas d'una imatge de situació
        p = _out_name(cache, "situacio1", s, s.get("crop"))
        if p.exists() or render_entry(project, s, p):
            out["fig_situacio_image_1"], out["fig_situacio_image_2"] = p, ""
    # Les tres figures automàtiques (geològic, tall, cullera), només si l'Eva hi ha pujat una imatge (2026-09-10):
    # el generador les aplica després del seu camí determinista
    if sel.get("source") == "user":
        for key, ctx_key in (("geologic", "fig_geological_image"), ("tall", "fig_correlation_image"),
                             ("cullera", "fig_spt_cullera_image")):
            e = sel.get(key)
            if isinstance(e, dict) and e.get("rel"):
                p = _out_name(cache, key, e, e.get("crop"))
                if p.exists() or render_entry(project, e, p):
                    out[ctx_key] = p
    return out


def write_selection(project: Path, clean: dict, meta: dict) -> Path:
    vdir = Path(project) / "validation"; vdir.mkdir(exist_ok=True)
    sel_path = vdir / SELECTION; bak = vdir / BACKUP
    if sel_path.exists() and not bak.exists():
        shutil.copy2(sel_path, bak)
    payload = {"source": "lector", "assaigs": clean.get("assaigs"), "projecte": clean.get("projecte") or [],
               "situacio": clean.get("situacio")}
    if clean.get("alternatives"):
        payload["alternatives"] = clean["alternatives"]
    payload["_lector"] = meta
    sel_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return sel_path


def run(project: Path, *, exclude_slug: str | None = None, model: str | None = None, effort: str = "medium",
        timeout: int = 600, claude_path: str | None = None, lang: str = "ca", dry_run: bool = False) -> dict:
    """Inventari → renders → prompt → `claude -p` → validació → `figure_selection.json` (source lector). Retorna un resum."""
    project = Path(project)
    work = project / "validation" / SUBDIR; work.mkdir(parents=True, exist_ok=True)
    inv = inventory(project, work)
    (work / "inventari.json").write_text(json.dumps(inv, ensure_ascii=False, indent=1), encoding="utf-8")
    sheet = contact_sheet(inv, work / "graella.jpg")
    exemplars = exemplar_sheets(exclude_slug if exclude_slug is not None else slug_of(project), work)
    out_json = work / RESULT
    prompt = build_prompt(inv, sheet, exemplars, out_json, lang)
    (work / "prompt.md").write_text(prompt, encoding="utf-8")
    summary = {"project": str(project), "n_candidats": len(inv["candidates"]),
               "exemplars": {k: v["n"] for k, v in exemplars.items()}, "warnings": list(inv["warnings"])}
    if dry_run or not inv["candidates"]:
        summary["skipped"] = "dry_run" if dry_run else "sense candidats"
        return summary
    from automation.lectura import runner as R
    cfg_model = model or os.getenv("G3DT_LECTURA_MODEL", "sonnet") or "sonnet"
    cpath = claude_path or os.getenv("G3DT_CLAUDE_PATH", "claude") or "claude"
    cpath = shutil.which(cpath) or cpath
    if out_json.exists():
        out_json.unlink()
    t0 = time.monotonic()
    call = R._run_claude(claude_path=cpath, prompt=prompt, timeout=timeout, log_path=work / "claude.log",
                         should_cancel=None, model=cfg_model, effort=effort)
    summary.update({"rc": call.get("rc"), "timeout": call.get("timeout"), "elapsed_s": round(time.monotonic() - t0, 1),
                    "model": cfg_model, "effort": effort, "cli": call.get("cli")})
    raw = None
    if out_json.exists():
        raw = parse_json_text(out_json.read_text(encoding="utf-8", errors="replace"))
    if raw is None:
        log_txt = (work / "claude.log").read_text(encoding="utf-8", errors="replace") if (work / "claude.log").exists() else ""
        marker = log_txt.rfind("--- result ---")
        raw = parse_json_text(log_txt[marker:] if marker >= 0 else log_txt)
    if raw is None:
        summary["error"] = "cap JSON a la sortida"
        return summary
    clean, warnings = validate_selection(raw, inv["candidates"])
    summary["warnings"] += warnings
    meta = {"data": time.strftime("%Y-%m-%d %H:%M"), "model": cfg_model, "effort": effort, "elapsed_s": summary["elapsed_s"],
            "exclude_slug": exclude_slug, "lang": lang, "raons": raw.get("raons"), "confianca": raw.get("confianca"),
            "cap_font": raw.get("cap_font"), "notes": raw.get("notes"), "warnings": warnings}
    summary["selection"] = clean
    summary["path"] = str(write_selection(project, clean, meta))
    return summary
