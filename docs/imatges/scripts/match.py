"""Aparellament veritat <-> candidats. Nivell 1: phash sencer. Nivell 2: NCC multiescala fina (veritat dins candidat i candidat dins veritat),
a resolucio reduida i amb desenfocat lleu per tolerar desalineacions; inclou l'escala nativa 1:1 (mateixa resolucio de pixel)."""
import os, sys, json, time
import numpy as np
from PIL import Image, ImageOps
import imagehash
from scipy.signal import fftconvolve
from scipy.ndimage import gaussian_filter
from multiprocessing import Pool
S = '/tmp/claude-1000/-home-josep-projects-claudecode-job-clients-g3dt-prod/a25f4f53-8ad8-4eaf-b120-f6cbb34cfb6d/scratchpad'
TRUTH = '/home/josep/g3dt-e2e/imatges/veritat'
IDX = '/home/josep/projects/claudecode-job/clients/g3dt-prod/docs/imatges/veritat'
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
def run(slug):
    t0 = time.time()
    idx = json.load(open(os.path.join(IDX, slug, 'index.json')))
    man = json.load(open(os.path.join(S, 'cands', slug, 'manifest.json')))
    cands = [{'rel': it['rel'], 'kind': it['kind'], 'page': r['page'], 'path': r['path'], 'roles': it['roles'], 'pt': r.get('pt')}
             for it in man['items'] for r in it['renders']]
    C = []
    for c in cands:
        try:
            g, orig = load_gray(c['path']); ph = imagehash.phash(Image.open(c['path']).convert('RGB'))
            C.append((c, g, orig, ph))
        except Exception: C.append((c, None, None, None))
    out = []
    for im in idx['images']:
        if im['slot'] in ('static_plantilla', 'fig_spt_cullera'): continue
        p = os.path.join(TRUTH, slug, im['file'])
        if p.lower().endswith('.wmf'): p = p[:-4] + '.png'
        T, torig = load_gray(p); tph = imagehash.phash(Image.open(p).convert('RGB'))
        res = []
        for c, g, orig, ph in C:
            if g is None: continue
            d = int(tph - ph)
            nat_in = torig[0] * (g.shape[1] / orig[0]); nat_rev = orig[0] * (T.shape[1] / torig[0])
            s_in, sc_in, pos_in = best_scaled(g, T, native=nat_in)
            # inversa (candidat dins veritat) nomes te sentit per a PECES: PNG d'ALTRES, imatges soltes, fotos; i nomes per a figures
            if (not im['slot'].startswith('foto_')) and c['kind'] in ('png_annex_altres', 'img', 'foto'):
                s_rev, sc_rev, pos_rev = best_scaled(T, g, native=nat_rev)
            else: s_rev, sc_rev, pos_rev = -1.0, None, None
            res.append({'rel': c['rel'], 'page': c['page'], 'kind': c['kind'], 'roles': c['roles'], 'phash_d': d,
                        'ncc_in': round(s_in, 3), 'scale_in': sc_in, 'pos_in': pos_in,
                        'ncc_rev': round(s_rev, 3), 'scale_rev': sc_rev, 'pos_rev': pos_rev,
                        'best': round(max(s_in, s_rev), 3)})
        res.sort(key=lambda r: (-(r['phash_d'] <= 10), -r['best']))
        out.append({'n': im['n'], 'file': im['file'], 'slot': im['slot'], 'caption': im['caption'], 'top': res[:8]})
        r0 = res[0]
        print(f"[{slug}] {im['n']:2d} {im['slot']:22s} top: {r0['rel'][-42:]} p{r0['page']} ph={r0['phash_d']} ncc={r0['best']} (in {r0['ncc_in']}@{r0['scale_in']} / rev {r0['ncc_rev']}@{r0['scale_rev']})", flush=True)
    json.dump({'slug': slug, 'n_cands': len(cands), 'secs': round(time.time() - t0), 'truth': out},
              open(os.path.join(S, 'match', slug + '.json'), 'w'), ensure_ascii=False, indent=1)
    return slug, round(time.time() - t0)
if __name__ == '__main__':
    os.makedirs(os.path.join(S, 'match'), exist_ok=True)
    slugs = sys.argv[1:] or ['castellar', 'rubi', 'linyola', 'bell-lloc', 'alcoletge', 'vilanova', 'anciles']
    with Pool(min(7, len(slugs))) as pool:
        for slug, secs in pool.imap_unordered(run, slugs): print('DONE', slug, secs, 's', flush=True)
