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
