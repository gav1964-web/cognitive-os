from __future__ import annotations

import json
from pathlib import Path

from tools.project_evolution_report import build_project_evolution_report


def test_project_evolution_report_infers_field_delta_and_9_5_gate(tmp_path: Path) -> None:
    baseline = _write_executor_report(tmp_path / "baseline.json", acceptance_callable=16, projects=["a", "b"])
    current = _write_executor_report(tmp_path / "current.json", acceptance_callable=19, projects=["a", "b"])

    report = build_project_evolution_report(
        root=tmp_path,
        baseline_report=baseline,
        current_report=current,
        change_types=["field_validated_capability", "kb_crystallization", "policy_extraction", "independent_holdout_validation"],
        evidence=["regression_tests", "config_doctor", "line_limit_check", "config_or_kb_change", "code_to_policy_move"],
        anti_patterns=[],
    )

    assert report["status"] == "ok"
    assert report["field_callable_delta"] == 3
    assert report["change"]["evidence"] == [
        "code_to_policy_move",
        "config_doctor",
        "config_or_kb_change",
        "field_report",
        "line_limit_check",
        "no_source_changes",
        "regression_tests",
    ]
    assert report["evolution"]["evolution_score"] == 7
    assert report["evolution"]["promotion_gates"]["role_score_9_5"]["passed"] is True
    assert report["evolution"]["promotion_gates"]["role_score_9_7"]["passed"] is False
    assert report["independent_holdout"]["status"] == "not_independent"
    assert report["independent_holdout"]["overlap_count"] == 2


def test_project_evolution_report_infers_independent_holdout_from_disjoint_report(tmp_path: Path) -> None:
    baseline = _write_executor_report(tmp_path / "baseline.json", acceptance_callable=16, projects=["a", "b"])
    current = _write_executor_report(tmp_path / "current.json", acceptance_callable=20, projects=["a", "b"])
    holdout = _write_executor_report(tmp_path / "holdout.json", acceptance_callable=12, projects=["c", "d"])

    report = build_project_evolution_report(
        root=tmp_path,
        baseline_report=baseline,
        current_report=current,
        holdout_report=holdout,
        change_types=["field_validated_capability", "kb_crystallization", "policy_extraction", "independent_holdout_validation"],
        evidence=["regression_tests", "config_doctor", "line_limit_check", "config_or_kb_change", "code_to_policy_move"],
        anti_patterns=[],
    )

    assert report["status"] == "ok"
    assert "independent_holdout" in report["change"]["evidence"]
    assert report["independent_holdout"]["status"] == "passed"
    assert report["evolution"]["evolution_score"] == 9
    assert report["evolution"]["promotion_gates"]["role_score_9_7"]["passed"] is True


def test_project_evolution_report_blocks_cosmetic_growth_with_antipattern(tmp_path: Path) -> None:
    baseline = _write_executor_report(tmp_path / "baseline.json", acceptance_callable=19, projects=["a"])
    current = _write_executor_report(tmp_path / "current.json", acceptance_callable=19, projects=["a"])

    report = build_project_evolution_report(
        root=tmp_path,
        baseline_report=baseline,
        current_report=current,
        change_types=["cosmetic_tuning"],
        evidence=["regression_tests"],
        anti_patterns=["score_increase_without_field_delta"],
    )

    assert report["status"] == "needs_work"
    assert report["field_callable_delta"] == 0
    assert "score_increase_without_field_delta" in report["evolution"]["blockers"]


def test_project_evolution_report_rejects_needs_review_holdout(tmp_path: Path) -> None:
    baseline = _write_executor_report(tmp_path / "baseline.json", acceptance_callable=16, projects=["a"])
    current = _write_executor_report(tmp_path / "current.json", acceptance_callable=20, projects=["a"])
    holdout = _write_executor_report(tmp_path / "holdout.json", acceptance_callable=0, projects=["b"], status="needs_review")

    report = build_project_evolution_report(
        root=tmp_path,
        baseline_report=baseline,
        current_report=current,
        holdout_report=holdout,
        change_types=["independent_holdout_validation"],
        evidence=["field_report", "regression_tests", "no_source_changes"],
        anti_patterns=[],
    )

    assert report["independent_holdout"]["status"] == "not_independent"
    assert "independent_holdout" not in report["change"]["evidence"]
    assert "independent_holdout_validation:independent_holdout" in report["evolution"]["missing_evidence"]


def _write_executor_report(path: Path, *, acceptance_callable: int, projects: list[str], status: str = "ok") -> Path:
    payload = {
        "artifact_type": "GitHubExecutorProbe",
        "status": status,
        "project_count": len(projects),
        "summary": {
            "acceptance_callable": acceptance_callable,
            "source_code_changes": 0,
        },
        "cases": [{"project": project} for project in projects],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path
