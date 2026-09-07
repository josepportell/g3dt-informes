"""Inventari de candidats per projecte: imatges, pàgines de PDF renderitzades, FH11 convertits.
Sortida: $S/cands/<slug>/*.png (renders) + $S/cands/<slug>/manifest.json"""
import os, sys, glob, json, re, hashlib
import fitz
from PIL import Image
S = '/tmp/claude-1000/-home-josep-projects-claudecode-job-clients-g3dt-prod/a25f4f53-8ad8-4eaf-b120-f6cbb34cfb6d/scratchpad'
BASE = '/home/josep/g3dt-e2e/projectes'
PROJ = {"castellar": "3001621 CASTELLAR DEL VALLES", "rubi": "3001631 RUBI", "linyola": "4001607 LINYOLA",
        "bell-lloc": "4001612 BELL-LLOC", "alcoletge": "4001670 ALCOLETGE", "vilanova": "4001671 VILANOVA DE SEGRIA",
        "anciles": "4001679 ANCILES"}
IMG_EXT = ('.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp', '.gif')
SKIP_PDF = ('informe', 'portada', 'pressupost', 'presupuesto', 'lab-sig', 'gtl-', 'thumbs')
AUX_PDF = ('_dpsh.pdf',)   # annex de taules, no font d'imatge: es llista però no es renderitza
DPI = 80
def kind_of(rel):
    r = rel.lower()
    if '/validation/' in r or r.startswith('validation/'): return 'validation'
    if r.endswith('.fh11'): return 'fh11'
    if r.endswith('.pdf'):
        if any(s in r for s in SKIP_PDF): return 'pdf_skip'
        if any(s in r for s in AUX_PDF): return 'pdf_aux'
        if re.search(r'pdf[ _-]?v0/', r): return 'pdf_v0'
        if 'annexes/' in r or 'anejos/' in r or 'anexos/' in r: return 'pdf_annex'
        return 'pdf'
    if r.endswith(IMG_EXT):
        if re.search(r'annexes/altres|anexos/otros', r): return 'png_annex_altres'
        if 'fotograf' in r or 'fotos' in r: return 'foto'
        return 'img'
    return 'other'
def roles_for(pdir):
    fm = os.path.join(pdir, 'file_mapping.json')
    out = {}
    if os.path.exists(fm):
        d = json.load(open(fm))
        for role, v in d.get('roles', {}).items():
            if isinstance(v, dict) and v.get('path'): out.setdefault(v['path'], []).append(role)
    return out
def main(only=None):
    for slug, name in PROJ.items():
        if only and slug not in only: continue
        pdir = os.path.join(BASE, name); out = os.path.join(S, 'cands', slug); os.makedirs(out, exist_ok=True)
        roles = roles_for(pdir); items = []
        files = sorted(glob.glob(pdir + '/**/*', recursive=True))
        # afegeix els FH11 convertits
        fh = sorted(glob.glob(os.path.join(S, 'fh11', name, '*.pdf')))
        for f in files + fh:
            if os.path.isdir(f): continue
            if f.startswith(pdir): rel = f[len(pdir) + 1:]; kind = kind_of(rel)
            else: rel = 'FH11→' + os.path.basename(f); kind = 'fh11_pdf'
            if kind in ('other', 'validation', 'fh11'):
                if kind == 'fh11' or (kind == 'validation' and re.search(r'msg_attachments|mined_images', rel) and rel.lower().endswith(IMG_EXT + ('.pdf',))):
                    items.append({'rel': rel, 'kind': kind, 'bytes': os.path.getsize(f), 'roles': roles.get(rel, []), 'renders': []})
                continue
            it = {'rel': rel, 'kind': kind, 'bytes': os.path.getsize(f), 'roles': roles.get(rel, []), 'renders': []}
            sid = hashlib.md5(rel.encode()).hexdigest()[:6]
            if kind in ('foto', 'img', 'png_annex_altres'):
                try:
                    im = Image.open(f); it['dims'] = [im.width, im.height]; it['renders'] = [{'page': 1, 'path': f}]
                except Exception as e: it['error'] = str(e)[:60]
            elif kind in ('pdf', 'pdf_annex', 'pdf_v0', 'fh11_pdf'):
                try:
                    d = fitz.open(f); it['pages'] = d.page_count
                    for i, pg in enumerate(d):
                        pth = os.path.join(out, f"{sid}_p{i+1:02d}.png")
                        if not os.path.exists(pth):
                            pix = pg.get_pixmap(dpi=DPI); pix.save(pth)
                        r = pg.rect
                        it['renders'].append({'page': i + 1, 'path': pth, 'pt': [round(r.width), round(r.height)]})
                    d.close()
                except Exception as e: it['error'] = str(e)[:60]
            elif kind in ('pdf_skip', 'pdf_aux'):
                try: d = fitz.open(f); it['pages'] = d.page_count; d.close()
                except Exception: pass
            items.append(it)
        json.dump({'slug': slug, 'project': name, 'dpi': DPI, 'items': items}, open(os.path.join(out, 'manifest.json'), 'w'), ensure_ascii=False, indent=1)
        n_r = sum(len(i['renders']) for i in items)
        kinds = {}
        for i in items: kinds[i['kind']] = kinds.get(i['kind'], 0) + 1
        print(f"{slug:10s} {len(items):3d} fitxers, {n_r:3d} candidats renderitzats  {kinds}")
if __name__ == '__main__': main(sys.argv[1:] or None)
