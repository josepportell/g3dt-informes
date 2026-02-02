# G3DT Report Automation

Data extraction modules for automating G3DT geotechnical report generation.

## Installation

Requires Python 3.10+ and `xlrd` for reading .xls files:

```bash
# Using uv (recommended)
uv run --with xlrd python3 <script.py>

# Or install xlrd globally
pip install xlrd
```

## Modules

### dpsh_extractor.py

Extracts penetration test data from DPSH Excel files (.xls format).

```bash
# Command line
uv run --with xlrd python3 dpsh_extractor.py path/to/DPSH.xls

# JSON output
uv run --with xlrd python3 dpsh_extractor.py path/to/DPSH.xls --json
```

```python
# As a module
from automation.dpsh_extractor import DPSHExtractor

extractor = DPSHExtractor('path/to/DPSH.xls')
data = extractor.extract_all()

print(f"Tests: {data.num_tests}")
print(f"Average N₂₀: {data.overall_average_n20}")

for test in data.tests:
    print(f"{test.test_id}: depth={test.depth_reached}m, avg N₂₀={test.average_n20}")
```

**Extracted data:**
- Test IDs (P-1, P-2, etc.)
- Correction factor (typically 0.83)
- Depth readings with N₂₀ values
- Normalized blow counts (NB)
- Water level (if detected)
- Refusal depth

### project_extractor.py

Extracts all available data from a G3DT project folder.

```bash
# Command line
uv run --with xlrd python3 project_extractor.py path/to/project/folder

# JSON output
uv run --with xlrd python3 project_extractor.py path/to/project/folder --json
```

```python
# As a module
from automation.project_extractor import ProjectExtractor

extractor = ProjectExtractor('path/to/project/folder')
data = extractor.extract_all()

print(f"Expedient: {data.expedient}")
print(f"Client: {data.client.company_name}")
print(f"DPSH tests: {data.dpsh.num_tests if data.dpsh else 0}")
```

**Extracted data:**
- Project identification (expedient, municipality)
- Client information (from DADES CLIENT.txt)
- DPSH test data (from DPSH.xls)
- File inventory (what files are available)
- Derived geotechnical parameters (correlations)

## Geotechnical Correlations

The `GeotechCorrelations` class provides standard correlations for deriving parameters from N values:

```python
from automation.dpsh_extractor import GeotechCorrelations

n20 = 35  # Average blow count

phi = GeotechCorrelations.n_to_friction_angle(n20)      # ~38°
E = GeotechCorrelations.n_to_deformation_modulus(n20)   # ~350 kg/cm²
gamma = GeotechCorrelations.n_to_density(n20)           # ~2.1 g/cm³
```

**Note:** These are approximate correlations from geotechnical literature. G3DT may use slightly different correlations in their Base de càlcul. Values should be validated against their actual practice.

## Expected Folder Structure

```
{expedient} {POBLACIO}/
├── ACCEPTACIO/
│   └── DADES CLIENT.txt          ← Client info
├── ANNEXES/
│   └── {expedient}_DPSH.xls      ← DPSH test data
├── FOTOGRAFIES/
│   ├── DPSH/                     ← Test photos
│   └── SONDEIG/                  ← Drilling photos
├── PDF/
│   └── ANNEXES/
│       └── LAB-SIG.pdf           ← Lab results
└── comanda laboratori_*.xls      ← Lab request
```

## Output JSON Structure

```json
{
  "project": {
    "expedient": "4001612",
    "municipality": "Bell Lloc",
    "folder_path": "..."
  },
  "client": {
    "company_name": "RAMON MITJANA SL",
    "nif": "B25771726",
    "representative": "...",
    "address": "...",
    "phone": "...",
    "email": "..."
  },
  "files": {
    "has_dpsh_excel": true,
    "has_sondeig": true,
    "has_photos": true,
    "photo_count": 10
  },
  "dpsh": {
    "expedient": "4001612",
    "num_tests": 2,
    "test_ids": ["P-1", "P-2"],
    "overall_average_n20": 36.72,
    "any_water_detected": false,
    "tests": [...]
  },
  "geotechnical": {
    "average_n20": 36.7,
    "friction_angle_deg": 38,
    "deformation_modulus_kg_cm2": 367,
    "density_g_cm3": 2.1,
    "relative_density": "Dens / Dense"
  }
}
```

## Next Steps

1. **Lab results parser** - Extract sulfate values, Lambe results from PDF
2. **Terzaghi calculator** - Calculate Qa using their exact formulas
3. **Report generator** - Integrate with Jinja2 template system
4. **Data entry form** - UI for manual fields (architect, building specs, etc.)

## Files

```
automation/
├── __init__.py           # Package exports
├── dpsh_extractor.py     # DPSH Excel extraction
├── project_extractor.py  # Full project extraction
└── README.md             # This file
```

---

*Part of G3DT report automation project - Eficients.cat*
