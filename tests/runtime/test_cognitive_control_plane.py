from __future__ import annotations

from runtime.cognitive_control_plane import run_cognitive_control_plane, run_prompt_product_control_plane
from runtime.semantic_reasoner import build_semantic_hypothesis_request


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


def test_prompt_product_control_plane_routes_ready_prompt_to_build():
    gate = {
        "artifact_type": "PromptAdequacyGate",
        "status": "ready",
        "system_type": "cli",
        "reason_code": "ready",
    }

    result = run_prompt_product_control_plane(
        prompt="build bounded CLI",
        prompt_adequacy=gate,
        supported_template="json_log_filter_cli",
    )

    assert result["mode"] == "prompt_to_product"
    assert result["prompt_product_gate"]["status"] == "passed"
    assert result["role_transition"]["next_action"] == "build_verified_system_package"
    assert result["semantic_escalation"]["l4_5_required"] is False
    assert result["crystallization_backlog"]


def test_prompt_product_control_plane_blocks_unclear_prompt_without_build():
    gate = {
        "artifact_type": "PromptAdequacyGate",
        "status": "needs_clarification",
        "system_type": None,
        "reason_code": "missing_inputs_outputs",
    }

    result = run_prompt_product_control_plane(
        prompt="сделай что-нибудь",
        prompt_adequacy=gate,
        supported_template=None,
    )

    assert result["prompt_product_gate"]["status"] == "blocked"
    assert result["role_transition"]["next_action"] == "ask_clarification"
    assert result["semantic_escalation"]["l4_5_required"] is False


def test_prompt_product_control_plane_requests_l45_for_ready_unknown_template():
    gate = {
        "artifact_type": "PromptAdequacyGate",
        "status": "ready",
        "system_type": "cli",
        "reason_code": "PROMPT_ADEQUATE",
    }

    decision = run_prompt_product_control_plane(
        prompt="build bounded CLI with an unsupported domain template",
        prompt_adequacy=gate,
        supported_template=None,
    )
    request = build_semantic_hypothesis_request(control_plane_decision=decision)

    assert decision["artifact_promotion_gate"]["status"] == "not_applicable"
    assert decision["semantic_escalation"]["l4_5_required"] is True
    assert "no_supported_package_template" in decision["semantic_escalation"]["reasons"]
    assert request is not None
    assert request["artifact_type"] == "SemanticHypothesisRequest"
    assert request["layer"] == "L4.5"
    assert "build_package" in request["forbidden_actions"]
    assert request["return_path"]["target_layer"] == "L4.0"
