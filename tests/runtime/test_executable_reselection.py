from runtime.executable_reselection import (
    build_execution_reselection_request,
    feedback_iteration_limit,
    record_rejected_target,
)
import runtime.role_pipeline_stages as stages


def _executor(signal="meta_only", count=0, reason="positive_sample_execution_failed", status="passed"):
    return {
        "test_result": {
            "executable_acceptance_result": {
                "status": status,
                "summary": {
                    "signal_strength": signal,
                    "callable_harness_count": count,
                    "skipped_reason_counts": {reason: 1},
                    "skipped_targets": [
                        {"target": "pkg/core.py:parse", "reason": reason, "detail": "bad sample"}
                    ],
                }
            }
        }
    }


def _spec():
    return {"extraction_contract": {"candidate": "pkg/core.py:parse"}}


def test_feedback_budget_remains_bounded():
    assert feedback_iteration_limit() == 4


def test_meta_only_acceptance_returns_target_to_architect():
    request = build_execution_reselection_request(_executor(), _spec())

    assert request["status"] == "required"
    assert request["trigger"] == "executable_acceptance_rejected"
    assert request["current_target"] == "pkg/core.py:parse"
    assert request["next_step"] == "return_to_architect_and_rebuild_spec_plan_test"


def test_callable_acceptance_does_not_request_reselection():
    request = build_execution_reselection_request(
        _executor(signal="executable_callable", count=1), _spec()
    )

    assert request["status"] == "not_required"


def test_failed_callable_acceptance_returns_target_to_architect():
    request = build_execution_reselection_request(
        _executor(signal="executable_callable", count=1, status="failed"), _spec()
    )

    assert request["status"] == "required"
    assert request["blocking_evidence"]["skipped_targets"][-1]["reason"] == "executable_acceptance_failed"


def test_non_actionable_skip_does_not_expand_architect_scope():
    request = build_execution_reselection_request(
        _executor(reason="unsupported_target_format"), _spec()
    )

    assert request["status"] == "not_required"


def test_rejected_target_is_added_to_architect_history():
    request = build_execution_reselection_request(_executor(), _spec())
    revised = record_rejected_target(
        {"artifact_type": "ArchitectureDecisionRecord"}, request, iteration=1
    )

    outcome = revised["first_slice_reselection_history"][0]
    assert outcome["selected_targets"] == ["pkg/core.py:parse"]
    assert outcome["status"] == "rejected_by_executable_acceptance"


def test_stage_rebuilds_previous_roles_after_executor_rejection(monkeypatch, tmp_path):
    def artifacts(target):
        return {
            "architecture_decision": {
                "artifact_type": "ArchitectureDecisionRecord",
                "first_slice_contract": {"targets": [target]},
            },
            "technical_spec": {
                "artifact_type": "TechnicalSpec",
                "extraction_contract": {"candidate": target},
            },
            "implementation_plan": {
                "artifact_type": "ImplementationPlan",
                "implementation_target": {"candidate": target},
            },
            "test_plan": {
                "artifact_type": "TestPlan",
                "test_target": {"candidate": target},
            },
        }

    calls = []
    executors = [
        _executor(),
        _executor(signal="executable_callable", count=1),
    ]

    def run_phase(phase, *, context):
        assert phase == "after_build"
        result = executors[len(calls)]
        calls.append(result)
        return {"executor": result}

    def reselect(**kwargs):
        history = kwargs["architecture_decision"]["first_slice_reselection_history"]
        assert history[-1]["selected_targets"] == ["pkg/core.py:parse"]
        return {
            "status": "selected",
            "architecture_decision": {
                "artifact_type": "ArchitectureDecisionRecord",
                "first_slice_contract": {"targets": ["pkg/core.py:normalize"]},
                "first_slice_reselection_history": history,
            },
            "outcome": {"selected_targets": ["pkg/core.py:normalize"]},
        }

    rebuilt = artifacts("pkg/core.py:normalize")
    monkeypatch.setattr(stages, "run_lifecycle_phase", run_phase)
    monkeypatch.setattr(stages, "reselect_architecture_first_slice", reselect)
    monkeypatch.setattr(stages, "run_configured_role_prefix", lambda **kwargs: rebuilt)
    state = {
        "root": tmp_path,
        "project_dir": tmp_path,
        "goal": "build executable contract",
        "project_report": {},
        "architect_advisory_config": None,
        "run_executor": True,
        "write": False,
    }
    stages._bind_build_artifacts(state, artifacts("pkg/core.py:parse"))

    stages.stage_after_build(state)

    assert len(calls) == 2
    assert state["spec"]["extraction_contract"]["candidate"] == "pkg/core.py:normalize"
    assert state["executor"]["execution_reselection_history"][0]["rejected_target"] == "pkg/core.py:parse"
    assert state["executor"]["execution_reselection_status"] == "resolved"


def test_stage_marks_iteration_limit_when_all_replacements_fail(monkeypatch, tmp_path):
    target = "pkg/core.py:parse"
    artifacts = {
        "architecture_decision": {"artifact_type": "ArchitectureDecisionRecord"},
        "technical_spec": {
            "artifact_type": "TechnicalSpec",
            "extraction_contract": {"candidate": target},
        },
        "implementation_plan": {"artifact_type": "ImplementationPlan"},
        "test_plan": {"artifact_type": "TestPlan"},
    }
    calls = []

    def run_phase(phase, *, context):
        calls.append(phase)
        return {"executor": _executor()}

    def reselect(**kwargs):
        return {
            "status": "selected",
            "architecture_decision": kwargs["architecture_decision"],
            "outcome": {"selected_targets": [target]},
        }

    monkeypatch.setattr(stages, "run_lifecycle_phase", run_phase)
    monkeypatch.setattr(stages, "reselect_architecture_first_slice", reselect)
    monkeypatch.setattr(stages, "run_configured_role_prefix", lambda **kwargs: artifacts)
    state = {
        "root": tmp_path,
        "project_dir": tmp_path,
        "goal": "bounded failure",
        "project_report": {},
        "architect_advisory_config": None,
        "run_executor": True,
        "write": False,
    }
    stages._bind_build_artifacts(state, artifacts)

    stages.stage_after_build(state)

    assert len(calls) == stages.feedback_iteration_limit() + 1
    assert state["executor"]["execution_reselection_status"] == "iteration_limit"
    assert state["executor"]["status"] == "needs_review"
    assert state["test_result"]["status"] == "failed"
