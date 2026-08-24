"""Fase 3+4 (via A, wizard headless) — runner subprocess de la lectura.

Vegeu `docs/DISSENY-WIZARD-HEADLESS-CANDIDATS-2026-08-24.md` §2 (seqüencia SSE en
2 temps + consolidacio), §5 (mecanica de la crida headless), §6 (cache i
re-execucio) i §7 (fallback i telemetria); i el Pas 4/5/5b de
`.claude/commands/g3dt-llegir-projecte.md`.

Patrons de referencia (NOMES lectura, no editats): `web/vision_fast.py:150-200`
(spawn `claude -p`, timeout+kill POSIX) i `web/wizard_service.py:2480-2560`
(`start_vision_cli`, mateix patro amb `os.killpg`).

Punt d'entrada public: `run_lectura(project_path, ...)`. Fase 4 (consolidacio +
degradat) viu al mateix modul perque comparteix estat amb el runner (cache,
telemetria, `out_dir`): `merge_degradat(out_dir)` es la consolidacio Python
determinista quan la crida `--consolida` no produeix un `_decisions.json` valid
(despres de `normalize.soft_normalize`).

Nom de fitxer per-document (`{safe_name}.json`) — CRITIC per a la Fase 5 i pel
skill (Fase 0, quan es construeixi): `safe_doc_name(rel_path)` es la SANEJADA
unica que aquest runner espera trobar a `--out` despres de cada crida `--only`.
Si el skill n'escriu un altre nom, `_check_doc_output` cau al fallback per mtime
(§5 de l'enunciat de la Fase 3/4).
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Callable

from automation import g3_templates
from automation.lectura.contract import ALLOWED_FIELD_KEYS, TABLE_ROW_GROUPS, validate_decisions
from automation.lectura.inventory import write_inventory
from automation.lectura.normalize import soft_normalize

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

#: Fitxers de `out_dir` que NO son un `{doc}.json` de lectura (mai comptats
#: com a document, mai candidats a "fallback per mtime").
_RESERVED_JSON_NAMES = {"_inventory.json", "_g3_templates.json", "_decisions.json"}

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9]+")

#: 1 intent + 1 reintent (disseny §5, fila "Retry").
_MAX_ATTEMPTS = 2

_telemetry_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Resultat
# ---------------------------------------------------------------------------


@dataclass
class LecturaResult:
    decisions: dict | None
    per_doc: list[dict] = field(default_factory=list)
    degraded: bool = False
    mode: str = "document"
    telemetry_path: Path | None = None


# ---------------------------------------------------------------------------
# Sanejada del nom de fitxer per-document (documentada al docstring del modul)
# ---------------------------------------------------------------------------


def safe_doc_name(rel_path: str) -> str:
    """Nom de fitxer determinista i llegible per al JSON d'un document.

    Pren el path relatiu SENCER (no nomes el nom de fitxer, perque dos
    documents amb el mateix nom en carpetes diferents, p.ex. "25.0647/tall.pdf"
    i "PDF/ANNEXES/tall.pdf", no col·lideixin), treu l'extensio, substitueix
    qualsevol caracter no alfanumeric per "_", col·lapsa repeticions, treu "_"
    inicial/final, i passa a minuscules.
    """
    p = PurePosixPath(str(rel_path).replace("\\", "/"))
    stem = str(p.with_suffix(""))
    safe = _SAFE_NAME_RE.sub("_", stem).strip("_").lower()
    return safe or "doc"


# ---------------------------------------------------------------------------
# Configuracio (env directe, NO automation.config — Fase 5)
# ---------------------------------------------------------------------------


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _load_config() -> dict[str, Any]:
    mode = os.getenv("G3DT_LECTURA_MODE", "document") or "document"
    if mode not in ("document", "projecte"):
        mode = "document"
    return {
        "claude_path": os.getenv("G3DT_CLAUDE_PATH", "claude") or "claude",
        "timeout": _env_int("G3DT_LECTURA_TIMEOUT", 240),
        "consolida_timeout": _env_int("G3DT_LECTURA_CONSOLIDA_TIMEOUT", 360),
        "concurrency": max(1, _env_int("G3DT_LECTURA_CONCURRENCY", 2)),
        "mode": mode,
    }


# ---------------------------------------------------------------------------
# Utilitats d'I/O (atomiques, utf-8 sempre)
# ---------------------------------------------------------------------------


def _write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=1, default=str)
        os.replace(tmp_name, path)
    except Exception:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
        raise


def _try_load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_telemetry(telemetry_path: Path, entry: dict) -> None:
    line = json.dumps(entry, ensure_ascii=False, default=str)
    with _telemetry_lock:
        telemetry_path.parent.mkdir(parents=True, exist_ok=True)
        with telemetry_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def _emit(on_event: Callable[[str, dict], None] | None, name: str, payload: dict) -> None:
    if on_event is None:
        return
    with contextlib.suppress(Exception):
        on_event(name, payload)


def _cancelled(should_cancel: Callable[[], bool] | None) -> bool:
    if should_cancel is None:
        return False
    with contextlib.suppress(Exception):
        return bool(should_cancel())
    return False


# ---------------------------------------------------------------------------
# Spawn multiplataforma (patro `web/vision_fast.py` / `wizard_service.py`,
# reescrit amb llista d'args -- mai shell=True -- i branca Windows nova)
# ---------------------------------------------------------------------------


def _kill_proc(proc: subprocess.Popen) -> None:
    try:
        if sys.platform == "win32":
            proc.kill()
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, OSError):
        with contextlib.suppress(Exception):
            proc.kill()


def _run_claude(
    *,
    claude_path: str,
    prompt: str,
    timeout: int,
    log_path: Path,
    should_cancel: Callable[[], bool] | None,
) -> dict[str, Any]:
    """Llanca `claude -p PROMPT --permission-mode bypassPermissions` i espera.

    Retorna `{"rc", "timeout", "cancelled", "elapsed_s", "error"?}`. `rc is None`
    vol dir mort per timeout o cancel·lacio (mai penjat: sempre es fa `proc.wait()`
    despres de matar, per no deixar zombis).
    """
    args = [claude_path, "-p", prompt, "--permission-mode", "bypassPermissions"]
    popen_kwargs: dict[str, Any] = {
        "stdin": subprocess.DEVNULL,
        "cwd": str(_PROJECT_ROOT),
    }
    if sys.platform == "win32":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["start_new_session"] = True

    log_path.parent.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    try:
        log_fh = log_path.open("wb")
    except OSError as exc:
        return {"rc": None, "timeout": False, "cancelled": False, "elapsed_s": 0.0, "error": str(exc)}

    try:
        try:
            proc = subprocess.Popen(args, stdout=log_fh, stderr=subprocess.STDOUT, **popen_kwargs)
        except FileNotFoundError:
            return {
                "rc": None, "timeout": False, "cancelled": False, "elapsed_s": 0.0,
                "error": f"claude CLI no trobat (buscat: {claude_path!r})",
            }

        timed_out = False
        cancelled = False
        rc: int | None = None
        while True:
            if _cancelled(should_cancel):
                cancelled = True
                _kill_proc(proc)
                proc.wait()
                break
            try:
                rc = proc.wait(timeout=0.2)
                break
            except subprocess.TimeoutExpired:
                if time.monotonic() - start > timeout:
                    timed_out = True
                    _kill_proc(proc)
                    proc.wait()
                    break
                continue
    finally:
        log_fh.close()

    elapsed = time.monotonic() - start
    return {"rc": rc, "timeout": timed_out, "cancelled": cancelled, "elapsed_s": elapsed}


def _capture_claude_version(claude_path: str) -> str | None:
    """`claude --version`, un cop per crida a `run_lectura`; tolerant a error
    (binari absent, timeout curt) — no bloqueja mai la lectura."""
    try:
        proc = subprocess.run(
            [claude_path, "--version"], capture_output=True, text=True, timeout=10,
        )
        out = (proc.stdout or proc.stderr or "").strip()
        return out or None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Cua per-document (col·lapsant duplicats per md5, disseny §2/§3.2)
# ---------------------------------------------------------------------------


def _build_queue(inventory: dict) -> tuple[list[dict], list[dict]]:
    """Retorna `(cua, saltats_per_duplicat)`: fitxers `route == "claude"`
    ordenats per `priority` (i despres per `path`, per determinisme), amb els
    duplicats (grup md5 de `inventory["duplicates"]`) col·lapsats — nomes la
    copia de path mes curt entra a la cua; la resta surt `skipped_duplicate`.
    """
    claude_files = [f for f in inventory.get("files", []) if f.get("route") == "claude"]
    claude_paths = {f["path"] for f in claude_files}

    skip_paths: set[str] = set()
    for group in inventory.get("duplicates", []):
        members = [p for p in group if p in claude_paths]
        if len(members) <= 1:
            continue
        rep = min(members, key=lambda p: (len(p), p))
        skip_paths.update(p for p in members if p != rep)

    queue_entries = sorted(
        (f for f in claude_files if f["path"] not in skip_paths),
        key=lambda f: (f.get("priority", 0), f["path"]),
    )
    skipped_entries = [f for f in claude_files if f["path"] in skip_paths]
    return queue_entries, skipped_entries


# ---------------------------------------------------------------------------
# Èxit d'una crida --only: el fitxer esperat existeix + parseja + schema_version
# ---------------------------------------------------------------------------


def _check_doc_output(
    expected_path: Path, out_dir: Path, existing_before: set[str], call_start_wall: float, rel_path: str,
) -> tuple[bool, Path | None]:
    data = _try_load_json(expected_path)
    if isinstance(data, dict) and data.get("schema_version") is not None:
        return True, expected_path

    # Fallback (disseny, Fase 3): el skill hauria d'escriure `{safe_doc_name}.json`
    # pero si n'escriu un altre, cerquem un JSON NOU (no hi era abans de la
    # crida, mtime posterior a l'inici) que no sigui un fitxer de servei. Amb
    # concurrencia, aixo NO n'hi ha prou: un altre document processat en
    # paral·lel tambe pot escriure un JSON nou en la mateixa finestra. Exigim
    # que `source_path` del candidat coincideixi amb EL document que estem
    # comprovant (camp obligatori del Pas 4 del skill).
    candidates: list[tuple[float, Path]] = []
    for p in out_dir.glob("*.json"):
        if p.name in _RESERVED_JSON_NAMES or p.name in existing_before:
            continue
        try:
            mtime = p.stat().st_mtime
        except OSError:
            continue
        if mtime < call_start_wall - 1.0:
            continue
        cand_data = _try_load_json(p)
        if (
            isinstance(cand_data, dict)
            and cand_data.get("schema_version") is not None
            and cand_data.get("source_path") == rel_path
        ):
            candidates.append((mtime, p))
    if candidates:
        candidates.sort(key=lambda t: -t[0])
        return True, candidates[0][1]
    return False, None


# ---------------------------------------------------------------------------
# Processament d'UN document (cache -> spawn -> retry)
# ---------------------------------------------------------------------------


def _process_one_doc(
    *,
    entry: dict,
    project_path: Path,
    out_dir: Path,
    inv_path: Path,
    cfg: dict,
    force: bool,
    on_event: Callable[[str, dict], None] | None,
    should_cancel: Callable[[], bool] | None,
    telemetry_path: Path,
    claude_version: str | None,
) -> dict:
    rel_path = entry["path"]
    name = safe_doc_name(rel_path)
    doc_json_path = out_dir / f"{name}.json"

    _emit(on_event, "lectura_doc_inici", {"doc": rel_path})

    if _cancelled(should_cancel):
        return {"doc": rel_path, "status": "cancelled", "attempts": 0, "elapsed_s": 0.0}

    # -- cache-hit (disseny §6): {doc}.json existent + source_md5 coincident --
    if not force and doc_json_path.exists():
        cached = _try_load_json(doc_json_path)
        if isinstance(cached, dict) and cached.get("source_md5") == entry.get("md5"):
            _emit(on_event, "lectura_doc", {"doc": rel_path, "cached": True})
            return {"doc": rel_path, "status": "cached", "attempts": 0, "elapsed_s": 0.0}

    last_elapsed = 0.0
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        if _cancelled(should_cancel):
            return {"doc": rel_path, "status": "cancelled", "attempts": attempt - 1, "elapsed_s": last_elapsed}

        existing_before = {p.name for p in out_dir.glob("*.json")}
        call_start_wall = time.time()
        ts_start = datetime.now().isoformat(timespec="seconds")

        prompt = (
            f"/g3dt-llegir-projecte {project_path} --only {rel_path} "
            f"--inventory {inv_path} --out {out_dir}"
        )
        log_path = Path(tempfile.gettempdir()) / f"g3dt-lectura-{project_path.name}-{name}-{attempt}.log"
        call = _run_claude(
            claude_path=cfg["claude_path"], prompt=prompt, timeout=cfg["timeout"],
            log_path=log_path, should_cancel=should_cancel,
        )
        last_elapsed = call["elapsed_s"]
        ts_end = datetime.now().isoformat(timespec="seconds")

        if call.get("cancelled"):
            _write_telemetry(telemetry_path, {
                "ts_start": ts_start, "ts_end": ts_end, "doc": rel_path, "mode": "only",
                "rc": call["rc"], "timeout": call["timeout"], "json_valid": False,
                "attempt": attempt, "cached": False, "elapsed_s": call["elapsed_s"],
                "log_path": str(log_path), "claude_version": claude_version,
            })
            return {"doc": rel_path, "status": "cancelled", "attempts": attempt, "elapsed_s": last_elapsed}

        json_valid, _found = _check_doc_output(
            doc_json_path, out_dir, existing_before, call_start_wall, rel_path,
        )

        _write_telemetry(telemetry_path, {
            "ts_start": ts_start, "ts_end": ts_end, "doc": rel_path, "mode": "only",
            "rc": call["rc"], "timeout": call["timeout"], "json_valid": json_valid,
            "attempt": attempt, "cached": False, "elapsed_s": call["elapsed_s"],
            "log_path": str(log_path), "claude_version": claude_version,
        })

        if json_valid:
            _emit(on_event, "lectura_doc", {"doc": rel_path, "cached": False, "attempt": attempt})
            return {"doc": rel_path, "status": "ok", "attempts": attempt, "elapsed_s": last_elapsed}

        _emit(on_event, "lectura_doc_error", {
            "doc": rel_path, "attempt": attempt, "rc": call["rc"], "timeout": call["timeout"],
        })

    return {"doc": rel_path, "status": "failed", "attempts": _MAX_ATTEMPTS, "elapsed_s": last_elapsed}


# ---------------------------------------------------------------------------
# Consolidacio (--consolida) + cache + degradat
# ---------------------------------------------------------------------------


def _consolida_cache_valid(out_dir: Path, decisions_path: Path) -> bool:
    """`_decisions.json` es reutilitzable si existeix i cap `{doc}.json` es
    mes nou que ell (disseny §6)."""
    if not decisions_path.exists():
        return False
    decisions_mtime = decisions_path.stat().st_mtime
    for p in out_dir.glob("*.json"):
        if p.name in _RESERVED_JSON_NAMES:
            continue
        try:
            if p.stat().st_mtime > decisions_mtime:
                return False
        except OSError:
            continue
    return True


def _consolidate(
    *,
    project_path: Path,
    out_dir: Path,
    cfg: dict,
    force: bool,
    on_event: Callable[[str, dict], None] | None,
    should_cancel: Callable[[], bool] | None,
    telemetry_path: Path,
    claude_version: str | None,
) -> tuple[dict | None, bool]:
    decisions_path = out_dir / "_decisions.json"

    if not force and _consolida_cache_valid(out_dir, decisions_path):
        cached = _try_load_json(decisions_path)
        if isinstance(cached, dict) and not validate_decisions(cached):
            _emit(on_event, "decisions", {"cached": True})
            return cached, False

    prompt = f"/g3dt-llegir-projecte {project_path} --consolida --out {out_dir}"
    log_path = Path(tempfile.gettempdir()) / f"g3dt-lectura-{project_path.name}-consolida.log"
    ts_start = datetime.now().isoformat(timespec="seconds")
    call = _run_claude(
        claude_path=cfg["claude_path"], prompt=prompt, timeout=cfg["consolida_timeout"],
        log_path=log_path, should_cancel=should_cancel,
    )
    ts_end = datetime.now().isoformat(timespec="seconds")

    raw = _try_load_json(decisions_path)
    json_valid = isinstance(raw, dict)

    _write_telemetry(telemetry_path, {
        "ts_start": ts_start, "ts_end": ts_end, "doc": None, "mode": "consolida",
        "rc": call["rc"], "timeout": call["timeout"], "json_valid": json_valid,
        "attempt": 1, "cached": False, "elapsed_s": call["elapsed_s"],
        "log_path": str(log_path), "claude_version": claude_version,
    })

    if call.get("cancelled"):
        return None, False

    errors: list[str] = []
    normalized: dict | None = None
    if json_valid:
        normalized = soft_normalize(raw)
        errors = validate_decisions(normalized)

    if json_valid and not errors:
        _emit(on_event, "decisions", {"cached": False})
        return normalized, False

    if _cancelled(should_cancel):
        _emit(on_event, "cancelled", {"phase": "pre_merge"})
        return None, False

    _emit(on_event, "consolidacio_fallback", {
        "errors": errors if json_valid else ["_decisions.json invalid o absent"],
    })
    return merge_degradat(out_dir), True


def _run_mode_projecte(
    *,
    project_path: Path,
    out_dir: Path,
    cfg: dict,
    on_event: Callable[[str, dict], None] | None,
    should_cancel: Callable[[], bool] | None,
    telemetry_path: Path,
    claude_version: str | None,
) -> tuple[list[dict], dict | None, bool]:
    """Mode de reserva (disseny §2): UNA sola crida sense `--only`, la forma
    exacta de la lectura d'or. Sense cache propia (no hi ha `{doc}.json` amb
    que comparar el mtime de `_decisions.json`)."""
    decisions_path = out_dir / "_decisions.json"
    prompt = f"/g3dt-llegir-projecte {project_path} --out {out_dir}"
    log_path = Path(tempfile.gettempdir()) / f"g3dt-lectura-{project_path.name}-projecte.log"
    ts_start = datetime.now().isoformat(timespec="seconds")
    call = _run_claude(
        claude_path=cfg["claude_path"], prompt=prompt, timeout=cfg["consolida_timeout"],
        log_path=log_path, should_cancel=should_cancel,
    )
    ts_end = datetime.now().isoformat(timespec="seconds")

    raw = _try_load_json(decisions_path)
    json_valid = isinstance(raw, dict)

    _write_telemetry(telemetry_path, {
        "ts_start": ts_start, "ts_end": ts_end, "doc": None, "mode": "projecte",
        "rc": call["rc"], "timeout": call["timeout"], "json_valid": json_valid,
        "attempt": 1, "cached": False, "elapsed_s": call["elapsed_s"],
        "log_path": str(log_path), "claude_version": claude_version,
    })

    status = "cancelled" if call.get("cancelled") else ("ok" if json_valid else "failed")
    per_doc = [{"doc": "(projecte sencer)", "status": status, "attempts": 1, "elapsed_s": call["elapsed_s"]}]

    if call.get("cancelled"):
        return per_doc, None, False

    if not json_valid:
        _emit(on_event, "consolidacio_fallback", {"errors": ["_decisions.json invalid o absent (mode projecte)"]})
        return per_doc, merge_degradat(out_dir), True

    normalized = soft_normalize(raw)
    errors = validate_decisions(normalized)
    if errors:
        _emit(on_event, "consolidacio_fallback", {"errors": errors})
        return per_doc, merge_degradat(out_dir), True

    _emit(on_event, "decisions", {"cached": False})
    return per_doc, normalized, False


# ---------------------------------------------------------------------------
# Fase 4 — merge_degradat: consolidacio Python determinista (fallback)
# ---------------------------------------------------------------------------


def merge_degradat(out_dir: Path) -> dict:
    """Consolidacio Python determinista quan `--consolida` no produeix un
    `_decisions.json` valid (despres de `soft_normalize`). Llegeix
    `_g3_templates.json` + tots els `{doc}.json` de `out_dir` (Pas 4 del
    skill: bloc `tier_a`).

    Deliberadament caut (disseny Fase 4): NOMES un camp de les 22 claus planes
    alimentat EXCLUSIVAMENT per senyals de `_g3_templates.json` amb
    `confidence >= 0.9` i sense contradiccio de valor pot ser `segur`.
    Qualsevol altra combinacio (algun senyal ve d'un `{doc}.json` de claude,
    hi ha contradiccio, o la confianca es < 0.9) es `candidats`. Sense cap
    senyal → `no_trobat`. Els blocs de `tables` s'emeten en la forma canonica
    buida (Pas 4 del skill / §4.3 regla b del contracte): no s'intenta
    reconstruir files de taula sense una consolidacio real.

    La sortida ha de passar `contract.validate_decisions` NET.
    """
    docs_read: list[str] = []
    signals_by_concept: dict[str, list[dict]] = {}

    g3_path = out_dir / "_g3_templates.json"
    if g3_path.exists():
        g3_data = _try_load_json(g3_path) or {}
        docs_read.append(g3_path.name)
        for concept_id, cands in (g3_data.get("concepts") or {}).items():
            for c in cands if isinstance(cands, list) else []:
                if not isinstance(c, dict):
                    continue
                signals_by_concept.setdefault(concept_id, []).append({
                    "value": c.get("value"),
                    "font": f"{c.get('source', '?')} {c.get('location', '')}".strip(),
                    "quote": c.get("quote", ""),
                    "confidence": c.get("confidence", 0.0) or 0.0,
                    "origin": "g3_templates",
                })

    for p in sorted(out_dir.glob("*.json")):
        if p.name in _RESERVED_JSON_NAMES:
            continue
        data = _try_load_json(p)
        if not isinstance(data, dict):
            continue
        docs_read.append(p.name)
        source_path = data.get("source_path", p.stem)
        for entry in data.get("tier_a", []) or []:
            if not isinstance(entry, dict):
                continue
            concept_id = entry.get("concept_id")
            if not concept_id:
                continue
            location = entry.get("location", "")
            signals_by_concept.setdefault(concept_id, []).append({
                "value": entry.get("value"),
                "font": f"{source_path} {location}".strip(),
                "quote": entry.get("quote", ""),
                "confidence": entry.get("confidence", 0.0) or 0.0,
                "origin": "claude",
            })

    sources_checked = docs_read or ["cap document llegit (mode degradat)"]

    fields_out: dict[str, Any] = {}
    for key in sorted(ALLOWED_FIELD_KEYS):
        fields_out[key] = _decide_field_degradat(signals_by_concept.get(key, []), sources_checked)

    tables_out: dict[str, Any] = {}
    for table_name in TABLE_ROW_GROUPS:
        tables_out[table_name] = {
            "estat_bloc": "no_trobat",
            "rows": [],
            "sources_checked": sources_checked,
        }
    tables_out["superficie_construida"] = {
        "estat": "no_trobat",
        "value": None,
        "candidates": [],
        "sources_checked": sources_checked,
    }

    project_name = out_dir.name
    if out_dir.name == "lectura" and out_dir.parent.name == "validation":
        project_name = out_dir.parent.parent.name

    return {
        "schema_version": 1,
        "project": project_name,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "skill_version": "degradat",
        "fields": fields_out,
        "tables": tables_out,
        "sources_read": docs_read,
        "notes_estructurals": [
            "_decisions.json generat en mode degradat (consolidacio claude invalida o absent, "
            "merge_degradat determinista sobre els {doc}.json + _g3_templates.json)",
        ],
    }


def _decide_field_degradat(sigs: list[dict], sources_checked: list[str]) -> dict:
    if not sigs:
        return {"estat": "no_trobat", "value": None, "sources_checked": sources_checked}

    only_g3 = all(s["origin"] == "g3_templates" for s in sigs)
    high_conf = all(s["confidence"] >= 0.9 for s in sigs)
    no_contradiction = len({s["value"] for s in sigs}) <= 1

    ordered = sorted(sigs, key=lambda s: -s["confidence"])[:3]
    candidates = [{"value": s["value"], "font": s["font"], "quote": s["quote"]} for s in ordered]

    if only_g3 and high_conf and no_contradiction:
        return {
            "estat": "segur",
            "value": candidates[0]["value"],
            "candidates": candidates,
            "rule": "mode degradat: unica font g3_templates, confianca >= 0.9, sense contradiccio",
        }

    return {
        "estat": "candidats",
        "value": candidates[0]["value"],
        "candidates": candidates,
        "rule": "mode degradat: multi-font, confianca < 0.9, o contradiccio de valor",
    }


# ---------------------------------------------------------------------------
# Agregat per a l'event `lectura_fi`
# ---------------------------------------------------------------------------


def _aggregate(per_doc: list[dict], degraded: bool) -> dict:
    by_status: dict[str, int] = {}
    total_elapsed = 0.0
    for d in per_doc:
        by_status[d["status"]] = by_status.get(d["status"], 0) + 1
        total_elapsed += d.get("elapsed_s", 0.0)
    return {"n_docs": len(per_doc), "by_status": by_status, "elapsed_s_total": total_elapsed, "degraded": degraded}


# ---------------------------------------------------------------------------
# Punt d'entrada public
# ---------------------------------------------------------------------------


def run_lectura(
    project_path: Path,
    *,
    out_dir: Path | None = None,
    on_event: Callable[[str, dict], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
    force: bool = False,
) -> LecturaResult:
    """Orquestra la lectura headless d'un projecte (disseny §2, TEMPS 2 +
    CONSOLIDACIO). Mai crida `automation.auto_extractor` ni `web/vision_*`
    (TEMPS 1 / via B): aixo es responsabilitat de la Fase 5 (`web/lectura_service.py`).

    Checkpoints de cancel·lacio (disseny §2): abans de comencar, post-inventari,
    entre documents (cada worker comprova abans de fer spawn) i pre-consolidacio/
    pre-merge. En cancel·lar, mata els processos vius (via el bucle de
    `_run_claude`) i retorna un resultat PARCIAL amb `decisions=None`.
    """
    project_path = Path(project_path)
    out_dir = Path(out_dir) if out_dir is not None else project_path / "validation" / "lectura"
    out_dir.mkdir(parents=True, exist_ok=True)
    telemetry_path = out_dir / "_telemetry.jsonl"

    cfg = _load_config()
    mode = cfg["mode"]
    claude_version = _capture_claude_version(cfg["claude_path"])

    if _cancelled(should_cancel):
        _emit(on_event, "cancelled", {"phase": "start"})
        return LecturaResult(decisions=None, per_doc=[], degraded=False, mode=mode, telemetry_path=telemetry_path)

    # -- 1/2: inventari + g3_templates (disseny §2, "c" i g3_templates part de "a") --
    inv_path = write_inventory(project_path, out_dir)
    inventory = json.loads(inv_path.read_text(encoding="utf-8"))
    _emit(on_event, "lectura_inventari", {"n_files": len(inventory.get("files", []))})

    g3_result = g3_templates.read_project(project_path)
    _write_json_atomic(out_dir / "_g3_templates.json", g3_result)
    _emit(on_event, "templates_fields", {"n_documents": len(g3_result.get("documents", []))})

    if _cancelled(should_cancel):
        _emit(on_event, "cancelled", {"phase": "post_inventari"})
        return LecturaResult(decisions=None, per_doc=[], degraded=False, mode=mode, telemetry_path=telemetry_path)

    if mode == "projecte":
        per_doc, decisions, degraded = _run_mode_projecte(
            project_path=project_path, out_dir=out_dir, cfg=cfg,
            on_event=on_event, should_cancel=should_cancel,
            telemetry_path=telemetry_path, claude_version=claude_version,
        )
        _emit(on_event, "lectura_fi", _aggregate(per_doc, degraded))
        return LecturaResult(decisions=decisions, per_doc=per_doc, degraded=degraded, mode=mode, telemetry_path=telemetry_path)

    # -- mode "document" ----------------------------------------------------
    queue_entries, skipped_entries = _build_queue(inventory)

    per_doc: list[dict] = []
    for entry in skipped_entries:
        per_doc.append({"doc": entry["path"], "status": "skipped_duplicate", "attempts": 0, "elapsed_s": 0.0})
        _emit(on_event, "lectura_doc", {"doc": entry["path"], "skipped_duplicate": True})

    n_python = sum(1 for f in inventory.get("files", []) if f.get("route") == "python")
    _emit(on_event, "lectura_inici", {
        "n_claude": len(queue_entries), "n_python": n_python,
        "docs": [f["path"] for f in queue_entries],
    })

    if _cancelled(should_cancel):
        for entry in queue_entries:
            per_doc.append({"doc": entry["path"], "status": "cancelled", "attempts": 0, "elapsed_s": 0.0})
    elif queue_entries:
        with ThreadPoolExecutor(max_workers=cfg["concurrency"]) as executor:
            futures = {
                executor.submit(
                    _process_one_doc,
                    entry=entry, project_path=project_path, out_dir=out_dir, inv_path=inv_path,
                    cfg=cfg, force=force, on_event=on_event, should_cancel=should_cancel,
                    telemetry_path=telemetry_path, claude_version=claude_version,
                ): entry
                for entry in queue_entries
            }
            for fut in as_completed(futures):
                per_doc.append(fut.result())

    was_cancelled = _cancelled(should_cancel) or any(d["status"] == "cancelled" for d in per_doc)
    if was_cancelled:
        _emit(on_event, "cancelled", {"phase": "documents"})
        return LecturaResult(decisions=None, per_doc=per_doc, degraded=False, mode=mode, telemetry_path=telemetry_path)

    decisions, degraded = _consolidate(
        project_path=project_path, out_dir=out_dir, cfg=cfg, force=force,
        on_event=on_event, should_cancel=should_cancel,
        telemetry_path=telemetry_path, claude_version=claude_version,
    )

    _emit(on_event, "lectura_fi", _aggregate(per_doc, degraded))
    return LecturaResult(decisions=decisions, per_doc=per_doc, degraded=degraded, mode=mode, telemetry_path=telemetry_path)
