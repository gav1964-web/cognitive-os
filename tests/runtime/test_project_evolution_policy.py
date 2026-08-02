from __future__ import annotations

from pathlib import Path

from runtime.project_evolution_policy import evaluate_project_evolution, load_project_evolution_policy


ROOT = Path(__file__).resolve().parents[2]


def test_project_evolution_policy_loads_current_catalog() -> None:
    policy = load_project_evolution_policy(str(ROOT / "config" / "project_evolution_policy.json"))

    assert policy["schema_version"] == "project_evolution_policy.v1"
    assert "kb_or_config_before_code_branch" in policy["principles"]
    assert "meta_only_is_not_callable" in policy["evolution_rules"]
    assert "role_score_9_5" in policy["promotion_gates"]


def test_project_evolution_allows_9_5_gate_for_field_validated_kb_growth() -> None:
    report = evaluate_project_evolution(
        {
            "change_types": ["field_validated_capability", "kb_crystallization"],
            "evidence": ["field_report", "regression_tests", "no_source_changes", "config_or_kb_change", "config_doctor", "line_limit_check"],
            "field_callable_delta": 2,
        }
    )

    assert report["status"] == "ok"
    assert report["promotion_gates"]["role_score_9_5"]["passed"] is True
    assert report["promotion_gates"]["role_score_9_7"]["passed"] is False


def test_project_evolution_blocks_cosmetic_score_growth() -> None:
    report = evaluate_project_evolution(
        {
            "change_types": ["cosmetic_tuning"],
            "evidence": ["regression_tests"],
            "field_callable_delta": 0,
            "anti_patterns": ["score_increase_without_field_delta"],
        }
    )

    assert report["status"] == "needs_work"
    assert "score_increase_without_field_delta" in report["blockers"]


def test_project_evolution_allows_9_7_gate_with_independent_holdout() -> None:
    report = evaluate_project_evolution(
        {
            "change_types": [
                "field_validated_capability",
                "kb_crystallization",
                "policy_extraction",
                "independent_holdout_validation",
            ],
            "evidence": [
                "field_report",
                "regression_tests",
                "no_source_changes",
                "config_or_kb_change",
                "config_doctor",
                "line_limit_check",
                "code_to_policy_move",
                "independent_holdout",
            ],
            "field_callable_delta": 4,
        }
    )

    assert report["status"] == "ok"
    assert report["evolution_score"] == 9
    assert report["promotion_gates"]["role_score_9_7"]["passed"] is True


def test_project_evolution_blocks_9_7_claim_without_independent_holdout() -> None:
    report = evaluate_project_evolution(
        {
            "change_types": ["field_validated_capability", "kb_crystallization", "policy_extraction"],
            "evidence": [
                "field_report",
                "regression_tests",
                "no_source_changes",
                "config_or_kb_change",
                "config_doctor",
                "line_limit_check",
                "code_to_policy_move",
            ],
            "field_callable_delta": 4,
            "target_gates": ["role_score_9_7"],
        }
    )

    assert report["status"] == "needs_work"
    assert "score_growth_without_independent_holdout" in report["blockers"]
    assert "reused_field_as_new_level_evidence" in report["blockers"]


def test_project_evolution_blocks_false_callable_and_native_boundary_mix() -> None:
    report = evaluate_project_evolution(
        {
            "change_types": ["field_validated_capability"],
            "evidence": ["field_report", "regression_tests", "no_source_changes", "line_limit_check"],
            "field_callable_delta": 1,
            "false_callable_regressions": 1,
            "meta_only_delta_as_callable": 1,
            "boundary_track": "native_extension",
        }
    )

    assert "false_callable_regression" in report["blockers"]
    assert "meta_only_counted_as_callable" in report["blockers"]
    assert "native_extension_mixed_into_pure_python_score" in report["blockers"]
