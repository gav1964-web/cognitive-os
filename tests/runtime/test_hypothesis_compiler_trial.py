import json

from runtime.hypothesis_compiler_trial import run_compiled_hypothesis_trials
from runtime.hypothesis_compiler_repository_gate import (
    PROMOTION_PATHS, capture_selection_state, rollback_selection_state,
)


def _report(root, project, *, delta=2.0, selected="app.py:weak", trained="app.py:better"):
    project_dir = root / "projects" / project
    project_dir.mkdir(parents=True, exist_ok=True)
    return {
        "project": project,
        "project_dir": project_dir.as_posix(),
        "baseline": {
            "project_min_score": 7.5,
            "selected_extraction_candidate": selected,
            "selected_candidate_quality": {"structural_evidence": {
                "observed_side_effects": [], "output_inference_basis": "return_expression",
            }},
            "downstream_evidence": {"acceptance_signal": "meta_only"},
        },
        "trained_attempt": {
            "project_min_score": 7.5 + delta,
            "selected_extraction_candidate": trained,
        },
        "diagnosis": {"failure_class": "executable_sample_contract"},
        "outcome": {
            "status": "candidate_improvement_confirmed",
            "score_delta": delta,
            "role_regressions": [],
        },
    }


def _stage(root, reports):
    directory = root / "artifacts" / "self_improvement"
    directory.mkdir(parents=True)
    for index, report in enumerate(reports):
        (directory / f"self_improvement_20260101T00000{index}Z.json").write_text(
            json.dumps(report), encoding="utf-8",
        )


def _compilation(root, evidence, controls):
    path = root / "compilation.json"
    path.write_text(json.dumps({"hypotheses": [{
        "artifact_type": "HypothesisCandidate",
        "hypothesis_id": "hc_trial",
        "candidate_type": "candidate_selection_rule",
        "portable_signature": "meta_only|pure|return_expression",
        "semantic_context": [],
        "evidence_refs": evidence,
        "counterexample_refs": controls,
    }]}), encoding="utf-8")
    return path


def test_trial_runner_preflights_then_promotes_with_existing_controls(tmp_path):
    positive = _report(tmp_path, "positive")
    control = _report(tmp_path, "control", delta=0.0, trained="app.py:weak")
    _stage(tmp_path, [positive, control])
    calls = []

    def admit(context):
        calls.append(context)
        return (
            {"status": "promoted", "policy_id": "policy"}
            if context["promote"] else {"status": "trial_passed", "policy_id": "policy"}
        )

    result = run_compiled_hypothesis_trials(
        root=tmp_path,
        compilation_path=_compilation(tmp_path, ["positive"], ["control"]),
        promote=True, admission=admit, write=False,
    )

    assert result["summary"]["promotion_count"] == 1
    assert result["trials"][0]["status"] == "promoted"
    assert [call["promote"] for call in calls] == [False, True]
    assert calls[1]["regression_projects"] == [tmp_path / "projects" / "control"]
    assert calls[1]["diagnosis"]["measured_selection_effect"]["score_delta"] == 2.0


def test_trial_runner_does_not_promote_rejected_preflight(tmp_path):
    positive = _report(tmp_path, "positive")
    _stage(tmp_path, [positive])
    calls = []

    def reject(context):
        calls.append(context)
        return {"status": "blocked", "reason": "no_structural_discriminator"}

    result = run_compiled_hypothesis_trials(
        root=tmp_path,
        compilation_path=_compilation(tmp_path, ["positive"], []),
        promote=True, admission=reject, write=False,
    )

    assert result["trials"][0]["status"] == "preflight_rejected"
    assert result["trials"][0]["reason"] == "no_structural_discriminator"
    assert len(calls) == 1
    assert calls[0]["promote"] is False


def test_trial_runner_reports_missing_measured_reselection(tmp_path):
    unchanged = _report(tmp_path, "unchanged", delta=0.0, trained="app.py:weak")
    _stage(tmp_path, [unchanged])

    result = run_compiled_hypothesis_trials(
        root=tmp_path,
        compilation_path=_compilation(tmp_path, ["unchanged"], []),
        admission=lambda _context: (_ for _ in ()).throw(AssertionError("must not run")),
        write=False,
    )

    assert result["trials"][0]["status"] == "blocked"
    assert result["trials"][0]["reason"] == "measured_holdout_missing"


def test_trial_runner_retries_timeout_with_bounded_larger_budget(tmp_path):
    positive = _report(tmp_path, "positive")
    control = _report(tmp_path, "control", delta=0.0, trained="app.py:weak")
    _stage(tmp_path, [positive, control])
    calls = []

    def admit(context):
        calls.append(context)
        if not context["promote"]:
            return {"status": "trial_passed", "policy_id": "policy"}
        timeout = context["plugin_config"]["regression_case_timeout_seconds"]
        return (
            {"status": "promoted", "policy_id": "policy"}
            if timeout == 60 else {"status": "blocked", "reason": "regression_case_timeout"}
        )

    result = run_compiled_hypothesis_trials(
        root=tmp_path,
        compilation_path=_compilation(tmp_path, ["positive"], ["control"]),
        promote=True, admission=admit, write=False,
        case_timeout_seconds=30, total_timeout_seconds=100,
        timeout_retry_multipliers=(2.0,),
    )

    assert result["trials"][0]["status"] == "promoted"
    assert [call["plugin_config"]["regression_case_timeout_seconds"] for call in calls] == [30, 30, 60]
    assert result["trials"][0]["admission_attempts"][-1]["total_timeout_seconds"] == 200


def test_plugin_contract_is_resolved_without_runtime_generation(tmp_path):
    path = tmp_path / "compilation.json"
    path.write_text(json.dumps({"hypotheses": [{
        "artifact_type": "HypothesisCandidate",
        "hypothesis_id": "hc_plugin",
        "candidate_type": "improvement_plugin_contract",
        "failure_class": "unknown_failure",
        "portable_signature": "unknown|pure|unknown",
        "semantic_context": [],
        "evidence_refs": ["one", "two", "three"],
        "counterexample_refs": [],
        "required_plugin_contract": {"capability": "new_bounded_improvement_plugin"},
    }]}), encoding="utf-8")

    result = run_compiled_hypothesis_trials(
        root=tmp_path, compilation_path=path, write=False,
        hypothesis_ids={"hc_plugin"},
    )

    assert result["summary"]["statuses"] == {"implementation_required": 1}
    assert result["trials"][0]["reason"] == "bounded_improvement_plugin_missing"
    assert "plugin_id" not in result["trials"][0]["foundry_resolution"]


def test_semantic_profile_requires_independent_matching_holdout(tmp_path):
    report = _report(tmp_path, "known", selected="app.py:render")
    report["diagnosis"]["failure_class"] = "side_effectful_target"
    report["baseline"]["downstream_evidence"] = {"acceptance_signal": "side_effectful_target"}
    _stage(tmp_path, [report])
    path = tmp_path / "compilation.json"
    path.write_text(json.dumps({"hypotheses": [{
        "artifact_type": "HypothesisCandidate",
        "hypothesis_id": "hc_profile",
        "candidate_type": "semantic_contract_profile",
        "failure_class": "side_effectful_target",
        "portable_signature": "side_effectful_target|pure|return_expression",
        "semantic_context": [],
        "evidence_refs": ["known"],
        "counterexample_refs": [],
        "required_plugin_contract": {"capability": "semantic_contract_profile_synthesis"},
    }]}), encoding="utf-8")

    result = run_compiled_hypothesis_trials(
        root=tmp_path, compilation_path=path, write=False,
        candidate_types={"semantic_contract_profile"},
    )

    assert result["trials"][0]["status"] == "evidence_required"
    assert result["trials"][0]["reason"] == "independent_matching_holdout_missing"
    assert result["trials"][0]["foundry_resolution"]["plugin_id"] == "semantic_profile_admission"


def test_repository_regression_failure_rolls_back_promotion(tmp_path):
    positive = _report(tmp_path, "positive")
    control = _report(tmp_path, "control", delta=0.0, trained="app.py:weak")
    _stage(tmp_path, [positive, control])

    result = run_compiled_hypothesis_trials(
        root=tmp_path,
        compilation_path=_compilation(tmp_path, ["positive"], ["control"]),
        promote=True, write=False,
        admission=lambda context: (
            {"status": "promoted", "promotion_applied": True}
            if context["promote"] else {"status": "trial_passed"}
        ),
        repository_verifier=lambda _root: {
            "status": "blocked", "reason": "repository_regression_gate_failed",
        },
    )

    trial = result["trials"][0]
    assert result["summary"]["promotion_count"] == 0
    assert trial["status"] == "blocked"
    assert trial["rollback_applied"] is True
    assert trial["admission"]["promotion_applied"] is False


def test_repository_snapshot_restores_all_promotion_kb_files(tmp_path):
    expected = {}
    for index, relative in enumerate(PROMOTION_PATHS):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        content = f"before-{index}".encode()
        path.write_bytes(content)
        expected[path] = content
    snapshot = capture_selection_state(tmp_path)
    for path in expected:
        path.write_text("after", encoding="utf-8")

    rollback_selection_state(tmp_path, snapshot)

    assert {path: path.read_bytes() for path in expected} == expected


def test_trial_report_keeps_versioned_history_and_latest_pointer(tmp_path):
    compilation = tmp_path / "compilation.json"
    compilation.write_text('{"hypotheses": []}', encoding="utf-8")

    first = run_compiled_hypothesis_trials(root=tmp_path, compilation_path=compilation)
    second = run_compiled_hypothesis_trials(root=tmp_path, compilation_path=compilation)

    directory = tmp_path / "artifacts" / "hypothesis_compiler"
    assert (directory / "compiled_hypothesis_trials.json").is_file()
    assert first["report_path"] != second["report_path"]
    assert len(list(directory.glob("compiled_hypothesis_trials_*.json"))) == 2


def test_quarantined_policy_requires_explicit_retry(tmp_path):
    positive = _report(tmp_path, "positive")
    _stage(tmp_path, [positive])
    policy_path = tmp_path / "knowledge" / "role_knowledge" / "promoted_candidate_selection_policies.json"
    policy_path.parent.mkdir(parents=True)
    policy_path.write_text(json.dumps({"policies": [{
        "id": "unsafe-policy", "activation_state": "quarantined",
    }]}), encoding="utf-8")
    calls = []

    result = run_compiled_hypothesis_trials(
        root=tmp_path,
        compilation_path=_compilation(tmp_path, ["positive"], []),
        promote=True, write=False,
        admission=lambda context: calls.append(context) or {
            "status": "trial_passed", "policy_id": "unsafe-policy",
        },
    )

    assert result["trials"][0]["status"] == "quarantined"
    assert result["trials"][0]["reason"] == "prior_repository_regression"
    assert len(calls) == 1
