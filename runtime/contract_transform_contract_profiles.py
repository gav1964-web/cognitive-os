"""Config-backed executable contract profiles for deterministic transforms."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "config" / "contract_transform_contract_profiles.json"


def load_contract_transform_contract_profiles(path: str | Path | None = None) -> dict[str, Any]:
    source = Path(path or DEFAULT_PATH)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "contract_transform_contract_profiles.v1":
        raise ValueError("Unsupported contract transform contract profiles schema")
    policy = dict(payload.get("admission_policy") or {})
    if policy.get("automatic_acceptance_mutation_allowed") is not False:
        raise ValueError("Contract transform profiles cannot allow automatic acceptance mutation")
    return payload


def profile_positive_case(
    *,
    target: str,
    input_contract: dict[str, Any],
    output_contract: dict[str, Any],
    catalog: dict[str, Any] | None = None,
    profile_id: str | None = None,
) -> dict[str, Any] | None:
    if _is_void_output(output_contract):
        return None
    payload = catalog or load_contract_transform_contract_profiles()
    target_tokens = _target_tokens(target)
    for profile in [dict(row) for row in list(payload.get("profiles") or [])]:
        exact_profile = bool(profile_id and profile.get("id") == profile_id)
        if profile_id and not exact_profile:
            continue
        if not exact_profile and not _matches_name(profile, target_tokens):
            continue
        field_name = _select_input_field(profile, input_contract)
        if not field_name or not _matches_output_type(profile, output_contract):
            continue
        return {
            "given": {field_name: profile.get("sample_input")},
            "expect": {str(profile.get("expect_key") or "return_value"): profile.get("expected_output")},
            "oracle": "literal_return_value_matches_contract_profile",
            "profile_id": str(profile.get("id") or ""),
            "operator_id": str(profile.get("operator_id") or ""),
        }
    return None


def contract_profile_hint(
    *,
    target: str,
    input_contract: dict[str, Any],
    output_contract: dict[str, Any],
    side_effects: list[Any] | None = None,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if side_effects or _is_void_output(output_contract):
        return None
    payload = catalog or load_contract_transform_contract_profiles()
    target_tokens = _target_tokens(target)
    for profile in [dict(row) for row in list(payload.get("profiles") or [])]:
        if not _matches_name(profile, target_tokens):
            continue
        field_name = _select_relaxed_input_field(profile, input_contract)
        if not field_name:
            continue
        output_field = next(iter(output_contract), "result")
        return {
            "input_contract": {**input_contract, field_name: _canonical_type(profile.get("input_types"), "str")},
            "output_contract": {output_field: _canonical_type(profile.get("output_types"), "str")},
            "contract_profile": {
                "id": str(profile.get("id") or ""),
                "operator_id": str(profile.get("operator_id") or ""),
                "source": "contract_transform_contract_profiles",
            },
        }
    return None


def contract_profile_for_operator(operator_id: str, catalog: dict[str, Any] | None = None) -> dict[str, Any] | None:
    payload = catalog or load_contract_transform_contract_profiles()
    for row in list(payload.get("profiles") or []):
        if isinstance(row, dict) and str(row.get("operator_id") or "") == operator_id:
            return dict(row)
    return None


def _target_tokens(target: str) -> set[str]:
    symbol = target.rsplit(":", 1)[-1]
    raw = re.split(r"[^a-zA-Z0-9]+", symbol.lower())
    tokens = {item for item in raw if item}
    tokens.update({"_".join(raw[index : index + 2]) for index in range(max(len(raw) - 1, 0))})
    return tokens


def _matches_name(profile: dict[str, Any], target_tokens: set[str]) -> bool:
    candidates = {str(item).lower() for item in list(profile.get("name_tokens") or [])}
    return bool(candidates & target_tokens)


def _select_input_field(profile: dict[str, Any], input_contract: dict[str, Any]) -> str | None:
    contract = {str(name): value for name, value in input_contract.items()}
    if not contract:
        return None
    for candidate in [str(item) for item in list(profile.get("input_field_candidates") or [])]:
        if candidate in contract and _type_matches(contract[candidate], profile.get("input_types")):
            return candidate
    if len(contract) == 1:
        name, type_name = next(iter(contract.items()))
        if _type_matches(type_name, profile.get("input_types")):
            return name
    return None


def _select_relaxed_input_field(profile: dict[str, Any], input_contract: dict[str, Any]) -> str | None:
    contract = {str(name): value for name, value in input_contract.items()}
    for candidate in [str(item) for item in list(profile.get("input_field_candidates") or [])]:
        if candidate in contract and (_type_matches(contract[candidate], profile.get("input_types")) or _is_inferred_type(contract[candidate])):
            return candidate
    if len(contract) == 1:
        name, type_name = next(iter(contract.items()))
        if _type_matches(type_name, profile.get("input_types")) or _is_inferred_type(type_name):
            return name
    return None


def _matches_output_type(profile: dict[str, Any], output_contract: dict[str, Any]) -> bool:
    contract = {str(name): value for name, value in output_contract.items()}
    if not contract:
        return False
    return any(_type_matches(type_name, profile.get("output_types")) for type_name in contract.values())


def _type_matches(type_name: Any, allowed: Any) -> bool:
    normalized = str(type_name).lower().replace(" ", "")
    return normalized in {str(item).lower().replace(" ", "") for item in list(allowed or [])}


def _is_inferred_type(type_name: Any) -> bool:
    return str(type_name).lower().startswith("inferred")


def _canonical_type(types: Any, fallback: str) -> str:
    values = [str(item) for item in list(types or []) if str(item)]
    return values[0] if values else fallback


def _is_void_output(output_contract: dict[str, Any]) -> bool:
    return any(str(value).lower() == "voidsideeffect" for value in output_contract.values())
