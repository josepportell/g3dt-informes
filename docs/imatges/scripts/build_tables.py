"""Taules markdown: per projecte (figura del signat · peu · procedència per hash · nosaltres) i mapa per fitxer. -> $S/tables/<slug>.md"""
import os, json, re
S = '/tmp/claude-1000/-home-josep-projects-claudecode-job-clients-g3dt-prod/a25f4f53-8ad8-4eaf-b120-f6cbb34cfb6d/scratchpad'
R = '/home/josep/projects/claudecode-job/clients/g3dt-prod'
OURS_FOR = {'fig_assaigs': 'fig_projecte'}
def verdict(c):
    if c['phash_d'] <= 10: return 'IGUAL (sencera)'
    if c['best'] >= 0.7: return 'RETALL/COMPOSICIÓ (fort)'
    if c['best'] >= 0.5: return 'retall probable'
    return 'no trobat per hash'
def build(slug):
    tr = json.load(open(f'{R}/docs/imatges/veritat/{slug}/index.json'))
    ours = json.load(open(f'{S}/nostres/{slug}/index.json'))
    mt = {t['n']: t for t in json.load(open(f'{S}/match/{slug}.json'))['truth']}
    man = json.load(open(f'{S}/cands/{slug}/manifest.json'))
    fonts = {r['n']: r for r in json.load(open(f'{S}/nostres/fonts.json'))[slug]}
    pool = {}; used = set()
    for o in ours['images']:
        if o['slot'] not in ('static_plantilla', 'fig_spt_cullera'): pool.setdefault(o['slot'], []).append(o)
    L = [f'| # | Figura del signat (peu) | ranura | mides | procedència per hash (top) | veredicte hash | nosaltres (bloc 4b) |', '|---|---|---|---|---|---|---|']
    src_files = {}
    for im in tr['images']:
        if im['slot'] in ('static_plantilla',): continue
        if im['slot'] == 'fig_spt_cullera':
            L.append(f'| {im["n"]} | {im["caption"][:70]} | {im["slot"]} | {im["dims"][0]}×{im["dims"][1]} | (estàtica, la posa el generador) | — | igual |'); continue
        t = mt.get(im['n']); top = t['top'][0] if t and t['top'] else None
        if top:
            ex = top.get('pos_in') if top['ncc_in'] >= top['ncc_rev'] else top.get('pos_rev')
            psr = ex.get('psr') if isinstance(ex, dict) else '?'
            dirn = 'veritat dins cand.' if top['ncc_in'] >= top['ncc_rev'] else 'cand. dins veritat'
            prov = f'`{top["rel"]}`' + (f' p{top["page"]}' if 'pdf' in top['kind'] else '') + f' — ph={top["phash_d"]}, ncc={top["best"]}, psr={psr}, escala {top["scale_in"] if top["ncc_in"] >= top["ncc_rev"] else top["scale_rev"]} ({dirn})'
            v = verdict(top)
            alt = [c for c in t['top'][1:3] if c['phash_d'] <= 10 or c['best'] >= 0.5]
            if alt: prov += '; també ' + ', '.join(f'`{c["rel"][-30:]}`' + (f' p{c["page"]}' if 'pdf' in c['kind'] else '') + f' ({c["best"]})' for c in alt)
            if v != 'no trobat per hash': src_files.setdefault(top['rel'], []).append(f'Fig/Foto {im["n"]} ({im["slot"]})')
        else: prov, v = '—', '—'
        oslot = OURS_FOR.get(im['slot'], im['slot']); cand = [o for o in pool.get(oslot, []) if o['n'] not in used]
        if cand:
            o = cand[0]; used.add(o['n'])
            if o['pending']: ours_s = 'PENDENT'
            else:
                fo = fonts.get(o['n'], {})
                srcs = f'← `{fo["src"][0]}`' + (f' p{fo["src"][1]}' if fo['src'][1] > 1 or 'pdf' in fo['src'][2] else '') if fo.get('src') else '← (font no identificada per phash: composició/retall nostre)'
                eq = ' **= Eva**' if fo.get('eva') and fo['eva'][0] == im['n'] else (f' (= Eva {fo["eva"][0]})' if fo.get('eva') else ' ≠ Eva')
                ours_s = f'{o["dims"][0]}×{o["dims"][1]} {srcs}{eq}'
        else: ours_s = 'absent (cap ranura)'
        cap = (im['caption'] or f'(sense peu; secció {im["heading"][:25]})')[:70]
        L.append(f'| {im["n"]} | {cap} | {im["slot"]} | {im["dims"][0]}×{im["dims"][1]} | {prov} | {v} | {ours_s} |')
    # mapa per fitxer
    M = ['| fitxer | tipus | rol (file_mapping) | ús segons el signat |', '|---|---|---|---|']
    for it in man['items']:
        rel = it['rel']; k = it['kind']
        if k in ('validation',): continue
        use = '**va a l\'informe**: ' + ', '.join(src_files[rel]) if rel in src_files else ''
        if not use:
            if k == 'pdf_skip': use = 'auxiliar (informe/pressupost/laboratori: text, no imatge)'
            elif k == 'pdf_aux': use = 'auxiliar (annex DPSH: taules)'
            elif k == 'fh11': use = 'original FreeHand de l\'annex (vegeu FH11→pdf)'
            elif k == 'fh11_pdf': use = 'render FH11 (font de visió)'
            elif it['roles'] and any('field_sheet' in r or 'field' in r for r in it['roles']): use = 'auxiliar (full de camp)'
            elif k == 'pdf_v0': use = 'versió antiga de l\'annex'
            else: use = 'no s\'usa a l\'informe (o no trobat per hash)'
        M.append(f'| `{rel}` | {k}' + (f' {it.get("pages")} pàg' if it.get('pages') else '') + f' | {", ".join(it["roles"]) or "—"} | {use} |')
    os.makedirs(f'{S}/tables', exist_ok=True)
    open(f'{S}/tables/{slug}.md', 'w').write('\n'.join(L) + '\n\n' + '\n'.join(M) + '\n')
    return len(L) - 2, len(M) - 2
if __name__ == '__main__':
    import sys
    for slug in (sys.argv[1:] or ['castellar', 'rubi', 'linyola', 'bell-lloc', 'alcoletge', 'vilanova', 'anciles']): print(slug, build(slug))
