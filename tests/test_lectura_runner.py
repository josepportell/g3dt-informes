"""Tests per al runner headless (Fase 3+4) — `automation/lectura/runner.py` +
`automation/lectura/normalize.py`.

Vegeu `docs/DISSENY-WIZARD-HEADLESS-CANDIDATS-2026-08-24.md` §2/§5/§6/§7 i el
Pas 4/5/5b de `.claude/commands/g3dt-llegir-projecte.md`.

CAP crida real a `claude` ni a cap API: `claude` es substitueix per un script
Python mock (`_write_mock_claude`), escrit i executat NOMES dins `tmp_path`.
El projecte de fixture ("proj/") tambe es SINTETIC i viu nomes a `tmp_path`
(mai `reference-material/`, mai `/mnt/c`).

Nom de fitxer per-document: el mock crida `automation.lectura.runner.safe_doc_name`
per escriure exactament el nom que el runner espera trobar — es la mateixa
sanejada, no una duplicada (evita divergencia mock/runner).
"""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from automation.lectura import runner as lectura_runner  # noqa: E402
from automation.lectura.contract import validate_decisions  # noqa: E402
from automation.lectura.normalize import soft_normalize  # noqa: E402


# ---------------------------------------------------------------------------
# Projecte sintetic (4 fitxers: 1 route claude, el seu duplicat md5, 1 route
# claude independent, 1 route python fals)
# ---------------------------------------------------------------------------


def _build_synthetic_project(base: Path) -> Path:
    proj = base / "proj"
    proj.mkdir()
    (proj / "annex_a.pdf").write_bytes(b"%PDF-1.4 fake annex A content for runner tests")
    # Mateix contingut -> mateix md5 -> duplicat d'annex_a.pdf (path mes llarg,
    # per tant el que ha de sortir "skipped_duplicate").
    (proj / "annex_a_copy.pdf").write_bytes(b"%PDF-1.4 fake annex A content for runner tests")
    (proj / "annex_b.pdf").write_bytes(b"%PDF-1.4 fake annex B, different content entirely")
    # Coincideix amb el patro `_RE_PRESSUPOST` -> route "python" (g3_templates
    # el llegeix directament; contingut brossa, capturat pel try/except intern).
    (proj / "PRESSUPOST GEOTEC.X.pdf").write_bytes(b"%PDF-1.4 not a real budget, garbage bytes")
    return proj


@pytest.fixture
def synth_project(tmp_path: Path) -> Path:
    return _build_synthetic_project(tmp_path)


# ---------------------------------------------------------------------------
# Mock `claude`: script Python executable escrit a tmp_path pel test.
# ---------------------------------------------------------------------------

_MOCK_CLAUDE_TEMPLATE = '''#!__SHEBANG__
import hashlib
import json
import os
import pathlib
import sys
import time

sys.path.insert(0, __REPO_ROOT__)
from automation.lectura.runner import safe_doc_name  # noqa: E402

MODE = os.environ.get("MOCK_CLAUDE_MODE", "happy")
ONLY_TARGETS = set(filter(None, os.environ.get("MOCK_CLAUDE_ONLY_TARGETS", "").split(",")))
SLEEP_S = float(os.environ.get("MOCK_CLAUDE_SLEEP", "3"))
SPAWN_LOG = os.environ.get("MOCK_CLAUDE_SPAWNLOG")
ARGVLOG = os.environ.get("MOCK_CLAUDE_ARGVLOG")
EMIT_JSON = os.environ.get("MOCK_CLAUDE_JSON") == "1"


def _log_spawn(kind, doc=""):
    if not SPAWN_LOG:
        return
    with open(SPAWN_LOG, "a", encoding="utf-8") as fh:
        fh.write(kind + "\\t" + doc + "\\n")


def _emit_happy_stdout():
    if EMIT_JSON:
        envelope = {
            "type": "result", "subtype": "success", "is_error": False,
            "duration_ms": 1234, "duration_api_ms": 1000, "num_turns": 3,
            "result": "Document read (mock).", "total_cost_usd": 0.05,
            "usage": {
                "input_tokens": 2, "output_tokens": 10,
                "cache_creation_input_tokens": 100, "cache_read_input_tokens": 200,
            },
            "modelUsage": {"claude-sonnet-5": {}},
        }
        print(json.dumps(envelope))
    else:
        print("mock done")


argv = sys.argv[1:]

if argv and argv[0] == "--version":
    print("2.0.0-mock")
    sys.exit(0)

if ARGVLOG:
    with open(ARGVLOG, "a", encoding="utf-8") as fh:
        fh.write(" ".join(argv) + "\\n")

prompt = argv[1] if len(argv) > 1 else ""
tokens = prompt.split()


def _after(flag):
    if flag in tokens:
        i = tokens.index(flag)
        if i + 1 < len(tokens):
            return tokens[i + 1]
    return None


only = _after("--only")
out_dir = _after("--out")
consolida = "--consolida" in tokens
project_path = tokens[1] if len(tokens) > 1 else None

is_consolida_like = consolida or (only is None)

if is_consolida_like:
    _log_spawn("consolida" if consolida else "projecte")
    if MODE == "invalid":
        pathlib.Path(out_dir, "_decisions.json").write_text("{not json", encoding="utf-8")
        sys.exit(0)
    if MODE == "decisions_invalid":
        bad = {
            "schema_version": 1, "project": "SYNTH", "generated": "now", "skill_version": "mock",
            "fields": {},
            "tables": {"spt_ma_tests": {"estat_bloc": "candidats", "rows": [
                {"n30": {"estat": "segur", "value": "40",
                         "candidates": [{"value": "40", "font": "x", "quote": "y"}],
                         "registre": {"estat": "segur", "value": "1/2",
                                      "candidates": [{"value": "1/2", "font": "x", "quote": "y"}]}}}
            ]}},
        }
        pathlib.Path(out_dir, "_decisions.json").write_text(
            json.dumps(bad, ensure_ascii=False), encoding="utf-8")
        sys.exit(0)
    good = {
        "schema_version": 1, "project": "SYNTH", "generated": "now", "skill_version": "mock",
        "fields": {"expedient": {"estat": "segur", "value": "EXP1",
                    "candidates": [{"value": "EXP1", "font": "mock", "quote": "EXP1"}],
                    "rule": "mock"}},
        "tables": {},
    }
    tmp = pathlib.Path(out_dir, "_decisions.json.tmp")
    tmp.write_text(json.dumps(good, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, pathlib.Path(out_dir, "_decisions.json"))
    _emit_happy_stdout()
    sys.exit(0)

# --- mode --only: escriu {safe_doc_name(only)}.json ------------------------
_log_spawn("only", only)

restricted = (not ONLY_TARGETS) or (only in ONLY_TARGETS)

if MODE == "timeout" and restricted:
    time.sleep(SLEEP_S)
    sys.exit(0)

if MODE == "rc" and restricted:
    sys.exit(1)

safe = safe_doc_name(only)
src_path = pathlib.Path(project_path) / only
md5 = hashlib.md5(src_path.read_bytes()).hexdigest() if src_path.exists() else "unknown"

if MODE == "invalid" and restricted:
    pathlib.Path(out_dir, safe + ".json").write_text("{broken", encoding="utf-8")
    sys.exit(0)

doc_json = {
    "source_path": only, "source_md5": md5, "skill_version": "mock", "schema_version": 1,
    "document_type": "altre",
    "tier_a": [
        {"concept_id": "expedient", "value": "EXP1", "location": "mock", "quote": "EXP1", "confidence": 0.95}
    ],
}
tmp = pathlib.Path(out_dir, safe + ".json.tmp")
tmp.write_text(json.dumps(doc_json, ensure_ascii=False), encoding="utf-8")
os.replace(tmp, pathlib.Path(out_dir, safe + ".json"))
_emit_happy_stdout()
sys.exit(0)
'''


def _write_mock_claude(base: Path, repo_root: Path) -> Path:
    script = base / "mock_claude.py"
    content = _MOCK_CLAUDE_TEMPLATE.replace("__SHEBANG__", sys.executable).replace(
        "__REPO_ROOT__", repr(str(repo_root))
    )
    script.write_text(content, encoding="utf-8")
    script.chmod(0o755)
    return script


@pytest.fixture
def mock_claude(tmp_path: Path) -> Path:
    return _write_mock_claude(tmp_path, PROJECT_ROOT)


@pytest.fixture
def base_env(monkeypatch, tmp_path: Path, mock_claude: Path) -> Path:
    """Env per defecte: mock `claude`, timeouts curts, concurrencia 2, mode
    happy. Retorna el path del spawn-log (una linia per invocacio del mock)."""
    monkeypatch.setenv("G3DT_CLAUDE_PATH", str(mock_claude))
    monkeypatch.setenv("G3DT_LECTURA_TIMEOUT", "2")
    monkeypatch.setenv("G3DT_LECTURA_CONSOLIDA_TIMEOUT", "5")
    monkeypatch.setenv("G3DT_LECTURA_CONCURRENCY", "2")
    monkeypatch.setenv("G3DT_LECTURA_MODE", "document")
    monkeypatch.setenv("MOCK_CLAUDE_MODE", "happy")
    monkeypatch.delenv("MOCK_CLAUDE_ONLY_TARGETS", raising=False)
    spawn_log = tmp_path / "spawns.log"
    monkeypatch.setenv("MOCK_CLAUDE_SPAWNLOG", str(spawn_log))
    return spawn_log


def _events_collector():
    events: list[tuple[str, dict]] = []

    def on_event(name: str, payload: dict) -> None:
        events.append((name, payload))

    return events, on_event


def _spawn_lines(spawn_log: Path) -> list[str]:
    if not spawn_log.exists():
        return []
    return [line for line in spawn_log.read_text(encoding="utf-8").splitlines() if line.strip()]


def _spawn_kinds(spawn_log: Path) -> list[str]:
    return [line.split("\t")[0] for line in _spawn_lines(spawn_log)]


# ---------------------------------------------------------------------------
# Escenaris del runner
# ---------------------------------------------------------------------------


def test_happy_end_to_end(synth_project, base_env):
    out_dir = synth_project / "validation" / "lectura"
    events, on_event = _events_collector()

    result = lectura_runner.run_lectura(synth_project, out_dir=out_dir, on_event=on_event)

    assert result.decisions is not None
    assert result.degraded is False
    assert result.mode == "document"
    assert validate_decisions(result.decisions) == []

    statuses = {d["doc"]: d["status"] for d in result.per_doc}
    assert statuses.get("annex_a.pdf") == "ok"
    assert statuses.get("annex_b.pdf") == "ok"
    assert statuses.get("annex_a_copy.pdf") == "skipped_duplicate"
    assert "PRESSUPOST GEOTEC.X.pdf" not in statuses  # route python, mai a la cua claude

    # telemetria: com a minim 1 linia per doc + 1 de consolida, totes amb claude_version.
    assert result.telemetry_path is not None and result.telemetry_path.exists()
    lines = [json.loads(l) for l in result.telemetry_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    modes = {l["mode"] for l in lines}
    assert modes == {"only", "consolida"}
    assert sum(1 for l in lines if l["mode"] == "only") == 2  # annex_a + annex_b (dup col·lapsat)
    assert all("claude_version" in l for l in lines)
    assert all(l["claude_version"] for l in lines)

    # events en ordre (relatiu, no exacte: hi ha lectura_doc intercalats).
    names = [n for n, _ in events]
    for required in ("lectura_inventari", "templates_fields", "lectura_inici", "decisions", "lectura_fi"):
        assert required in names, f"falta l'event {required!r}: {names}"
    assert names.index("lectura_inventari") < names.index("templates_fields")
    assert names.index("templates_fields") < names.index("lectura_inici")
    assert names.index("lectura_inici") < names.index("decisions")
    assert names.index("decisions") < names.index("lectura_fi")
    assert names[-1] == "lectura_fi"


def test_cache_hit_second_run_zero_new_spawns(synth_project, base_env):
    out_dir = synth_project / "validation" / "lectura"

    r1 = lectura_runner.run_lectura(synth_project, out_dir=out_dir)
    assert r1.decisions is not None
    kinds_after_1 = _spawn_kinds(base_env)
    assert kinds_after_1.count("only") == 2
    assert kinds_after_1.count("consolida") == 1

    r2 = lectura_runner.run_lectura(synth_project, out_dir=out_dir)
    assert r2.decisions is not None

    kinds_after_2 = _spawn_kinds(base_env)
    new_kinds = kinds_after_2[len(kinds_after_1):]
    assert new_kinds == [], f"esperava 0 crides noves al mock, hi ha: {new_kinds}"

    statuses = {d["doc"]: d["status"] for d in r2.per_doc}
    assert statuses.get("annex_a.pdf") == "cached"
    assert statuses.get("annex_b.pdf") == "cached"


def test_timeout_then_retry_doc_failed_rest_continues(synth_project, base_env, monkeypatch):
    monkeypatch.setenv("MOCK_CLAUDE_MODE", "timeout")
    monkeypatch.setenv("MOCK_CLAUDE_SLEEP", "3")
    # annex_a.pdf guanya el grup duplicat (path mes curt) -> es l'unic dels dos
    # que arriba a la cua; restringim el timeout nomes a ell.
    monkeypatch.setenv("MOCK_CLAUDE_ONLY_TARGETS", "annex_a.pdf")

    out_dir = synth_project / "validation" / "lectura"
    result = lectura_runner.run_lectura(synth_project, out_dir=out_dir)

    per_doc_by_name = {d["doc"]: d for d in result.per_doc}
    assert per_doc_by_name["annex_a.pdf"]["status"] == "failed"
    assert per_doc_by_name["annex_a.pdf"]["attempts"] == 2
    assert per_doc_by_name["annex_b.pdf"]["status"] == "ok"

    # el mock fa la consolidacio incondicionalment "happy": la resta del
    # pipeline continua i produeix decisions vàlides tot i el doc fallit.
    assert result.decisions is not None
    assert validate_decisions(result.decisions) == []

    lines = [json.loads(l) for l in result.telemetry_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    a_lines = [l for l in lines if l["doc"] == "annex_a.pdf"]
    assert len(a_lines) == 2
    assert all(l["timeout"] is True for l in a_lines)
    assert [l["attempt"] for l in a_lines] == [1, 2]


def test_consolidacio_invalida_causa_degradat(synth_project, base_env, monkeypatch):
    monkeypatch.setenv("MOCK_CLAUDE_MODE", "decisions_invalid")
    out_dir = synth_project / "validation" / "lectura"
    events, on_event = _events_collector()

    result = lectura_runner.run_lectura(synth_project, out_dir=out_dir, on_event=on_event)

    assert result.degraded is True
    assert result.decisions is not None
    assert validate_decisions(result.decisions) == []

    names = [n for n, _ in events]
    assert "consolidacio_fallback" in names

    for table_name in ("dpsh_tests", "sondeig_tests", "spt_ma_tests", "soil_levels"):
        assert result.decisions["tables"][table_name]["rows"] == []


def test_cancellation_immediate_returns_partial_without_hanging(synth_project, base_env):
    out_dir = synth_project / "validation" / "lectura"
    events, on_event = _events_collector()

    start = time.monotonic()
    result = lectura_runner.run_lectura(
        synth_project, out_dir=out_dir, on_event=on_event, should_cancel=lambda: True,
    )
    elapsed = time.monotonic() - start

    assert elapsed < 5.0, f"cancel·lacio immediata ha trigat {elapsed:.1f}s"
    assert result.decisions is None
    assert result.per_doc == []
    assert "cancelled" in [n for n, _ in events]
    # cap crida al mock: la cancel·lacio es detecta abans de fer cap spawn.
    assert _spawn_lines(base_env) == []


def test_cancellation_mid_flight_kills_live_process(synth_project, base_env, monkeypatch):
    monkeypatch.setenv("MOCK_CLAUDE_MODE", "timeout")
    monkeypatch.setenv("MOCK_CLAUDE_SLEEP", "30")
    monkeypatch.setenv("G3DT_LECTURA_TIMEOUT", "60")  # el timeout normal no ha d'intervenir

    cancel_event = threading.Event()
    timer = threading.Timer(0.6, cancel_event.set)
    timer.daemon = True
    timer.start()

    out_dir = synth_project / "validation" / "lectura"
    start = time.monotonic()
    result = lectura_runner.run_lectura(
        synth_project, out_dir=out_dir, should_cancel=cancel_event.is_set,
    )
    elapsed = time.monotonic() - start
    timer.cancel()

    assert elapsed < 15.0, f"la cancel·lacio no ha matat el proces a temps ({elapsed:.1f}s)"
    assert result.decisions is None
    assert any(d["status"] == "cancelled" for d in result.per_doc)


def test_duplicate_collapsed_single_call_per_md5_group(synth_project, base_env):
    out_dir = synth_project / "validation" / "lectura"
    result = lectura_runner.run_lectura(synth_project, out_dir=out_dir)

    statuses = {d["doc"]: d["status"] for d in result.per_doc}
    assert statuses["annex_a.pdf"] == "ok"
    assert statuses["annex_a_copy.pdf"] == "skipped_duplicate"

    only_docs = [line.split("\t", 1)[1] for line in _spawn_lines(base_env) if line.startswith("only\t")]
    assert only_docs.count("annex_a.pdf") == 1
    assert "annex_a_copy.pdf" not in only_docs


def test_mode_projecte_happy(synth_project, base_env, monkeypatch):
    monkeypatch.setenv("G3DT_LECTURA_MODE", "projecte")
    out_dir = synth_project / "validation" / "lectura"

    result = lectura_runner.run_lectura(synth_project, out_dir=out_dir)

    assert result.mode == "projecte"
    assert result.decisions is not None
    assert result.degraded is False
    assert validate_decisions(result.decisions) == []
    assert len(result.per_doc) == 1
    assert result.per_doc[0]["status"] == "ok"

    kinds = _spawn_kinds(base_env)
    assert kinds.count("projecte") == 1
    assert kinds.count("only") == 0
    assert kinds.count("consolida") == 0


# ---------------------------------------------------------------------------
# Fase 9 — model pinat + `--output-format json` + metriques CLI a telemetria
# ---------------------------------------------------------------------------


def test_argv_pins_model_and_json_format(synth_project, base_env, monkeypatch, tmp_path):
    argv_log = tmp_path / "argv.log"
    monkeypatch.setenv("MOCK_CLAUDE_ARGVLOG", str(argv_log))
    out_dir = synth_project / "validation" / "lectura"

    result = lectura_runner.run_lectura(synth_project, out_dir=out_dir)
    assert result.decisions is not None

    lines = [l for l in argv_log.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert lines, "cap linia d'argv registrada"
    for line in lines:
        assert "--permission-mode bypassPermissions --model sonnet --output-format json" in line

    monkeypatch.setenv("G3DT_LECTURA_MODEL", "opus")
    result2 = lectura_runner.run_lectura(synth_project, out_dir=out_dir, force=True)
    assert result2.decisions is not None

    lines_2 = [l for l in argv_log.read_text(encoding="utf-8").splitlines() if l.strip()]
    new_lines = lines_2[len(lines):]
    assert new_lines, "cap linia nova d'argv al segon run"
    for line in new_lines:
        assert "--permission-mode bypassPermissions --model opus --output-format json" in line


def test_telemetry_has_cli_metrics_when_json(synth_project, base_env, monkeypatch):
    monkeypatch.setenv("MOCK_CLAUDE_JSON", "1")
    out_dir = synth_project / "validation" / "lectura"

    result = lectura_runner.run_lectura(synth_project, out_dir=out_dir)
    assert result.decisions is not None

    lines = [json.loads(l) for l in result.telemetry_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert lines, "cap linia de telemetria"
    for entry in lines:
        assert entry["cli_json_ok"] is True
        assert entry["num_turns"] == 3
        assert entry["duration_api_ms"] == 1000
        assert entry["cost_usd"] == 0.05
        assert entry["models"] == ["claude-sonnet-5"]
        assert entry["usage"]["cache_read_input_tokens"] == 200
        assert entry["model"] == "sonnet"

        log_path = Path(entry["log_path"])
        assert "Document read (mock)." in log_path.read_text(encoding="utf-8")
        assert not Path(str(log_path) + ".out").exists()


def test_telemetry_without_json_is_marked(synth_project, base_env):
    out_dir = synth_project / "validation" / "lectura"

    result = lectura_runner.run_lectura(synth_project, out_dir=out_dir)
    assert result.decisions is not None

    lines = [json.loads(l) for l in result.telemetry_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert lines, "cap linia de telemetria"
    for entry in lines:
        assert entry["cli_json_ok"] is False
        assert "num_turns" not in entry

        log_path = Path(entry["log_path"])
        assert "mock done" in log_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# soft_normalize
# ---------------------------------------------------------------------------


def test_soft_normalize_repairs_candidats_value_mismatch():
    d = {"fields": {"expedient": {
        "estat": "candidats", "value": "WRONG",
        "candidates": [{"value": "RIGHT", "font": "doc", "quote": "q"}],
    }}}

    out = soft_normalize(d)

    assert out["fields"]["expedient"]["value"] == "RIGHT"
    assert d["fields"]["expedient"]["value"] == "WRONG"  # no muta l'entrada


def test_soft_normalize_wraps_top_level_font_quote():
    d = {"fields": {"municipality": {
        "estat": "segur", "value": "BELL-LLOC", "font": "comanda N21", "quote": "BELL-LLOC",
    }}}

    out = soft_normalize(d)

    cell = out["fields"]["municipality"]
    assert cell["candidates"] == [{"value": "BELL-LLOC", "font": "comanda N21", "quote": "BELL-LLOC"}]


def test_soft_normalize_leaves_well_formed_cell_untouched():
    d = {"fields": {"expedient": {
        "estat": "segur", "value": "4001612",
        "candidates": [{"value": "4001612", "font": "comanda N19", "quote": "4001612"}],
        "rule": "…",
    }}}

    out = soft_normalize(d)

    assert out == d


def test_soft_normalize_does_not_repair_no_trobat():
    d = {"fields": {"lab_depth": {"estat": "no_trobat", "value": None, "sources_checked": ["…"]}}}

    out = soft_normalize(d)

    assert out == d


# --- Autenticacio del fill (G3DT_LECTURA_AUTH) -------------------------------

def test_child_env_strips_api_key_by_default():
    from automation.lectura.runner import _child_env
    base = {"PATH": "/bin", "ANTHROPIC_API_KEY": "sk-x", "ANTHROPIC_AUTH_TOKEN": "t", "HOME": "/h"}
    env = _child_env(base)
    assert "ANTHROPIC_API_KEY" not in env and "ANTHROPIC_AUTH_TOKEN" not in env
    assert env["PATH"] == "/bin" and env["HOME"] == "/h"
    assert base["ANTHROPIC_API_KEY"] == "sk-x"  # no mutacio


def test_child_env_keeps_api_key_when_requested():
    from automation.lectura.runner import _child_env
    base = {"ANTHROPIC_API_KEY": "sk-x", "G3DT_LECTURA_AUTH": "api_key"}
    assert _child_env(base)["ANTHROPIC_API_KEY"] == "sk-x"
