"""OperationRecipe API artifact for sandbox programmer routing."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .operation_recipe_rules import allowed_interface_contracts, allowed_transforms


@dataclass(frozen=True)
class OperationRecipe:
    artifact_type: str
    status: str
    interface_contract: str
    transform: str
    expression: str | None
    input_shape: str
    output_shape: str
    evidence: list[str]
    source: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def recipe_from_operation(operation: dict[str, Any], *, interface_contract: dict[str, Any]) -> dict[str, Any]:
    profile = str(operation.get("profile") or "")
    expression = operation.get("expression")
    transform = _transform_from_operation(operation)
    return OperationRecipe(
        artifact_type="OperationRecipe",
        status="ready",
        interface_contract=str(interface_contract.get("id") or ""),
        transform=transform,
        expression=str(expression) if expression is not None else None,
        input_shape=str(dict(interface_contract.get("input") or {}).get("shape") or ""),
        output_shape=str(dict(interface_contract.get("output") or {}).get("shape") or ""),
        evidence=[str(item) for item in operation.get("evidence", [])],
        source="sandbox_operation",
    ).to_dict()


def _transform_from_operation(operation: dict[str, Any]) -> str:
    operation_id = str(operation.get("operation") or "")
    profile = str(operation.get("profile") or "")
    expression = str(operation.get("expression") or "")
    if profile.startswith("numeric_args_"):
        return "numeric_expression"
    if "word_count" in operation_id or "len(text.split())" in expression:
        return "word_count"
    if "upper" in operation_id or ".upper()" in expression:
        return "uppercase"
    if "lower" in operation_id or ".lower()" in expression:
        return "lowercase"
    if "trim" in operation_id or ".strip()" in expression:
        return "trim"
    if "reverse" in operation_id or "[::-1]" in expression:
        return "reverse"
    return profile or operation_id


def validate_operation_recipe(recipe: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if recipe.get("artifact_type") != "OperationRecipe":
        errors.append("artifact_type_mismatch")
    if recipe.get("status") != "ready":
        errors.append("status_not_ready")
    if recipe.get("interface_contract") not in allowed_interface_contracts():
        errors.append("unsupported_interface_contract")
    if recipe.get("transform") not in allowed_transforms():
        errors.append("unsupported_transform")
    if recipe.get("transform") == "numeric_expression" and not recipe.get("expression"):
        errors.append("numeric_expression_missing_expression")
    return not errors, errors
