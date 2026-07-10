from __future__ import annotations

import json
from pathlib import Path

from tools.evaluation_summary import build_summary, to_markdown


def test_evaluation_summary_reads_metrics(tmp_path: Path) -> None:
    task = tmp_path / "evaluation" / "task01_demo"
    task.mkdir(parents=True)
    metrics = {
        "task_id": "task01_demo",
        "task_class": "project_analysis",
        "routes": {
            "direct_agent": {"status": "not_run"},
            "cognitive_os": {"status": "not_run"},
        },
        "comparison": {"winner": "undecided", "confidence": 0.0},
        "verdict": "not_evaluated",
    }
    (task / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")

    summary = build_summary(tmp_path)
    markdown = to_markdown(summary)

    assert summary["task_count"] == 1
    assert summary["task_classes"] == {"project_analysis": 1}
    assert "`task01_demo`" in markdown

