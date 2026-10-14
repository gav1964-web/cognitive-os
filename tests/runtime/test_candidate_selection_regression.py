from runtime.improvement_plugins import candidate_selection_regression as regression
from runtime.improvement_plugins.candidate_selection_regression import regression_failures
import pytest


def test_regression_gate_rejects_failure_on_second_repetition(monkeypatch, tmp_path):
    results = iter([
        {"status": "ok", "project_min_score": 9.7},
        {"status": "ok", "project_min_score": 8.8},
    ])
    monkeypatch.setattr(
        "runtime.improvement_plugins.candidate_selection_regression.evaluate_project",
        lambda *_args, **_kwargs: next(results),
    )
    before = [{
        "project": "unstable",
        "project_dir": tmp_path,
        "result": {"status": "ok", "project_min_score": 9.7},
    }]

    failures = regression_failures(tmp_path, before, repetitions=2)

    assert failures[0]["project"] == "unstable"
    assert failures[0]["failed_repetition_count"] == 1
    assert failures[0]["after_score"] == 8.8


def test_regression_gate_stops_before_evaluation_when_total_budget_is_exhausted(
    monkeypatch, tmp_path,
):
    monkeypatch.setattr(regression.time, "monotonic", lambda: 5.1)
    monkeypatch.setattr(
        regression, "evaluate_project",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not run")),
    )
    before = [{
        "project": "slow", "project_dir": tmp_path,
        "result": {"status": "ok", "project_min_score": 9.7},
    }]

    budget = regression.RegressionBudget(
        total_timeout_seconds=5.0, total_evaluations=3, started=0.0,
    )
    with pytest.raises(regression.RegressionGateBudgetExceeded) as raised:
        regression_failures(tmp_path, before, repetitions=3, budget=budget)

    assert raised.value.reason == "regression_gate_budget_exceeded"
    assert raised.value.details["completed_evaluations"] == 0
    assert raised.value.details["total_evaluations"] == 3


def test_regression_case_timeout_emits_bounded_progress(monkeypatch, tmp_path):
    calls = []
    events = []
    monkeypatch.setattr(
        regression, "evaluate_project",
        lambda *_args, **kwargs: calls.append(kwargs) or {
            "status": "blocked", "blocker": "field_trial_case_timeout",
            "project_min_score": 0.0,
        },
    )
    before = [{
        "project": "slow", "project_dir": tmp_path,
        "result": {"status": "ok", "project_min_score": 9.7},
    }]

    with pytest.raises(regression.RegressionGateBudgetExceeded) as raised:
        regression_failures(
            tmp_path, before, repetitions=3, case_timeout_seconds=12,
            total_timeout_seconds=60, progress=events.append,
        )

    assert raised.value.reason == "regression_case_timeout"
    assert calls[0]["timeout_seconds"] <= 12
    assert [event["stage"] for event in events] == [
        "regression_case_started", "regression_case_completed",
    ]
    assert events[-1]["completed"] == 1
    assert events[-1]["total"] == 3


def test_regression_evaluation_uses_full_execution_feedback_route(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(
        "runtime.role_foundation_field_trial._run_isolated_case",
        lambda **kwargs: calls.append(kwargs) or {
            "status": "ok", "project_min_score": 9.7,
        },
    )

    from runtime.improvement_plugins.candidate_selection_regression import evaluate_projects

    rows = evaluate_projects(tmp_path, [tmp_path / "control"])

    assert rows[0]["result"]["project_min_score"] == 9.7
    assert calls == [{
        "root": tmp_path,
        "project_dir": tmp_path / "control",
        "write": True,
        "executable_acceptance": True,
    }]
