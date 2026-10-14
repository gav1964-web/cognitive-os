from pathlib import Path

from runtime import self_improvement_hypothesis_validation as validation
from runtime.self_improvement_hypothesis_validation import _limit_prior_projects


def test_prior_probe_budget_stops_at_required_matching_minimum():
    projects = [Path(f"project_{index}") for index in range(8)]

    assert _limit_prior_projects(projects, 4) == projects[:4]


def test_prior_matches_are_regression_evidence_not_training_cases(monkeypatch, tmp_path):
    prior = tmp_path / "prior"
    fresh = tmp_path / "fresh"
    prior.mkdir(); fresh.mkdir()
    monkeypatch.setattr(validation, "_prior_matching_projects", lambda *_args: [prior])
    trained = []
    report = {
        "project": "source",
        "knowledge_candidate_path": "candidate.json",
        "diagnosis": {"failure_class": "side_effectful_target"},
        "baseline": {
            "downstream_evidence": {"reason": "side_effectful_target"},
            "selected_candidate_quality": {"structural_evidence": {
                "observed_side_effects": ["memory_state"],
                "output_inference_basis": "no_value_return",
            }},
        },
    }
    policy = {"hypothesis_holdout": {
        "query_profiles": {"side_effectful_target": ["state management"]},
        "minimum_projects": 2, "minimum_new_projects": 1, "maximum_projects": 3,
    }}

    result = validation.run_hypothesis_validation(
        root=tmp_path, training=[report], discover=lambda _plan: [fresh],
        trainer=lambda **kwargs: trained.append(kwargs["project_dir"].name) or {
            "project": kwargs["project_dir"].name, "status": "hypothesis_not_confirmed",
        },
        target_score=9.7, regression_projects=[], promote_config=False,
        write=False, policy=policy,
    )

    assert result["status"] == "completed"
    assert trained == ["fresh"]
