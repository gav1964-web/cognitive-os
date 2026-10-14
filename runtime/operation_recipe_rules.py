"""Load OperationRecipe interpretation rules from external configuration."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = ROOT / "config" / "operation_recipe_rules.json"


class OperationRecipeRulesError(RuntimeError):
    """Raised when OperationRecipe rules are invalid."""


@lru_cache(maxsize=1)
def load_operation_recipe_rules(path: str | None = None) -> dict[str, Any]:
    source = Path(path) if path else RULES_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "operation_recipe_rules.v1":
        raise OperationRecipeRulesError("operation recipe rules must use schema_version operation_recipe_rules.v1")
    if payload.get("status") != "active":
        raise OperationRecipeRulesError("operation recipe rules must be active")
    for field in (
        "allowed_interface_contracts",
        "allowed_transforms",
        "numeric",
        "text_transforms",
        "contract_profiles",
        "text_interface_markers",
        "text_interface_resolution",
        "l45_prompt",
    ):
        if field not in payload:
            raise OperationRecipeRulesError(f"operation recipe rules require {field}")
    allowed_contracts = {str(item) for item in payload["allowed_interface_contracts"]}
    allowed_transforms = {str(item) for item in payload["allowed_transforms"]}
    if "numeric_expression" not in allowed_transforms:
        raise OperationRecipeRulesError("operation recipe rules must allow numeric_expression")
    for transform, row in dict(payload.get("text_transforms") or {}).items():
        if transform not in allowed_transforms:
            raise OperationRecipeRulesError(f"text transform is not in allowed_transforms: {transform}")
        if not isinstance(row, dict) or not row.get("expression") or not isinstance(row.get("markers"), list):
            raise OperationRecipeRulesError(f"text transform requires expression and markers: {transform}")
    for contract in dict(payload.get("contract_profiles") or {}):
        if contract not in allowed_contracts:
            raise OperationRecipeRulesError(f"contract_profiles references unsupported contract: {contract}")
    for row in payload.get("text_interface_resolution") or []:
        if str(dict(row).get("interface_contract") or "") not in allowed_contracts:
            raise OperationRecipeRulesError("text_interface_resolution references unsupported contract")
    return payload


def allowed_interface_contracts(*, rules: dict[str, Any] | None = None) -> set[str]:
    payload = rules or load_operation_recipe_rules()
    return {str(item) for item in payload.get("allowed_interface_contracts", [])}


def allowed_transforms(*, rules: dict[str, Any] | None = None) -> set[str]:
    payload = rules or load_operation_recipe_rules()
    return {str(item) for item in payload.get("allowed_transforms", [])}
