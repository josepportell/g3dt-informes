#!/usr/bin/env python3
"""Escriptura validada i atòmica del JSON per document (skill `/g3dt-llegir-projecte*`).

Substitueix la "cerimònia d'escriptura" que el model es construïa a mà
(`os.replace` + rellegir per verificar) — vegeu
`docs/wizard-headless/mesures/probes/2026-08-24-tall-stream-json/turns.md`, usos
14-15. El model passa el payload per stdin (o fitxer), aquest script el valida
contra el contracte mínim del Pas 4 del skill, tria el nom canònic
(`automation.lectura.runner.safe_doc_name`) i escriu de forma atòmica.

Ús:
    .venv/bin/python scripts/write_doc_json.py --out OUT_DIR \\
        --expect-source-path "REL/AL/DOCUMENT.pdf" --expect-md5 MD5 <<'EOF'
    {...payload...}
    EOF

    .venv/bin/python scripts/write_doc_json.py --out OUT_DIR payload.json

Sortida: `OK {path} tier_a={n} tables={claus amb files} not_present={n}` a
stdout (exit 0). Errors de validació: una línia `ERROR: ...` per error a
stderr (exit 2, no escriu res). Avisos no bloquejants (p. ex.
`context.authority_for` sense cobertura a `tier_a`): `WARNING: ...` a stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from automation.lectura.runner import safe_doc_name  # noqa: E402


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=1)
        os.replace(tmp_name, path)
    except Exception:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
        raise


_TIER_A_REQUIRED_KEYS = ("concept_id", "value", "location", "quote", "confidence")


def validate_payload(
    payload: Any, expect_source_path: str | None, expect_md5: str | None,
) -> tuple[list[str], list[str]]:
    """Retorna `(errors, warnings)`. `errors` no buit -> el caller no escriu res."""
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(payload, dict):
        return ["el payload no és un dict"], warnings

    if "schema_version" not in payload:
        errors.append("schema_version: absent")

    source_path = payload.get("source_path")
    if not source_path:
        errors.append("source_path: absent")
    elif expect_source_path is not None and source_path != expect_source_path:
        errors.append(f"source_path: esperat {expect_source_path!r}, trobat {source_path!r}")

    source_md5 = payload.get("source_md5")
    if not source_md5:
        errors.append("source_md5: absent")
    elif expect_md5 is not None and source_md5 != expect_md5:
        errors.append(f"source_md5: esperat {expect_md5!r}, trobat {source_md5!r}")

    tier_a = payload.get("tier_a")
    if not isinstance(tier_a, list):
        errors.append("tier_a: absent o no és una llista")
        tier_a = []
    else:
        for i, entry in enumerate(tier_a):
            if not isinstance(entry, dict):
                errors.append(f"tier_a[{i}]: no és un dict")
                continue
            for key in _TIER_A_REQUIRED_KEYS:
                if key not in entry:
                    errors.append(f"tier_a[{i}].{key}: absent")
            if "confidence" in entry:
                conf = entry["confidence"]
                valid_number = isinstance(conf, (int, float)) and not isinstance(conf, bool)
                if not valid_number or not (0.0 <= float(conf) <= 1.0):
                    errors.append(f"tier_a[{i}].confidence: ha de ser un float 0-1, trobat {conf!r}")

    context = payload.get("context")
    if not isinstance(context, dict):
        errors.append("context: absent o no és un dict")
        context = {}

    not_present = payload.get("not_present")
    if not_present is not None and not isinstance(not_present, list):
        errors.append("not_present: no és una llista")
        not_present = []
    not_present = not_present or []

    authority_for = context.get("authority_for")
    if not isinstance(authority_for, list):
        errors.append("context.authority_for: absent o no és una llista")
        authority_for = []

    tier_a_concept_ids = {e.get("concept_id") for e in tier_a if isinstance(e, dict)}
    for concept_id in authority_for:
        if concept_id not in tier_a_concept_ids and concept_id not in not_present:
            warnings.append(
                f"context.authority_for conté {concept_id!r} sense entrada a tier_a ni a not_present"
            )

    tables = payload.get("tables")
    if tables is not None and not isinstance(tables, dict):
        errors.append("tables: present però no és un dict")

    return errors, warnings


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", nargs="?", type=Path, default=None, help="Payload JSON (per defecte: stdin)")
    parser.add_argument("--out", required=True, type=Path, help="Directori de sortida")
    parser.add_argument("--expect-source-path", default=None, help="source_path esperat (validació creuada)")
    parser.add_argument("--expect-md5", default=None, help="source_md5 esperat (validació creuada)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)

    raw = args.file.read_text(encoding="utf-8") if args.file else sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"ERROR: JSON invàlid: {exc}", file=sys.stderr)
        return 2

    errors, warnings = validate_payload(payload, args.expect_source_path, args.expect_md5)
    for w in warnings:
        print(f"WARNING: {w}", file=sys.stderr)
    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    out_path = args.out / (safe_doc_name(payload["source_path"]) + ".json")
    _write_json_atomic(out_path, payload)

    tables = payload.get("tables") or {}
    table_keys = [k for k, v in tables.items() if isinstance(v, list) and v]
    tier_a = payload.get("tier_a") or []
    not_present = payload.get("not_present") or []
    print(f"OK {out_path} tier_a={len(tier_a)} tables={','.join(table_keys)} not_present={len(not_present)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
