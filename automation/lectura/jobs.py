"""Fase 10 (via A, tres botons) — registre de jobs de lectura a disc.

Separa l'EXECUCIÓ del job (fil propi, estat persistent a
`validation/lectura/_job.json`, un sol job viu per projecte) de
l'STREAMING SSE (un subscriptor que pot arribar tard i "enganxar-se").

Vegeu `docs/DISSENY-ANNEX-TRES-BOTONS-JOBS-NOTIFICACIONS-2026-08-24.md` §3
(registre de jobs, format `_job.json` §3.2, estats §3.3, transicions §3.4).

Mòdul autocontingut: NO depèn de `web/` (perquè sigui testable sol). El
productor d'events (el target passat a `JobRegistry.start`) crida
`Job.emit(event_type, detail)` amb el MATEIX vocabulari d'events que
`automation.lectura.runner.run_lectura` + els events propis que
`web/lectura_service.py` injecta (`templates_fields`, `decisions` amb
payload enriquit, `lectura_templates_marker`, `lectura_decisions_marker`,
`lectura_fallback`, `prefills`, `error_event`).

Nota de disseny (decisió d'aquest mòdul, no fixada pel disseny): l'event
propi "decisions" (payload sencer, injectat per `lectura_service` DESPRÉS
que `run_lectura` ja hagi emès `lectura_fi`) NO es mapeja a l'estat
`consolidating` — només ho fa `lectura_decisions_marker` (el marcador
renombrat del runner, que sempre arriba ABANS de `lectura_fi`). Mapejar
també "decisions" faria retrocedir l'estat de `merging` a `consolidating`
just abans de `ready`, cosa que la taula d'estat (disseny §5.2) mostraria
com un pas enrere. També s'afegeix `consolidacio_fallback` (consolidació
Python degradada, sense `_decisions.json` vàlid) a `consolidating`, perquè
el runner no emet cap `decisions`/`lectura_decisions_marker` en aquest cas
i l'estat es quedaria erròniament a `reading` fins a `lectura_fi`.

Segona decisió: a l'event `prefills`, es conserva el `result.fallback` que
un event previ `lectura_fallback` hagi anotat (en lloc del `null` fix que
descriu l'exemple del disseny) — perdre aquesta informació semblava un
overxit, no una decisió deliberada; documentat aquí i a l'informe final.

Tercera decisió: `Job.emit()` escriu `_job.json` a disc ABANS de repartir
l'event als subscriptors (no simultàniament ni després). Així, un
subscriptor SSE que acaba de rebre l'event terminal i tot seguit consulta
`GET /api/jobs` mai troba un `_job.json` desactualitzat per una carrera
d'escriptura encara en curs al fil del job.
"""

from __future__ import annotations

import contextlib
import json
import logging
import math
import os
import queue
import statistics
import tempfile
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Estats (disseny §3.3)
# ---------------------------------------------------------------------------

QUEUED = "queued"
SYNCING = "syncing"
READING = "reading"
CONSOLIDATING = "consolidating"
MERGING = "merging"
READY = "ready"
INTERRUPTED = "interrupted"
ERROR = "error"
CANCELLED = "cancelled"

#: Estats terminals: cap més event canvia el job (§3.4).
TERMINAL = frozenset({READY, INTERRUPTED, ERROR, CANCELLED})

#: Pas visible a la taula (disseny §3.3): 4 passos totals.
STATE_STEP: dict[str, int] = {
    SYNCING: 1,
    READING: 2,
    CONSOLIDATING: 3,
    MERGING: 4,
}
_TOTAL_STEPS = 4

JOB_FILENAME = "_job.json"
SCHEMA_VERSION = 1

#: Botons vàlids (disseny §2). A la Fase 10 tots tres executen el mateix
#: pipeline (`run_lectura_job`); el delta-sync per botó és la Fase 11.
BUTTONS = ("desde_zero", "preparar", "enllestir")

#: Defectes d'estimació (disseny §3.4, mesurats la nit del 2026-08-24).
_DEFAULT_MEDIAN_DOC_S = 270.0
_DEFAULT_MEDIAN_CONSOLIDA_S = 600.0
_MIN_DOC_SAMPLES = 5
_MIN_CONSOLIDA_SAMPLES = 2


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _write_json_atomic(path: Path, payload: Any) -> None:
    """Escriptura atòmica (tmp al mateix directori + `os.replace`), mateix
    patró que `automation.lectura.runner._write_json_atomic`."""
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


# ---------------------------------------------------------------------------
# Job
# ---------------------------------------------------------------------------


@dataclass(eq=False)
class Job:
    """Estat d'un job de lectura headless per a un projecte (disseny §3.2).

    Instanciat només per `JobRegistry.start()`. `emit()` és el punt d'entrada
    per al productor d'events (el `target` que corre al fil del job): manté
    l'estat, persisteix `_job.json` a cada transició rellevant, i reparteix
    l'event a tots els subscriptors SSE vius.
    """

    project: str
    button: str
    job_path: Path
    state: str = QUEUED
    step_index: int = 0
    docs_total: int = 0
    docs_done: int = 0
    docs_cached: int = 0
    docs_errors: int = 0
    docs_current: list[str] = field(default_factory=list)
    started_at: str = ""
    updated_at: str = ""
    finished_at: str | None = None
    estimate_remaining_s: int = 0
    estimate_basis: str = ""
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    pid: int = field(default_factory=os.getpid)
    claude_version: str | None = None
    network_delta: dict[str, Any] | None = None
    concurrency: int = 2
    telemetry_paths_fn: Callable[[], list[Path]] | None = None
    #: En memòria (mai a `_job.json`): historial complet d'events (per al
    #: replay de subscriptors tardans), subscriptors SSE vius, lock, fil.
    history: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    subscribers: list[queue.Queue] = field(default_factory=list)
    thread: threading.Thread | None = None
    lock: threading.RLock = field(default_factory=threading.RLock)
    #: Intern: `degraded` de l'últim `lectura_fi`, per construir `result` a `prefills`.
    _degraded: bool = False

    # -- Persistència -------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """Forma exacta de `_job.json` (disseny §3.2)."""
        return {
            "schema_version": SCHEMA_VERSION,
            "project": self.project,
            "button": self.button,
            "state": self.state,
            "step": {"index": self.step_index, "total": _TOTAL_STEPS},
            "docs": {
                "total": self.docs_total,
                "done": self.docs_done,
                "cached": self.docs_cached,
                "errors": self.docs_errors,
                "current": list(self.docs_current),
            },
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "finished_at": self.finished_at,
            "estimate_s": {"remaining": self.estimate_remaining_s, "basis": self.estimate_basis},
            "result": self.result,
            "error": self.error,
            "pid": self.pid,
            "claude_version": self.claude_version,
            "network_delta": self.network_delta,
        }

    def write(self) -> None:
        """Escriu `_job.json` atòmicament. Actualitza `updated_at` a ara."""
        with self.lock:
            self.updated_at = _now_iso()
            payload = self.snapshot()
        self._write_payload(payload)

    def _write_payload(self, payload: dict[str, Any]) -> None:
        _write_json_atomic(self.job_path, payload)

    # -- Events ---------------------------------------------------------

    def emit(self, event_type: str, detail: dict[str, Any]) -> None:
        """Registra un event: l'afegeix a `history`, actualitza l'estat
        (§3.3/§3.4), escriu `_job.json` si l'estat ha canviat o si l'event
        és de progrés per document (`lectura_doc`/`lectura_doc_error`), i
        NOMÉS DESPRÉS el reparteix als subscriptors vius.

        L'ordre (disc abans que subscriptors) és deliberat: un subscriptor
        que acaba de rebre l'event terminal (`prefills`/`cancelled`/
        `error_event`) i tot seguit consulta `GET /api/jobs` ha de trobar
        `_job.json` ja consistent amb l'estat que acaba de rebre — mai un
        estat anterior per una carrera d'escriptura a disc encara pendent.
        """
        with self.lock:
            self.history.append((event_type, detail))
            state_changed = self._apply_event(event_type, detail)
            need_write = state_changed or event_type in ("lectura_doc", "lectura_doc_error")
            if need_write:
                self.updated_at = _now_iso()
            payload = self.snapshot() if need_write else None
            subs = list(self.subscribers)

        if payload is not None:
            with contextlib.suppress(Exception):
                self._write_payload(payload)

        for q in subs:
            with contextlib.suppress(Exception):
                q.put((event_type, detail))

    def subscribe(self) -> queue.Queue:
        """Crea una cua nova: hi posa primer TOTA la `history` (replay) i
        després la registra com a subscriptora — un subscriptor tardà no
        perd res ni rep duplicats (secció "subscriptor tardà" del disseny)."""
        with self.lock:
            q: queue.Queue = queue.Queue()
            for item in self.history:
                q.put(item)
            self.subscribers.append(q)
            return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self.lock:
            with contextlib.suppress(ValueError):
                self.subscribers.remove(q)

    # -- Màquina d'estats (crida'l sempre amb `self.lock` agafat) -----------

    def _apply_event(self, event_type: str, detail: dict[str, Any]) -> bool:
        prev_state = self.state

        if event_type == "lectura_inventari":
            self._set_state(READING)
        elif event_type == "lectura_inici":
            self.docs_total = int(detail.get("n_claude") or 0)
        elif event_type == "lectura_doc_inici":
            doc = detail.get("doc")
            if doc and doc not in self.docs_current:
                self.docs_current.append(doc)
        elif event_type == "lectura_doc":
            doc = detail.get("doc")
            if doc in self.docs_current:
                self.docs_current.remove(doc)
            self.docs_done += 1
            if detail.get("cached"):
                self.docs_cached += 1
            self._recompute_estimate()
        elif event_type == "lectura_doc_error":
            self.docs_errors += 1
        elif event_type in ("consolidacio_inici", "lectura_decisions_marker", "consolidacio_fallback"):
            self._set_state(CONSOLIDATING)
        elif event_type == "lectura_fi":
            self._degraded = bool(detail.get("degraded", False))
            self._set_state(MERGING)
        elif event_type == "prefills":
            fallback = (self.result or {}).get("fallback")
            self.result = {"ok": True, "degraded": self._degraded, "fallback": fallback}
            self.finished_at = _now_iso()
            self._set_state(READY)
        elif event_type == "lectura_fallback":
            self.result = {**(self.result or {}), "fallback": detail.get("reason")}
        elif event_type == "cancelled":
            self.finished_at = _now_iso()
            self._set_state(CANCELLED)
        elif event_type == "error_event":
            self.error = {"code": "exception", "detail": detail.get("message")}
            self.finished_at = _now_iso()
            self._set_state(ERROR)

        return self.state != prev_state

    def _set_state(self, new_state: str) -> None:
        self.state = new_state
        self.step_index = STATE_STEP.get(new_state, self.step_index)

    def _recompute_estimate(self) -> None:
        try:
            paths = self.telemetry_paths_fn() if self.telemetry_paths_fn else []
        except Exception:
            paths = []
        try:
            est = estimate_remaining(self, paths, self.concurrency)
        except Exception:
            logger.warning("estimate_remaining failed for %s", self.project, exc_info=True)
            return
        self.estimate_remaining_s = est["remaining"]
        self.estimate_basis = est["basis"]


# ---------------------------------------------------------------------------
# Estimació autocalibrada (disseny §3.4)
# ---------------------------------------------------------------------------


def estimate_remaining(job: Job, telemetry_paths: list[Path], concurrency: int) -> dict[str, Any]:
    """Temps restant estimat en segons, a partir de la mediana d'`elapsed_s`
    de totes les `_telemetry.jsonl` (de tots els projectes — l'estimació es
    calibra amb l'experiència de l'ordinador, no només d'aquest job).

    `mode == "only"`, `cached is False`, `rc == 0` → mostres per document.
    `mode == "consolida"`, `rc == 0` → mostres per consolidació. Línies
    malformades s'ignoren silenciosament.
    """
    if job.state in TERMINAL:
        return {"remaining": 0, "basis": "terminal"}

    doc_samples: list[float] = []
    consolida_samples: list[float] = []

    for path in telemetry_paths:
        try:
            raw = Path(path).read_text(encoding="utf-8")
        except OSError:
            continue
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(entry, dict):
                continue
            elapsed = entry.get("elapsed_s")
            if not isinstance(elapsed, (int, float)):
                continue
            mode = entry.get("mode")
            rc = entry.get("rc")
            if mode == "only" and entry.get("cached") is False and rc == 0:
                doc_samples.append(float(elapsed))
            elif mode == "consolida" and rc == 0:
                consolida_samples.append(float(elapsed))

    if len(doc_samples) < _MIN_DOC_SAMPLES:
        median_doc = _DEFAULT_MEDIAN_DOC_S
        basis = f"default (n={len(doc_samples)})"
    else:
        median_doc = statistics.median(doc_samples)
        basis = f"median_doc_s={median_doc:.0f} from {len(doc_samples)} telemetry rows"

    median_consolida = (
        _DEFAULT_MEDIAN_CONSOLIDA_S
        if len(consolida_samples) < _MIN_CONSOLIDA_SAMPLES
        else statistics.median(consolida_samples)
    )

    if job.state == CONSOLIDATING:
        remaining = int(round(median_consolida))
    elif job.state == MERGING:
        remaining = 60
    else:
        pending = max(0, job.docs_total - job.docs_done)
        blocks = math.ceil(pending / max(1, concurrency)) if pending else 0
        extra_consolida = median_consolida if job.state == READING else 0.0
        remaining = int(round(blocks * median_doc + extra_consolida + 60))

    return {"remaining": remaining, "basis": basis}


# ---------------------------------------------------------------------------
# Registre (un job viu per projecte)
# ---------------------------------------------------------------------------


class JobRegistry:
    """Registre en memòria de jobs vius, més detecció lazy d'interromputs a
    disc (disseny §3.4). Un sol procés (el servidor del wizard) — qualsevol
    `pid` diferent al `_job.json` és, per definició, mort."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def start(
        self,
        project_name: str,
        project_path: Path,
        button: str,
        target: Callable[[Job], None],
        *,
        concurrency: int,
        telemetry_paths_fn: Callable[[], list[Path]],
    ) -> tuple[Job, bool]:
        """Arrenca un job nou, o retorna `(job, False)` si ja n'hi ha un de
        viu (no terminal) per aquest projecte — mai dos `run_lectura` del
        mateix projecte alhora (disseny §3.4)."""
        with self._lock:
            existing = self._jobs.get(project_name)
            if existing is not None and existing.state not in TERMINAL:
                return existing, False

            job_path = project_path / "validation" / "lectura" / JOB_FILENAME
            now = _now_iso()
            job = Job(
                project=project_name,
                button=button,
                job_path=job_path,
                started_at=now,
                updated_at=now,
                concurrency=concurrency,
                telemetry_paths_fn=telemetry_paths_fn,
            )
            job.write()
            self._jobs[project_name] = job

        def _run() -> None:
            try:
                target(job)
            except Exception as exc:
                logger.exception("Job de lectura fallit per a %s", project_name)
                job.emit("error_event", {"message": str(exc)})
            finally:
                if job.state not in TERMINAL:
                    job.emit("error_event", {"message": "job ended without terminal event"})

        thread = threading.Thread(target=_run, daemon=True)
        job.thread = thread
        thread.start()
        return job, True

    def get(self, project_name: str) -> Job | None:
        with self._lock:
            return self._jobs.get(project_name)

    def live(self, project_name: str) -> Job | None:
        with self._lock:
            job = self._jobs.get(project_name)
        if job is not None and job.state not in TERMINAL:
            return job
        return None

    def list_jobs(self, root: Path, *, max_age_days: int | None = 30) -> list[dict[str, Any]]:
        """Escaneja `root/*/validation/lectura/_job.json` (1r nivell de
        projectes). Vius (al registre) → snapshot en memòria. A disc, no
        terminal i `pid` d'un altre procés → reescrit com `interrupted`
        (detecció lazy, disseny §3.4). Filtra per `updated_at` dins
        `max_age_days` (`None` = sense filtre). Ordre: vius primer, després
        `updated_at` desc."""
        root = Path(root)
        if not root.is_dir():
            return []

        with self._lock:
            live_jobs = dict(self._jobs)

        cutoff = datetime.now() - timedelta(days=max_age_days) if max_age_days is not None else None

        alive: list[dict[str, Any]] = []
        others: list[dict[str, Any]] = []

        for project_dir in sorted(p for p in root.iterdir() if p.is_dir()):
            project_name = project_dir.name
            job_path = project_dir / "validation" / "lectura" / JOB_FILENAME
            if not job_path.exists():
                continue

            live = live_jobs.get(project_name)
            if live is not None:
                alive.append(live.snapshot())
                continue

            try:
                data = json.loads(job_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
                logger.warning("_job.json il·legible per a %s: %s", project_name, exc)
                continue
            if not isinstance(data, dict):
                logger.warning("_job.json amb forma inesperada per a %s", project_name)
                continue

            state = data.get("state")
            pid = data.get("pid")
            if state not in TERMINAL and pid != os.getpid():
                data = dict(data)
                data["state"] = INTERRUPTED
                data["finished_at"] = _now_iso()
                data["error"] = None
                with contextlib.suppress(OSError):
                    _write_json_atomic(job_path, data)

            updated_at = data.get("updated_at")
            if cutoff is not None and updated_at:
                try:
                    dt = datetime.fromisoformat(updated_at)
                except (ValueError, TypeError):
                    dt = None
                if dt is not None and dt < cutoff:
                    continue

            others.append(data)

        alive.sort(key=lambda d: d.get("updated_at") or "", reverse=True)
        others.sort(key=lambda d: d.get("updated_at") or "", reverse=True)
        return alive + others

    def mark_interrupted_at_startup(self, root: Path) -> list[dict[str, Any]]:
        """Alias de `list_jobs` sense filtre de data (Fase 10): la crida a
        l'arrencada del servidor es construirà en una fase posterior; aquí
        n'hi ha prou que la detecció lazy d'interromputs sigui correcta."""
        return self.list_jobs(root, max_age_days=None)


#: Singleton de mòdul.
registry = JobRegistry()
