"""Veritat d'imatges: (imatge, peu, secció, ranura) de cada signat → fitxers + index.json.
Ús: truth_extract.py <dir docx> <out_full> <out_index> [--label X]
Estàtiques: phash ≤ 6 contra word/media de la plantilla g3dt-jinja-template.docx."""
import zipfile, re, io, os, sys, glob, hashlib, json, subprocess, unicodedata
from PIL import Image
import imagehash
from lxml import etree
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
      "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
      "v": "urn:schemas-microsoft-com:vml",
      "pr": "http://schemas.openxmlformats.org/package/2006/relationships"}
CAP = re.compile(r"^\s*(Figura|Fotografia|Fotografía|Taula|Tabla)s?\s+\d+", re.I)
FIGCAP = re.compile(r"^\s*(Figura|Fotografia|Fotografía)", re.I)
HEAD = re.compile(r"^\s*\d+(\.\d+)*\.?\s+[A-ZÀ-Ü]")
SLUG = {"3001621_informe_v0": "castellar", "3001631_informe": "rubi", "4001607_informe": "linyola",
        "4001612_informe": "bell-lloc", "4001670_informe": "alcoletge", "4001671_informe": "vilanova",
        "4001679_informe_V0": "anciles"}
TEMPLATE = "/home/josep/projects/claudecode-job/clients/g3dt-prod/templates/g3dt-jinja-template.docx"

def norm(s):
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))

def slot_for(caption, heading):
    c = norm(caption or ""); h = norm(heading or "")
    if not c:
        if "estabilitat" in h or "saturac" in c: return "fig_extra_estabilitat"
        if "empuje" in h or "empent" in h: return "fig_extra_empentes"
        return "sense_peu"
    if "cullera" in c or "cuchara" in c: return "fig_spt_cullera"
    if c.startswith("fotograf"):
        if "material" in c: return "foto_materials"
        if "penetrac" in c or "dpsh" in c: return "foto_dpsh"
        if "sondeig" in c or "sondeo" in c: return "foto_sondeig"
        if "vista" in c or "general" in c or "parcela" in c or "google" in c: return "foto_vista"
        return "foto_altres"
    # figures
    if "mapa geolog" in c: return "fig_geologic"
    if "tall de correlac" in c or "corte de correlac" in c: return "fig_tall"
    if "assaigs realitzats" in c or "ensayos realizados" in c: return "fig_assaigs"
    if "saturac" in c: return "fig_extra_estabilitat"
    if any(k in c for k in ("situacio de la zona", "situacion de la parcela", "ubicacio de la parcel", "vista de la zona en estudio")):
        return "fig_situacio"
    if any(k in c for k in ("perfil", "topografic", "viviendas prevista", "interior de la parcel", "emplazamiento de la vivienda", "font: projecte", "fuente: proyecto")):
        return "fig_projecte"
    return "fig_altres"

def template_hashes():
    z = zipfile.ZipFile(TEMPLATE); out = []
    used = set()
    for part in z.namelist():
        if re.match(r"word/(document|header\d*|footer\d*)\.xml$", part):
            relp = part.replace("word/", "word/_rels/") + ".rels"
            if relp not in z.namelist(): continue
            rels = z.read(relp).decode()
            m = {}
            for a, b in re.findall(r'Id="(rId\d+)"[^>]*Target="(media/[^"]+)"', rels): m[a] = b
            for b, a in re.findall(r'Target="(media/[^"]+)"[^>]*Id="(rId\d+)"', rels): m[a] = b
            x = z.read(part).decode()
            for rid in set(re.findall(r'r:embed="(rId\d+)"', x)) | set(re.findall(r'r:id="(rId\d+)"', x)):
                if rid in m: used.add("word/" + m[rid])
    for n in z.namelist():
        if n in used:
            try: out.append((n, imagehash.phash(Image.open(io.BytesIO(z.read(n))).convert("RGB"))))
            except Exception: pass
    return out

def seq(docx):
    z = zipfile.ZipFile(docx)
    rels = etree.fromstring(z.read("word/_rels/document.xml.rels"))
    rid2t = {r.get("Id"): r.get("Target") for r in rels.findall("pr:Relationship", NS)}
    body = etree.fromstring(z.read("word/document.xml")).find("w:body", NS)
    items = []; head = ""; pidx = 0
    for p in body.iter("{%s}p" % NS["w"]):
        pidx += 1
        txt = "".join(t.text or "" for t in p.iter("{%s}t" % NS["w"])).strip()
        rids = [b.get("{%s}embed" % NS["r"]) for b in p.findall(".//a:blip", NS)]
        rids += [b.get("{%s}id" % NS["r"]) for b in p.findall(".//v:imagedata", NS)]
        seen = set()
        for rid in rids:
            if rid in seen: continue
            seen.add(rid)
            tgt = rid2t.get(rid, "")
            if tgt and "media/" in tgt:
                items.append(("img", {"media": os.path.basename(tgt), "data": z.read("word/" + tgt), "heading": head, "para": pidx}))
        if txt and CAP.match(txt):
            items.append(("cap", txt, bool(FIGCAP.match(txt))))
        elif txt and HEAD.match(txt) and len(txt) < 90:
            head = txt; items.append(("head", txt))
    return items

def main():
    src, out_full, out_index = sys.argv[1:4]
    label = sys.argv[sys.argv.index("--label") + 1] if "--label" in sys.argv else ""
    thash = template_hashes()
    summary = {}
    for f in sorted(glob.glob(src + "/*.docx")):
        stem = os.path.basename(f)[:-5]; slug = SLUG.get(stem, stem)
        d_full = os.path.join(out_full, slug); os.makedirs(d_full, exist_ok=True)
        d_idx = os.path.join(out_index, slug); os.makedirs(d_idx, exist_ok=True)
        entries = []; buf = []
        def flush(caption, is_fig):
            nonlocal buf
            n = len(buf)
            for i, im in enumerate(buf):
                entries.append({**im, "caption": caption if is_fig else "", "shared_caption": n > 1,
                                "after": None if is_fig else caption})
            buf = []
        for it in seq(f):
            if it[0] == "img": buf.append(it[1])
            elif it[0] == "cap":
                if buf: flush(it[1], it[2])
            elif it[0] == "head":
                if buf: flush("(capçalera: %s)" % it[1], False)
        if buf: flush("(final del document)", False)
        index = []
        for k, e in enumerate(entries, 1):
            data = e.pop("data"); ext = os.path.splitext(e["media"])[1].lower()
            md5 = hashlib.md5(data).hexdigest()
            dims = None; ph = None; static_of = None
            try:
                im = Image.open(io.BytesIO(data)); dims = [im.width, im.height]
                ph = imagehash.phash(im.convert("RGB"))
                for n, th in thash:
                    if ph - th <= 6: static_of = os.path.basename(n); break
            except Exception: pass
            slot = "static_plantilla" if static_of else slot_for(e["caption"], e["heading"])
            short = re.sub(r"[^a-z0-9]+", "-", norm(e["caption"] or e.get("after") or ""))[:40].strip("-")
            fname = f"{k:02d}_{slot}_{short}{ext}"
            with open(os.path.join(d_full, fname), "wb") as fh: fh.write(data)
            index.append({"n": k, "file": fname, "media": e["media"], "md5": md5, "dims": dims, "bytes": len(data),
                          "phash": str(ph) if ph else None, "slot": slot, "static_of": static_of,
                          "caption": e["caption"], "shared_caption": e["shared_caption"], "after": e["after"],
                          "heading": e["heading"], "para": e["para"]})
        meta = {"signat": os.path.basename(f), "slug": slug, "label": label, "n_images": len(index),
                "n_static": sum(1 for i in index if i["static_of"]), "template": os.path.basename(TEMPLATE), "images": index}
        json.dump(meta, open(os.path.join(d_idx, "index.json"), "w"), ensure_ascii=False, indent=1)
        summary[slug] = index
        print(f"##### {slug}  ({len(index)} imatges, {meta['n_static']} estàtiques)")
        for i in index:
            print(f"  {i['n']:2d} {i['slot']:22s} {str(i['dims']):12s} {i['bytes']//1024:5d}K  {i['caption'][:70] if i['caption'] else '(sense peu → '+str(i['after'])[:40]+')'}")
    return summary
if __name__ == "__main__": main()
