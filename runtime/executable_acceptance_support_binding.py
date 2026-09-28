"""Argument binding helpers for executable-acceptance support analysis."""

from __future__ import annotations

import inspect
from typing import Any

from .executable_acceptance_negative_case import missing_input_case_required
from .executable_acceptance_policy import sample_value


ACCEPTED_PARAM_KINDS = {
    inspect.Parameter.POSITIONAL_ONLY,
    inspect.Parameter.POSITIONAL_OR_KEYWORD,
    inspect.Parameter.KEYWORD_ONLY,
}


def positive_case_binding(func: object, target: str, obligations: list[dict[str, Any]], inferred: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return {"accepted": False, "mapping": {}, "defaults": {}, "overrides": {}, "evidence": {}, "drop_surplus_payload": False}
    mapping: dict[str, str] = {}
    defaults: dict[str, Any] = {}
    drop_surplus = False
    for row in obligations:
        if row.get("target") != target or row.get("kind") != "positive_contract_case":
            continue
        given = dict(row.get("given", {}))
        try:
            signature.bind(**given)
            mapping.update({key: key for key in given})
        except TypeError:
            adapted = _adapt_given_to_signature(signature, given)
            if adapted is None:
                return {"accepted": False, "mapping": {}, "defaults": {}, "overrides": {}, "evidence": {}, "drop_surplus_payload": False}
            drop_surplus = drop_surplus or (not adapted and bool(given))
            mapping.update({actual: source for actual, source in adapted.items()})
        defaults.update(_missing_required_samples(signature, mapping))
    accepts_keywords = any(
        param.kind == inspect.Parameter.VAR_KEYWORD
        for param in signature.parameters.values()
    )
    configured = dict(defaults)
    for row in obligations:
        if row.get("target") != target or row.get("kind") != "positive_contract_case":
            continue
        configured.update(dict(row.get("given") or {}))
    forced_linked_sources = _linked_contract_sources_requiring_override(
        dict(inferred or {}), configured
    )
    evidence = {
        name: dict(row)
        for name, row in dict(inferred or {}).items()
        if (name in signature.parameters or accepts_keywords)
        and (
            str(row.get("source") or "") in forced_linked_sources
            or not _weaker_than_configured_fixture(name, row, configured)
        )
    }
    overrides = {name: row["value"] for name, row in evidence.items()}
    return {"accepted": True, "mapping": mapping, "defaults": defaults, "overrides": overrides, "evidence": evidence, "drop_surplus_payload": drop_surplus}


def _linked_contract_sources_requiring_override(
    inferred: dict[str, dict[str, Any]], configured: dict[str, Any]
) -> set[str]:
    linked_sources = {"ast_tensor_window_contract"}
    required: set[str] = set()
    for name, row in inferred.items():
        source = str(row.get("source") or "")
        if source not in linked_sources or name not in configured:
            continue
        current = configured[name]
        inferred_value = row.get("value")
        shape_mismatch = (
            isinstance(inferred_value, list) and not isinstance(current, (list, tuple))
            or isinstance(inferred_value, dict)
            and "__fixture__" in inferred_value
            and not (isinstance(current, dict) and "__fixture__" in current)
        )
        if current == "sample" or shape_mismatch:
            required.add(source)
    return required


def _weaker_than_configured_fixture(
    name: str, inferred: dict[str, Any], defaults: dict[str, Any]
) -> bool:
    if name not in defaults:
        return False
    configured = defaults.get(name)
    inferred_value = inferred.get("value")
    source = str(inferred.get("source") or "")
    if configured == "sample" or isinstance(configured, (dict, list)) and not configured:
        return False
    if source == "ast_literal_membership_domain" and not configured and inferred_value:
        return False
    if source in {"ast_parameter_unpack", "ast_parameter_attribute_unpack", "ast_parameter_attributes"} and isinstance(
        configured, (str, int, float, bool)
    ):
        return False
    if (
        source == "ast_parameter_attribute_unpack"
        and isinstance(inferred_value, dict)
        and inferred_value.get("__fixture__") == "declared_model"
        and not (
            isinstance(configured, dict)
            and configured.get("__fixture__") == "declared_model"
        )
    ):
        return False
    if (
        source.startswith("ast_mapping_protocol:") or source == "ast_required_mapping_keys"
    ) and isinstance(configured, dict) and "__fixture__" in configured:
        return False
    return configured != inferred_value


def signature_needs_negative_case(
    func: object,
    target: str,
    obligations: list[dict[str, Any]],
    *,
    synthetic_input_keys: set[str] | None = None,
) -> bool:
    binding = positive_case_binding(func, target, obligations)
    ignored = set(synthetic_input_keys or set())
    effective_obligations = [
        {
            **row,
            "given": {
                key: value
                for key, value in dict(row.get("given") or {}).items()
                if key not in ignored
            },
        }
        if row.get("target") == target else row
        for row in obligations
    ]
    return missing_input_case_required(
        func, target, effective_obligations,
        drops_surplus_payload=bool(binding.get("drop_surplus_payload")),
    )


def _adapt_given_to_signature(signature: inspect.Signature, given: dict[str, Any]) -> dict[str, str] | None:
    params = [name for name, param in signature.parameters.items() if param.kind in ACCEPTED_PARAM_KINDS]
    if not params:
        return {}
    if set(given) <= set(params):
        return {key: key for key in given}
    exact = {name: name for name in params if name in given}
    required = {
        name
        for name, param in signature.parameters.items()
        if param.kind in ACCEPTED_PARAM_KINDS and param.default is inspect.Parameter.empty
    }
    if required <= set(exact):
        return exact
    if len(params) < len(given):
        return None
    return dict(zip(params, given))


def _missing_required_samples(signature: inspect.Signature, mapping: dict[str, str]) -> dict[str, Any]:
    defaults: dict[str, Any] = {}
    for name, param in signature.parameters.items():
        if name in mapping or param.default is not inspect.Parameter.empty:
            continue
        if param.kind not in ACCEPTED_PARAM_KINDS:
            continue
        defaults[name] = _signature_sample_value(name, str(param.annotation or ""))
    return defaults


def _signature_sample_value(name: str, annotation: str) -> Any:
    return sample_value(annotation, name, signature_mode=True)
