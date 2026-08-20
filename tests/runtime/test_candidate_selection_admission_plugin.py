import json

from runtime import architect_first_slice_reselection as reselection
from runtime.improvement_plugins import candidate_selection_admission as admission
from runtime.knowledge_admission import build_kb_candidate, write_kb_candidate
from runtime.promoted_candidate_selection_policies import (
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


def _record(*, failed_returns=0, successful_returns=1):
    return {
        "contrast_id": "side_effectful_target:measured_candidate_reselection",
        "failed_contract": {
            "acceptance_signal": "",
            "return_paths": failed_returns,
            "output_inference_basis": "no_value_return" if failed_returns == 0 else "return_expression",
            "state_mutation": False,
            "typed_argument_count": 0,
        },
        "successful_contract": {
            "acceptance_signal": "executable_callable",
            "return_paths": successful_returns,
            "output_inference_basis": "return_expression",
            "state_mutation": False,
            "typed_argument_count": 0,
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
        "control": {"status": "ok", "project_min_score": 8.8, "role_scores": {"spec_writer": 8.8}},
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


def test_architect_reselection_passes_structure_to_policy_hook(monkeypatch):
    context = {
        "app.py:write": {
            "snippet": {
                "structural_contract": {
                    "return_paths": 0,
                    "output_inference_basis": "no_value_return",
                    "typed_argument_count": 0,
                }
            }
        },
        "app.py:build": {
            "snippet": {
                "structural_contract": {
                    "return_paths": 1,
                    "output_inference_basis": "return_expression",
                    "typed_argument_count": 1,
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
    assert captured["request"] == request
