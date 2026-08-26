"""Fase 15 — avisos (toast + correu) quan un job acaba (disseny §6).

El que es prova aquí, per ordre d'importància:

1. **Res del que hi ha dins d'un projecte de l'Eva pot sortir per correu**
   (§6.4): ni noms de fitxer, ni rutes, ni el nom de la carpeta, ni valors de
   camps. Es prova amb un projecte sintètic amb noms de persona a tot arreu.
2. **Cap avís pot fer caure un job** (§6.1): SMTP mort, toast inexistent,
   telemetria il·legible — el job acaba igual.
3. **Canal buit = res**, no un error.
4. Un senyal per projecte i mai en `cancelled`.

El servidor SMTP de prova és de casa (socket + fil): `aiosmtpd` no és a l'entorn
i `smtpd` va desaparèixer a Python 3.12. Són 40 línies i exerciten `smtplib` de
veritat, que és el punt.
"""

from __future__ import annotations

import json
import socket
import threading
from pathlib import Path

import pytest

from automation.lectura import notify as N


# ---------------------------------------------------------------------------
# Servidor SMTP de prova
# ---------------------------------------------------------------------------

def _parse(rcpt: str, raw: str) -> dict[str, str]:
    """Assumpte i cos DESCODIFICATS.

    Les comprovacions de fuita s'han de fer sobre el text real, no sobre el
    quoted-printable: `Jordi Bosch Novell` pot quedar partit per un `=\r\n` al
    fil i «no hi surt» seria fals.
    """
    from email import message_from_string
    from email.header import decode_header, make_header

    msg = message_from_string(raw)
    payload = msg.get_payload(decode=True) or b""
    return {
        "to": rcpt,
        "raw": raw,
        "subject": str(make_header(decode_header(msg.get("Subject", "")))),
        "body": payload.decode(msg.get_content_charset() or "utf-8", "replace"),
    }


class FakeSMTP:
    """Accepta una conversa SMTP mínima i desa els missatges rebuts."""

    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []
        self._sock = socket.socket()
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(5)
        self.port = self._sock.getsockname()[1]
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()
            except OSError:
                return
            with conn:
                try:
                    self._session(conn)
                except OSError:
                    pass

    def _session(self, conn: socket.socket) -> None:
        f = conn.makefile("rwb")
        f.write(b"220 fake ESMTP\r\n"); f.flush()
        rcpt, data_mode, body = "", False, []
        while True:
            line = f.readline()
            if not line:
                return
            if data_mode:
                if line.strip() == b".":
                    self.messages.append(_parse(rcpt, b"".join(body).decode("utf-8", "replace")))
                    body, data_mode = [], False
                    f.write(b"250 OK\r\n"); f.flush()
                    continue
                body.append(line)
                continue
            cmd = line.decode("utf-8", "replace").strip()
            upper = cmd.upper()
            if upper.startswith(("EHLO", "HELO")):
                f.write(b"250-fake\r\n250 SIZE 10240000\r\n")
            elif upper.startswith("MAIL"):
                f.write(b"250 OK\r\n")
            elif upper.startswith("RCPT"):
                rcpt = cmd.split("<", 1)[-1].rstrip(">").strip() if "<" in cmd else cmd
                f.write(b"250 OK\r\n")
            elif upper == "DATA":
                data_mode = True
                f.write(b"354 go\r\n")
            elif upper == "QUIT":
                f.write(b"221 bye\r\n"); f.flush()
                return
            else:
                f.write(b"250 OK\r\n")
            f.flush()

    def close(self) -> None:
        self._stop.set()
        self._sock.close()


@pytest.fixture
def smtp(monkeypatch: pytest.MonkeyPatch):
    server = FakeSMTP()
    monkeypatch.setenv("G3DT_NOTIFY_SMTP_HOST", "127.0.0.1")
    monkeypatch.setenv("G3DT_NOTIFY_SMTP_PORT", str(server.port))
    monkeypatch.setenv("G3DT_NOTIFY_SMTP_STARTTLS", "false")
    monkeypatch.setenv("G3DT_NOTIFY_FROM", "g3dt@eficients.cat")
    monkeypatch.setenv("G3DT_NOTIFY_TOAST", "false")
    monkeypatch.delenv("G3DT_NOTIFY_SMTP_USER", raising=False)
    yield server
    server.close()


# ---------------------------------------------------------------------------
# Un projecte sintètic amb noms de persona a tot arreu
# ---------------------------------------------------------------------------

PERSONA = "Jordi Bosch Novell"
CARPETA = "4001612 BELL-LLOC"
FITXERS = [
    f"ACCEPTACIO/PRESSUPOST {PERSONA}.pdf",
    "PDF/ANNEXES/4001612_sondeig.pdf",
    f"Re_ ESTUDI {PERSONA}.msg",
]


@pytest.fixture
def out_dir(tmp_path: Path) -> Path:
    d = tmp_path / CARPETA / "validation" / "lectura"
    d.mkdir(parents=True)
    (d / "_inventory.json").write_text(json.dumps({"files": [
        {"path": FITXERS[0], "size": 1234, "route": "claude", "doc_type_hint": "acceptacio"},
        {"path": FITXERS[1], "size": 5678, "route": "claude", "doc_type_hint": "annex_sondeig"},
        {"path": FITXERS[2], "size": 999, "route": "claude", "doc_type_hint": "correu"},
        {"path": "Thumbs.db", "size": 10, "route": "skip", "doc_type_hint": "exclos_nom:Thumbs.db"},
    ]}, ensure_ascii=False), encoding="utf-8")
    log = tmp_path / "cli.log"
    log.write_text(
        f"llegint /home/eva/{CARPETA}/{FITXERS[1]}\n"
        f"client detectat: {PERSONA}\n"
        "Error: rc=1 usage limit reached\n", encoding="utf-8")
    (d / "_telemetry.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in [
        {"doc": FITXERS[0], "mode": "only", "rc": 0, "timeout": False, "cached": False,
         "elapsed_s": 108.333, "log_path": str(tmp_path / "ok.log")},
        {"doc": FITXERS[1], "mode": "only", "rc": 1, "timeout": True, "cached": False,
         "elapsed_s": 240.2, "log_path": str(log)},
    ]), encoding="utf-8")
    return d


def _job(state: str = "ready", **kw):
    j = {
        "project": CARPETA, "button": "preparar", "state": state,
        "step": {"index": 4, "total": 4},
        "docs": {"total": 3, "done": 3, "cached": 1, "errors": 0, "current": []},
        "started_at": "2026-08-26T17:00:00", "finished_at": "2026-08-26T18:32:00",
        "claude_version": "2.1.241", "error": None,
    }
    j.update(kw)
    return j


# ---------------------------------------------------------------------------
# 1. Minimització: què NO pot sortir mai (§6.4)
# ---------------------------------------------------------------------------

def test_the_telemetry_email_carries_no_file_name_no_path_and_no_person(smtp, out_dir, monkeypatch):
    monkeypatch.setenv("G3DT_NOTIFY_TO_EFICIENTS", "telemetria@eficients.cat")
    monkeypatch.delenv("G3DT_NOTIFY_TO_EVA", raising=False)

    N.notify_job_finished(CARPETA, out_dir, _job("error", error=f"ha fallat {FITXERS[1]}"),
                          log_text=(out_dir.parent.parent.parent / "cli.log").read_text(encoding="utf-8"))

    assert len(smtp.messages) == 1
    raw = smtp.messages[0]["subject"] + "\n" + smtp.messages[0]["body"]
    for filename in FITXERS:
        assert filename not in raw
        assert Path(filename).name not in raw
    assert PERSONA not in raw
    assert "/home/eva" not in raw


def test_the_telemetry_email_still_says_enough_to_debug(smtp, out_dir, monkeypatch):
    """Sense noms de fitxer, però amb àlies estable, tipus de document, mida,
    durada, `rc` i timeout: prou per saber què ha passat sense saber què deia."""
    monkeypatch.setenv("G3DT_NOTIFY_TO_EFICIENTS", "telemetria@eficients.cat")

    N.notify_job_finished(CARPETA, out_dir, _job("ready"))

    raw = smtp.messages[0]["body"]
    assert "doc_1" in raw and "annex_sondeig" in raw
    assert "240.2" in raw and "True" in raw          # elapsed + timeout
    assert "2 .pdf" in raw and "1 .msg" in raw       # n documents per tipus
    assert "2.1.241" in raw
    assert "Cap valor de camp ni cita de document." in raw


def test_sanitize_log_keeps_only_known_technical_lines():
    """Llista blanca, no substitució: el log del CLI pot portar VALORS de camps
    (`client detectat: …`), i cap substitució els pot cobrir. Ho va destapar
    aquest fitxer de test, no una revisió."""
    aliases = N._doc_alias_map(FITXERS)
    text = (
        f"obrint /home/eva/{CARPETA}/{FITXERS[1]}\n"
        f"client detectat: {PERSONA}\n"
        "adreça de l'obra: Carrer Major 12\n"
        "Error: rc=1 usage limit reached\n"
    )
    out = N.sanitize_log(text, aliases, project=CARPETA)
    assert "usage limit" in out
    assert PERSONA not in out
    assert "Carrer Major" not in out
    assert "3 línies omeses" in out


def test_sanitize_log_still_masks_file_names_inside_a_technical_line():
    aliases = N._doc_alias_map(FITXERS)
    out = N.sanitize_log(f"Error: ENOENT llegint {FITXERS[1]} a /home/eva/{CARPETA}", aliases, project=CARPETA)
    assert "ENOENT" in out
    assert FITXERS[1] not in out and "4001612_sondeig" not in out
    assert CARPETA not in out and "/home/eva" not in out


@pytest.mark.parametrize("line", [
    "rc=1", "process timed out after 240s", "HTTP 503 over capacity",
    "credit balance is too low", "Traceback (most recent call last):",
    "ECONNRESET", "invalid json", "command not found: claude",
])
def test_the_technical_vocabulary_survives(line):
    assert line.split()[0][:6].lower() in N.sanitize_log(line, {}).lower()


def test_sanitize_log_looks_only_at_the_tail():
    text = "\n".join(["rc=0 linia antiga"] * 50 + ["rc=1 usage limit"])
    out = N.sanitize_log(text, {}, tail=3)
    assert out.count("rc=") == 3


def test_telemetry_rows_never_expose_doc_or_log_path(out_dir):
    aliases = N._doc_alias_map(FITXERS)
    rows = N.telemetry_rows(out_dir / "_telemetry.jsonl", aliases, {FITXERS[0]: 1234})
    assert [r["doc"] for r in rows] == ["doc_0", "doc_1"]
    assert all("log_path" not in r for r in rows)
    assert rows[0]["ext"] == ".pdf" and rows[0]["size"] == 1234
    assert rows[1]["timeout"] is True and rows[1]["elapsed_s"] == 240.2


# ---------------------------------------------------------------------------
# 2. Els dos correus i el seu contingut
# ---------------------------------------------------------------------------

def test_a_finished_job_sends_two_emails_one_for_eva_one_for_eficients(smtp, out_dir, monkeypatch):
    monkeypatch.setenv("G3DT_NOTIFY_TO_EVA", "eva@g3.cat")
    monkeypatch.setenv("G3DT_NOTIFY_TO_EFICIENTS", "telemetria@eficients.cat")

    sent = N.notify_job_finished(CARPETA, out_dir, _job("ready"))

    assert sent["eva"] is True and sent["telemetry"] is True
    assert {m["to"] for m in smtp.messages} == {"eva@g3.cat", "telemetria@eficients.cat"}
    eva = next(m for m in smtp.messages if m["to"] == "eva@g3.cat")
    assert "llest per enllestir" in eva["subject"]
    eva = eva["body"]
    assert "Enllestir informe preparat" in eva
    assert "review.html" in eva


def test_evas_email_never_carries_telemetry(smtp, out_dir, monkeypatch):
    """El correu d'ella diu què ha de fer; el detall tècnic és l'altre."""
    monkeypatch.setenv("G3DT_NOTIFY_TO_EVA", "eva@g3.cat")
    monkeypatch.delenv("G3DT_NOTIFY_TO_EFICIENTS", raising=False)

    N.notify_job_finished(CARPETA, out_dir, _job("ready"))

    raw = smtp.messages[0]["body"]
    assert "doc_0" not in raw and "elapsed" not in raw and "rc" not in raw.split("\n\n")[-1]


def test_a_failed_job_tells_eva_that_eficients_already_knows(smtp, out_dir, monkeypatch):
    monkeypatch.setenv("G3DT_NOTIFY_TO_EVA", "eva@g3.cat")

    N.notify_job_finished(CARPETA, out_dir, _job("error", error="rc=1"))

    raw = smtp.messages[0]["subject"] + smtp.messages[0]["body"]
    assert "no s'ha pogut preparar" in raw.lower()
    assert "Eficients" in raw


# ---------------------------------------------------------------------------
# 3. Canal buit = res. 4. Cap avís pot fer caure un job.
# ---------------------------------------------------------------------------

def test_an_empty_recipient_is_a_disabled_channel_not_an_error(smtp, out_dir, monkeypatch):
    monkeypatch.setenv("G3DT_NOTIFY_TO_EVA", "")
    monkeypatch.setenv("G3DT_NOTIFY_TO_EFICIENTS", "")

    sent = N.notify_job_finished(CARPETA, out_dir, _job("ready"))

    assert sent == {"toast": None, "eva": False, "telemetry": False}
    assert smtp.messages == []


def test_without_smtp_configured_nothing_is_sent_and_nothing_raises(out_dir, monkeypatch):
    for var in ("G3DT_NOTIFY_SMTP_HOST", "G3DT_NOTIFY_FROM"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("G3DT_NOTIFY_TO_EVA", "eva@g3.cat")
    monkeypatch.setenv("G3DT_NOTIFY_TOAST", "false")

    assert N.notify_job_finished(CARPETA, out_dir, _job("ready"))["eva"] is False


def test_a_dead_smtp_server_does_not_raise(out_dir, monkeypatch):
    monkeypatch.setenv("G3DT_NOTIFY_SMTP_HOST", "127.0.0.1")
    monkeypatch.setenv("G3DT_NOTIFY_SMTP_PORT", "9")     # discard, res escolta
    monkeypatch.setenv("G3DT_NOTIFY_FROM", "g3dt@eficients.cat")
    monkeypatch.setenv("G3DT_NOTIFY_TO_EVA", "eva@g3.cat")
    monkeypatch.setenv("G3DT_NOTIFY_TOAST", "false")

    assert N.notify_job_finished(CARPETA, out_dir, _job("ready"))["eva"] is False


def test_an_unreadable_project_still_notifies(smtp, tmp_path, monkeypatch):
    """Sense inventari ni telemetria: el correu surt igual, més buit."""
    monkeypatch.setenv("G3DT_NOTIFY_TO_EFICIENTS", "telemetria@eficients.cat")
    empty = tmp_path / "buit"
    empty.mkdir()

    assert N.notify_job_finished(CARPETA, empty, _job("ready"))["telemetry"] is True
    assert "—" in smtp.messages[0]["body"]


# ---------------------------------------------------------------------------
# Toast
# ---------------------------------------------------------------------------

def test_toast_is_best_effort_and_reports_which_channel_worked(monkeypatch):
    calls = []

    class Done:
        returncode = 0
        stderr = b""

    monkeypatch.setenv("G3DT_NOTIFY_TOAST", "true")
    monkeypatch.setattr(N.shutil, "which", lambda name: "/usr/bin/notify-send" if name == "notify-send" else None)
    monkeypatch.setattr(N.subprocess, "run", lambda argv, **kw: (calls.append(argv), Done())[1])

    assert N.send_toast("G3DT", "llest") == "notify-send"
    assert calls[0][:2] == ["notify-send", "G3DT"]


def test_toast_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("G3DT_NOTIFY_TOAST", "false")
    monkeypatch.setattr(N.subprocess, "run", lambda *a, **k: pytest.fail("no s'havia de cridar"))
    assert N.send_toast("G3DT", "llest") is None


def test_toast_falls_through_to_the_next_channel(monkeypatch):
    tried = []

    class Fail:
        returncode = 1
        stderr = b"no module BurntToast"

    class Ok:
        returncode = 0
        stderr = b""

    monkeypatch.setenv("G3DT_NOTIFY_TOAST", "true")
    monkeypatch.setattr(N.shutil, "which", lambda name: f"/x/{name}")

    def run(argv, **kw):
        tried.append(argv[0])
        return Fail() if argv[0].endswith("notify-send") else Ok()

    monkeypatch.setattr(N.subprocess, "run", run)
    assert N.send_toast("G3DT", "llest") == "burnt-toast"
    assert len(tried) == 2


def test_a_toast_that_explodes_is_not_fatal(monkeypatch):
    monkeypatch.setenv("G3DT_NOTIFY_TOAST", "true")
    monkeypatch.setattr(N.shutil, "which", lambda name: "/usr/bin/notify-send" if name == "notify-send" else None)
    monkeypatch.setattr(N.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(OSError("no display")))
    assert N.send_toast("G3DT", "llest") is None


def test_powershell_command_escapes_catalan_apostrophes(monkeypatch):
    monkeypatch.setattr(N.shutil, "which", lambda name: "/x/powershell.exe" if "powershell" in name else None)
    cmds = dict(N._toast_commands("G3DT", "l'informe és a punt"))
    assert "''informe" in cmds["burnt-toast"][-1]


# ---------------------------------------------------------------------------
# Log de l'última lectura fallida
# ---------------------------------------------------------------------------

def test_last_failed_log_picks_the_failing_row(out_dir):
    text = N.last_failed_log(out_dir)
    assert "usage limit" in text


def test_last_failed_log_is_empty_when_nothing_failed(tmp_path):
    d = tmp_path / "lectura"
    d.mkdir()
    (d / "_telemetry.jsonl").write_text(json.dumps(
        {"doc": "a.pdf", "rc": 0, "timeout": False, "log_path": "/no/existeix.log"}), encoding="utf-8")
    assert N.last_failed_log(d) == ""


def test_our_own_error_message_survives_without_the_allowlist(smtp, out_dir, monkeypatch):
    """`error_event` el redacta el nostre codi Python, no el model: se'n
    controla la forma, i per això no passa per la llista blanca. La substitució
    de noms sí que s'hi aplica."""
    monkeypatch.setenv("G3DT_NOTIFY_TO_EFICIENTS", "telemetria@eficients.cat")

    N.notify_job_finished(CARPETA, out_dir,
                          _job("error", error=f"Extraction ended without result ({FITXERS[1]})"))

    body = smtp.messages[0]["body"]
    assert "Extraction ended without result" in body
    assert FITXERS[1] not in body and "4001612_sondeig" not in body


def test_the_model_log_never_gets_the_same_pass(out_dir):
    """Simetria explícita: el mateix text, pels dos camins, dona resultats
    diferents — i el del model és el restrictiu."""
    aliases = N._doc_alias_map(FITXERS)
    text = f"client detectat: {PERSONA}"
    assert PERSONA not in N.sanitize_log(text, aliases)
    assert PERSONA in N.sanitize_log(text, aliases, technical_only=False)
