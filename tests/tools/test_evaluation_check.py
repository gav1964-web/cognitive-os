from __future__ import annotations

import json
from pathlib import Path

from tools.evaluation_check import check_evaluation


def _write_valid_task(root: Path, name: str = "task01_demo") -> Path:
    task = root / "evaluation" / name
    (task / "direct_agent").mkdir(parents=True)
    (task / "cognitive_os").mkdir()
    (task / "prompt.md").write_text("# Prompt\n", encoding="utf-8")
    (task / "direct_agent" / "README.md").write_text("# Direct\n", encoding="utf-8")
    (task / "cognitive_os" / "README.md").write_text("# Cognitive OS\n", encoding="utf-8")
    (task / "verdict.md").write_text("# Verdict\n", encoding="utf-8")
    route = {
        "executor": "demo",
        "model": "demo",
        "status": "ok",
        "requirement_coverage": 1.0,
        "missed_requirements": 0,
        "invented_requirements": 0,
        "tests_passed": 1,
        "tests_total": 1,
        "verification_status": "ok",
        "repair_cycles": 0,
        "runtime_seconds": 1.0,
        "estimated_cost": 0.0,
        "artifact_completeness": 1.0,
        "source_safety_violations": 0,
        "review_blockers": 0,
        "human_correction_minutes": 0,
    }
    metrics = {
        "task_id": name,
        "task_class": "cli_utility",
        "prompt_hash": "sha256:demo",
        "routes": {"direct_agent": route, "cognitive_os": route},
        "comparison": {
            "winner": "no_clear_difference",
            "cognitive_os_advantages": [],
            "direct_agent_advantages": [],
            "no_difference": [],
            "confidence": 0.5,
        },
        "invariants": {
            "same_original_prompt": True,
            "same_constraints": True,
            "manual_corrections_recorded": True,
            "teacher_reference_is_ground_truth": False,
            "source_mutation_detected": False,
        },
        "verdict": "no_clear_difference",
    }
    (task / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    return task


def test_evaluation_check_accepts_valid_task(tmp_path: Path) -> None:
    _write_valid_task(tmp_path)

    report = check_evaluation(tmp_path)

    assert report["ok"] is True
    assert report["task_count"] == 1


def test_evaluation_check_rejects_ground_truth_teacher_reference(tmp_path: Path) -> None:
    task = _write_valid_task(tmp_path)
    metrics_path = task / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics["invariants"]["teacher_reference_is_ground_truth"] = True
    metrics_path.write_text(json.dumps(metrics), encoding="utf-8")

    report = check_evaluation(tmp_path)

    assert report["ok"] is False
    assert any("teacher_reference_is_ground_truth" in error for error in report["errors"])

