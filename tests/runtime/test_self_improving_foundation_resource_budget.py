from pathlib import Path

from runtime.self_improving_foundation_trial import run_self_improving_foundation_trial


def test_trial_routes_resource_timeout_to_capability_request(monkeypatch, tmp_path: Path):
    timeout_case = {
        "project": "slow", "project_dir": str(tmp_path / "slow"),
        "status": "blocked", "blocker": "field_trial_case_timeout",
        "project_min_score": 0.0,
    }
    monkeypatch.setattr(
        "runtime.self_improving_foundation_trial.run_role_foundation_field_trial",
        lambda **_kwargs: {"status": "needs_work", "cases": [timeout_case]},
    )

    result = run_self_improving_foundation_trial(
        root=tmp_path, project_roots=[tmp_path], max_iterations=1, write=False,
        _trainer=lambda **_kwargs: (_ for _ in ()).throw(AssertionError("trainer called")),
    )

    request = result["capability_development_requests"][0]
    assert request["missing_capability"] == "bounded_foundation_analysis_optimization"
    assert request["observed_projects"] == ["slow"]
    assert result["summary"]["resource_blocked_project_count"] == 1
