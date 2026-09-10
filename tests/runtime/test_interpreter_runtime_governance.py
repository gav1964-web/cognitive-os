from copy import deepcopy
from pathlib import Path

from runtime.configured_role_pipeline import _bind_pipeline_authority
from runtime.interpreter_authority import verify_interpreter_decision
from runtime.interpreter_coverage_audit import (
    load_interpreter_coverage_policy,
    run_interpreter_coverage_audit,
)
from runtime.interpreter_runtime_governance import build_verified_runtime_transition, evidence_record
from runtime.project_development_handoff import _role_chain_handoff
from runtime.role_pipeline_stages import stage_after_decision


def test_configured_pipeline_binds_a_verified_trace_chain() -> None:
    pipeline = {"steps": [
        {"step_id": "architecture", "role_id": "architect", "output_key": "adr"},
        {"step_id": "specification", "role_id": "spec_writer", "output_key": "spec"},
        {"step_id": "implementation", "role_id": "implementer", "output_key": "plan"},
    ]}
    artifacts = {
        "adr": {"artifact_type": "ArchitectureDecisionRecord"},
        "spec": {"artifact_type": "TechnicalSpec"},
        "plan": {"artifact_type": "ImplementationPlan"},
    }
    report = {"summary": {"root": "demo", "entrypoints": ["src/demo.py"]}}

    _bind_pipeline_authority(
        artifacts=artifacts, pipeline=pipeline, goal="Improve demo",
        project_report=report, prior_trace=None, target=None, scope=None,
    )

    traces = [artifacts[key]["interpreter_decision_trace"] for key in ("adr", "spec", "plan")]
    assert [trace["next_stage"] for trace in traces] == [
        "architecture", "specification", "implementation",
    ]
    assert all(verify_interpreter_decision(trace)["status"] == "verified" for trace in traces)
    assert traces[1]["prior_trace_digest"] == traces[0]["trace_digest"]
    assert traces[2]["prior_trace_digest"] == traces[1]["trace_digest"]


def test_runtime_transition_rejects_a_tampered_prior_trace() -> None:
    first = build_verified_runtime_transition(
        stage="project_analysis", next_stage="architecture", goal="Improve demo",
        target="src/demo.py", scope=["src/demo.py"],
        evidence=[evidence_record("report", {"status": "ok"}, kind="project_report")],
        rule_id="test_entry",
    )
    tampered = deepcopy(first)
    tampered["target"] = "src/easy.py"

    result = build_verified_runtime_transition(
        stage="architecture", next_stage="specification", goal="Improve demo",
        target="src/demo.py", scope=["src/demo.py"],
        evidence=[evidence_record("adr", {"status": "ok"}, kind="role_artifact")],
        rule_id="test_spec", prior_trace=tampered,
    )

    assert result["status"] == "controlled_stop"
    assert "prior_trace_invalid" in result["violations"]


def test_project_development_research_handoff_is_interpreter_bound() -> None:
    handoff = _role_chain_handoff(
        project_report={"summary": {"root": "demo"}},
        recognition={"status": "ambiguous"},
        decision={"selected_option": {"route": "research"}},
        goal="Understand demo", run_role_chain=False, policy={},
    )

    trace = handoff["interpreter_decision_trace"]
    assert handoff["status"] == "research_required"
    assert trace["next_stage"] == "research"
    assert verify_interpreter_decision(trace)["status"] == "verified"


def test_failure_backed_handoff_stops_without_evidence_bound_contract() -> None:
    handoff = _role_chain_handoff(
        project_report={"summary": {"root": "demo"}},
        recognition={"status": "recognized"},
        decision={
            "selected_option": {"route": "role_chain", "strategy": "repair"},
            "selected_issue": {
                "issue_id": "ISSUE-1",
                "rule_id": "weak_contracts",
                "failure_specific_reducer_required": True,
                "affected_targets": ["pkg/service.py:run"],
                "failure_evidence": [],
            },
        },
        goal="Repair demo",
        run_role_chain=True,
        policy={},
    )

    assert handoff["status"] == "controlled_stop"
    assert handoff["reason"] == "failure_backed_problem_outcome_contract_invalid"


def test_completed_handoff_retains_focused_project_analyzer_artifact(monkeypatch) -> None:
    captured = {}

    def fake_role_prefix(**kwargs):
        captured["project_report"] = kwargs["project_report"]
        contract = kwargs["project_report"]["problem_outcome_contract"]
        return {
            "adr": {"artifact_type": "ArchitectureDecisionRecord", "status": "ok"},
            "spec": {
                "artifact_type": "TechnicalSpec",
                "status": "ok",
                "extraction_contract": {"candidate": "pkg/service.py:run"},
            },
            "implementation": {"artifact_type": "ImplementationPlan", "status": "ok"},
            "tests": {"artifact_type": "TestPlan", "status": "ok"},
            "tree": {"artifact_type": "ProgrammerTaskTree", "status": "ready"},
            "review": {
                "artifact_type": "ReviewFindings",
                "status": "ok",
                "recommendation": "approve_with_risks",
                "problem_outcome_contract": contract,
                "problem_outcome_conformance": {"status": "passed"},
            },
        }

    monkeypatch.setattr(
        "runtime.project_development_handoff.run_configured_role_prefix",
        fake_role_prefix,
    )
    handoff = _role_chain_handoff(
        project_report={"summary": {"root": "demo"}, "answers": {}},
        recognition={"status": "recognized"},
        decision={
            "selected_option": {"route": "role_chain", "strategy": "repair"},
            "selected_issue": {
                "issue_id": "ISSUE-1",
                "rule_id": "weak_contracts",
                "affected_targets": ["pkg/service.py:run"],
                "evidence": ["failing_contract_test:pkg/service.py:run"],
                "failure_evidence": [{
                    "target": "pkg/service.py:run",
                    "failure_signature": "sig",
                    "failing_nodeids": ["tests/test_service.py::test_run"],
                    "authority": "failing_contract_test",
                }],
            },
        },
        goal="Repair demo",
        run_role_chain=True,
        policy={},
    )

    assert handoff["_project_report"] is captured["project_report"]
    assert handoff["_project_report"]["problem_outcome_contract"]["status"] == "evidence_bound"


def test_transform_stage_stops_without_accepted_interpreter_authority() -> None:
    state = {"next_action": "controlled_stop"}

    stage_after_decision(state)

    assert state["transform"]["status"] == "controlled_stop"
    assert state["transform"]["source_changes"] is False


def test_real_runtime_boundary_audit_reaches_complete_coverage() -> None:
    root = Path(__file__).resolve().parents[2]

    report = run_interpreter_coverage_audit(
        root=root, policy=load_interpreter_coverage_policy()
    )

    assert report["status"] == "passed"
    assert report["summary"]["transition_producer_count"] == 5
    assert report["summary"]["covered_count"] == 5
    assert report["summary"]["coverage"] == 1.0
