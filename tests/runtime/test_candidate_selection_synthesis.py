from runtime.improvement_plugins.candidate_selection_synthesis import (
    synthesized_discriminator_families,
)
from runtime.improvement_plugins import candidate_selection_admission as admission
import json


def _record(project: str, *, literal: bool, successful_costs=None):
    return {
        "_confirmed_projects": [project],
        "failed_contract": {
            "acceptance_signal": "meta_only",
            "argument_count": 1,
            "literal_return_only": literal,
            "observed_side_effects": ["filesystem_read"],
            "output_inference_basis": "return_expression",
            "return_paths": 1,
        },
        "successful_contract": {
            "acceptance_signal": "executable_callable",
            "argument_count": 1,
            "literal_return_only": False,
            "observed_side_effects": [],
            "output_inference_basis": "explicit_return_annotation",
            "return_paths": 1,
            "execution_cost_rules": successful_costs or [],
        },
    }


def test_synthesis_combines_support_across_heterogeneous_complete_policies():
    records = [
        _record("alpha", literal=True),
        _record("beta", literal=False, successful_costs=["protocol_input"]),
        _record("gamma", literal=False),
    ]

    families = synthesized_discriminator_families([{
        "id": "side_effectful_target:measured_candidate_reselection",
        "records": records,
    }])
    side_effect_family = next(
        row for row in families
        if row["policy"]["structural_requirements"] == {
            "no_observed_side_effects": True,
        }
    )

    assert side_effect_family["projects"] == {"alpha", "beta", "gamma"}
    assert side_effect_family["policy"]["preflight_trigger_requirements"] == {
        "observed_side_effects": "nonempty",
    }
    assert ":synthesized_" in side_effect_family["id"]


def test_synthesis_does_not_use_unknown_dependency_as_separator():
    record = _record("alpha", literal=False)
    record["failed_contract"]["dependency_status"] = "unknown"
    record["successful_contract"]["dependency_status"] = "ready"

    families = synthesized_discriminator_families([{
        "id": "contrast", "records": [record],
    }])

    assert all(
        "forbidden_dependency_status"
        not in row["policy"]["structural_requirements"]
        for row in families
    )


def test_synthesis_keeps_failure_signals_separate():
    first = _record("alpha", literal=False)
    second = _record("beta", literal=False)
    second["failed_contract"]["acceptance_signal"] = "not_measured"

    families = synthesized_discriminator_families([{
        "id": "contrast", "records": [first, second],
    }])
    side_effects = [
        row for row in families
        if row["policy"]["structural_requirements"] == {
            "no_observed_side_effects": True,
        }
    ]

    assert {tuple(row["policy"]["trigger_signals"]) for row in side_effects} == {
        ("meta_only",), ("not_measured",),
    }


def test_admission_uses_shared_atom_when_complete_policies_differ(tmp_path, monkeypatch):
    policy_path = (
        tmp_path / "knowledge" / "role_knowledge"
        / "promoted_candidate_selection_policies.json"
    )
    policy_path.parent.mkdir(parents=True)
    policy_path.write_text(json.dumps({
        "schema_version": "promoted_candidate_selection_policies.v1", "policies": [],
    }), encoding="utf-8")
    records = [
        _record("alpha", literal=True),
        _record("beta", literal=False, successful_costs=["protocol_input"]),
        _record("gamma", literal=False),
    ]
    monkeypatch.setattr(admission, "_contrast_groups", lambda _root: [{
        "id": "side_effectful_target:measured_candidate_reselection",
        "records": records, "projects": {"alpha", "beta", "gamma"},
    }])
    monkeypatch.setattr(admission, "_holdout_effect", lambda *_args: {
        "status": "confirmed_selection_effect", "score_delta": 0.9,
        "role_regressions": [],
        "control": {"selected_candidate_quality": {"structural_evidence": {
            "observed_side_effects": ["filesystem_read"],
            "output_inference_basis": "return_expression",
        }}},
        "treatment": {
            "selected_extraction_candidate": "app.py:parse",
            "selected_candidate_quality": {"structural_evidence": {
                "observed_side_effects": [],
                "output_inference_basis": "explicit_return_annotation",
            }},
        },
    })
    holdout = tmp_path / "holdout"
    holdout.mkdir()

    result = admission.run({
        "root": tmp_path, "project_dir": holdout,
        "failure_packet": {
            "selected_candidate": "app.py:load",
            "downstream_evidence": {"acceptance_signal": "meta_only"},
        },
        "diagnosis": {
            "failure_class": "side_effectful_target",
            "recommended_source": "app.py:parse",
        },
        "plugin_config": {"minimum_confirmed_cases": 3},
        "promote": False,
    })

    assert result["status"] == "trial_passed"
    assert ":synthesized_" in result["policy_id"]
    assert result["evolution"]["gates"]["structural_discriminator"] is True
