# G3DT Report Generation System

**Status:** MVP COMPLETE - Generates reports with 10 variable fields

Generate geotechnical reports (informes geotècnics) with 100% G3DT styling using template-based approach.

## Quick Start

```bash
# Generate report with sample data (Rubí project)
python3 generate_from_template.py --sample

# Generate report from JSON data
python3 generate_from_template.py --data myproject.json --output report.docx

# Export data schema
python3 generate_from_template.py --export-schema
```

## Files

### Core Generation Files
| File | Description |
|------|-------------|
| `g3dt-jinja-template.docx` | Main template with Jinja2 placeholders |
| `g3dt-base-template.docx` | Original Rubí sample (backup) |
| `generate_from_template.py` | Report generator |
| `data_schema.json` | Data structure reference |

### Tools
| File | Description |
|------|-------------|
| `create_template_v2.py` | Creates template from sample (one-time) |
| `extract_docx_styles.py` | Analyzes Word document styles |
| `analyze_content.py` | Analyzes document content structure |
| `test_template.py` | Tests template rendering |

### Legacy (not recommended)
| File | Description |
|------|-------------|
| `generate_report.py` | Programmatic generator (~80% fidelity) |
| `latex/` | LaTeX-based PDF generation (~90% fidelity) |

## Template Variables (MVP)

The template currently supports 10 Jinja2 placeholders:

### Core Fields
```
{{ client }}              - Client name (e.g., "SRA. MARIA GARCIA")
{{ expedient }}           - Expedition number (e.g., "3001632")
{{ location }}            - Town/municipality (e.g., "LLEIDA")
{{ data_camp_text }}      - Field date in Catalan (e.g., "14 de novembre de 2025")
{{ data_signatura_text }} - Signature date in Catalan (e.g., "17 de desembre de 2025")
```

### Building Data (Table 0)
```
{{ plantes }}             - Number of floors (e.g., "PB + 1")
{{ superficie_parcela }}  - Plot area in m² (e.g., "500")
{{ superficie_construida }} - Built area in m² (e.g., "150")
```

### CTE Classification (Table 1)
```
{{ cte_edificacio }}      - Building classification (C-0, C-1, or C-2)
{{ cte_sol }}             - Soil classification (T-1, T-2, or T-3)
```

## Sample Data File

Create a JSON file with your project data:

```json
{
    "client": "SR. JOAN PERE GARCIA",
    "expedient": "4001650",
    "location": "BALAGUER",
    "data_camp_text": "20 de gener de 2026",
    "data_signatura_text": "25 de gener de 2026",
    "plantes": "PB + 2",
    "superficie_parcela": "800",
    "superficie_construida": "300",
    "cte_edificacio": "C-1",
    "cte_sol": "T-2"
}
```

Then generate:
```bash
python3 generate_from_template.py --data project.json --output 4001650_informe.docx
```

## How It Works

1. **Template** (`g3dt-jinja-template.docx`) - Word document with Jinja2 placeholders
2. **Data** - JSON file or Python dict with project-specific values
3. **Generator** - Uses `docxtpl` to merge data into template
4. **Output** - Complete Word document with G3DT styling

### Why Template-Based?

| Approach | Effort | Fidelity | Maintenance |
|----------|--------|----------|-------------|
| Template + docxtpl | Low | **100%** | Edit Word template |
| Programmatic (python-docx) | High | ~80% | Code changes |
| LaTeX | Medium | ~90% | Requires LaTeX knowledge |

**Key insight:** We preserve G3DT's exact styling by replacing content within existing styled elements, not reconstructing styles programmatically.

## Dependencies

```bash
pip install python-docx docxtpl
```

## Recreating the Template

If you need to update the template from a new sample:

```bash
# 1. Copy new sample as base
cp /path/to/new_sample.docx g3dt-base-template.docx

# 2. Create Jinja2 template
python3 create_template_v2.py --input g3dt-base-template.docx --output g3dt-jinja-template.docx

# 3. Test
python3 test_template.py
```

## Future Expansion

The MVP handles simple reports (Rubí type). Future versions will add:

- [ ] DPSH test results table (`{% for test in dpsh_results %}`)
- [ ] Lab test results
- [ ] Conditional sections (expansivity, slope stability, earth pressure)
- [ ] Geotechnical parameters table
- [ ] Conclusions section (Qa, foundation type, settlement)
- [ ] Cover page OBRA text
- [ ] Annex generation

## Source Samples

From Eva (G3DT), January 2026:
```
/mnt/c/claude/g3dt/mostres/docx/
├── 3001621_informe_v0.docx  - Castellar (complex)
├── 3001631_informe.docx     - Rubí (simple) ← USED AS BASE
├── 4001607_informe.docx     - Linyola (expansive soils)
└── 4001612_informe.docx     - Bell-Lloc
```

## Changelog

### v1.0 (Jan 7, 2026)
- Initial MVP with 10 variable fields
- Template created from Rubí sample (3001631)
- Generator working with docxtpl
- Test scripts for validation
