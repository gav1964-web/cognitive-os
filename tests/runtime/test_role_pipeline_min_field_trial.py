import runtime.role_pipeline_min_field_trial as field_trial
from runtime.role_pipeline_min_field_trial import _gate_score, _programmer_score, _report


def test_gate_score_uses_worst_case_role_criteria_ratio():
    case = {
        "gates": [{"status": "passed"}, {"status": "failed"}],
        "quality_criteria": [{"status": "passed"}, {"status": "skipped"}],
    }

    assert _gate_score(case) == 6.67


def test_programmer_score_requires_executable_callable_evidence():
    result = {
        "executor": {
            "status": "failed",
            "source_code_changes": False,
            "patch_package_path": "patch.json",
            "test_result": {
                "commands": [{"status": "passed"}],
                "executable_acceptance_result": {
                    "status": "passed",
                    "summary": {"signal_strength": "meta_only", "skipped_targets": [{"target": "app.py:run"}]},
                },
                "executor_strategy": {
                    "contract_alignment": {"status": "aligned"},
                    "deterministic_strategy": {"action": "request_dependency_boundary_profile"},
                    "sandbox_patch_candidate": {"status": "not_available"},
                },
                "programmer_task_tree": {
                    "coverage": {"all_changes_traced": True, "unmapped_acceptance_ids": []}
                },
            },
        }
    }

    assert _programmer_score(result) == 6.67


def test_report_publishes_role_minima_not_averages():
    cases = [
        {"project": "a", "role_scores": {role: 10.0 for role in ("implementer", "task_tree_builder", "programmer_executor", "tester", "reviewer")}, "project_min_score": 10.0, "safety": {}},
        {"project": "b", "role_scores": {"implementer": 8.0, "task_tree_builder": 9.0, "programmer_executor": 6.0, "tester": 7.0, "reviewer": 5.0}, "project_min_score": 5.0, "safety": {}},
    ]

    report = _report(cases, 9.7)

    assert report["summary"]["role_min_scores"] == {
        "implementer": 8.0,
        "task_tree_builder": 9.0,
        "programmer_executor": 6.0,
        "tester": 7.0,
        "reviewer": 5.0,
    }
    assert report["summary"]["project_min_score"] == 5.0


def test_project_system_exit_is_recorded_not_raised(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setattr(field_trial, "run_role_pipeline", lambda **_kwargs: (_ for _ in ()).throw(SystemExit(False)))

    case = field_trial._run_case(tmp_path, project)

    assert case["status"] == "failed"
    assert case["error"] == "SystemExit: False"
    assert set(case["role_scores"].values()) == {0.0}
