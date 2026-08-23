import json
from runtime import architect_first_slice_reselection as reselection
from runtime.improvement_plugins import candidate_selection_admission as admission
from runtime.knowledge_admission import build_kb_candidate, write_kb_candidate
from runtime.promoted_candidate_selection_policies import (
    apply_preflight_selection_policies,
    apply_selection_policies,
    load_selection_policies,
)


def _root(tmp_path):
    path = tmp_path / "knowledge" / "role_knowledge" / "promoted_candidate_selection_policies.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"schema_version": "promoted_candidate_selection_policies.v1", "policies": []}),
        encoding="utf-8",
    )
    return tmp_path
def _record(*, failed_returns=0, successful_returns=1, failed_effects=None):
    return {
        "contrast_id": "side_effectful_target:measured_candidate_reselection",
        "failed_contract": {
            "acceptance_signal": "",
            "return_paths": failed_returns,
            "output_inference_basis": "no_value_return" if failed_returns == 0 else "return_expression",
            "state_mutation": False,
            "typed_argument_count": 0,
            "observed_side_effects": list(failed_effects or []),
        },
        "successful_contract": {
            "acceptance_signal": "executable_callable",
            "return_paths": successful_returns,
            "output_inference_basis": "return_expression",
            "state_mutation": False,
            "typed_argument_count": 0,
            "observed_side_effects": [],
        },
        "numeric_bonus_from_training": False,
    }
def _stage(root, project, record=None):
    candidate = build_kb_candidate(
        record_type="foundation_selection_contrast",
        proposed_record=record or _record(),
        source_cases=[{"project": project, "status": "confirmed", "before": 8.8, "after": 9.7}],
        teacher_reference="measured candidate contrast",
    )
    write_kb_candidate(candidate, root=root)

def _effect():
    return {
        "status": "confirmed_selection_effect",
        "source": "app.py:write_only",
        "challenger": "app.py:build_value",
        "score_delta": 0.9,
        "role_regressions": [],
        "control": {"status": "ok", "project_min_score": 8.8,
                    "role_scores": {"spec_writer": 8.8}, "selected_candidate_quality": {
                        "structural_evidence": {"return_paths": 0, "output_inference_basis": "no_value_return"}}},
        "treatment": {
            "status": "ok",
            "project_min_score": 9.7,
            "role_scores": {"spec_writer": 9.7},
            "selected_extraction_candidate": "app.py:build_value",
            "selected_candidate_quality": {
                "structural_evidence": {
                    "return_paths": 1,
                    "output_inference_basis": "return_expression",
                    "state_mutation": False,
                    "typed_argument_count": 0,
                }
            },
            "downstream_evidence": {"acceptance_signal": "executable_callable"},
        },
    }

def test_selection_admission_promotes_structural_policy(monkeypatch, tmp_path):
    root = _root(tmp_path)
    for project in ("alpha", "beta", "gamma"):
        _stage(root, project)
    holdout = root / "holdout"
    holdout.mkdir()
    monkeypatch.setattr(admission, "_holdout_effect", lambda *_args: _effect())
    monkeypatch.setattr(admission, "_holdout_reproduction_failure", lambda *_args: {})

    result = admission.run({
        "root": root,
        "project_dir": holdout,
        "failure_packet": {
            "selected_candidate": "app.py:write_only",
            "downstream_evidence": {"acceptance_signal": "meta_only"},
        },
        "diagnosis": {"recommended_source": "app.py:build_value"},
        "promote": True,
        "plugin_config": {"minimum_confirmed_cases": 3},
    })

    assert result["status"] == "promoted"
    assert result["evolution"]["gates"]["structural_discriminator"] is True
    catalog = load_selection_policies(
        str(root / "knowledge" / "role_knowledge" / "promoted_candidate_selection_policies.json")
    )
    policy = catalog["policies"][0]
    assert policy["structural_requirements"]["min_return_paths"] == 1
    assert policy["numeric_bonus"] is False


def test_active_policy_reorders_only_execution_reselection(tmp_path):
    root = _root(tmp_path)
    policy_path = root / "knowledge" / "role_knowledge" / "promoted_candidate_selection_policies.json"
    policy_path.write_text(json.dumps({
        "schema_version": "promoted_candidate_selection_policies.v1",
        "policies": [{
            "id": "returning_challenger",
            "activation_state": "active",
            "trigger": "executable_acceptance_rejected",
            "trigger_signals": ["meta_only"],
            "structural_requirements": {
                "min_return_paths": 1,
                "forbidden_output_inference_basis": ["no_value_return"],
            },
            "numeric_bonus": False,
        }],
    }), encoding="utf-8")
    ranked = [
        {"target": "write", "return_paths": 0, "output_inference_basis": "no_value_return"},
        {"target": "build", "return_paths": 1, "output_inference_basis": "return_expression"},
    ]

    unchanged = apply_selection_policies(ranked, {}, path=str(policy_path))
    reordered = apply_selection_policies(
        ranked,
        {"trigger": "executable_acceptance_rejected", "blocking_evidence": {"acceptance_signal": "meta_only"}},
        path=str(policy_path),
    )

    assert [row["target"] for row in unchanged] == ["write", "build"]
    assert [row["target"] for row in reordered] == ["build", "write"]
    assert reordered[0]["selection_policy_ids"] == ["returning_challenger"]


def test_active_policy_preflight_reorders_existing_candidate_evidence(tmp_path):
    root = _root(tmp_path)
    policy_path = root / "knowledge" / "role_knowledge" / "promoted_candidate_selection_policies.json"
    policy_path.write_text(json.dumps({
        "schema_version": "promoted_candidate_selection_policies.v1",
        "policies": [{
            "id": "side_effect_free_challenger",
            "activation_state": "active",
            "trigger": "executable_acceptance_rejected",
            "trigger_signals": ["meta_only"],
            "selection_mode": "stable_partition_existing_candidates",
            "preflight_trigger_requirements": {
                "observed_side_effects": "nonempty",
                "output_inference_basis": ["no_value_return"],
            },
            "structural_requirements": {"no_observed_side_effects": True},
            "numeric_bonus": False,
        }],
    }), encoding="utf-8")
    ranked = [
        {
            "source": "write", "side_effects": ["memory_state"],
            "evidence": {"snippet": "def write():\n    STATE.append(1)"},
        },
        {"source": "build", "evidence": {"snippet": "def build():\n    return 1"}},
    ]

    reordered = apply_preflight_selection_policies(ranked, path=str(policy_path))

    assert [row["source"] for row in reordered] == ["build", "write"]
    assert reordered[0]["selection_policy_ids"] == ["side_effect_free_challenger"]


def test_admission_rejects_contrast_without_structural_difference(tmp_path):
    root = _root(tmp_path)
    record = _record(failed_returns=1, successful_returns=1)
    for project in ("alpha", "beta", "gamma"):
        _stage(root, project, record)
    holdout = root / "holdout"
    holdout.mkdir()

    result = admission.run({
        "root": root,
        "project_dir": holdout,
        "failure_packet": {
            "selected_candidate": "app.py:meta",
            "downstream_evidence": {"acceptance_signal": "meta_only"},
        },
        "diagnosis": {"recommended_source": "app.py:other"},
        "promote": True,
        "plugin_config": {"minimum_confirmed_cases": 3},
    })

    assert result["status"] == "blocked"
    assert result["reason"] == "no_structural_discriminator"


def test_admission_does_not_reuse_contrast_from_another_failure_class(tmp_path):
    root = _root(tmp_path)
    for project in ("alpha", "beta", "gamma"):
        _stage(root, project)
    holdout = root / "holdout"
    holdout.mkdir()

    result = admission.run({
        "root": root,
        "project_dir": holdout,
        "failure_packet": {
            "selected_candidate": "app.py:parse_args",
            "downstream_evidence": {"acceptance_signal": "meta_only"},
        },
        "diagnosis": {
            "failure_class": "executable_sample_contract",
            "recommended_source": "app.py:build_value",
        },
        "promote": True,
        "plugin_config": {"minimum_confirmed_cases": 3},
    })

    assert result["status"] == "blocked"
    assert result["reason"] == "confirmed_cases_required"


def test_admission_requires_regression_projects_when_configured(monkeypatch, tmp_path):
    root = _root(tmp_path)
    record = _record()
    for project in ("alpha", "beta", "gamma"):
        _stage(root, project, record)
    holdout = root / "holdout"
    holdout.mkdir()
    monkeypatch.setattr(
        admission, "_holdout_effect",
            lambda *_args: {
                "status": "confirmed_selection_effect", "score_delta": 0.8,
                "role_regressions": [], "control": {"selected_candidate_quality": {
                    "structural_evidence": {"return_paths": 0, "output_inference_basis": "no_value_return"}}},
                "treatment": {"selected_candidate_quality": {"structural_evidence": {"return_paths": 1}}},
            },
    )

    result = admission.run({
        "root": root, "project_dir": holdout,
        "failure_packet": {"selected_candidate": "app.py:meta", "downstream_evidence": {}},
        "diagnosis": {"recommended_source": "app.py:other"},
        "promote": True, "requires_regression_cases": True,
        "regression_projects": [], "plugin_config": {"minimum_confirmed_cases": 3},
    })

    assert result == {"status": "blocked", "reason": "regression_projects_required"}


def test_admission_reports_transactional_regression_rejection(monkeypatch, tmp_path):
    root = _root(tmp_path)
    for project in ("alpha", "beta", "gamma"):
        _stage(root, project)
    holdout = root / "holdout"
    holdout.mkdir()
    monkeypatch.setattr(
        admission, "_promote_with_regression_gate",
        lambda *_args: {
            "applied": False, "status": "rejected", "reason": "regression_gate_failed",
        },
    )

    result = admission.run({
        "root": root, "project_dir": holdout,
        "failure_packet": {"selected_candidate": "app.py:write_only", "downstream_evidence": {}},
        "diagnosis": {
            "recommended_source": "app.py:build_value",
            "measured_selection_effect": _effect(),
        },
        "promote": True, "requires_regression_cases": True,
        "regression_projects": [root / "stable"],
        "plugin_config": {"minimum_confirmed_cases": 3},
    })

    assert result["status"] == "blocked"
    assert result["reason"] == "regression_gate_failed"


def test_admission_learns_side_effect_free_selection_without_relaxing_execution_gate(
    monkeypatch, tmp_path
):
    root = _root(tmp_path)
    record = _record(failed_returns=0, successful_returns=0, failed_effects=["memory_state"])
    for project in ("alpha", "beta", "gamma"):
        _stage(root, project, record)
    holdout = root / "holdout"
    holdout.mkdir()
    effect = _effect()
    effect["treatment"]["selected_candidate_quality"]["structural_evidence"].update({
        "return_paths": 0,
        "output_inference_basis": "no_value_return",
        "observed_side_effects": [],
    })
    effect["control"]["selected_candidate_quality"]["structural_evidence"]["observed_side_effects"] = ["memory_state"]
    monkeypatch.setattr(admission, "_holdout_effect", lambda *_args: effect)
    monkeypatch.setattr(admission, "_holdout_reproduction_failure", lambda *_args: {})

    result = admission.run({
        "root": root,
        "project_dir": holdout,
        "failure_packet": {
            "selected_candidate": "app.py:write_only",
            "downstream_evidence": {"acceptance_signal": ""},
        },
        "diagnosis": {"recommended_source": "app.py:build_value"},
        "promote": True,
        "plugin_config": {"minimum_confirmed_cases": 3},
    })

    assert result["status"] == "promoted"
    policy = load_selection_policies(
        str(root / "knowledge" / "role_knowledge" / "promoted_candidate_selection_policies.json")
    )["policies"][0]
    assert policy["structural_requirements"] == {"no_observed_side_effects": True}


def test_policy_synthesis_keeps_only_persistent_removed_effects():
    records = []
    for failed_effects, successful_effects in (
        (["memory_state"], []),
        (["memory_state", "observability"], ["observability"]),
        (["filesystem_read", "memory_state"], ["observability"]),
    ):
        record = _record(failed_returns=0, successful_returns=0, failed_effects=failed_effects)
        record["successful_contract"]["observed_side_effects"] = successful_effects
        records.append(record)

    policy = admission._synthesize_policy({"id": "contrast", "records": records})

    assert policy["structural_requirements"] == {
        "forbidden_observed_side_effects": ["memory_state"],
    }
    assert policy["preflight_trigger_requirements"]["required_observed_side_effects"] == [
        "memory_state",
    ]


def test_architect_reselection_passes_structure_to_policy_hook(monkeypatch):
    context = {
        "app.py:write": {
            "snippet": {
                "structural_contract": {
                    "return_paths": 0,
                    "output_inference_basis": "no_value_return",
                    "typed_argument_count": 0,
                    "observed_side_effects": ["memory_state"],
                }
            }
        },
        "app.py:build": {
            "snippet": {
                "structural_contract": {
                    "return_paths": 1,
                    "output_inference_basis": "return_expression",
                    "typed_argument_count": 1,
                    "observed_side_effects": [],
                }
            }
        },
    }
    monkeypatch.setattr(
        reselection,
        "first_slice_viability",
        lambda *_args, **_kwargs: {"status": "eligible", "reselection_required": False, "score": 80},
    )
    monkeypatch.setattr(
        reselection,
        "contract_quality",
        lambda *_args, **_kwargs: {"semantic_score": 95, "contract_shape_score": 90},
    )
    captured = {}

    def apply(rows, request):
        captured["rows"] = rows
        captured["request"] = request
        return sorted(rows, key=lambda row: row["target"] != "app.py:build")

    monkeypatch.setattr(reselection, "apply_selection_policies", apply)
    request = {
        "trigger": "executable_acceptance_rejected",
        "blocking_evidence": {"acceptance_signal": "meta_only"},
    }

    selected, _ranked = reselection._viable_candidates(
        ["app.py:write", "app.py:build"],
        context,
        {"first_slice_contract": {}},
        limit=2,
        selection_request=request,
    )

    assert selected == ["app.py:build", "app.py:write"]
    build = next(row for row in captured["rows"] if row["target"] == "app.py:build")
    assert build["return_paths"] == 1
    assert build["typed_argument_count"] == 1
    assert build["observed_side_effects"] == []
    assert captured["request"] == request
