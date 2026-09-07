#!/usr/bin/env python3
"""M341 — MESURA COMPLETA de l'informe: totes les variables de la plantilla vs els informes signats de l'Eva, 7 projectes.

Tanca l'ajornament del 2026-08-25 («unificar veritat, camps i semàntica»). Les tres unificacions:

  * **Veritat**: `reference-material/<projecte>/validation/eva_reference_values.json` (extractor de referència sobre el
    signat, 56-65 variables amb el NOM de la plantilla) per als escalars i la narrativa; `_eva_truth/<slug>.json` (11
    taules transcrites) per a les taules. Cap veritat nova: les dues ja existien, aquí es fan servir juntes.
  * **Camps**: el CONTEXT Jinja que el generador passa a la plantilla (`_build_template_context`, capturat en el
    `render_template` real, cap re-extracció del `.docx` generat): la variable `X` del signat es compara amb `context[X]`.
    Els 100 noms de la plantilla són l'univers; les llistes (taules) van pel comparador de taules.
  * **Semàntica**: `status_for` de `scripts/compare_prefills_vs_eva.py` (MATCH / CLOSE / MISMATCH amb tolerància per
    variable) per als escalars i la narrativa; `scripts/compare_tables_vs_eva.py` per a les taules. Un sol valor per
    costat (el que s'imprimeix): els candidats de la lectura no compten aquí, només el defecte.

Variants:
  viaA  Els 7 projectes generats NOMÉS amb la via A + via B (carpeta amb Fase 0 feta: `reference-material/` on hi és,
        amb els JSON de visió de producció; si no, el corpus de lectura amb SmartScan nivell 1): escalars de `_decisions.json` (superposició
        `web/lectura_service._apply_lectura_overlay`, la mateixa del wizard), taules llegides
        (`automation/lectura/tables_report.build_report_tables`), Excel DPSH del projecte, i DUES assumpcions per
        projecte que cap document dona: la Df (`DF_SIGNAT`, pous a Linyola i Anciles) i la data de signatura
        (`data_signatura`: al wizard és el dia que l'Eva signa; aquí la del signat, bloc 1 2026-09-07). Cap
        `_user_data_prev.json`, cap `geomech_params`, cap `Es_settlement`. És «el que el sistema faria sol».
  t2    Només els 3 amb `_user_data_prev.json` (Castellar, Rubí, Bell-lloc): mateixa variant que `mesura_informe.py`
        (escalars d'abril de l'Eva + taules de la lectura), per veure què aporten els escalars manuals.

Ús:
  PYTHONPATH=$PWD G3DT_CACHE_DIR=/home/josep/g3dt-prod-cache \\
    .venv/bin/python docs/wizard-headless/mesures/mesura_341.py <nom-run> [--variants viaA,t2] [--projects …]
      [--lectura-sub _reconsolida-2026-09-06-pend] [--projectes-dir ~/g3dt-e2e/projectes] [--docx-dir DIR]

Sortida: `runs/<nom-run>/<slug>/<variant>/_compare_341.{txt,json}` (escalars + narrativa per grup), `_compare_informe.*`
(11 taules), `_calc.json`, `_user_data_usat.json`, `_context_usat.json` (sense imatges), i `<nom-run>/_AGREGAT-341.md`.
Els `.docx` van FORA del repositori. Cost: 0 (cap LLM).

Narrativa (peça 0, 2026-09-06 nit, `docs/ANALISI-NARRATIVA-2026-09-06.md` §5): les variables del grup `narr` (i les que són
l'únic forat d'un paràgraf de la plantilla, com `location_sentence`) es puntuen FORAT CONTRA FORAT (`narr_status`): es
renderitza el paràgraf de la plantilla amb el valor generat, es treu a les dues bandes el text comú als extrems (paraules) i
es puntuen els residus (iguals → MATCH; un residu buit → CLOSE, «res del que escrivim és fals, però falta o sobra text»;
similitud ≥ 0,92 MATCH, ≥ 0,6 CLOSE, si no MISMATCH). Abans, «pla» es comparava amb el paràgraf sencer del signat (X segur).
`csn_radon_text` queda FORA (el paràgraf de l'Eva ja és text fix de la plantilla, p474). L'idioma del signat (ca/es) surt
per projecte a l'agregat: les cel·les ES són un sostre de la plantilla catalana, no un error de narrativa.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import importlib.util
import io
import json
import logging
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
MESURA_8 = RUNS / "2026-09-03-mesura-8"
DEFAULT_LECTURA_SUB = "_reconsolida-2026-09-06-pend"
DEFAULT_PROJECTES = Path.home() / "g3dt-e2e" / "projectes"

NAMES = {
    "castellar": "3001621 CASTELLAR DEL VALLES", "rubi": "3001631 RUBI", "bell-lloc": "4001612 BELL-LLOC",
    "linyola": "4001607 LINYOLA", "alcoletge": "4001670 ALCOLETGE", "vilanova": "4001671 VILANOVA DE SEGRIA",
    "anciles": "4001679 ANCILES",
}
WITH_PREV = ("castellar", "rubi", "bell-lloc")
VARIANTS = ("viaA", "t2")

#: Df (m) que la fonamentació descrita al signat implica (tests/test_bearing_layer_rule.py, RECERCA-CRITERIS §):
#: sabates encastades 20-40 cm al primer nivell sanejat (0,3), Rubí sabata a 1,0, pous a Linyola (L2 a 1,4 → 1,7)
#: i Anciles (L2 a 2,6 → 2,9), Alcoletge sota el rebliment (1,0). ASSUMPCIÓ documentada: és l'única dada que al
#: wizard posa l'Eva i que cap document llegit dona.
#: Vilanova (bloc 3, 2026-09-07): el signat diu «cimentación superficial mediante zapatas … combinada con pozos de cimentación,
#: apoyada en los materiales del 2do nivel saneado» (veritat `bearing_layer_idx` = 1); abans 0,3 (sabata al 1r nivell) era
#: una lectura equivocada del signat. Com a Linyola/Anciles: contacte del 2n nivell a la geometria del sistema (segmentador
#: DPSH: 0,8; el signat, Tabla 6, dona 1,0 / 1,6 / 2,2 per punt) + 0,3 = 1,1.
DF_SIGNAT = {"castellar": 0.3, "rubi": 1.0, "bell-lloc": 0.3, "linyola": 1.7, "alcoletge": 1.0, "vilanova": 1.1, "anciles": 2.9}

#: Grup de cada variable de la plantilla (v1, 2026-09-06). A = nivell A (lectura de documents); calc = criteris de
#: càlcul; narr = narrativa generada; taula = llistes (comparador de taules); fix = text fix / numeració / figures.
GROUPS = {
    "A": {"architect_company", "architect_name_upper", "building_type_lower", "client", "plantes", "expedient",
          "municipality", "municipality_upper", "municipality_de", "client_de", "building_type_de", "architect_company_de", "superficie_parcela", "superficie_construida", "data_camp_text",
          "data_camp_inici_text", "num_dpsh_tests", "lab_depth", "lab_location", "lab_sample_id", "lab_testing_company",
          "lab_field_company", "cota_referencia", "utm_x", "utm_y", "spt_test_id", "spt_location", "spt_depth_range",
          "spt_n30", "spt_lithology", "location_sentence", "has_sondeig", "num_soil_levels"},
    "calc": {"qa_value", "settlement", "settlement_sentence", "k30_value", "geomech_E", "geomech_cohesion", "geomech_gamma",
             "geomech_phi", "cte_edificacio", "cte_sol", "seismic_ab_text", "radon_zone", "table_dpsh_range",
             "sulfate_value", "sulfate_baumann", "sulfate_classification", "sulfate_level_name", "show_granulometric", "bearing_layer_idx",
             "include_earth_pressure", "include_expansivity", "include_slope_stability"},
    "narr": {"adjacent_east_fmt", "adjacent_north_fmt", "adjacent_south_fmt", "adjacent_west_fmt", "access_street",
             "site_description", "site_condition", "building_structure_desc", "lab_tests_text", "materials_intro",
             "conclusions_level_1", "conclusions_levels_detected", "conclusions_water_statement",
             "conclusions_aggressivity_statement", "geology_paragraphs", "empentes_paragraph", "estabilitat_paragraph",
             "photo_site_text", "csn_radon_text", "radon_zone_description", "radon_sentence", "adjacent_intro"},
    "taula": {"dpsh_tests", "sondeig_tests", "spt_ma_tests", "soil_levels", "soil_level_rows", "perm_rows", "seismic_rows",
              "geotech_rows"},
}


def group_of(var: str) -> str:
    for g, vs in GROUPS.items():
        if var in vs:
            return g
    if var.startswith(("fig_", "photo_", "section_", "table_")) or var.endswith(("_num", "_image")):
        return "fix"
    return "resta"


# --- Narrativa: forat contra forat -------------------------------------------------------------------------------
#: Paràgraf fix de la plantilla (p474): el generador l'afegia per segon cop a p498. Fora de la mesura.
NARR_EXCLUDED = {"csn_radon_text"}
#: Variables d'altres grups que també són l'únic forat d'un paràgraf amb text fix i es puntuen forat contra forat.
NARR_SLOT_EXTRA = {"location_sentence"}
#: Frases fixes del bloc «Descripció del solar» que la veritat de l'extractor inclou dins `site_description` (p122, p126, p127
#: de la plantilla): es treuen de la veritat abans de comparar amb el forat (només l'estat del solar).
_SITE_DESC_FIXED_PREFIXES = (
    "el dia dels treballs de camp es realitza l'entrada", "en solars propers existeixen construccions",
    "destacar que no es poden veure aflorar",
    "el día de los trabajos de campo se realiza la entrada", "en solares próximos existen construcciones",
    "dada la geomorfología de la zona",
)
_ES_MARKERS = ("por la parte", "ensayo", "en la zona de estudio", "según el proyecto", "la parcela concreta")
_SLOTS: dict[str, str] | None = None


def template_slots() -> dict[str, str]:
    """var → text del paràgraf de la plantilla on la variable és l'ÚNIC forat i hi ha text fix al voltant."""
    global _SLOTS
    if _SLOTS is None:
        from automation.intelligent_audit import JINJA_ANY_RE, extract_template_paragraphs
        from automation.reference_extractor import DEFAULT_TEMPLATE
        paras, _ = extract_template_paragraphs(DEFAULT_TEMPLATE)
        slots: dict[str, str] = {}
        for tp in paras:
            if tp.is_static or len(tp.variables) != 1 or tp.variables[0] in slots:
                continue
            var = tp.variables[0]
            parts = re.split(r"\{\{[-\s]*" + re.escape(var) + r"\s*(?:\|[^}]*)?\s*\}\}", tp.text, maxsplit=1)
            if len(parts) != 2:
                continue
            if (JINJA_ANY_RE.sub("", parts[0]).strip() or JINJA_ANY_RE.sub("", parts[1]).strip()):
                slots[var] = tp.text
        _SLOTS = slots
    return _SLOTS


def _slot_parts(var: str) -> tuple[str, str, str] | None:
    """(text sencer, prefix fix, sufix fix) del forat `var`, sense etiquetes Jinja."""
    from automation.intelligent_audit import JINJA_ANY_RE
    text = template_slots().get(var)
    if text is None:
        return None
    parts = re.split(r"\{\{[-\s]*" + re.escape(var) + r"\s*(?:\|[^}]*)?\s*\}\}", text, maxsplit=1)
    return text, JINJA_ANY_RE.sub("", parts[0]).strip(), JINJA_ANY_RE.sub("", parts[1]).strip()


def _render_slot(var: str, gen: str) -> str:
    from automation.intelligent_audit import JINJA_ANY_RE
    text = template_slots()[var]
    return JINJA_ANY_RE.sub("", re.sub(r"\{\{[-\s]*" + re.escape(var) + r"\s*(?:\|[^}]*)?\s*\}\}", lambda _m: gen, text, count=1)).strip()


def _norm_narr(s: str) -> str:
    """Minúscules, apòstrofs i cometes rectes, SENSE accents («un sòl nivell» de l'Eva = «un sol nivell»), espais normals."""
    import unicodedata
    s = str(s).lower().replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    s = "".join(ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", s).strip()


def _tokens(s: str) -> list[str]:
    return re.findall(r"\w+", _norm_narr(s))


def residues(a: str, b: str) -> tuple[str, str]:
    """Els dos textos sense les paraules comunes als extrems (el «forat» de cadascun)."""
    wa, wb = _tokens(a), _tokens(b)
    i = 0
    while i < min(len(wa), len(wb)) and wa[i] == wb[i]:
        i += 1
    j = 0
    while j < min(len(wa), len(wb)) - i and wa[-1 - j] == wb[-1 - j]:
        j += 1
    return " ".join(wa[i:len(wa) - j]), " ".join(wb[i:len(wb) - j])


def _strip_site_desc_fixed(eva: str) -> str:
    keep = []
    for line in re.split(r"[\n\r]+", str(eva)):
        n = _norm_narr(line)
        if n and not n.startswith(_SITE_DESC_FIXED_PREFIXES):
            keep.append(line.strip())
    return "\n".join(keep)


def narr_status(var: str, eva, gen) -> str:
    """MATCH / CLOSE / MISMATCH forat contra forat (vegeu la capçalera). `gen` i `eva` no buits."""
    from difflib import SequenceMatcher
    e, g = str(eva).strip(), str(gen).strip()
    if var == "site_description":
        e = _strip_site_desc_fixed(e) or e
    parts = _slot_parts(var)
    if parts is not None:
        _text, pre, suf = parts
        pre_in = bool(pre) and _norm_narr(pre) in _norm_narr(e)
        suf_in = len(suf) >= 3 and _norm_narr(suf) in _norm_narr(e)
        if pre_in or suf_in:            # la veritat és el paràgraf sencer → comparem la frase renderitzada
            g = _render_slot(var, g)
        # si no: la veritat ja és el forat (l'extractor va trobar el prefix) → forat contra forat directe
    ra, rb = residues(g, e)
    if not ra and not rb:
        return "MATCH"
    if not ra or not rb:
        return "CLOSE"
    r = SequenceMatcher(None, ra, rb, autojunk=False).ratio()
    return "MATCH" if r >= 0.92 else ("CLOSE" if r >= 0.6 else "MISMATCH")


def lang_of_eva(eva: dict) -> str:
    """Idioma del signat (ca/es) pels textos narratius de la veritat."""
    for var, info in eva.items():
        if group_of(var) != "narr":
            continue
        v = info.get("value") if isinstance(info, dict) else info
        if isinstance(v, str) and any(m in v.lower() for m in _ES_MARKERS):
            return "es"
    return "ca"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


MI = _load(HERE / "mesura_informe.py", "mesura_informe")
CPE = _load(REPO / "scripts" / "compare_prefills_vs_eva.py", "compare_prefills_vs_eva")


def _decisions(slug: str, sub: str) -> dict:
    return json.loads((MESURA_8 / slug / sub / "_decisions.json").read_text(encoding="utf-8"))


def _lith_text(row: dict) -> str:
    for k in ("litologia", "description", "descripcio", "nom"):
        v = row.get(k)
        if isinstance(v, dict):
            v = v.get("value")
        if v:
            return str(v)
    return ""


def user_data_from_lectura(slug: str, decisions: dict, signature_date: str | None = None) -> dict:
    """`user_data` de la via A sola: escalars per la superposició del wizard, taules llegides, Df del signat."""
    from web.lectura_service import _apply_lectura_overlay
    from automation.lectura.tables_report import build_report_tables
    from automation.cte_geomech import detect_soil_type
    merged: dict = {}
    _apply_lectura_overlay(merged, decisions)
    ud = {k: (v.get("value") if isinstance(v, dict) else v) for k, v in merged.items()}
    ud = {k: v for k, v in ud.items() if v not in (None, "")}
    # El wizard converteix els tipus en desar; aquí ho fem igual: UTM i superfície numèrics («571 m²» → 571.0).
    for k in ("utm_x", "utm_y", "superficie_parcela_m2", "superficie_construida_m2"):
        if isinstance(ud.get(k), str):
            m = re.search(r"-?\d+(?:[.,]\d+)?", ud[k].replace(".", "") if k.startswith("superficie") and re.search(r"\d\.\d{3}", ud[k]) else ud[k])
            ud[k] = float(m.group(0).replace(",", ".")) if m else None
            if ud[k] is None:
                del ud[k]
    tables = build_report_tables(decisions)
    ud["lectura_tables"] = tables
    levels = tables.get("soil_levels") or []
    if isinstance(levels, dict):
        levels = levels.get("rows") or []
    if levels:
        ud["num_soil_levels"] = len(levels)
        ud["soil_types"] = [detect_soil_type(_lith_text(r)) for r in levels]
    ud.setdefault("num_soil_levels", 1)
    ud["foundation_depth_m"] = DF_SIGNAT[slug]
    ud["expedient"] = NAMES[slug].split()[0]
    ud["_metadata"] = {"origen": "mesura_341 viaA: lectura + Df del signat", "Df_assumida": DF_SIGNAT[slug]}
    # Segona ASSUMPCIÓ documentada (bloc 1, 2026-09-07): la data de signatura és la que l'Eva escriu al wizard el dia
    # que signa (camp `data_signatura`, defecte avui); no és a cap document. Es pren del signat, com la Df.
    if signature_date:
        ud["data_signatura"] = signature_date
        ud["_metadata"]["data_signatura_assumida"] = signature_date
    return ud


_MONTHS = {"gener": 1, "febrer": 2, "març": 3, "marc": 3, "abril": 4, "maig": 5, "juny": 6, "juliol": 7, "agost": 8,
           "setembre": 9, "octubre": 10, "novembre": 11, "desembre": 12,
           "enero": 1, "febrero": 2, "marzo": 3, "mayo": 5, "junio": 6, "julio": 7, "septiembre": 9, "diciembre": 12}


def signature_date_iso(eva_text) -> str | None:
    """«29 d'octubre de 2025» / «Els Omells de Na Gaia, 16 de marzo de 2026» → `2025-10-29` / `2026-03-16`; None si no."""
    m = re.search(r"(\d{1,2})\s+d[e'’]\s*([A-Za-zçÇ]+)\s+de\s+(\d{4})", str(eva_text or ""))
    if not m:
        return None
    month = _MONTHS.get(m.group(2).lower())
    return f"{int(m.group(3)):04d}-{month:02d}-{int(m.group(1)):02d}" if month else None


def _project_path(name: str, projectes: Path) -> Path:
    """Carpeta del projecte per a la via B: `reference-material/<projecte>` si ja té `file_mapping.json` (Fase 0 feta:
    Excel DPSH + JSON de visió del plànol/sondeig, com a producció), si no la del corpus de lectura. Sense
    `file_mapping.json`, el generador cau a l'inventari antic (només `ANNEXES/`) i no troba l'Excel de Vilanova
    (`ANEXOS/`) ni d'Anciles (`ANEJOS/`): es fa la Fase 0 amb SmartScan de nivell 1 (regex de noms, cap LLM) i es desa
    al costat del projecte, com faria el wizard."""
    ref = REPO / "reference-material" / name
    if (ref / "file_mapping.json").exists():
        return ref
    path = projectes / name
    if not (path / "file_mapping.json").exists():
        from automation.smartscan import scan_project
        result = scan_project(path, max_tier=1, include_vision=False)
        # `to_file_mapping()` ja és el JSON de `file_mapping.json` (format que llegeix `FileScanner.load`)
        (path / "file_mapping.json").write_text(json.dumps(result.to_file_mapping(), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _jsonable(v):
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    return f"<{type(v).__name__}>"


def _generate(project_path: Path, ud: dict, out_docx: Path) -> tuple[dict, dict, object]:
    from automation.report_generator import ReportGenerator
    gen = ReportGenerator(project_path=project_path, user_data=ud)
    captured: list[dict] = []
    orig = gen.render_template

    def _render(context, output_path):
        captured.append(context)
        return orig(context, output_path)

    gen.render_template = _render  # type: ignore[method-assign]
    res = gen.generate(out_docx)
    ctx = captured[0] if captured else {}
    return {"success": res.success, "errors": list(res.errors), "warnings": list(res.warnings),
            "calc": MI._calc_summary(gen, ud)}, ctx, gen


_ADJ_WORDS = {"north": ("nord", "norte"), "south": ("sud", "sur"), "east": ("est", "este"), "west": ("oest", "oeste")}


def _grouped_adjacent(var: str, ctx: dict):
    """Costat agrupat (peça 2): el seu forat és buit i la frase és al forat d'un altre costat («Per la part nord, sud i
    est amb parcel·les buides.»). Es compara aquella frase, no NO_DATA: l'informe SÍ que ho diu."""
    d = var[len("adjacent_"):-len("_fmt")]
    if d not in _ADJ_WORDS:
        return None
    for other in ("north", "south", "east", "west"):
        if other == d:
            continue
        sent = str(ctx.get(f"adjacent_{other}_fmt") or "")
        head = sent.split(" amb ")[0].split(", con ")[0].split(" con ")[0].lower()
        if any(re.search(rf"\b{w}\b", head) for w in _ADJ_WORDS[d]):
            return sent
    return None


def _gen_value(var: str, ctx: dict, ud: dict, calc: dict, eva=None):
    if var == "settlement" and isinstance(eva, str) and "assentaments" in eva.lower():
        return ctx.get("settlement_sentence") or ctx.get("settlement")   # el signat porta la frase sencera
    if var.startswith("adjacent_") and var.endswith("_fmt") and not ctx.get(var):
        return _grouped_adjacent(var, ctx)
    if var in ctx:
        return ctx[var]
    gp = (calc or {}).get("geotechnical_params") or {}
    if var == "bearing_layer_idx":                      # veritat del bloc 3 (`bearing_rule`): fila portant 0-based
        return (calc or {}).get("bearing_layer_idx")
    if var == "geomech_E":
        return gp.get("E")
    if var == "geomech_cohesion":
        return gp.get("cohesion")
    if var == "geomech_gamma":
        return gp.get("gamma")
    if var == "geomech_phi":
        return gp.get("phi")
    for k in (var, {"superficie_parcela": "superficie_parcela_m2", "superficie_construida": "superficie_construida_m2",
                    "municipality": "site_municipality", "client": "client_name"}.get(var, "")):
        if k and k in ud:
            return ud[k]
    return None


#: Forats d'imatge de la plantilla (bloc 4, 2026-09-07): 6 figures + 3 fotos + 2 vistes generals (condicionals).
IMAGE_SLOTS = ("fig_cadastre_image", "fig_aerea_image", "fig_main_plan_image", "fig_spt_cullera_image",
               "fig_geological_image", "fig_correlation_image", "photo_dpsh_image", "photo_sondeig_image",
               "photo_materials_image", "photo_site_image_1", "photo_site_image_2")
IMAGE_PLACEHOLDER = "[Imatge pendent]"


def image_presence(ctx: dict) -> dict:
    """Test de presència de les imatges (bloc 4): per forat, «present» (InlineImage), «pendent» (el text
    `[Imatge pendent]` de `image_manager`) o «absent» (buit: foto de vista general no triada, sondeig que no hi és).
    No jutja si la imatge és la correcta ni el retall: això és el full de control visual (`_IMATGES.md` del run)."""
    out = {"present": [], "pendent": [], "absent": []}
    for k in IMAGE_SLOTS:
        v = ctx.get(k)
        # Un `InlineImage` viu no es pot passar per `str()` (docxtpl intenta inserir-lo); `_jsonable` el desa
        # com a «<InlineImage>» a `_context_usat.json`.
        sv = "<InlineImage>" if type(v).__name__ == "InlineImage" else ("" if v is None else str(v))
        if k == "photo_sondeig_image" and not ctx.get("has_sondeig"):
            out["absent"].append(k)             # el bloc és dins de `{%p if has_sondeig %}`: no s'imprimeix
        elif not sv.strip():
            out["absent"].append(k)
        elif IMAGE_PLACEHOLDER in sv:
            out["pendent"].append(k)
        else:
            out["present"].append(k)
    return out


def _norm_numbering(v) -> str:
    """«3» / 3 / «3.» → «3»; «2.4.2.» → «2.4.2»; None / '' → ''."""
    return "" if v is None else str(v).strip().rstrip(".")


def compare_scalars(eva: dict, ctx: dict, ud: dict, calc: dict) -> list[dict]:
    rows = []
    for var, info in sorted(eva.items()):
        ev = info.get("value") if isinstance(info, dict) else info
        g = group_of(var)
        if g == "taula" or isinstance(ev, (list, dict)):
            continue
        if ev is None or str(ev).strip() in ("", "---"):
            continue
        if var in NARR_EXCLUDED:
            continue
        gv = _gen_value(var, ctx, ud, calc, ev)
        if isinstance(gv, (list, dict)):
            rows.append({"var": var, "grup": g, "eva": ev, "gen": "<llista>", "status": "NO_DATA"})
            continue
        if g == "fix":
            # Bloc 4 (2026-09-07): la numeració és text EXACTE («2.4.3» ≠ «2.4.4», «3» ≠ «4»; cap CLOSE) i el buit del
            # generador amb veritat al signat és una X, no un NO_DATA: és la secció o la foto que el signat té i el
            # generador decideix no imprimir (`section_empentes_num` = '' sense empentes).
            st = "MATCH" if _norm_numbering(ev) == _norm_numbering(gv) else "MISMATCH"
            rows.append({"var": var, "grup": g, "eva": ev, "gen": gv, "status": st,
                         "method": (info.get("extraction_method") if isinstance(info, dict) else "")})
            continue
        if gv is None or str(gv).strip() == "":
            rows.append({"var": var, "grup": g, "eva": ev, "gen": None, "status": "NO_DATA"})
            continue
        # `settlement_sentence` (veritat del bloc 3) es puntua com `settlement`: pel NÚMERO de la frase (tolerància 10 %),
        # no pel text — «inferiors a 1.80 cm» i «inferiors a 1.50 cm» s'assemblen un 97 % i són una X (registre #1).
        cmp_var = "settlement" if var == "settlement_sentence" else var
        st = narr_status(var, ev, gv) if (g == "narr" or var in NARR_SLOT_EXTRA) else CPE.status_for(cmp_var, ev, gv)
        rows.append({"var": var, "grup": g, "eva": ev, "gen": gv, "status": st,
                     "method": (info.get("extraction_method") if isinstance(info, dict) else "")})
    return rows


def _fmt_rows(rows: list[dict], tag: str) -> str:
    L = [f"# {tag} — escalars i narrativa vs signat (`eva_reference_values.json`)", ""]
    by = defaultdict(Counter)
    for r in rows:
        by[r["grup"]][r["status"]] += 1
    L.append("| grup | MATCH | CLOSE | MISMATCH | NO_DATA | % (M+C)/comparables |")
    L.append("|---|--:|--:|--:|--:|--:|")
    for g in ("A", "calc", "narr", "fix", "resta"):
        c = by.get(g)
        if not c:
            continue
        L.append(f"| {g} | {c['MATCH']} | {c['CLOSE']} | {c['MISMATCH']} | {c['NO_DATA']} | {MI._pct(c)} |")
    L.append("")
    for r in rows:
        if r["status"] == "MATCH":
            continue
        L.append(f"- [{r['grup']}] `{r['var']}` **{r['status']}** gen=«{str(r['gen'])[:90]}» ↔ eva=«{str(r['eva'])[:90]}»")
    return "\n".join(L) + "\n"


def _agregat(run: str, results: dict, variants: list[str], sub: str) -> str:
    L = [f"# Agregat M341 — mesura completa `{run}`", ""]
    L.append(f"Informe generat des de `~/g3dt-e2e/projectes/<projecte>` vs signat. Escalars/narrativa: context de plantilla "
             f"vs `eva_reference_values.json` (`status_for`); taules: `compare_tables_vs_eva.py` (11 taules). Lectura `{sub}`. "
             f"Variants: `viaA` = només lectura + via B + Df del signat (7 projectes); `t2` = escalars d'abril de l'Eva + lectura (3).")
    L.append("")
    L.append("## Titulars per projecte i variant (escalars+narrativa: M · C · X · ND → % · taules: M · C · X → %)")
    L.append("")
    L.append("| projecte | " + " | ".join(f"{v} escalars" for v in variants) + " | " + " | ".join(f"{v} taules" for v in variants) + " |")
    L.append("|---|" + "---|" * (2 * len(variants)))
    tot_s = {v: Counter() for v in variants}
    tot_t = {v: Counter() for v in variants}
    for slug, per in results.items():
        cells_s, cells_t = [], []
        lang = next((r.get("lang") for r in per.values() if r.get("lang")), "ca")
        slug = f"{slug} ({lang})" if lang != "ca" else slug
        for v in variants:
            r = per.get(v)
            if not r or not r["gen"]["success"]:
                cells_s.append("**ERR**" if r else "—")
                cells_t.append("**ERR**" if r else "—")
                continue
            c = Counter(x["status"] for x in r["scalars"])
            tot_s[v].update(c)
            cells_s.append(f"{c['MATCH']} · {c['CLOSE']} · {c['MISMATCH']} · {c['NO_DATA']} → **{MI._pct(c)}**")
            t = r["report"]["totals"] if r.get("report") else {}
            tot_t[v].update({k: t.get(k, 0) for k in ("MATCH", "CLOSE", "MISMATCH")})
            cells_t.append(f"{t.get('MATCH', 0)} · {t.get('CLOSE', 0)} · {t.get('MISMATCH', 0)} → **{MI._pct(t)}**" if t else "—")
        L.append(f"| {slug} | " + " | ".join(cells_s) + " | " + " | ".join(cells_t) + " |")
    L.append("| **Total** | " + " | ".join(
        f"{tot_s[v]['MATCH']} · {tot_s[v]['CLOSE']} · {tot_s[v]['MISMATCH']} · {tot_s[v]['NO_DATA']} → **{MI._pct(tot_s[v])}**"
        for v in variants) + " | " + " | ".join(
        f"{tot_t[v]['MATCH']} · {tot_t[v]['CLOSE']} · {tot_t[v]['MISMATCH']} → **{MI._pct(tot_t[v])}**" for v in variants) + " |")
    L.append("")
    L.append("## Per GRUP (escalars+narrativa), variant × grup, agregat dels projectes")
    L.append("")
    L.append("| variant | grup | MATCH | CLOSE | MISMATCH | NO_DATA | % |")
    L.append("|---|---|--:|--:|--:|--:|--:|")
    for v in variants:
        by = defaultdict(Counter)
        for per in results.values():
            r = per.get(v)
            if r and r["gen"]["success"]:
                for x in r["scalars"]:
                    by[x["grup"]][x["status"]] += 1
        for g in ("A", "calc", "narr", "fix", "resta"):
            c = by.get(g)
            if c:
                L.append(f"| `{v}` | {g} | {c['MATCH']} | {c['CLOSE']} | {c['MISMATCH']} | {c['NO_DATA']} | {MI._pct(c)} |")
    L.append("")
    L.append("## Narrativa per IDIOMA del signat (viaA): les cel·les ES són el sostre de la plantilla catalana, no un error")
    L.append("")
    L.append("| idioma | projectes | MATCH | CLOSE | MISMATCH | NO_DATA | % |")
    L.append("|---|---|--:|--:|--:|--:|--:|")
    bylang: dict[str, Counter] = defaultdict(Counter)
    projs: dict[str, list[str]] = defaultdict(list)
    for slug, per in results.items():
        r = per.get("viaA")
        if r and r["gen"]["success"]:
            lg = r.get("lang", "ca")
            projs[lg].append(slug)
            for x in r["scalars"]:
                if x["grup"] == "narr":
                    bylang[lg][x["status"]] += 1
    for lg in ("ca", "es"):
        c = bylang.get(lg)
        if c:
            L.append(f"| {lg} | {', '.join(projs[lg])} | {c['MATCH']} | {c['CLOSE']} | {c['MISMATCH']} | {c['NO_DATA']} | {MI._pct(c)} |")
    L.append("")
    L.append(f"`{', '.join(sorted(NARR_EXCLUDED))}` fora de la mesura (text fix de la plantilla). Narrativa puntuada forat contra forat (`narr_status`).")
    L.append("")
    L.append("## Imatges (viaA): presència per forat — present · pendent («[Imatge pendent]») · absent (buit)")
    L.append("")
    L.append("| projecte | present | pendent | absent | forats pendents |")
    L.append("|---|--:|--:|--:|---|")
    for slug, per in results.items():
        r = per.get("viaA")
        im = (r or {}).get("images")
        if not im:
            continue
        L.append(f"| {slug} | {len(im['present'])} | {len(im['pendent'])} | {len(im['absent'])} | "
                 f"{', '.join(f'`{k}`' for k in im['pendent']) or '—'} |")
    L.append("")
    L.append("Absent = vistes generals no triades (`photo_site_image_*`) o foto del sondeig sense sondeig: no és cap defecte. "
             "Pendent = `image_manager` no ha trobat o no ha pogut baixar la imatge. La correcció del contingut es mira al full "
             "de control visual (`_IMATGES.md`, una vegada a mà).")
    L.append("")
    L.append("## Per VARIABLE (viaA): en quants projectes és MATCH / CLOSE / MISMATCH / NO_DATA")
    L.append("")
    byvar = defaultdict(Counter)
    for per in results.values():
        r = per.get("viaA")
        if r and r["gen"]["success"]:
            for x in r["scalars"]:
                byvar[x["var"]][x["status"]] += 1
    L.append("| variable | grup | M | C | X | ND |")
    L.append("|---|---|--:|--:|--:|--:|")
    for var in sorted(byvar, key=lambda k: (group_of(k), -byvar[k]["MISMATCH"], k)):
        c = byvar[var]
        L.append(f"| `{var}` | {group_of(var)} | {c['MATCH']} | {c['CLOSE']} | {c['MISMATCH']} | {c['NO_DATA']} |")
    L.append("")
    L.append("## Càlcul per projecte (viaA): nivell portant, Nb, φ, E, Qa, assentament")
    L.append("")
    L.append("| projecte | Df | nivell portant | Nb | φ | γ | c | E | Qa (gov) | assent. | imprès | Es |")
    L.append("|---|--:|---|--:|--:|--:|--:|--:|---|--:|---|---|")
    for slug, per in results.items():
        r = per.get("viaA")
        c = ((r or {}).get("gen") or {}).get("calc") or {}
        gp, tz, lv = c.get("geotechnical_params") or {}, c.get("terzaghi") or {}, c.get("soil_levels") or []
        last = lv[-1] if lv else {}
        sg = MI.SIGNAT_CALC.get(slug, {})
        L.append(f"| {slug} | {c.get('Df_user', '')} | {c.get('bearing_layer_idx', '')}: {(c.get('bearing_layer_description') or '')[:40]} | "
                 f"{last.get('Nb', '')} | {gp.get('phi', '')} | {gp.get('gamma', '')} | {gp.get('cohesion', '')} | {gp.get('E', '')} | "
                 f"{'' if tz.get('Qa') is None else f'{tz.get('Qa'):.2f}'} ({tz.get('qa_governs', '')}) | "
                 f"{'' if tz.get('settlement_cm') is None else f'{tz.get('settlement_cm'):.2f}'} | "
                 f"{MI._settle_cell(tz, sg.get('assentament'))} | {(tz.get('Es_used') and f'{tz.get('Es_used'):.0f}') or ''} |")
    L.append("")
    L.append("## Errors i avisos del generador")
    L.append("")
    for slug, per in results.items():
        for v, r in per.items():
            g = r["gen"]
            if g["errors"] or g["warnings"]:
                L.append(f"- **{slug}/{v}**: errors={g['errors']} warnings={g['warnings'][:8]}")
    L.append("")
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run")
    ap.add_argument("--variants", default=",".join(VARIANTS))
    ap.add_argument("--projects", default=",".join(NAMES))
    ap.add_argument("--lectura-sub", default=DEFAULT_LECTURA_SUB)
    ap.add_argument("--projectes-dir", default=str(DEFAULT_PROJECTES))
    ap.add_argument("--docx-dir", default=None)
    args = ap.parse_args()
    logging.basicConfig(level=logging.ERROR)
    for noisy in ("automation", "web"):
        logging.getLogger(noisy).setLevel(logging.ERROR)

    variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    slugs = [s.strip() for s in args.projects.split(",") if s.strip()]
    projectes = Path(args.projectes_dir).expanduser()
    run_dir = RUNS / args.run
    docx_dir = Path(args.docx_dir).expanduser() if args.docx_dir else Path.home() / "g3dt-e2e" / "informes-mesura" / args.run
    docx_dir.mkdir(parents=True, exist_ok=True)
    cmp_mod = MI._load_compare_module()

    results: dict[str, dict[str, dict]] = {}
    for slug in slugs:
        name = NAMES[slug]
        eva_path = REPO / "reference-material" / name / "validation" / "eva_reference_values.json"
        eva = json.loads(eva_path.read_text(encoding="utf-8"))["variables"]
        results[slug] = {}
        for v in variants:
            if v == "t2" and slug not in WITH_PREV:
                continue
            if v == "viaA":
                _sig = eva.get("data_signatura_text")
                ud = user_data_from_lectura(slug, _decisions(slug, args.lectura_sub),
                                            signature_date_iso(_sig.get("value") if isinstance(_sig, dict) else _sig))
                project_path = _project_path(name, projectes)
            else:
                ud = MI._user_data(slug, "t2", args.lectura_sub)
                project_path = REPO / "reference-material" / name
            out = run_dir / slug / v
            out.mkdir(parents=True, exist_ok=True)
            (out / "_user_data_usat.json").write_text(json.dumps(ud, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
            docx = docx_dir / f"{slug}_{v}.docx"
            gen, ctx, _ = _generate(project_path, ud, docx)
            entry: dict = {"gen": gen, "docx": str(docx), "lang": lang_of_eva(eva)}
            (out / "_calc.json").write_text(json.dumps(gen.get("calc") or {}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
            if gen["success"]:
                (out / "_context_usat.json").write_text(json.dumps(_jsonable(ctx), ensure_ascii=False, indent=1), encoding="utf-8")
                rows = compare_scalars(eva, ctx, ud, gen.get("calc") or {})
                entry["scalars"] = rows
                entry["images"] = image_presence(ctx)
                (out / "_compare_341.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
                (out / "_compare_341.txt").write_text(_fmt_rows(rows, f"{slug}/{v}"), encoding="utf-8")
                try:
                    txt = MI._compare(cmp_mod, docx, slug, f"{slug}/{v}", out / "_compare_informe.json")
                    (out / "_compare_informe.txt").write_text(txt, encoding="utf-8")
                    entry["report"] = json.loads((out / "_compare_informe.json").read_text(encoding="utf-8"))
                except Exception as exc:  # la veritat de taules pot faltar o no alinear
                    entry["report"] = None
                    gen["warnings"].append(f"taules: {exc}")
                c = Counter(r["status"] for r in rows)
                t = (entry.get("report") or {}).get("totals") or {}
                print(f"{slug:10s} {v:5s} escalars {c['MATCH']:3d} M · {c['CLOSE']:2d} C · {c['MISMATCH']:2d} X · {c['NO_DATA']:2d} ND → {MI._pct(c)}"
                      f" | taules {t.get('MATCH', 0)} M · {t.get('CLOSE', 0)} C · {t.get('MISMATCH', 0)} X → {MI._pct(t) if t else '—'}"
                      + (f"   [{len(gen['warnings'])} avisos]" if gen["warnings"] else ""), flush=True)
            else:
                entry["scalars"] = []
                print(f"{slug:10s} {v:5s} ERR generació: {gen['errors']}", flush=True)
            results[slug][v] = entry

    (run_dir / "_AGREGAT-341.md").write_text(_agregat(args.run, results, variants, args.lectura_sub), encoding="utf-8")
    print(f"\nAgregat: {run_dir / '_AGREGAT-341.md'}\n.docx a: {docx_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
