from pathlib import Path

from runtime.self_improvement_hypothesis_validation import (
    build_validation_plan,
    run_hypothesis_validation,
)
from runtime.self_improving_foundation_trial import run_self_improving_foundation_trial


def _training_report(project="source"):
    return {
        "project": project,
        "status": "candidate_improvement_confirmed",
        "knowledge_candidate_path": f"artifacts/{project}.json",
        "diagnosis": {"failure_class": "side_effectful_target"},
        "baseline": {
            "downstream_evidence": {"reason": "side_effectful_target"},
            "selected_candidate_quality": {"structural_evidence": {
                "observed_side_effects": ["memory_state"],
                "output_inference_basis": "no_value_return",
            }},
        },
        "improvement_plugin_cycle": {"promotion_count": 0},
    }


def _policy():
    return {"hypothesis_holdout": {
        "provider": "gitlab", "minimum_projects": 2, "maximum_projects": 3,
        "maximum_search_pages": 2,
        "query_profiles": {"side_effectful_target": ["state management", "command handler"]},
    }}


def test_validation_plan_is_portable_and_excludes_training_project():
    plan = build_validation_plan([_training_report("private_project")], _policy())

    assert plan["failure_class"] == "side_effectful_target"
    assert plan["portable_signature"] == "side_effectful_target|memory_state|no_value_return"
    assert plan["queries"] == ["state management", "command handler"]
    assert plan["excluded_projects"] == ["private_project"]
    assert "private_project" not in plan["portable_signature"]


def test_hypothesis_validation_trains_sequential_independent_holdouts(tmp_path: Path):
    projects = [tmp_path / name for name in ("holdout_one", "holdout_two", "holdout_three")]
    for project in projects:
        project.mkdir()
    trained = []

    def trainer(**kwargs):
        trained.append(kwargs["project_dir"].name)
        promoted = kwargs["project_dir"].name == "holdout_two"
        return {
            "project": kwargs["project_dir"].name,
            "status": "candidate_improvement_confirmed",
            "post_training_admission": {"promotion_count": int(promoted)},
            "trained_attempt": {"project_min_score": 9.7},
        }

    result = run_hypothesis_validation(
        root=tmp_path, training=[_training_report()], discover=lambda _plan: projects,
        trainer=trainer, target_score=9.7, regression_projects=[],
        promote_config=True, write=False, policy=_policy(),
    )

    assert result["status"] == "completed"
    assert result["decision"] == "hypothesis_promoted"
    assert result["promotion_count"] == 1
    assert trained == ["holdout_one", "holdout_two", "holdout_three"]


def test_foundation_trial_automatically_validates_staged_hypothesis(monkeypatch, tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    holdouts = [tmp_path / "holdout_one", tmp_path / "holdout_two"]
    for path in holdouts:
        path.mkdir()
    baseline = {"status": "needs_work", "cases": [{
        "project": "source", "project_dir": str(source),
        "status": "ok", "project_min_score": 8.8,
    }]}
    verified = {"status": "ok", "cases": [{
        "project": "source", "project_dir": str(source),
        "status": "ok", "project_min_score": 9.7,
    }]}
    measurements = iter([baseline, verified])
    monkeypatch.setattr(
        "runtime.self_improving_foundation_trial.run_role_foundation_field_trial",
        lambda **_kwargs: next(measurements),
    )

    def trainer(**kwargs):
        project = kwargs["project_dir"].name
        if project == "source":
            return _training_report(project)
        return {
            "project": project, "status": "candidate_improvement_confirmed",
            "post_training_admission": {"promotion_count": int(project == "holdout_two")},
            "trained_attempt": {"project_min_score": 9.7},
        }

    result = run_self_improving_foundation_trial(
        root=tmp_path, project_roots=[tmp_path], max_training_projects=1,
        max_iterations=1, write=False, _trainer=trainer,
        _holdout_discoverer=lambda _plan: holdouts,
    )

    validation = result["iterations"][0]["hypothesis_validation"]
    assert result["status"] == "target_verified"
    assert validation["decision"] == "hypothesis_promoted"
    assert result["summary"]["hypothesis_holdout_project_count"] == 2


def test_external_discovery_failure_is_reported_without_crashing(tmp_path: Path):
    def fail(_plan):
        raise RuntimeError("rate limited")

    result = run_hypothesis_validation(
        root=tmp_path, training=[_training_report()], discover=fail,
        trainer=lambda **_kwargs: {}, target_score=9.7, regression_projects=[],
        promote_config=True, write=False, policy=_policy(),
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "external_discovery_failed"
    assert "rate limited" in result["error"]
