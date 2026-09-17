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
    IMATGES,
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


def _reading_found_nothing(job: dict) -> bool:
    """Cert quan un job `ready` no ha llegit realment CAP document — ni un.

    Historial (per què `done` i `errors` ja es van descartar com a senyal, tercera passada
    2026-09-17): `done` compta duplicats saltats que mai passen per `claude -p` (arreglat a
    l'origen, `Job._apply_event`, però sense cap invariant que el protegeixi de tornar-se a
    inflar per una causa futura). `errors` és PER INTENT, no per document: amb `_MAX_ATTEMPTS =
    2`, un document que encerta al segon intent aporta 1 error i està LLEGIT — el reviewer ho va
    reproduir en directe amb 2 documents, tots dos amb un reintent transitori i tots dos llegits
    (`{"total": 2, "done": 2, "errors": 2}`), que la versió anterior d'aquesta funció marcava
    fals-positiu com «sense llegir cap document» quan s'havia llegit tot.

    Font de veritat actual: `docs.failed`, un comptador NOU (`Job.docs_failed`) que només
    s'incrementa amb la fallada DEFINITIVA d'un document — `automation/lectura/runner.py` ja
    calcula aquesta llista (`docs_failed`) amb l'estat FINAL de cada document (`"failed"` amb els
    `_MAX_ATTEMPTS` esgotats, o `"skipped_systemic"` si la parada sistèmica el va deixar sense
    enviar) i la porta a l'event `lectura_fi`; mai un intent que després ha reeixit. La guarda és
    doncs «hi havia documents i TOTS han quedat sense llegir» (`failed >= total`), mai `errors`
    ni `done`.

    Compatibilitat amb `_job.json` antics (escrits abans d'aquest camp): `d.get("failed")` no hi
    és → per defecte 0 → la condició és sempre falsa per a qualsevol `total > 0` → repintar un
    job vell mai dispara un avís fals (verificat amb un snapshot real de disc,
    `{"total": 18, "done": 19, "errors": 0}`, sense la clau `failed`)."""
    d = job.get("docs")
    d = d if isinstance(d, dict) else {}
    try:
        total = int(d.get("total") or 0)
        failed = int(d.get("failed") or 0)
    except (TypeError, ValueError):
        return False
    return total > 0 and failed >= total


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
    basis = (est.get("basis") if isinstance(est, dict) else None) or ""

    pas = _ICON.get(state) or (f"{step_index}/{step_total}" if step_index else "—")
    counter = f"{done}/{total}" if total else None
    # `basis` buida vol dir que `Job._recompute_estimate()` encara no s'ha cridat mai
    # (`estimate_remaining_s`/`estimate_basis` són als valors de naixement del dataclass,
    # `0`/`""`) — no que la mediana de telemetria hagi donat 0. Sense aquesta guarda,
    # `_round_estimate(0)` diu «< 1 min», que és fals: mesurat al projecte Rubí
    # (2026-09-17), la fila va dir «0/12 · < 1 min restants» durant 3 min 43 s abans que
    # el primer document acabés. Un cop hi ha base (encara que sigui el default per manca
    # de mostres), el número és real i es mostra igual que sempre.
    estimate = _round_estimate(remaining) if basis else None
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
    elif state == IMATGES:
        title = "Triant les imatges de l'informe"
        detail = f"{estimate} restants" if estimate else None
        counter = None
    elif state == MERGING:
        title = "Preparant el formulari"
        estimate = estimate or "< 1 min"
        detail = f"{estimate} restants"
        counter = None
    elif state == READY:
        when = _when(job.get("finished_at") or job.get("updated_at"), now)
        if _reading_found_nothing(job):
            title = "Preparat sense llegir cap document"
            detail = "torna-ho a provar amb «Preparar» — si persisteix, avisa Eficients"
        else:
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
        err = job.get("error") if isinstance(job.get("error"), dict) else {}
        code = err.get("code")
        if code == "usage_limit":
            # No és una avaria nostra: el compte de Claude ha dit prou per avui (o fins que es
            # renovi la finestra). Els documents ja llegits queden a la cau; «Preparar» reprèn.
            title = "Aturat: el compte de Claude ha arribat al límit d'ús"
            detail = "els documents ja llegits es conserven — prem Preparar quan el pla torni a estar disponible"
        elif code == "auth":
            # Tampoc és una avaria nostra: la sessió de Claude ha caducat (2026-09-16, prova WSL).
            # Els documents ja llegits queden a la cau igual que amb el límit d'ús. 2026-09-17
            # (decisió del Josep): l'Eva no obre mai un terminal — arrenca el wizard amb un .bat i
            # treballa al navegador —, així que el detall apunta a la drecera dedicada de
            # l'escriptori («Tornar a entrar a Claude»), no a `claude login` ni a cap terminal.
            title = "Aturat: cal tornar a iniciar sessió a Claude"
            detail = (
                "fes doble clic a «Tornar a entrar a Claude» a l'escriptori; després torna aquí i "
                "prem «Preparar» — els documents ja llegits es conserven"
            )
        else:
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
