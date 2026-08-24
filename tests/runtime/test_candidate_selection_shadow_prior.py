from runtime.improvement_plugins import candidate_selection_shadow_prior as prior


def _record(project):
    return {
        "_confirmed_projects": [project],
        "failed_contract": {
            "acceptance_signal": "meta_only",
            "observed_side_effects": ["filesystem_read"],
            "output_inference_basis": "return_expression",
        },
        "successful_contract": {
            "acceptance_signal": "executable_callable",
            "observed_side_effects": [],
            "output_inference_basis": "explicit_return_annotation",
        },
    }


def test_shadow_prior_moves_supported_structural_match_into_trial_budget(
    tmp_path, monkeypatch,
):
    records = [_record("alpha"), _record("beta")]
    monkeypatch.setattr(prior, "contrast_groups", lambda _root: [{
        "id": "side_effectful_target:measured_candidate_reselection",
        "records": records,
        "projects": {"alpha", "beta"},
    }])

    def evidence(_project, target):
        explicit = target.endswith(":portable")
        return {"snippet": {"structural_contract": {
            "source_body_complete": True,
            "argument_count": 0 if explicit else 2,
            "called_operations": [] if explicit else ["service.call"],
            "return_paths": 1,
            "observed_side_effects": [],
            "output_inference_basis": (
                "explicit_return_annotation" if explicit else "return_expression"
            ),
        }}}

    monkeypatch.setattr(prior, "source_target_evidence", evidence)
    candidates = [f"app.py:ordinary_{index}" for index in range(5)] + ["app.py:portable"]

    ordered, trace = prior.prioritize_shadow_candidates(
        root=tmp_path, project_dir=tmp_path / "holdout", candidates=candidates,
        packet={
            "candidate_quality": {"structural_evidence": {
                "observed_side_effects": ["filesystem_read"],
                "output_inference_basis": "return_expression",
            }},
            "downstream_evidence": {"acceptance_signal": "meta_only"},
        },
        failure_class="side_effectful_target",
    )

    assert ordered[0] == "app.py:portable"
    assert trace[0]["candidate"] == "app.py:portable"
    assert trace[0]["support"] >= 2


def test_shadow_prior_excludes_current_project_from_support(tmp_path, monkeypatch):
    records = [_record("holdout"), _record("alpha")]
    monkeypatch.setattr(prior, "contrast_groups", lambda _root: [{
        "id": "side_effectful_target:measured_candidate_reselection",
        "records": records,
        "projects": {"holdout", "alpha"},
    }])
    monkeypatch.setattr(prior, "source_target_evidence", lambda *_args: {
        "snippet": {"structural_contract": {
            "observed_side_effects": [],
            "output_inference_basis": "explicit_return_annotation",
        }},
    })

    ordered, trace = prior.prioritize_shadow_candidates(
        root=tmp_path, project_dir=tmp_path / "holdout", candidates=["app.py:portable"],
        packet={
            "candidate_quality": {"structural_evidence": {
                "observed_side_effects": ["filesystem_read"],
                "output_inference_basis": "return_expression",
            }},
            "downstream_evidence": {"acceptance_signal": "meta_only"},
        },
        failure_class="side_effectful_target", minimum_support=2,
    )

    assert ordered == ["app.py:portable"]
    assert trace == []
