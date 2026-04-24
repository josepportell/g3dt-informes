"""CLI smoke tests for scripts/ai_pipeline_ranking.py.

All tests use passthrough-only analyses (0/1 candidate concepts) so no
LLM call is made — safe to run without ANTHROPIC_API_KEY.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from automation.ai_pipeline.analysis import (
    Candidate,
    ProjectAnalysis,
    SourceAnalysis,
    SourceInsight,
)


_REPO_ROOT = Path(__file__).resolve().parent.parent
_CLI = _REPO_ROOT / "scripts" / "ai_pipeline_ranking.py"


def _make_passthrough_analysis() -> ProjectAnalysis:
    """Build a minimal analysis where every concept has ≤1 candidate.

    One source contributes a single candidate for one concept — the rest of
    the concept registry falls through as `no_candidates`. No concept reaches
    ≥2 candidates, so Pass A never fires and no API key is required.
    """
    sources = [
        SourceAnalysis(
            source_path="plans/A.01.pdf",
            insight=SourceInsight(
                source_path="plans/A.01.pdf",
                document_type="test",
                purpose="test",
            ),
            candidates=[
                Candidate(
                    concept_id="architect_name",
                    value="Test Architect",
                    confidence=0.9,
                    source_path="plans/A.01.pdf",
                )
            ],
        )
    ]
    return ProjectAnalysis(
        project_path="/tmp/fake",
        analyzed_at="2026-04-24T00:00:00+00:00",
        sources=sources,
    )


def _make_project(tmp_path: Path, analysis: ProjectAnalysis) -> Path:
    p = tmp_path / "demo"
    (p / "validation").mkdir(parents=True)
    (p / "validation" / "ai_analysis.json").write_text(
        analysis.model_dump_json(indent=2), encoding="utf-8"
    )
    return p


def _run_cli(args: list[str], env: dict | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(_CLI), *args]
    run_env = os.environ.copy()
    if env is not None:
        run_env.update(env)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=run_env,
        cwd=str(_REPO_ROOT),
    )


def test_cli_human_output_passthrough(tmp_path: Path) -> None:
    analysis = _make_passthrough_analysis()
    project = _make_project(tmp_path, analysis)

    result = _run_cli(
        ["--project-path", str(project), "--no-group-pass"],
    )
    assert result.returncode == 0, (
        f"stdout=\n{result.stdout}\nstderr=\n{result.stderr}"
    )
    # Catalan summary from _build_ranking_summary
    assert "Rànquing de Fase 5" in result.stdout
    # Basic structure
    assert "Project:" in result.stdout
    assert "Concepts:" in result.stdout


def test_cli_json_output_is_valid(tmp_path: Path) -> None:
    analysis = _make_passthrough_analysis()
    project = _make_project(tmp_path, analysis)

    result = _run_cli(
        ["--project-path", str(project), "--no-group-pass", "--json"],
    )
    assert result.returncode == 0, (
        f"stdout=\n{result.stdout}\nstderr=\n{result.stderr}"
    )
    payload = json.loads(result.stdout)
    # model_dump of ProjectRanking
    assert "concepts" in payload
    assert "groups" in payload
    assert "eva_summary" in payload
    # architect_name should be "single"
    assert payload["concepts"]["architect_name"]["status"] == "single"


def test_cli_no_api_key_passthrough_succeeds(tmp_path: Path) -> None:
    """Without ANTHROPIC_API_KEY, a passthrough-only project still exits 0.

    No concept has ≥2 candidates → `_get_client()` is never called.
    """
    analysis = _make_passthrough_analysis()
    project = _make_project(tmp_path, analysis)

    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)
    result = subprocess.run(
        [sys.executable, str(_CLI), "--project-path", str(project), "--no-group-pass"],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(_REPO_ROOT),
    )
    assert result.returncode == 0, (
        f"stdout=\n{result.stdout}\nstderr=\n{result.stderr}"
    )
    assert "Rànquing de Fase 5" in result.stdout


def test_cli_save_writes_ai_ranking_json(tmp_path: Path) -> None:
    analysis = _make_passthrough_analysis()
    project = _make_project(tmp_path, analysis)

    out_path = project / "validation" / "ai_ranking.json"
    assert not out_path.exists()

    result = _run_cli(
        ["--project-path", str(project), "--no-group-pass", "--save"],
    )
    assert result.returncode == 0, (
        f"stdout=\n{result.stdout}\nstderr=\n{result.stderr}"
    )
    assert out_path.is_file(), "ai_ranking.json was not created"
    # Saved path is mentioned in human output
    assert "Saved:" in result.stdout
    # Content is valid ProjectRanking JSON
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert "concepts" in payload
    assert payload["concepts"]["architect_name"]["status"] == "single"
