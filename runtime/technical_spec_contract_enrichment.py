"""Contract enrichment helpers for TechnicalSpec extraction contracts."""

from __future__ import annotations

from typing import Any

from runtime.contract_transform_contract_profiles import contract_profile_hint


def enrich_signature_contract(
    *,
    target: str,
    input_contract: dict[str, Any],
    output_contract: dict[str, Any],
    side_effects: list[Any] | None = None,
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
    return {
        "input_contract": dict(hint.get("input_contract") or input_contract),
        "output_contract": dict(hint.get("output_contract") or output_contract),
        "contract_profile": dict(hint.get("contract_profile") or {}),
    }
