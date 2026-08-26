"""Fase 14a — la fila de la taula d'estat, en el llenguatge de l'Eva (disseny §3.3).

Per què això viu aquí i no al JavaScript de `review.html`: les regles de redacció
del disseny són regles, no decoració — arrodonir a 5 minuts, dir sempre «restants»
i mai el total, i que «Interromput» **no soni a error**. `review.html` fa 10.000
línies i no té cap test; aquí es cobreixen amb pytest i el bloc de la UI es queda
en pintar cadenes ja fetes.

Entrada: el `snapshot()` d'un `Job` (o el `_job.json` llegit del disc — mateixa
forma). Sortida: un dict `eva` que `GET /api/jobs` adjunta a cada job **sense
tocar** el snapshot, de manera que res del que ja consumeix `/api/jobs` es mou.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from automation.lectura.jobs import (
    CANCELLED,
    CONSOLIDATING,
    ERROR,
    INTERRUPTED,
    MERGING,
    QUEUED,
    READING,
    READY,
    SYNCING,
)

#: Icona per estat (§3.3, columna «Pas»). Els estats amb pas numèric no en tenen:
#: hi va el «2/4».
_ICON = {READY: "✓", INTERRUPTED: "⚠", ERROR: "✗", CANCELLED: "⏹"}

#: Etiqueta del botó d'acció de la fila (§5.2, columna «Acció»).
_ACTION = {
    READY: ("enllestir", "Enllestir"),
    INTERRUPTED: ("preparar", "Continuar"),
    ERROR: ("error", "Veure error"),
}


def _round_estimate(seconds: float | int | None) -> str | None:
    """«≈ 25 min restants», mai «24 min 37 s» (§3.3, regles de redacció).

    L'arrodoniment a 5 minuts serveix perquè el número no balli mentre l'Eva
    mira la taula; per sota dels 10 minuts fa el contrari, perquè arrodonir 8
    minuts a 10 és un 25 % de més justament quan la xifra importa (l'exemple del
    disseny per al delta de xarxa és literalment «Enllestir ≈ 8 min»). Per això:
    segons mai, minut exacte fins a 10 min, múltiples de 5 a partir d'allà.
    """
    if seconds is None:
        return None
    try:
        s = float(seconds)
    except (TypeError, ValueError):
        return None
    if s < 0:
        return None
    if s < 60:
        return "< 1 min"
    minutes = s / 60.0
    if minutes < 10:
        return f"≈ {int(round(minutes))} min"
    minutes = int(round(minutes / 5.0)) * 5
    if minutes < 60:
        return f"≈ {minutes} min"
    hours, rest = divmod(minutes, 60)
    return f"≈ {hours} h" if rest == 0 else f"≈ {hours} h {rest} min"


def _when(iso: str | None, now: datetime | None = None) -> str | None:
    """«avui 18:32» / «ahir 18:32» / «12/08 18:32». Mai un ISO cru a la taula."""
    if not iso:
        return None
    try:
        ts = datetime.fromisoformat(str(iso))
    except (TypeError, ValueError):
        return None
    now = now or datetime.now()
    delta_days = (date(now.year, now.month, now.day) - date(ts.year, ts.month, ts.day)).days
    hhmm = ts.strftime("%H:%M")
    if delta_days == 0:
        return f"avui {hhmm}"
    if delta_days == 1:
        return f"ahir {hhmm}"
    return f"{ts.strftime('%d/%m')} {hhmm}"


def _docs(job: dict) -> tuple[int, int]:
    d = job.get("docs")
    d = d if isinstance(d, dict) else {}
    try:
        return int(d.get("done") or 0), int(d.get("total") or 0)
    except (TypeError, ValueError):
        return 0, 0


def _delta_phrase(job: dict) -> str | None:
    """«2 documents nous des de llavors → Enllestir ≈ 8 min» (§3.3, fila `ready`).

    `network_delta` el calcula el delta-sync (Fase 11); mentre no hi sigui, la
    fila `ready` no diu res sobre la xarxa — que és millor que dir «res ha
    canviat» sense haver mirat.
    """
    delta = job.get("network_delta")
    if not isinstance(delta, dict):
        return None
    try:
        changed = int(delta.get("changed") or 0) + int(delta.get("new") or 0)
    except (TypeError, ValueError):
        return None
    if changed <= 0:
        return "res no ha canviat a la xarxa"
    noun = "document nou o canviat" if changed == 1 else "documents nous o canviats"
    tail = _round_estimate(delta.get("estimate_s"))
    phrase = f"{changed} {noun} des de llavors"
    return f"{phrase} → Enllestir {tail}" if tail else phrase


def row(job: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    """Fila de la taula per a un snapshot de job. Mai llança: una fila lletja és
    millor que una taula que no es pinta."""
    state = str(job.get("state") or "")
    step = job.get("step")
    step = step if isinstance(step, dict) else {}
    try:
        step_index, step_total = int(step.get("index") or 0), int(step.get("total") or 4)
    except (TypeError, ValueError):
        step_index, step_total = 0, 4
    done, total = _docs(job)
    est = job.get("estimate_s")
    remaining = est.get("remaining") if isinstance(est, dict) else None

    pas = _ICON.get(state) or (f"{step_index}/{step_total}" if step_index else "—")
    counter = f"{done}/{total}" if total else None
    estimate = _round_estimate(remaining)
    detail: str | None = None

    if state == QUEUED:
        title = "En cua"
    elif state == SYNCING:
        title = "Copiant fitxers de la xarxa"
        estimate = estimate or "< 1 min"
    elif state == READING:
        title = "Llegint documents"
        detail = f"{estimate} restants" if estimate else None
    elif state == CONSOLIDATING:
        title = "Consolidant el que ha llegit"
        detail = f"{estimate} restants" if estimate else None
        counter = None
    elif state == MERGING:
        title = "Preparant el formulari"
        estimate = estimate or "< 1 min"
        detail = f"{estimate} restants"
        counter = None
    elif state == READY:
        when = _when(job.get("finished_at") or job.get("updated_at"), now)
        title = f"Preparat ({when})" if when else "Preparat"
        detail = _delta_phrase(job)
        counter = None
        estimate = None
    elif state == INTERRUPTED:
        # «Interromput» NO és un error (§3.3): la cache per md5 fa que reprendre
        # costi només els documents que falten, i la taula ho ha de dir.
        at = f" a {step_index}/{step_total}" if step_index else ""
        read = f" ({done}/{total} llegits)" if total else ""
        title = f"Interromput{at}{read}"
        detail = "prem Preparar per continuar — els documents ja llegits no es tornen a llegir"
        counter = None
        estimate = None
    elif state == ERROR:
        title = "No s'ha pogut preparar"
        detail = "avisat Eficients"
        counter = None
        estimate = None
    elif state == CANCELLED:
        title = "Aturat per tu"
        counter = None
        estimate = None
    else:
        title = state or "Desconegut"
        counter = None

    action_key, action_label = _ACTION.get(state, ("attach", "Continuar") if state not in ("", None) else ("", ""))
    if state not in _ACTION:
        # Estats vius: la fila s'enganxa a l'stream que ja corre.
        action_key, action_label = ("attach", "Veure progrés")

    return {
        "project": job.get("project"),
        "pas": pas,
        "titol": title,
        "comptador": counter,   # «7/17» — en negreta a la UI, és el que més calma
        "detall": detail,
        "estimacio": estimate,
        "preparat_el": _when(job.get("finished_at"), now) if state == READY else None,
        "accio": action_key,
        "accio_text": action_label,
        "viu": state not in ("", READY, INTERRUPTED, ERROR, CANCELLED),
    }


def rows(jobs: list[dict[str, Any]], *, now: datetime | None = None) -> list[dict[str, Any]]:
    return [row(j, now=now) for j in jobs]
