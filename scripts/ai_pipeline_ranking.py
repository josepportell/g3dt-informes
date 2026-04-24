#!/usr/bin/env python3
"""AI pipeline Stage 5 — authority ranking per concept CLI.

Usage:
    python scripts/ai_pipeline_ranking.py --project 4001670
    python scripts/ai_pipeline_ranking.py --project 4001670 --save
    python scripts/ai_pipeline_ranking.py --project 4001670 --concept architect_name
    python scripts/ai_pipeline_ranking.py --project 4001670 --group parcel --group lab
    python scripts/ai_pipeline_ranking.py --project 4001670 --no-group-pass
    python scripts/ai_pipeline_ranking.py --project 4001670 --model claude-opus-4-7

Notes:
- Requires ANTHROPIC_API_KEY in the environment when any concept has ≥2
  candidates (Pass A hits the LLM). Passthrough-only projects need no key.
- Uses per-concept / per-group / per-revision caches under
  validation/ai_pipeline/ranking/; re-runs are free unless --force is passed
  or upstream inputs (principles, glossary, candidates) changed.
- --concept and --group are independent: --concept restricts Pass A to one
  concept, --group restricts Pass B/C to the given group(s). They can be
  combined (e.g. rank one concept while still auditing its group).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def _load_dotenv() -> None:
    """Load .env from project root if it exists (matches analysis CLI pattern)."""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()

from automation.ai_pipeline.ranking import (
    load_ranking,
    rank_project,
    save_ranking,
)


REFERENCE_ROOT = Path(__file__).parent.parent / "reference-material"


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
    matches = [d for d in REFERENCE_ROOT.iterdir() if d.is_dir() and d.name.startswith(project)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise SystemExit(
            f"Ambiguous --project {project!r}; matches:\n" + "\n".join(f"  - {d.name}" for d in matches)
        )
    raise SystemExit(f"No project matches {project!r} under {REFERENCE_ROOT}")


def _systemic_failure(ranking) -> dict | None:
    """Return the systemic-failure entry (concept_id=='*' or systemic error_type)."""
    systemic_types = {"missing_api_key", "sdk_missing", "circuit_breaker"}
    for f in ranking.failures:
        if f.get("concept_id") == "*" or f.get("error_type") in systemic_types:
            return f
    return None


def _print_human(ranking, project_root: Path) -> None:
    print(f"Project:  {project_root.name}")
    print(f"Ranked:   {ranking.ranked_at}")
    print()

    systemic = _systemic_failure(ranking)
    if systemic is not None:
        print(f"⚠ SYSTEMIC FAILURE: {systemic.get('error_type', 'unknown')}")
        last_error = systemic.get("last_error", "")
        if last_error:
            print(f"  {last_error[:200]}")
        print()

    for line in ranking.eva_summary:
        print(line)
    print()

    n_ranked = sum(1 for c in ranking.concepts.values() if c.status == "ranked")
    n_single = sum(1 for c in ranking.concepts.values() if c.status == "single")
    n_none = sum(
        1 for c in ranking.concepts.values() if c.status == "no_candidates"
    )
    n_pending = sum(
        1 for c in ranking.concepts.values() if c.status == "pending_fase5"
    )
    print(
        f"Concepts: {n_ranked} ranked / {n_single} single / "
        f"{n_none} no_candidates / {n_pending} pending_fase5"
    )

    groups_processed = sum(
        1 for g in ranking.groups.values() if not g.skipped_reason
    )
    factors_total = sum(len(g.factors) for g in ranking.groups.values())
    n_revised = sum(
        1 for c in ranking.concepts.values() if c.revised_by_group_pass
    )
    # Guardrail count: concepts whose pre-revision rationale was kept
    # (surfaced via the audit's "revisions" entries where `revise=true` but the
    # concept was not actually revised). Best-effort count — if detail absent,
    # leave zero.
    n_no_change = 0
    for g in ranking.groups.values():
        for rev in g.revisions:
            if rev.get("revise"):
                cid = rev.get("concept_id", "")
                cr = ranking.concepts.get(cid)
                if cr is not None and not cr.revised_by_group_pass:
                    n_no_change += 1
    print(
        f"Groups:   {groups_processed} processed / "
        f"{factors_total} factors detected / "
        f"{n_revised} revisions applied / "
        f"{n_no_change} no-change guardrails"
    )
    print(
        f"Tokens:   {ranking.total_input_tokens:,} in / "
        f"{ranking.total_output_tokens:,} out / "
        f"{ranking.total_cache_creation_tokens:,} cache_creation / "
        f"{ranking.total_cache_read_tokens:,} cache_read"
    )
    print(f"Cost:     ${ranking.estimated_cost_usd:.4f}")
    if ranking.cache_hits:
        print(f"Cache hits: {ranking.cache_hits}")

    # Per-concept failures (non-systemic)
    per_concept_failures = [
        f for f in ranking.failures if f.get("concept_id") not in ("*", "")
    ]
    if per_concept_failures:
        print()
        print(f"Per-concept failures: {len(per_concept_failures)}")
        for f in per_concept_failures:
            err_type = f.get("error_type", "unknown")
            cid = f.get("concept_id", "?")
            last_error = f.get("last_error", "")
            print(f"  [{err_type}] {cid}: {last_error[:120]}")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--project", help="Project name or ID prefix (under reference-material/)")
    g.add_argument("--project-path", help="Absolute or relative path to project folder")
    ap.add_argument(
        "--save",
        action="store_true",
        help="Write manifest to {project}/validation/ai_ranking.json",
    )
    ap.add_argument(
        "--json",
        action="store_true",
        help="Print full ranking as JSON",
    )
    ap.add_argument(
        "--concept",
        help="Restrict Pass A to a single concept_id",
    )
    ap.add_argument(
        "--group",
        action="append",
        help="Restrict Pass B/C to these group(s); may be passed multiple times",
    )
    ap.add_argument(
        "--no-group-pass",
        action="store_true",
        help="Skip Pass B (group audit) and Pass C (targeted revision)",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="Ignore caches and re-call the LLM",
    )
    ap.add_argument("--model", help="Override default model (e.g. claude-opus-4-7)")
    args = ap.parse_args()

    project_root = _resolve_project(args.project, args.project_path)

    group_filter: set[str] | None = set(args.group) if args.group else None
    concept_filter: str | None = args.concept

    ranking = rank_project(
        project_root,
        model=args.model,
        concept_filter=concept_filter,
        group_filter=group_filter,
        no_group_pass=args.no_group_pass,
        force=args.force,
    )

    if args.json:
        print(ranking.model_dump_json(indent=2))
    else:
        _print_human(ranking, project_root)

    if args.save:
        out = save_ranking(ranking, project_root)
        if not args.json:
            print(f"\nSaved: {out}")

    # Exit nonzero on systemic failure so scripts can chain
    return 2 if _systemic_failure(ranking) is not None else 0


if __name__ == "__main__":
    raise SystemExit(main())
