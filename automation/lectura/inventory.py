"""Fase 2 (via A, wizard headless) — inventari i enrutament de documents.

Escaneja recursivament una carpeta de projecte G3 i decideix, per a CADA fitxer,
qui l'ha de llegir: `route: "python"` (lector determinista de
`automation/g3_templates.py`), `route: "claude"` (crida headless `claude -p
/g3dt-llegir-projecte --only`) o `route: "skip"` (sortida nostra/de l'Eva, foto,
o fitxer no rellevant per al nivell A). Escriu `_inventory.json` (disseny
`docs/DISSENY-WIZARD-HEADLESS-CANDIDATS-2026-08-24.md` §3.2).

Fonts de les regles d'exclusió (dues, combinades — mai reescrites, sempre citades):
  - Pas 1 del skill `.claude/commands/g3dt-llegir-projecte.md` (`*_informe*`,
    `*_generated*`, `*PORTADA*`, `PDF/LLETRA/`, `PDF-V0/`, `PDF V0/`, `*.FH11`,
    `validation/`, `_validation/`, `Thumbs.db`, `*EXPLICACI*`).
  - `automation/g3_templates.EXCLUDE_DIRS` / `EXCLUDE_NAME_PARTS` (importats
    directament, no replicats, per evitar deriva entre els dos mòduls). Ja cobreixen
    `validation/`, `_validation/`, `mined_images/`, `concept_probes/`,
    `msg_attachments/`, `PDF-V0/`, `PDF V0/`, `PDF_V0/`, `LLETRA/` i els noms
    `_generated`, `informe`, `PORTADA`, `AUDIT`, `~$`.
  Complementem amb el que aquestes dues fonts NO cobreixen: extensió `.fh11`
  (original FreeHand no llegible; la còpia PDF/ANNEXES sí ho és), `*EXPLICACI*`
  (meta-document), `Thumbs.db`.

Decisions d'enrutament AMBIGÜES preses aquí (documentades també al recompte final
del mòdul que crida `build_inventory`, i al report de la Fase 2):

  1. **Excel DPSH (`*_DPSH.xls`) → route "claude", NO "python"**, tot i ser una
     de "les 5 plantilles G3". Instrucció explícita de la Fase 2: NO emetre dues
     entrades (python+claude) pel mateix fitxer — `g3_templates.read_project()`
     ja el llegeix pel seu compte, FORA de l'inventari (no és inventory-driven:
     escaneja la carpeta amb els seus propis patrons, sempre, independentment del
     que digui aquest `route`). L'entrada de l'inventari només serveix per a la
     part que el Python NO pot fer (N.F./Nivells marcats per COLOR de cel·la,
     `xlrd formatting_info=True` — disseny §3.1, fila "Excel DPSH"). doc_type_hint
     `"dpsh_excel"`, priority 3.
  2. **`ACCEPTACIO/`** (pressupost signat, `DADES CLIENT.txt`, o una foto/WhatsApp
     del formulari p.5 quan no hi ha PDF escanejat) — carpeta sencera → route
     "claude", doc_type_hint `"acceptacio"`, priority 2, ABANS de qualsevol regla
     de nom o d'extensió (fins i tot si el fitxer és `.jpg`/`.jpeg`, que altrament
     seria "foto"→skip): el skill la tracta com a font pròpia i AUTORITAT A per a
     `client_name` (Pas 3), no com una foto de camp. Prioritat 2 no ve donada
     explícitament al disseny §3.1 (no hi surt ACCEPTACIO): triada per ser molt
     primerenca (l'ordre de lectura del Pas 1 del skill la posa just després de
     les plantilles G3, abans dels annexos), sense xocar amb les prioritats donades.
  3. **`tall.pdf` / `pl. situaci.pdf` arrel I `PDF/ANNEXES/{exp}_tall de
     correlació.pdf` / `PDF/ANNEXES/{exp}_plànol de situació.pdf`** es tracten
     com el MATEIX tipus de document (dues còpies — Print-To-PDF net vs.
     FreeHand-exportat brossa — que el skill creua explícitament, Pas 3
     "Esborranys de l'Eva"), no només el nom literal `tall.pdf` de la taula
     §3.1: totes dues formes reben route "claude" amb el mateix doc_type_hint
     (`annex_tall` / `annex_planol_situacio`).
  4. **PDF/DWG no classificat per cap altra regla** (p. ex. `LAB-SIG.pdf`,
     `*_fotografies.pdf`) → cau al calaix "plànol/projecte arquitecte, pdf/dwg no
     classificats com a res més" del disseny §3.1 (route "claude",
     doc_type_hint `"altre"`, priority 6, la mateixa cua que `A.0*.pdf`): el
     skill sap identificar-lo en llegir-lo (`document_type` obert al Pas 4);
     millor una crida de més que un fitxer mai llegit.
  5. **Qualsevol altre fitxer no reconegut** (`.json` d'estat del pipeline,
     `.docx`/`.doc` sobrants de proves de desenvolupament, `.zip` no obert —
     obrir zips és fora d'abast d'aquesta fase) → route "skip",
     doc_type_hint `"no_classificat"`. Mai `.pdf`/`.dwg`: aquests sempre cauen
     al calaix 4, no aquí.

Determinisme: cap accés de xarxa, cap escriptura dins `project_path` (només
`write_inventory` escriu, i només a `out_dir`), fitxers ordenats per `path`, md5
en streaming.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path, PurePosixPath

from automation.g3_templates import EXCLUDE_DIRS, EXCLUDE_NAME_PARTS

# Exclusions de nom que ni el skill Pas 1 ni g3_templates cobreixen totes dues.
_EXTRA_EXCLUDE_NAME_PARTS = ("EXPLICACI", "Thumbs.db")
_SKIP_EXTENSIONS = {".fh11"}
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
_FALLBACK_CLAUDE_EXTENSIONS = {".pdf", ".dwg"}

_MD5_CHUNK = 1 << 20  # 1 MiB, per a fitxers grans (lectura en streaming)

# --------------------------------------------------------------------------
# Prioritat de cua (disseny §3.1, "Prioritat cua"; 0 = no aplica / instantani).
# Decisions 2-4 del docstring hi afegeixen ACCEPTACIO (2, empatat amb l'annex
# DPSH) i "altre" (6, mateixa cua que "planol").
# --------------------------------------------------------------------------
_PRIORITY_BY_HINT = {
    "annex_sondeig": 1,
    "annex_dpsh": 2,
    "acceptacio": 2,
    "dpsh_excel": 3,
    "annex_tall": 4,
    "informe_laboratori": 5,
    "planol": 6,
    "altre": 6,
    "camp_penetros": 7,
    "correu": 8,
    "annex_planol_situacio": 9,
    "full_camp_manuscrit": 10,
}

# --------------------------------------------------------------------------
# Patrons de les 4 plantilles G3 deterministes (route python; la 5a, l'Excel
# DPSH, és route claude — decisió 1 del docstring).
# --------------------------------------------------------------------------
_RE_PRESSUPOST = re.compile(r"^PRESSUPOST\s+GEOTEC.*\.pdf$", re.I)
_RE_FITXA_CAMP = re.compile(r"^DADES\s+PER\s+ANAR\s+A\s+CAMP.*\.xlsx$", re.I)
_RE_COMANDA_LAB = re.compile(r"^comanda\s+laboratori.*\.xls$", re.I)
_RE_PLAN_COST = re.compile(r"^PLAN_COST.*\.xlsx$", re.I)
_RE_COORDENADES = re.compile(r"^COORDENADES\.txt$", re.I)
_RE_DPSH_EXCEL = re.compile(r".*_DPSH\.xls$", re.I)
# RC cadastral: 7 xifres seguides IMMEDIATAMENT (sense separador) d'almenys 6
# caràcters alfanumèrics/guionets — format típic "4613172CG1141S0001SU-15.pdf".
_RE_CADASTRE_RC = re.compile(r"^\d{7}[A-Z0-9-]{6,}\.pdf$", re.I)
_CERTIFICACIO_SUBSTR = "certificaci"

_RE_ANNEX_SONDEIG = re.compile(r".*_sondeig\.pdf$", re.I)
_RE_ANNEX_DPSH_PDF = re.compile(r".*_DPSH\.pdf$", re.I)
_RE_ANNEX_TALL = re.compile(r"^tall\.pdf$|tall\s*de\s*correlaci.*\.pdf$", re.I)
_RE_ANNEX_PLANOL_SITUACIO = re.compile(r"pl.*situaci.*\.pdf$", re.I)
_RE_PENETROS = re.compile(r"penetros", re.I)
_RE_SONDEIG_MANUSCRIT = re.compile(r"^SONDEIG\.pdf$", re.I)
_RE_GTL = re.compile(r"gtl", re.I)
_RE_PLANOL_ARQUITECTE = re.compile(r"^A\.0\d.*\.pdf$", re.I)


def _md5_of(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(_MD5_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def _classify(rel: PurePosixPath) -> tuple[str, str]:
    """Retorna (route, doc_type_hint) per a un path relatiu (separador '/')."""
    parts = rel.parts
    name = rel.name
    lname = name.lower()
    suffix = rel.suffix.lower()

    # -- 1. Exclusions dures (skip), en ordre --------------------------------
    if any(part in EXCLUDE_DIRS for part in parts):
        return "skip", "exclos_carpeta"
    for token in EXCLUDE_NAME_PARTS:
        if token.lower() in lname:
            return "skip", f"exclos_nom:{token}"
    for token in _EXTRA_EXCLUDE_NAME_PARTS:
        if token.lower() in lname:
            return "skip", f"exclos_nom:{token}"
    if suffix in _SKIP_EXTENSIONS:
        return "skip", "annex_freehand_no_llegible"

    # -- 2. ACCEPTACIO/ — override abans de qualsevol altra regla (decisió 2) -
    if any(part.upper() == "ACCEPTACIO" for part in parts):
        return "claude", "acceptacio"

    # -- 3. Plantilles G3 deterministes (route python) -----------------------
    if _RE_PRESSUPOST.match(name):
        return "python", "pressupost_g3"
    if _RE_FITXA_CAMP.match(name):
        return "python", "fitxa_camp_g3"
    if _RE_COMANDA_LAB.match(name):
        return "python", "comanda_lab_g3"
    if _RE_PLAN_COST.match(name):
        return "python", "plan_cost_g3"
    if _RE_COORDENADES.match(name):
        return "python", "coordenades_gps"
    if _RE_CADASTRE_RC.match(name) or _CERTIFICACIO_SUBSTR in lname:
        return "python", "consulta_cadastre"

    # -- 4. Excel DPSH — route claude, decisió 1 del docstring ---------------
    if _RE_DPSH_EXCEL.match(name):
        return "claude", "dpsh_excel"

    # -- 5. Annexos de l'Eva (route claude) -----------------------------------
    if _RE_ANNEX_SONDEIG.match(name):
        return "claude", "annex_sondeig"
    if _RE_ANNEX_DPSH_PDF.match(name) and any(p.upper() == "ANNEXES" for p in parts):
        return "claude", "annex_dpsh"
    if _RE_ANNEX_TALL.search(name):
        return "claude", "annex_tall"
    if _RE_ANNEX_PLANOL_SITUACIO.search(name):
        return "claude", "annex_planol_situacio"

    # -- 6. Camp ---------------------------------------------------------------
    if suffix == ".pdf" and _RE_PENETROS.search(name):
        return "claude", "camp_penetros"
    if _RE_SONDEIG_MANUSCRIT.match(name):
        return "claude", "full_camp_manuscrit"

    # -- 7. Laboratori -----------------------------------------------------
    if suffix == ".pdf" and _RE_GTL.search(name):
        return "claude", "informe_laboratori"

    # -- 8. Arquitecte / plànols --------------------------------------------
    if _RE_PLANOL_ARQUITECTE.match(name):
        return "claude", "planol"

    # -- 9. Correus ----------------------------------------------------------
    if suffix == ".msg":
        return "claude", "correu"

    # -- 10. Fallback pdf/dwg no classificats com a res més (decisió 4) ------
    if suffix in _FALLBACK_CLAUDE_EXTENSIONS:
        return "claude", "altre"

    # -- 11. Fotos -------------------------------------------------------------
    if suffix in _IMAGE_EXTENSIONS:
        return "skip", "foto"

    # -- 12. Qualsevol altra cosa (decisió 5) ---------------------------------
    return "skip", "no_classificat"


def build_inventory(project_path: Path) -> dict:
    """Escaneja `project_path` i retorna l'estructura d'inventari (disseny §3.2).

    Read-only: no escriu res, no fa accés de xarxa. Determinista: els fitxers
    de sortida estan ordenats per `path`.
    """
    project_path = Path(project_path)
    entries: list[dict] = []
    for p in project_path.rglob("*"):
        if not p.is_file():
            continue
        rel = PurePosixPath(p.relative_to(project_path).as_posix())
        route, doc_type_hint = _classify(rel)
        priority = _PRIORITY_BY_HINT.get(doc_type_hint, 0) if route == "claude" else 0
        st = p.stat()
        entries.append({
            "path": str(rel),
            "size": st.st_size,
            "md5": _md5_of(p),
            "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
            "route": route,
            "doc_type_hint": doc_type_hint,
            "priority": priority,
        })
    entries.sort(key=lambda e: e["path"])

    md5_groups: dict[str, list[str]] = {}
    for e in entries:
        if e["route"] == "skip":
            continue
        md5_groups.setdefault(e["md5"], []).append(e["path"])
    duplicates = sorted(
        (sorted(paths) for paths in md5_groups.values() if len(paths) > 1),
        key=lambda g: g[0],
    )

    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "project": project_path.name,
        "files": entries,
        "duplicates": duplicates,
    }


def write_inventory(project_path: Path, out_dir: Path) -> Path:
    """Escriu `_inventory.json` de forma ATÒMICA a `out_dir` (tmp + os.replace).

    Mai escriu dins `project_path`: només al `out_dir` explícit que rep. El
    caller (el servei del wizard, Fase 5) decideix si `out_dir` viu sota
    `validation/lectura/` del projecte o en un altre lloc (p. ex. fixtures de test).
    """
    project_path = Path(project_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    final_path = out_dir / "_inventory.json"

    inventory = build_inventory(project_path)
    payload = json.dumps(inventory, ensure_ascii=False, indent=1)

    fd, tmp_name = tempfile.mkstemp(dir=str(out_dir), prefix="_inventory.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp_name, final_path)
    except Exception:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
        raise
    return final_path
