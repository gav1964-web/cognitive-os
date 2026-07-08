from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_field_trial_report_summarizes_recent_reports(tmp_path):
    reports = tmp_path / "artifacts" / "goals" / "reports"
    reports.mkdir(parents=True)
    (reports / "goal_1.json").write_text(
        json.dumps(
            {
                "goal_id": "goal_1",
                "goal": "Normalize text",
                "summary": "ok",
                "level4_decision": {"action": "PLAN_WITH_L35", "required_capabilities": ["normalize_text"]},
                "level4_deliberation": {
                    "recommendation": "continue_to_level35",
                    "risks": [{"code": "x"}],
                    "route_alternatives": [{"id": "memory_template"}],
                    "selected_alternative": {"id": "memory_template"},
                },
                "level35_plan": {"planner": "memory_template", "template_id": "tpl_1"},
                "execution": {"status": "ok", "completed_nodes": ["normalize_text"]},
            }
        ),
        encoding="utf-8",
    )
    root = Path(__file__).resolve().parents[2]

    result = subprocess.run(
        [sys.executable, str(root / "tools" / "field_trial_report.py"), "--root", str(tmp_path), "--write"],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["summary"]["actions"] == {"PLAN_WITH_L35": 1}
    assert payload["summary"]["recommendations"] == {"continue_to_level35": 1}
    assert payload["summary"]["selected_alternatives"] == {"memory_template": 1}
    assert payload["summary"]["execution"] == {"ok": 1}
    assert payload["tasks"][0]["level4_risk_count"] == 1
    assert payload["tasks"][0]["alternative_count"] == 1
    assert Path(payload["report_path"]).exists()
