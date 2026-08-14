from __future__ import annotations
from runtime.cognitive_control_plane import run_prompt_product_control_plane
from runtime.contract_registry import ContractRegistry
from runtime.l4_decision_table import decision_table_catalog, match_prompt_product_rule
from runtime.l45_model_modes import resolve_model_quality_mode
from runtime.l45_semantic_analytics import analyze_l45_semantic_benchmark, build_l45_risk_policy_gap_report
from runtime.l45_semantic_corpus import generate_l45_semantic_cases
from runtime.l45_semantic_benchmark import run_l45_semantic_benchmark
from runtime.l45_semantic_comparison import compare_l45_semantic_reports
from runtime.l45_semantic_eval_suite import run_l45_semantic_evaluation_suite
from runtime.l45_model_failure_analysis import analyze_l45_model_failures
from runtime.l4_semantic_validation import validate_l45_semantic_proposal
from runtime.prompt_boundary_classifier import classify_prompt_boundary
from runtime.prompt_adequacy import evaluate_prompt_adequacy
from runtime.registry import CapabilityRegistry
from runtime.semantic_evidence_pack import build_semantic_evidence_pack
from runtime.semantic_reasoner import (
    build_developer_improvement_request,
    build_semantic_hypothesis_request,
    build_successful_resolution_candidate,
    run_semantic_reasoner,
)
from runtime.semantic_replay import build_semantic_replay_record

def test_l45_model_path_uses_deepseek_default(monkeypatch):
    request = {
        "artifact_type": "SemanticHypothesisRequest",
        "layer": "L4.5",
        "source_decision": {"mode": "prompt_to_product"},
        "trigger_reasons": ["prompt_intake_uncertainty"],
        "allowed_hypothesis_types": ["developer_improvement_request"],
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
        "evidence_context": {"prompt": "добавь вывод в новый формат"},
    }
    captured = {}

    def fake_call_json_chat(_messages, *, config=None):
        captured["config"] = config
        return {
            "hypothesis_type": "developer_improvement_request",
            "proposal": {"request_id": "test", "actions": ["record_developer_improvement_request"]},
            "confidence": 0.7,
            "evidence_refs": ["test"],
            "risks": ["bounded model proposal"],
            "return_to_gate": True,
        }

    monkeypatch.delenv("COGNITIVE_OS_L45_MODEL", raising=False)
    monkeypatch.setattr("runtime.semantic_reasoner.call_json_chat", fake_call_json_chat)

    proposal = run_semantic_reasoner(request=request, use_model=True)

    assert proposal["hardening"]["raw_model_output_used"] is True
    assert captured["config"].model == "deepseek/deepseek-chat"
    assert captured["config"].response_format is False
    assert captured["config"].provider_label == "external_l45_intent_resolver"


def test_contract_registry_knows_l45_loop_artifacts(runtime_workspace):
    root = runtime_workspace
    registry = CapabilityRegistry(root)
    registry.reset_from_plugins()
    contracts = ContractRegistry.from_capability_registry(registry)

    contracts.validate_artifact(
        {
            "artifact_type": "SemanticEvidencePack",
            "layer": "L4.0",
            "status": "ready",
            "prompt_facts": {},
            "control_facts": {},
            "forbidden_actions": [],
            "authority": {},
        }
    )
    contracts.validate_artifact(
        {
            "artifact_type": "SemanticProposalReplay",
            "status": "recorded",
            "request": {},
            "proposal": {},
            "validation": {},
            "model_quality_mode": "deterministic",
            "outcome": {},
            "audit": {},
        }
    )
    contracts.validate_artifact(
        {
            "artifact_type": "L45SemanticBenchmarkReport",
            "status": "ok",
            "model_quality_mode": "deterministic",
            "summary": {},
            "cases": [],
        }
    )
    contracts.validate_artifact(
        {
            "artifact_type": "L45SemanticCorpusAnalyticsReport",
            "status": "ok",
            "source_report": {},
            "summary": {},
            "boundary_counts": {},
            "action_counts": {},
        }
    )
    contracts.validate_artifact(
        {
            "artifact_type": "L45RiskPolicyGapReport",
            "status": "ok",
            "source_report": {},
            "summary": {},
            "gaps": [],
            "policy_recommendations": [],
        }
    )
    contracts.validate_artifact(
        {
            "artifact_type": "L45SemanticComparisonReport",
            "status": "ok",
            "summary": {},
            "cases": [],
            "interpretation": {},
        }
    )
    contracts.validate_artifact(
        {
            "artifact_type": "L45SemanticEvaluationSuiteReport",
            "status": "ok",
            "config": {},
            "summary": {},
            "profiles": [],
        }
    )
    contracts.validate_artifact(
        {
            "artifact_type": "L45ModelFailureAnalysisReport",
            "status": "ok",
            "summary": {},
            "failures": [],
            "recommendations": [],
        }
    )
    contracts.validate_artifact(
        {
            "artifact_type": "PromptBoundaryClassification",
            "status": "ok",
            "boundary": "bounded_supported_class",
            "confidence": 0.9,
            "reasons": [],
            "recommended_action": "route_to_l4_gate",
        }
    )
    contracts.validate_artifact(decision_table_catalog())
