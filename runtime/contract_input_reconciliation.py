"""Bind callable arguments to aggregate contract-family inputs."""

from __future__ import annotations

from typing import Any


def reconcile_input_contract(
    signature: dict[str, str], domain: dict[str, Any], bindings: dict[str, Any] | None = None
) -> dict[str, str]:
    if not signature:
        return _strings(domain)
    if not domain:
        return signature
    bound = _bound_contract(signature, domain, dict(bindings or {}))
    if bound:
        return bound
    signature_keys = list(signature)
    domain_keys = list(domain)
    if signature_keys == domain_keys:
        return {key: str(domain.get(key) or signature[key]) for key in signature_keys}
    if signature_keys == ["call_context"] and "call_context" in domain:
        return _strings(domain)
    if len(signature_keys) == len(domain_keys):
        return {
            signature_key: str(domain.get(domain_key) or signature[signature_key])
            for signature_key, domain_key in zip(signature_keys, domain_keys)
        }
    if {"consensus_input", "failure_evidence"} & set(map(str, domain)):
        return _strings(domain)
    return signature


def _bound_contract(signature: dict[str, str], domain: dict[str, Any], bindings: dict[str, Any]) -> dict[str, str]:
    if not bindings:
        return {}
    remaining = set(signature)
    result = {}
    for domain_key, aliases in bindings.items():
        explicit = [str(alias) for alias in list(aliases or []) if alias != "*remaining"]
        matched = [key for key in signature if key in explicit]
        if matched:
            result[str(domain_key)] = str(domain.get(domain_key) or signature[matched[0]])
            remaining.difference_update(matched)
    for domain_key, aliases in bindings.items():
        if "*remaining" in list(aliases or []) and remaining:
            result[str(domain_key)] = str(domain.get(domain_key) or "StructuredInput")
            remaining.clear()
    return result if not remaining and set(result) == set(domain) else {}


def _strings(value: dict[str, Any]) -> dict[str, str]:
    return {str(key): str(item) for key, item in value.items()}
