from runtime.improvement_plugins import candidate_selection_admission as admission


def test_admission_rejects_mismatched_control_family(monkeypatch, tmp_path):
    policy = {
        "id": "returning_candidate",
        "trigger_signals": ["meta_only"],
        "structural_requirements": {
            "min_return_paths": 1,
            "forbidden_output_inference_basis": ["no_value_return"],
        },
        "preflight_trigger_requirements": {
            "output_inference_basis": ["no_value_return"],
        },
    }
    monkeypatch.setattr(admission, "_contrast_groups", lambda _root: [{"id": "failure", "records": []}])
    monkeypatch.setattr(admission, "_structural_families", lambda _groups: [{
        "id": "failure", "projects": {"alpha", "beta", "gamma"}, "policy": policy,
    }])
    monkeypatch.setattr(admission, "_holdout_effect", lambda *_args: {
        "status": "confirmed_selection_effect",
        "control": {"selected_candidate_quality": {"structural_evidence": {
            "return_paths": 1, "output_inference_basis": "explicit_return_annotation",
        }}},
        "treatment": {"selected_candidate_quality": {"structural_evidence": {
            "return_paths": 1, "output_inference_basis": "return_expression",
        }}},
    })
    holdout = tmp_path / "holdout"
    holdout.mkdir()

    result = admission.run({
        "root": tmp_path,
        "project_dir": holdout,
        "failure_packet": {
            "selected_candidate": "app.py:annotated",
            "downstream_evidence": {"acceptance_signal": "meta_only"},
        },
        "diagnosis": {
            "failure_class": "failure",
            "recommended_source": "app.py:build_value",
        },
        "plugin_config": {"minimum_confirmed_cases": 3},
    })

    assert result["status"] == "blocked"
    assert result["reason"] == "no_structural_discriminator"
