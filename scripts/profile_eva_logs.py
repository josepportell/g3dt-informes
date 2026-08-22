#!/usr/bin/env python3
"""Perfil d'ús real de G3DT a partir dels logs de l'ordinador de l'Eva.

Llegeix `g3dt.log*` (fitxers rotats + actual), els fusiona cronològicament i
imprimeix, en Markdown:

  1. Quadre per projecte: obertures, informes OK, crashes (generació / prefills)
  2. Tipus de crash (traceback → línia culpable)
  3. Temps d'espera dels prefills per obertura (SmartScan → LLM synthesis)
  4. On van els minuts: espera HTTP per proveïdor i per context que la consumeix
  5. Visió: OK/FAIL per proveïdor i tipus, motius de fallada

Marcadors (estables a `production/g3dt-eva-v1`):
  obertura  = "SmartScan: N entries found in <projecte>"
  prefills  = "LLM synthesis: ..." (fi) | "Error merging prefills" (crash)
  generació = "Copied report to network" (OK) | "Error generating report for" (crash)

Ús:
    python3 scripts/profile_eva_logs.py /mnt/c/claude/g3dt/dades-eva/g3dt.log.batch.zip \
        /mnt/c/claude/g3dt/dades-eva/g3dt.log.txt > docs/audit/eva-logs-profile.md

Accepta .zip (amb logs rotats dins), fitxers solts o carpetes. Només lectura.
"""
from __future__ import annotations

import collections
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path

TS = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ (\S+?):\d+ (\w+): (.*)$")
HOSTS = {"api.openai.com": "OpenAI", "api.groq.com": "Groq", "api.anthropic.com": "Anthropic"}
MAX_GAP = 600  # s — salts més grans són pauses de l'Eva, no espera del sistema


def load_lines(paths: list[str]) -> list[str]:
    lines: list[str] = []
    for p in paths:
        path = Path(p)
        if path.suffix == ".zip":
            with zipfile.ZipFile(path) as z:
                for name in sorted(z.namelist()):
                    if not name.endswith("/"):
                        lines += z.read(name).decode("utf-8", "replace").splitlines()
        elif path.is_dir():
            for f in sorted(path.glob("g3dt.log*")):
                lines += f.read_text(encoding="utf-8", errors="replace").splitlines()
        else:
            lines += path.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines


def parse(lines: list[str]):
    """→ llista de (ts, logger, level, msg, raw_index), ordenada per ts."""
    out = []
    for i, l in enumerate(lines):
        m = TS.match(l)
        if m:
            out.append((datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S"), m.group(2), m.group(3), m.group(4), i))
    out.sort(key=lambda r: (r[0], r[4]))
    return out


def norm(s: str) -> str:
    return re.sub(r"[\d.]+", "N", s)


def scoreboard(P):
    R = collections.defaultdict(lambda: dict(days=set(), opened=0, ok=0, fail_gen=0, fail_prefill=0))
    cur = None
    for t, lg, lv, msg, _ in P:
        d = t.date().isoformat()
        if m := re.search(r"SmartScan: \d+ entries found in (.+)$", msg):
            cur = m.group(1).strip(); R[cur]["opened"] += 1; R[cur]["days"].add(d)
        elif m := re.search(r"Error generating report for (.+)$", msg):
            R[m.group(1).strip()]["fail_gen"] += 1
        elif m := re.search(r"Copied report to network: .*[\\/](\d{7} [^\\/]+?)[\\/]", msg):
            R[m.group(1).strip()]["ok"] += 1; R[m.group(1).strip()]["days"].add(d)
        elif "Error merging prefills" in msg and cur:
            R[cur]["fail_prefill"] += 1
    print("## 1. Quadre per projecte\n")
    print("| Projecte | Dies | Obertures | Informes OK | Crash generació | Crash prefills | Dates |")
    print("|---|--:|--:|--:|--:|--:|---|")
    for k, v in sorted(R.items(), key=lambda kv: min(kv[1]["days"]) if kv[1]["days"] else ""):
        print(f"| {k} | {len(v['days'])} | {v['opened']} | {v['ok']} | {v['fail_gen']} | {v['fail_prefill']} | {', '.join(sorted(x[5:] for x in v['days']))} |")
    tot = lambda f: sum(v[f] for v in R.values())
    print(f"\n**Total:** {len(R)} projectes · {tot('opened')} obertures · {tot('ok')} informes OK · "
          f"{tot('fail_gen')} crashes de generació · {tot('fail_prefill')} crashes de prefills\n")


def crash_types(lines):
    print("## 2. Tipus de crash (línia culpable → excepció)\n")
    c = collections.Counter()
    i = 0
    while i < len(lines):
        if lines[i].startswith("Traceback"):
            j = i + 1; frames = []
            while j < len(lines) and not TS.match(lines[j]) and not re.match(r"^\w+Error", lines[j]):
                if lines[j].strip().startswith("File"):
                    frames.append(lines[j].strip())
                j += 1
            exc = lines[j].strip()[:110] if j < len(lines) else "?"
            last = re.sub(r'^File "[^"]*[\\/]', "", frames[-1]) if frames else "?"
            c[(last, exc)] += 1
            i = j
        i += 1
    for (frame, exc), n in c.most_common():
        print(f"- **{n}×** `{frame}` → `{exc}`")
    print()


def prefill_waits(P):
    print("## 3. Temps d'espera dels prefills (obertura → prefills llestos)\n")
    print("| Data | Projecte | Minuts | Resultat |")
    print("|---|---|--:|---|")
    start = proj = None; waits = []
    for t, lg, lv, msg, _ in P:
        if m := re.search(r"SmartScan: \d+ entries found in (.+)$", msg):
            start, proj = t, m.group(1).strip(); continue
        if start and ("LLM synthesis" in msg or "Error merging prefills" in msg):
            mins = (t - start).total_seconds() / 60; waits.append(mins)
            print(f"| {start:%m-%d %H:%M} | {proj} | {mins:.1f} | {'CRASH' if 'Error' in msg else 'ok'} |")
            start = None
    if waits:
        w = sorted(waits)
        print(f"\n**{len(w)} obertures** · mediana {w[len(w)//2]:.1f} min · màxim {w[-1]:.1f} min · "
              f"≥5 min en {sum(1 for x in w if x >= 5)} casos\n")


def http_wait(P):
    print("## 4. On van els minuts: espera HTTP per proveïdor i context\n")
    print("(temps entre la línia anterior i la resposta HTTP, atribuït a la línia de log que la consumeix)\n")
    for host, name in HOSTS.items():
        secs = collections.Counter(); n = collections.Counter()
        for i, (t, lg, lv, msg, _) in enumerate(P):
            if lg == "httpx" and host in msg:
                gap = (t - P[i - 1][0]).total_seconds() if i else 0
                ctx = "?"
                for j in range(i + 1, min(i + 4, len(P))):
                    if P[j][1] != "httpx":
                        ctx = P[j][1].replace("automation.", "").replace("web.", "") + ": " + norm(P[j][3])[:48]; break
                secs[ctx] += min(gap, MAX_GAP); n[ctx] += 1
        print(f"### {name} — {sum(secs.values())/60:.0f} min d'espera, {sum(n.values())} crides\n")
        print("| Minuts | Crides | Context |\n|--:|--:|---|")
        for k, v in secs.most_common(8):
            print(f"| {v/60:.1f} | {n[k]} | `{k}` |")
        print()


def vision(P):
    print("## 5. Visió: resultat per proveïdor i tipus\n")
    c = collections.Counter(); reasons = collections.Counter(); prev = None
    for t, lg, lv, msg, _ in P:
        if m := re.search(r"VISION (OK|FAIL) provider=(\w+) .*type=(\w+)", msg):
            c[(m.group(2), m.group(3), m.group(1))] += 1
            if m.group(1) == "FAIL" and prev:
                reasons[(m.group(2), norm(prev)[:70])] += 1
        if lg == "web.vision_groq" and lv == "WARNING":
            prev = msg
    print("| Proveïdor | Tipus | OK | FAIL | % FAIL |\n|---|---|--:|--:|--:|")
    keys = sorted({(p, ty) for p, ty, _ in c})
    for p, ty in keys:
        ok, fail = c[(p, ty, "OK")], c[(p, ty, "FAIL")]
        print(f"| {p} | {ty} | {ok} | {fail} | {100*fail/(ok+fail):.0f}% |")
    print("\n**Motius de FAIL (últim WARNING previ):**\n")
    for (p, r), n in reasons.most_common(10):
        print(f"- {n}× {p}: `{r}`")
    print()


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    lines = load_lines(sys.argv[1:])
    P = parse(lines)
    days = sorted({r[0].date().isoformat() for r in P})
    print(f"# Perfil logs Eva — {days[0]} → {days[-1]} ({len(days)} dies, {len(P)} línies)\n")
    scoreboard(P)
    crash_types(lines)
    prefill_waits(P)
    http_wait(P)
    vision(P)


if __name__ == "__main__":
    main()
