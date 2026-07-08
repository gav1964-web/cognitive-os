from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_role_skill_run_cli_writes_full_chain():
    tool = ROOT / "tools" / "role_skill_run.py"
    adr = _run(
        tool,
        "--role",
        "architect",
        "--goal",
        "Extract first safe capability",
        "--project-dir",
        "benchmarks/project_analyzer/projects/simple_cli_tool",
    )
    spec = _run(tool, "--role", "spec_writer", "--adr", adr["artifact_path"])
    plan = _run(tool, "--role", "implementer", "--spec", spec["artifact_path"])
    test_plan = _run(tool, "--role", "tester", "--spec", spec["artifact_path"], "--plan", plan["artifact_path"])
    review = _run(
        tool,
        "--role",
        "reviewer",
        "--spec",
        spec["artifact_path"],
        "--plan",
        plan["artifact_path"],
        "--test-plan",
        test_plan["artifact_path"],
    )

    assert adr["artifact_type"] == "ArchitectureDecisionRecord"
    assert spec["artifact_type"] == "TechnicalSpec"
    assert plan["artifact_type"] == "ImplementationPlan"
    assert test_plan["artifact_type"] == "TestPlan"
    assert review["artifact_type"] == "ReviewFindings"
    for payload in (adr, spec, plan, test_plan, review):
        assert Path(payload["artifact_path"]).exists()


def _run(tool: Path, *args: str) -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, str(tool), "--root", str(ROOT), *args, "--write"],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)
