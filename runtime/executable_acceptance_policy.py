"""Config-backed policy helpers for executable acceptance samples."""

from __future__ import annotations

import json
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "config" / "executable_acceptance_policy.json"
_OVERRIDE: ContextVar[dict[str, Any] | None] = ContextVar("executable_acceptance_policy_override", default=None)


def load_executable_acceptance_policy(path: str | Path | None = None) -> dict[str, Any]:
    source = Path(path or DEFAULT_PATH)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "executable_acceptance_policy.v1":
        raise ValueError("Unsupported executable acceptance policy schema")
    return payload


def _policy() -> dict[str, Any]:
    return _OVERRIDE.get() or _cached_policy()


@lru_cache(maxsize=1)
def _cached_policy() -> dict[str, Any]:
    return load_executable_acceptance_policy()


def clear_executable_acceptance_policy_cache() -> None:
    _cached_policy.cache_clear()


def effective_executable_acceptance_policy() -> dict[str, Any]:
    """Return an isolated copy suitable for a sandbox worker payload."""
    return _clone(_policy())


@contextmanager
def temporary_executable_acceptance_policy(policy: dict[str, Any]):
    if policy.get("schema_version") != "executable_acceptance_policy.v1":
        raise ValueError("Unsupported temporary executable acceptance policy schema")
    token = _OVERRIDE.set(policy)
    try:
        yield
    finally:
        _OVERRIDE.reset(token)


def external_call_tokens() -> tuple[str, ...]:
    dependency = dict(_policy().get("dependency_policy") or {})
    return tuple(str(item) for item in dependency.get("external_call_tokens", []) if item)


def dependency_stub_policy() -> dict[str, Any]:
    from .promoted_executable_adapters import generated_module_profiles

    dependency = dict(_policy().get("dependency_policy") or {})
    stubs = dict(dependency.get("controlled_stubs") or {})
    metadata = dict(dependency.get("metadata_profiles") or {})
    generated = dict(dependency.get("generated_module_profiles") or {})
    return {
        "enabled": bool(stubs.get("enabled")),
        "max_missing_modules": int(stubs.get("max_missing_modules") or 0),
        "max_namespace_modules_per_dependency": int(
            stubs.get("max_namespace_modules_per_dependency") or 1
        ),
        "pre_stub_modules": tuple(str(item) for item in stubs.get("pre_stub_modules", []) if item),
        "stub_external_missing_modules": bool(stubs.get("stub_external_missing_modules")),
        "stub_object_features": tuple(str(item) for item in stubs.get("stub_object_features", []) if item),
        "metadata_profiles_enabled": bool(metadata.get("enabled")),
        "metadata_default_version": str(metadata.get("default_version") or "0.0.0"),
        "metadata_packages": tuple(str(item) for item in metadata.get("packages", []) if item),
        "generated_module_profiles_enabled": bool(generated.get("enabled")),
        "generated_module_profiles": {
            **generated_module_profiles(),
            **dict(generated.get("modules") or {}),
        },
    }


def method_fixture_policy() -> dict[str, Any]:
    policy = dict(_policy().get("method_fixture_policy") or {})
    return {
        "enabled": bool(policy.get("enabled")),
        "safe_uninitialized_instance": bool(policy.get("safe_uninitialized_instance")),
        "default_constructor_first": bool(policy.get("default_constructor_first")),
        "delegated_transport_methods": tuple(
            str(item) for item in policy.get("delegated_transport_methods", []) if item
        ),
        "delegated_transport_fixture": str(policy.get("delegated_transport_fixture") or ""),
        "numeric_receiver_calls": tuple(
            str(item) for item in policy.get("numeric_receiver_calls", []) if item
        ),
        "numeric_receiver_attribute_sample": int(
            policy.get("numeric_receiver_attribute_sample") or 1
        ),
        "required_mapping_key_sample": str(policy.get("required_mapping_key_sample") or "sample"),
        "required_mapping_value_fixture": str(
            policy.get("required_mapping_value_fixture") or "safe_method_attribute"
        ),
        "callable_attribute_fixtures": dict(policy.get("callable_attribute_fixtures") or {}),
        "boolean_condition_value": bool(policy.get("boolean_condition_value", False)),
        "nullable_comparison_enabled": bool(policy.get("nullable_comparison_enabled")),
        "mapping_value_sample": policy.get("mapping_value_sample", "sample"),
        "local_import_stub_functions": tuple(str(item) for item in policy.get("local_import_stub_functions", []) if item),
        "local_import_stub_methods": tuple(str(item) for item in policy.get("local_import_stub_methods", []) if item),
        "instance_attribute_profiles": dict(policy.get("instance_attribute_profiles") or {}),
        "recipes": dict(policy.get("recipes") or {}),
    }


def source_isolation_policy() -> dict[str, Any]:
    policy = dict(_policy().get("source_isolation_policy") or {})
    return {
        "stdlib_import_fallbacks": _clone(list(policy.get("stdlib_import_fallbacks") or [])),
        "effect_module_stubs": dict(policy.get("effect_module_stubs") or {}),
        "framework_contexts": _clone(dict(policy.get("framework_contexts") or {})),
        "global_factory_fixtures": dict(policy.get("global_factory_fixtures") or {}),
        "local_import_factory_fixtures": _clone(dict(policy.get("local_import_factory_fixtures") or {})),
        "global_symbol_fixtures": dict(policy.get("global_symbol_fixtures") or {}),
        "preserved_stdlib_class_bases": tuple(
            str(item) for item in policy.get("preserved_stdlib_class_bases", []) if item
        ),
    }


def structural_sample_policy() -> dict[str, Any]:
    return _clone(dict(_policy().get("structural_sample_policy") or {}))


def target_path_resolution_policy() -> dict[str, Any]:
    policy = dict(_policy().get("target_path_resolution") or {})
    return {
        "enabled": bool(policy.get("enabled")),
        "max_candidate_files": max(1, int(policy.get("max_candidate_files") or 1)),
        "max_unique_matches": max(1, int(policy.get("max_unique_matches") or 1)),
        "ignored_directories": tuple(str(item) for item in policy.get("ignored_directories", []) if item),
    }


def execution_context_policy() -> dict[str, Any]:
    policy = dict(_policy().get("execution_context") or {})
    return {
        "isolate_process_arguments": bool(policy.get("isolate_process_arguments")),
        "program_name": str(policy.get("program_name") or "acceptance-probe"),
    }


def foundation_evidence_policy() -> dict[str, Any]:
    policy = dict(_policy().get("foundation_evidence") or {})
    shadow = dict(policy.get("shadow_target_admission") or {})
    return {
        "isolated_process_timeout_seconds": max(
            1, int(policy.get("isolated_process_timeout_seconds") or 180)
        ),
        "isolated_transitive_effects": tuple(
            str(item) for item in policy.get("isolated_transitive_effects", []) if item
        ),
        "process_isolated_direct_effects": tuple(
            str(item) for item in policy.get("process_isolated_direct_effects", []) if item
        ),
        "process_isolated_direct_effect_profiles": {
            str(name): tuple(str(item) for item in effects if item)
            for name, effects in dict(policy.get("process_isolated_direct_effect_profiles") or {}).items()
        },
        "isolated_direct_effect_profiles": {
            str(name): tuple(str(item) for item in effects if item)
            for name, effects in dict(policy.get("isolated_direct_effect_profiles") or {}).items()
        },
        "isolated_delegated_effect_profiles": {
            str(name): tuple(str(item) for item in effects if item)
            for name, effects in dict(policy.get("isolated_delegated_effect_profiles") or {}).items()
        },
        "shadow_target_admission": {
            "enabled": bool(shadow.get("enabled")),
            "allowed_reselection_triggers": tuple(
                str(item) for item in shadow.get("allowed_reselection_triggers", []) if item
            ),
            "require_process_isolation": bool(shadow.get("require_process_isolation", True)),
            "require_complete_source_body": bool(shadow.get("require_complete_source_body", True)),
            "require_no_declared_effects": bool(shadow.get("require_no_declared_effects", True)),
            "require_no_direct_effects": bool(shadow.get("require_no_direct_effects", True)),
            "require_no_state_mutation": bool(shadow.get("require_no_state_mutation", True)),
        },
        "promoted_selection_policy_admission": _clone(dict(
            policy.get("promoted_selection_policy_admission") or {}
        )),
    }


def skipped_recovery_hint(reason: str) -> str:
    recovery = dict(_policy().get("skipped_recovery") or {})
    return str(recovery.get(reason) or "")


def sample_value(type_name: str, field_name: str = "", *, signature_mode: bool = False) -> Any:
    samples = dict(_policy().get("sample_values") or {})
    field = field_name.lower()
    lowered = type_name.lower()
    field_values = dict(samples.get("field_values") or {})
    if field in field_values:
        return _clone(field_values[field])
    if field in set(samples.get("nullable_fields") or []):
        return None
    if field in set(samples.get("optional_nullable_fields") or []) and ("none" in lowered or "optional" in lowered):
        return None
    for prefix, value in dict(samples.get("field_prefix_values") or {}).items():
        if field.startswith(str(prefix)):
            return _clone(value)
    fixture = _fixture_for(samples, field, lowered)
    if fixture:
        return {"__fixture__": fixture}
    type_rules = dict(samples.get("signature_type_contains" if signature_mode else "type_contains") or {})
    for token, value in type_rules.items():
        if str(token) in lowered:
            return _clone(value)
    return _clone(samples.get("default", "sample"))


def _fixture_for(samples: dict[str, Any], field: str, lowered_type: str) -> str:
    fixtures = dict(samples.get("fixture_fields") or {})
    if field in fixtures:
        return str(fixtures[field])
    field_types = dict(dict(samples.get("fixture_field_type_contains") or {}).get(field) or {})
    for token, fixture in field_types.items():
        if str(token) in lowered_type:
            return str(fixture)
    for token, fixture in dict(samples.get("fixture_type_contains") or {}).items():
        if str(token) in lowered_type:
            return str(fixture)
    return ""


def _clone(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))
