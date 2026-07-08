from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_project_tasks_tool_filters_and_writes_spec(tmp_path):
    root = tmp_path
    reports_dir = root / "artifacts" / "goals" / "reports"
    reports_dir.mkdir(parents=True)
    report = {
        "goal_id": "goal_demo",
        "goal": "Analyze project F:\\demo\\app",
        "root_input": {"path": "F:\\demo\\app"},
        "analysis_tasks": {
            "tasks": [
                {
                    "task_id": "analysis_one",
                    "type": "EXTRACT_CAPABILITY",
                    "title": "Extract capability candidate from app/api.py:handle",
                    "target": "app/api.py:handle",
                    "priority": "P1",
                    "status": "proposed",
                    "acceptance": "Candidate has contracts and tests.",
                },
                {
                    "task_id": "analysis_two",
                    "type": "HARDEN_CONTRACT",
                    "title": "Harden contract around app/schema.py",
                    "target": "app/schema.py",
                    "priority": "P2",
                    "status": "proposed",
                    "acceptance": "Schema mismatch is testable.",
                },
            ]
        },
    }
    report_path = reports_dir / "goal_demo.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    tool = Path(__file__).resolve().parents[2] / "tools" / "project_tasks.py"

    listed = subprocess.run(
        [sys.executable, str(tool), "--root", str(root), "--json", "--project", "demo", "--priority", "P1"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(listed.stdout)

    assert payload["task_count"] == 1
    assert payload["tasks"][0]["task_id"] == "analysis_one"

    created = subprocess.run(
        [
            sys.executable,
            str(tool),
            "--root",
            str(root),
            "--task-id",
            "analysis_one",
            "--write-spec",
            "--spec-id",
            "extract_api_handle",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    spec_path = Path(json.loads(created.stdout)["spec"])
    spec = json.loads(spec_path.read_text(encoding="utf-8"))

    assert spec["id"] == "extract_api_handle"
    assert spec["source_analysis_task"]["task_id"] == "analysis_one"
    assert spec["source_analysis_task"]["acceptance"] == "Candidate has contracts and tests."
