"""Shared predicates for concrete source-derived contract shapes."""

from __future__ import annotations

from typing import Any


WEAK_TYPES = {"", "any", "typing.any", "object", "inferredinput", "inferredoutput", "dispatchedresult"}


def concrete_output(contract: dict[str, Any]) -> bool:
    return bool(contract) and all(concrete_type(value) for value in contract.values())


def all_contract_shapes_concrete(inputs: dict[str, Any], outputs: dict[str, Any]) -> bool:
    return bool(inputs and outputs) and all(concrete_type(value) for value in [*inputs.values(), *outputs.values()])


def concrete_type(value: object) -> bool:
    text = str(value or "").strip().lower()
    return bool(text) and text not in WEAK_TYPES and not text.startswith("inferred")
