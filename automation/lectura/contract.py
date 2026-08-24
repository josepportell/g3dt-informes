"""Contracte del schema v1 de `_decisions.json` (Fase 1 del wizard headless).

Vegeu `docs/DISSENY-WIZARD-HEADLESS-CANDIDATS-2026-08-24.md` §4 i el Pas 5 /
Pas 5b de `.claude/commands/g3dt-llegir-projecte.md` per al disseny complet.

Aquest mòdul NO llegeix ni escriu cap fitxer (stdlib pur, sense I/O): el
runner headless (Fase 3) l'invocarà per validar la sortida de
`claude -p ... --consolida` abans de confiar-hi.

Dos punts d'entrada:

- `validate_decisions(d)` — valida un dict ja en dialecte v1 (`estat`/`font`)
  contra les regles del §4.3 del disseny. Retorna la llista d'errors (buida
  = vàlid).
- `adapt_legacy(d)` — converteix els dos dialectes antics dels fixtures d'or
  (`docs/golden-read/*/_decisions.json` amb `status`/`source` i niuats
  `lab`/`cte`/`utm_x_utm_y`; `docs/golden-read-taules/*/_tables_decisions.json`
  amb `estat`/`font` però estructura pre-v1) al schema v1, perquè es puguin
  fer servir com a fixtures de test de `validate_decisions`.
"""

from __future__ import annotations

import copy
import re
from typing import Any

# ---------------------------------------------------------------------------
# Constants del contracte (Pas 5 del skill g3dt-llegir-projecte, v1.0)
# ---------------------------------------------------------------------------

#: Les 22 claus planes de `fields` (Pas 5 del skill / §4.2 del disseny).
ALLOWED_FIELD_KEYS: frozenset[str] = frozenset(
    {
        "expedient",
        "client_name",
        "street_address",
        "municipality",
        "architect_name",
        "architect_company",
        "building_type",
        "num_floors",
        "superficie_parcela",
        "field_date",
        "cota_referencia",
        "num_soil_levels",
        "num_dpsh_tests",
        "utm_x",
        "utm_y",
        "referencia_catastral",
        "lab_testing_company",
        "lab_sample_id",
        "lab_depth",
        "lab_location",
        "cte_edificacio",
        "cte_sol",
    }
)

#: Els 3 estats vàlids d'una decisió (camp o cel·la de taula).
VALID_ESTATS: frozenset[str] = frozenset({"segur", "candidats", "no_trobat"})

#: Claus del dialecte antic (`docs/golden-read/*`): la seva presència, a
#: QUALSEVOL nivell del dict, és un error del contracte v1.
OLD_DIALECT_KEYS: frozenset[str] = frozenset({"status", "source"})

#: Valors vàlids de `matis` a `nivell_freatic` (regla g / Pas 3b del skill).
VALID_MATIS: frozenset[Any] = frozenset({None, "humitat", "aigua"})

#: Blocs de `tables` que segueixen el patró `{"estat_bloc": ..., "rows": [...]}`.
TABLE_ROW_GROUPS: tuple[str, ...] = (
    "dpsh_tests",
    "sondeig_tests",
    "spt_ma_tests",
    "soil_levels",
)

#: Subclaus planes de l'antic camp niuat `lab` (ordre = ordre d'aparició al skill).
_LAB_SUBKEYS: tuple[str, ...] = (
    "lab_testing_company",
    "lab_sample_id",
    "lab_depth",
    "lab_location",
)

#: Subclaus planes de l'antic camp niuat `cte`.
_CTE_SUBKEYS: tuple[str, ...] = ("cte_edificacio", "cte_sol")

#: Parteja "X <num> ; Y <num>" (amb decimals amb punt o coma) de l'antic
#: `utm_x_utm_y.value` per obtenir `utm_x`/`utm_y`.
_UTM_RE = re.compile(r"X\s*([\-\d.,]+)\s*;\s*Y\s*([\-\d.,]+)", re.IGNORECASE)


# ---------------------------------------------------------------------------
# validate_decisions
# ---------------------------------------------------------------------------


def validate_decisions(d: dict) -> list[str]:
    """Valida un `_decisions.json` (schema v1) contra les regles del §4.3.

    Retorna la llista d'errors trobats (buida = vàlid). No llança excepcions
    per un `d` mal format: ho reporta com a errors i continua el que pugui.
    """
    errors: list[str] = []

    if not isinstance(d, dict):
        return ["arrel: no és un dict"]

    # a. schema_version == 1; fields i tables presents (dict).
    if d.get("schema_version") != 1:
        errors.append(f"schema_version: esperat 1, trobat {d.get('schema_version')!r}")

    fields = d.get("fields")
    if not isinstance(fields, dict):
        errors.append("fields: absent o no és un dict")
        fields = {}

    tables = d.get("tables")
    if not isinstance(tables, dict):
        errors.append("tables: absent o no és un dict")
        tables = {}

    # b (part 2). Cap clau del dialecte antic (status/source), a cap nivell.
    errors.extend(_scan_old_dialect_keys(d, "arrel"))

    # h. Claus de `fields` subconjunt de les 22 claus planes.
    for key, cell in fields.items():
        path = f"fields.{key}"
        if key not in ALLOWED_FIELD_KEYS:
            errors.append(f"{path}: clau desconeguda (no és a les 22 claus planes de fields)")
        errors.extend(_validate_cell(cell, path))

    # Blocs de taula amb files (dpsh_tests, sondeig_tests, spt_ma_tests, soil_levels).
    for table_name in TABLE_ROW_GROUPS:
        if table_name not in tables:
            continue
        table_val = tables[table_name]
        if not isinstance(table_val, dict) or not isinstance(table_val.get("rows"), list):
            errors.append(f"tables.{table_name}: falta 'rows' (llista)")
            continue

        for i, row in enumerate(table_val["rows"]):
            row_path = f"tables.{table_name}.rows[{i}]"
            if not isinstance(row, dict):
                errors.append(f"{row_path}: fila no és un dict")
                continue

            for cell_key, cell in row.items():
                if not (isinstance(cell, dict) and "estat" in cell):
                    continue
                cell_path = f"{row_path}.{cell_key}"
                errors.extend(_validate_cell(cell, cell_path))

                # cel·les niuades (p.ex. n30.registre): mateixes regles si porten `estat`.
                nested = cell.get("registre")
                if isinstance(nested, dict) and "estat" in nested:
                    errors.extend(_validate_cell(nested, f"{cell_path}.registre"))

            # f. n30 (spt_ma_tests) mai segur; ha de portar `registre`.
            if table_name == "spt_ma_tests":
                n30 = row.get("n30")
                if isinstance(n30, dict):
                    if n30.get("estat") == "segur":
                        errors.append(f"{row_path}.n30.estat: mai pot ser 'segur'")
                    if "registre" not in n30:
                        errors.append(f"{row_path}.n30: falta la clau 'registre'")

            # f. litologia (soil_levels) mai segur.
            if table_name == "soil_levels":
                litologia = row.get("litologia")
                if isinstance(litologia, dict) and litologia.get("estat") == "segur":
                    errors.append(f"{row_path}.litologia.estat: mai pot ser 'segur'")

            # g. nivell_freatic.matis ∈ {None, "humitat", "aigua"}.
            if table_name in ("dpsh_tests", "sondeig_tests"):
                nf = row.get("nivell_freatic")
                if isinstance(nf, dict) and "matis" in nf and nf["matis"] not in VALID_MATIS:
                    errors.append(f"{row_path}.nivell_freatic.matis: valor invàlid {nf['matis']!r}")

    # superficie_construida: cel·la plana (no és una llista de files).
    if "superficie_construida" in tables:
        sc = tables["superficie_construida"]
        if isinstance(sc, dict) and "estat" in sc:
            errors.extend(_validate_cell(sc, "tables.superficie_construida"))

    return errors


def _validate_cell(cell: Any, path: str) -> list[str]:
    """Valida una "decisió" (camp de `fields` o cel·la de fila de `tables`).

    Regles b, c, d, e del §4.3.
    """
    errors: list[str] = []

    if not isinstance(cell, dict):
        errors.append(f"{path}: no és un dict")
        return errors

    estat = cell.get("estat")
    if estat not in VALID_ESTATS:
        errors.append(f"{path}.estat: valor invàlid {estat!r}")
        return errors

    if estat in ("segur", "candidats"):
        candidates = cell.get("candidates")
        if not candidates:
            errors.append(f"{path}.candidates: buit o absent (calen per a estat={estat!r})")
        else:
            if len(candidates) > 3:
                errors.append(f"{path}.candidates: {len(candidates)} entrades (màxim 3)")
            for j, c in enumerate(candidates):
                if not isinstance(c, dict):
                    errors.append(f"{path}.candidates[{j}]: no és un dict")
                    continue
                for required_key in ("value", "font", "quote"):
                    if required_key not in c:
                        errors.append(f"{path}.candidates[{j}].{required_key}: absent")

            if estat == "candidats" and isinstance(candidates[0], dict):
                if cell.get("value") != candidates[0].get("value"):
                    errors.append(f"{path}.value: no coincideix amb candidates[0].value")

    elif estat == "no_trobat":
        if cell.get("value") is not None:
            errors.append(f"{path}.value: ha de ser None per a estat=no_trobat")
        if not cell.get("sources_checked"):
            errors.append(f"{path}.sources_checked: buit o absent per a estat=no_trobat")

    return errors


def _scan_old_dialect_keys(obj: Any, path: str) -> list[str]:
    """Cerca recursivament claus `status`/`source` (dialecte antic) a `obj`."""
    errors: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in OLD_DIALECT_KEYS:
                errors.append(f"{path}.{k}: clau del dialecte antic prohibida (usa estat/font)")
            errors.extend(_scan_old_dialect_keys(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            errors.extend(_scan_old_dialect_keys(v, f"{path}[{i}]"))
    return errors


# ---------------------------------------------------------------------------
# adapt_legacy
# ---------------------------------------------------------------------------


def adapt_legacy(d: dict) -> dict:
    """Adapta un fixture d'or (dialecte antic) a l'estructura del schema v1.

    Gestiona dues formes d'entrada:

    - Escalars (`docs/golden-read/*/_decisions.json`): arrel amb clau
      `"decisions"`, dialecte `status`/`source`, camps niuats `lab`/`cte`
      (value = dict de 4/2 subclaus) i `utm_x_utm_y` (value = "X ... ; Y ...").
    - Taules (`docs/golden-read-taules/*/_tables_decisions.json`): arrel amb
      clau `"tables"`, ja en dialecte `estat`/`font` però amb variacions
      estructurals entre projectes (llista plana vs `{estat_bloc, rows}`,
      `litologia_candidats` vs `litologia`, `registre` germà vs niuat a `n30`).

    Un dict que ja sembli schema v1 (claus `fields`/`tables` a l'arrel, sense
    `decisions`) es normalitza mínimament i es retorna.

    NO és fabricació de dades: quan un fixture d'or no compleix una regla
    purament ESTRUCTURAL del contracte (p. ex. `candidates` absent en un
    camp `segur`, o `value` absent en un camp `candidats`), es reconstrueix
    la forma exigida pel contracte a partir de les dades JA PRESENTS al
    fixture (el primer candidat, el `value` existent) — mai s'inventa un
    valor nou.
    """
    d = _rename_dialect_keys(copy.deepcopy(d))

    if "decisions" in d:
        return _adapt_scalar_dialect(d)
    if "tables" in d:
        return _adapt_tables_dialect(d)

    # Ja sembla v1 (o prou a prop): normalitza l'embolcall mínim.
    return {
        "schema_version": 1,
        "project": d.get("project", ""),
        "generated": d.get("generated", ""),
        "fields": d.get("fields", {}) if isinstance(d.get("fields"), dict) else {},
        "tables": d.get("tables", {}) if isinstance(d.get("tables"), dict) else {},
    }


def _rename_dialect_keys(obj: Any) -> Any:
    """Renombra recursivament `status`→`estat` i `source`→`font` a tot `obj`."""
    if isinstance(obj, dict):
        renamed = {}
        for k, v in obj.items():
            new_key = {"status": "estat", "source": "font"}.get(k, k)
            renamed[new_key] = _rename_dialect_keys(v)
        return renamed
    if isinstance(obj, list):
        return [_rename_dialect_keys(x) for x in obj]
    return obj


def _adapt_scalar_dialect(d: dict) -> dict:
    """Adapta `docs/golden-read/*/_decisions.json` (ja amb estat/font)."""
    fields_out: dict[str, Any] = {}

    for key, entry in d.get("decisions", {}).items():
        if not isinstance(entry, dict):
            continue
        if key == "lab":
            _flatten_nested_field(fields_out, _LAB_SUBKEYS, entry)
        elif key == "cte":
            _flatten_nested_field(fields_out, _CTE_SUBKEYS, entry)
        elif key == "utm_x_utm_y":
            x_entry, y_entry = _split_utm(entry)
            fields_out["utm_x"] = x_entry
            fields_out["utm_y"] = y_entry
        else:
            fields_out[key] = copy.deepcopy(entry)

    for key in list(fields_out):
        fields_out[key] = _canonicalize_cell(fields_out[key])

    return {
        "schema_version": 1,
        "project": d.get("project", ""),
        "generated": d.get("read_on", d.get("generated", "")),
        "fields": fields_out,
        "tables": {},
    }


def _flatten_nested_field(fields_out: dict[str, Any], subkeys: tuple[str, ...], entry: dict) -> None:
    """Aplana un camp niuat (`lab`/`cte`) en N camps plans amb el mateix
    estat/rule/candidates/sources_checked, `value` = la subclau corresponent."""
    nested_value = entry.get("value")
    value_dict = nested_value if isinstance(nested_value, dict) else {}
    for sub in subkeys:
        sub_entry = copy.deepcopy(entry)
        sub_entry["value"] = value_dict.get(sub)
        fields_out[sub] = sub_entry


def _split_utm(entry: dict) -> tuple[dict, dict]:
    """Parteja `utm_x_utm_y.value` ("X nnn ; Y nnn ...") en (utm_x, utm_y).

    Si el `value` no matcheja el patró (o no és una cadena, p. ex. `None`
    per a `no_trobat`), es fa servir el mateix `value` per a totes dues.
    """
    value = entry.get("value")
    x_value = y_value = value
    if isinstance(value, str):
        m = _UTM_RE.search(value)
        if m:
            x_value, y_value = m.group(1), m.group(2)

    x_entry = copy.deepcopy(entry)
    x_entry["value"] = x_value
    y_entry = copy.deepcopy(entry)
    y_entry["value"] = y_value
    return x_entry, y_entry


def _adapt_tables_dialect(d: dict) -> dict:
    """Adapta `docs/golden-read-taules/*/_tables_decisions.json`."""
    tables_in = d.get("tables", {})
    tables_out: dict[str, Any] = {}

    for table_name in TABLE_ROW_GROUPS:
        if table_name not in tables_in:
            continue
        wrapped = _wrap_rows(tables_in[table_name])
        fixed_rows = []
        for row in wrapped.get("rows", []):
            if not isinstance(row, dict):
                continue
            row = copy.deepcopy(row)
            if table_name == "spt_ma_tests":
                row = _fix_spt_ma_row(row)
            elif table_name == "soil_levels":
                row = _fix_soil_level_row(row)
            row = _canonicalize_row_cells(row)
            fixed_rows.append(row)
        wrapped["rows"] = fixed_rows
        tables_out[table_name] = wrapped

    if "superficie_construida" in tables_in:
        sc = copy.deepcopy(tables_in["superficie_construida"])
        if isinstance(sc, dict) and "estat" in sc:
            sc = _canonicalize_cell(sc)
        tables_out["superficie_construida"] = sc

    return {
        "schema_version": 1,
        "project": d.get("project", ""),
        "generated": d.get("generated", d.get("read_date", "")),
        "fields": {},
        "tables": tables_out,
    }


def _wrap_rows(table_val: Any) -> dict:
    """Normalitza un bloc de taula a `{"estat_bloc": ..., "rows": [...]}`.

    `docs/golden-read-taules/4001612 BELL-LLOC` ja ve en aquesta forma;
    `docs/golden-read-taules/4001679 ANCILES` ve com a llista plana de files.
    """
    if isinstance(table_val, list):
        return {"estat_bloc": "adaptat", "rows": table_val}
    if isinstance(table_val, dict):
        if isinstance(table_val.get("rows"), list):
            return table_val
        return {"estat_bloc": table_val.get("estat_bloc", "adaptat"), "rows": []}
    return {"estat_bloc": "adaptat", "rows": []}


def _fix_spt_ma_row(row: dict) -> dict:
    """Assegura que `n30` porta la clau `registre` (regla f):

    - Bell-lloc: `n30.registre_15cm` (llista) → `n30.registre`.
    - Anciles: `registre` germà de `n30` (cel·la pròpia, `segur`) → niuada
      dins `n30.registre`.
    """
    n30 = row.get("n30")
    if "registre" in row and isinstance(n30, dict):
        sibling_registre = row.pop("registre")
        n30.setdefault("registre", sibling_registre)
    if isinstance(n30, dict) and "registre_15cm" in n30 and "registre" not in n30:
        n30["registre"] = n30.pop("registre_15cm")
    return row


def _fix_soil_level_row(row: dict) -> dict:
    """Converteix `litologia_candidats` (llista) en `litologia` (cel·la),
    quan el projecte encara no porta `litologia` directament (Bell-lloc)."""
    if "litologia_candidats" in row and "litologia" not in row:
        candidates = row.pop("litologia_candidats")
        value = candidates[0].get("value") if candidates else None
        row["litologia"] = {
            "estat": "candidats",
            "value": value,
            "candidates": candidates,
            "rule": row.get("rule"),
        }
    return row


def _canonicalize_row_cells(row: dict) -> dict:
    """Aplica `_canonicalize_cell` a cada cel·la (i cel·la niuada `registre`)
    d'una fila de taula."""
    for key, val in list(row.items()):
        if isinstance(val, dict) and "estat" in val:
            val = _canonicalize_cell(val)
            row[key] = val
            nested = val.get("registre")
            if isinstance(nested, dict) and "estat" in nested:
                val["registre"] = _canonicalize_cell(nested)
    return row


def _canonicalize_cell(cell: Any) -> Any:
    """Repara una decisió perquè compleixi les regles c/d del §4.3:

    - `segur`/`candidats` sense `candidates` (o buit): sintetitza un únic
      candidat a partir del `value` existent (font "(adaptat)").
    - `candidats` amb `value` absent o diferent de `candidates[0].value`:
      adopta `candidates[0].value` com a `value` de la cel·la (és exactament
      el que la UI hauria de pre-omplir, Pas 5 del skill).
    """
    if not isinstance(cell, dict) or "estat" not in cell:
        return cell

    estat = cell.get("estat")
    if estat not in ("segur", "candidats"):
        return cell

    candidates = cell.get("candidates")
    if not candidates:
        value = cell.get("value")
        quote = value if isinstance(value, str) else ("" if value is None else str(value))
        candidates = [{"value": value, "font": "(adaptat)", "quote": quote}]
        cell["candidates"] = candidates

    if estat == "candidats" and isinstance(candidates[0], dict):
        first_value = candidates[0].get("value")
        if cell.get("value") != first_value:
            cell["value"] = first_value

    return cell
