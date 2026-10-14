from __future__ import annotations

from tests.runtime.self_improving_foundation_trial_helpers import *

def test_trial_requests_strategy_extension_after_registered_plugin_exhaustion(monkeypatch, tmp_path):
    cases = [
        {"project": name, "project_dir": str(tmp_path / name), "status": "ok", "project_min_score": score}
        for name, score in (("first", 8.0), ("second", 8.1), ("third", 8.2))
    ]
    monkeypatch.setattr(
        "runtime.self_improving_foundation_trial.run_role_foundation_field_trial",
        lambda **kwargs: _report(cases),
    )

    def train(**kwargs):
        project = kwargs["project_dir"].name
        return {
            "project": project, "status": "hypothesis_not_confirmed",
            "diagnosis": {"failure_class": "executable_sample_contract", "target_roles": ["spec_writer"]},
            "knowledge_candidate_path": str(tmp_path / f"{project}.json"),
            "trial_conclusion": {"recommended_change_type": "none", "next_hypothesis": "continue_bounded_parameter_search"},
            "improvement_plugin_cycle": {"promotion_count": 0, "attempts": [{
                "plugin_id": "bounded_parameter_strategy", "status": "blocked",
            }]},
        }

    result = run_self_improving_foundation_trial(
        root=tmp_path, project_roots=[tmp_path], max_training_projects=3,
        max_iterations=2, write=False, _trainer=train,
    )

    assert result["capability_development_requests"][0]["missing_capability"] == (
        "bounded_parameter_strategy_extension"
    )


def test_curriculum_resumes_latest_critical_report_for_same_corpus(tmp_path: Path):
    cases = [{"project": "first"}, {"project": "second"}]
    fingerprint = "engine-v2"
    directory = tmp_path / "artifacts" / "self_improvement"
    directory.mkdir(parents=True)
    (directory / "self_improving_foundation_trial_1.json").write_text(json.dumps({
        "status": "critical_intervention_required",
        "improvement_engine_fingerprint": fingerprint,
        "baseline": {"cases": [{"project": "first"}, {"project": "second"}]},
        "training": [{"project": "first"}],
    }), encoding="utf-8")
    (directory / "self_improving_foundation_trial_2.json").write_text(json.dumps({
        "status": "critical_intervention_required",
        "improvement_engine_fingerprint": fingerprint,
        "baseline": {"cases": [{"project": "first"}, {"project": "second"}]},
        "training": [{"project": "second"}],
    }), encoding="utf-8")

    assert _prior_attempted_projects(tmp_path, cases, fingerprint) == {"first", "second"}
    assert _prior_attempted_projects(tmp_path, cases, "engine-v3") == set()
