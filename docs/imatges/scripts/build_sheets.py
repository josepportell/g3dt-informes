"""Fulls visuals a tres columnes: Eva (veritat) | nosaltres (bloc 4b) | candidats (top 3 per hash). -> docs/imatges/fulls/<slug>.jpg"""
import os, json, glob, textwrap
from PIL import Image, ImageDraw, ImageFont, ImageOps
S = '/tmp/claude-1000/-home-josep-projects-claudecode-job-clients-g3dt-prod/a25f4f53-8ad8-4eaf-b120-f6cbb34cfb6d/scratchpad'
R = '/home/josep/projects/claudecode-job/clients/g3dt-prod'
TRUTH = '/home/josep/g3dt-e2e/imatges/veritat'
font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 12)
fontb = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 13)
W, H, TXT = 250, 190, 62
OURS_FOR = {'fig_assaigs': 'fig_projecte'}  # la ranura nostra que hi correspon
def thumb(path):
    im = Image.open(path); im = ImageOps.exif_transpose(im)
    if im.mode in ('RGBA', 'LA') or (im.mode == 'P' and 'transparency' in im.info):
        im = im.convert('RGBA'); bg = Image.new('RGBA', im.size, (255, 255, 255, 255)); im = Image.alpha_composite(bg, im)
    im = im.convert('RGB'); im.thumbnail((W, H)); return im
def cell(d, im, x, y, label, color='#bbb', note=None):
    if im is not None:
        d.rectangle([x, y, x + W, y + H], outline=color, width=2)
        d._image.paste(im, (x + (W - im.width) // 2, y + (H - im.height) // 2))
    else:
        d.rectangle([x, y, x + W, y + H], outline=color, width=2); d.text((x + 10, y + H // 2 - 8), note or '—', fill=color, font=fontb)
    for j, l in enumerate(textwrap.wrap(label, 40)[:4]): d.text((x, y + H + 3 + j * 14), l, fill='black', font=font)
def build(slug):
    tr = json.load(open(f'{R}/docs/imatges/veritat/{slug}/index.json'))
    ours = json.load(open(f'{S}/nostres/{slug}/index.json'))
    mt = {t['n']: t for t in json.load(open(f'{S}/match/{slug}.json'))['truth']}
    rows = [im for im in tr['images'] if im['slot'] not in ('static_plantilla', 'fig_spt_cullera')]
    pool = {}
    for o in ours['images']:
        if o['slot'] in ('static_plantilla', 'fig_spt_cullera'): continue
        pool.setdefault(o['slot'], []).append(o)
    used = set()
    cols = 5; width = 20 + cols * (W + 14); height = 50 + len(rows) * (H + TXT + 10)
    img = Image.new('RGB', (width, height), 'white'); d = ImageDraw.Draw(img); d._image = img
    d.text((20, 12), f'{slug} — Eva (signat) | nosaltres (bloc 4b viaA) | candidats del projecte (hash: ph=phash, ncc, psr)', fill='black', font=fontb)
    for i, im in enumerate(rows):
        y = 50 + i * (H + TXT + 10); x = 20
        p = f'{TRUTH}/{slug}/{im["file"]}'; p = p[:-4] + '.png' if p.endswith('.wmf') else p
        cell(d, thumb(p), x, y, f'EVA {im["n"]}. {im["slot"]} | {im["caption"][:60]}', '#1a6')
        x += W + 14
        oslot = OURS_FOR.get(im['slot'], im['slot']); cand = [o for o in pool.get(oslot, []) if o['n'] not in used]
        if cand:
            o = cand[0]; used.add(o['n'])
            if o['pending']: cell(d, None, x, y, f'NOSALTRES {o["n"]}. {o["slot"]} PENDENT', 'red', '[Imatge pendent]')
            else: cell(d, thumb(f'{S}/nostres/{slug}/{o["file"]}'), x, y, f'NOSALTRES {o["n"]}. {o["slot"]} {o["dims"]}', '#36c')
        else: cell(d, None, x, y, f'NOSALTRES: cap ranura «{oslot}» lliure', '#999', 'absent')
        x += W + 14
        for c in mt.get(im['n'], {}).get('top', [])[:3]:
            lab = f'{c["rel"][-38:]}' + (f' p{c["page"]}' if c['page'] > 1 or 'pdf' in c['kind'] else '') + f' | ph={c["phash_d"]} ncc={c["best"]}'
            ex = c.get('pos_in') if c['ncc_in'] >= c['ncc_rev'] else c.get('pos_rev')
            if isinstance(ex, dict): lab += f' psr={ex.get("psr")} @{c["scale_in"] if c["ncc_in"] >= c["ncc_rev"] else c["scale_rev"]}' + ('' if c['ncc_in'] >= c['ncc_rev'] else ' (cand. dins Eva)')
            path = None
            man = json.load(open(f'{S}/cands/{slug}/manifest.json'))
            for it in man['items']:
                if it['rel'] == c['rel']:
                    for r in it['renders']:
                        if r['page'] == c['page']: path = r['path']
            strong = c['phash_d'] <= 10 or c['best'] >= 0.6
            cell(d, thumb(path) if path else None, x, y, lab, '#c60' if strong else '#bbb')
            x += W + 14
    os.makedirs(f'{R}/docs/imatges/fulls', exist_ok=True)
    img.save(f'{R}/docs/imatges/fulls/{slug}.jpg', quality=78, optimize=True)
    return os.path.getsize(f'{R}/docs/imatges/fulls/{slug}.jpg') // 1024
if __name__ == '__main__':
    import sys
    for slug in (sys.argv[1:] or ['castellar', 'rubi', 'linyola', 'bell-lloc', 'alcoletge', 'vilanova', 'anciles']):
        print(slug, build(slug), 'KB')
