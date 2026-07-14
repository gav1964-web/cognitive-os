from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from runtime.contract_registry import ContractRegistry, ContractRegistryError
from runtime.layer_packets import intent_packet
from runtime.models import Pipeline, PipelineNode
from runtime.registry import CapabilityRegistry


@pytest.fixture()
def registry():
    root = Path(__file__).resolve().parents[2]
    reg = CapabilityRegistry(root)
    reg.reset_from_plugins()
    return reg


def test_contract_registry_builds_capability_and_packet_catalog(registry):
    contracts = ContractRegistry.from_capability_registry(registry)
    catalog = contracts.catalog()

    assert any(item["id"] == "normalize_text" for item in catalog["capabilities"])
    assert {"source_layer": "L4", "target_layer": "L3.5", "packet_type": "INTENT"} in catalog["packet_routes"]
    assert any(item["artifact_type"] == "TechnicalSpec" for item in catalog["artifacts"])


def test_contract_registry_rejects_non_executable_capability(registry):
    capability = registry.capabilities["normalize_text"]
    registry.capabilities["normalize_text"] = replace(capability, lifecycle_status="quarantined")
    contracts = ContractRegistry.from_capability_registry(registry)

    with pytest.raises(ContractRegistryError, match="not executable"):
        contracts.require_capability("normalize_text")


def test_contract_registry_validates_pipeline_capabilities(registry):
    pipeline = Pipeline(
        id="contracted",
        version="0.1.0",
        nodes=[PipelineNode(id="normalize", capability="normalize_text", input={"text": "$input.text"})],
        edges=[],
        retry_policy={},
    )

    ContractRegistry.from_capability_registry(registry).validate_pipeline(pipeline)


def test_contract_registry_validates_layer_packet_routes(registry):
    packet = intent_packet(
        correlation_id="goal_1",
        intent="ANALYZE_PROJECT",
        objective="Analyze project",
        constraints={"read_only": True},
        expected_artifacts=["project_map_report"],
        success_criteria=["report exists"],
    )

    ContractRegistry.from_capability_registry(registry).validate_layer_packet(packet)


def test_contract_registry_validates_artifact_api(registry):
    contracts = ContractRegistry.from_capability_registry(registry)
    contracts.validate_artifact(
        {
            "artifact_type": "ReviewFindings",
            "findings": [],
            "risk_assessment": [],
            "recommendation": "approve",
        }
    )
    contracts.validate_artifact(
        {
            "artifact_type": "CognitiveControlPlaneDecision",
            "layer": "L4.0",
            "artifact_promotion_gate": {"status": "passed"},
            "role_transition": {"next_action": "run_project_transform"},
            "semantic_escalation": {"l4_5_required": False},
        }
    )


def test_contract_registry_rejects_incomplete_artifact_api(registry):
    with pytest.raises(ContractRegistryError, match="missing fields"):
        ContractRegistry.from_capability_registry(registry).validate_artifact(
            {"artifact_type": "TechnicalSpec", "requirements": []}
        )
