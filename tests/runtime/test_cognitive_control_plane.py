from __future__ import annotations

from unittest.mock import patch

from runtime.cognitive_control_plane import run_cognitive_control_plane, run_prompt_product_control_plane
from runtime.l4_semantic_validation import validate_l45_semantic_proposal
from runtime.local_inference import LocalInferenceConfig
from runtime.semantic_evidence_pack import build_semantic_evidence_pack
from runtime.semantic_reasoner import (
    build_developer_improvement_request,
    build_semantic_hypothesis_request,
    build_successful_resolution_candidate,
    run_semantic_reasoner,
    validate_semantic_hypothesis_proposal,
)


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


def test_control_plane_ignores_declarative_blocked_if_text():
    artifacts = _artifacts()
    artifacts["implementation_plan"]["executor_handoff"] = {
        "artifact_type": "ExecutorHandoff",
        "blocked_if": ["ImplementationPlan.implementation_target.status == blocked_no_safe_candidate"],
    }

    result = run_cognitive_control_plane(
        goal="Extract first safe capability",
        artifacts=artifacts,
        review={"artifact_type": "ReviewFindings", "recommendation": "approve", "conformance_status": "passed"},
    )

    assert result["semantic_escalation"]["l4_5_required"] is False


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


def test_prompt_product_control_plane_escalates_bounded_intake_uncertainty_to_l45():
    gate = {
        "artifact_type": "PromptAdequacyGate",
        "status": "needs_clarification",
        "system_type": "cli",
        "reason_code": "PROMPT_ADEQUACY_MISSING_REQUIRED_FIELDS",
        "goal_spec": {"intent": "implementation"},
        "boundary_classification": {"boundary": "incomplete_bounded_prompt"},
    }

    decision = run_prompt_product_control_plane(
        prompt="напиши CLI .py, которая перечислит содержимое картинки",
        prompt_adequacy=gate,
        supported_template=None,
    )

    assert decision["role_transition"]["next_action"] == "ask_clarification"
    assert decision["semantic_escalation"]["l4_5_required"] is True
    assert "prompt_intake_uncertainty" in decision["semantic_escalation"]["reasons"]


def test_l45_maps_intake_uncertainty_to_existing_image_contents_route():
    prompt = "напиши CLI .py, которая перечислит содержимое картинки"
    gate = {
        "artifact_type": "PromptAdequacyGate",
        "status": "needs_clarification",
        "system_type": "cli",
        "reason_code": "PROMPT_ADEQUACY_MISSING_REQUIRED_FIELDS",
        "goal_spec": {"intent": "implementation"},
        "boundary_classification": {"boundary": "incomplete_bounded_prompt"},
    }
    decision = run_prompt_product_control_plane(prompt=prompt, prompt_adequacy=gate, supported_template=None)
    pack = build_semantic_evidence_pack(
        control_plane_decision=decision,
        prompt=prompt,
        prompt_adequacy=gate,
        known_templates=["image_contents_cli"],
    )
    request = build_semantic_hypothesis_request(
        control_plane_decision=decision,
        context={"prompt": prompt, "evidence_pack": pack},
    )

    assert request is not None
    proposal = run_semantic_reasoner(request=request)
    validation = validate_l45_semantic_proposal(request=request, proposal=proposal)
    candidate = build_successful_resolution_candidate(proposal)

    assert proposal["hypothesis_type"] == "successful_existing_resolution"
    assert validation["accepted_action"] == "record_successful_resolution_candidate"
    assert candidate is not None
    assert candidate["resolution_id"] == "map_to_existing_image_contents_cli"


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

    proposal = run_semantic_reasoner(request=request)
    validation = validate_l45_semantic_proposal(request=request, proposal=proposal)
    improvement = build_developer_improvement_request(proposal)

    assert proposal["artifact_type"] == "SemanticHypothesisProposal"
    assert proposal["status"] == "ok"
    assert proposal["hypothesis_type"] == "developer_improvement_request"
    assert proposal["return_to_gate"] is True
    assert validation["artifact_type"] == "L4SemanticValidationResult"
    assert validation["status"] == "accepted"
    assert validation["accepted_action"] == "record_developer_improvement_request"
    assert improvement is not None
    assert improvement["artifact_type"] == "DeveloperImprovementRequest"
    assert improvement["requires_developer"] is True


def test_semantic_reasoner_blocks_invalid_or_forbidden_proposal():
    request = {
        "artifact_type": "SemanticHypothesisRequest",
        "layer": "L4.5",
        "allowed_hypothesis_types": ["new_template_candidate"],
        "output_contract": {
            "required_fields": [
                "hypothesis_type",
                "proposal",
                "confidence",
                "evidence_refs",
                "risks",
                "return_to_gate",
            ],
        },
        "forbidden_actions": ["build_package"],
    }
    proposal = {
        "hypothesis_type": "new_template_candidate",
        "proposal": {"actions": ["build_package"]},
        "confidence": 0.7,
        "evidence_refs": [],
        "risks": [],
        "return_to_gate": True,
    }

    validation = validate_semantic_hypothesis_proposal(request=request, proposal=proposal)

    assert validation["status"] == "blocked"
    assert any(item.startswith("forbidden_actions_requested") for item in validation["violations"])


def test_l4_semantic_validation_blocks_l45_proposal_with_forbidden_action():
    request = {
        "artifact_type": "SemanticHypothesisRequest",
        "layer": "L4.5",
        "trigger_reasons": ["no_supported_package_template"],
        "allowed_hypothesis_types": ["new_template_candidate"],
        "output_contract": {
            "required_fields": [
                "hypothesis_type",
                "proposal",
                "confidence",
                "evidence_refs",
                "risks",
                "return_to_gate",
            ],
        },
        "forbidden_actions": ["build_package"],
        "return_path": {"target_layer": "L4.0"},
    }
    proposal = {
        "artifact_type": "SemanticHypothesisProposal",
        "layer": "L4.5",
        "status": "ok",
        "hypothesis_type": "new_template_candidate",
        "proposal": {"template_id": "unsafe", "actions": ["build_package"]},
        "confidence": 0.8,
        "evidence_refs": ["test"],
        "risks": ["unsafe action"],
        "return_to_gate": True,
    }

    validation = validate_l45_semantic_proposal(request=request, proposal=proposal)

    assert validation["status"] == "blocked"
    assert validation["accepted_action"] == "blocked"
    assert "contract_valid" in validation["quality"]["failed_codes"]
    assert validation["forbidden_actions_observed"] == ["build_package"]


def test_semantic_reasoner_can_use_model_backed_proposal():
    request = {
        "artifact_type": "SemanticHypothesisRequest",
        "layer": "L4.5",
        "source_decision": {"mode": "prompt_to_product"},
        "trigger_reasons": ["no_supported_package_template"],
        "allowed_hypothesis_types": ["new_template_candidate"],
        "output_contract": {
            "required_fields": [
                "hypothesis_type",
                "proposal",
                "confidence",
                "evidence_refs",
                "risks",
                "return_to_gate",
            ],
        },
        "forbidden_actions": ["build_package"],
    }
    model_payload = {
        "hypothesis_type": "new_template_candidate",
        "proposal": {
            "template_id": "csv_sort_cli",
            "system_type": "cli",
            "purpose": "Sort CSV rows",
            "acceptance_focus": ["sorts rows"],
            "actions": ["record_backlog_item"],
        },
        "confidence": 0.8,
        "evidence_refs": ["model:evidence"],
        "risks": ["requires review"],
        "return_to_gate": True,
    }

    with patch("runtime.semantic_reasoner.call_json_chat", return_value=model_payload) as mocked:
        proposal = run_semantic_reasoner(
            request=request,
            use_model=True,
            config=LocalInferenceConfig(base_url="http://127.0.0.1:8000/v1", model="GigaChat-Pro"),
        )

    assert mocked.called
    assert proposal["status"] == "ok"
    assert proposal["hypothesis_type"] == "new_template_candidate"
    assert proposal["hardening"]["raw_model_output_used"] is True
    assert proposal["validation"]["status"] == "ok"
