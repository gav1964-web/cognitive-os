import json

from runtime.hypothesis_compiler_trial import run_compiled_hypothesis_trials


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
