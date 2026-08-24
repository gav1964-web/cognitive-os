import json

from runtime.improvement_plugins import candidate_selection_admission as admission
from runtime.improvement_plugins.candidate_selection_holdout import _repair_legacy_preflight
from runtime.knowledge_admission import build_kb_candidate, write_kb_candidate


def _root(tmp_path):
    path = tmp_path / "knowledge/role_knowledge/promoted_candidate_selection_policies.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "schema_version": "promoted_candidate_selection_policies.v1", "policies": [],
    }), encoding="utf-8")
    return tmp_path


def _stage(root, project):
    record = {
        "contrast_id": "side_effectful_target:measured_candidate_reselection",
        "failed_contract": {
            "acceptance_signal": "meta_only", "return_paths": 0,
            "output_inference_basis": "no_value_return", "observed_side_effects": [],
        },
        "successful_contract": {
            "acceptance_signal": "executable_callable", "return_paths": 1,
            "output_inference_basis": "return_expression", "observed_side_effects": [],
        },
    }
    candidate = build_kb_candidate(
        record_type="foundation_selection_contrast", proposed_record=record,
        source_cases=[{"project": project, "status": "confirmed"}],
        teacher_reference="measured contrast",
    )
    write_kb_candidate(candidate, root=root)


def _effect():
    return {
        "status": "confirmed_selection_effect", "score_delta": 0.9,
        "role_regressions": [],
        "control": {"selected_candidate_quality": {"structural_evidence": {}}},
        "treatment": {
            "selected_candidate_quality": {"structural_evidence": {}},
            "selected_extraction_candidate": "app.py:build_value",
            "downstream_evidence": {"acceptance_signal": "executable_callable"},
        },
    }


def test_current_staged_contrast_is_holdout_not_training(monkeypatch, tmp_path):
    root = _root(tmp_path)
    for project in ("alpha", "beta", "gamma", "holdout"):
        _stage(root, project)
    holdout = root / "holdout"
    holdout.mkdir()
    monkeypatch.setattr(admission, "_holdout_effect", lambda *_args: _effect())

    result = admission.run({
        "root": root,
        "project_dir": holdout,
        "failure_packet": {
            "selected_candidate": "app.py:write_only",
            "downstream_evidence": {"acceptance_signal": "meta_only"},
        },
        "diagnosis": {"recommended_source": "app.py:build_value"},
        "plugin_config": {"minimum_confirmed_cases": 3},
    })

    assert result["status"] == "trial_passed"
    assert result["evolution"]["gates"]["independent_holdout"] is True
    assert result["policy_id"] == "side_effectful_target:measured_candidate_reselection"


def test_current_contrast_can_revalidate_quarantined_legacy_policy(monkeypatch, tmp_path):
    root = _root(tmp_path)
    _stage(root, "holdout")
    policy_path = root / "knowledge/role_knowledge/promoted_candidate_selection_policies.json"
    policy_path.write_text(json.dumps({
        "schema_version": "promoted_candidate_selection_policies.v1",
        "policies": [{
            "id": "side_effectful_target:measured_candidate_reselection",
            "trigger": "executable_acceptance_rejected", "trigger_signals": ["meta_only"],
            "selection_mode": "stable_partition_existing_candidates",
            "preflight_trigger_requirements": {"output_inference_basis": ["no_value_return"]},
            "structural_requirements": {
                "min_return_paths": 1,
                "forbidden_output_inference_basis": ["no_value_return"],
            },
            "numeric_bonus": False,
            "promotion_evidence": {
                "confirmed_projects": ["alpha", "beta", "gamma"],
                "holdout_project": "prior_holdout",
            },
        }],
    }), encoding="utf-8")
    admission.load_selection_policies.cache_clear()
    holdout = root / "holdout"
    holdout.mkdir()
    monkeypatch.setattr(admission, "_holdout_effect", lambda *_args: _effect())

    result = admission.run({
        "root": root, "project_dir": holdout,
        "failure_packet": {
            "selected_candidate": "app.py:write_only",
            "downstream_evidence": {"acceptance_signal": "meta_only"},
        },
        "diagnosis": {"failure_class": "side_effectful_target",
                      "recommended_source": "app.py:build_value"},
        "plugin_config": {"minimum_confirmed_cases": 3},
    })

    assert result["status"] == "trial_passed"
    assert result["policy_id"] == "side_effectful_target:measured_candidate_reselection"


def test_legacy_revalidation_repairs_unreachable_output_preflight():
    repaired = _repair_legacy_preflight({
        "preflight_trigger_requirements": {"output_inference_basis": ["return_expression"]},
        "structural_requirements": {
            "forbidden_output_inference_basis": ["no_value_return"],
        },
    })

    assert repaired["preflight_trigger_requirements"]["output_inference_basis"] == [
        "no_value_return", "return_expression",
    ]
