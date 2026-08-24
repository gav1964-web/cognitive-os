from runtime.improvement_plugins.candidate_selection_regression import regression_failures


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
