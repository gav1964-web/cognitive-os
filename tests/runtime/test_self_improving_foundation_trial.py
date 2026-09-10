from __future__ import annotations

from tests.runtime.self_improving_foundation_trial_helpers import *

def test_promotion_count_includes_post_training_admission():
    report = {
        "improvement_plugin_cycle": {"promotion_count": 1},
        "post_training_admission": {"promotion_count": 2},
    }

    assert _promotion_count(report) == 3


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
    assert result["status"] == "critical_intervention_required"
    assert result["critical_intervention"]["reason"] == "no_safe_autonomous_promotion"
    assert result["summary"]["eligible_failure_count"] == 2
    assert [event["stage"] for event in progress] == [
        "baseline_started", "baseline_completed", "training_started",
        "training_completed", "verification_skipped", "completed",
    ]


def test_trial_does_not_remeasure_unchanged_active_policy(monkeypatch, tmp_path: Path):
    case = {
        "project": "weak", "project_dir": str(tmp_path / "weak"),
        "status": "ok", "project_min_score": 9.0,
    }
    measurements = []

    def measure(**kwargs):
        measurements.append(kwargs)
        return _report([case])

    monkeypatch.setattr(
        "runtime.self_improving_foundation_trial.run_role_foundation_field_trial", measure,
    )
    result = run_self_improving_foundation_trial(
        root=tmp_path, project_roots=[tmp_path], max_iterations=1, write=False,
        _trainer=lambda **kwargs: {
            "status": "hypothesis_not_confirmed",
            "outcome": {"target_reached": False},
            "improvement_plugin_cycle": {"promotion_count": 0},
        },
    )

    assert len(measurements) == 1
    assert result["iterations"][0]["verification"] is result["baseline"]


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


def test_trial_delegates_config_promotion_to_plugin_policy(monkeypatch, tmp_path: Path):
    weak = {
        "project": "weak", "project_dir": str(tmp_path / "weak"),
        "status": "ok", "project_min_score": 9.0,
    }
    stable = {
        "project": "stable", "project_dir": str(tmp_path / "stable"),
        "status": "ok", "project_min_score": 9.8,
    }
    reports = iter([_report([weak, stable]), _report([weak, stable])])
    monkeypatch.setattr(
        "runtime.self_improving_foundation_trial.run_role_foundation_field_trial",
        lambda **kwargs: next(reports),
    )
    calls = []

    def train(**kwargs):
        calls.append(kwargs)
        return {"status": "hypothesis_not_confirmed", "outcome": {"target_reached": False}}

    result = run_self_improving_foundation_trial(
        root=tmp_path, project_roots=[tmp_path], write=False, _trainer=train,
    )

    assert calls[0]["promote_config"] is None
    assert result["invariants"]["config_promotion_mode"] == "plugin_policy"


def test_trial_repeats_autonomously_after_measured_promotion(monkeypatch, tmp_path: Path):
    weak = lambda score, status="needs_work": _report([{
        "project": "weak", "project_dir": str(tmp_path / "weak"),
        "status": "ok", "project_min_score": score,
    }], status=status)
    reports = iter([weak(9.0), weak(9.4), weak(9.7, status="ok")])
    monkeypatch.setattr(
        "runtime.self_improving_foundation_trial.run_role_foundation_field_trial",
        lambda **kwargs: next(reports),
    )
    calls = []

    def train(**kwargs):
        calls.append(kwargs)
        return {
            "status": "candidate_improvement_confirmed",
            "outcome": {"target_reached": False},
            "improvement_plugin_cycle": {"promotion_count": 1},
        }

    result = run_self_improving_foundation_trial(
        root=tmp_path, project_roots=[tmp_path], max_training_projects=1,
        max_iterations=3, write=False, _trainer=train,
    )

    assert result["status"] == "target_verified"
    assert len(calls) == 2
    assert result["summary"]["iteration_count"] == 2
    assert result["critical_intervention"]["required"] is False


def test_trial_rolls_back_promotion_rejected_by_corpus_gate(monkeypatch, tmp_path: Path):
    target = tmp_path / "config" / "executable_acceptance_policy.json"
    target.parent.mkdir(parents=True)
    target.write_text('{"state":"before"}\n', encoding="utf-8")
    case = lambda score: _report([{
        "project": "weak", "project_dir": str(tmp_path / "weak"),
        "status": "ok", "project_min_score": score,
    }])
    reports = iter([case(9.0), case(8.0), case(9.0)])
    monkeypatch.setattr(
        "runtime.self_improving_foundation_trial.run_role_foundation_field_trial",
        lambda **kwargs: next(reports),
    )

    def train(**kwargs):
        target.write_text('{"state":"promoted"}\n', encoding="utf-8")
        return {
            "status": "candidate_improvement_confirmed",
            "outcome": {"target_reached": False},
            "improvement_plugin_cycle": {"promotion_count": 1},
        }

    result = run_self_improving_foundation_trial(
        root=tmp_path, project_roots=[tmp_path], max_training_projects=1,
        max_iterations=3, write=False, _trainer=train,
    )

    assert result["status"] == "critical_intervention_required"
    assert result["critical_intervention"]["reason"] == "promotion_failed_corpus_gate"
    assert result["iterations"][0]["rollback"]["applied"] is True
    assert target.read_text(encoding="utf-8") == '{"state":"before"}\n'


def test_trial_collects_staged_learning_from_distinct_failures(monkeypatch, tmp_path: Path):
    cases = [
        {"project": "first", "project_dir": str(tmp_path / "first"), "status": "needs_review", "project_min_score": 5.0},
        {"project": "second", "project_dir": str(tmp_path / "second"), "status": "needs_review", "project_min_score": 6.0},
    ]
    monkeypatch.setattr(
        "runtime.self_improving_foundation_trial.run_role_foundation_field_trial",
        lambda **kwargs: _report(cases),
    )
    trained = []

    def train(**kwargs):
        trained.append(kwargs["project_dir"].name)
        return {
            "status": "hypothesis_not_confirmed",
            "outcome": {"target_reached": False},
            "knowledge_candidate_path": str(tmp_path / f"{trained[-1]}.json"),
            "trial_conclusion": {"recommended_change_type": "staged_capability_gap"},
            "improvement_plugin_cycle": {"promotion_count": 0},
        }

    result = run_self_improving_foundation_trial(
        root=tmp_path, project_roots=[tmp_path], max_training_projects=1,
        max_iterations=2, write=False, _trainer=train,
    )

    assert trained == ["first", "second"]
    assert result["critical_intervention"]["reason"] == "autonomous_evidence_exhausted_without_promotion"


def test_trial_escalates_repeated_gap_as_missing_plugin(monkeypatch, tmp_path: Path):
    cases = [
        {"project": name, "project_dir": str(tmp_path / name), "status": "needs_review", "project_min_score": 5.0}
        for name in ("first", "second", "third")
    ]
    monkeypatch.setattr(
        "runtime.self_improving_foundation_trial.run_role_foundation_field_trial",
        lambda **kwargs: _report(cases),
    )

    def train(**kwargs):
        project = kwargs["project_dir"].name
        candidate_dir = tmp_path / "artifacts" / "knowledge_candidates"
        candidate_dir.mkdir(parents=True, exist_ok=True)
        candidate = {
            "candidate_id": f"candidate_{project}",
            "record_type": "foundation_capability_gap",
            "proposed_record": {
                "gap_id": "first_slice_reselection_required:no_viable_executable_candidate:low_viability|external_effect|function",
                "label": "No viable executable candidate",
                "role_scope": ["architect", "spec_writer"],
            },
            "source_cases": [{"project": project, "status": "observed"}],
        }
        path = candidate_dir / f"{project}.json"
        path.write_text(json.dumps(candidate), encoding="utf-8")
        return {
            "status": "hypothesis_not_confirmed",
            "diagnosis": {"failure_class": "first_slice_reselection_required"},
            "knowledge_candidate_path": str(path),
            "trial_conclusion": {
                "recommended_change_type": "staged_capability_gap",
                "next_hypothesis": "no_viable_executable_candidate",
                "capability_signature": "low_viability|external_effect|function",
            },
            "improvement_plugin_cycle": {
                "promotion_count": 0,
                "attempts": [{"status": "not_applicable"}],
            },
        }

    result = run_self_improving_foundation_trial(
        root=tmp_path, project_roots=[tmp_path], max_training_projects=3,
        max_iterations=1, write=False, _trainer=train,
    )

    assert result["critical_intervention"]["reason"] == "missing_registered_improvement_capability"
    request = result["capability_development_requests"][0]
    assert request["missing_capability"] == "bounded_executable_target_discovery_or_sandbox_adapter"
    assert request["observed_projects"] == ["first", "second", "third"]
    dossier = result["self_development_shadow_dossiers"][0]
    assert dossier["status"] == "shadow_only"
    assert dossier["proposal"]["classification"]["class"] == "L3"
    assert dossier["admissions"]["promote"]["status"] == "external_review_required"
    assert dossier["constraints"]["promotion_applied"] is False


def test_trial_escalates_repeated_parameter_search_as_missing_strategy(monkeypatch, tmp_path: Path):
    cases = [
        {"project": name, "project_dir": str(tmp_path / name), "status": "ok", "project_min_score": 7.5}
        for name in ("first", "second", "third")
    ]
    monkeypatch.setattr(
        "runtime.self_improving_foundation_trial.run_role_foundation_field_trial",
        lambda **kwargs: _report(cases),
    )

    def train(**kwargs):
        project = kwargs["project_dir"].name
        return {
            "project": project,
            "status": "hypothesis_not_confirmed",
            "diagnosis": {
                "failure_class": "executable_sample_contract",
                "target_roles": ["spec_writer"],
            },
            "knowledge_candidate_path": str(tmp_path / f"{project}.json"),
            "trial_conclusion": {
                "recommended_change_type": "none",
                "next_hypothesis": "continue_bounded_parameter_search",
            },
            "improvement_plugin_cycle": {
                "promotion_count": 0,
                "attempts": [{"status": "not_applicable"}],
            },
        }

    result = run_self_improving_foundation_trial(
        root=tmp_path, project_roots=[tmp_path], max_training_projects=3,
        max_iterations=2, write=False, _trainer=train,
    )

    assert result["critical_intervention"]["reason"] == "missing_registered_improvement_capability"
    request = result["capability_development_requests"][0]
    assert request["missing_capability"] == "bounded_parameter_strategy_plugin"
    assert request["observed_projects"] == ["first", "second", "third"]
