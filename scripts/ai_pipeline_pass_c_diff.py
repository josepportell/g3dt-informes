#!/usr/bin/env python3
"""Pass C effectiveness diff — does the group-revision pass earn its keep?

For each concept where Pass C reordered the ranking
(`revised_by_group_pass=True`), compare:
  - Original Pass A top-1 (read from the per-concept Pass A cache)
  - Revised Pass C top-1 (current ranking in ai_ranking.json)
  - Eva ground truth (validation/eva_reference_values.json)

Outputs a verdict per concept:
  - `better`  — revised matches Eva, original didn't
  - `worse`   — original matched Eva, revised lost it
  - `neutral` — Eva matches both or neither (no behavioural change vs Eva)
  - `no_eva_ref` — no ground truth available

Usage:
  python scripts/ai_pipeline_pass_c_diff.py --project 4001670
  python scripts/ai_pipeline_pass_c_diff.py --project 4001670 --save
  python scripts/ai_pipeline_pass_c_diff.py --all --save
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from automation.ai_pipeline.ranking import (
    ConceptRanking,
    ProjectRanking,
    load_ranking,
)
from automation.ai_pipeline.trace import _load_template_aliases


REFERENCE_ROOT = Path(__file__).parent.parent / "reference-material"
DIAGNOSTICS_DIR = Path(__file__).parent.parent / "docs" / "diagnostics"

_SLUG_RE = re.compile(r"[^A-Za-z0-9]+")


def _slugify(s: str) -> str:
    """Mirror automation.ai_pipeline.ranking._slugify."""
    slug = _SLUG_RE.sub("_", s).strip("_")
    return slug or "unnamed"


# ─── Loading helpers ────────────────────────────────────────────────────


def _resolve_project(project: str) -> Path:
    """Resolve --project arg (id, prefix, or absolute path) to a directory."""
    p = Path(project)
    if p.is_absolute() and p.is_dir():
        return p
    candidate = REFERENCE_ROOT / project
    if candidate.is_dir():
        return candidate
    matches = [
        d for d in REFERENCE_ROOT.iterdir()
        if d.is_dir() and d.name.startswith(project)
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise SystemExit(
            f"Ambiguous --project {project!r}; matches:\n"
            + "\n".join(f"  - {d.name}" for d in matches)
        )
    raise SystemExit(f"No project matches {project!r}")


def load_original_pass_a(pp: Path, concept_id: str) -> ConceptRanking | None:
    """Read the pre-revision Pass A ranking from the per-concept cache file."""
    cache_file = (
        pp / "validation" / "ai_pipeline" / "ranking"
        / f"{_slugify(concept_id)}_cache.json"
    )
    if not cache_file.is_file():
        return None
    try:
        payload = json.loads(cache_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    raw = payload.get("ranking")
    if not isinstance(raw, dict):
        return None
    try:
        return ConceptRanking.model_validate(raw)
    except Exception:
        return None


def load_eva_reference(pp: Path) -> dict[str, Any]:
    """Read validation/eva_reference_values.json variables, or {} if absent."""
    p = pp / "validation" / "eva_reference_values.json"
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data.get("variables", {}) or {}


# ─── Comparison ─────────────────────────────────────────────────────────


def _norm_value(v: Any) -> str:
    """Normalise a value for loose equality (case/whitespace-insensitive)."""
    if v is None:
        return ""
    return re.sub(r"\s+", " ", str(v)).strip().lower()


def _matches_eva(candidate_value: Any, eva_value: Any) -> bool:
    """Loose match: equal after normalisation, or one contains the other.

    Eva's reference often captures a full narrative paragraph where the
    candidate is the underlying value. A substring check on either side covers
    that without overfitting.
    """
    cv = _norm_value(candidate_value)
    ev = _norm_value(eva_value)
    if not cv or not ev:
        return False
    if cv == ev:
        return True
    if cv in ev or ev in cv:
        return True
    return False


def verdict_for(
    original_top1: Any,
    revised_top1: Any,
    eva_value: Any,
) -> str:
    """Return the verdict label for a single reorder."""
    if eva_value is None:
        return "no_eva_ref"
    orig_match = _matches_eva(original_top1, eva_value)
    rev_match = _matches_eva(revised_top1, eva_value)
    if rev_match and not orig_match:
        return "better"
    if orig_match and not rev_match:
        return "worse"
    return "neutral"


# ─── Project diff ──────────────────────────────────────────────────────


def _resolve_eva_entry(
    eva_vars: dict[str, Any],
    concept_id: str,
    aliases_map: dict[str, list[str]],
) -> dict | None:
    """Look up Eva's reference entry for a concept, trying canonical name
    then template-placeholder aliases."""
    entry = eva_vars.get(concept_id)
    if isinstance(entry, dict):
        return entry
    for alias in aliases_map.get(concept_id, []):
        if alias and alias != concept_id:
            entry = eva_vars.get(alias)
            if isinstance(entry, dict):
                return entry
    return None


def diff_project(pp: Path) -> dict:
    """Compute Pass C verdicts for one project."""
    ranking = load_ranking(pp)
    if ranking is None:
        return {
            "project": pp.name,
            "error": "no ai_ranking.json — run Stage 5 first",
            "rows": [],
        }
    eva_vars = load_eva_reference(pp)
    aliases_map = _load_template_aliases()

    rows: list[dict] = []
    for cid, cr in sorted(ranking.concepts.items()):
        if not cr.revised_by_group_pass:
            continue
        original = load_original_pass_a(pp, cid)
        if original is None or not original.ranked:
            continue
        if not cr.ranked:
            continue
        original_top1 = original.ranked[0].value
        revised_top1 = cr.ranked[0].value
        if _norm_value(original_top1) == _norm_value(revised_top1):
            # Same top-1 value (Pass C reordered tail only). Skip.
            continue

        eva_entry = _resolve_eva_entry(eva_vars, cid, aliases_map)
        eva_value = eva_entry.get("value") if isinstance(eva_entry, dict) else None
        v = verdict_for(original_top1, revised_top1, eva_value)
        rows.append(
            {
                "concept_id": cid,
                "original_top1": original_top1,
                "revised_top1": revised_top1,
                "eva": eva_value,
                "verdict": v,
            }
        )

    counts = {"better": 0, "worse": 0, "neutral": 0, "no_eva_ref": 0}
    for r in rows:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1

    return {
        "project": pp.name,
        "project_path": str(pp),
        "rows": rows,
        "counts": counts,
        "total_revised_concepts": sum(
            1 for c in ranking.concepts.values() if c.revised_by_group_pass
        ),
    }


# ─── Output ────────────────────────────────────────────────────────────


def _truncate(v: Any, n: int = 60) -> str:
    s = "" if v is None else str(v)
    s = s.replace("\n", " ").replace("|", "/")
    if len(s) > n:
        return s[: n - 1] + "…"
    return s


def render_markdown(diff: dict) -> str:
    lines: list[str] = []
    lines.append(f"# Pass C effectiveness — {diff['project']}")
    lines.append("")
    if diff.get("error"):
        lines.append(f"_{diff['error']}_")
        lines.append("")
        return "\n".join(lines)

    rows = diff["rows"]
    counts = diff["counts"]
    if not rows:
        lines.append(
            f"_{diff.get('total_revised_concepts', 0)} concepts marked "
            "`revised_by_group_pass=True`, but Pass C did not change any "
            "top-1 value._"
        )
        lines.append("")
        return "\n".join(lines)

    lines.append("| concept_id | original top-1 | revised top-1 | eva | verdict |")
    lines.append("|---|---|---|---|---|")
    for r in rows:
        verdict = r["verdict"]
        verdict_md = (
            f"**{verdict}**" if verdict in ("better", "worse") else verdict
        )
        lines.append(
            f"| {r['concept_id']} | {_truncate(r['original_top1'])} | "
            f"{_truncate(r['revised_top1'])} | {_truncate(r['eva'])} | "
            f"{verdict_md} |"
        )

    lines.append("")
    summary = (
        f"Summary: {len(rows)} reorderings — "
        f"{counts['better']} better, {counts['worse']} worse, "
        f"{counts['neutral']} neutral, {counts['no_eva_ref']} no_eva_ref."
    )
    lines.append(summary)
    lines.append("")
    return "\n".join(lines)


def render_aggregate(diffs: list[dict]) -> str:
    lines: list[str] = []
    lines.append("# Pass C effectiveness — aggregate")
    lines.append("")
    totals = {"better": 0, "worse": 0, "neutral": 0, "no_eva_ref": 0, "rows": 0}
    lines.append("| project | reorderings | better | worse | neutral | no_eva_ref |")
    lines.append("|---|---|---|---|---|---|")
    for d in diffs:
        if d.get("error"):
            lines.append(f"| {d['project']} | _{d['error']}_ | | | | |")
            continue
        c = d["counts"]
        lines.append(
            f"| {d['project']} | {len(d['rows'])} | "
            f"{c['better']} | {c['worse']} | {c['neutral']} | {c['no_eva_ref']} |"
        )
        totals["rows"] += len(d["rows"])
        for k in ("better", "worse", "neutral", "no_eva_ref"):
            totals[k] += c.get(k, 0)
    lines.append(
        f"| **TOTAL** | **{totals['rows']}** | "
        f"**{totals['better']}** | **{totals['worse']}** | "
        f"**{totals['neutral']}** | **{totals['no_eva_ref']}** |"
    )
    lines.append("")
    return "\n".join(lines)


# ─── CLI ───────────────────────────────────────────────────────────────


def _save_report(content: str, project_name: str) -> Path:
    DIAGNOSTICS_DIR.mkdir(parents=True, exist_ok=True)
    date = datetime.now().strftime("%Y-%m-%d")
    safe_name = _slugify(project_name)
    out = DIAGNOSTICS_DIR / f"pass_c_effectiveness_{safe_name}_{date}.md"
    out.write_text(content, encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--project", help="Project ID, prefix, or path.")
    parser.add_argument(
        "--all", action="store_true",
        help="Process all reference projects with an ai_ranking.json.",
    )
    parser.add_argument(
        "--save", action="store_true",
        help="Write the report to docs/diagnostics/.",
    )
    args = parser.parse_args()

    if not args.project and not args.all:
        parser.error("Must pass --project or --all")

    if args.all:
        diffs = []
        for d in sorted(REFERENCE_ROOT.iterdir()):
            if not d.is_dir():
                continue
            if not (d / "validation" / "ai_ranking.json").is_file():
                continue
            diffs.append(diff_project(d))

        for d in diffs:
            md = render_markdown(d)
            print(md)
        agg = render_aggregate(diffs)
        print(agg)
        if args.save:
            payload = "\n\n".join(
                [render_markdown(d) for d in diffs] + [agg]
            )
            out = _save_report(payload, "all_projects")
            print(f"\nSaved: {out}", file=sys.stderr)
        return 0

    pp = _resolve_project(args.project)
    diff = diff_project(pp)
    md = render_markdown(diff)
    print(md)
    if args.save:
        out = _save_report(md, pp.name)
        print(f"\nSaved: {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
