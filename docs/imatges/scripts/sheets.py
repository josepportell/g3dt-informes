import os, json, glob, sys, textwrap
from PIL import Image, ImageDraw, ImageFont, ImageOps
S = '/tmp/claude-1000/-home-josep-projects-claudecode-job-clients-g3dt-prod/a25f4f53-8ad8-4eaf-b120-f6cbb34cfb6d/scratchpad'
TRUTH = '/home/josep/g3dt-e2e/imatges/veritat'
IDX = '/home/josep/projects/claudecode-job/clients/g3dt-prod/docs/imatges/veritat'
font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 13)
fontb = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 14)
def grid(cells, out, W=380, H=280, cols=4, title=''):
    rows = (len(cells) + cols - 1) // cols
    im = Image.new('RGB', (cols * (W + 12) + 12, rows * (H + 78) + 40), 'white'); d = ImageDraw.Draw(im)
    d.text((12, 10), title, fill='black', font=fontb)
    for i, (label, path) in enumerate(cells):
        x = 12 + (i % cols) * (W + 12); y = 40 + (i // cols) * (H + 78)
        try:
            pic = ImageOps.exif_transpose(Image.open(path)).convert('RGB'); dims = f'{pic.width}x{pic.height}'
            pic.thumbnail((W, H)); im.paste(pic, (x + (W - pic.width) // 2, y + (H - pic.height) // 2))
            d.rectangle([x, y, x + W, y + H], outline='#bbb')
        except Exception as e:
            d.rectangle([x, y, x + W, y + H], outline='red'); d.text((x + 5, y + 5), f'ERR {e}'[:50], fill='red', font=font); dims = '?'
        for j, l in enumerate(textwrap.wrap(f'{label}  [{dims}]', 52)[:4]): d.text((x, y + H + 4 + j * 15), l, fill='black', font=font)
    im.save(out, quality=85)
def truth_sheets():
    for slug in ['castellar', 'rubi', 'linyola', 'bell-lloc', 'alcoletge', 'vilanova', 'anciles']:
        idx = json.load(open(f'{IDX}/{slug}/index.json')); cells = []
        for im in idx['images']:
            p = f'{TRUTH}/{slug}/{im["file"]}'
            if p.endswith('.wmf'): p = p[:-4] + '.png'
            cells.append((f'{im["n"]}. {im["slot"]} | {im["caption"] or "(sense peu)"}', p))
        grid(cells, f'{S}/view/veritat_{slug}.jpg', title=f'VERITAT {slug} — {idx["signat"]}')
def cand_sheets():
    for slug in ['castellar', 'rubi', 'linyola', 'bell-lloc', 'alcoletge', 'vilanova', 'anciles']:
        man = json.load(open(f'{S}/cands/{slug}/manifest.json')); cells = []
        for it in man['items']:
            for r in it['renders']:
                lab = f'{it["kind"]} | {it["rel"]}' + (f' p{r["page"]}' if it.get('pages', 1) > 1 else '') + (f' | rol {",".join(it["roles"])}' if it['roles'] else '')
                cells.append((lab, r['path']))
        for k in range(0, len(cells), 20):
            grid(cells[k:k + 20], f'{S}/view/cands_{slug}_{k // 20 + 1:02d}.jpg', W=330, H=250, cols=4, title=f'CANDIDATS {slug} ({k + 1}-{min(k + 20, len(cells))} de {len(cells)})')
os.makedirs(f'{S}/view', exist_ok=True)
truth_sheets(); cand_sheets()
print('\n'.join(sorted(os.listdir(f'{S}/view'))))
