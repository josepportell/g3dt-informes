"""Fase 5+6 (via A, wizard headless) — servei + endpoint SSE.

Orquestra la lectura headless (`automation/lectura/runner.run_lectura`) EN
PARAL·LEL amb `auto_extract` (via B / Python determinista — DPSH, lab, ICGC,
Cadastre, geocode), consolida les decisions i sobreescriu els camps del
wizard amb el resultat (Fase 6: merge → camps wizard).

Vegeu `docs/DISSENY-WIZARD-HEADLESS-CANDIDATS-2026-08-24.md` §2 (seqüència
SSE en 2 temps + consolidació), §7 (fallback i telemetria), §8.3 (mapping
decisions→wizard) i §9 Fases 5-6 (aquest mòdul); i el vocabulari d'events
de `automation/lectura/runner.py` (`lectura_inici`, `lectura_doc_inici`,
`lectura_doc`, `lectura_doc_error`, `consolidacio_inici`,
`consolidacio_fallback`, `decisions`, `lectura_fi`, `cancelled`).

Patró SSE de referència (NO tocat): `web/wizard_service.get_prefills_streaming`
+ endpoint `web/api.py::prefills_stream` (via B).

Aquest mòdul és NOU: NOMÉS lectura de `automation/lectura/` (contract.py,
inventory.py, runner.py, normalize.py) — cap edició. Les úniques tres
edicions "quirúrgiques" permeses viuen a `web/wizard_service.py`
(`_merge_prefills(..., skip_vision=...)`), `web/api.py` (guard +
endpoint) i `automation/config.py` (flag `G3DT_USE_LECTURA_HEADLESS`).

Complement del coordinador (2026-08-24): el runner (`automation/lectura/runner.py`)
NOMÉS emet marcadors — `templates_fields` amb `{n_documents}` i `decisions` amb
`{cached}` — cap dels dos porta el payload que la UI necessita per pintar
candidats/quotes. Aquest servei injecta DOS events propis amb el payload
enriquit (§1/§2 més avall) i, per no col·lidir de nom amb els marcadors del
runner, els reenvia sota un nom diferent, DOCUMENTAT:

    runner "templates_fields" {n_documents}  -> "lectura_templates_marker"
    runner "decisions"        {cached}       -> "lectura_decisions_marker"

Els events propis d'aquest servei es diuen "templates_fields" i "decisions"
(sense el prefix "lectura_") — són els que la UI ha de consumir per al
payload real.

Fase 10 (2026-08-25, annex `docs/DISSENY-ANNEX-TRES-BOTONS-JOBS-NOTIFICACIONS-
2026-08-24.md` §3): el cos del pipeline (fils A+B, merge Fase 6) viu ara a
`run_lectura_job()`, que parla amb un `emit(event_type, detail)` en lloc de
`yield` — és el `target` que `automation.lectura.jobs.JobRegistry.start()`
corre en un fil propi, amb estat persistent a `validation/lectura/_job.json`
(un sol job viu per projecte). `get_lectura_streaming()` ja no executa el
pipeline directament: arrenca (o s'enganxa a) un `Job` via
`start_or_attach_job()`/`registry.live()` i es limita a fer de subscriptor
SSE (`Job.subscribe()`), que reemet en ordre l'historial + els events en
viu. La seqüència d'events que rep un client que ARRENCA el job és
IDÈNTICA a la d'abans de la Fase 10 (mateixos noms, mateix ordre).
"""

from __future__ import annotations

import json
import logging
import os
import queue
import shutil
import threading
from pathlib import Path
from typing import Any, Callable

from automation.lectura.jobs import Job, registry
from automation.lectura.runner import LecturaResult, run_lectura
from web import wizard_service
from web.wizard_service import (
    _clear_stale_user_data,
    _merge_prefills,
    _resolve_project,
    clear_cancellation,
    is_cancelled,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Mapping decisions -> camps del wizard (disseny §8.3, Fase 6)
# ---------------------------------------------------------------------------
#
# Confirmat via grep de `templates/validation/review.html` (`id="src-…"`, mai
# editat) i de les claus REALS que `web/wizard_service.py` escriu a `merged`
# (`_merge_prefills` i els seus helpers `_compute_*`). `None` = cap clau de
# wizard confirmada amb aquest nom: la decisió NO es fusiona — viatja
# igualment dins el payload `_lectura` de l'event `prefills` (§ més avall),
# perquè una futura UI (Fase 7) hi pugui accedir encara que no hi hagi un
# input del wizard per mostrar-la directament.
MAPPING_DECISIONS_WIZARD: dict[str, str | None] = {
    # -- Confirmats (grep `id="src-…"` de review.html) -----------------------
    "client_name": "client_name",
    "street_address": "street_address",
    "municipality": "site_municipality",
    "architect_name": "architect_name",
    "architect_company": "architect_company",
    "building_type": "building_type",
    "num_floors": "num_floors",
    "superficie_parcela": "superficie_parcela_m2",
    "cota_referencia": "cota_referencia",
    "num_soil_levels": "num_soil_levels",
    "utm_x": "utm_x",
    "utm_y": "utm_y",
    # -- Confirmats (grep de claus REALS de `merged`, no tenen source-badge --
    # -- pròpia al wizard perquè no viuen a `WIZARD_FIELDS`, però la clau
    # -- de `merged` existeix i té el MATEIX nom): auto_extractor.py
    # -- `_phase2_lab_results` (L.1279-1291) escriu directament
    # -- `result.prefills['lab_testing_company'|'lab_sample_id'|'lab_depth'|
    # -- 'lab_location']`, que `_merge_prefills` bolca tal qual a `merged`.
    "lab_testing_company": "lab_testing_company",
    "lab_sample_id": "lab_sample_id",
    "lab_depth": "lab_depth",
    "lab_location": "lab_location",
    # -- Trobats, PERÒ amb una advertència (documentada, no resolta aquí): --
    # `merged['cte_edificacio']`/`merged['cte_sol']` EXISTEIXEN
    # (wizard_service._compute_lookup_prefills, ~L.1032/1051) però avui són
    # un LOOKUP determinista (building_type+num_floors / N20 mitjà), NO una
    # lectura de document. El disseny §8.3 posa "lectura segur" per damunt
    # de "via B/auto_extract" a la precedència, així que es mapa seguint
    # aquesta precedència — però si val la pena que la lectura d'un document
    # (quan en digui alguna cosa) trepitgi el càlcul determinista és una
    # decisió de producte pendent de Josep/Fase 7, no una decisió tècnica
    # d'aquest mòdul.
    "cte_edificacio": "cte_edificacio",
    "cte_sol": "cte_sol",
    # -- NO trobats: cap clau de wizard amb aquest nom exacte -----------------
    # `expedient`: EXCLÒS explícitament dels prefills del wizard
    # (automation/wizard.py::_load_docs_intel, comentari "Skip expedient:
    # pressupost documents reference the budget number..."). La clau
    # `'expedient'` que sí existeix a `web/wizard_service.py:133` és la del
    # dropdown de `list_projects()` (funció diferent, mai arriba a `merged`).
    "expedient": None,
    # `field_date`: `merged` només té `field_work_dates` (llista) i
    # `field_work_dates_text` (frase ja formatada en català/castellà) —
    # semàntica diferent (llista de dates vs data única): no es força la
    # coincidència de nom.
    "field_date": None,
    # `num_dpsh_tests`: la clau EXISTEIX a `merged`
    # (wizard_service._compute_narrative_prefills, ~L.951/958) però hi conté
    # una FRASE narrativa ja formatada per al wizard ("3 assaigs de
    # penetració dinàmica tipus DPSH (veure annex…)"), no un enter/recompte
    # cru com el que produirà la lectura. Sobreescriure-la amb
    # `decision["value"]` trencaria la frase sense cap pas de reformatat —
    # EXCLÒS deliberadament (erroni-amb-confiança=0). El valor de la lectura
    # hi és igualment, dins `_lectura`.
    "num_dpsh_tests": None,
    # `referencia_catastral`: cap ocurrència enlloc del codebase (ni prefill,
    # ni WIZARD_FIELDS, ni report_generator) — no hi ha clau amb què comparar.
    "referencia_catastral": None,
}

#: Valors REALS de `source` que `save_wizard`/`_load_existing_user_data`
#: (`web/wizard_service.py::save_wizard`, `automation/wizard.py::
#: _load_existing_user_data`) deixen a `merged[...]['source']` quan el valor
#: ve d'una decisió d'Eva desada a `user_data.json`: `'user'` (camp que Eva
#: ha canviat explícitament aquesta sessió — `save_wizard`'s `_is_changed`) i
#: `'user_data.json anterior'` (fallback quan es carrega un `user_data.json`
#: previ sense `_sources` explícit per aquest camp). Totes dues són
#: intocables: la lectura MAI les sobreescriu (disseny §8.3, "user_data
#: mana sempre").
_INTOCABLE_SOURCES = frozenset({"user", "user_data.json anterior"})


def _apply_lectura_overlay(merged: dict[str, Any], decisions: dict[str, Any]) -> None:
    """Fase 6 — sobreescriu `merged` amb les decisions escalars (`fields`),
    seguint la precedència del disseny §8.3: `user_data` (Eva mana sempre) >
    lectura `segur` > lectura candidat-1 (marcat `lectura_candidats`) >
    via B/auto_extract > defecte. Muta `merged` in place.

    `no_trobat` MAI escriu valor (regla 4 del contracte, §4.3). Un camp de
    `MAPPING_DECISIONS_WIZARD` amb `wizard_key is None` mai toca `merged`
    (viu només al payload `_lectura`).
    """
    fields = decisions.get("fields") if isinstance(decisions, dict) else None
    if not isinstance(fields, dict):
        return

    for decision_key, wizard_key in MAPPING_DECISIONS_WIZARD.items():
        if wizard_key is None:
            continue
        cell = fields.get(decision_key)
        if not isinstance(cell, dict):
            continue

        existing = merged.get(wizard_key)
        existing_source = existing.get("source") if isinstance(existing, dict) else None
        if existing_source in _INTOCABLE_SOURCES:
            continue  # Eva mana sempre — mai sobreescrit per la lectura.

        estat = cell.get("estat")
        if estat == "segur":
            merged[wizard_key] = {"value": cell.get("value"), "source": "lectura"}
        elif estat == "candidats":
            candidates = cell.get("candidates") or []
            if candidates and isinstance(candidates[0], dict):
                merged[wizard_key] = {
                    "value": candidates[0].get("value"),
                    "source": "lectura_candidats",
                }
        # "no_trobat" -> mai escriu valor (regla 4, §4.3).


# ---------------------------------------------------------------------------
# `_g3_templates.json` -> payload "templates_fields" (millor senyal/concepte)
# ---------------------------------------------------------------------------


def _best_g3_templates_payload(out_dir: Path) -> dict[str, dict[str, Any]] | None:
    """Llegeix `{out_dir}/_g3_templates.json` (ja escrit pel runner ABANS
    de l'event `lectura_inici` — disseny §2 TEMPS 1, `runner.run_lectura`
    l'escriu abans de construir la cua) i retorna, per concepte, NOMÉS el
    millor senyal: `concepts[cid][0]` — `g3_templates.read_project()` ja els
    deixa ordenats best-first (document_type→mod_date→confidence, vegeu
    `automation/g3_templates.py::read_project`).

    Retorna `None` si el fitxer encara no existeix o és il·legible (el
    caller reintenta al primer `lectura_doc_inici`).
    """
    path = out_dir / "_g3_templates.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    concepts = data.get("concepts") if isinstance(data, dict) else None
    if not isinstance(concepts, dict):
        return None

    payload: dict[str, dict[str, Any]] = {}
    for concept_id, candidates in concepts.items():
        if not isinstance(candidates, list) or not candidates:
            continue
        best = candidates[0]
        if not isinstance(best, dict):
            continue
        payload[concept_id] = {
            "value": best.get("value"),
            "location": best.get("location"),
            "quote": best.get("quote"),
            "confidence": best.get("confidence"),
        }
    return payload


def _lectura_payload(result: LecturaResult) -> dict[str, Any]:
    """Forma compartida entre l'event SSE `decisions` (payload sencer,
    complement del coordinador punt 2) i la clau `_lectura` de l'event final
    `prefills` (disseny §9 Fase 6)."""
    return {
        "decisions": result.decisions,
        "degraded": result.degraded,
        "per_doc": result.per_doc,
    }


# ---------------------------------------------------------------------------
# Cos del job (Fase 10): abans era el cos del generator, ara parla amb
# `emit(event_type, detail)` en lloc de `yield` — és el `target` que
# `JobRegistry.start()` corre en un fil propi (`web/api.py` no en sap res).
# ---------------------------------------------------------------------------


def run_lectura_job(
    project_name: str,
    project_path: Path,
    emit: Callable[[str, dict], None],
    should_cancel: Callable[[], bool],
) -> None:
    """TEMPS 1 (g3_templates + auto_extract, en paral·lel amb TEMPS 2) +
    TEMPS 2 (lectura headless `claude -p`) + merge final (Fase 6). Idèntic al
    pipeline d'abans de la Fase 10 (mateixos events, mateix ordre relatiu),
    però parla amb `emit()` en lloc de `yield` SSE.

    Fallback de servei (disseny §7, punt 1): si `claude` no es troba al PATH
    (`shutil.which`) o `run_lectura` peta amb excepció, emet
    `lectura_fallback {reason}` i segueix el camí via B COMPLET — crida
    `_merge_prefills` SENSE `skip_vision` (comportament d'avui, cap
    regressió). Si `run_lectura` retorna degradat (`result.degraded=True`)
    amb `decisions` vàlides, NO és fallback: continua normal (disseny §7).

    Acaba SEMPRE amb exactament un event terminal: `prefills`, `cancelled`
    o `error_event` — el registre de jobs (`automation.lectura.jobs.Job`)
    en depèn per marcar l'estat com a terminal.
    """
    _clear_stale_user_data(project_path)
    clear_cancellation(project_name)

    out_dir = project_path / "validation" / "lectura"

    event_queue: queue.Queue = queue.Queue()
    auto_result_holder: list = []
    auto_error_holder: list = []
    lectura_result_holder: list[LecturaResult] = []

    templates_state = {"emitted": False}

    def _try_emit_templates_fields() -> None:
        if templates_state["emitted"]:
            return
        payload = _best_g3_templates_payload(out_dir)
        if payload is None:
            return
        templates_state["emitted"] = True
        event_queue.put(("templates_fields", payload))

    # -- Fil A: auto_extract (via B / Python determinista, TEMPS 1) ---------
    def auto_progress_cb(event_type: str, detail: dict) -> None:
        event_queue.put((event_type, detail))

    def run_extract() -> None:
        try:
            from automation.auto_extractor import auto_extract
            result = auto_extract(project_path, on_progress=auto_progress_cb)
            auto_result_holder.append(result)
        except Exception as exc:
            auto_error_holder.append(exc)
        finally:
            event_queue.put(None)  # sentinella A

    # -- Fil B: lectura headless (`claude -p`, TEMPS 2 + consolidació) ------
    def lectura_event_cb(event_type: str, detail: dict) -> None:
        # Vegeu la capçalera del mòdul: el runner NOMÉS emet marcadors —
        # es reenvien sota un nom diferent perquè no col·lideixin amb els
        # events enriquits que aquest servei injecta amb el mateix nom base.
        if event_type == "templates_fields":
            event_queue.put(("lectura_templates_marker", detail))
            return
        if event_type == "decisions":
            event_queue.put(("lectura_decisions_marker", detail))
            return
        event_queue.put((event_type, detail))
        if event_type in ("lectura_inici", "lectura_doc_inici"):
            # `_g3_templates.json` ja hi hauria de ser en rebre `lectura_inici`
            # (el runner l'escriu abans de construir la cua). Si per algun
            # motiu encara no hi és, es reintenta en rebre el primer
            # `lectura_doc_inici` (complement del coordinador, punt 1).
            _try_emit_templates_fields()

    def run_lectura_phase() -> None:
        try:
            claude_bin = os.getenv("G3DT_CLAUDE_PATH", "claude") or "claude"
            if shutil.which(claude_bin) is None:
                event_queue.put(("lectura_fallback", {"reason": "claude_not_found"}))
                return
            result = run_lectura(
                project_path, out_dir=out_dir, on_event=lectura_event_cb,
                should_cancel=should_cancel,
            )
            lectura_result_holder.append(result)
            if result.decisions is not None:
                event_queue.put(("decisions", _lectura_payload(result)))
        except Exception as exc:
            logger.exception("Lectura headless failed for %s", project_name)
            event_queue.put(("lectura_fallback", {"reason": "exception", "detail": str(exc)}))
        finally:
            event_queue.put(None)  # sentinella B

    thread_a = threading.Thread(target=run_extract, daemon=True)
    thread_b = threading.Thread(target=run_lectura_phase, daemon=True)
    thread_a.start()
    thread_b.start()

    # Un sol bucle consumidor amb DOS sentinelles (un per fil): els events
    # de tots dos s'emeten a mesura que arriben (disseny §2).
    sentinels_seen = 0
    cancelled_flag = False
    while sentinels_seen < 2:
        item = event_queue.get()
        if item is None:
            sentinels_seen += 1
            continue
        if not cancelled_flag and should_cancel():
            cancelled_flag = True
        if cancelled_flag:
            continue  # esgota la cua sense emetre, fins als 2 sentinelles
        event_type, detail = item
        emit(event_type, detail)

    thread_a.join()
    thread_b.join()

    if cancelled_flag:
        emit("cancelled", {"phase": "lectura"})
        return

    if auto_error_holder:
        emit("error_event", {"message": str(auto_error_holder[0])})
        return

    if not auto_result_holder:
        emit("error_event", {"message": "Extraction ended without result"})
        return

    # Checkpoint pre-merge (disseny §2/§7): si Eva ha aturat just entre el
    # buidat de les cues i el merge, ens estalviem el merge sencer.
    if should_cancel():
        emit("cancelled", {"phase": "pre_merge"})
        return

    auto_result = auto_result_holder[0]
    lectura_result = lectura_result_holder[0] if lectura_result_holder else None
    has_lectura = bool(lectura_result and lectura_result.decisions is not None)

    try:
        # Fase 6: `skip_vision` NOMÉS quan la lectura ha produït decisions
        # (disseny §9 Fase 6) — si ha caigut a fallback, `_merge_prefills`
        # corre amb el seu comportament d'avui (via B sencera, cap regressió).
        merged = _merge_prefills(project_name, project_path, auto_result, skip_vision=has_lectura)

        if has_lectura:
            payload = _lectura_payload(lectura_result)
            # Wrapping {value, source} per coherència amb la resta de claus
            # de sistema de `merged` (`_vision_status`, `_concept_map`,
            # `_missing_summary`, …) — decisió d'aquest mòdul, no fixada pel
            # disseny; la Fase 7 (UI) hi pot llegir `merged['_lectura']['value']`.
            merged["_lectura"] = {"value": payload, "source": "system"}
            _apply_lectura_overlay(merged, lectura_result.decisions)
        # Fallback (has_lectura=False): NO s'afegeix `_lectura` — `merged` és
        # exactament el que via B produiria avui (forma triada, disseny §7).

        emit("prefills", merged)
    except Exception as exc:
        logger.exception("Error merging lectura prefills for streaming")
        emit("error_event", {"message": str(exc)})


# ---------------------------------------------------------------------------
# Wiring del job (Fase 10): resol el projecte, crea/enganxa un `Job` al
# `JobRegistry` singleton.
# ---------------------------------------------------------------------------


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _jobs_root() -> Path:
    """Arrel contra la qual `_resolve_project` resol (dev: `reference-material/`;
    xarxa: workspace local) — coherent perquè `list_jobs()` escanegi el mateix
    arbre on viuen els `_job.json`. NOTA: es llegeix `wizard_service._REF_DIR`
    dinàmicament (no importat com a valor a l'inici del mòdul) perquè els
    tests el reassignen via `monkeypatch.setattr(wizard_service, "_REF_DIR", ...)`.
    """
    return wizard_service._REF_DIR


def start_or_attach_job(project_name: str, button: str = "desde_zero") -> tuple[Job, bool]:
    """Arrenca un job de lectura per a `project_name`, o s'hi enganxa si ja
    n'hi ha un de viu (disseny §3.4: un job viu per projecte — mai dos
    `run_lectura` alhora)."""
    project_path = _resolve_project(project_name)
    concurrency = _env_int("G3DT_LECTURA_CONCURRENCY", 2)

    def _telemetry_paths_fn() -> list[Path]:
        return sorted(_jobs_root().glob("*/validation/lectura/_telemetry.jsonl"))

    def _target(job: Job) -> None:
        run_lectura_job(project_name, project_path, job.emit, lambda: is_cancelled(project_name))

    return registry.start(
        project_name, project_path, button, _target,
        concurrency=concurrency, telemetry_paths_fn=_telemetry_paths_fn,
    )


def list_jobs() -> list[dict[str, Any]]:
    """Taula d'estat dels jobs (disseny §5.2): vius primer, després
    `updated_at` desc, últims 30 dies."""
    return registry.list_jobs(_jobs_root())


# ---------------------------------------------------------------------------
# Generator SSE (endpoint `GET /api/lectura-stream/{p}`, web/api.py)
# ---------------------------------------------------------------------------


def get_lectura_streaming(project_name: str, *, attach: bool = False):
    """Generator SSE: subscriptor d'un `Job` (Fase 10) — NO executa el
    pipeline directament, es limita a reemetre l'historial + els events en
    viu d'un `Job` (`automation.lectura.jobs.Job.subscribe()`).

    `attach=False` (per defecte): arrenca un job nou o s'enganxa a un de viu
    (`start_or_attach_job`) — la seqüència d'events per a un client que
    ARRENCA el job és IDÈNTICA a la d'abans de la Fase 10.

    `attach=True`: només subscriu a un job JA viu (§5.2, "Eva torna i clica
    la fila"); si no n'hi ha cap, emet un únic `error_event` i acaba.
    """
    if attach:
        job = registry.live(project_name)
        if job is None:
            yield (
                "event: error_event\n"
                f"data: {json.dumps({'message': 'cap job viu per a aquest projecte'}, ensure_ascii=False)}\n\n"
            )
            return
    else:
        job, _created = start_or_attach_job(project_name)

    q = job.subscribe()
    try:
        while True:
            event_type, detail = q.get()
            yield f"event: {event_type}\ndata: {json.dumps(detail, ensure_ascii=False)}\n\n"
            if event_type in ("prefills", "cancelled", "error_event"):
                break
    finally:
        job.unsubscribe(q)
