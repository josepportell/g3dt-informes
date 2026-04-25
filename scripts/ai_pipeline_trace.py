#!/usr/bin/env python3
"""AI pipeline diagnostic trace — read-only join over Stages 1-5 manifests.

Usage:
    python scripts/ai_pipeline_trace.py --project 4001670 --all
    python scripts/ai_pipeline_trace.py --project 4001670 --concept expedient
    python scripts/ai_pipeline_trace.py --project 4001670 --source 26.0049/A.01.pdf
    python scripts/ai_pipeline_trace.py --project 4001670 --decisions
    python scripts/ai_pipeline_trace.py --project 4001670 --issues-only
    python scripts/ai_pipeline_trace.py --project 4001670 --save --report markdown
    python scripts/ai_pipeline_trace.py --project 4001670 --diff prior_trace.json
    python scripts/ai_pipeline_trace.py --project 4001670 --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from automation.ai_pipeline.trace import (  # noqa: E402
    PipelineTrace,
    build_trace,
    diff_traces,
    load_trace,
    save_trace,
)


REFERENCE_ROOT = Path(__file__).parent.parent / "reference-material"


# ─── Project resolution ────────────────────────────────────────────────


def _resolve_project(project: str | None, project_path: str | None) -> Path:
    if project_path:
        p = Path(project_path)
        if not p.is_absolute():
            p = (Path.cwd() / p).resolve()
        if not p.is_dir():
            raise SystemExit(f"Project path does not exist: {p}")
        return p
    if not project:
        raise SystemExit("Must provide --project or --project-path")

    candidate = REFERENCE_ROOT / project
    if candidate.is_dir():
        return candidate
    matches = [
        d for d in REFERENCE_ROOT.iterdir() if d.is_dir() and d.name.startswith(project)
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise SystemExit(
            f"Ambiguous --project {project!r}; matches:\n"
            + "\n".join(f"  - {d.name}" for d in matches)
        )
    raise SystemExit(f"No project matches {project!r} under {REFERENCE_ROOT}")


# ─── Human-readable printers ───────────────────────────────────────────


def _print_top_issues(trace: PipelineTrace, limit: int = 30) -> None:
    print(f"\n## Top issues to investigate (capped at {limit})")
    if not trace.top_issues:
        print("  (none)")
        return
    for i, issue in enumerate(trace.top_issues[:limit], 1):
        target = issue.get("concept_id") or issue.get("source_path") or "?"
        also = issue.get("also_flagged") or []
        also_suffix = f"  (also: {', '.join(also)})" if also else ""
        print(
            f"  {i:>2}. [{issue['signal_strength']:.2f}] {issue['kind']} — {target}{also_suffix}"
        )
        print(f"       {issue['description']}")
        print(f"       → {issue['suggested_action']}")


def _print_stage_health(trace: PipelineTrace) -> None:
    print("\n## Per-stage health")
    for label, summary in (
        ("Stage 1 (Inventari)", trace.stage1_summary),
        ("Stage 2 (Tipologia)", trace.stage2_summary),
        ("Stage 3 (Conversió)", trace.stage3_summary),
        ("Stage 4 (Anàlisi)", trace.stage4_summary),
        ("Stage 5 (Rànquing)", trace.stage5_summary),
    ):
        if not summary.get("available"):
            print(f"  {label}: (manifest absent)")
            continue
        print(f"  {label}:")
        for k, v in summary.items():
            if k == "available":
                continue
            if isinstance(v, dict):
                v = ", ".join(f"{kk}={vv}" for kk, vv in sorted(v.items()))
            print(f"    {k}: {v}")
    if trace.eva_summary:
        print("  Eva ground truth:")
        for k, v in trace.eva_summary.items():
            print(f"    {k}: {v}")


def _print_concept(trace: PipelineTrace, concept_id: str) -> int:
    j = trace.concepts.get(concept_id)
    if j is None:
        print(f"Concept {concept_id!r} not found in trace.", file=sys.stderr)
        return 1
    print(f"\n# Concept journey — {concept_id}")
    print(f"Group: {j.group}    Final status: {j.final_status}")
    print(f"Picker action: {j.picker_action} ({j.picker_rationale})")
    print(f"Source agreement: {j.source_agreement}")
    if j.domain_flags:
        print("Domain flags:")
        for f in j.domain_flags:
            print(f"  • {f}")
    print(f"\nCandidates ({len(j.candidates)}):")
    for c in j.candidates:
        print(
            f"  - {c.candidate_id}\n"
            f"    value={c.value!r}  conf={c.confidence:.2f}  source={c.source_path}"
        )
        if c.quote:
            quote_short = c.quote.replace("\n", " ")[:120]
            print(f"    quote: {quote_short}")
    if j.final_ranked:
        print("\nRanking:")
        for i, rc in enumerate(j.final_ranked, 1):
            print(
                f"  {i}. {rc.value!r}  (source={rc.source_path}, conf={rc.confidence:.2f})"
            )
            if rc.rationale:
                print(f"     rationale: {rc.rationale[:200]}")
    if j.final_has_conflict:
        print(f"\n⚠ has_conflict: {j.final_conflict_note[:300]}")
    if j.group_factors_mentioning:
        print("\nGroup factors mentioning this concept (Pass B):")
        for f in j.group_factors_mentioning:
            print(f"  • affects={f.get('affects')}: {f.get('description', '')[:200]}")
    if j.group_revision_flag:
        print(f"\nGroup revision flag: {j.group_revision_flag}")
    if j.revised_by_group_pass:
        print(f"Pass C reordering applied. Factor: {j.group_factor_considered[:200]}")
    elif j.no_change_guardrail_fired:
        print(
            f"Pass C no-change guardrail fired. Factor considered: "
            f"{j.group_factor_considered[:200]}"
        )
    if j.eva_top1_match != "no_ground_truth":
        print("\nEva ground truth:")
        print(f"  eva_value: {j.eva_value!r}")
        print(f"  match status: {j.eva_top1_match}")
        if j.eva_rank_in_ranked is not None:
            print(f"  Eva's value sits at rank {j.eva_rank_in_ranked}")
        else:
            print("  Eva's value is not present in the ranked list.")
    return 0


def _print_source(trace: PipelineTrace, source_path: str) -> int:
    j = trace.sources.get(source_path)
    if j is None:
        # Fuzzy: substring match.
        matches = [k for k in trace.sources if source_path.lower() in k.lower()]
        if len(matches) == 1:
            j = trace.sources[matches[0]]
            source_path = matches[0]
        elif len(matches) > 1:
            print("Multiple sources match. Did you mean:", file=sys.stderr)
            for m in matches[:10]:
                print(f"  - {m}", file=sys.stderr)
            return 1
        else:
            print(f"Source {source_path!r} not found in trace.", file=sys.stderr)
            return 1
    print(f"\n# Source journey — {source_path}")
    if j.inventory:
        print(f"Inventory: type={j.inventory.get('type')} size_kb={j.inventory.get('size_kb')}")
    if j.typology:
        print(
            f"Typology: category={j.typology.get('category')} "
            f"useful={j.typology.get('useful')} "
            f"strategy={j.typology.get('conversion_strategy')}"
        )
    print(f"Stage 3 artifacts: {len(j.artifacts)}")
    for a in j.artifacts[:10]:
        print(
            f"  • {a.get('path')} ({a.get('format')}) "
            f"page={a.get('page')} sheet={a.get('sheet')} "
            f"skipped={a.get('skipped')}"
        )
    if j.insight:
        print(
            f"Stage 4 insight: type={j.insight.document_type} "
            f"author={j.insight.author!r} confidence={j.insight.confidence:.2f}"
        )
        if j.insight.purpose:
            print(f"  purpose: {j.insight.purpose[:200]}")
    print(f"Stage 4 candidates emitted: {len(j.candidates_emitted)}")
    for c in j.candidates_emitted[:15]:
        print(
            f"  • {c['concept_id']} = {c['value']!r} (conf={c['confidence']:.2f})"
        )
    if j.pass4_failure:
        print(f"Stage 4 FAILURE: {j.pass4_failure}")
    if j.rankings_contributed_to:
        print("Stage 5 contributions:")
        for entry in j.rankings_contributed_to[:20]:
            print(
                f"  • {entry['concept_id']}: rank {entry['rank']}/{entry['rank_total']}"
                f" (revised={entry['was_revised']})"
            )
    return 0


def _print_decisions(trace: PipelineTrace) -> None:
    d = trace.decisions
    print("\n## Decision audit")
    print(f"Stage 2 dev-only skips: {len(d.stage2_dev_only_skips)}")
    for s in d.stage2_dev_only_skips[:10]:
        print(f"  • {s['path']} — {s['reason']}")
    print(f"Stage 2 logo skips: {len(d.stage2_logo_skips)}")
    for s in d.stage2_logo_skips[:10]:
        print(f"  • {s['path']} — {s['reason']}")
    print(f"Stage 3 conversion failures: {len(d.stage3_conversion_failures)}")
    for s in d.stage3_conversion_failures[:10]:
        print(
            f"  • {s['source_path']} (strategy={s['strategy_used']}): {s['skip_reason']}"
        )
    print(f"Stage 4 retried sources: {len(d.stage4_retried_sources)}")
    for s in d.stage4_retried_sources[:10]:
        print(f"  • {s['source_path']} — attempts={s['attempts']}")
    print(f"Stage 4 failed sources: {len(d.stage4_failed_sources)}")
    for s in d.stage4_failed_sources[:10]:
        print(f"  • {s['source_path']} ({s['error_type']}): {s['last_error'][:120]}")
    print(f"Stage 5 Pass A retries: {len(d.stage5_pass_a_retries)}")
    print(
        f"Stage 5 Pass B revisions flagged per group: {dict(d.stage5_pass_b_revisions_flagged)}"
    )
    print(
        f"Stage 5 Pass C no-change guardrails: {len(d.stage5_pass_c_no_change_guardrails)}"
    )
    print(
        f"Stage 5 Pass C reorderings: {len(d.stage5_pass_c_reorderings)}"
    )
    if d.instrumentation_gaps:
        print("\nInstrumentation gaps (cannot be derived from current manifests):")
        for g in d.instrumentation_gaps:
            print(f"  • {g}")


# ─── Markdown report ───────────────────────────────────────────────────


def _md_escape(s: str) -> str:
    return s.replace("|", "\\|")


def _slug(s: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("._-")
    return cleaned or "unnamed"


def _build_markdown_report(trace: PipelineTrace) -> str:
    lines: list[str] = []
    lines.append(f"# AI Pipeline Trace — {trace.project_name}")
    lines.append(f"Generated: {trace.generated_at}")
    lines.append("")

    # Executive summary.
    lines.append("## Executive summary")
    if trace.stage1_summary.get("available"):
        s1 = trace.stage1_summary
        lines.append(
            f"- **Stage 1**: {s1.get('total_files')} files, "
            f"{s1.get('msg_count')} .msg, "
            f"{s1.get('extracted_attachments')} extracted attachments"
        )
    if trace.stage2_summary.get("available"):
        s2 = trace.stage2_summary
        lines.append(
            f"- **Stage 2**: {s2.get('useful')} useful, {s2.get('skipped')} skipped"
        )
    if trace.stage3_summary.get("available"):
        s3 = trace.stage3_summary
        lines.append(
            f"- **Stage 3**: {s3.get('total_artifacts')} artifacts, "
            f"{s3.get('skipped')} skipped, {s3.get('total_bytes')} bytes"
        )
    if trace.stage4_summary.get("available"):
        s4 = trace.stage4_summary
        lines.append(
            f"- **Stage 4**: {s4.get('sources')} sources, "
            f"{s4.get('candidates')} candidates, "
            f"{s4.get('failures')} failures, "
            f"cost ${s4.get('estimated_cost_usd', 0):.4f}"
        )
    if trace.stage5_summary.get("available"):
        s5 = trace.stage5_summary
        lines.append(
            f"- **Stage 5**: {s5.get('concepts')} concepts, "
            f"{s5.get('conflicts')} conflicts, "
            f"{s5.get('pass_c_reorderings')} Pass-C reorderings, "
            f"{s5.get('pass_c_no_change_guardrails')} no-change guardrails, "
            f"cost ${s5.get('estimated_cost_usd', 0):.4f}"
        )
    if trace.eva_summary:
        e = trace.eva_summary
        lines.append(
            f"- **Eva ground truth**: {e['compared']} concepts compared, "
            f"{e['exact']} exact, {e['substring']} substring, "
            f"{e['mismatch']} mismatch — top-1 accuracy {e['top1_accuracy']*100:.1f}%"
        )
    lines.append("")

    # Top issues.
    lines.append("## Top issues to investigate")
    if not trace.top_issues:
        lines.append("_No issues surfaced._")
    for i, issue in enumerate(trace.top_issues, 1):
        target = issue.get("concept_id") or issue.get("source_path") or "?"
        also = issue.get("also_flagged") or []
        also_suffix = f"  *(also: {', '.join(also)})*" if also else ""
        lines.append(
            f"{i}. **[signal={issue['signal_strength']:.2f}]** "
            f"`{issue['kind']}` — `{target}` — {issue['description']}{also_suffix}"
        )
        lines.append(f"    - **Action**: {issue['suggested_action']}")
    lines.append("")

    # Per-stage health.
    lines.append("## Per-stage health")
    for label, summary in (
        ("Stage 1: Inventari", trace.stage1_summary),
        ("Stage 2: Tipologia", trace.stage2_summary),
        ("Stage 3: Conversió", trace.stage3_summary),
        ("Stage 4: Anàlisi", trace.stage4_summary),
        ("Stage 5: Rànquing", trace.stage5_summary),
    ):
        lines.append(f"### {label}")
        if not summary.get("available"):
            lines.append("_(manifest absent)_")
            lines.append("")
            continue
        for k, v in summary.items():
            if k == "available":
                continue
            if isinstance(v, dict):
                v = ", ".join(f"`{kk}`={vv}" for kk, vv in sorted(v.items()))
            lines.append(f"- `{k}`: {v}")
        lines.append("")

    # Concept journeys (sorted by signal strength).
    lines.append("## Concept journeys")
    concept_signal: dict[str, float] = {}
    for issue in trace.top_issues:
        cid = issue.get("concept_id")
        if cid:
            concept_signal[cid] = max(
                concept_signal.get(cid, 0.0), issue["signal_strength"]
            )
    sorted_concepts = sorted(
        trace.concepts.values(),
        key=lambda j: (-concept_signal.get(j.concept_id, 0.0), j.concept_id),
    )
    for j in sorted_concepts:
        if not j.candidates and not j.final_ranked:
            continue
        lines.append(f"### `{j.concept_id}`  (group: {j.group or '—'})")
        lines.append(
            f"- **Status**: `{j.final_status or '—'}`  •  "
            f"**Picker**: `{j.picker_action}`  •  "
            f"**Agreement**: `{j.source_agreement}`"
        )
        lines.append(f"- _{_md_escape(j.picker_rationale)}_")
        if j.candidates:
            lines.append("\n**Candidates**")
            lines.append("| value | confidence | source |")
            lines.append("|---|---|---|")
            for c in j.candidates:
                lines.append(
                    f"| {_md_escape(repr(c.value))} | {c.confidence:.2f} | "
                    f"`{_md_escape(c.source_path)}` |"
                )
        if j.final_ranked:
            lines.append("\n**Pass A ranking**")
            lines.append("| rank | value | conf | source | rationale |")
            lines.append("|---|---|---|---|---|")
            for i, rc in enumerate(j.final_ranked, 1):
                rationale = (rc.rationale or "")[:150]
                lines.append(
                    f"| {i} | {_md_escape(repr(rc.value))} | {rc.confidence:.2f} | "
                    f"`{_md_escape(rc.source_path)}` | {_md_escape(rationale)} |"
                )
        if j.final_has_conflict and j.final_conflict_note:
            lines.append(f"\n⚠ **has_conflict**: {_md_escape(j.final_conflict_note[:600])}")
        if j.group_factors_mentioning:
            lines.append("\n**Pass B factors mentioning this concept**")
            for f in j.group_factors_mentioning:
                lines.append(
                    f"- affects=`{f.get('affects')}` — {_md_escape(str(f.get('description', ''))[:300])}"
                )
        if j.revised_by_group_pass:
            lines.append(
                f"\n**Pass C reorder applied.** Factor: _{_md_escape(j.group_factor_considered[:300])}_"
            )
        elif j.no_change_guardrail_fired:
            lines.append(
                f"\n**Pass C no-change guardrail fired.** Factor considered: "
                f"_{_md_escape(j.group_factor_considered[:300])}_"
            )
        if j.eva_top1_match != "no_ground_truth":
            lines.append("\n**Eva ground truth**")
            lines.append(f"- value: `{_md_escape(repr(j.eva_value))}`")
            lines.append(f"- match: `{j.eva_top1_match}`")
            if j.eva_rank_in_ranked is not None:
                lines.append(f"- rank in ranked list: {j.eva_rank_in_ranked}")
            else:
                lines.append("- not present in ranked list")
        if j.domain_flags:
            lines.append("\n**Domain flags**")
            for f in j.domain_flags:
                lines.append(f"- {_md_escape(f)}")
        lines.append("")

    # Source journeys (sorted by candidates emitted).
    lines.append("## Source journeys")
    sorted_sources = sorted(
        trace.sources.values(),
        key=lambda s: (-len(s.candidates_emitted), s.source_path),
    )
    for s in sorted_sources:
        if not s.candidates_emitted and not s.insight:
            continue
        lines.append(f"### `{s.source_path}`")
        if s.typology:
            lines.append(
                f"- **Stage 2**: category=`{s.typology.get('category')}`, "
                f"useful=`{s.typology.get('useful')}`, "
                f"strategy=`{s.typology.get('conversion_strategy')}`"
            )
        if s.artifacts:
            lines.append(f"- **Stage 3**: {len(s.artifacts)} artifacts")
        if s.insight:
            lines.append(
                f"- **Stage 4 insight**: `{s.insight.document_type}` — {_md_escape(s.insight.purpose[:200])}"
            )
            if s.insight.author:
                lines.append(f"  - author: {_md_escape(s.insight.author)}")
            if s.insight.date_info:
                lines.append(f"  - date: {_md_escape(s.insight.date_info)}")
        lines.append(f"- **Candidates emitted**: {len(s.candidates_emitted)}")
        if s.candidates_emitted:
            lines.append("| concept_id | value | conf |")
            lines.append("|---|---|---|")
            for c in s.candidates_emitted[:30]:
                lines.append(
                    f"| `{c['concept_id']}` | {_md_escape(repr(c['value']))} | {c['confidence']:.2f} |"
                )
        if s.pass4_failure:
            lines.append(f"- **Stage 4 FAILURE**: {_md_escape(json.dumps(s.pass4_failure)[:300])}")
        if s.rankings_contributed_to:
            lines.append("- **Stage 5 contributions**:")
            for entry in s.rankings_contributed_to[:20]:
                lines.append(
                    f"  - `{entry['concept_id']}`: rank {entry['rank']}/{entry['rank_total']}"
                    + (" (revised)" if entry["was_revised"] else "")
                )
        lines.append("")

    # Decision audit.
    lines.append("## Decision audit")
    d = trace.decisions
    lines.append(f"### Stage 2 dev-only skips ({len(d.stage2_dev_only_skips)})")
    for s in d.stage2_dev_only_skips:
        lines.append(f"- `{s['path']}` — {_md_escape(s['reason'])}")
    lines.append(f"\n### Stage 2 logo skips ({len(d.stage2_logo_skips)})")
    for s in d.stage2_logo_skips:
        lines.append(f"- `{s['path']}` — {_md_escape(s['reason'])}")
    lines.append(
        f"\n### Stage 3 conversion failures ({len(d.stage3_conversion_failures)})"
    )
    for s in d.stage3_conversion_failures:
        lines.append(
            f"- `{s['source_path']}` (strategy=`{s['strategy_used']}`): "
            f"{_md_escape(s['skip_reason'])}"
        )
    lines.append(f"\n### Stage 4 retried sources ({len(d.stage4_retried_sources)})")
    for s in d.stage4_retried_sources:
        lines.append(f"- `{s['source_path']}` — attempts={s['attempts']}")
    lines.append(f"\n### Stage 4 failed sources ({len(d.stage4_failed_sources)})")
    for s in d.stage4_failed_sources:
        lines.append(
            f"- `{s['source_path']}` (`{s['error_type']}`): "
            f"{_md_escape(s['last_error'][:200])}"
        )
    lines.append(
        f"\n### Stage 5 Pass A retries ({len(d.stage5_pass_a_retries)})"
    )
    lines.append(
        f"\n### Stage 5 Pass B revisions flagged per group: "
        f"{dict(d.stage5_pass_b_revisions_flagged)}"
    )
    lines.append(
        f"\n### Stage 5 Pass C no-change guardrails ({len(d.stage5_pass_c_no_change_guardrails)})"
    )
    for cid in d.stage5_pass_c_no_change_guardrails:
        lines.append(f"- `{cid}`")
    lines.append(
        f"\n### Stage 5 Pass C reorderings ({len(d.stage5_pass_c_reorderings)})"
    )
    for cid in d.stage5_pass_c_reorderings:
        lines.append(f"- `{cid}`")

    lines.append("\n## Instrumentation gaps (v2 candidates)")
    for g in d.instrumentation_gaps:
        lines.append(f"- {g}")

    return "\n".join(lines) + "\n"


def _build_html_report(trace: PipelineTrace) -> str:
    """Minimal HTML for in-browser navigation. No external deps."""
    md = _build_markdown_report(trace)
    # We won't render markdown; we'll just wrap it in <pre> with simple anchors
    # for concepts and sources. Eva can search (Ctrl-F) for navigation.
    body = md.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>AI Pipeline Trace — {trace.project_name}</title>
<style>
body {{ font-family: -apple-system, system-ui, sans-serif; margin: 2em; max-width: 1100px; }}
pre {{ white-space: pre-wrap; word-wrap: break-word; font-size: 13px; line-height: 1.4; }}
</style></head>
<body>
<pre>{body}</pre>
</body></html>"""


# ─── Main ──────────────────────────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--project", help="Project name or ID prefix (relative to reference-material/)")
    g.add_argument("--project-path", help="Absolute or relative path to project folder")

    ap.add_argument("--concept", help="Show concept journey only")
    ap.add_argument("--source", help="Show source journey only (substring match accepted)")
    ap.add_argument("--decisions", action="store_true", help="Show decision audit only")
    ap.add_argument("--all", action="store_true", help="Show everything (default)")
    ap.add_argument("--issues-only", action="store_true", help="Short summary: just top_issues")

    ap.add_argument("--save", action="store_true",
                    help="Write validation/ai_pipeline_trace.json")
    ap.add_argument("--report", choices=("markdown", "html", "both"),
                    help="Write a Markdown and/or HTML report under docs/diagnostics/")
    ap.add_argument("--diff", help="Path to a prior PipelineTrace JSON to diff against")
    ap.add_argument("--json", action="store_true",
                    help="Emit full PipelineTrace JSON to stdout")

    args = ap.parse_args()
    project_root = _resolve_project(args.project, args.project_path)

    trace = build_trace(project_root)

    if args.diff:
        prior_path = Path(args.diff)
        if not prior_path.is_file():
            raise SystemExit(f"Prior trace not found: {prior_path}")
        prior = PipelineTrace.model_validate_json(prior_path.read_text(encoding="utf-8"))
        diff = diff_traces(prior, trace)
        print(json.dumps(diff, indent=2, default=str, ensure_ascii=False))
        return 0

    if args.json:
        print(trace.model_dump_json(indent=2))
        return 0

    if args.concept:
        rc = _print_concept(trace, args.concept)
    elif args.source:
        rc = _print_source(trace, args.source)
    elif args.decisions:
        _print_decisions(trace)
        rc = 0
    elif args.issues_only:
        _print_top_issues(trace, limit=30)
        rc = 0
    else:
        # Default: --all
        print(f"# AI Pipeline Trace — {trace.project_name}")
        print(f"Generated: {trace.generated_at}")
        _print_top_issues(trace, limit=30)
        _print_stage_health(trace)
        _print_decisions(trace)
        rc = 0

    if args.save:
        out = save_trace(trace, project_root)
        print(f"\nSaved trace: {out}")

    if args.report:
        date = datetime.now(timezone.utc).strftime("%Y%m%d")
        slug = _slug(trace.project_name).split("_")[0] or _slug(trace.project_name)
        diag_dir = Path(__file__).parent.parent / "docs" / "diagnostics"
        diag_dir.mkdir(parents=True, exist_ok=True)
        if args.report in ("markdown", "both"):
            md_path = diag_dir / f"ai_pipeline_{slug}_{date}.md"
            md_path.write_text(_build_markdown_report(trace), encoding="utf-8")
            print(f"Markdown report: {md_path}")
        if args.report in ("html", "both"):
            html_path = diag_dir / f"ai_pipeline_{slug}_{date}.html"
            html_path.write_text(_build_html_report(trace), encoding="utf-8")
            print(f"HTML report: {html_path}")

    return rc


if __name__ == "__main__":
    raise SystemExit(main())
