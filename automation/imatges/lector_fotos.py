"""Peça 2 del pas 3 d'imatges (2026-09-07): lector de FOTOS de camp amb Claude Code (skill `g3dt-llegir-fotos`).

Què fa (D5-D7 del pas 2): per a cada forat de foto de l'informe (vistes generals 1-2, màquina DPSH, màquina del sondeig,
materials) tria la foto del projecte que l'Eva posaria, MIRANT-LES: Claude Code rep un full de contacte numerat amb
totes les imatges de la carpeta de fotos, l'annex de fotografies de l'Eva renderitzat (la seva pròpia selecció amb peu,
existeix abans del wizard) i, per forat, els exemplars dels signats d'ALTRES projectes (leave-one-out). Python fa la part
determinista: inventari, orientació EXIF, aparellament foto ↔ annex per phash, fulls de contacte, prompt, crida
`claude -p` (el mateix runner que la lectura de text), validació i escriptura de `validation/photo_selection.json` amb
`source: "lector"` (precedència al generador: Eva `user` > `lector` > cau IA antiga > patrons).

Mai inventa: un forat sense foto vàlida queda `null` i surt a `cap_font`. Cost: UNA crida de visió per projecte.

Ús: `automation.imatges.lector_fotos.run(project_path, exclude_slug=…, model=…, effort=…)`; corpus dels 7 signats:
`docs/wizard-headless/mesures/llegir_fotos_corpus.py`.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
import unicodedata
from pathlib import Path

import imagehash
from PIL import Image, ImageDraw, ImageFont, ImageOps

log = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parents[2]
SKILL = REPO / ".claude" / "commands" / "g3dt-llegir-fotos.md"
TRUTH_IDX = REPO / "docs" / "imatges" / "veritat"
TRUTH_IMG = Path(os.environ.get("G3DT_IMATGES_VERITAT", "~/g3dt-e2e/imatges/veritat")).expanduser()
IMG_EXTS = {".jpg", ".jpeg", ".png"}
SLOTS = ("site_1", "site_2", "dpsh", "sondeig", "materials")
#: ranura de la veritat (pas 1) → nom del bloc d'exemplars al prompt
EXEMPLAR_SLOTS = {"foto_dpsh": "dpsh", "foto_sondeig": "sondeig", "foto_materials": "materials", "foto_vista": "vistes"}
SLUG_KEYS = {"castellar": "CASTELLAR", "rubi": "RUBI", "linyola": "LINYOLA", "bell-lloc": "BELL-LLOC",
             "alcoletge": "ALCOLETGE", "vilanova": "VILANOVA", "anciles": "ANCILES"}
PHASH_MAX = 10
MIN_ANNEX_SIDE = 300          # el logo de l'annex fa 138×138
SUBDIR = "_lector_fotos"      # dins `validation/`
SELECTION = "photo_selection.json"
BACKUP = "photo_selection.abans-lector.json"
RESULT = "fotos_lector.json"


def _cache_dir() -> Path:
    try:
        from automation import config
        return Path(config.cache_dir("lector-fotos"))
    except Exception:
        d = Path(os.environ.get("G3DT_CACHE_DIR", "~/.g3dt/cache")).expanduser() / "lector-fotos"
        d.mkdir(parents=True, exist_ok=True)
        return d


def _norm(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def slug_of(project: Path) -> str | None:
    up = project.name.upper()
    for slug, key in SLUG_KEYS.items():
        if key in up:
            return slug
    return None


# ------------------------------------------------------------------------------------------------ inventari
def _roles(project: Path) -> dict[str, list[str]]:
    fm = project / "file_mapping.json"
    out: dict[str, list[str]] = {}
    if fm.exists():
        try:
            for role, v in (json.loads(fm.read_text(encoding="utf-8")).get("roles") or {}).items():
                if isinstance(v, dict) and v.get("path"):
                    out.setdefault(str(v["path"]).replace("\\", "/"), []).append(role)
        except Exception:
            pass
    return out


def find_photos_dir(project: Path) -> Path | None:
    """Mateixa cerca que `ImageManager._find_photos_dir`: rol `photos_dir`, noms habituals, `FOTOS*`/`FOTOGRAF*`."""
    for rel, roles in _roles(project).items():
        if "photos_dir" in roles and (project / rel).is_dir():
            return project / rel
    for name in ("FOTOGRAFIES", "FOTOGRAFIA", "FOTOS DE CAMP + PLANOL PUNTS", "FOTOGRAFÍAS", "FOTOGRAFIAS"):
        if (project / name).is_dir():
            return project / name
    for d in sorted(project.iterdir()):
        if d.is_dir() and d.name.upper().startswith(("FOTOS", "FOTOGRAF")):
            return d
    return None


def list_candidates(photos_dir: Path) -> list[Path]:
    return [f for f in sorted(photos_dir.rglob("*"))
            if f.is_file() and f.suffix.lower() in IMG_EXTS and f.name != "Thumbs.db" and not f.name.startswith("_")]


def find_annex_fotografies(project: Path) -> Path | None:
    """L'annex de fotografies de l'Eva (`*_fotografies.pdf` / `*_fotografías.pdf` / `.FH11`): PDF primer."""
    hits = [p for p in project.rglob("*") if p.is_file() and "fotograf" in _norm(p.name)
            and p.suffix.lower() in (".pdf", ".fh11") and "/validation/" not in p.as_posix()]
    pdfs = sorted((p for p in hits if p.suffix.lower() == ".pdf"), key=lambda p: (("v0" in _norm(p.as_posix())), len(p.as_posix())))
    if pdfs:
        return pdfs[0]
    fh = sorted(p for p in hits if p.suffix.lower() == ".fh11")
    return fh[0] if fh else None


def fh11_to_pdf(fh11: Path) -> Path | None:
    """FreeHand → PDF amb soffice (3-14 s), cau per md5 (com `_cache_name` de les imatges)."""
    digest = hashlib.md5(fh11.read_bytes()).hexdigest()[:10]
    out = _cache_dir() / f"{fh11.stem}_{digest}.pdf"
    if out.exists():
        return out
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        log.warning("soffice no trobat: no es pot convertir %s", fh11)
        return None
    with tempfile.TemporaryDirectory() as tmp:
        try:
            subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", tmp, str(fh11)],
                           check=True, timeout=180, capture_output=True)
        except Exception as exc:
            log.warning("soffice ha fallat amb %s: %s", fh11, exc)
            return None
        pdfs = list(Path(tmp).glob("*.pdf"))
        if not pdfs:
            return None
        shutil.move(str(pdfs[0]), out)
    return out


def annex_images(pdf: Path) -> list[dict]:
    """Fotos incrustades a l'annex, per pàgina i ordre de lectura (dalt→baix), amb phash; el logo (138×138) fora."""
    import fitz
    out = []
    doc = fitz.open(pdf)
    for pno, page in enumerate(doc, 1):
        found = []
        for img in page.get_images(full=True):
            xref = img[0]
            try:
                info = doc.extract_image(xref)
                if min(info["width"], info["height"]) < MIN_ANNEX_SIDE:
                    continue
                rects = page.get_image_rects(xref)
                y0, x0 = (rects[0].y0, rects[0].x0) if rects else (0.0, 0.0)
                import io
                ph = str(imagehash.phash(Image.open(io.BytesIO(info["image"])).convert("RGB")))
                found.append({"page": pno, "y": round(float(y0), 1), "x": round(float(x0), 1), "phash": ph,
                              "w": info["width"], "h": info["height"]})
            except Exception as exc:  # una imatge corrupta no atura l'inventari
                log.debug("annex %s p%d xref %s: %s", pdf.name, pno, xref, exc)
        found.sort(key=lambda r: (r["y"], r["x"]))
        for k, r in enumerate(found, 1):
            r["ordinal"] = k
        out.extend(found)
    return out


def render_pages(pdf: Path, out_dir: Path, dpi: int = 80) -> list[Path]:
    import fitz
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for pno, page in enumerate(fitz.open(pdf), 1):
        p = out_dir / f"annex_p{pno}.png"
        page.get_pixmap(dpi=dpi).save(p)
        paths.append(p)
    return paths


def inventory(project: Path, work: Path) -> dict:
    """Candidats (índex, camí relatiu, mides, phash, rols, aparellament amb l'annex) + annex renderitzat."""
    project = Path(project)
    photos_dir = find_photos_dir(project)
    warnings: list[str] = []
    cands: list[dict] = []
    roles = _roles(project)
    duplicates: dict[str, list[str]] = {}
    if photos_dir:
        # el mateix fitxer amb dos noms (còpies renombrades): un sol candidat. Canònic = el camí dins una subcarpeta
        # (`SONDEIG/`, `DPSH/`, `S1/`: el nom de la carpeta és una pista que el lector fa servir), si no el primer.
        groups: dict[str, list[Path]] = {}
        for f in list_candidates(photos_dir):
            groups.setdefault(hashlib.md5(f.read_bytes()).hexdigest(), []).append(f)
        ordered: list[tuple[Path, str, list[Path]]] = []
        for md5, files in groups.items():
            canon = sorted(files, key=lambda x: (-len(x.relative_to(photos_dir).parts), x.as_posix()))[0]
            ordered.append((canon, md5, [x for x in files if x != canon]))
        ordered.sort(key=lambda t: t[0].as_posix())
        k = 0
        for f, md5, others in ordered:
            rel = f.relative_to(project).as_posix()
            try:
                im = ImageOps.exif_transpose(Image.open(f)).convert("RGB")
                dims, ph = [im.width, im.height], str(imagehash.phash(im))
            except Exception as exc:
                warnings.append(f"{rel}: no es pot obrir ({exc})")
                continue
            k += 1
            dups = [x.relative_to(project).as_posix() for x in others]
            duplicates[rel] = dups
            rs = set(roles.get(rel, []))
            for d in dups:
                rs |= set(roles.get(d, []))
            cands.append({"idx": k, "rel": rel, "path": str(f), "dims": dims, "phash": ph, "md5": md5,
                          "roles": sorted(rs), "annex": None, "duplicates": dups})
        duplicates = {k: v for k, v in duplicates.items() if v}
    else:
        warnings.append("cap carpeta de fotos")
    annex = find_annex_fotografies(project)
    annex_pdf = None
    if annex and annex.suffix.lower() == ".fh11":
        annex_pdf = fh11_to_pdf(annex)
    elif annex:
        annex_pdf = annex
    annex_imgs, pages = [], []
    if annex_pdf:
        try:
            annex_imgs = annex_images(annex_pdf)
            pages = render_pages(annex_pdf, work)
        except Exception as exc:
            warnings.append(f"annex {annex.name}: {exc}")
        for c in cands:
            best = None
            for a in annex_imgs:
                d = imagehash.hex_to_hash(c["phash"]) - imagehash.hex_to_hash(a["phash"])
                if d <= PHASH_MAX and (best is None or d < best[0]):
                    best = (d, a)
            if best:
                c["annex"] = {"page": best[1]["page"], "ordinal": best[1]["ordinal"], "phash_d": int(best[0])}
    return {"project": str(project), "photos_dir": str(photos_dir) if photos_dir else None,
            "annex": str(annex) if annex else None, "annex_pdf": str(annex_pdf) if annex_pdf else None,
            "annex_pages": [str(p) for p in pages], "annex_images": annex_imgs, "candidates": cands, "warnings": warnings,
            "duplicates": duplicates}


# ------------------------------------------------------------------------------------------------ fulls de contacte
def _fonts():
    try:
        return (ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13),
                ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 15))
    except Exception:
        return ImageFont.load_default(), ImageFont.load_default()


def grid(cells: list[tuple[str, str]], out: Path, W: int = 360, H: int = 270, cols: int = 4, title: str = "") -> Path:
    """Graella de miniatures amb etiqueta (còpia de `docs/imatges/scripts/sheets.py`, pas 1)."""
    import textwrap
    font, fontb = _fonts()
    rows = max(1, (len(cells) + cols - 1) // cols)
    im = Image.new("RGB", (cols * (W + 12) + 12, rows * (H + 78) + 44), "white"); d = ImageDraw.Draw(im)
    d.text((12, 10), title, fill="black", font=fontb)
    for i, (label, path) in enumerate(cells):
        x = 12 + (i % cols) * (W + 12); y = 44 + (i // cols) * (H + 78)
        try:
            pic = ImageOps.exif_transpose(Image.open(path)).convert("RGB"); pic.thumbnail((W, H))
            im.paste(pic, (x + (W - pic.width) // 2, y + (H - pic.height) // 2)); d.rectangle([x, y, x + W, y + H], outline="#bbb")
        except Exception as exc:
            d.rectangle([x, y, x + W, y + H], outline="red"); d.text((x + 5, y + 5), f"ERR {exc}"[:50], fill="red", font=font)
        for j, l in enumerate(textwrap.wrap(label, 50)[:4]):
            d.text((x, y + H + 4 + j * 15), l, fill="black", font=font)
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, quality=85)
    return out


def contact_sheet(inv: dict, out: Path) -> Path:
    cells = []
    for c in inv["candidates"]:
        tag = f" · annex p{c['annex']['page']} #{c['annex']['ordinal']}" if c.get("annex") else ""
        rol = f" · rol {','.join(c['roles'])}" if c.get("roles") else ""
        cells.append((f"{c['idx']}. {Path(c['rel']).name} [{c['dims'][0]}×{c['dims'][1]}]{tag}{rol}", c["path"]))
    return grid(cells, out, title=f"FOTOS DEL PROJECTE {Path(inv['project']).name} — {len(cells)} candidats (número = índex)")


def exemplar_sheets(exclude_slug: str | None, out_dir: Path) -> dict:
    """Per forat, les fotos que l'Eva va posar als signats dels ALTRES projectes (leave-one-out), amb el seu peu."""
    out: dict[str, dict] = {}
    if not TRUTH_IDX.exists() or not TRUTH_IMG.exists():
        return out
    for truth_slot, name in EXEMPLAR_SLOTS.items():
        cells, slugs = [], []
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
                    cells.append((f"{slug} · {(im.get('caption') or '')[:80]}", str(p))); slugs.append(slug)
        if cells:
            path = grid(cells, out_dir / f"exemplars_{name}.jpg", W=300, H=225, cols=4,
                        title=f"EXEMPLARS «{name}» — el que l'Eva posa als signats dels altres projectes")
            out[name] = {"path": str(path), "n": len(cells), "slugs": sorted(set(slugs))}
    return out


# ------------------------------------------------------------------------------------------------ prompt i crida
def build_prompt(inv: dict, sheet: Path, exemplars: dict, out_json: Path, has_sondeig: bool | None) -> str:
    skill = SKILL.read_text(encoding="utf-8") if SKILL.exists() else ""
    L = [skill.strip(), "", "---", "", f"## Projecte: `{Path(inv['project']).name}`", ""]
    L.append(f"- Full de contacte amb TOTS els candidats (número = índex): `{sheet}`")
    if inv.get("annex_pages"):
        L.append(f"- Annex de fotografies de l'Eva (la seva selecció, amb peu; llegeix-ne els peus): " + ", ".join(f"`{p}`" for p in inv["annex_pages"]))
    else:
        L.append("- Annex de fotografies de l'Eva: cap al projecte.")
    for name, e in exemplars.items():
        L.append(f"- Exemplars «{name}» (altres projectes, {e['n']} fotos): `{e['path']}`")
    L.append(f"- Sondeig a rotació al projecte: {'sí' if has_sondeig else ('no' if has_sondeig is False else 'desconegut (mira les fotos)')}")
    L += ["", "### Candidats (índex · fitxer · mides · aparellament amb l'annex · rol SmartScan)", ""]
    for c in inv["candidates"]:
        tag = f"annex p{c['annex']['page']} foto #{c['annex']['ordinal']}" if c.get("annex") else "no és a l'annex"
        L.append(f"{c['idx']}. `{c['rel']}` · {c['dims'][0]}×{c['dims'][1]} · {tag}" + (f" · rol {','.join(c['roles'])}" if c.get("roles") else "")
                 + (f" · el mateix fitxer també com a {', '.join('`' + d + '`' for d in c['duplicates'])}" if c.get("duplicates") else ""))
    if inv.get("warnings"):
        L += ["", "Avisos de l'inventari: " + "; ".join(inv["warnings"])]
    L += ["", f"### Sortida", "", f"Escriu el JSON (només el JSON, sense res més) a `{out_json}` amb el Write tool i imprimeix-lo també com a resposta final."]
    return "\n".join(L) + "\n"


def parse_json_text(text: str) -> dict | None:
    if not text:
        return None
    s, e = text.find("{"), text.rfind("}")
    if s < 0 or e <= s:
        return None
    try:
        d = json.loads(text[s:e + 1])
        return d if isinstance(d, dict) else None
    except json.JSONDecodeError:
        return None


def validate_selection(sel: dict, cands: list[dict]) -> tuple[dict, list[str]]:
    """Índex (1-based) o camí relatiu → camí relatiu existent; una foto per forat (la primera guanya); avisos."""
    by_idx = {c["idx"]: c for c in cands}; by_rel = {c["rel"]: c for c in cands}
    by_name = {Path(c["rel"]).name: c for c in cands}
    for c in cands:
        for d in c.get("duplicates") or []:
            by_rel.setdefault(d, c); by_name.setdefault(Path(d).name, c)
    clean: dict[str, str | None] = {}; used: set[str] = set(); warnings: list[str] = []

    def resolve(v):
        if v is None or v == "":
            return None
        if isinstance(v, bool):
            return None
        if isinstance(v, (int, float)) or (isinstance(v, str) and v.strip().isdigit()):
            c = by_idx.get(int(v)); return c["rel"] if c else None
        if isinstance(v, str):
            v2 = v.replace("\\", "/").strip()
            c = by_rel.get(v2) or by_name.get(Path(v2).name)
            return c["rel"] if c else None
        return None

    for slot in SLOTS:
        rel = resolve(sel.get(slot))
        if sel.get(slot) not in (None, "") and rel is None:
            warnings.append(f"{slot}: «{sel.get(slot)}» no és cap candidat")
        if rel and rel in used:
            warnings.append(f"{slot}: {rel} ja assignada a un altre forat → null"); rel = None
        if rel:
            used.add(rel)
        clean[slot] = rel
    extra = []
    for item in sel.get("materials_per_punt") or []:
        if isinstance(item, dict):
            rel = resolve(item.get("idx", item.get("rel")))
            if rel:
                extra.append({"punt": str(item.get("punt") or ""), "rel": rel})
    if extra:
        clean["materials_per_punt"] = extra
    return clean, warnings


def write_selection(project: Path, clean: dict, meta: dict) -> Path:
    vdir = Path(project) / "validation"; vdir.mkdir(exist_ok=True)
    sel_path = vdir / SELECTION; bak = vdir / BACKUP
    if sel_path.exists() and not bak.exists():
        shutil.copy2(sel_path, bak)
    payload = {"source": "lector", **{k: clean.get(k) for k in SLOTS}}
    if clean.get("materials_per_punt"):
        payload["materials_per_punt"] = clean["materials_per_punt"]
    payload["_lector"] = meta
    sel_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return sel_path


def run(project: Path, *, exclude_slug: str | None = None, model: str | None = None, effort: str = "medium",
        timeout: int = 420, claude_path: str | None = None, has_sondeig: bool | None = None, dry_run: bool = False) -> dict:
    """Inventari → fulls → prompt → `claude -p` → validació → `photo_selection.json` (source lector). Retorna un resum."""
    project = Path(project)
    work = project / "validation" / SUBDIR; work.mkdir(parents=True, exist_ok=True)
    inv = inventory(project, work)
    (work / "inventari.json").write_text(json.dumps(inv, ensure_ascii=False, indent=1), encoding="utf-8")
    sheet = contact_sheet(inv, work / "graella.jpg")
    exemplars = exemplar_sheets(exclude_slug if exclude_slug is not None else slug_of(project), work)
    out_json = work / RESULT
    prompt = build_prompt(inv, sheet, exemplars, out_json, has_sondeig)
    (work / "prompt.md").write_text(prompt, encoding="utf-8")
    summary = {"project": str(project), "n_candidats": len(inv["candidates"]), "annex": inv.get("annex"),
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
            "exclude_slug": exclude_slug, "raons": raw.get("raons"), "confianca": raw.get("confianca"),
            "cap_font": raw.get("cap_font"), "notes": raw.get("notes"), "warnings": warnings}
    summary["selection"] = clean
    summary["path"] = str(write_selection(project, clean, meta))
    return summary
