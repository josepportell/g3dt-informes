# Els `.FH11` d'Eva es poden llegir: libfreehand via LibreOffice (prova 2026-09-04)

**Estat:** provat en sec sobre 3 fitxers, sense tocar cap projecte ni cap codi de lectura. **No integrat.**
**Origen:** nota del Josep (2026-09-04): «mai hem obert els fitxers FH11; podríem llegir-los utilitzant libfreehand?»
+ recerca que adjunta (apèndix A, literal).

## Per què importa

Eva dibuixa **tots** els annexos (sondeig, tall de correlació, plànol de situació, fotografies, mapa geològic) amb
FreeHand 11 i n'exporta PDF a `PDF/ANNEXES/`. Als 8 projectes hi ha **35 `.FH11`** (llista a §Inventari): són
l'**original** de cada annex; el PDF n'és l'exportació. Fins avui l'inventari els marcava `annex_freehand_no_llegible`
i els saltava. Conseqüència mesurada: a **Anciles** no hi ha `PDF/` (només `PDF_V0/`, exclosa per la regla «versió
anterior») i el sistema es queda **sense cap cota** (9 cel·les en blanc, causa **I1** de la mesura dels 8).

## Què hi ha instal·lat (WSL2 Ubuntu, 2026-09-04)

- `libfreehand-0.1.so.1.0.2` a `/usr/lib/x86_64-linux-gnu/` — **ja hi és** (dependència de LibreOffice).
- `soffice` / `libreoffice` a `/usr/bin` — importa FH11 «as a Draw document» amb el filtre de libfreehand.
- `fh2svg` / `fh2text` / `fh2raw` (`libfreehand-tools`): **no instal·lats**. Instal·lació: `sudo apt install
  libfreehand-tools` (cal el Josep: `! sudo apt install libfreehand-tools`). No és imprescindible: LibreOffice ja
  fa la conversió.
- `pdftotext`, `pdftoppm` (poppler): sí. `inkscape`: no cal (pdftoppm en fa les previsualitzacions).

## Prova (3 fitxers, scratchpad, cap escriptura a `/mnt/c` ni a `~/g3dt-e2e`)

```bash
soffice --headless --convert-to pdf --outdir OUT  "4001670_tall de correlació.FH11"   # 96 KB  → PDF 101 KB, 1 pàg.
soffice --headless --convert-to pdf --outdir OUT  "4001679_sondeos.FH11"              # 4,6 MB → PDF 3,9 MB, 1 pàg.
soffice --headless --convert-to pdf --outdir OUT  "4001612_sondeig.FH11"              # 7,6 MB → PDF 1,4 MB, 1 pàg.
soffice --headless --convert-to svg --outdir OUT  "4001670_tall de correlació.FH11"   # SVG 202 KB, 38 <text>, 106 tspans
pdftotext -layout X.pdf X.txt ; pdftoppm -png -r 60 -f 1 -l 1 X.pdf X_p
```

| Fitxer | Conversió | Render (PNG inspeccionat) | Text extret |
|---|---|---|---|
| Alcoletge `tall de correlació` | OK, 1 s | **Tot hi és**: planta amb P-1/P-2/P-3, secció A-A', llegenda (Nivell 1 rebliment antròpic / Nivell 2 lutites), línia d'humitat, cota de fonamentació, Nb per punt, caixetí (títol, adreça, exp. 4001670, febrer 2026). Text **reflueix** per substitució de tipus de lletra («LLEGE/NDA», «P-1» vertical, peus solapats) | `pdftotext`: **fragmentat lletra a lletra** (3,2 KB) — pitjor que el PDF oficial d'Eva (`PDF/ANNEXES`, 2,0 KB, «LLEGENDA», «Nivell 1: Rebliment antròpic.», «Nb=5» nets). L'SVG conserva les cadenes en `tspan` però també partides («Pàgin», «a 1/1») |
| Anciles `sondeos` (el cas I1) | OK, ~20 s | **4 «pàgines» del FH aplanades en un sol llenç**: full S-1 + fotos S-1 / full S-2 + fotos S-2. Capçalera completa (**+1106.65 msnm** S-1, **+1106.42** S-2, 19/02/2026, TPS S.L., Sr. Daniel Fernández, Ariadna Salla M. Geòloga), columna litològica amb farcits, descripcions («Arcillas limosas y arenosas con puntualmente gravitas y bolos de granito», «Bolos y gravas de granito en matriz arenosa y arcillosa»), fotos incrustades. Peus de foto il·legibles (reflueix) | 98 KB de text en columnes molt amples (llenç únic) i **duplicat** (dues còpies de cada bloc); hi ha «+1106.65 msnm», «7 viviendas adosadas», «Calle Gral Ferraz 20» |
| Bell-lloc `sondeig` | OK, ~15 s | (no inspeccionat visualment) | 55 KB: «199.50m», «6/10/2025», «Eva Vázquez Marcet», «Geóloga núm. 4302», títol del projecte |

**Veredicte.** (1) **Sí que es poden llegir**, i el render és fidel en geometria, colors, capçaleres i columnes: serveix
com a **font de visió** (Claude llegeix el PNG igual que llegeix el PDF oficial). (2) Per a **text extret**, el PDF
exportat per la mateixa FreeHand és **millor** que la ruta libfreehand (que trenca les cadenes per substitució de fonts);
per tant el FH11 no substitueix el PDF oficial quan aquest existeix. (3) El valor real és de **cobertura**: quan l'annex
no té PDF vigent (Anciles) o el PDF és una versió antiga, el `.FH11` és l'original i és llegible. (4) Cal esperar
**diverses pàgines aplanades en una** (4 a Anciles): el lector ha de tallar el llenç per fulls o llegir-lo sencer a
resolució alta.

## Què faria (després de la mesura, no ara)

1. `inventory.py`: `.FH11` passa de `annex_freehand_no_llegible` (skip) a **`annex_freehand` amb conversió prèvia**
   (`soffice --convert-to pdf`, cache a `G3DT_CACHE_DIR` per md5) **només quan no hi ha PDF vigent del mateix annex**
   (regla I1: sense `PDF/` → FH11 o `PDF_V0`). Prioritat: PDF oficial > FH11 > PDF_V0.
2. El lector de l'annex convertit treballa amb la **visió** (PNG a 150-200 dpi, o retall per full), no amb `pdftotext`.
3. Cost: la conversió és local i gratuïta (1-20 s); l'única despesa és la crida de lectura, que ja fem per al PDF.
4. Prova d'acceptació: Anciles amb FH11 → les 9 cotes deixen d'estar en blanc; Bell-lloc/Castellar (que tenen PDF) no
   canvien. Mesurar temps i ERR abans/després (franja de soroll 2,8 pp).
5. `libfreehand-tools` (`fh2svg`/`fh2text`) només si volem text estructurat de l'SVG; amb el que hem vist, poc guany.

## Inventari dels `.FH11` (e2e, 2026-09-04) — 35 fitxers, 8/8 projectes

Castellar 5 (fotografies, plànol, **sondeig 7,1 MB**, tall, mapa geològic) · Rubí 4 (fotografies, plànol, tall, mapa) ·
Tulipa 8 (×2 cases: fotografies, plànol, **sondeig 8,5 MB**, tall) · Linyola 3 (fotografies, plànol, tall) ·
Bell-lloc 4 (fotografies, plànol, **sondeig 7,7 MB**, tall) · Alcoletge 3 (fotografies, plànol, tall) ·
Vilanova 4 (corte, fotografías, plano, mapa) · Anciles 4 (corte, fotografías, plano, **sondeos 4,6 MB**).
Els de sondeig són els grossos (fotos incrustades). `rtk proxy find ~/g3dt-e2e/projectes -iname "*.fh11"` per la llista.

---

## Apèndix A — Recerca aportada pel Josep (2026-09-04), literal

Yes. For your goal—**seeing the contents and making the drawings usable by Claude Code**—convert each `.FH11` (Macromedia/Adobe FreeHand 11) file to **SVG** first, and also create a **PDF or PNG preview** for quick inspection.

The best route is usually **local, open-source conversion with `libfreehand`**, rather than uploading proprietary drawings to a random web converter. `libfreehand` is an open-source FreeHand parser maintained in the Document Liberation ecosystem and explicitly supports FreeHand document versions 3 through 11, including FH11. Its utilities can output SVG, text, or a raw representation. [wiki.documentfoundation](https://wiki.documentfoundation.org/DLP/Libraries/libfreehand)

## Recommended workflow

| Goal | Output | Why |
|---|---|---|
| Preserve editable vector geometry | SVG | Open, text-based vector format; can be inspected, versioned, parsed, and edited |
| Quickly see the artwork | PDF or PNG | Easy preview in browser, OS viewer, or Claude Code image workflow |
| Extract any selectable text | TXT | Useful for indexing/searching document labels and copy |
| Open in a GUI for cleanup | SVG in Inkscape or Scribus | Lets you validate fidelity and repair minor import issues |

For a folder of files, I would produce:

```text
archive/
  original/
    drawing-01.FH11
    drawing-02.FH11
  converted/
    drawing-01.svg
    drawing-01.txt
    drawing-02.svg
    drawing-02.txt
  previews/
    drawing-01.png
    drawing-02.png
```

Keep the originals unchanged. Treat SVG as the working/open format and PDF/PNG as visual verification.

## Option 1: Local open-source conversion

### Ubuntu / WSL2

Given that you use WSL2/Ubuntu, this is likely the cleanest route:

```bash
sudo apt update
sudo apt install libfreehand-tools
```

Then convert one file:

```bash
fh2svg "drawing.FH11" "drawing.svg"
fh2text "drawing.FH11" "drawing.txt"
```

Batch-convert an entire directory safely:

```bash
mkdir -p converted

find . -maxdepth 1 -type f \( -iname '*.fh11' -o -iname '*.fh' \) -print0 |
while IFS= read -r -d '' f; do
  base="$(basename "$f")"
  name="${base%.*}"

  fh2svg "$f" "converted/$name.svg"
  fh2text "$f" "converted/$name.txt"
done
```

Then inspect the result:

```bash
ls -lh converted
```

To create browser-friendly PNG previews from the SVGs, use Inkscape headlessly:

```bash
sudo apt install inkscape
mkdir -p previews

for f in converted/*.svg; do
  name="$(basename "${f%.svg}")"
  inkscape "$f" --export-type=png --export-filename="previews/$name.png"
done
```

`libfreehand` is specifically intended to interpret/import Aldus, Macromedia, and Adobe FreeHand documents, and current Linux distributions package it as an import library/toolchain. [packages.debian](https://packages.debian.org/sid/libfreehand-0.1-1)

### macOS

With Homebrew:

```bash
brew install libfreehand
```

Then check which commands were installed:

```bash
brew list libfreehand
which fh2svg fh2text
```

The Homebrew formula describes `libfreehand` as an interpreter/importer for Aldus/Macromedia/Adobe FreeHand documents. [formulae.brew](https://formulae.brew.sh/formula/libfreehand)

### Windows without WSL

Use one of:

- **Scribus**: open/import the FH11 file, then export to PDF/SVG where viable.
- **Inkscape**: useful mainly once you have SVG; direct FH11 import support is less dependable than the `libfreehand` route.
- A temporary Linux environment—WSL2 is preferable if available.

Scribus is open-source and includes a dependency on `libfreehand`, which is why it can be a sensible GUI fallback. [packages.debian](https://packages.debian.org/sid/scribus)

## Making the results useful to Claude Code

Claude Code cannot meaningfully inspect a proprietary binary FH11 file on its own. But after conversion:

### SVG: best for technical analysis and reuse

SVG is XML text, so Claude Code can:

- Read the document structure: layers/groups, paths, colors, text objects, transforms.
- Search for visible labels, headings, logos, dimensions, and metadata.
- Help clean SVG markup or simplify paths.
- Generate a React/HTML/CSS version, if the FreeHand file is an old UI, diagram, or branded asset.
- Build an asset inventory across your whole folder.
- Convert or incorporate artwork into a web app, print workflow, or an architecture/construction report template.

Example prompt after conversion:

```text
Inspect every SVG in ./converted and create a Markdown inventory showing:
- filename
- canvas dimensions
- number of text elements
- extracted visible text
- colors used
- whether it appears to be a logo, diagram, drawing, or page layout
- any conversion anomalies or missing linked assets
```

### PNG/PDF: best for visual interpretation

Give Claude Code access to a generated PNG preview, then ask:

```text
Analyze the visual content of previews/drawing-01.png.
Describe all objects, readable labels, the likely purpose of the design,
and any issues you see with the SVG conversion.
```

A useful practical pattern is:

1. `FH11 → SVG` via `fh2svg`.
2. `SVG → PNG` via headless Inkscape.
3. Have Claude inspect both:
   - SVG for structure and extractable content.
   - PNG for what actually rendered.

That dual check catches common legacy-format issues: missing fonts, shifted text, bitmap links, clipping masks, gradients, or unusual FreeHand effects.

## Online converters

If the drawings are non-sensitive and you just need a quick answer today, online services do exist:

- **Convert.Guru** advertises conversion from FH11 to SVG, PDF, AI, EPS, JPG, and other formats. [convert](https://convert.guru/es/convertidor-de-fh11)
- **CoolUtils** advertises an FH11-to-PDF web converter. [coolutils](https://www.coolutils.com/es/online/FH11-to-PDF)
- **Dordio Design** advertises paid conversion of FH/FH11 to PDF, EPS, AI, CDR, SVG, and DXF. [dordiodesign](https://www.dordiodesign.com/en/convert-fh11-to-pdf-eps-or-ai-online-service)

However, I would regard these as **fallbacks**, not the primary method—especially for client files, drawings containing identifiers, or material you may later need to reproduce faithfully. They require sending files to a third party, and claims about "AI" or reverse conversion to FH11 on generic converter sites should be treated cautiously.

## Important caveats

- **FH11 is proprietary and old**, so no conversion is guaranteed pixel-perfect.
- The main risk is usually **fonts**: text may substitute, reflow, or become positioned differently.
- Embedded raster images may convert, but **linked external assets** can be missing if the original FreeHand document depended on files stored elsewhere.
- Complex blends, brushes, clipping, transparency, and multi-page/page-layout material may need manual cleanup in Inkscape or Scribus.
- An SVG that looks correct in a browser is normally the best evidence the conversion succeeded; retain the original FH11 regardless.

Adobe Illustrator is also often cited as a practical proprietary fallback for opening FH11 and saving to SVG, PDF, or EPS, but it is not necessary to try first if `libfreehand` produces usable output. [en.wikipedia](https://en.wikipedia.org/wiki/Wikipedia:Graphics_Lab/Images_to_improve/Archive/Feb_2008)

## Bottom line

Use **`libfreehand-tools` → `fh2svg`** as the first attempt. It is local, open source, supports FreeHand 11, produces an open format Claude Code can inspect directly, and avoids uploading the files. Generate **PNG previews with Inkscape** beside the SVGs so you can validate every conversion visually. [wiki.documentfoundation](https://wiki.documentfoundation.org/DLP/Libraries/libfreehand)

If `fh2svg` produces malformed or incomplete output for a particular file, try importing that file in **Scribus**, then export it; only after that would I use an online FH11-to-PDF/SVG converter for that specific problematic file.
