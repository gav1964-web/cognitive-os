from __future__ import annotations

from runtime.cognitive_control_plane import run_cognitive_control_plane


def _artifacts() -> dict[str, dict]:
    return {
        "architecture_decision": {"artifact_type": "ArchitectureDecisionRecord", "architect_advisory": {"source": "deterministic"}},
        "technical_spec": {"artifact_type": "TechnicalSpec"},
        "implementation_plan": {"artifact_type": "ImplementationPlan"},
        "test_plan": {"artifact_type": "TestPlan"},
        "review_findings": {"artifact_type": "ReviewFindings"},
    }


def test_control_plane_decides_known_role_transition_without_l45():
    result = run_cognitive_control_plane(
        goal="Extract first safe capability",
        artifacts=_artifacts(),
        review={"artifact_type": "ReviewFindings", "recommendation": "approve", "conformance_status": "passed"},
    )

    assert result["artifact_type"] == "CognitiveControlPlaneDecision"
    assert result["layer"] == "L4.0"
    assert result["artifact_promotion_gate"]["status"] == "passed"
    assert result["role_transition"]["next_action"] == "run_project_transform"
    assert result["semantic_escalation"]["l4_5_required"] is False
    assert result["crystallization_backlog"]


def test_control_plane_escalates_when_contracts_pass_but_semantic_rework_requested():
    result = run_cognitive_control_plane(
        goal="Assess unclear architecture",
        artifacts=_artifacts(),
        review={"artifact_type": "ReviewFindings", "recommendation": "request_rework", "conformance_status": "passed"},
    )

    assert result["role_transition"]["next_action"] == "rework_role_artifacts"
    assert result["semantic_escalation"]["l4_5_required"] is True
    assert "semantic_rework_after_contracts_passed" in result["semantic_escalation"]["reasons"]


def test_control_plane_escalates_on_architect_fallback():
    artifacts = _artifacts()
    artifacts["architecture_decision"]["architect_advisory"] = {"source": "deterministic_fallback"}

    result = run_cognitive_control_plane(
        goal="Extract first safe capability",
        artifacts=artifacts,
        review={"artifact_type": "ReviewFindings", "recommendation": "approve", "conformance_status": "passed"},
    )

    assert result["semantic_escalation"]["l4_5_required"] is True
    assert "architect_advisory_backend_failed" in result["semantic_escalation"]["reasons"]
