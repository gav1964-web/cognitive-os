import json
from pathlib import Path

from runtime.self_improvement_hypothesis_validation import run_hypothesis_validation


def _training_report():
    return {
        "project": "source", "knowledge_candidate_path": "candidate.json",
        "diagnosis": {"failure_class": "side_effectful_target"},
        "baseline": {
            "downstream_evidence": {"reason": "side_effectful_target"},
            "selected_candidate_quality": {"structural_evidence": {
                "observed_side_effects": ["memory_state"],
                "output_inference_basis": "no_value_return",
            }},
        },
    }


def _policy():
    return {"hypothesis_holdout": {
        "query_profiles": {"side_effectful_target": ["state management"]},
        "minimum_projects": 2, "maximum_projects": 3,
        "maximum_search_pages": 2, "maximum_discovery_rounds": 1,
        "signature_normalization": {"output_basis_families": {
            "void_side_effect": ["no_value_return", "explicit_none_annotation"],
        }},
    }}


def _matching_probe(**_kwargs):
    return {
        "source_fingerprint": "unchanged",
        "baseline": {
            "project_min_score": 8.8,
            "downstream_evidence": {"reason": "side_effectful_target"},
            "selected_candidate_quality": {"structural_evidence": {
                "observed_side_effects": ["memory_state"],
                "output_inference_basis": "explicit_none_annotation",
            }},
        },
        "diagnosis": {"failure_class": "side_effectful_target"},
    }


def test_validation_reuses_durable_exact_probe_after_plan_evolution(tmp_path: Path):
    prior = tmp_path / "artifacts" / "hypothesis_holdouts" / "old" / "src" / "prior_match"
    fresh = tmp_path / "fresh_match"
    prior.mkdir(parents=True); fresh.mkdir()
    reports = tmp_path / "artifacts" / "self_improvement"
    reports.mkdir(parents=True)
    reports.joinpath("hypothesis_validation_old.json").write_text(json.dumps({
        "plan": {
            "failure_class": "side_effectful_target",
            "portable_signature": "side_effectful_target|memory_state|no_value_return",
        },
        "probe_results": [{
            "project": "prior_match", "project_dir": prior.as_posix(),
            "failure_class": "side_effectful_target",
            "portable_signature": "side_effectful_target|memory_state|explicit_none_annotation",
            "matches_hypothesis": False,
            "retrieval_alignment": {
                "target": "state.py:Store.update", "aligned": True,
            },
        }],
    }), encoding="utf-8")
    observed_plans = []
    trained = []

    observed_probes = []

    def probe(**kwargs):
        observed_probes.append((kwargs["project_dir"].name, kwargs.get("evaluation_target")))
        return _matching_probe(**kwargs)

    result = run_hypothesis_validation(
        root=tmp_path, training=[_training_report()],
        discover=lambda plan: observed_plans.append(plan) or [fresh],
        trainer=lambda **kwargs: trained.append((
            kwargs["project_dir"].name,
            sorted(path.name for path in kwargs["regression_projects"]),
        )) or {
            "project": kwargs["project_dir"].name, "status": "hypothesis_not_confirmed",
        },
        probe=probe, target_score=9.7, regression_projects=[],
        promote_config=True, write=False, policy=_policy(),
    )

    assert result["prior_evidence_project_count"] == 1
    assert result["discovered_project_count"] == 1
    assert result["matching_project_count"] == 2
    assert trained == [("fresh_match", ["prior_match"])]
    assert "prior_match" in observed_plans[0]["excluded_projects"]
    assert result["probe_results"][0]["evidence_source"] == "prior_validation"
    assert observed_probes[0] == ("prior_match", "state.py:Store.update")
    assert result["plan"]["portable_signature"] == "side_effectful_target|memory_state|void_side_effect"
