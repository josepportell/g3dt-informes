# G3DT Report Generation System - Technical Documentation

**Version:** 1.1
**Date:** 13 de gener de 2026
**Author:** Eficients / Josep Portell

---

## 1. Overview

The G3DT Report Generation System automates the creation of geotechnical reports (informes geotècnics) for G3 Desenvolupament Territorial S.L. The system preserves the exact corporate styling while allowing rapid generation of new reports with different project data.

### Key Capabilities

- **Preserves 100% brand styling** (fonts, colors, headers, footers, watermarks)
- **Generates complete reports** with all 4 sections + index (including toc 3 entries)
- **Includes images** (maps, photos) extracted from sample documents
- **Adapts content** to different locations and project types
- **Outputs editable Word documents** (.docx format)

---

## 2. Architecture

### 2.1 Base Template Approach

The system uses a **base template** (`base-template.docx`) that contains:

```
base-template.docx
├── Styles (Heading 1, 2, 3, Normal, Caption, toc 1/2/3, etc.)
├── Header 1 (First page - cover design with logo/watermark)
├── Header 2 (Regular pages - expedient/location info)
├── Footer (Company info: G3 DT, S.L. | www.g3dt.com | g3@g3dt.com)
└── Page setup (A4, margins, orientation)
```

**Why this approach?**
- Editing styles in Word is easier than coding them
- Changes to branding only require updating one file
- New report = copy template + insert content with style references

### 2.2 Generation Flow

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Project Data   │───▶│  Generator       │───▶│  Word Report    │
│  (JSON/dict)    │    │  (Python)        │    │  (.docx)        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
             ┌──────────────┐    ┌──────────────┐
             │ Base Template│    │   Images     │
             │ (styles)     │    │   (maps/     │
             └──────────────┘    │    photos)   │
                                 └──────────────┘
```

---

## 3. File Structure

```
clients/g3dt/demo/
├── base-template.docx           # Master template with all styles
├── generate_full_report.py      # Main generator (complete reports with images)
├── generate_styled_report.py    # Simpler generator (partial reports)
├── extract_images.py            # Utility: extract images from DOCX samples
├── analyze_styles.py            # Utility: analyze document styles
├── analyze_cover_watermark.py   # Utility: analyze cover structure
├── analyze_body_start.py        # Utility: analyze document body
├── analyze_header_detail.py     # Utility: analyze header structure
├── extract_sections.py          # Utility: extract sections from samples
├── images/                      # Standard images for reports
│   ├── location_map.png         # Figura 1: Location map (2.7 MB)
│   ├── site_plan.png            # Figura 2: Site plan with test locations
│   ├── geological_map.png       # Figura 4: Geological map
│   ├── site_photo_1.jpeg        # Fotografia 1: General site view
│   ├── dpsh_photo.jpeg          # Fotografia 2: DPSH machine
│   └── material_detail.jpeg     # Fotografia 3: Material detail
├── extracted-images/            # Images extracted from samples (for reference)
│   ├── 3001631_informe/         # Images from each sample
│   ├── 4001612_informe/
│   ├── 4001607_informe/
│   ├── 3001621_informe_v0/
│   └── all_images_mapping.json  # Combined image mapping
└── SYSTEM-DOCUMENTATION.md      # This file

clients/g3dt/demo-sections/
├── 01-antecedents.md            # Extracted section content
├── 02-treballs-camp.md
├── 03-descripcio.md
├── 04-conclusions.md
├── metadata.json                # Demo scenarios data
└── generated/                   # Output folder for generated reports

clients/g3dt/samples/
├── 3001631_informe.docx         # Base sample (Rubí)
├── 4001612_informe.docx         # Bell-Lloc sample
├── 4001607_informe.docx         # Additional sample
└── 3001621_informe_v0.docx      # Additional sample
```

---

## 4. How It Works

### 4.1 Base Template Creation

The base template is created from an actual G3DT sample report:

1. **Copy** a real report (e.g., `3001631_informe.docx`)
2. **Preserve** all styles, headers, footers, page setup
3. **Clear** body content (but keep the structure)

This ensures the generated reports look identical to real G3DT reports.

### 4.2 Content Generation

The generator creates content with proper style references:

```python
# Adding a heading
doc.add_paragraph("1. PRESENTACIÓ DE L'ESTUDI", style="Heading 1")

# Adding a Heading 3 with forced left alignment
self._add_heading3(doc, "2.1.1. Descripció de les parcel·les adjacents")

# Adding a table with G3DT green headers
table = doc.add_table(rows=3, cols=2)
for cell in table.rows[0].cells:
    shade_cell(cell, "4A7C59")  # G3DT green (#4A7C59)

# Adding a figure with image and caption
self._add_figure(doc, "figura_1", "Figura 1. Situació de la zona d'estudi.")

# Adding a caption
doc.add_paragraph("Taula 1. Descripció...", style="Caption")
```

### 4.3 Style Mapping

| Content Type | Word Style | Notes |
|--------------|------------|-------|
| Main sections | `Heading 1` | Green, 14pt |
| Subsections | `Heading 2` | Dark, 12pt |
| Sub-subsections | `Heading 3` | 11pt, left-aligned (forced) |
| Body text | `Normal` | Calibri 11pt |
| Figure/table captions | `Caption` | Italic, centered |
| TOC level 1 | `toc 1` | Main sections |
| TOC level 2 | `toc 2` | Subsections |
| TOC level 3 | `toc 3` | Sub-subsections |
| Bullet lists | `List Bullet` | Standard bullets |
| Header | `Header` | Contains expedient info |
| Footer | `Footer` | Company contact info |

### 4.4 Table Styling

Tables use the G3DT brand colors:

```python
def _shade_cell(self, cell, color: str):
    """Add background shading to a table cell."""
    shading = OxmlElement("w:shd")
    shading.set(qn("w:fill"), color)
    cell._tc.get_or_add_tcPr().append(shading)

# G3DT Green for headers: #4A7C59
self._shade_cell(cell, "4A7C59")
```

### 4.5 Image Insertion

Images are inserted using the `_add_figure()` method:

```python
# Standard images mapping
STANDARD_IMAGES = {
    "figura_1": "location_map.png",       # Situació de la zona d'estudi
    "figura_2": "site_plan.png",          # Situació assaigs realitzats
    "figura_4": "geological_map.png",     # Mapa geològic
    "foto_1": "site_photo_1.jpeg",        # Vista general zona
    "foto_2": "dpsh_photo.jpeg",          # Màquina DPSH
    "foto_3": "material_detail.jpeg",     # Detall materials
}

# Adding a figure with image and caption
self._add_figure(doc, "figura_1", "Figura 1. Situació de la zona d'estudi.")
```

---

## 5. Document Structure

A complete G3DT report contains:

### 5.1 Cover Page
- Company logo/watermark (in first page header)
- Project title
- Client name

### 5.2 Index (Índex)
- Table of contents with page numbers
- Uses `toc 1`, `toc 2`, `toc 3` styles (all three levels)
- Right-aligned page numbers with dot leaders
- Includes third-level entries (e.g., 2.1.1, 2.4.1, 3.2.1, etc.)

### 5.3 Section 1: Presentació de l'Estudi
- 1.1. Antecedents (client, location, building type)
- 1.2. Classificació CTE (building/terrain classification)
- 1.3. Objectius (study objectives)
- **Figura 1**: Location map

### 5.4 Section 2: Treballs de Camp
- 2.1. Descripció zona (site description)
  - 2.1.1. Descripció de les parcel·les adjacents
  - 2.1.2. Descripció del solar
- 2.2. Reconeixement terreny (field survey)
- 2.3. Justificació CTE (compliance)
- 2.4. Descripció assaigs (test descriptions)
  - 2.4.1. Assaigs de penetració tipus "DPSH"
  - 2.4.2. Assaig tipus S.P.T.
  - 2.4.3. Resum dels assaigs in-situ realitzats
- 2.5. Assaigs laboratori (lab tests)
- **Fotografia 1**: Site general view
- **Figura 2**: Site plan with test locations
- **Fotografia 2**: DPSH machine

### 5.5 Section 3: Descripció Geològica i Geotècnica
- 3.1. Marc geològic (geological context)
- 3.2. Caracterització materials (material properties)
  - 3.2.1. Nivell 1
- 3.3. Hidrologia (water conditions)
  - 3.3.1. Hidrogeologia superficial
  - 3.3.2. Hidrogeologia subterrània
  - 3.3.3. Permeabilitat dels materials
- 3.4. Agressivitat (concrete aggressivity)
- 3.5. Excavabilitat (excavation feasibility)
- 3.6. Acceleració sísmica (seismic parameters)
- 3.7. Exposició al radó (radon exposure)
- **Figura 4**: Geological map
- **Fotografia 3**: Material detail

### 5.6 Section 4: Conclusions
- 4.1. Geologia (geological summary)
- 4.2. Hidrogeologia i agressivitat (water & aggressivity)
- 4.3. Fonamentació (foundation recommendations)

### 5.7 Signature Block
- Company disclaimer
- Expedient number
- Date and location

---

## 6. Usage

### 6.1 Command Line

```bash
# Generate a report for Balaguer
python generate_full_report.py --scenario balaguer --output report.docx

# Available scenarios: balaguer, tarrega, mollerussa
python generate_full_report.py --scenario tarrega --output tarrega.docx
```

### 6.2 Demo Scenarios

| Scenario | Client | Location | Building Type |
|----------|--------|----------|---------------|
| balaguer | PROMOTORA PONENT SL | BALAGUER | Habitatge unifamiliar |
| tarrega | CONSTRUCCIONS XYZ SL | TÀRREGA | Nau industrial |
| mollerussa | AJUNTAMENT DE MOLLERUSSA | MOLLERUSSA | Equipament públic |

### 6.3 Custom Projects

To generate a report for a new project, create a scenario dictionary:

```python
custom_scenario = {
    "client": "CLIENT NAME",
    "expedient": "4001XXX",
    "ubicacio": "LOCATION",
    "comarca": "Comarca",
    "provincia": "Lleida",
    "adreca": "Address",
    "tipus_obra": "habitatge unifamiliar",
    "plantes": "PB + 1",
    "superficie_parcela": "500 m²",
    "superficie_construida": "150 m²",
    "cte_edificacio": "C-0",
    "cte_sol": "T-1",
    "data_camp": "10 de gener de 2026",
    "data_signatura": "16 de gener de 2026",
    "lloc_signatura": "Els Omells de Na Gaia",
}

generator = G3DTFullReportGenerator()
generator.create_report(custom_scenario, "output.docx")
```

---

## 7. Image Management

### 7.1 Extracting Images from Samples

Use the `extract_images.py` utility to extract images from DOCX files:

```bash
# Extract from all samples
python extract_images.py

# Extract from a specific file
python extract_images.py /path/to/document.docx
```

This creates:
- Individual folders for each document in `extracted-images/`
- `image_mapping.json` with filename-to-path mappings
- Combined mapping at `all_images_mapping.json`

### 7.2 Standard Images

The `images/` folder contains reusable images for reports:

| Image Key | Filename | Description | Size |
|-----------|----------|-------------|------|
| `figura_1` | `location_map.png` | Location map (ICGC) | 2.7 MB |
| `figura_2` | `site_plan.png` | Site plan with test locations | 866 KB |
| `figura_4` | `geological_map.png` | Geological map | 1.0 MB |
| `foto_1` | `site_photo_1.jpeg` | General site view | 533 KB |
| `foto_2` | `dpsh_photo.jpeg` | DPSH machine | 525 KB |
| `foto_3` | `material_detail.jpeg` | Material detail | 105 KB |

### 7.3 Adding New Images

1. Add the image file to the `images/` folder
2. Update the `STANDARD_IMAGES` dictionary in `generate_full_report.py`:
   ```python
   STANDARD_IMAGES = {
       # ... existing images ...
       "new_key": "new_image.png",
   }
   ```
3. Use `self._add_figure(doc, "new_key", "Caption text.")` in the generator

---

## 8. Customization

### 8.1 Updating the Base Template

To change branding (colors, fonts, logos):

1. Open `base-template.docx` in Word
2. Modify styles via **Home > Styles**
3. Edit headers/footers via **Insert > Header/Footer**
4. Save the template

All future generated reports will use the updated styling.

### 8.2 Adding New Sections

To add new content sections:

1. Create a new method in `G3DTFullReportGenerator`:
   ```python
   def _add_section_X_new_content(self, doc, scenario):
       doc.add_paragraph("X. NEW SECTION", style="Heading 1")
       doc.add_paragraph("Content...", style="Normal")
   ```

2. Call it from `create_report()`:
   ```python
   self._add_section_X_new_content(doc, scenario)
   ```

### 8.3 Changing Table Colors

The G3DT green color is defined as `#4A7C59`. To change:

```python
# In _add_table method, change:
self._shade_cell(cell, "4A7C59")  # Current green
# To:
self._shade_cell(cell, "RRGGBB")  # New color in hex
```

### 8.4 Fixing Style Alignment Issues

Some styles in the base template may have unexpected alignment. Use helper methods to force alignment:

```python
def _add_heading3(self, doc: Document, text: str):
    """Add a Heading 3 paragraph with forced left alignment."""
    para = doc.add_paragraph(text, style="Heading 3")
    para.alignment = WD_ALIGN_PARAGRAPH.LEFT
    return para
```

---

## 9. Output Quality

### 9.1 What's Preserved

✅ Heading styles (green H1, proper hierarchy)
✅ Heading 3 left-aligned (forced in code)
✅ Table formatting (green headers, borders)
✅ Page margins (3.0cm top, 1.8cm bottom, 3.2cm sides)
✅ Headers/footers (expedient info, company contact)
✅ Font families (Calibri throughout)
✅ Caption styling (centered, italic)
✅ Index with toc 1, toc 2, and toc 3 entries
✅ Images (maps, photographs) with proper sizing

### 9.2 Limitations (Demo)

⚠️ Cover page text boxes (preserved from template, not dynamic)
⚠️ Annexes (not included in demo version)
⚠️ Location-specific maps (uses generic images for demo)

---

## 10. Integration with SiteBoon UI

The system can be run via Claude Code slash commands through the SiteBoon UI:

```
/g3dt-demo-informe client="CLIENT" ubicacio="LOCATION" tipus="TYPE"
```

This provides a user-friendly interface for non-technical staff.

---

## 11. File Sizes

| Report Type | Size | Notes |
|-------------|------|-------|
| Base template | ~7.5 MB | Includes all embedded assets |
| Generated report (with images) | ~12-15 MB | Includes 6 standard images |
| Original sample | ~7.5 MB | Reference document |
| Standard images folder | ~5.7 MB | 6 reusable images |

---

## 12. Dependencies

```
python >= 3.8
python-docx >= 0.8.11
```

Install via:
```bash
pip install python-docx
```

---

## 13. Future Improvements

1. **Dynamic cover page** - Update cover text boxes programmatically
2. ~~**Image insertion** - Add maps, photos, cross-sections~~ ✅ DONE
3. **Annex generation** - Include test logs, lab reports
4. **PDF export** - Direct PDF output option
5. **Template validation** - Check base template has required styles
6. **LLM integration** - Generate section content from field data
7. **Location-specific images** - Generate maps for specific locations via API

---

## 14. Changelog

### Version 1.1 (13 gener 2026)
- ✅ Added image extraction from sample documents (`extract_images.py`)
- ✅ Added image insertion in generated reports (6 standard images)
- ✅ Fixed Heading 3 alignment (forced left-align via `_add_heading3()`)
- ✅ Added toc 3 entries to index (10 third-level entries)
- ✅ Created `images/` folder with reusable standard images
- ✅ Updated documentation with image management section

### Version 1.0 (13 gener 2026)
- Initial release with full report generation
- Cover page, index, 4 sections, signature block
- Base template approach for style preservation

---

## Contact

**Eficients**
Josep Portell
josep@eficients.cat
+34 687 838 596
