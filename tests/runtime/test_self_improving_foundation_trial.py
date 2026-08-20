import json
from pathlib import Path

from runtime.self_improving_foundation_trial import _write_checkpoint, run_self_improving_foundation_trial


def _report(cases, status="needs_work"):
    return {"status": status, "cases": cases}


def test_trial_trains_weakest_case_with_stable_regression_projects(monkeypatch, tmp_path: Path):
    weak = {
        "project": "weak", "project_dir": str(tmp_path / "weak"),
        "status": "blocked_ok", "project_min_score": 9.0,
    }
    low = {
        "project": "low", "project_dir": str(tmp_path / "low"),
        "status": "ok", "project_min_score": 9.4,
    }
    stable = {
        "project": "stable", "project_dir": str(tmp_path / "stable"),
        "status": "ok", "project_min_score": 9.8,
    }
    reports = iter([_report([low, weak, stable]), _report([low, weak, stable])])
    monkeypatch.setattr(
        "runtime.self_improving_foundation_trial.run_role_foundation_field_trial",
        lambda **kwargs: next(reports),
    )
    calls = []

    def train(**kwargs):
        calls.append(kwargs)
        return {"status": "candidate_improvement_confirmed", "outcome": {"target_reached": False}}

    progress = []
    result = run_self_improving_foundation_trial(
        root=tmp_path, project_roots=[tmp_path], max_training_projects=1,
        write=False, _trainer=train, _progress=progress.append,
    )

    assert calls[0]["project_dir"] == tmp_path / "weak"
    assert calls[0]["regression_projects"] == [tmp_path / "stable"]
    assert result["status"] == "improvement_candidates_staged"
    assert result["summary"]["eligible_failure_count"] == 2
    assert [event["stage"] for event in progress] == [
        "baseline_started", "baseline_completed", "training_started",
        "training_completed", "verification_started", "completed",
    ]


def test_trial_does_not_train_out_of_scope_or_target_cases(monkeypatch, tmp_path: Path):
    cases = [
        {"project": "native", "project_dir": str(tmp_path / "native"), "status": "out_of_scope", "project_min_score": 0},
        {"project": "ready", "project_dir": str(tmp_path / "ready"), "status": "ok", "project_min_score": 9.7},
    ]
    monkeypatch.setattr(
        "runtime.self_improving_foundation_trial.run_role_foundation_field_trial",
        lambda **kwargs: _report(cases, status="ok"),
    )

    result = run_self_improving_foundation_trial(
        root=tmp_path,
        project_roots=[tmp_path],
        write=False,
        _trainer=lambda **kwargs: (_ for _ in ()).throw(AssertionError("trainer called")),
    )

    assert result["status"] == "target_verified"
    assert result["training"] == []
    assert result["summary"]["eligible_failure_count"] == 0


def test_checkpoint_preserves_completed_training_before_verification(tmp_path: Path):
    path = _write_checkpoint(
        tmp_path,
        {"report_path": "baseline.json"},
        [{
            "project": "sample", "status": "candidate_improvement_confirmed",
            "report_path": "training.json", "outcome": {"target_reached": True},
        }],
        9.7,
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["status"] == "verification_pending"
    assert payload["training"][0]["status"] == "candidate_improvement_confirmed"
