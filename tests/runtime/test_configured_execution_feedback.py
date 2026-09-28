from runtime import configured_execution_feedback as feedback


def _artifacts(target):
    return {
        "adr": {
            "artifact_type": "ArchitectureDecisionRecord",
            "first_slice_reselection_history": [],
        },
        "spec": {
            "artifact_type": "TechnicalSpec",
            "extraction_contract": {"candidate": target},
        },
    }


def _executor(target, callable_count=0):
    return {
        "executable_acceptance": "passed",
        "acceptance_signal": "executable_callable" if callable_count else "meta_only",
        "callable_harness_count": callable_count,
        "acceptance_skipped_reasons": {} if callable_count else {"positive_sample_execution_failed": 1},
        "acceptance_skipped_targets": [] if callable_count else [{
            "target": target,
            "reason": "positive_sample_execution_failed",
        }],
    }


def test_configured_feedback_reruns_architect_selection_until_callable(monkeypatch):
    selected = "module.py:simple"
    monkeypatch.setattr(feedback, "feedback_iteration_limit", lambda: 1)
    monkeypatch.setattr(feedback, "reselect_architecture_first_slice", lambda **kwargs: {
        "status": "selected",
        "architecture_decision": {**kwargs["architecture_decision"], "source_context": {}},
        "outcome": {
            "iteration": 1,
            "selected_targets": [selected],
            "selection_policy_ids": ["fixture-ready"],
        },
    })

    artifacts, executor, result = feedback.close_configured_execution_feedback(
        artifacts=_artifacts("module.py:complex"),
        executor=_executor("module.py:complex"),
        project_report={},
        rerun=lambda _adr: (_artifacts(selected), _executor(selected, callable_count=1)),
    )

    assert artifacts["spec"]["extraction_contract"]["candidate"] == selected
    assert executor["callable_harness_count"] == 1
    assert result["status"] == "resolved"
    assert result["history"][0]["rejected_target"] == "module.py:complex"
    assert result["history"][0]["selected_targets"] == [selected]


def test_configured_feedback_stops_when_architect_exhausts_candidates(monkeypatch):
    monkeypatch.setattr(feedback, "feedback_iteration_limit", lambda: 2)
    monkeypatch.setattr(feedback, "reselect_architecture_first_slice", lambda **_kwargs: {
        "status": "exhausted",
        "architecture_decision": {},
        "outcome": {"selected_targets": []},
    })

    artifacts, executor, result = feedback.close_configured_execution_feedback(
        artifacts=_artifacts("module.py:complex"),
        executor=_executor("module.py:complex"),
        project_report={},
        rerun=lambda _adr: (_artifacts("never"), _executor("never", callable_count=1)),
    )

    assert artifacts["spec"]["extraction_contract"]["candidate"] == "module.py:complex"
    assert executor["callable_harness_count"] == 0
    assert result["status"] == "exhausted"
