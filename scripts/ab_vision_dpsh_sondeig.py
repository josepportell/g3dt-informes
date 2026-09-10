#!/usr/bin/env python3
"""A/B de models de visió a `dpsh` i `sondeig` amb ground truth (diagnòstic 2026-08-23).

Reutilitza el camí de producció (prompts, renderitzat `_file_to_images`, parser
`_parse_json_response`, pressupost `_max_tokens_for`, context Excel del DPSH) i
només canvia el model / el proveïdor. Tot via OpenRouter (SDK Anthropic amb
`base_url`), perquè la clau Anthropic del `.env` de dev no té crèdit.

Ground truth:
  dpsh    → N20 de l'Excel DPSH (`DPSHExtractor`), cotes de rebuig, aigua.
  sondeig → `validation/eva_reference_values.json` (sondeig_tests, spt_n30,
            spt_depth_range, conclusions_levels_detected, cota_referencia).

Condicions DPSH: `xl` = prompt de producció (inclou "EXCEL COMPARISON DATA");
`raw` = prompt sense l'Excel (mesura la lectura real del manuscrit).

Ús:
    .venv/bin/python scripts/ab_vision_dpsh_sondeig.py run --out DIR WS_PROJECT_DIR...
    .venv/bin/python scripts/ab_vision_dpsh_sondeig.py score --out DIR WS_PROJECT_DIR...
      [--models s46,s5] [--types dpsh,sondeig] [--conds xl,raw] [--ref-root reference-material]

WS_PROJECT_DIR = carpeta de projecte ja processada (té `file_mapping.json`).
Només llegeix els projectes; escriu a --out.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

MODELS = {
    "s46": {"id": "anthropic/claude-sonnet-4.6", "extra": {}},
    "s5": {"id": "anthropic/claude-sonnet-5", "extra": {"thinking": {"type": "disabled"}}},
    "s5low": {"id": "anthropic/claude-sonnet-5",
              "extra": {"thinking": {"type": "adaptive"},
                        "extra_body": {"output_config": {"effort": "low"}}}},
    "o47": {"id": "anthropic/claude-opus-4.7", "extra": {"thinking": {"type": "disabled"}}},
    "h45": {"id": "anthropic/claude-haiku-4.5", "extra": {}},
}
PRICE_PER_M = {  # USD per 1M tokens (in, out) — OpenRouter 2026-08-23
    "s46": (3.0, 15.0), "s5": (2.0, 10.0), "s5low": (2.0, 10.0), "o47": (5.0, 25.0), "h45": (1.0, 5.0),
}


# ---------------------------------------------------------------------------
# Project inputs (same selection as web.vision_groq.run_vision_groq_sync)
# ---------------------------------------------------------------------------

def project_inputs(project_path: Path) -> dict:
    from automation.file_scanner import FileScanner
    mapping = FileScanner(project_path).load()
    if not mapping:
        raise RuntimeError(f"no file_mapping.json in {project_path}")
    out: dict = {"project": project_path.name, "files": {}, "excel": None}
    for role_name, role in mapping.roles.items():
        vt = role.vision_type
        if vt in ("dpsh", "sondeig") and vt not in out["files"]:
            out["files"][vt] = {"role": role_name, "path": str(project_path / role.path)}
    excel_role = mapping.roles.get("dpsh_excel")
    if excel_role:
        out["excel"] = str(project_path / excel_role.path)
    return out


def excel_ground_truth(excel_path: str) -> dict | None:
    from automation.dpsh_extractor import DPSHExtractor
    try:
        return DPSHExtractor(excel_path).extract_all().to_dict()
    except Exception as exc:  # noqa: BLE001
        print(f"  ! Excel GT failed for {excel_path}: {exc}", file=sys.stderr)
        return None


def excel_context(gt: dict | None) -> str:
    if not gt:
        return ""
    return (
        "\n\nEXCEL COMPARISON DATA:\n"
        + json.dumps(gt, indent=2, ensure_ascii=False)
        + "\nCompare each N20 value you extract with the Excel values above."
    )


# ---------------------------------------------------------------------------
# Model call
# ---------------------------------------------------------------------------

def call_model(model_key: str, prompt: str, images: list[str], system_prompt: str, max_tokens: int) -> dict:
    import anthropic
    from web.vision_groq import _parse_json_response

    spec = MODELS[model_key]
    client = anthropic.Anthropic(api_key=os.environ["OPENROUTER_API_KEY"], base_url="https://openrouter.ai/api")
    content: list[dict] = [
        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b}}
        for b in images
    ]
    content.append({"type": "text", "text": prompt})
    meta = {"model": spec["id"], "model_key": model_key, "max_tokens": max_tokens, "n_images": len(images)}
    t0 = time.monotonic()
    try:
        resp = client.messages.create(
            model=spec["id"], max_tokens=max_tokens, system=system_prompt,
            messages=[{"role": "user", "content": content}], **spec["extra"],
        )
        meta["elapsed_s"] = round(time.monotonic() - t0, 1)
        meta["stop_reason"] = getattr(resp, "stop_reason", None)
        meta["in_tokens"] = resp.usage.input_tokens
        meta["out_tokens"] = resp.usage.output_tokens
        text = "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text")
        meta["reply_len"] = len(text)
        try:
            result = _parse_json_response(text)
            meta["ok"] = True
        except Exception as exc:  # noqa: BLE001
            result = None
            meta["ok"] = False
            meta["error"] = f"parse: {exc}"[:300]
    except Exception as exc:  # noqa: BLE001
        meta["elapsed_s"] = round(time.monotonic() - t0, 1)
        meta["ok"] = False
        meta["error"] = f"{type(exc).__name__}: {exc}"[:300]
        result = None
    return {"meta": meta, "result": result}


def run(args) -> None:
    from automation.validation.prompts import (
        DPSH_EXTRACTION_PROMPT, EXTRACTION_SYSTEM_PROMPT, SONDEIG_EXTRACTION_PROMPT,
    )
    from web.vision_groq import _file_to_images, _max_tokens_for

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    jobs: list[dict] = []  # one per (project, type, cond)
    for p in args.projects:
        pp = Path(p)
        info = project_inputs(pp)
        tag = pp.name[:7]
        gt = excel_ground_truth(info["excel"]) if info["excel"] else None
        if gt:
            (out / f"{tag}_dpsh_excel_gt.json").write_text(json.dumps(gt, indent=1, ensure_ascii=False), encoding="utf-8")
        for vtype in args.types:
            f = info["files"].get(vtype)
            if not f:
                print(f"  - {tag}: no {vtype} file in mapping", file=sys.stderr)
                continue
            images = _file_to_images(Path(f["path"]), max_pages=5)
            if not images:
                print(f"  - {tag}: {vtype} rendered 0 images ({f['path']})", file=sys.stderr)
                continue
            conds = args.conds if vtype == "dpsh" else ["-"]
            for cond in conds:
                prompt = SONDEIG_EXTRACTION_PROMPT if vtype == "sondeig" else DPSH_EXTRACTION_PROMPT
                if vtype == "dpsh" and cond == "xl":
                    prompt = prompt + excel_context(gt)
                jobs.append({"tag": tag, "vtype": vtype, "cond": cond, "file": Path(f["path"]).name,
                             "images": images, "prompt": prompt,
                             "max_tokens": _max_tokens_for(vtype, provider="anthropic")})
    print(f"{len(jobs)} jobs × {len(args.models)} models", file=sys.stderr)

    def worker(model_key: str) -> None:
        for j in jobs:
            name = f"{j['tag']}_{j['vtype']}_{j['cond']}_{model_key}.json"
            dest = out / name
            if dest.exists() and not args.force:
                continue
            r = call_model(model_key, j["prompt"], j["images"], EXTRACTION_SYSTEM_PROMPT, j["max_tokens"])
            r["meta"].update({"tag": j["tag"], "vtype": j["vtype"], "cond": j["cond"], "file": j["file"]})
            dest.write_text(json.dumps(r, indent=1, ensure_ascii=False), encoding="utf-8")
            m = r["meta"]
            print(f"  {name}: ok={m.get('ok')} {m.get('elapsed_s')}s out={m.get('out_tokens')} "
                  f"stop={m.get('stop_reason')} {m.get('error','')}", file=sys.stderr)

    threads = [threading.Thread(target=worker, args=(mk,)) for mk in args.models]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _norm_id(s) -> str:
    s = str(s or "").upper().replace(" ", "")
    m = re.match(r"^([A-Z]+)-?(\d+)$", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2))}"
    m = re.search(r"P-?(\d+)$", s)  # "S2-P5" → "P-5"
    return f"P-{int(m.group(1))}" if m else s


def _num(v):
    if v is None:
        return None
    try:
        return float(str(v).replace(",", ".").replace("+", "").strip())
    except ValueError:
        return None


def score_dpsh(gt: dict, res: dict | None) -> dict:
    s = {"gt_readings": 0, "match": 0, "wrong": 0, "missing": 0, "illegible": 0, "extra": 0,
         "tests_gt": 0, "tests_found": 0, "refusal_match": 0, "refusal_gt": 0, "water_match": 0}
    gt_tests = {_norm_id(t["test_id"]): t for t in gt.get("tests", [])}
    s["tests_gt"] = len(gt_tests)
    if not res:
        for t in gt_tests.values():
            s["gt_readings"] += len(t["readings"]); s["missing"] += len(t["readings"])
        return s
    vis_list = res.get("dpsh_tests") or []
    vis_tests = {_norm_id(t.get("test_id")): t for t in vis_list}
    if not (set(vis_tests) & set(gt_tests)) and len(vis_list) >= 1:
        # ids no coincideixen (p. ex. Excel "P-1.1"/"P-1.2" vs full "P-1"/"P-2"): alinea per ordre
        vis_tests = {tid: vis_list[i] for i, tid in enumerate(gt_tests) if i < len(vis_list)}
        s["aligned_by_order"] = True
    for tid, t in gt_tests.items():
        gt_r = {round(abs(float(r["depth_m"])), 2): r["n20"] for r in t["readings"]}
        s["gt_readings"] += len(gt_r)
        if t.get("refusal_depth_m") is not None:
            s["refusal_gt"] += 1
        v = vis_tests.get(tid)
        if not v:
            s["missing"] += len(gt_r)
            continue
        s["tests_found"] += 1
        vis_r = {}
        for r in v.get("readings") or []:
            d = _num(r.get("depth_m"))
            if d is not None:
                vis_r[round(abs(d), 2)] = r.get("n20")
        for d, n in gt_r.items():
            if d not in vis_r:
                s["missing"] += 1
            elif str(vis_r[d]).strip() in ("??", "", "None"):
                s["illegible"] += 1
            else:
                try:
                    vn = int(float(str(vis_r[d]).replace("R", "100")))
                except ValueError:
                    s["illegible"] += 1; continue
                if vn == int(n):
                    s["match"] += 1
                else:
                    s["wrong"] += 1
        s["extra"] += len(set(vis_r) - set(gt_r))
        rg, rv = t.get("refusal_depth_m"), _num(v.get("refusal_depth_m"))
        if rg is not None and rv is not None and abs(abs(rv) - rg) <= 0.051:
            s["refusal_match"] += 1
        wg = bool(t.get("water_detected")); wv = bool(v.get("water_detected"))
        if wg == wv:
            s["water_match"] += 1
    return s


_LEVEL_WORDS = {"un": 1, "sol": 1, "sòl": 1, "dos": 2, "tres": 3, "quatre": 4, "cinc": 5}


def eva_levels(eva_vars: dict) -> int | None:
    txt = str((eva_vars.get("conclusions_levels_detected") or {}).get("value") or "").lower()
    m = re.search(r"detect(?:a|en)\s+(\w+)\s+(?:sòl\s+)?nivell", txt)
    if m:
        return _LEVEL_WORDS.get(m.group(1))
    return None


def score_sondeig(eva_vars: dict, res: dict | None) -> dict:
    s = {}
    st = (eva_vars.get("sondeig_tests") or {}).get("value") or []
    st0 = st[0] if st else {}
    gt = {
        "depth": abs(_num(st0.get("depth")) or 0) or None,
        "cota": _num(st0.get("cota")) or _num((eva_vars.get("cota_referencia") or {}).get("value")),
        "levels": eva_levels(eva_vars),
        "n_spt": _num((eva_vars.get("spt_n30") or {}).get("value")),
        "spt_range": str((eva_vars.get("spt_depth_range") or {}).get("value") or ""),
        "water": "detect" in str(st0.get("water", "")).lower() and "no detect" not in str(st0.get("water", "")).lower(),
    }
    s["gt"] = gt
    if not res:
        s["ok"] = False
        return s
    v = (res.get("sondeig_tests") or [{}])[0]
    spt = (v.get("spt_results") or [{}])[0]
    rng = ""
    if spt.get("depth_from_m") is not None:
        rng = f"-{float(spt['depth_from_m']):.2f} a {float(spt['depth_to_m']):.2f}" if spt.get("depth_to_m") is not None else ""
    got = {
        "depth": _num(v.get("total_depth_m")),
        "cota": _num(v.get("elevation_z")),
        "levels": v.get("num_geological_levels"),
        "n_spt": _num(spt.get("n_spt")),
        "spt_range": rng,
        "water": v.get("water_level_m") is not None,
        "n_layers": len(v.get("layers") or []),
    }
    s["got"] = got
    s["ok"] = True
    s["depth_ok"] = gt["depth"] is not None and got["depth"] is not None and abs(gt["depth"] - got["depth"]) <= 0.051
    s["cota_ok"] = gt["cota"] is not None and got["cota"] is not None and abs(gt["cota"] - got["cota"]) <= 0.051
    s["levels_ok"] = gt["levels"] is not None and got["levels"] == gt["levels"]
    s["nspt_ok"] = gt["n_spt"] is not None and got["n_spt"] == gt["n_spt"]
    gr = re.findall(r"\d+[.,]\d+", gt["spt_range"]); vr = re.findall(r"\d+[.,]\d+", got["spt_range"])
    s["spt_range_ok"] = bool(gr) and [float(x.replace(",", ".")) for x in gr] == [float(x.replace(",", ".")) for x in vr]
    s["water_ok"] = gt["water"] == got["water"]
    return s


def _eva_ref(tag: str, ref_root: Path, projects: list[Path]) -> dict:
    for p in projects:
        if p.name.startswith(tag):
            f = p / "validation" / "eva_reference_values.json"
            if f.exists():
                return json.loads(f.read_text(encoding="utf-8")).get("variables", {})
    for d in ref_root.glob(f"{tag}*"):
        f = d / "validation" / "eva_reference_values.json"
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8")).get("variables", {})
    return {}


def score(args) -> None:
    out = Path(args.out)
    projects = [Path(p) for p in args.projects]
    ref_root = Path(args.ref_root)
    lines: list[str] = []
    P = lines.append
    P("# A/B visió `dpsh` / `sondeig` — Sonnet 5 vs 4.6 (OpenRouter)\n")

    # --- DPSH
    if "dpsh" in args.types:
        P("## DPSH — N20 vs Excel (ground truth)\n")
        P("| Projecte | cond | model | tests | lect. GT | = | ≠ | ?? | falta | rebuig ok | aigua ok | s | tok out | $ |")
        P("|---|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
        agg: dict = {}
        for p in projects:
            tag = p.name[:7]
            gtf = out / f"{tag}_dpsh_excel_gt.json"
            if not gtf.exists():
                continue
            gt = json.loads(gtf.read_text(encoding="utf-8"))
            for cond in args.conds:
                for mk in args.models:
                    f = out / f"{tag}_dpsh_{cond}_{mk}.json"
                    if not f.exists():
                        continue
                    r = json.loads(f.read_text(encoding="utf-8"))
                    m, sc = r["meta"], score_dpsh(gt, r.get("result"))
                    cost = (m.get("in_tokens", 0) * PRICE_PER_M[mk][0] + m.get("out_tokens", 0) * PRICE_PER_M[mk][1]) / 1e6
                    P(f"| {tag} | {cond} | {mk} | {sc['tests_found']}/{sc['tests_gt']} | {sc['gt_readings']} | {sc['match']} | {sc['wrong']} | "
                      f"{sc['illegible']} | {sc['missing']} | {sc['refusal_match']}/{sc['refusal_gt']} | {sc['water_match']}/{sc['tests_gt']} | "
                      f"{m.get('elapsed_s')} | {m.get('out_tokens')} | {cost:.3f} |" + ("" if m.get("ok") else f" ERR {m.get('error')}"))
                    a = agg.setdefault((cond, mk), {"gt": 0, "match": 0, "wrong": 0, "ill": 0, "miss": 0, "ref": 0, "refgt": 0, "s": [], "cost": 0.0, "n": 0, "err": 0})
                    a["gt"] += sc["gt_readings"]; a["match"] += sc["match"]; a["wrong"] += sc["wrong"]; a["ill"] += sc["illegible"]
                    a["miss"] += sc["missing"]; a["ref"] += sc["refusal_match"]; a["refgt"] += sc["refusal_gt"]
                    a["s"].append(m.get("elapsed_s") or 0); a["cost"] += cost; a["n"] += 1; a["err"] += 0 if m.get("ok") else 1
        P("\n### Agregat DPSH\n")
        P("| cond | model | crides | err | lect. GT | = (%) | ≠ | ?? | falta | rebuig | s mediana | s total | $ total |")
        P("|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
        for (cond, mk), a in sorted(agg.items()):
            ss = sorted(a["s"]); med = ss[len(ss) // 2] if ss else 0
            pct = 100 * a["match"] / a["gt"] if a["gt"] else 0
            P(f"| {cond} | {mk} | {a['n']} | {a['err']} | {a['gt']} | {a['match']} ({pct:.1f}%) | {a['wrong']} | {a['ill']} | {a['miss']} | "
              f"{a['ref']}/{a['refgt']} | {med} | {sum(ss):.0f} | {a['cost']:.2f} |")

    # --- Sondeig
    if "sondeig" in args.types:
        P("\n## Sondeig — vs informe d'Eva (eva_reference_values.json)\n")
        P("| Projecte | model | prof. (GT→vis) | cota (GT→vis) | nivells (GT→vis) | N SPT (GT→vis) | rang SPT | aigua | capes | s | tok out |")
        P("|---|---|---|---|---|---|---|---|--:|--:|--:|")
        agg2: dict = {}
        for p in projects:
            tag = p.name[:7]
            eva = _eva_ref(tag, ref_root, projects)
            for mk in args.models:
                f = out / f"{tag}_sondeig_-_{mk}.json"
                if not f.exists():
                    continue
                r = json.loads(f.read_text(encoding="utf-8"))
                m, sc = r["meta"], score_sondeig(eva, r.get("result"))
                if not sc.get("ok"):
                    P(f"| {tag} | {mk} | ERR {m.get('error')} | | | | | | | {m.get('elapsed_s')} | |")
                    continue
                g, v = sc["gt"], sc["got"]
                def cell(ok, a, b):
                    return f"{'✅' if ok else '❌'} {a}→{b}"
                P(f"| {tag} | {mk} | {cell(sc['depth_ok'], g['depth'], v['depth'])} | {cell(sc['cota_ok'], g['cota'], v['cota'])} | "
                  f"{cell(sc['levels_ok'], g['levels'], v['levels'])} | {cell(sc['nspt_ok'], g['n_spt'], v['n_spt'])} | "
                  f"{cell(sc['spt_range_ok'], g['spt_range'], v['spt_range'])} | {cell(sc['water_ok'], g['water'], v['water'])} | {v['n_layers']} | "
                  f"{m.get('elapsed_s')} | {m.get('out_tokens')} |")
                a = agg2.setdefault(mk, {"n": 0, "depth": 0, "cota": 0, "levels": 0, "nspt": 0, "rng": 0, "water": 0, "s": []})
                a["n"] += 1; a["s"].append(m.get("elapsed_s") or 0)
                for k in ("depth", "cota", "levels", "nspt", "water"):
                    a[k] += int(bool(sc[f"{k}_ok"]))
                a["rng"] += int(bool(sc["spt_range_ok"]))
        P("\n### Agregat sondeig\n")
        P("| model | n | prof. ok | cota ok | nivells ok | N SPT ok | rang SPT ok | aigua ok | s mediana |")
        P("|---|--:|--:|--:|--:|--:|--:|--:|--:|")
        for mk, a in sorted(agg2.items()):
            ss = sorted(a["s"]); med = ss[len(ss) // 2] if ss else 0
            P(f"| {mk} | {a['n']} | {a['depth']} | {a['cota']} | {a['levels']} | {a['nspt']} | {a['rng']} | {a['water']} | {med} |")
    print("\n".join(lines))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["run", "score"])
    ap.add_argument("projects", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--models", default="s46,s5")
    ap.add_argument("--types", default="dpsh,sondeig")
    ap.add_argument("--conds", default="xl,raw")
    ap.add_argument("--ref-root", default=str(Path(__file__).resolve().parent.parent / "reference-material"))
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    args.models = args.models.split(","); args.types = args.types.split(","); args.conds = args.conds.split(",")
    if args.cmd == "run":
        run(args)
    else:
        score(args)


if __name__ == "__main__":
    main()
