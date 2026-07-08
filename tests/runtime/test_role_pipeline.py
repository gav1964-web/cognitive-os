from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from runtime.local_inference import LocalInferenceConfig
from runtime.role_pipeline import run_role_pipeline


ROOT = Path(__file__).resolve().parents[2]


def test_role_pipeline_returns_next_action(tmp_path):
    project_dir = ROOT / "benchmarks" / "project_analyzer" / "projects" / "simple_cli_tool"

    result = run_role_pipeline(root=ROOT, project_dir=project_dir, goal="Extract first safe capability", write=True)

    assert result["status"] == "ok"
    assert result["kind"] == "role_pipeline"
    assert result["next_action"] in {"run_project_transform", "review_risks_then_run_project_transform", "rework_role_artifacts"}
    assert result["safety"]["source_code_changes"] is False
    assert result["safety"]["llm_invoked"] is False
    assert result["safety"]["foundry_invoked"] is False
    assert result["architect_advisory"]["source"] == "deterministic"
    assert result["transform"]["status"] == "skipped"
    assert Path(result["report_path"]).exists()
    assert Path(result["human_documents"]["architecture_analysis"]).exists()
    assert result["artifacts"]["review_findings"]["artifact_type"] == "ReviewFindings"


def test_role_pipeline_cli_writes_report():
    tool = ROOT / "tools" / "role_pipeline_run.py"
    result = subprocess.run(
        [
            sys.executable,
            str(tool),
            "--root",
            str(ROOT),
            "--project-dir",
            "benchmarks/project_analyzer/projects/simple_cli_tool",
            "--goal",
            "Extract first safe capability",
            "--write",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "ok"
    assert Path(payload["report_path"]).exists()


def test_role_pipeline_can_run_transform():
    project_dir = ROOT / "benchmarks" / "project_analyzer" / "projects" / "simple_cli_tool"

    result = run_role_pipeline(
        root=ROOT,
        project_dir=project_dir,
        goal="Extract first safe capability",
        write=True,
        run_transform=True,
        force_transform=True,
    )

    assert result["status"] == "ok"
    assert result["safety"]["foundry_invoked"] is True
    assert result["transform"]["status"] == "promotion_ready"
    assert Path(result["transform"]["candidate_path"]).exists()


def test_role_pipeline_architect_llm_fallback():
    project_dir = ROOT / "benchmarks" / "project_analyzer" / "projects" / "simple_cli_tool"
    config = LocalInferenceConfig(base_url="http://127.0.0.1:9/v1", model="missing", timeout_seconds=0.05)

    result = run_role_pipeline(
        root=ROOT,
        project_dir=project_dir,
        goal="Extract first safe capability",
        architect_advisory_config=config,
    )

    assert result["status"] == "ok"
    assert result["safety"]["llm_invoked"] is False
    assert result["safety"]["foundry_invoked"] is False
    assert result["architect_advisory"]["source"] == "deterministic_fallback"
