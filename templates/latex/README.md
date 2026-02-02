# G3DT LaTeX Report Template

Pixel-perfect LaTeX template for G3DT geotechnical reports, using fonts extracted from the original PDF.

## Requirements

- **XeLaTeX** (for custom font support)
- **TinyTeX** or full TeX Live installation
- Required packages: `titlesec`, `booktabs`, `enumitem`, `tocloft`, `eso-pic`, `lastpage`

## Files

```
latex/
├── g3dt-report.cls          # Document class with G3DT styling
├── sample-report.tex         # Sample report (Rubí 3001631)
├── sample-report.pdf         # Generated PDF
├── fonts/
│   └── Swiss721BT-LightExtended.ttf  # Extracted subset font
└── assets/
    ├── g3-logo-circular.png  # G3 logo (header, cover)
    ├── 25-anys-banner.png    # Anniversary banner
    ├── g3-watermark.png      # Cover watermark
    └── company-stamp.png     # Signature page seal
```

## Usage

```bash
# Compile with XeLaTeX (run twice for cross-references)
xelatex sample-report.tex
xelatex sample-report.tex
```

## Font Notes

The extracted `Swiss721BT-LightExtended.ttf` is a **subset font** containing ~109 glyphs from the original PDF. It includes:
- Full lowercase alphabet
- 25/26 uppercase letters
- All digits
- Catalan accented characters (àèéíòóúüïç)

For characters not in the subset, the template falls back to **Liberation Sans** (a metrically-compatible Arial alternative available on Linux).

## Styling (from PDF analysis)

| Element | Font | Size | Color |
|---------|------|------|-------|
| Body text | Swiss721BT-LightExtended | 10pt | Black |
| Section headings | Swiss721BT-LightExtended | 12pt | #003300 (dark green) |
| Subsection headings | Swiss721BT-LightExtended | 11pt | #003300 |
| Tables | Swiss721BT-LightExtended | 9pt | Black / White on green |
| Footer website | Liberation Sans | 9pt | #008000 (green) |
| Page number | Liberation Sans | 10pt | White on #4A7C59 box |

## Custom Commands

```latex
% Set document title (appears in header)
\setg3doctitle{3001631/Estudi geològic – geotècnic_RUBÍ}

% Create cover page
\makecover{Client}{Expedient}{Date}{Description}{Location}

% Create signature page
\signaturepage{Location}{Date}{Signers}

% Green table header
\tableheader{Column Name}

% Use G3 font explicitly
\gthreetext{This text uses the extracted font}
```

## Colors Defined

```latex
\definecolor{g3green-headings}{HTML}{003300}  % Section headings
\definecolor{g3green-links}{HTML}{008000}     % Website links
\definecolor{g3green-box}{HTML}{4A7C59}       % Page number box
\definecolor{g3green-light}{HTML}{8FBC8F}     % Light accents
\definecolor{g3gray-table}{HTML}{F5F5F5}      % Table rows
```

## Comparison with python-docx

| Feature | python-docx | LaTeX |
|---------|-------------|-------|
| Font control | Limited (Word substitution) | Precise (embedded fonts) |
| Color accuracy | Good | Excellent |
| Positioning | Approximate | Exact |
| Output format | DOCX | PDF |
| Editing by client | Easy (Word) | Requires LaTeX |

**Recommendation**: Use LaTeX for final delivery PDFs, python-docx for editable drafts.

## Next Steps

1. Create Python generator script (`generate_latex.py`)
2. Test with all 4 sample reports
3. Add DPSH graph generation (matplotlib → PDF)
4. Add cross-section diagram generation
