"""Tier-A truth map: where does each Tier-A value of Eva's signed report actually live in the project folder?

Read-only. Text-searches every *source* document (excluding Eva's own outputs: informes, PDF/ annexos, FH11) for each
Tier-A reference value (expedient, client, architect, municipality, surfaces, field date, cota).
Output: per project x field -> list of documents that contain it (+ JSON).  Evidence for
docs/ANALISI-NIVELL-A-LECTURA-HUMANA-2026-08-23.md §3.  Usage: .venv/bin/python scripts/tier_a_truth_map.py OUT.json
"""
"""
import json, re, sys, unicodedata, datetime, io, zipfile
from pathlib import Path
from collections import defaultdict
import fitz, openpyxl, xlrd, extract_msg, docx

PROJ = {
    '3001621 CASTELLAR DEL VALLES': Path('/mnt/c/claude/g3dt/projectes/3001621 CASTELLAR DEL VALLES'),
    '3001631 RUBI': Path('/mnt/c/claude/g3dt/projectes/3001631 RUBI'),
    '4001607 LINYOLA': Path('/mnt/c/claude/g3dt/projectes/4001607 LINYOLA'),
    '4001612 BELL-LLOC': Path('/mnt/c/claude/g3dt/projectes/4001612 BELL-LLOC'),
    '4001670 ALCOLETGE': Path('/mnt/c/claude/g3dt/projectes/4001670 ALCOLETGE'),
    '4001671 VILANOVA DE SEGRIA': Path('/mnt/c/claude/g3dt/projectes/4001671 VILANOVA DE SEGRIA'),
    '4001679 ANCILES': Path('/mnt/c/claude/g3dt/projectes/4001679 ANCILES'),
    '3001706 C.TULIPA CERDANYOLA': Path('/mnt/c/claude/g3dt/projectes-debug/3001706 C.TULIPA CERDANYOLA'),
}
REF_DIR = Path('reference-material')

EXCLUDE_DIRS = {'validation', '_validation', 'PDF', 'PDF-V0', 'PDF V0', 'PDF_V0', 'LLETRA', 'LETRA'}
EXCLUDE_NAME = re.compile(r'_informe|_generated|portada|INFORME_FIX|_user_data|Thumbs\.db|\.FH11$|\.tmp$|\.lock|\.dwg$', re.I)

def norm(s):
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode()
    s = s.lower().replace('’', "'").replace('·', '.')
    return re.sub(r'\s+', ' ', s).strip()

def pdf_text(p):
    try:
        d = fitz.open(p)
        pages = [pg.get_text() for pg in d]
        scanned = sum(1 for t in pages if len(t.strip()) < 50)
        return '\n'.join(pages), f"{len(pages)}p" + (f" ({scanned} escanejades)" if scanned else '')
    except Exception as e:
        return '', f'ERR {e}'

def xlsx_text(p):
    out = []
    try:
        wb = openpyxl.load_workbook(p, data_only=True)
        for ws in wb.worksheets:
            for row in ws.iter_rows(values_only=True):
                for c in row:
                    if c is None: continue
                    if isinstance(c, (datetime.date, datetime.datetime)):
                        out.append(c.strftime('%d/%m/%Y')); out.append(c.strftime('%Y-%m-%d')); out.append(c.strftime('%d-%m-%Y'))
                    else:
                        out.append(str(c))
    except Exception as e:
        return '', f'ERR {e}'
    return '\n'.join(out), 'xlsx'

def xls_text(p):
    out = []
    try:
        wb = xlrd.open_workbook(p)
        for sh in wb.sheets():
            for r in range(sh.nrows):
                for c in sh.row(r):
                    if c.ctype == xlrd.XL_CELL_DATE:
                        dt = xlrd.xldate_as_datetime(c.value, wb.datemode)
                        out += [dt.strftime('%d/%m/%Y'), dt.strftime('%Y-%m-%d'), dt.strftime('%d-%m-%Y')]
                    elif c.ctype == xlrd.XL_CELL_NUMBER and 40000 < c.value < 50000:
                        try:
                            dt = xlrd.xldate_as_datetime(c.value, wb.datemode)
                            out += [dt.strftime('%d/%m/%Y'), dt.strftime('%Y-%m-%d')]
                        except Exception: pass
                        out.append(str(c.value))
                    elif c.value not in ('', None):
                        out.append(str(c.value))
    except Exception as e:
        return '', f'ERR {e}'
    return '\n'.join(out), 'xls'

def msg_text(p):
    """Body + subject + attachment names + text of text-like attachments (pdf/xlsx/docx)."""
    out, att = [], []
    try:
        m = extract_msg.Message(str(p))
        out += [m.subject or '', m.sender or '', m.body or '']
        for a in m.attachments:
            name = a.longFilename or a.shortFilename or ''
            att.append(name)
            data = a.data
            if not isinstance(data, (bytes, bytearray)): continue
            ext = Path(name).suffix.lower()
            try:
                if ext == '.pdf':
                    d = fitz.open(stream=bytes(data), filetype='pdf')
                    out.append('\n'.join(pg.get_text() for pg in d))
                elif ext == '.xlsx':
                    wb = openpyxl.load_workbook(io.BytesIO(bytes(data)), data_only=True)
                    for ws in wb.worksheets:
                        for row in ws.iter_rows(values_only=True):
                            out += [str(c) for c in row if c is not None]
                elif ext == '.docx':
                    dd = docx.Document(io.BytesIO(bytes(data)))
                    out += [para.text for para in dd.paragraphs]
            except Exception: pass
    except Exception as e:
        return '', f'ERR {e}', []
    return '\n'.join(out), f'msg ({len(att)} adj: ' + ', '.join(a[:25] for a in att[:6]) + ')', att

def docx_text(p):
    try:
        d = docx.Document(p)
        t = [para.text for para in d.paragraphs]
        for tb in d.tables:
            for row in tb.rows:
                t += [c.text for c in row.cells]
        return '\n'.join(t), 'docx'
    except Exception as e:
        return '', f'ERR {e}'

def zip_text(p):
    out, names = [], []
    try:
        z = zipfile.ZipFile(p)
        for n in z.namelist():
            names.append(n)
            if n.lower().endswith('.pdf'):
                try:
                    d = fitz.open(stream=z.read(n), filetype='pdf')
                    out.append('\n'.join(pg.get_text() for pg in d))
                except Exception: pass
    except Exception as e:
        return '', f'ERR {e}'
    return '\n'.join(out), f'zip ({len(names)} fitxers)'

def collect_sources(root):
    srcs = {}
    images = []
    for p in sorted(root.rglob('*')):
        if not p.is_file(): continue
        rel = p.relative_to(root)
        if any(part in EXCLUDE_DIRS for part in rel.parts): continue
        if EXCLUDE_NAME.search(p.name): continue
        ext = p.suffix.lower()
        if ext == '.pdf': t, info = pdf_text(p)
        elif ext == '.xlsx': t, info = xlsx_text(p)
        elif ext == '.xls': t, info = xls_text(p)
        elif ext == '.msg': t, info, _ = msg_text(p)
        elif ext == '.docx': t, info = docx_text(p)
        elif ext == '.zip': t, info = zip_text(p)
        elif ext == '.txt':
            try: t, info = p.read_text(errors='ignore'), 'txt'
            except Exception: t, info = '', 'txt ERR'
        elif ext in ('.jpg', '.jpeg', '.png'):
            images.append(str(rel)); continue
        else: continue
        srcs[str(rel)] = (norm(t), info)
    return srcs, images

def date_variants(txt):
    """'24 de octubre de 2025' -> ['24/10/2025','24-10-2025','2025-10-24','24/10/25', '24 de octubre de 2025', '24 d'octubre']"""
    months = {'gener':1,'febrer':2,'març':3,'marc':3,'abril':4,'maig':5,'juny':6,'juliol':7,'agost':8,'setembre':9,'octubre':10,'novembre':11,'desembre':12,
              'enero':1,'febrero':2,'marzo':3,'mayo':5,'junio':6,'julio':7,'septiembre':9,'noviembre':11,'diciembre':12}
    t = norm(txt)
    m = re.search(r'(\d{1,2})\s*d[e\' ]*\s*([a-z]+)\s*(?:de|del)?\s*(\d{4})', t)
    if not m: return [t]
    d, mon, y = int(m.group(1)), months.get(m.group(2)), int(m.group(3))
    if not mon: return [t]
    return [f'{d:02d}/{mon:02d}/{y}', f'{d:02d}-{mon:02d}-{y}', f'{y}-{mon:02d}-{d:02d}', f'{d}/{mon}/{y}', f'{d:02d}/{mon:02d}/{str(y)[2:]}', f'{d} de {m.group(2)}', f'{d} d {m.group(2)}', f"{d} d'{m.group(2)}"]

def num_variants(v):
    s = norm(v).replace(' m2', '').strip()
    s = re.sub(r'[^\d.,+]', '', s)
    parts = re.split(r'\+', s)
    out = []
    for part in parts:
        if not part: continue
        raw = part.replace('.', '').replace(',', '.') if re.match(r'^\d{1,3}\.\d{3}$', part) else part
        try: f = float(raw.replace(',', '.'))
        except ValueError: continue
        cands = {f'{f:.2f}', f'{f:.1f}', f'{f:g}', f'{f:.2f}'.replace('.', ','), f'{f:.1f}'.replace('.', ','), str(int(f)) if f == int(f) else f'{f:g}'}
        if f >= 1000: cands.add(f'{int(f):,}'.replace(',', '.'))
        out.append((part, sorted(cands)))
    return out

FIELDS = ['expedient', 'client', 'architect_name_upper', 'architect_company', 'municipality', 'superficie_parcela', 'superficie_construida', 'data_camp_text', 'cota_referencia']
MUNI_FIX = {'4001670 ALCOLETGE': 'Alcoletge', '4001671 VILANOVA DE SEGRIA': 'Vilanova de Segrià', '4001679 ANCILES': 'Anciles', '3001706 C.TULIPA CERDANYOLA': 'Cerdanyola', '3001631 RUBI': 'Rubí'}

def main():
    report = {}
    for name, root in PROJ.items():
        refp = (REF_DIR / name / 'validation' / 'eva_reference_values.json')
        if not refp.exists(): refp = root / 'validation' / 'eva_reference_values.json'
        ref = {k: (v.get('value') if isinstance(v, dict) else v) for k, v in json.load(open(refp))['variables'].items()}
        srcs, images = collect_sources(root)
        res = {}
        for f in FIELDS:
            v = ref.get(f)
            if f == 'municipality': v = MUNI_FIX.get(name, v)
            if v in (None, '', '—'): res[f] = {'value': None, 'hits': []}; continue
            v = str(v)
            if f == 'data_camp_text': variants = date_variants(v); kind = 'date'
            elif f in ('superficie_parcela', 'superficie_construida', 'cota_referencia'):
                variants = [c for _, cs in num_variants(v) for c in cs]; kind = 'num'
            elif f == 'expedient': variants = [re.search(r'\d{7}', v).group(0)] if re.search(r'\d{7}', v) else [norm(v)]; kind = 'id'
            else:
                nv = norm(re.sub(r'^(sr\.|sra\.)\s*', '', v, flags=re.I))
                variants = [nv]
                toks = [t for t in nv.split() if len(t) > 2 and t not in ('s.l', 'slu', 's.l.', 'sl')]
                if len(toks) >= 2: variants.append(' '.join(toks[-2:]))  # surname pair
                if len(toks) >= 2: variants.append(' '.join(toks[:2]))
                kind = 'text'
            hits = []
            for rel, (t, info) in srcs.items():
                which = [c for c in variants if c and norm(c) in t]
                if which: hits.append((rel, info, which[0]))
            res[f] = {'value': v, 'variants': variants[:4], 'hits': hits}
        report[name] = {'fields': res, 'n_sources': len(srcs), 'n_images': len(images), 'images': images}
    json.dump(report, open(sys.argv[1] if len(sys.argv) > 1 else 'truth_map.json', 'w'), indent=1, ensure_ascii=False)
    # human summary
    for name, r in report.items():
        print(f"\n=== {name}  ({r['n_sources']} fonts de text, {r['n_images']} imatges)")
        for f, d in r['fields'].items():
            if d['value'] is None: print(f"  {f:22s} — (sense referència)"); continue
            print(f"  {f:22s} {str(d['value'])[:40]!r:44s} -> {len(d['hits'])} docs")
            for rel, info, c in d['hits'][:8]:
                print(f"        · {rel[:75]:75s} [{info[:40]}] ~{c[:25]}")

if __name__ == '__main__':
    main()
