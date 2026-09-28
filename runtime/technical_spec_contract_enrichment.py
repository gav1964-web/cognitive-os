"""Contract enrichment helpers for TechnicalSpec extraction contracts."""

from __future__ import annotations

import ast
from typing import Any

from runtime.contract_transform_contract_profiles import contract_profile_hint
from runtime.contract_transform_mutation import observed_operator


def enrich_signature_contract(
    *,
    target: str,
    input_contract: dict[str, Any],
    output_contract: dict[str, Any],
    side_effects: list[Any] | None = None,
    source_snippet: str = "",
) -> dict[str, Any]:
    hint = contract_profile_hint(
        target=target,
        input_contract=input_contract,
        output_contract=output_contract,
        side_effects=list(side_effects or []),
    )
    if not hint:
        return {
            "input_contract": dict(input_contract),
            "output_contract": dict(output_contract),
            "contract_profile": {},
        }
    profile = dict(hint.get("contract_profile") or {})
    profile["oracle_authority"] = _oracle_authority(source_snippet, target, profile)
    return {
        "input_contract": dict(hint.get("input_contract") or input_contract),
        "output_contract": dict(hint.get("output_contract") or output_contract),
        "contract_profile": profile,
    }


def _oracle_authority(snippet: str, target: str, profile: dict[str, Any]) -> str:
    """Distinguish a naming hint from source-proven executable semantics."""
    if not snippet.strip():
        return "name_hint_only"
    try:
        tree = ast.parse(snippet)
    except SyntaxError:
        return "name_hint_only"
    symbol = target.rsplit(":", 1)[-1]
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name != symbol:
            continue
        args = [arg.arg for arg in node.args.args if arg.arg not in {"self", "cls"}]
        if len(args) == 1 and observed_operator(node, args[0]) == profile.get("operator_id"):
            return "source_observed_operator"
    return "name_hint_only"
