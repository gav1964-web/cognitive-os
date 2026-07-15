"""Runtime contract catalog and enforcement helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .layer_packets import LAYER_ROUTES, validate_packet
from .models import Capability, Pipeline
from .registry import CapabilityRegistry


class ContractRegistryError(ValueError):
    """Raised when a runtime contract is missing or cannot be used."""


ARTIFACT_CONTRACTS: dict[str, dict[str, Any]] = {
    "GoalSpec": {
        "producer": "goal_intake",
        "consumers": ["L4"],
        "required_fields": ["artifact_type", "intent", "inputs", "outputs", "constraints", "success_criteria"],
    },
    "ProjectMapReport": {
        "producer": "project_analyzer",
        "consumers": ["architect"],
        "required_fields": ["artifact_type", "project", "summary"],
    },
    "ArchitectureDecisionRecord": {
        "producer": "architect",
        "consumers": ["spec_writer"],
        "required_fields": ["artifact_type", "architecture_options", "chosen_option", "risks", "spec_writer_brief"],
    },
    "TechnicalSpec": {
        "producer": "spec_writer",
        "consumers": ["implementer", "tester", "reviewer"],
        "required_fields": ["artifact_type", "requirements", "acceptance_criteria", "traceability_table"],
    },
    "ImplementationPlan": {
        "producer": "implementer",
        "consumers": ["programmer_executor", "tester", "reviewer"],
        "required_fields": ["artifact_type", "patch_scope", "expected_files", "verification_commands", "rollback_plan"],
    },
    "TestPlan": {
        "producer": "tester",
        "consumers": ["programmer_executor", "reviewer"],
        "required_fields": ["artifact_type", "acceptance_tests", "executable_acceptance", "negative_tests", "regression_risks"],
    },
    "PatchPackage": {
        "producer": "programmer_executor",
        "consumers": ["tester", "reviewer"],
        "required_fields": ["artifact_type", "expected_files", "patches", "policy"],
    },
    "TestResult": {
        "producer": "programmer_executor",
        "consumers": ["reviewer"],
        "required_fields": ["artifact_type", "status", "commands"],
    },
    "ExecutableAcceptanceResult": {
        "producer": "programmer_executor",
        "consumers": ["reviewer"],
        "required_fields": ["artifact_type", "status", "generated_tests", "summary", "command"],
    },
    "ReviewFindings": {
        "producer": "reviewer",
        "consumers": ["human", "release_gate"],
        "required_fields": ["artifact_type", "findings", "risk_assessment", "recommendation"],
    },
    "CognitiveControlPlaneDecision": {
        "producer": "cognitive_control_plane",
        "consumers": ["role_pipeline", "semantic_reasoner", "human", "release_gate"],
        "required_fields": ["artifact_type", "layer", "artifact_promotion_gate", "role_transition", "semantic_escalation"],
    },
    "SemanticHypothesisRequest": {
        "producer": "cognitive_control_plane",
        "consumers": ["semantic_reasoner", "human"],
        "required_fields": ["artifact_type", "layer", "source_decision", "trigger_reasons", "question", "output_contract", "forbidden_actions", "return_path"],
    },
    "SemanticEvidencePack": {
        "producer": "cognitive_control_plane",
        "consumers": ["semantic_reasoner", "human"],
        "required_fields": ["artifact_type", "layer", "status", "prompt_facts", "control_facts", "forbidden_actions", "authority"],
    },
    "SemanticHypothesisProposal": {
        "producer": "semantic_reasoner",
        "consumers": ["cognitive_control_plane", "human"],
        "required_fields": ["artifact_type", "layer", "hypothesis_type", "proposal", "confidence", "evidence_refs", "risks", "return_to_gate"],
    },
    "L4SemanticValidationResult": {
        "producer": "cognitive_control_plane",
        "consumers": ["verified_system_package", "human", "stage2_template_curriculum"],
        "required_fields": ["artifact_type", "layer", "status", "source_request", "source_proposal", "contract_validation", "quality", "accepted_action", "decision"],
    },
    "Stage2TemplateBacklogItem": {
        "producer": "semantic_reasoner",
        "consumers": ["human", "engineer", "stage2_template_curriculum"],
        "required_fields": ["artifact_type", "status", "template_id", "purpose", "requires_human_review", "next_step"],
    },
    "Stage2TemplateAdmissionResult": {
        "producer": "stage2_template_admission",
        "consumers": ["human", "engineer", "verified_system_package"],
        "required_fields": ["artifact_type", "status", "case", "blockers", "invariants"],
    },
    "SemanticProposalReplay": {
        "producer": "semantic_replay",
        "consumers": ["human", "evaluation"],
        "required_fields": ["artifact_type", "status", "request", "proposal", "validation", "model_quality_mode", "outcome", "audit"],
    },
    "L45SemanticBenchmarkReport": {
        "producer": "l45_semantic_benchmark",
        "consumers": ["human", "evaluation"],
        "required_fields": ["artifact_type", "status", "model_quality_mode", "summary", "cases"],
    },
    "L45SemanticCorpusAnalyticsReport": {
        "producer": "l45_semantic_analytics",
        "consumers": ["human", "evaluation"],
        "required_fields": ["artifact_type", "status", "source_report", "summary", "boundary_counts", "action_counts"],
    },
    "L45RiskPolicyGapReport": {
        "producer": "l45_semantic_analytics",
        "consumers": ["human", "evaluation", "cognitive_control_plane"],
        "required_fields": ["artifact_type", "status", "source_report", "summary", "gaps", "policy_recommendations"],
    },
    "L45SemanticComparisonReport": {
        "producer": "l45_semantic_comparison",
        "consumers": ["human", "evaluation"],
        "required_fields": ["artifact_type", "status", "summary", "cases", "interpretation"],
    },
    "L45SemanticEvaluationSuiteReport": {
        "producer": "l45_semantic_eval_suite",
        "consumers": ["human", "evaluation"],
        "required_fields": ["artifact_type", "status", "config", "summary", "profiles"],
    },
    "L45ModelFailureAnalysisReport": {
        "producer": "l45_model_failure_analysis",
        "consumers": ["human", "evaluation"],
        "required_fields": ["artifact_type", "status", "summary", "failures", "recommendations"],
    },
    "L4DecisionTable": {
        "producer": "l4_decision_table",
        "consumers": ["cognitive_control_plane", "human"],
        "required_fields": ["artifact_type", "status", "rule_count", "rules", "principle"],
    },
    "PromptBoundaryClassification": {
        "producer": "prompt_boundary_classifier",
        "consumers": ["prompt_adequacy", "cognitive_control_plane", "human"],
        "required_fields": ["artifact_type", "status", "boundary", "confidence", "reasons", "recommended_action"],
    },
}


@dataclass(frozen=True)
class CapabilityContract:
    capability_id: str
    version: str
    input_schema_ref: str
    output_schema_ref: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    lifecycle_status: str
    side_effects: dict[str, Any]

    @property
    def executable(self) -> bool:
        return self.lifecycle_status in {"active", "degraded"}


class ContractRegistry:
    """Contract source of truth derived from manifests, schemas, and packet routes."""

    def __init__(self, capabilities: dict[str, CapabilityContract]) -> None:
        self.capabilities = capabilities
        self.packet_routes = set(LAYER_ROUTES)
        self.artifacts = {key: dict(value) for key, value in ARTIFACT_CONTRACTS.items()}

    @classmethod
    def from_capability_registry(cls, registry: CapabilityRegistry) -> "ContractRegistry":
        return cls(
            {
                capability_id: _capability_contract(capability)
                for capability_id, capability in registry.capabilities.items()
            }
        )

    @classmethod
    def load(cls, root: Path) -> "ContractRegistry":
        registry = CapabilityRegistry(root)
        registry.load()
        return cls.from_capability_registry(registry)

    def require_capability(self, capability_id: str) -> CapabilityContract:
        if capability_id not in self.capabilities:
            raise ContractRegistryError(f"missing capability contract: {capability_id}")
        contract = self.capabilities[capability_id]
        if not contract.executable:
            raise ContractRegistryError(
                f"capability contract is not executable: {capability_id}:{contract.lifecycle_status}"
            )
        _validate_schema_contract(capability_id, "input", contract.input_schema)
        _validate_schema_contract(capability_id, "output", contract.output_schema)
        return contract

    def validate_pipeline(self, pipeline: Pipeline) -> None:
        for node in pipeline.nodes:
            self.require_capability(node.capability)

    def validate_layer_packet(self, packet: dict[str, Any]) -> None:
        validate_packet(packet)
        route = (str(packet["source_layer"]), str(packet["target_layer"]), str(packet["packet_type"]))
        if route not in self.packet_routes:
            raise ContractRegistryError(f"missing packet route contract: {route}")

    def require_artifact(self, artifact_type: str) -> dict[str, Any]:
        if artifact_type not in self.artifacts:
            raise ContractRegistryError(f"missing artifact contract: {artifact_type}")
        return dict(self.artifacts[artifact_type])

    def validate_artifact(self, artifact: dict[str, Any]) -> None:
        artifact_type = str(artifact.get("artifact_type") or "")
        contract = self.require_artifact(artifact_type)
        missing = [field for field in contract["required_fields"] if field not in artifact]
        if missing:
            raise ContractRegistryError(
                f"{artifact_type} artifact missing fields: {', '.join(missing)}"
            )

    def catalog(self) -> dict[str, Any]:
        return {
            "capabilities": [
                {
                    "id": contract.capability_id,
                    "version": contract.version,
                    "input_schema_ref": contract.input_schema_ref,
                    "output_schema_ref": contract.output_schema_ref,
                    "lifecycle_status": contract.lifecycle_status,
                    "executable": contract.executable,
                    "side_effects": contract.side_effects,
                }
                for contract in sorted(self.capabilities.values(), key=lambda item: item.capability_id)
            ],
            "packet_routes": [
                {"source_layer": source, "target_layer": target, "packet_type": packet_type}
                for source, target, packet_type in sorted(self.packet_routes)
            ],
            "artifacts": [
                {"artifact_type": artifact_type, **contract}
                for artifact_type, contract in sorted(self.artifacts.items())
            ],
        }


def validate_pipeline_contracts(pipeline: Pipeline, registry: CapabilityRegistry) -> None:
    ContractRegistry.from_capability_registry(registry).validate_pipeline(pipeline)


def _capability_contract(capability: Capability) -> CapabilityContract:
    return CapabilityContract(
        capability_id=capability.id,
        version=capability.version,
        input_schema_ref=capability.input_schema_ref,
        output_schema_ref=capability.output_schema_ref,
        input_schema=capability.input_schema,
        output_schema=capability.output_schema,
        lifecycle_status=capability.lifecycle_status,
        side_effects=capability.side_effects,
    )


def _validate_schema_contract(capability_id: str, schema_name: str, schema: dict[str, Any]) -> None:
    if schema.get("type") != "object":
        raise ContractRegistryError(f"{capability_id} {schema_name} contract must be object schema")
    if not isinstance(schema.get("properties", {}), dict):
        raise ContractRegistryError(f"{capability_id} {schema_name} contract properties must be object")
    if not isinstance(schema.get("required", []), list):
        raise ContractRegistryError(f"{capability_id} {schema_name} contract required must be list")
    if schema.get("additionalProperties") is not False:
        raise ContractRegistryError(
            f"{capability_id} {schema_name} contract must set additionalProperties=false"
        )
