from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_local_automation_mvp_trial_smoke():
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "local_automation_mvp_trial.py"),
            "--root",
            str(ROOT),
            "--write",
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    report = json.loads(completed.stdout)
    assert report["artifact_type"] == "LocalAutomationMVPTrialReport"
    assert report["status"] == "ok"
    assert report["summary"]["case_count"] == 39
    assert report["summary"]["passed"] == 39
    assert report["summary"]["failed"] == 0
    assert report["summary"]["pass_rate"] == 1.0
    assert report["summary"]["categories"]["controlled_refusal"]["passed"] == 5
    assert report["summary"]["categories"]["document_automation"]["passed"] == 4
    assert report["summary"]["categories"]["needs_clarification"]["passed"] == 5
    assert report["summary"]["categories"]["sandbox_atomic_operation"]["passed"] == 17
    assert {case["case"] for case in report["cases"]} >= {
        "stage2_cli_text_stats",
        "stage2_fastapi_csv_aggregator",
        "sandbox_stdin_upper_file",
        "sandbox_numeric_expr_args_to_file",
        "clarification_generic_file_utility",
    }
