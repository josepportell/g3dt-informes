"""Imatges dels NOSTRES generats (bloc 4b, viaA): (imatge, peu, ranura, pendent) -> $S/nostres/<slug>/ + index.json"""
import sys, os, glob, json, hashlib, io, re
sys.path.insert(0, '/tmp/claude-1000/-home-josep-projects-claudecode-job-clients-g3dt-prod/a25f4f53-8ad8-4eaf-b120-f6cbb34cfb6d/scratchpad')
import truth_extract as te
import zipfile
from lxml import etree
from PIL import Image
import imagehash
S = '/tmp/claude-1000/-home-josep-projects-claudecode-job-clients-g3dt-prod/a25f4f53-8ad8-4eaf-b120-f6cbb34cfb6d/scratchpad'
NS = te.NS
def seq(docx):
    z = zipfile.ZipFile(docx)
    rels = etree.fromstring(z.read("word/_rels/document.xml.rels"))
    rid2t = {r.get("Id"): r.get("Target") for r in rels.findall("pr:Relationship", NS)}
    body = etree.fromstring(z.read("word/document.xml")).find("w:body", NS)
    items = []; head = ""
    for p in body.iter("{%s}p" % NS["w"]):
        txt = "".join(t.text or "" for t in p.iter("{%s}t" % NS["w"])).strip()
        rids = [b.get("{%s}embed" % NS["r"]) for b in p.findall(".//a:blip", NS)]
        seen = set()
        for rid in rids:
            if rid in seen: continue
            seen.add(rid); tgt = rid2t.get(rid, "")
            if tgt and "media/" in tgt: items.append(("img", {"media": os.path.basename(tgt), "data": z.read("word/" + tgt), "heading": head}))
        if "[Imatge pendent]" in txt: items.append(("img", {"media": None, "data": None, "heading": head, "pending": True}))
        if txt and te.CAP.match(txt): items.append(("cap", txt, bool(te.FIGCAP.match(txt))))
        elif txt and te.HEAD.match(txt) and len(txt) < 90: head = txt; items.append(("head", txt))
    return items
thash = te.template_hashes()
for f in sorted(glob.glob(os.path.expanduser('~/g3dt-e2e/informes-mesura/2026-09-07-m341-bloc4b/*_viaA.docx'))):
    slug = os.path.basename(f).replace('_viaA.docx', ''); out = os.path.join(S, 'nostres', slug); os.makedirs(out, exist_ok=True)
    entries = []; buf = []
    def flush(cap, isfig):
        global buf
        for e in buf: entries.append({**e, "caption": cap if isfig else "", "after": None if isfig else cap})
        buf = []
    for it in seq(f):
        if it[0] == "img": buf.append(it[1])
        elif it[0] == "cap" and buf: flush(it[1], it[2])
        elif it[0] == "head" and buf: flush("(capçalera: %s)" % it[1], False)
    if buf: flush("(final)", False)
    index = []
    for k, e in enumerate(entries, 1):
        data = e.pop("data"); pending = e.get("pending", False)
        rec = {"n": k, "pending": pending, "caption": e["caption"], "after": e["after"], "heading": e["heading"], "media": e["media"]}
        if pending: rec["slot"] = te.slot_for(e["caption"], e["heading"]); rec["file"] = None
        else:
            ext = os.path.splitext(e["media"])[1].lower(); md5 = hashlib.md5(data).hexdigest()
            im = Image.open(io.BytesIO(data)); ph = imagehash.phash(im.convert("RGB")); static = None
            for n, th in thash:
                if ph - th <= 6: static = os.path.basename(n); break
            slot = "static_plantilla" if static else te.slot_for(e["caption"], e["heading"])
            fname = f"{k:02d}_{slot}{ext}"; open(os.path.join(out, fname), "wb").write(data)
            rec.update({"file": fname, "md5": md5, "dims": [im.width, im.height], "bytes": len(data), "phash": str(ph), "slot": slot, "static_of": static})
        index.append(rec)
    json.dump({"slug": slug, "docx": os.path.basename(f), "images": index}, open(os.path.join(out, "index.json"), "w"), ensure_ascii=False, indent=1)
    print(f"##### {slug}"); 
    for r in index: print(f"  {r['n']:2d} {r['slot']:22s} {'PENDENT' if r['pending'] else str(r['dims']):14s} {(r['caption'] or '(sense peu → '+str(r['after'])[:30]+')')[:80]}")
