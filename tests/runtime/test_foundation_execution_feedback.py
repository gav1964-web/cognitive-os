from runtime import foundation_execution_feedback as feedback


def _result(target):
    return {
        "status": "ok",
        "artifact_contents": {
            "project_map_report": {
                "artifact_type": "ProjectMapReport",
                "content": {"summary": {"root": "/project"}},
            },
            "architecture_decision": {
                "artifact_type": "ArchitectureDecisionRecord",
                "first_slice_contract": {"targets": [target]},
            },
            "technical_spec": {
                "artifact_type": "TechnicalSpec",
                "extraction_contract": {"candidate": target},
            },
        },
    }


def _evidence(signal, count=0):
    return {
        "status": "passed",
        "summary": {
            "signal_strength": signal,
            "callable_harness_count": count,
            "skipped_targets": [{
                "target": "pkg/core.py:first",
                "reason": "positive_sample_execution_failed",
            }] if not count else [],
        },
    }


def test_foundation_feedback_rebuilds_roles_and_retests(monkeypatch, tmp_path):
    evidence = iter([_evidence("meta_only"), _evidence("executable_callable", 1)])
    monkeypatch.setattr(feedback, "collect_foundation_executable_evidence", lambda **kwargs: next(evidence))
    monkeypatch.setattr(feedback, "feedback_iteration_limit", lambda: 2)
    monkeypatch.setattr(feedback, "reselect_architecture_first_slice", lambda **kwargs: {
        "status": "selected",
        "architecture_decision": kwargs["architecture_decision"],
        "outcome": {"selected_targets": ["pkg/core.py:second"]},
    })
    targets = []

    def rerun(target):
        targets.append(target)
        return _result(target)

    result, final_evidence = feedback.run_foundation_execution_feedback(
        root=tmp_path,
        project_dir=tmp_path,
        initial_result=_result("pkg/core.py:first"),
        rerun=rerun,
    )

    assert targets == ["pkg/core.py:second"]
    assert final_evidence["summary"]["signal_strength"] == "executable_callable"
    assert result["execution_reselection_status"] == "resolved"
    assert result["execution_reselection_history"][0]["rejected_target"] == "pkg/core.py:first"


def test_foundation_feedback_stops_at_configured_limit(monkeypatch, tmp_path):
    monkeypatch.setattr(
        feedback, "collect_foundation_executable_evidence", lambda **kwargs: _evidence("meta_only")
    )
    monkeypatch.setattr(feedback, "feedback_iteration_limit", lambda: 1)
    monkeypatch.setattr(feedback, "reselect_architecture_first_slice", lambda **kwargs: {
        "status": "selected",
        "architecture_decision": kwargs["architecture_decision"],
        "outcome": {"selected_targets": ["pkg/core.py:second"]},
    })

    result, _ = feedback.run_foundation_execution_feedback(
        root=tmp_path,
        project_dir=tmp_path,
        initial_result=_result("pkg/core.py:first"),
        rerun=lambda target: _result(target),
    )

    assert result["execution_reselection_status"] == "iteration_limit"
    assert len(result["execution_reselection_history"]) == 1


def test_foundation_feedback_returns_safe_eligibility_rejection_to_architect(
    monkeypatch, tmp_path
):
    evidence = iter([
        _evidence("meta_only"),
        {"status": "skipped", "reason": "side_effectful_target", "target": "pkg/core.py:second"},
        _evidence("executable_callable", 1),
    ])
    monkeypatch.setattr(feedback, "collect_foundation_executable_evidence", lambda **kwargs: next(evidence))
    monkeypatch.setattr(feedback, "feedback_iteration_limit", lambda: 4)
    selected = iter(["pkg/core.py:second", "pkg/core.py:third"])
    monkeypatch.setattr(feedback, "reselect_architecture_first_slice", lambda **kwargs: {
        "status": "selected",
        "architecture_decision": kwargs["architecture_decision"],
        "outcome": {"selected_targets": [next(selected)]},
    })

    result, _ = feedback.run_foundation_execution_feedback(
        root=tmp_path,
        project_dir=tmp_path,
        initial_result=_result("pkg/core.py:first"),
        rerun=_result,
    )

    assert result["execution_reselection_status"] == "resolved"
    assert [row["rejected_target"] for row in result["execution_reselection_history"]] == [
        "pkg/core.py:first", "pkg/core.py:second",
    ]


def test_foundation_feedback_keeps_best_safe_handoff_when_later_candidate_regresses(
    monkeypatch, tmp_path
):
    evidence = iter([
        _evidence("meta_only"),
        {"status": "skipped", "reason": "side_effectful_target", "target": "pkg/core.py:second"},
        {"status": "skipped", "reason": "first_slice_reselection_required", "target": "pkg/core.py:third"},
    ])
    monkeypatch.setattr(feedback, "collect_foundation_executable_evidence", lambda **kwargs: next(evidence))
    monkeypatch.setattr(feedback, "feedback_iteration_limit", lambda: 2)
    selected = iter(["pkg/core.py:second", "pkg/core.py:third"])
    monkeypatch.setattr(feedback, "reselect_architecture_first_slice", lambda **kwargs: {
        "status": "selected",
        "architecture_decision": kwargs["architecture_decision"],
        "outcome": {"selected_targets": [next(selected)]},
    })

    result, final_evidence = feedback.run_foundation_execution_feedback(
        root=tmp_path, project_dir=tmp_path,
        initial_result=_result("pkg/core.py:first"), rerun=_result,
    )

    assert result["artifact_contents"]["technical_spec"]["extraction_contract"]["candidate"] == "pkg/core.py:second"
    assert final_evidence["reason"] == "side_effectful_target"
