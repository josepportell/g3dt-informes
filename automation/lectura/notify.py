"""Fase 15 — avisos quan un job acaba: toast a l'escriptori i correu.

Principi del disseny (§6.1): **la taula és la veritat**; això són avisos. Cap
canal és bloquejant i cap pot fer caure un job — si falla, `logger.warning` i
avall. Per això tota funció pública d'aquest mòdul retorna un resum del que ha
fet i no llança mai.

Un senyal per projecte, en acabar o en fallar; mai un avís per pas. L'Eva no
necessita saber que va pel document 7 de 17 — per això hi ha la taula.

Canals (§6.2):

- **Toast** (`G3DT_NOTIFY_TOAST`, per defecte actiu). A l'ordinador de l'Eva,
  `powershell New-BurntToastNotification`; en desenvolupament sota WSL,
  `notify-send` si hi és. Tots dos són millor-esforç: quin funciona de veritat a
  la seva màquina es decideix presencialment (Fase 17), i mentrestant el correu
  cobreix el cas.
- **Correu a l'Eva**: expedient + carpeta + una línia d'instrucció.
- **Correu de telemetria a Eficients** (§6.4): explícit, mai BCC, i **mínim**.
  El Josep no pot veure què passa a l'ordinador de l'Eva; fins ara l'única
  visibilitat era demanar-li l'arxiu de logs.

Configuració, llegida directament de l'entorn — mateixa decisió que les
`G3DT_LECTURA_*` del runner (`automation/config.py`, comentari del flag del
wizard headless): no es dupliquen a `config.py`.

    G3DT_NOTIFY_TOAST           true|false (defecte true)
    G3DT_NOTIFY_SMTP_HOST/PORT/USER/PASS
    G3DT_NOTIFY_FROM            remitent dedicat (mai el correu personal del Josep)
    G3DT_NOTIFY_TO_EVA          buit = canal desactivat
    G3DT_NOTIFY_TO_EFICIENTS    buit = canal desactivat (si G3 no vol telemetria)
    G3DT_NOTIFY_WIZARD_URL      defecte http://localhost:8765/review.html

**Què NO surt mai d'aquest ordinador** (§6.4, minimització): valors de camps,
cites de documents i noms de fitxer. Les files de telemetria van per índex
(`doc_3`), extensió i tipus de document; les línies de log del CLI passen per
`sanitize_log()` abans d'entrar enlloc. La substitució és per llista explícita
de noms de fitxer coneguts, no per heurística sobre majúscules: una regex tipus
`[A-Z]{2,} [A-Z]{2,}` deixa passar «Can Mir» i es menja «PDF ANNEXES».
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import smtplib
import subprocess
from email.message import EmailMessage
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_SMTP_TIMEOUT_S = 15
_TOAST_TIMEOUT_S = 10
_LOG_TAIL_LINES = 30
_DEFAULT_WIZARD_URL = "http://localhost:8765/review.html"


# ---------------------------------------------------------------------------
# Configuració
# ---------------------------------------------------------------------------

def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _env_bool(name: str, default: bool) -> bool:
    raw = _env(name)
    if not raw:
        return default
    return raw.lower() not in ("0", "false", "no", "off")


def toast_enabled() -> bool:
    return _env_bool("G3DT_NOTIFY_TOAST", True)


def smtp_configured() -> bool:
    return bool(_env("G3DT_NOTIFY_SMTP_HOST") and _env("G3DT_NOTIFY_FROM"))


def wizard_url() -> str:
    return _env("G3DT_NOTIFY_WIZARD_URL", _DEFAULT_WIZARD_URL)


# ---------------------------------------------------------------------------
# Sanejament (§6.4)
# ---------------------------------------------------------------------------

def _doc_alias_map(docs: list[str]) -> dict[str, str]:
    """`{'PDF/ANNEXES/4001612_sondeig.pdf': 'doc_2'}` — ordre estable pel llistat."""
    return {doc: f"doc_{i}" for i, doc in enumerate(docs) if doc}


#: Vocabulari tècnic d'una lectura que falla. Vegeu `sanitize_log`: NOMÉS
#: sobreviuen les línies que en contenen alguna cosa.
_LOG_KEEP = re.compile(
    r"rc\s*=\s*-?\d+|returncode|exit\s*code"
    r"|timeout|timed out|s'ha exhaurit"
    r"|usage limit|rate limit|credit balance|quota|overloaded|over capacity"
    r"|HTTP\s*\d{3}|status\s*\d{3}"
    r"|ECONN\w*|ENOTFOUND|ENOENT|EACCES|EPIPE|connection error|name resolution|refused"
    r"|traceback|exception|permission denied|command not found|no such file"
    r"|json[_ ]?(valid|decode|parse)|invalid json|not valid json"
    r"|killed|signal \d+|out of memory",
    re.IGNORECASE,
)


def sanitize_log(text: str, aliases: dict[str, str], *, project: str = "",
                 tail: int = _LOG_TAIL_LINES, technical_only: bool = True) -> str:
    """Últimes `tail` línies del log del CLI, **filtrades per llista blanca**.

    El disseny (§6.4) demanava substituir els noms de fitxer per `doc_{i}` abans
    d'incloure res. No n'hi ha prou, i ho va destapar el test amb un projecte
    sintètic amb noms a tot arreu: el log del CLI no només porta noms de fitxer,
    porta **valors de camps** (`client detectat: Jordi Bosch Novell`). Cap
    substitució pot cobrir això, perquè el que hi pot sortir és qualsevol cosa
    que el model hagi llegit del document — i la regla del mateix §6.4 és «mai
    valors de camps ni cites».

    Per això s'inverteix el criteri: en lloc d'esborrar el que sabem que és
    sensible, **només es conserva el que sabem que és tècnic** (`_LOG_KEEP`:
    codis de retorn, timeouts, límits d'ús, errors de xarxa, traces). La resta
    es descarta i només se'n diu quantes línies eren. Les línies que sobreviuen
    encara passen per la substitució de noms de fitxer, rutes i nom de carpeta,
    perquè un missatge tècnic pot citar el fitxer que ha petat.

    `technical_only=False` desactiva la llista blanca i deixa només la
    substitució. **Només** per a text que ha escrit el nostre propi codi Python
    (el missatge d'`error_event`), mai per a sortida del model: la diferència és
    que d'un `str(exc)` nostre en controlem la forma, i del log del CLI no.
    """
    if not text:
        return ""
    lines = text.splitlines()[-max(1, tail):]
    kept, dropped = [], 0
    for line in lines:
        if not technical_only or _LOG_KEEP.search(line):
            kept.append(line)
        else:
            dropped += 1

    out = "\n".join(kept)
    # Primer els camins complets, després els basenames: si es fes al revés,
    # una ruta quedaria mig substituïda («PDF/ANNEXES/doc_2»).
    for doc, alias in sorted(aliases.items(), key=lambda kv: len(kv[0]), reverse=True):
        out = out.replace(doc, alias)
    for doc, alias in sorted(aliases.items(), key=lambda kv: len(Path(kv[0]).name), reverse=True):
        name = Path(doc).name
        if name:
            out = out.replace(name, alias)
            stem = Path(doc).stem
            if len(stem) > 3:
                out = out.replace(stem, alias)
    if project:
        out = out.replace(project, "(projecte)")
    # Rutes absolutes que hagin sobreviscut (temporals, home de l'usuari).
    out = re.sub(r"(/[^\s:'\"]+){2,}", "(ruta)", out)
    out = re.sub(r"[A-Za-z]:\\\\[^\s'\"]+", "(ruta)", out)

    if dropped:
        note = f"({dropped} línies omeses: no són missatges tècnics coneguts)"
        out = f"{out}\n{note}" if out else note
    return out


def telemetry_rows(path: Path, aliases: dict[str, str], sizes: dict[str, int]) -> list[dict[str, Any]]:
    """`_telemetry.jsonl` sense noms de fitxer (§6.4).

    Es conserva el que serveix per diagnosticar (durada, `rc`, timeout, cache,
    mode) i el que situa el document sense identificar-lo (àlies, extensió,
    mida). `log_path` i `doc` no surten mai: tots dos porten el nom del fitxer i
    el de la carpeta del projecte.
    """
    rows: list[dict[str, Any]] = []
    try:
        raw = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return rows
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        doc = r.get("doc")
        row: dict[str, Any] = {
            "doc": aliases.get(doc, "—") if doc else "—",
            "ext": Path(doc).suffix.lower() if doc else "",
            "size": sizes.get(doc) if doc else None,
            "mode": r.get("mode"),
            "elapsed_s": round(float(r["elapsed_s"]), 1) if isinstance(r.get("elapsed_s"), (int, float)) else None,
            "rc": r.get("rc"),
            "timeout": bool(r.get("timeout")),
            "cached": bool(r.get("cached")),
        }
        rows.append(row)
    return rows


def _inventory(out_dir: Path) -> tuple[list[str], dict[str, int], dict[str, str], dict[str, int]]:
    """`(docs, mides, tipus, recompte per extensió)` des de `_inventory.json`."""
    docs: list[str] = []
    sizes: dict[str, int] = {}
    hints: dict[str, str] = {}
    by_ext: dict[str, int] = {}
    try:
        inv = json.loads((Path(out_dir) / "_inventory.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return docs, sizes, hints, by_ext
    for f in inv.get("files") or []:
        if not isinstance(f, dict):
            continue
        path = f.get("path")
        if not path:
            continue
        ext = Path(path).suffix.lower() or "(sense extensió)"
        by_ext[ext] = by_ext.get(ext, 0) + 1
        if f.get("route") != "claude":
            continue
        docs.append(path)
        if isinstance(f.get("size"), int):
            sizes[path] = f["size"]
        hints[path] = str(f.get("doc_type_hint") or "")
    docs.sort()
    return docs, sizes, hints, by_ext


# ---------------------------------------------------------------------------
# Toast
# ---------------------------------------------------------------------------

def send_toast(title: str, body: str) -> str | None:
    """Retorna el canal que ha funcionat (`notify-send` / `burnt-toast`) o None.

    Millor esforç i mai bloquejant. Quin dels dos funciona de veritat a
    l'ordinador de l'Eva es decideix presencialment (Fase 17); si cap, el correu
    cobreix el cas i la taula segueix sent la veritat.
    """
    if not toast_enabled():
        return None
    for channel, argv in _toast_commands(title, body):
        try:
            done = subprocess.run(argv, capture_output=True, timeout=_TOAST_TIMEOUT_S, check=False)
        except (OSError, subprocess.SubprocessError) as exc:
            logger.warning("toast %s ha fallat: %s", channel, exc)
            continue
        if done.returncode == 0:
            return channel
        logger.warning("toast %s rc=%s: %s", channel, done.returncode, done.stderr[:200])
    return None


def _toast_commands(title: str, body: str) -> list[tuple[str, list[str]]]:
    out: list[tuple[str, list[str]]] = []
    if shutil.which("notify-send"):
        out.append(("notify-send", ["notify-send", title, body]))
    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    if powershell:
        # Cometes simples i `''` per escapar: el text va dins d'un literal de
        # PowerShell, no d'una shell — un apòstrof català («l'informe») trencaria
        # la comanda si no s'escapés.
        def q(s: str) -> str:
            return "'" + s.replace("'", "''") + "'"
        out.append((
            "burnt-toast",
            [powershell, "-NoProfile", "-NonInteractive", "-Command",
             f"New-BurntToastNotification -Text {q(title)}, {q(body)}"],
        ))
    return out


# ---------------------------------------------------------------------------
# Correu
# ---------------------------------------------------------------------------

def send_mail(to: str, subject: str, body: str) -> bool:
    """Envia un correu de text pla. `to` buit = canal desactivat, no és un error."""
    to = (to or "").strip()
    if not to:
        return False
    if not smtp_configured():
        logger.warning("correu no enviat (SMTP sense configurar): %s", subject)
        return False

    msg = EmailMessage()
    msg["From"] = _env("G3DT_NOTIFY_FROM")
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    host = _env("G3DT_NOTIFY_SMTP_HOST")
    try:
        port = int(_env("G3DT_NOTIFY_SMTP_PORT", "587"))
    except ValueError:
        port = 587
    user, password = _env("G3DT_NOTIFY_SMTP_USER"), _env("G3DT_NOTIFY_SMTP_PASS")

    try:
        if port == 465:
            server: smtplib.SMTP = smtplib.SMTP_SSL(host, port, timeout=_SMTP_TIMEOUT_S)
        else:
            server = smtplib.SMTP(host, port, timeout=_SMTP_TIMEOUT_S)
        with server:
            server.ehlo()
            if port != 465 and _env_bool("G3DT_NOTIFY_SMTP_STARTTLS", port == 587):
                with_tls = server.starttls()
                logger.debug("STARTTLS: %s", with_tls[0] if with_tls else "?")
                server.ehlo()
            if user:
                server.login(user, password)
            server.send_message(msg)
    except Exception as exc:  # noqa: BLE001 — cap avís pot fer caure un job
        logger.warning("correu no enviat (%s): %s", subject, exc)
        return False
    return True


def eva_body(project: str, *, ok: bool) -> str:
    if ok:
        return (
            f"L'informe de {project} ja està preparat.\n\n"
            f"Obre el wizard i prem «Enllestir informe preparat»:\n{wizard_url()}\n\n"
            "Comprovarà si algú ha tocat res a la xarxa i t'obrirà el formulari.\n"
        )
    return (
        f"No s'ha pogut preparar l'informe de {project}.\n\n"
        "Eficients ja n'està avisat i ho mirem. Pots tornar-ho a provar des del wizard:\n"
        f"{wizard_url()}\n"
    )


def telemetry_body(
    project: str,
    job: dict[str, Any],
    *,
    rows: list[dict[str, Any]],
    by_ext: dict[str, int],
    hints: dict[str, str],
    aliases: dict[str, str],
    log_excerpt: str = "",
) -> str:
    """Cos del correu de telemetria (§6.4): expedient, carpeta, durades, `n`
    documents per tipus i les files sanejades. Cap valor de camp, cap cita, cap
    nom de fitxer."""
    docs = job.get("docs") if isinstance(job.get("docs"), dict) else {}
    lines = [
        f"Projecte: {project}",
        f"Botó: {job.get('button') or '?'}",
        f"Estat: {job.get('state') or '?'}",
        f"Inici: {job.get('started_at') or '?'}  ·  Fi: {job.get('finished_at') or '?'}",
        f"Documents: {docs.get('done') or 0}/{docs.get('total') or 0}"
        f"  (cache {docs.get('cached') or 0}, errors {docs.get('errors') or 0})",
        f"claude: {job.get('claude_version') or '?'}",
        "",
        "Fitxers per extensió: " + (", ".join(f"{n} {ext}" for ext, n in sorted(by_ext.items())) or "—"),
        "",
        "Lectures (sense noms de fitxer):",
    ]
    if rows:
        lines.append(f"{'doc':<8} {'tipus':<22} {'ext':<8} {'mida':>9} {'mode':<16} {'s':>7}  rc  timeout cache")
        alias_to_hint = {alias: hints.get(doc, "") for doc, alias in aliases.items()}
        for r in rows:
            size = f"{r['size']:,}".replace(",", ".") if isinstance(r.get("size"), int) else "—"
            lines.append(
                f"{r['doc']:<8} {alias_to_hint.get(r['doc'], ''):<22} {r['ext']:<8} {size:>9} "
                f"{str(r.get('mode') or ''):<16} {str(r.get('elapsed_s') or ''):>7}  "
                f"{str(r.get('rc')):<3} {str(r.get('timeout')):<7} {r.get('cached')}"
            )
    else:
        lines.append("—")

    if job.get("error"):
        # Missatge del nostre propi codi (`emit("error_event", …)`), no sortida
        # del model: substitució sí, llista blanca no (vegeu `sanitize_log`).
        err = sanitize_log(str(job["error"])[:300], aliases, project=project, tail=6, technical_only=False)
        lines += ["", "Error (missatge del wizard):", err]
    if log_excerpt:
        lines += ["", f"Últimes {_LOG_TAIL_LINES} línies del CLI (sanejades):", log_excerpt]
    lines += ["", "Avís tècnic automàtic del wizard G3DT. Cap valor de camp ni cita de document."]
    return "\n".join(lines)


def last_failed_log(out_dir: Path) -> str:
    """Text del log del CLI de l'última lectura que ha fallat, o cadena buida.

    El `log_path` de `_telemetry.jsonl` porta el nom del projecte i del fitxer;
    per això el CONTINGUT passa sempre per `sanitize_log()` i la RUTA no surt
    mai enlloc.
    """
    try:
        raw = (Path(out_dir) / "_telemetry.jsonl").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    candidate: str | None = None
    for line in raw.splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("rc") not in (0, None) or r.get("timeout"):
            path = r.get("log_path")
            if path:
                candidate = path
    if not candidate:
        return ""
    try:
        return Path(candidate).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


# ---------------------------------------------------------------------------
# API pública: un avís per job
# ---------------------------------------------------------------------------

def notify_job_finished(
    project: str,
    out_dir: Path,
    job: dict[str, Any],
    *,
    log_text: str = "",
) -> dict[str, Any]:
    """Avisa que un job ha acabat (`ready`) o ha fallat (`error`).

    Retorna què s'ha enviat — útil per als tests i per al log. **Mai llança.**
    """
    result: dict[str, Any] = {"toast": None, "eva": False, "telemetry": False}
    try:
        ok = str(job.get("state")) == "ready"
        out_dir = Path(out_dir)
        docs, sizes, hints, by_ext = _inventory(out_dir)
        aliases = _doc_alias_map(docs)

        title = "G3DT" if ok else "G3DT · error"
        toast_text = (
            f"{project} preparat. Obre el wizard i prem Enllestir."
            if ok else f"No s'ha pogut preparar {project}. Eficients n'està avisat."
        )
        result["toast"] = send_toast(title, toast_text)

        subject_eva = f"G3DT · {project} llest per enllestir" if ok else f"G3DT · {project} no s'ha pogut preparar"
        result["eva"] = send_mail(_env("G3DT_NOTIFY_TO_EVA"), subject_eva, eva_body(project, ok=ok))

        to_eficients = _env("G3DT_NOTIFY_TO_EFICIENTS")
        if to_eficients:
            rows = telemetry_rows(out_dir / "_telemetry.jsonl", aliases, sizes)
            excerpt = sanitize_log(log_text, aliases, project=project) if (log_text and not ok) else ""
            body = telemetry_body(project, job, rows=rows, by_ext=by_ext, hints=hints,
                                  aliases=aliases, log_excerpt=excerpt)
            subject = f"Eficients · telemetria G3DT · {project} · {'OK' if ok else 'ERROR'}"
            result["telemetry"] = send_mail(to_eficients, subject, body)
    except Exception:  # noqa: BLE001 — un avís mai pot fer caure un job
        logger.warning("notificació fallida per a %s", project, exc_info=True)
    return result
